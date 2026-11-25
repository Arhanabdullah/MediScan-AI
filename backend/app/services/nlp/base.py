"""Shared helpers and the extractor contract for the NLP pipeline."""

from __future__ import annotations

from typing import Any

from app.services.protocols import EntityResult


class EntityExtractorBase:
    """Convenience base class; duck-typing against EntityExtractor is enough."""

    name = "base"
    display_name = "Extractor"

    def available(self) -> bool:
        return True

    def extract(self, text: str) -> EntityResult:
        raise NotImplementedError


def empty_result() -> EntityResult:
    return {
        "medicine_names": [],
        "strengths": [],
        "frequencies": [],
        "durations": [],
        "forms": [],
    }


def add_entity(
    entities: EntityResult,
    key: str,
    value: str,
    confidence: float,
    labels: dict[str, str] | None = None,
) -> None:
    """Append a de-duplicated entity, creating custom keys when configured."""
    cleaned = value.strip()
    if not cleaned:
        return
    labels = labels or {}
    if any(item["value"].casefold() == cleaned.casefold() for item in entities.get(key, [])):
        return
    entities.setdefault(key, []).append(
        {"label": labels.get(key, key), "value": cleaned, "confidence": confidence}
    )


def merge_results(results: list[EntityResult]) -> EntityResult:
    """Combine extractor outputs while preserving first-seen ordering."""
    merged = empty_result()
    for result in results:
        for key, items in result.items():
            for item in items:
                add_entity(merged, key, item["value"], item["confidence"], {key: item["label"]})
    return merged


def has_entities(result: EntityResult) -> bool:
    return any(items for items in result.values())


def label_map_from_config(config: dict[str, Any]) -> dict[str, str]:
    """Normalise YAML label maps so values are entity keys, not lists."""
    return {str(label): str(key) for label, key in (config or {}).items()}
