"""Deduplication, unit normalization and optional catalogue validation."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.services.medicines import get_repository
from app.services.protocols import EntityResult

_STRENGTH_UNIT = r"(?:mcg|µg|mg|ml|iu|g|units?)"


def normalize_strength(value: str) -> str:
    """Put a space before units and canonicalise microgram spelling."""

    def _unit(match: re.Match[str]) -> str:
        unit = match.group(1).lower()
        return " mcg" if unit == "µg" else f" {unit}"

    result = re.sub(rf"(?<=\d)\s*({_STRENGTH_UNIT})\b", _unit, value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", result).strip()


def normalize_frequency(value: str, aliases: Mapping[str, str] | None = None) -> str:
    """Expand prescription abbreviations without altering full phrases."""
    lookup = {key.casefold(): str(target) for key, target in (aliases or {}).items()}
    return lookup.get(value.strip().casefold(), value)


def normalize_form(value: str, aliases: Mapping[str, str] | None = None) -> str:
    """Canonicalise plural forms (tablets -> tablet)."""
    lookup = {key.casefold(): str(target) for key, target in (aliases or {}).items()}
    return lookup.get(value.strip().casefold(), value)


def deduplicate(entities: EntityResult) -> EntityResult:
    """Remove repeated values within each entity category, keeping the first."""
    cleaned: EntityResult = {}
    for key, items in entities.items():
        seen: set[str] = set()
        unique = []
        for item in items:
            value = " ".join(str(item["value"]).split())
            fingerprint = value.casefold()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            unique.append({**item, "value": value})
        cleaned[key] = unique
    return cleaned


def _known_names() -> set[str]:
    return {
        name.casefold()
        for medicine in get_repository().all()
        for name in medicine.search_names
        if name
    }


def validate_medicine_names(entities: EntityResult) -> EntityResult:
    """Drop unknown medicine names (off by default: reduces typo recall)."""
    known = _known_names()
    result = {key: list(items) for key, items in entities.items()}
    result["medicine_names"] = [
        item
        for item in result.get("medicine_names", [])
        if item["value"].casefold() in known
        or any(name in item["value"].casefold() for name in known if len(name) > 2)
    ]
    return result


def postprocess(entities: EntityResult, config: Mapping[str, Any] | None = None) -> EntityResult:
    """Apply the configured post-processing steps in a deterministic order."""
    config = dict(config or {})
    result = deduplicate(entities)

    if config.get("normalize_strength", False):
        for item in result.get("strengths", []):
            item["value"] = normalize_strength(item["value"])

    if config.get("normalize_frequency", False):
        aliases = config.get("frequency_aliases") or {}
        for item in result.get("frequencies", []):
            item["value"] = normalize_frequency(item["value"], aliases)

    if config.get("normalize_form", False):
        aliases = config.get("form_aliases") or {}
        for item in result.get("forms", []):
            item["value"] = normalize_form(item["value"], aliases)

    if config.get("validate_medicine_names", False):
        result = validate_medicine_names(result)

    return result
