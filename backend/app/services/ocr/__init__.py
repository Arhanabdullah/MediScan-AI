"""OCR engine registry, factory and backward-compatible facade.

``extract_text(image)`` keeps the original call signature while delegating to
configurable engines. Heavy engines (EasyOCR/PaddleOCR) are optional and only
imported when they are actually selected.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.config import settings
from app.services.protocols import OCREngine, OCRResult
from config.loader import load_ocr_config

from .base import BaseOCREngine
from .demo import DemoEngine
from .easyocr import EasyOCREngine
from .paddleocr import PaddleOCREngine
from .tesseract import TesseractEngine

__all__ = [
    "BaseOCREngine",
    "DemoEngine",
    "EasyOCREngine",
    "OCRRegistry",
    "PaddleOCREngine",
    "TesseractEngine",
    "available_engines",
    "extract_text",
    "preferred_preprocess_mode",
    "resolve_engine",
]


class OCRRegistry:
    """Registry of OCR engine instances keyed by configured name."""

    _engines: dict[str, OCREngine] = {}

    @classmethod
    def register(cls, name: str, engine: OCREngine) -> None:
        cls._engines[name] = engine

    @classmethod
    def get(cls, name: str) -> OCREngine | None:
        return cls._engines.get(name)

    @classmethod
    def configured_order(cls) -> list[str]:
        engines: dict[str, Any] = load_ocr_config()["engines"]
        ordered = sorted(engines.items(), key=lambda item: item[1].get("priority", 99))
        return [name for name, options in ordered if options.get("enabled", True)]

    @classmethod
    def best_available(cls, preference: list[str] | None = None) -> OCREngine | None:
        for name in preference or cls.configured_order():
            engine = cls._engines.get(name)
            if engine is not None and engine.available():
                return engine
        return None

    @classmethod
    def names(cls) -> list[str]:
        return list(cls._engines)


_ENGINE_TYPES: dict[str, type[BaseOCREngine]] = {
    "tesseract": TesseractEngine,
    "easyocr": EasyOCREngine,
    "paddleocr": PaddleOCREngine,
    "demo": DemoEngine,
}


def _register_configured() -> None:
    for name, options in load_ocr_config()["engines"].items():
        engine_type = _ENGINE_TYPES.get(name)
        if engine_type is not None and options.get("enabled", True):
            OCRRegistry.register(name, engine_type(**options))


_register_configured()


def _fallback_engine() -> OCREngine:
    fallback_name = str(load_ocr_config().get("fallback", "demo"))
    engine = OCRRegistry.get(fallback_name)
    if engine is not None:
        return engine
    return DemoEngine()


def resolve_engine(name: str | None = None) -> OCREngine:
    """Resolve a configured backend name to an engine instance."""
    requested = (name or settings.ocr_backend or "auto").lower()
    if requested == "auto":
        return OCRRegistry.best_available() or _fallback_engine()
    return OCRRegistry.get(requested) or _fallback_engine()


def available_engines() -> dict[str, bool]:
    """Report engine availability for diagnostics and health endpoints."""
    return {name: engine.available() for name, engine in OCRRegistry._engines.items()}


def preferred_preprocess_mode(name: str | None = None) -> str:
    """Which preprocessing variant the selected engine works best with."""
    engine = resolve_engine(name)
    if not engine.available():
        engine = _fallback_engine()
    return engine.preferred_preprocess


def extract_text(image: np.ndarray, engine_name: str | None = None) -> OCRResult:
    """Run OCR with the requested engine, falling back when appropriate."""
    requested = (engine_name or settings.ocr_backend or "auto").lower()
    warnings: list[str] = []

    if requested == "auto":
        tesseract = OCRRegistry.get("tesseract")
        if tesseract is not None and not tesseract.available():
            warnings.append("Tesseract was not found; selecting the next available OCR engine.")

    engine = resolve_engine(requested)
    if not engine.available():
        if requested != "auto":
            warnings = [f"{engine.display_name} is not installed; OCR is unavailable."]
            return OCRResult("", f"{engine.name}-unavailable", warnings)
        engine = _fallback_engine()

    result = engine.extract(image)
    if warnings:
        return OCRResult(result.text, result.engine, warnings + result.warnings)
    return result
