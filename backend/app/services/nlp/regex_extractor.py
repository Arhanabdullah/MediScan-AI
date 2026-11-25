"""Config-driven regex entity extractor (the default pipeline stage)."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.config import settings
from app.services.logging import log_stage
from app.services.medicines import get_repository
from app.services.protocols import EntityResult

from .base import EntityExtractorBase, add_entity

DEFAULT_ENTITY_KEYS: dict[str, str] = {
    "strength": "strengths",
    "frequency": "frequencies",
    "duration": "durations",
    "form": "forms",
}


class RegexExtractor(EntityExtractorBase):
    """Regex rules and entity types come entirely from YAML configuration."""

    name = "regex"
    display_name = "Regex"

    def __init__(
        self,
        patterns: Mapping[str, Any] | None = None,
        config: Mapping[str, Any] | None = None,
    ) -> None:
        patterns = dict(patterns or settings.patterns)
        config = dict(config or settings.nlp)
        self.regexes = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in patterns.get("regex", {}).items()
        }
        self.labels: dict[str, str] = dict(patterns.get("entity_labels", {}))
        self.skip_prefixes = tuple(patterns.get("skip_prefixes", ()))
        self.confidence_hints: dict[str, float] = dict(patterns.get("entity_confidence", {}))
        self.max_medicine_words = int(patterns.get("max_medicine_words", 5))
        self.max_medicine_line_length = int(patterns.get("max_medicine_line_length", 90))
        # The mapping order defines extraction priority; custom types can be
        # appended without touching Python code.
        self.entity_keys: dict[str, str] = dict(config.get("entity_keys") or DEFAULT_ENTITY_KEYS)

    def _known_names(self) -> tuple[str, ...]:
        names = {
            name
            for medicine in get_repository().all()
            for name in medicine.search_names
            if name
        }
        return tuple(sorted(names, key=len, reverse=True))

    def _looks_like_medicine_line(self, line: str) -> bool:
        lowered = line.lower().strip()
        if not lowered or lowered.startswith(self.skip_prefixes):
            return False
        if len(line) > self.max_medicine_line_length:
            return False
        return bool(self.regexes["strength"].search(line) or self.regexes["form"].search(line))

    def _medicine_candidate(self, line: str) -> str:
        candidate = self.regexes["list_bullet"].sub("", line)
        candidate = self.regexes["strength"].split(candidate, maxsplit=1)[0]
        candidate = self.regexes["form"].split(candidate, maxsplit=1)[0]
        candidate = self.regexes["label_prefix"].sub("", candidate)
        candidate = candidate.strip(" :;,-")
        return " ".join(candidate.split()[: self.max_medicine_words])

    def extract(self, text: str) -> EntityResult:
        with log_stage("entity_extraction", output_summary=f"{len(text)} chars"):
            entities: EntityResult = {
                "medicine_names": [],
                "strengths": [],
                "frequencies": [],
                "durations": [],
                "forms": [],
            }
            known_names = self._known_names()

            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue

                for pattern_name, entity_key in self.entity_keys.items():
                    regex = self.regexes.get(pattern_name)
                    if regex is None:
                        continue
                    for match in regex.finditer(line):
                        add_entity(
                            entities,
                            entity_key,
                            match.group(0),
                            self.confidence_hints.get(pattern_name, 0.9),
                            self.labels,
                        )

                known_match = next(
                    (
                        name
                        for name in known_names
                        if re.search(rf"\b{re.escape(name)}\b", line, re.IGNORECASE)
                    ),
                    None,
                )
                if known_match:
                    add_entity(
                        entities,
                        "medicine_names",
                        known_match,
                        self.confidence_hints.get("known_name", 0.95),
                        self.labels,
                    )
                    continue

                if self._looks_like_medicine_line(line):
                    candidate = self._medicine_candidate(line)
                    if candidate and len(candidate) > 2:
                        add_entity(
                            entities,
                            "medicine_names",
                            candidate,
                            self.confidence_hints.get("candidate", 0.68),
                            self.labels,
                        )

            return entities
