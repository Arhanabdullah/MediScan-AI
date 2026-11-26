"""Train and evaluate the synthetic OCR-typo medicine classifier.

Produces a versioned joblib artifact plus a JSON metrics card. The held-out
test split is never used for fitting or hyperparameter selection.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

try:
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support
    from sklearn.pipeline import Pipeline
except ImportError as error:  # pragma: no cover - depends on optional packages
    raise SystemExit(
        "Training requires scikit-learn and joblib: pip install -r requirements.txt"
    ) from error

CONFIG = settings.model["medicine_corrector"]


def _load(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("samples", [])
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"No samples found in {path}")
    return payload


def _xy(samples: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    return [str(item["text"]) for item in samples], [str(item["label"]) for item in samples]


def _metrics(y_true: list[str], y_pred: list[str]) -> dict[str, float]:
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )
    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
    }


def train(data_path: Path, artifact_path: Path, metadata_path: Path, seed: int) -> dict[str, Any]:
    samples = _load(data_path)
    splits = {
        name: [item for item in samples if item.get("split") == name]
        for name in ("train", "validation", "test")
    }
    for name, items in splits.items():
        if not items:
            raise ValueError(f"Missing '{name}' split in {data_path}")

    x_train, y_train = _xy(splits["train"])
    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char",
                    ngram_range=(2, 5),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(max_iter=2000, C=4.0, random_state=seed),
            ),
        ]
    )
    pipeline.fit(x_train, y_train)

    evaluated = {
        name: _metrics(y_true := _xy(items)[1], pipeline.predict(_xy(items)[0]))
        for name, items in splits.items()
        if name != "train"
    }
    evaluated["train"] = _metrics(y_train, pipeline.predict(x_train))

    metadata: dict[str, Any] = {
        "name": "medicine-corrector",
        "version": "1.0.0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "method": "char n-gram TF-IDF + logistic regression",
        "labels": sorted(set(y_train)),
        "split_counts": {name: len(items) for name, items in splits.items()},
        "metrics": evaluated,
        "note": "Trained only on synthetic catalogue spelling variants. Not a clinical accuracy claim.",
    }

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "version": metadata["version"]}, artifact_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=ROOT / str(settings.model.get("data_dir", "data/model")) / "medicine_typos.json",
    )
    parser.add_argument("--artifact", type=Path, default=ROOT / str(CONFIG["artifact"]))
    parser.add_argument("--metadata", type=Path, default=ROOT / str(CONFIG["metadata"]))
    parser.add_argument("--seed", type=int, default=int(settings.model.get("seed", 20261127)))
    args = parser.parse_args()
    train(args.data, args.artifact, args.metadata, args.seed)


if __name__ == "__main__":
    main()
