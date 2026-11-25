"""Weighted confidence models (fixed config variant + dynamic default)."""

from __future__ import annotations

from typing import Any

from app.config import settings

from .base import ConfidenceModelBase, ModelParams


class WeightedConfidenceModel(ConfidenceModelBase):
    """A fixed, fully parameterised weighted model (e.g. an A/B variant)."""

    name = "weighted"
    version = "v1"

    def __init__(
        self,
        params: ModelParams,
        *,
        name: str | None = None,
        version: str | None = None,
    ) -> None:
        self._fixed = params
        if name:
            self.name = name
        if version:
            self.version = version

    def _params(self) -> ModelParams:
        return self._fixed


class DynamicWeightedConfidenceModel(WeightedConfidenceModel):
    """The default model: reads settings on every call so tuning scripts work."""

    name = "weighted-v1"

    def __init__(self, *, name: str | None = None) -> None:
        # Placeholder params are never used because _params() reads settings.
        super().__init__(_settings_params(), name=name or "weighted-v1", version="v1")

    def _params(self) -> ModelParams:
        return _settings_params()


def _settings_params() -> ModelParams:
    return ModelParams(
        weights=dict(settings.confidence_weights),
        penalties=dict(settings.confidence_penalties),
        ocr_scores=dict(settings.ocr_scores),
        text_length_reference=settings.text_length_reference,
        min_score=settings.confidence_min,
        max_score=settings.confidence_max,
    )


def params_from_variant(config: dict[str, Any]) -> ModelParams:
    """Build fixed params for a named variant from confidence.yaml."""
    weights: dict[str, float] = {
        **settings.confidence_weights,
        **{key: float(value) for key, value in (config.get("weights") or {}).items()},
    }
    penalties: dict[str, float] = {
        **settings.confidence_penalties,
        **{key: float(value) for key, value in (config.get("penalties") or {}).items()},
    }
    return ModelParams(
        weights=weights,
        penalties=penalties,
        ocr_scores=dict(settings.ocr_scores),
        text_length_reference=settings.text_length_reference,
        min_score=settings.confidence_min,
        max_score=settings.confidence_max,
        use_reserved_penalties=bool(config.get("use_reserved_penalties", False)),
    )
