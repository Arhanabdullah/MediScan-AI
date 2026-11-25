"""Typed medicine records shared by all repository backends."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Medicine(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    generic_name: str | None = None
    strength: str | None = None
    form: str | None = None
    aliases: list[str] = Field(default_factory=list)
    # Optional per-entry rejection threshold for the fuzzy matcher.
    min_score: float | None = None

    @field_validator("id", "name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("aliases", mode="before")
    @classmethod
    def _aliases_to_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split("|") if item.strip()]
        return list(value)

    @property
    def search_names(self) -> tuple[str, ...]:
        """All names compared by the matcher, de-duplicated and non-empty."""
        names = [self.name, self.generic_name or "", *self.aliases]
        return tuple(dict.fromkeys(name.strip() for name in names if name and name.strip()))
