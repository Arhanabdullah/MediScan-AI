"""Phase 5 tests: confidence model registry, A/B safety and telemetry."""

from __future__ import annotations

import io
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.main import app
from app.services.confidence import (
    ConfidenceRegistry,
    build_registry,
    get_registry,
    set_registry,
)
from app.services.confidence.base import ModelParams
from app.services.confidence.weighted import DynamicWeightedConfidenceModel, WeightedConfidenceModel
from app.services.logging import correlation_id
from app.services.protocols import ConfidenceBreakdown, ConfidenceContext
from app.services.telemetry import METRICS

client = TestClient(app)


def _ctx(text: str = "x" * 200, warnings: list[str] | None = None) -> ConfidenceContext:
    return ConfidenceContext(
        raw_text=text,
        entities={"medicine_names": [{"value": "Paracetamol"}], "strengths": []},
        medicines=[{"confidence": 0.9}],
        ocr_engine="tesseract",
        warnings=warnings or [],
    )


def _config(
    *,
    ab_enabled: bool = False,
    variants: list[dict[str, Any]] | None = None,
    max_delta: float = 0.15,
) -> dict[str, Any]:
    return {
        "default": "weighted-v1",
        "fallback": "weighted-v1",
        "ab": {
            "enabled": ab_enabled,
            "variants": variants or [
                {"name": "weighted-v1", "weight": 50},
                {"name": "weighted-v2", "weight": 50},
            ],
            "max_delta": max_delta,
        },
        "variants": {},
    }


@pytest.fixture(autouse=True)
def _restore_state() -> None:
    registry = get_registry()
    previous_correlation = correlation_id.get()
    METRICS.reset()
    yield
    set_registry(registry)
    correlation_id.set(previous_correlation)
    METRICS.reset()


def test_registry_default_is_explainable_and_stable() -> None:
    registry = build_registry(_config())
    assert registry.names() == ["weighted-v1"] or registry.names() == [
        "weighted-v1",
        "weighted-v2",
    ]

    breakdown = registry.score(_ctx())
    assert set(breakdown.components) == set(settings.confidence_weights)
    assert breakdown.metadata["model"] == "weighted-v1"
    assert breakdown.metadata["strategy"] == "default"
    assert breakdown.warnings_penalty == 0.0
    contributions = sum(
        score.contribution for score in breakdown.metadata["component_scores"].values()
    )
    assert contributions == pytest.approx(breakdown.overall, abs=0.01)
    assert breakdown.overall == registry.score(_ctx()).overall


def test_ab_selection_is_deterministic_and_uses_both_variants() -> None:
    config = _config(ab_enabled=True, max_delta=1.0)
    config["variants"]["weighted-v2"] = {
        "weights": {"ocr_engine": 0.0, "text_length": 0.0, "entity_coverage": 0.0, "medicine_match": 1.0}
    }
    registry = build_registry(config)

    selected: set[str] = set()
    for index in range(20):
        correlation_id.set(f"correlation-{index}")
        first = registry.score(_ctx())
        second = registry.score(_ctx())
        assert first.metadata["model"] == second.metadata["model"]
        assert first.metadata["strategy"] == "ab"
        selected.add(str(first.metadata["model"]))
    assert {"weighted-v1", "weighted-v2"} <= selected


def test_ab_delta_guard_keeps_default_score() -> None:
    aggressive = WeightedConfidenceModel(
        ModelParams(
            weights={"medicine_match": 1.0},
            penalties={},
            ocr_scores=dict(settings.ocr_scores),
            text_length_reference=settings.text_length_reference,
            min_score=settings.confidence_min,
            max_score=settings.confidence_max,
            empty_medicine_score=0.0,
        ),
        name="aggressive",
        version="test",
    )
    registry = ConfidenceRegistry(
        _config(ab_enabled=True, variants=[{"name": "aggressive", "weight": 100}]),
        models=[aggressive, DynamicWeightedConfidenceModel()],
    )
    baseline = registry.get("weighted-v1")
    assert baseline is not None

    ctx = replace(_ctx(warnings=["warning"]), medicines=[])
    correlation_id.set("guard-check")
    breakdown = registry.score(ctx)
    expected = baseline.calculate(ctx).overall
    assert breakdown.metadata["fallback_used"] is True
    assert breakdown.metadata["reason"] == "delta_guard"
    assert breakdown.metadata["model"] == "weighted-v1"
    assert breakdown.overall == expected


def test_failing_variant_falls_back_to_default_model() -> None:
    class BrokenModel:
        name = "broken"
        version = "v0"

        def calculate(self, ctx: ConfidenceContext) -> ConfidenceBreakdown:
            raise RuntimeError("variant unavailable")

    registry = ConfidenceRegistry(
        _config(ab_enabled=True, variants=[{"name": "broken", "weight": 100}]),
        models=[BrokenModel(), DynamicWeightedConfidenceModel()],
    )
    correlation_id.set("broken-variant")
    breakdown = registry.score(_ctx())
    assert breakdown.metadata["reason"] == "exception"
    assert breakdown.metadata["model"] == "weighted-v1"
    assert 0.0 <= breakdown.overall <= 1.0


def test_telemetry_snapshot_and_prometheus_exporter() -> None:
    METRICS.inc("stage_total", stage="nlp")
    METRICS.inc("stage_total", stage="nlp")
    METRICS.observe("stage_duration_ms", 12.5, stage="nlp")

    snapshot = METRICS.snapshot()
    assert snapshot["counters"]['mediscan_stage_total{stage="nlp"}'] == 2
    assert snapshot["histograms"]['mediscan_stage_duration_ms{stage="nlp"}']['count'] == 1

    text = METRICS.render_prometheus()
    assert "# TYPE mediscan_stage_total counter" in text
    assert 'mediscan_stage_total{stage="nlp"} 2' in text
    assert 'mediscan_stage_duration_ms_bucket{le="+Inf",stage="nlp"} 1' in text


def test_metrics_endpoint_does_not_expose_patient_text() -> None:
    image = io.BytesIO()
    Image.new("RGB", (120, 80), "white").save(image, format="PNG")

    scan = client.post(
        "/api/scan",
        files={"file": ("private-prescription-name.png", image.getvalue(), "image/png")},
    )
    assert scan.status_code == 200

    models = client.get("/api/confidence/models")
    assert models.status_code == 200
    assert models.json()["default"] == "weighted-v1"
    assert "weighted-v1" in models.json()["models"]

    text = client.get("/api/metrics").text
    assert "mediscan_scans_total" in text
    assert "mediscan_confidence_model_total" in text
    assert "private-prescription-name" not in text
    assert scan.json()["raw_text"] not in text

    snapshot = client.get("/api/metrics?format=json").json()
    assert any(key.startswith("mediscan_scans_total") for key in snapshot["counters"])
