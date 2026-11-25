"""Pluggable NLP entity extraction.

``extract_entities(text)`` remains the stable facade used by the API. New code
can build/inject custom pipelines via ``build_pipeline`` / ``set_pipeline``.
"""

from __future__ import annotations

from typing import Any

from app.services.protocols import EntityResult

from .base import EntityExtractorBase, add_entity, empty_result, merge_results
from .pipeline import ExtractorPipeline, build_pipeline, register_extractor
from .postprocess import (
    deduplicate,
    normalize_form,
    normalize_frequency,
    normalize_strength,
    postprocess,
    validate_medicine_names,
)
from .regex_extractor import RegexExtractor
from .spacy_extractor import SpacyExtractor
from .transformer_extractor import TransformerExtractor

_pipeline: ExtractorPipeline | None = None


def get_pipeline() -> ExtractorPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


def set_pipeline(pipeline: ExtractorPipeline | None) -> None:
    """Inject a pipeline (used by tests and callers with custom extractors)."""
    global _pipeline
    _pipeline = pipeline


def extract_entities(text: str) -> EntityResult:
    """Extract entities using the configured pipeline."""
    return get_pipeline().extract(text)


# Backwards-compatible module attributes from the previous monolithic nlp.py.
_shared_regex = RegexExtractor()
REGEXES: dict[str, Any] = _shared_regex.regexes
ENTITY_LABELS: dict[str, str] = _shared_regex.labels
SKIP_PREFIXES: tuple[str, ...] = _shared_regex.skip_prefixes
CONFIDENCE_HINTS: dict[str, float] = _shared_regex.confidence_hints
MAX_MEDICINE_WORDS: int = _shared_regex.max_medicine_words
MAX_MEDICINE_LINE_LENGTH: int = _shared_regex.max_medicine_line_length
_add = add_entity

__all__ = [
    "CONFIDENCE_HINTS",
    "ENTITY_LABELS",
    "MAX_MEDICINE_LINE_LENGTH",
    "MAX_MEDICINE_WORDS",
    "REGEXES",
    "SKIP_PREFIXES",
    "EntityExtractorBase",
    "ExtractorPipeline",
    "RegexExtractor",
    "SpacyExtractor",
    "TransformerExtractor",
    "add_entity",
    "build_pipeline",
    "deduplicate",
    "empty_result",
    "extract_entities",
    "get_pipeline",
    "merge_results",
    "normalize_form",
    "normalize_frequency",
    "normalize_strength",
    "postprocess",
    "register_extractor",
    "set_pipeline",
    "validate_medicine_names",
]
