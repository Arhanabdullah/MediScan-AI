"""Measure and tune fuzzy matching + confidence weights on synthetic labels.

Usage (from backend/):
    python scripts/tune_pipeline.py

The script reports measurements on synthetic fixtures. It never writes new
weights back to config, and its numbers are not real-prescription accuracy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from itertools import product
from pathlib import Path
from typing import Any

os.environ.setdefault("MEDISCAN_LOG_LEVEL", "WARNING")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services import medicines as medicine_service
from app.services.confidence import calculate_breakdown
from app.services.protocols import ConfidenceContext

DEFAULT_MATCHING = ROOT / "tests" / "fixtures" / "matching.json"
DEFAULT_CONFIDENCE = ROOT / "tests" / "fixtures" / "confidence.json"
DEFAULT_OUTPUT = ROOT / "reports" / "tuning_report.json"
WEIGHT_KEYS = ("ocr_engine", "text_length", "entity_coverage", "medicine_match")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _classification_metrics(pairs: list[tuple[str | None, str]]) -> dict[str, float]:
    """Macro precision/recall/F1 plus top-1 accuracy."""
    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)

    for predicted, expected in pairs:
        if predicted == expected:
            tp[expected] += 1
        else:
            if predicted:
                fp[predicted] += 1
            fn[expected] += 1

    labels = set(tp) | set(fp) | set(fn)
    precisions, recalls, f1s = [], [], []
    for label in labels:
        true_positive = tp[label]
        precision = true_positive / (true_positive + fp[label]) if true_positive + fp[label] else 0.0
        recall = true_positive / (true_positive + fn[label]) if true_positive + fn[label] else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)

    return {
        "top1_accuracy": round(sum(1 for p, e in pairs if p == e) / len(pairs), 4),
        "macro_precision": round(sum(precisions) / len(precisions), 4),
        "macro_recall": round(sum(recalls) / len(recalls), 4),
        "macro_f1": round(sum(f1s) / len(f1s), 4),
    }


def tune_matching(path: Path) -> dict[str, Any]:
    samples = _read_json(path)["samples"]
    original_bonus = medicine_service.MATCHING.get("strength_bonus", 0.05)
    results: list[dict[str, Any]] = []

    for bonus in (0.0, 0.025, 0.05, 0.1, 0.2):
        medicine_service.MATCHING["strength_bonus"] = bonus
        pairs: list[tuple[str | None, str]] = []
        for sample in samples:
            match = medicine_service.match_medicine(sample["text"], sample.get("strength"))
            pairs.append((match["id"] if match else None, sample["expected_id"]))
        results.append({"strength_bonus": bonus, **_classification_metrics(pairs)})

    medicine_service.MATCHING["strength_bonus"] = original_bonus
    best = max(results, key=lambda item: (item["macro_f1"], item["top1_accuracy"]))
    return {"samples": len(samples), "sweep": results, "best_by_macro_f1": best}


def _predict(sample: dict[str, Any], weights: dict[str, float], penalty: float) -> float:
    entities = {
        key: [{"label": key, "value": "sample", "confidence": 0.9}] for key in sample["entity_keys"]
    }
    medicines = [{"confidence": value} for value in sample["medicine_confidences"]]
    original_weights = dict(settings.confidence_weights)
    original_penalty = dict(settings.confidence_penalties)
    try:
        settings.confidence_weights = weights
        settings.confidence_penalties = {**original_penalty, "per_warning": penalty}
        ctx = ConfidenceContext(
            raw_text=sample["raw_text"],
            entities=entities,
            medicines=medicines,
            ocr_engine=sample["ocr_engine"],
            warnings=list(sample["warnings"]),
        )
        return calculate_breakdown(ctx).overall
    finally:
        settings.confidence_weights = original_weights
        settings.confidence_penalties = original_penalty


def tune_confidence(path: Path) -> dict[str, Any]:
    samples = _read_json(path)["samples"]
    current_weights = dict(settings.confidence_weights)
    current_penalty = float(settings.confidence_penalties.get("per_warning", 0.05))

    def mae(weights: dict[str, float], penalty: float) -> float:
        errors = [abs(_predict(sample, weights, penalty) - sample["target"]) for sample in samples]
        return round(sum(errors) / len(errors), 4)

    baseline = mae(current_weights, current_penalty)

    # Coarse grid over weights that sum to 1 (in 0.1 steps) and warning penalty.
    best: dict[str, Any] | None = None
    for parts in product(range(11), repeat=3):
        fourth = 10 - sum(parts)
        if fourth < 0:
            continue
        candidate = dict(zip(WEIGHT_KEYS, [value / 10 for value in (*parts, fourth)]))
        for penalty in (0.0, 0.025, 0.05, 0.1):
            score = mae(candidate, penalty)
            if best is None or score < best["mae"]:
                best = {"weights": candidate, "per_warning": penalty, "mae": score}

    return {
        "samples": len(samples),
        "current_weights": current_weights,
        "current_per_warning": current_penalty,
        "current_mae": baseline,
        "best_on_synthetic_labels": best,
        "caveat": "Grid search on synthetic labels; do not deploy without real annotated data.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matching-fixtures", type=Path, default=DEFAULT_MATCHING)
    parser.add_argument("--confidence-fixtures", type=Path, default=DEFAULT_CONFIDENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args(argv)

    report = {
        "disclaimer": "Synthetic fixtures only - not a real-prescription accuracy claim.",
        "matching": tune_matching(args.matching_fixtures),
        "confidence": tune_confidence(args.confidence_fixtures),
    }

    matching = report["matching"]
    confidence = report["confidence"]
    print(f"Matching: best strength_bonus={matching['best_by_macro_f1']['strength_bonus']} "
          f"(macro F1={matching['best_by_macro_f1']['macro_f1']}, "
          f"baseline F1={matching['sweep'][2]['macro_f1']})")
    print(f"Confidence: current MAE={confidence['current_mae']}, "
          f"best synthetic MAE={confidence['best_on_synthetic_labels']['mae']}")
    print(report["disclaimer"])

    if not args.no_save:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
