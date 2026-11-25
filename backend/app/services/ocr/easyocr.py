"""Optional EasyOCR engine. The heavy dependency is imported lazily."""

from __future__ import annotations

import importlib.util
from typing import Any

import numpy as np

from .base import BaseOCREngine


class EasyOCREngine(BaseOCREngine):
    name = "easyocr"
    display_name = "EasyOCR"
    preferred_preprocess = "enhanced"

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self._reader: Any = None

    def available(self) -> bool:
        return importlib.util.find_spec("easyocr") is not None

    def _extract(self, image: np.ndarray) -> str:
        import easyocr  # optional dependency - imported only when used

        languages = list(self.options.get("languages") or ["en"])
        gpu = bool(self.options.get("gpu", False))
        if self._reader is None:
            self._reader = easyocr.Reader(languages, gpu=gpu, verbose=False)
        lines = self._reader.readtext(image, detail=0, paragraph=True)
        return "\n".join(str(line) for line in lines)
