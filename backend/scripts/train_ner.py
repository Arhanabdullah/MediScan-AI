"""Train and evaluate a small spaCy NER model on synthetic prescription lines.

The model learns medicine/strength/frequency/duration/form spans. It is an
optional extractor: the regex pipeline remains the default until this model is
trained, evaluated and explicitly enabled in config/model.yaml.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

CONFIG = settings.model["ner"]
LABELS = tuple(CONFIG.get("label_map", {}).keys()) or (
    "MEDICINE", "STRENGTH", "FREQUENCY", "DURATION", "FORM"
)


def _require_spacy() -> Any:
    try:
        import spacy
        from spacy.training import Example
        from spacy.util import compounding, minibatch
    except ImportError as error:  # pragma: no cover - depends on optional package
        raise SystemExit("NER training requires spaCy: pip install spacy>=3.7,<4") from error
    return {
        "spacy": spacy,
        "Example": Example,
        "compounding": compounding,
        "minibatch": minibatch,
    }


def _load(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("samples", [])
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"No samples found in {path}")
    return payload


def _gold(sample: dict[str, Any]) -> set[tuple[int, int, str]]:
    return {(int(start), int(end), str(label)) for start, end, label in sample.get("entities", [])}


def _predicted(nlp: Any, text: str) -> set[tuple[int, int, str]]:
    doc = nlp(text)
    return {(entity.start_char, entity.end_char, entity.label_) for entity in doc.ents}


def _metrics(samples: list[dict[str, Any]], nlp: Any) -> dict[str, float]:
    true_positive = false_positive = false_negative = 0
    for sample in samples:
        gold = _gold(sample)
        predicted = _predicted(nlp, sample["text"])
        true_positive += len(gold & predicted)
        false_positive += len(predicted - gold)
        false_negative += len(gold - predicted)

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def train(
    data_path: Path,
    model_path: Path,
    metadata_path: Path,
    seed: int,
    epochs: int,
    dropout: float,
) -> dict[str, Any]:
    dependencies = _require_spacy()
    spacy = dependencies["spacy"]
    Example = dependencies["Example"]
    compounding = dependencies["compounding"]
    minibatch = dependencies["minibatch"]

    samples = _load(data_path)
    splits = {
        name: [item for item in samples if item.get("split") == name]
        for name in ("train", "validation", "test")
    }
    for name, items in splits.items():
        if not items:
            raise ValueError(f"Missing '{name}' split in {data_path}")

    nlp = spacy.blank("en")
    ner = nlp.add_pipe("ner")
    for label in LABELS:
        ner.add_label(label)

    examples = [
        Example.from_dict(
            nlp.make_doc(sample["text"]),
            {"entities": [tuple(entity) for entity in sample.get("entities", [])]},
        )
        for sample in splits["train"]
    ]
    nlp.initialize(lambda: examples)

    rng = random.Random(seed)
    for epoch in range(epochs):
        rng.shuffle(examples)
        losses: dict[str, float] = {}
        for batch in minibatch(examples, size=compounding(4.0, 32.0, 1.001)):
            nlp.update(batch, drop=dropout, losses=losses)
        print(f"epoch {epoch + 1}/{epochs} loss={losses.get('ner', 0.0):.4f}")

    metrics = {name: _metrics(items, nlp) for name, items in splits.items()}
    metadata: dict[str, Any] = {
        "name": "prescription-ner",
        "version": "1.0.0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "method": "spaCy blank English NER",
        "labels": list(LABELS),
        "epochs": epochs,
        "dropout": dropout,
        "split_counts": {name: len(items) for name, items in splits.items()},
        "metrics": metrics,
        "note": "Trained only on synthetic template text. Not a clinical accuracy claim.",
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    nlp.to_disk(model_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=ROOT / str(settings.model.get("data_dir", "data/model")) / "ner_samples.json",
    )
    parser.add_argument("--model-output", type=Path, default=ROOT / str(CONFIG["model_path"]))
    parser.add_argument("--metadata", type=Path, default=ROOT / str(CONFIG["metadata"]))
    parser.add_argument("--seed", type=int, default=int(settings.model.get("seed", 20261127)))
    parser.add_argument("--epochs", type=int, default=int(CONFIG["training"].get("epochs", 12)))
    parser.add_argument("--dropout", type=float, default=float(CONFIG["training"].get("dropout", 0.2)))
    args = parser.parse_args()
    train(args.data, args.model_output, args.metadata, args.seed, args.epochs, args.dropout)


if __name__ == "__main__":
    main()
