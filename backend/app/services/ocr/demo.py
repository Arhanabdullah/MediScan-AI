"""Deterministic synthetic OCR fallback used for development and tests."""

from __future__ import annotations

import numpy as np

from app.config import settings

from .base import BaseOCREngine


class DemoEngine(BaseOCREngine):
    name = "demo-fallback"
    display_name = "Demo OCR"
    preferred_preprocess = "threshold"

    def available(self) -> bool:
        return True

    def _extract(self, image: np.ndarray) -> str:
        return settings.demo_text
