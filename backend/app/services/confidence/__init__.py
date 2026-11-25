"""Explainable, versioned confidence scoring.

``calculate_breakdown(ctx)`` and ``calculate_confidence(...)`` remain the stable
facades used by the API and tuning scripts.
"""

from __future__ import annotations

from app.config import settings
from app.services.protocols import ConfidenceBreakdown, ConfidenceContext

from .base import ConfidenceModelBase, ModelParams
from .registry import (
    ConfidenceRegistry,
    build_registry,
    get_registry,
    register_model,
    set_registry,
)
from .weighted import DynamicWeightedConfidenceModel, WeightedConfidenceModel, params_from_variant

# Kept as a module attribute for compatibility with earlier imports.
OCR_SCORES: dict[str, float] = settings.ocr_scores


def calculate_breakdown(ctx: ConfidenceContext) -> ConfidenceBreakdown:
    """Score one scan and return the per-component breakdown."""
    return get_registry().score(ctx)


def calculate_confidence(
    raw_text: str,
    entities: dict[str, list],
    medicines: list[dict],
    ocr_engine: str,
    warnings: list[str],
) -> float:
    """Backward-compatible wrapper returning only the overall score."""
    ctx = ConfidenceContext(
        raw_text=raw_text,
        entities=entities,
        medicines=medicines,
        ocr_engine=ocr_engine,
        warnings=warnings,
    )
    return calculate_breakdown(ctx).overall


__all__ = [
    "OCR_SCORES",
    "ConfidenceModelBase",
    "ConfidenceRegistry",
    "DynamicWeightedConfidenceModel",
    "ModelParams",
    "WeightedConfidenceModel",
    "build_registry",
    "calculate_breakdown",
    "calculate_confidence",
    "get_registry",
    "params_from_variant",
    "register_model",
    "set_registry",
]
