"""Generate reproducible synthetic datasets for the trained-model experiments.

All text is derived from the authoritative medicine catalogue and fixed
prescription templates. No patient data or real prescriptions are used.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services.medicines import get_repository

DATA_DIR = ROOT / str(settings.model.get("data_dir", "data/model"))
SEED = int(settings.model.get("seed", 20261127))

SUBSTITUTIONS = {
    "a": "o", "e": "a", "i": "e", "o": "a", "u": "o",
    "c": "s", "s": "c", "f": "t", "t": "f", "m": "n", "n": "m",
}


def _split_indices(count: int, rng: random.Random, validation: float, test: float) -> dict[int, str]:
    indices = list(range(count))
    rng.shuffle(indices)
    test_size = int(count * test)
    validation_size = int(count * validation)
    result = {index: "train" for index in indices}
    for index in indices[:test_size]:
        result[index] = "test"
    for index in indices[test_size : test_size + validation_size]:
        result[index] = "validation"
    return result


def _corrupt(value: str, rng: random.Random) -> tuple[str, str]:
    """Apply one OCR-like character error, returning (text, operation)."""
    operation = rng.choice(("substitute", "delete", "swap", "insert", "split"))
    letters = list(value.lower())
    if len(letters) < 3:
        operation = "substitute"
    position = rng.randrange(len(letters))

    if operation == "substitute":
        letters[position] = SUBSTITUTIONS.get(letters[position], rng.choice("aeinost"))
    elif operation == "delete":
        letters.pop(position)
    elif operation == "swap" and position + 1 < len(letters):
        letters[position], letters[position + 1] = letters[position + 1], letters[position]
    elif operation == "insert":
        letters.insert(position, rng.choice("cilmnos"))
    elif operation == "split":
        letters.insert(position, " ")
    else:
        operation = "substitute"
        letters[position] = SUBSTITUTIONS.get(letters[position], "a")

    text = "".join(letters)
    return (text if text.strip() and text != value.lower() else value.lower()), operation


def build_medicine_typos(
    variants_per_label: int,
    rng: random.Random,
    validation: float,
    test: float,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for medicine in get_repository().all():
        search_names = [name for name in medicine.search_names if len(name) > 2]
        if not search_names:
            continue
        for index in range(variants_per_label):
            source = search_names[index % len(search_names)]
            if index == 0:
                text, operation = source.lower(), "exact"
            else:
                text, operation = _corrupt(source, rng)
            samples.append(
                {
                    "text": text,
                    "label": medicine.name,
                    "source_name": source,
                    "operation": operation,
                }
            )

    splits = _split_indices(len(samples), rng, validation, test)
    for index, sample in enumerate(samples):
        sample["split"] = splits[index]
    return {
        "metadata": {
            "description": "Synthetic OCR-style spelling variants from the medicine catalogue.",
            "seed": SEED,
            "count": len(samples),
            "classes": sorted({sample["label"] for sample in samples}),
        },
        "samples": samples,
    }


def _segments_to_example(
    segments: list[tuple[str, str | None]],
    split: str,
) -> dict[str, Any]:
    text_parts: list[str] = []
    entities: list[list[Any]] = []
    cursor = 0
    for part, label in segments:
        text_parts.append(part)
        if label:
            entities.append([cursor, cursor + len(part), label])
        cursor += len(part) + 1
    return {"text": " ".join(text_parts), "entities": entities, "split": split}


def build_ner_samples(
    samples_per_template: int,
    rng: random.Random,
    validation: float,
    test: float,
) -> dict[str, Any]:
    medicines = get_repository().all()
    frequencies = ("once daily", "twice daily", "three times daily", "at bedtime", "if needed")
    durations = ("5 days", "7 days", "10 days", "14 days")

    def make_segments(medicine: Any, style: int) -> list[tuple[str, str | None]]:
        source = rng.choice([name for name in medicine.search_names if name] or [medicine.name])
        strength = medicine.strength or "500 mg"
        form = medicine.form or "tablet"
        frequency = rng.choice(frequencies)
        duration = rng.choice(durations)
        if style == 0:
            return [
                ("Take", None), ("1", None), (form, "FORM"), (source, "MEDICINE"),
                (strength, "STRENGTH"), (frequency, "FREQUENCY"), ("for", None),
                (duration, "DURATION"),
            ]
        if style == 1:
            return [
                ("Name:", None), (source, "MEDICINE"), (strength, "STRENGTH"),
                (form, "FORM"), (frequency, "FREQUENCY"),
            ]
        if style == 2:
            return [
                ("1.", None), (source, "MEDICINE"), (strength, "STRENGTH"),
                (form, "FORM"), ("-", None), (frequency, "FREQUENCY"),
            ]
        if style == 3:
            return [
                (source, "MEDICINE"), (strength, "STRENGTH"), (form, "FORM"),
                ("twice", None), ("daily", None), ("for", None), (duration, "DURATION"),
            ]
        return [
            ("Rx", None), ("1", None), (source, "MEDICINE"), (strength, "STRENGTH"),
            ("capsule", "FORM"), (frequency, "FREQUENCY"),
        ]

    samples: list[dict[str, Any]] = []
    for style in range(5):
        for medicine in medicines:
            for _ in range(samples_per_template):
                samples.append(_segments_to_example(make_segments(medicine, style), "train"))

    splits = _split_indices(len(samples), rng, validation, test)
    for index, sample in enumerate(samples):
        sample["split"] = splits[index]
    return {
        "metadata": {
            "description": "Synthetic prescription lines with exact entity offsets.",
            "seed": SEED,
            "count": len(samples),
            "labels": ["MEDICINE", "STRENGTH", "FREQUENCY", "DURATION", "FORM"],
        },
        "samples": samples,
    }


def _write(name: str, payload: dict[str, Any]) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {path} ({payload['metadata']['count']} samples)")
    return path


def main() -> None:
    rng = random.Random(SEED)
    corrector_config = settings.model["medicine_corrector"]["training"]
    ner_config = settings.model["ner"]["training"]

    typos = build_medicine_typos(
        int(corrector_config.get("variants_per_label", 24)),
        rng,
        float(corrector_config.get("validation_fraction", 0.15)),
        float(corrector_config.get("test_fraction", 0.15)),
    )
    ner = build_ner_samples(
        int(ner_config.get("samples_per_template", 20)),
        rng,
        float(ner_config.get("validation_fraction", 0.15)),
        float(ner_config.get("test_fraction", 0.15)),
    )

    _write("medicine_typos.json", typos)
    _write("ner_samples.json", ner)
    print("Synthetic data only - not a clinical dataset.")


if __name__ == "__main__":
    main()
