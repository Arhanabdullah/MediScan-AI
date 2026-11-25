import io
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from app.config import settings
from app.services import medicines as medicine_service
from app.services.confidence import calculate_breakdown
from app.services.logging import JSONFormatter, correlation_id
from app.services.nlp import extract_entities
from app.services.ocr import OCRRegistry, extract_text, resolve_engine
from app.services.preprocess import preprocess_image
from app.services.protocols import ConfidenceContext, OCREngine, PreprocessResult
import benchmark_ocr


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (120, 80), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_config_files_are_loaded() -> None:
    assert "strength" in settings.patterns["regex"]
    assert sum(settings.confidence_weights.values()) == pytest.approx(1.0)
    assert "strength_bonus" in settings.matching
    assert "demo-fallback" in settings.ocr_scores
    assert "Amoxicillin" in settings.demo_text


def test_named_tuple_results_keep_tuple_api() -> None:
    result = preprocess_image(_png_bytes())
    assert isinstance(result, PreprocessResult)
    processed, size, warnings = result
    assert isinstance(processed, np.ndarray)
    assert isinstance(size, dict)
    assert isinstance(warnings, list)


def test_preprocess_modes() -> None:
    binary = preprocess_image(_png_bytes(), mode="threshold").image
    enhanced = preprocess_image(_png_bytes(), mode="enhanced").image
    assert binary.ndim == enhanced.ndim == 2
    assert set(np.unique(binary)).issubset({0, 255})
    assert enhanced.max() > 0
    with pytest.raises(ValueError):
        preprocess_image(_png_bytes(), mode="unknown")


def test_ocr_registry_and_explicit_unavailable_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    assert {"tesseract", "easyocr", "paddleocr", "demo"} <= set(OCRRegistry.names())
    assert isinstance(resolve_engine("demo"), OCREngine)
    assert resolve_engine("demo").name == "demo-fallback"

    result = extract_text(np.zeros((40, 40), dtype=np.uint8), "demo")
    assert result.engine == "demo-fallback"
    assert result.text == settings.demo_text.strip()

    tesseract = OCRRegistry.get("tesseract")
    assert tesseract is not None
    monkeypatch.setattr(tesseract, "available", lambda: False)
    unavailable = extract_text(np.zeros((40, 40), dtype=np.uint8), "tesseract")
    assert unavailable.engine == "tesseract-unavailable"
    assert unavailable.text == ""


def test_entity_extraction_reads_configured_patterns() -> None:
    fixture = (ROOT / "tests" / "fixtures" / "demo_prescription.txt").read_text(encoding="utf-8")
    entities = extract_entities(fixture)
    assert len(entities["medicine_names"]) == 3
    assert entities["strengths"]
    assert entities["frequencies"]
    assert entities["forms"]


def test_medicine_matching_and_strength_bonus() -> None:
    assert medicine_service.normalize("1. Paracetmol!") == "paracetmol"
    match = medicine_service.match_medicine("Paracetmol", "650 mg")
    assert match is not None
    assert match["id"] == "paracetamol-650"
    assert match["match_score"] >= medicine_service.match_medicine("Paracetmol")["match_score"]
    assert medicine_service.match_medicine("Paracetmol", min_score=1.01) is None

    entities = extract_entities("1. Paracetmol 650 mg tablet\n2. Amoxil 500 mg capsule")
    matches = medicine_service.match_entities(entities)
    assert [item["id"] for item in matches] == ["paracetamol-650", "amoxicillin-500"]


def test_confidence_breakdown_is_explainable() -> None:
    ctx = ConfidenceContext(
        raw_text="x" * 200,
        entities={"medicine_names": [{"value": "Paracetamol"}], "strengths": []},
        medicines=[{"confidence": 0.9}],
        ocr_engine="tesseract",
        warnings=[],
    )
    breakdown = calculate_breakdown(ctx)
    assert 0.0 <= breakdown.overall <= 0.99
    assert set(breakdown.components) == set(settings.confidence_weights)
    assert breakdown.warnings_penalty == 0.0

    empty = calculate_breakdown(
        ConfidenceContext(raw_text="", entities={}, medicines=[], ocr_engine="demo-fallback", warnings=[])
    )
    assert empty.overall == 0.0


def test_json_logging_includes_correlation_id() -> None:
    correlation_id.set("test-correlation")
    record = logging.LogRecord(
        name="mediscan.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="stage_end",
        args=(),
        exc_info=None,
    )
    record.stage = "preprocess"
    payload = json.loads(JSONFormatter().format(record))
    assert payload["correlation_id"] == "test-correlation"
    assert payload["stage"] == "preprocess"


def test_ocr_benchmark_metrics() -> None:
    assert benchmark_ocr.cer("abc", "abc") == 0.0
    assert benchmark_ocr.wer("one two", "one two") == 0.0
    assert benchmark_ocr.cer("abc", "axc") == pytest.approx(round(1 / 3, 4))
    assert benchmark_ocr.wer("one two", "one too") == pytest.approx(0.5)
