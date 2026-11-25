"""Confidence model contract and shared weighted-scoring implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.protocols import ComponentScore, ConfidenceBreakdown, ConfidenceContext


@dataclass(frozen=True)
class ModelParams:
    weights: dict[str, float]
    penalties: dict[str, float]
    ocr_scores: dict[str, float]
    text_length_reference: int
    min_score: float
    max_score: float
    empty_medicine_score: float = 0.2
    use_reserved_penalties: bool = False


class ConfidenceModelBase:
    """Base class implementing the explainable weighted formula."""

    name = "base"
    version = "0"

    def _params(self) -> ModelParams:  # pragma: no cover - abstract by convention
        raise NotImplementedError

    @staticmethod
    def _normalised(weights: dict[str, float]) -> dict[str, float]:
        positive = {key: max(0.0, float(value)) for key, value in weights.items()}
        total = sum(positive.values())
        return {key: value / total for key, value in positive.items()} if total else positive

    @staticmethod
    def _average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def calculate(self, ctx: ConfidenceContext) -> ConfidenceBreakdown:
        params = self._params()
        weights = self._normalised(params.weights)
        identity = {"model": self.name, "version": self.version}

        if not ctx.raw_text.strip():
            penalty = float(params.penalties.get("empty_ocr", 0.5)) if params.use_reserved_penalties else 0.0
            return ConfidenceBreakdown(
                overall=0.0,
                components={key: 0.0 for key in weights},
                warnings_penalty=round(penalty, 3),
                metadata={**identity, "empty_ocr": True},
            )

        components: dict[str, float] = {
            "ocr_engine": params.ocr_scores.get(ctx.ocr_engine, 0.6),
            "text_length": min(1.0, len(ctx.raw_text) / max(1, params.text_length_reference)),
            "entity_coverage": sum(1 for items in ctx.entities.values() if items) / max(1, len(ctx.entities)),
            "medicine_match": (
                self._average([medicine["confidence"] for medicine in ctx.medicines])
                if ctx.medicines
                else params.empty_medicine_score
            ),
        }
        for key in weights:
            components.setdefault(key, 0.0)

        weighted = sum(weights.get(key, 0.0) * value for key, value in components.items())
        penalty = float(params.penalties.get("per_warning", 0.05)) * len(ctx.warnings)
        if params.use_reserved_penalties and not ctx.medicines:
            penalty += float(params.penalties.get("no_medicines", 0.3))

        score = weighted - penalty
        overall = round(max(params.min_score, min(params.max_score, score)), 3)

        component_scores: dict[str, ComponentScore] = {
            key: ComponentScore(
                value=round(value, 3),
                weight=round(weights.get(key, 0.0), 3),
                contribution=round(weights.get(key, 0.0) * value, 3),
            )
            for key, value in components.items()
        }
        metadata: dict[str, Any] = {
            **identity,
            "weights": {key: round(value, 3) for key, value in weights.items()},
            "warning_count": len(ctx.warnings),
            "component_scores": component_scores,
        }
        return ConfidenceBreakdown(
            overall=overall,
            components={key: round(value, 3) for key, value in components.items()},
            warnings_penalty=round(penalty, 3),
            metadata=metadata,
        )
