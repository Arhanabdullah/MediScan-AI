"""Versioned confidence models with deterministic A/B selection and fallback."""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

from app.config import settings
from app.services.logging import correlation_id, get_logger
from app.services.protocols import ConfidenceBreakdown, ConfidenceContext, ConfidenceModel
from app.services.telemetry import METRICS

from .weighted import DynamicWeightedConfidenceModel, WeightedConfidenceModel, params_from_variant

logger = get_logger("confidence")


class ConfidenceRegistry:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        models: Iterable[ConfidenceModel] | None = None,
    ) -> None:
        config = dict(config or settings.confidence_models)
        self.default_name = str(config.get("default", "weighted-v1"))
        self.fallback_name = str(config.get("fallback", self.default_name))
        self.ab: dict[str, Any] = dict(config.get("ab") or {})
        self.models: dict[str, ConfidenceModel] = {}

        for model in models or ():
            self.register(model)

        if not self.models:
            self.register(DynamicWeightedConfidenceModel(name=self.default_name))
            for name, variant_config in (config.get("variants") or {}).items():
                if name == self.default_name:
                    continue
                options = dict(variant_config or {})
                if name == "weighted-v2":
                    options["weights"] = dict(settings.confidence_v2_weights)
                self.register(
                    WeightedConfidenceModel(
                        params_from_variant(options),
                        name=str(name),
                        version="v2",
                    )
                )

        for required in (self.default_name, self.fallback_name):
            if required not in self.models:
                self.register(DynamicWeightedConfidenceModel(name=required))

    def register(self, model: ConfidenceModel) -> None:
        self.models[model.name] = model

    def get(self, name: str) -> ConfidenceModel | None:
        return self.models.get(name)

    def names(self) -> list[str]:
        return sorted(self.models)

    def _require(self, name: str) -> ConfidenceModel:
        model = self.get(name)
        if model is None:
            raise KeyError(f"Unknown confidence model: {name}")
        return model

    def _bucket(self, ctx: ConfidenceContext) -> int:
        variants = [item for item in self.ab.get("variants", []) if isinstance(item, dict)]
        total = sum(max(0, int(item.get("weight", 0))) for item in variants)
        if total <= 0:
            return 0
        key = correlation_id.get() or ctx.raw_text or "mediscan"
        digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
        return int(digest[:16], 16) % total

    def _variant_for(self, bucket: int) -> ConfidenceModel | None:
        cumulative = 0
        for item in self.ab.get("variants", []):
            if not isinstance(item, dict):
                continue
            cumulative += max(0, int(item.get("weight", 0)))
            if bucket < cumulative:
                return self.get(str(item.get("name", "")))
        return None

    def score(self, ctx: ConfidenceContext) -> ConfidenceBreakdown:
        """Select a model, calculate the score, and apply safety fallbacks."""
        default = self._require(self.default_name)
        model = default
        selection: dict[str, Any] = {"model": default.name, "strategy": "default"}

        if self.ab.get("enabled") and self.ab.get("variants"):
            bucket = self._bucket(ctx)
            selection.update({"strategy": "ab", "bucket": bucket})
            model = self._variant_for(bucket) or default
            selection["model"] = model.name

        METRICS.inc("confidence_model_total", model=model.name, strategy=str(selection["strategy"]))

        try:
            breakdown = model.calculate(ctx)
        except Exception as error:
            logger.warning("confidence_model_failed", extra={"output_summary": str(error)})
            model = self._require(self.fallback_name)
            breakdown = model.calculate(ctx)
            selection.update({"model": model.name, "fallback_used": True, "reason": "exception"})
            METRICS.inc("confidence_fallback_total", reason="exception", model=model.name)

        if model is not default:
            try:
                baseline = default.calculate(ctx)
            except Exception:
                baseline = None
            max_delta = float(self.ab.get("max_delta", 0.15))
            if baseline is not None and abs(breakdown.overall - baseline.overall) > max_delta:
                logger.warning("confidence_guard_triggered", extra={"output_summary": model.name})
                breakdown = baseline
                selection.update({"model": default.name, "fallback_used": True, "reason": "delta_guard"})
                METRICS.inc("confidence_fallback_total", reason="delta_guard", model=default.name)

        breakdown.metadata.update(selection)
        return breakdown


def build_registry(config: dict[str, Any] | None = None) -> ConfidenceRegistry:
    return ConfidenceRegistry(config)


_registry: ConfidenceRegistry = build_registry()


def get_registry() -> ConfidenceRegistry:
    return _registry


def set_registry(registry: ConfidenceRegistry | None) -> None:
    """Replace the active registry (used by tests and A/B tooling)."""
    global _registry
    _registry = registry or build_registry()


def register_model(model: ConfidenceModel) -> None:
    _registry.register(model)
