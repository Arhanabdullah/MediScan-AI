"""Phase M1 tests: synthetic datasets, trained inference and optional wiring."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.loader import load_model_config
from app.main import app
from app.services.ml import MedicineCorrector, reset_medicine_corrector, set_medicine_corrector
from app.services.medicines.matcher import MODEL_CONFIG, _combined_score, match_medicine
from app.services.nlp import TrainedNerExtractor
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def _restore_corrector() -> None:
    yield
    set_medicine_corrector(None)


class FakePipeline:
    classes_ = np.array(["Amoxicillin", "Paracetamol"])

    def predict_proba(self, values: list[str]) -> np.ndarray:
        return np.array([[0.15, 0.85] for _ in values])


class StubCorrector:
    def __init__(self, prediction: tuple[str, float]) -> None:
        self.prediction = prediction

    def predict(self, text: str) -> tuple[str, float]:
        return self.prediction


def test_model_config_is_disabled_by_default() -> None:
    config = load_model_config()
    assert config["medicine_corrector"]["enabled"] is False
    assert config["ner"]["enabled"] is False
    assert config["ner"]["label_map"]["MEDICINE"] == "medicine_names"


def test_generators_produce_disjoint_synthetic_splits() -> None:
    from scripts.generate_model_data import build_medicine_typos, build_ner_samples

    rng = random.Random(7)
    typos = build_medicine_typos(6, rng, 0.25, 0.25)
    ner = build_ner_samples(2, rng, 0.25, 0.25)

    typo_splits = {item["split"] for item in typos["samples"]}
    ner_splits = {item["split"] for item in ner["samples"]}
    assert typo_splits == {"train", "validation", "test"}
    assert ner_splits == {"train", "validation", "test"}
    assert all(item["label"] for item in typos["samples"])
    assert all(item["entities"] for item in ner["samples"])


def test_medicine_corrector_respects_threshold_and_availability() -> None:
    corrector = MedicineCorrector(
        FakePipeline(),
        {"name": "test-corrector", "version": "1.0"},
        {"enabled": True, "min_score": 0.6},
    )
    assert corrector.available() is True
    assert corrector.predict("Paracetmol") == ("Paracetamol", 0.85)

    strict = MedicineCorrector(FakePipeline(), {}, {"enabled": True, "min_score": 0.9})
    assert strict.predict("Paracetmol") is None
    assert MedicineCorrector(None).predict("Paracetmol") is None


def test_matcher_blends_trained_suggestion(monkeypatch: pytest.MonkeyPatch) -> None:
    base = _combined_score("paracetmol", ("amoxicillin",))
    boosted = _combined_score("paracetmol", ("amoxicillin",), ("Amoxicillin", 0.95))
    assert boosted > base
    # A suggestion for a different catalogue entry must not change the score.
    assert _combined_score("paracetmol", ("amoxicillin",), ("Paracetamol", 0.95)) == base

    monkeypatch.setitem(MODEL_CONFIG, "enabled", True)
    set_medicine_corrector(StubCorrector(("Paracetamol", 0.99)))
    match = match_medicine("Paracetmol")
    assert match is not None
    assert match["matched_name"] == "Paracetamol"
    reset_medicine_corrector()


def test_trained_ner_extractor_maps_labels_when_enabled() -> None:
    extractor = TrainedNerExtractor(
        {
            "enabled": True,
            "model_path": "unused",
            "confidence": 0.8,
            "label_map": {"MEDICINE": "medicine_names", "STRENGTH": "strengths"},
        }
    )
    assert TrainedNerExtractor({"enabled": False}).available() is False
    assert extractor.available() is False  # path missing

    extractor.available = lambda: True  # type: ignore[method-assign]
    extractor._nlp = lambda text: SimpleNamespace(
        ents=[
            SimpleNamespace(text="Paracetamol", label_="MEDICINE"),
            SimpleNamespace(text="500 mg", label_="STRENGTH"),
            SimpleNamespace(text="unknown", label_="OTHER"),
        ]
    )
    result = extractor.extract("Paracetamol 500 mg")
    assert [item["value"] for item in result["medicine_names"]] == ["Paracetamol"]
    assert [item["value"] for item in result["strengths"]] == ["500 mg"]
    assert "other" not in result


def test_corrector_training_writes_artifact_and_metrics(tmp_path: Path) -> None:
    from scripts.train_medicine_corrector import train as train_corrector

    samples = []
    for split in ("train", "validation", "test"):
        samples.extend(
            [
                {"text": "paracetmol", "label": "Paracetamol", "split": split},
                {"text": "Paracetamol 500 mg", "label": "Paracetamol", "split": split},
                {"text": "amoxcilin", "label": "Amoxicillin", "split": split},
                {"text": "Amoxicillin 500 mg", "label": "Amoxicillin", "split": split},
            ]
        )
    data = tmp_path / "samples.json"
    data.write_text(json.dumps({"samples": samples}), encoding="utf-8")

    metadata = train_corrector(
        data,
        tmp_path / "corrector.joblib",
        tmp_path / "corrector.json",
        seed=42,
    )
    assert (tmp_path / "corrector.joblib").exists()
    assert metadata["metrics"]["test"]["accuracy"] >= 0.0
    assert set(metadata["labels"]) == {"Amoxicillin", "Paracetamol"}


def test_model_info_exposes_trained_model_status() -> None:
    response = client.get("/api/model-info")
    assert response.status_code == 200
    payload = response.json()
    assert "trained_models" in payload
    assert set(payload["trained_models"]) == {"medicine_corrector", "ner"}
