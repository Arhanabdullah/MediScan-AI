"""Optional HuggingFace token-classification extractor (lazy import)."""

from __future__ import annotations

import importlib.util
from typing import Any, Mapping

from app.config import settings
from app.services.logging import get_logger
from app.services.protocols import EntityResult

from .base import EntityExtractorBase, add_entity, empty_result, label_map_from_config

logger = get_logger("nlp")


class TransformerExtractor(EntityExtractorBase):
    name = "transformer"
    display_name = "Transformer"

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        config = dict(config or settings.nlp.get("transformer") or {})
        self.model_name = str(config.get("model") or "")
        self.label_map = label_map_from_config(config.get("label_map"))
        self.confidence = float(config.get("confidence", 0.85))

    def available(self) -> bool:
        if not self.model_name:
            return False
        try:
            return importlib.util.find_spec("transformers") is not None
        except (ImportError, ValueError):
            return False

    def extract(self, text: str) -> EntityResult:
        result = empty_result()
        if not self.available():
            return result
        try:
            from transformers import pipeline

            classifier = pipeline("token-classification", model=self.model_name)
            outputs = classifier(text)
        except Exception as error:
            logger.warning("transformer_unavailable", extra={"output_summary": str(error)})
            return result

        for output in outputs:
            key = self.label_map.get(str(output.get("entity", "")).upper())
            if key:
                add_entity(result, key, str(output.get("word", "")), self.confidence)
        return result
