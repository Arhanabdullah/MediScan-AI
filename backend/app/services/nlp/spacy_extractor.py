"""Optional spaCy NER extractor (lazy import, skipped when unavailable)."""

from __future__ import annotations

import importlib.util
from typing import Any, Mapping

from app.config import settings
from app.services.logging import get_logger
from app.services.protocols import EntityResult

from .base import EntityExtractorBase, add_entity, empty_result, label_map_from_config

logger = get_logger("nlp")


class SpacyExtractor(EntityExtractorBase):
    name = "spacy"
    display_name = "spaCy"

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        config = dict(config or settings.nlp.get("spacy") or {})
        # An explicitly empty model name disables the extractor; only a missing
        # key falls back to the conventional English model.
        self.model_name = str(config.get("model", "en_core_web_sm"))
        self.label_map = label_map_from_config(config.get("label_map"))
        self.confidence = float(config.get("confidence", 0.8))

    def available(self) -> bool:
        if not self.model_name:
            return False
        try:
            return importlib.util.find_spec("spacy") is not None
        except (ImportError, ValueError):
            return False

    def extract(self, text: str) -> EntityResult:
        result = empty_result()
        if not self.available():
            return result
        try:
            import spacy

            nlp = spacy.load(self.model_name)
            doc = nlp(text)
        except Exception as error:
            logger.warning("spacy_unavailable", extra={"output_summary": str(error)})
            return result

        for entity in doc.ents:
            key = self.label_map.get(entity.label_.upper())
            if key:
                add_entity(result, key, entity.text, self.confidence)
        return result
