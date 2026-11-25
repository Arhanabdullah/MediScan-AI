"""Benchmark OCR engines with CER/WER on labelled synthetic images.

Usage (from backend/):
    python scripts/benchmark_ocr.py
    python scripts/benchmark_ocr.py --engines tesseract,demo --output reports/ocr_benchmark.json

Results are measured on synthetic fixtures in this repository. They are NOT
an accuracy claim for real prescriptions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("MEDISCAN_LOG_LEVEL", "WARNING")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from rapidfuzz.distance import Levenshtein
except ImportError:  # pragma: no cover - fallback for minimal environments
    Levenshtein = None  # type: ignore[assignment]

from app.services.ocr import available_engines, extract_text, preferred_preprocess_mode
from app.services.preprocess import preprocess_image

DEFAULT_DATA = ROOT / "tests" / "fixtures" / "ocr" / "labels.json"
DEFAULT_OUTPUT = ROOT / "reports" / "ocr_benchmark.json"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _distance(left: str, right: str) -> int:
    if Levenshtein is not None:
        return Levenshtein.distance(left, right)
    # Small pure-Python fallback so the benchmark runs without RapidFuzz.
    previous = list(range(len(right) + 1))
    for i, char_left in enumerate(left, start=1):
        current = [i]
        for j, char_right in enumerate(right, start=1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_left != char_right))
            )
        previous = current
    return previous[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate (lower is better)."""
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return round(min(1.0, _distance(reference, hypothesis) / len(reference)), 4)


def wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate (lower is better)."""
    ref_words, hyp_words = reference.split(), hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    return round(min(1.0, _distance(" ".join(ref_words), " ".join(hyp_words)) / len(ref_words)), 4)


def _load_samples(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    samples = data.get("samples") if isinstance(data, dict) else data
    if not isinstance(samples, list) or not samples:
        raise ValueError(f"No samples found in {path}")
    return samples


def run_benchmark(
    data_path: Path = DEFAULT_DATA,
    engines: list[str] | None = None,
) -> dict[str, Any]:
    samples = _load_samples(data_path)
    availability = available_engines()
    selected = engines or [name for name, available in availability.items() if available]

    report: dict[str, Any] = {
        "fixture_file": str(data_path.relative_to(ROOT)) if data_path.is_relative_to(ROOT) else str(data_path),
        "sample_count": len(samples),
        "disclaimer": "Synthetic fixtures only - not a real-prescription accuracy claim.",
        "engines": {},
    }

    for name in selected:
        if not availability.get(name, False):
            report["engines"][name] = {"error": "engine not installed"}
            continue

        mode = preferred_preprocess_mode(name)
        per_sample: list[dict[str, Any]] = []
        cers: list[float] = []
        wers: list[float] = []

        for sample in samples:
            image_path = data_path.parent / sample["image"]
            processed, _, _ = preprocess_image(image_path.read_bytes(), mode=mode)
            result = extract_text(processed, name)
            reference = normalize_text(sample["text"])
            hypothesis = normalize_text(result.text)
            sample_cer, sample_wer = cer(reference, hypothesis), wer(reference, hypothesis)
            cers.append(sample_cer)
            wers.append(sample_wer)
            per_sample.append(
                {
                    "image": sample["image"],
                    "engine": result.engine,
                    "cer": sample_cer,
                    "wer": sample_wer,
                    "warnings": result.warnings,
                }
            )

        report["engines"][name] = {
            "preprocess_mode": mode,
            "mean_cer": round(sum(cers) / len(cers), 4),
            "mean_wer": round(sum(wers) / len(wers), 4),
            "samples": per_sample,
        }

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Labelled fixture JSON")
    parser.add_argument("--engines", help="Comma-separated engine names (default: all available)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Report JSON path")
    parser.add_argument("--no-save", action="store_true", help="Print only, do not write a report")
    args = parser.parse_args(argv)

    engines = [item.strip() for item in args.engines.split(",") if item.strip()] if args.engines else None
    report = run_benchmark(args.data, engines)

    print(f"OCR benchmark on {report['sample_count']} synthetic sample(s)")
    print(f"{'engine':<12} {'preprocess':<12} {'CER':>8} {'WER':>8}")
    for name, result in report["engines"].items():
        if "error" in result:
            print(f"{name:<12} {'-':<12} {result['error']:>17}")
            continue
        print(
            f"{name:<12} {result['preprocess_mode']:<12} {result['mean_cer']:>8.4f} {result['mean_wer']:>8.4f}"
        )
    print(report["disclaimer"])

    if not args.no_save:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
