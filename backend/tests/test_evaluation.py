import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.evaluate import main as evaluate_main

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


def test_evaluate_script_accepts_custom_data(tmp_path: Path, capsys) -> None:
    samples = [
        {
            "ocr_text": "Cetirizine 10 mg once daily",
            "expected_text": "Cetirizine 10 mg once daily",
            "expected_medicines": ["Cetirizine"],
        }
    ]
    data_path = tmp_path / "my_samples.json"
    data_path.write_text(json.dumps(samples), encoding="utf-8")
    report_path = tmp_path / "report.json"

    assert evaluate_main(["--data", str(data_path), "--output", str(report_path)]) == 0
    output = json.loads(report_path.read_text(encoding="utf-8"))
    assert output["sample_count"] == 1
    assert output["sample_source"] == str(data_path)
    assert "Custom dataset" in output["note"]
    assert "Custom dataset" in capsys.readouterr().out
