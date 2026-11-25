"""Chain pluggable extractors with fallback/merge strategies."""

from __future__ import annotations

from typing import Any, Callable, Iterable

from app.config import settings
from app.services.logging import get_logger
from app.services.protocols import EntityExtractor, EntityResult

from .base import empty_result, has_entities, merge_results
from .postprocess import postprocess
from .regex_extractor import RegexExtractor
from .spacy_extractor import SpacyExtractor
from .transformer_extractor import TransformerExtractor

logger = get_logger("nlp")

ExtractorFactory = Callable[[], EntityExtractor]

_FACTORIES: dict[str, ExtractorFactory] = {
    "regex": RegexExtractor,
    "spacy": SpacyExtractor,
    "transformer": TransformerExtractor,
}


class ExtractorPipeline:
    """Run configured extractors and apply post-processing once at the end."""

    def __init__(
        self,
        extractors: Iterable[EntityExtractor],
        *,
        strategy: str = "fallback",
        postprocess_config: dict[str, Any] | None = None,
    ) -> None:
        self.extractors = list(extractors)
        if strategy not in ("fallback", "merge"):
            raise ValueError("strategy must be 'fallback' or 'merge'")
        self.strategy = strategy
        self.postprocess_config = dict(postprocess_config or {})

    def extract(self, text: str) -> EntityResult:
        results: list[EntityResult] = []
        selected: EntityResult | None = None

        for extractor in self.extractors:
            if not extractor.available():
                logger.info("extractor_skipped", extra={"output_summary": getattr(extractor, "name", "?")})
                continue
            try:
                result = extractor.extract(text)
            except Exception as error:
                logger.warning(
                    "extractor_failed",
                    extra={"output_summary": f"{getattr(extractor, 'name', '?')}: {error}"},
                )
                continue

            results.append(result)
            if self.strategy == "fallback" and has_entities(result):
                selected = result
                break

        if self.strategy == "merge":
            combined = merge_results(results)
        else:
            combined = selected if selected is not None else empty_result()

        return postprocess(combined, self.postprocess_config)


def build_pipeline(config: dict[str, Any] | None = None) -> ExtractorPipeline:
    """Build the pipeline described by config/nlp.yaml."""
    config = dict(config or settings.nlp)
    extractors: list[EntityExtractor] = []
    for name in config.get("extractors", ["regex"]):
        factory = _FACTORIES.get(str(name).lower())
        if factory is None:
            logger.warning("unknown_extractor", extra={"output_summary": str(name)})
            continue
        extractors.append(factory())

    return ExtractorPipeline(
        extractors,
        strategy=str(config.get("strategy", "fallback")),
        postprocess_config=dict(config.get("postprocess") or {}),
    )


def register_extractor(name: str, factory: ExtractorFactory) -> None:
    """Register a custom extractor class/factory for config-driven selection."""
    _FACTORIES[name.lower()] = factory
