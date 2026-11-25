from collections import Counter

from app.services.evaluation import (
    character_error_rate,
    classification_metrics,
    evaluate_samples,
    word_error_rate,
)


def test_error_rates() -> None:
    assert character_error_rate("paracetamol", "paracetamol") == 0.0
    assert character_error_rate("paracetamol", "paracetmol") > 0
    assert word_error_rate("take one tablet", "take one tablet") == 0.0
    assert word_error_rate("take one tablet", "take two tablet") > 0


def test_classification_metrics() -> None:
    metrics = classification_metrics(Counter(["A", "B"]), Counter(["A", "C"]))
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5


def test_synthetic_evaluation() -> None:
    samples = [
        {
            "ocr_text": "Paracetmol 500 mg twice daily",
            "expected_text": "Paracetamol 500 mg twice daily",
            "expected_medicines": ["Paracetamol"],
        }
    ]
    result = evaluate_samples(samples)
    assert result["sample_count"] == 1
    assert 0 <= result["medicine_f1"] <= 1
    assert "Not a clinical accuracy claim" in result["note"]
