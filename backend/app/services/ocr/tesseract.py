"""Tesseract OCR engine (installed via system package + pytesseract)."""

from __future__ import annotations

import shutil

import cv2
import numpy as np
import pytesseract

from app.config import settings

from .base import BaseOCREngine


class TesseractEngine(BaseOCREngine):
    name = "tesseract"
    display_name = "Tesseract"
    preferred_preprocess = "threshold"

    def available(self) -> bool:
        return bool(settings.tesseract_cmd or shutil.which("tesseract"))

    def _extract(self, image: np.ndarray) -> str:
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if image.ndim == 3 else image
        config = str(self.options.get("config", "--psm 6"))
        return pytesseract.image_to_string(rgb, config=config)
