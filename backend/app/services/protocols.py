"""Typed contracts for every pipeline stage.

NamedTuple results keep the historical tuple-unpacking API working while
giving each value a descriptive name. TypedDicts describe the dictionary
shapes that already flow through the API layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NamedTuple, Protocol, TypedDict, runtime_checkable

import numpy as np


class PreprocessResult(NamedTuple):
    image: np.ndarray
    size: dict[str, int]
    warnings: list[str]


class OCRResult(NamedTuple):
    text: str
    engine: str
    warnings: list[str]


class Entity(TypedDict):
    label: str
    value: str
    confidence: float


class EntityResult(TypedDict):
    medicine_names: list[Entity]
    strengths: list[Entity]
    frequencies: list[Entity]
    durations: list[Entity]
    forms: list[Entity]


class MedicineMatchDict(TypedDict):
    id: str
    text: str
    matched_name: str
    generic_name: str | None
    strength: str | None
    form: str | None
    match_score: float
    confidence: float
    alternatives: list[str]


@dataclass(frozen=True)
class ConfidenceContext:
    """Everything the confidence calculator needs for one scan."""

    raw_text: str
    entities: dict[str, list[dict[str, Any]]]
    medicines: list[dict[str, Any]]
    ocr_engine: str
    warnings: list[str]


@dataclass(frozen=True)
class ComponentScore:
    """One explainable contribution to an overall confidence score."""

    value: float
    weight: float
    contribution: float


@dataclass(frozen=True)
class ConfidenceBreakdown:
    """Explainable confidence result: overall score plus its components."""

    overall: float
    components: dict[str, float] = field(default_factory=dict)
    warnings_penalty: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Preprocessor(Protocol):
    def __call__(self, data: bytes) -> PreprocessResult: ...


@runtime_checkable
class OCREngine(Protocol):
    name: str
    display_name: str
    preferred_preprocess: str

    def available(self) -> bool: ...

    def extract(self, image: np.ndarray) -> OCRResult: ...


@runtime_checkable
class EntityExtractor(Protocol):
    def extract(self, text: str) -> EntityResult: ...


@runtime_checkable
class MedicineMatcher(Protocol):
    def match(self, text: str, strength: str | None = None) -> MedicineMatchDict: ...


@runtime_checkable
class ConfidenceCalculator(Protocol):
    def calculate(self, ctx: ConfidenceContext) -> ConfidenceBreakdown: ...


@runtime_checkable
class ConfidenceModel(Protocol):
    name: str
    version: str

    def calculate(self, ctx: ConfidenceContext) -> ConfidenceBreakdown: ...
