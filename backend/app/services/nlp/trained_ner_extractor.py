"""Optional trained spaCy NER extractor from Phase M1."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Mapping

from app.config import BACKEND_DIR, settings
from app.services.logging import get_logger
from app.services.protocols import EntityResult

from .base import EntityExtractorBase, add_entity, empty_result, label_map_from_config

logger = get_logger("nlp")


class TrainedNerExtractor(EntityExtractorBase):
    """Loads the locally trained NER artifact when the model flag is enabled."""

    name = "trained_ner"
    display_name = "Trained NER"

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        config = dict(config or settings.model["ner"])
        self.enabled = bool(config.get("enabled", False))
        self.model_path: Path = BACKEND_DIR / str(config.get("model_path", ""))
        self.label_map = label_map_from_config(config.get("label_map"))
        self.confidence = float(config.get("confidence", 0.85))
        self._nlp: Any | None = None

    def available(self) -> bool:
        if not self.enabled or not self.model_path.exists():
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
            if self._nlp is None:
                import spacy

                self._nlp = spacy.load(str(self.model_path))
            doc = self._nlp(text)
        except Exception as error:
            logger.warning("trained_ner_unavailable", extra={"output_summary": str(error)})
            return result

        for entity in doc.ents:
            key = self.label_map.get(entity.label_.upper())
            if key:
                add_entity(result, key, entity.text, self.confidence)
        return result
