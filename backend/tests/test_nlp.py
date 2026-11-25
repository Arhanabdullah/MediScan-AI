"""Phase 4 tests: pluggable extractors, pipeline strategies and post-processing."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.loader import load_nlp_config
from app.services import nlp as nlp_service
from app.services.medicines import JsonMedicineRepository, get_repository, set_repository
from app.services.nlp import (
    EntityExtractorBase,
    ExtractorPipeline,
    RegexExtractor,
    SpacyExtractor,
    TransformerExtractor,
    build_pipeline,
    deduplicate,
    extract_entities,
    normalize_form,
    normalize_frequency,
    normalize_strength,
    postprocess,
    set_pipeline,
)
from app.services.nlp import pipeline as pipeline_module
from app.services.protocols import EntityResult


@pytest.fixture(autouse=True)
def _restore_state():
    original_pipeline = nlp_service.get_pipeline()
    original_repository = get_repository()
    yield
    set_pipeline(original_pipeline)
    set_repository(original_repository)


def _entity(value: str, confidence: float = 0.9, key: str = "medicine_names") -> EntityResult:
    result: EntityResult = {
        "medicine_names": [],
        "strengths": [],
        "frequencies": [],
        "durations": [],
        "forms": [],
    }
    result.setdefault(key, []).append({"label": key, "value": value, "confidence": confidence})
    return result


class StubExtractor(EntityExtractorBase):
    name = "stub"

    def __init__(
        self,
        result: EntityResult | None = None,
        *,
        available: bool = True,
        error: bool = False,
    ) -> None:
        self.result = result or {key: [] for key in (result or _entity("x"))}
        self._available = available
        self._error = error

    def available(self) -> bool:
        return self._available

    def extract(self, text: str) -> EntityResult:
        if self._error:
            raise RuntimeError("stub failure")
        return {key: [dict(item) for item in items] for key, items in self.result.items()}


def test_nlp_config_is_loaded() -> None:
    config = load_nlp_config()
    assert config["extractors"] == ["regex"]
    assert config["strategy"] == "fallback"
    assert config["entity_keys"]["form"] == "forms"
    assert config["postprocess"]["normalize_strength"] is True


def test_regex_extractor_supports_custom_entity_types() -> None:
    patterns: dict[str, Any] = {
        "regex": {
            "strength": r"\b\d+\s*mg\b",
            "frequency": r"\bdaily\b",
            "duration": r"\bfor \d+ days\b",
            "form": r"\btablet\b",
            "list_bullet": r"^\s*\d+[.)]?\s*",
            "label_prefix": r"^(?:name|medicine)\s*[:.]\s*",
            "allergy": r"\bpenicillin\b",
        },
        "entity_labels": {"allergies": "allergy"},
        "skip_prefixes": [],
        "entity_confidence": {"allergy": 0.7},
    }
    config = {
        "entity_keys": {
            "strength": "strengths",
            "frequency": "frequencies",
            "duration": "durations",
            "form": "forms",
            "allergy": "allergies",
        }
    }
    result = RegexExtractor(patterns, config).extract("1. Penicillin 500 mg daily for 5 days")
    assert result["allergies"] == [{"label": "allergy", "value": "Penicillin", "confidence": 0.7}]
    assert result["strengths"][0]["value"] == "500 mg"
    assert result["frequencies"][0]["value"] == "daily"


def test_pipeline_fallback_uses_first_extractor_with_entities() -> None:
    pipeline = ExtractorPipeline(
        [StubExtractor(), StubExtractor(_entity("Amoxicillin"))],
        strategy="fallback",
        postprocess_config={"deduplicate": True},
    )
    result = pipeline.extract("1. Amoxicillin 500 mg")
    assert [item["value"] for item in result["medicine_names"]] == ["Amoxicillin"]


def test_pipeline_merge_combines_and_deduplicates() -> None:
    pipeline = ExtractorPipeline(
        [
            StubExtractor(_entity("Amoxicillin")),
            StubExtractor(_entity("amoxicillin")),
            StubExtractor(_entity("Paracetamol", key="strengths")),
        ],
        strategy="merge",
        postprocess_config={"deduplicate": True},
    )
    result = pipeline.extract("text")
    assert [item["value"] for item in result["medicine_names"]] == ["Amoxicillin"]
    assert [item["value"] for item in result["strengths"]] == ["Paracetamol"]


def test_pipeline_skips_unavailable_and_failing_extractors() -> None:
    pipeline = ExtractorPipeline(
        [
            StubExtractor(available=False),
            StubExtractor(error=True),
            StubExtractor(_entity("Cetirizine")),
        ]
    )
    result = pipeline.extract("text")
    assert [item["value"] for item in result["medicine_names"]] == ["Cetirizine"]

    empty = ExtractorPipeline([StubExtractor(available=False)]).extract("text")
    assert not any(empty.values())


def test_postprocess_normalizes_units_and_dedupes() -> None:
    assert normalize_strength("500mg") == "500 mg"
    assert normalize_strength("10 µg") == "10 mcg"
    assert normalize_frequency("bd", {"bd": "twice daily"}) == "twice daily"
    assert normalize_form("Tablets", {"tablets": "tablet"}) == "tablet"

    entities = _entity("Amoxicillin")
    entities["medicine_names"].append({"label": "medicine_name", "value": "amoxicillin", "confidence": 0.9})
    assert len(deduplicate(entities)["medicine_names"]) == 1

    result = postprocess(entities, {"deduplicate": True})
    assert len(result["medicine_names"]) == 1


def test_validate_medicine_names_is_optional(tmp_path: Path) -> None:
    path = tmp_path / "medicines.json"
    path.write_text(
        json.dumps([{"id": "a", "name": "Amoxicillin", "generic_name": "Amoxicillin"}]),
        encoding="utf-8",
    )
    set_repository(JsonMedicineRepository(path, hot_reload=False))
    entities = _entity("Amoxicillin")
    entities["medicine_names"].append({"label": "medicine_name", "value": "Unknownz", "confidence": 0.6})

    kept = postprocess(entities, {"validate_medicine_names": True})
    assert [item["value"] for item in kept["medicine_names"]] == ["Amoxicillin"]
    assert len(postprocess(entities, {})["medicine_names"]) == 2


def test_optional_extractors_are_lazy_and_safe() -> None:
    assert SpacyExtractor({"model": ""}).available() is False
    assert TransformerExtractor({"model": ""}).available() is False
    assert SpacyExtractor().extract("text")["medicine_names"] == []
    assert TransformerExtractor().extract("text") == {
        key: [] for key in _entity("x")
    }


def test_custom_extractor_registration_and_facade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(pipeline_module._FACTORIES, "stub", lambda: StubExtractor(_entity("Custommed")))
    pipeline = build_pipeline(
        {"extractors": ["stub"], "strategy": "fallback", "postprocess": {"deduplicate": True}}
    )
    result = pipeline.extract("Custommed")
    assert [item["value"] for item in result["medicine_names"]] == ["Custommed"]

    set_pipeline(pipeline)
    assert [item["value"] for item in extract_entities("anything")["medicine_names"]] == ["Custommed"]

    # Unknown names are ignored rather than crashing the pipeline.
    resilient = build_pipeline({"extractors": ["does-not-exist"], "strategy": "merge"})
    assert not any(resilient.extract("text").values())
