"""Common OCR engine behaviour and error handling."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from app.services.protocols import OCRResult


class BaseOCREngine(ABC):
    """Abstract OCR engine with uniform availability checks and warnings."""

    name: str = "base"
    display_name: str = "OCR"
    preferred_preprocess: str = "threshold"

    def __init__(self, **options: Any) -> None:
        self.options = options

    @abstractmethod
    def available(self) -> bool:
        """Return True when the engine can run in this environment."""

    @abstractmethod
    def _extract(self, image: np.ndarray) -> str:
        """Return raw text from a prepared image."""

    def extract(self, image: np.ndarray) -> OCRResult:
        warnings: list[str] = []
        if not self.available():
            return OCRResult(
                "",
                f"{self.name}-unavailable",
                [f"{self.display_name} is not installed; OCR is unavailable."],
            )
        try:
            text = (self._extract(image) or "").strip()
        except Exception as error:  # keep a scan alive when one engine fails
            warnings.append(f"{self.name} failed: {type(error).__name__}.")
            return OCRResult("", f"{self.name}-error", warnings)
        if not text:
            warnings.append("OCR returned no readable text.")
        return OCRResult(text, self.name, warnings)
