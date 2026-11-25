"""Optional PaddleOCR engine. The heavy dependency is imported lazily."""

from __future__ import annotations

import importlib.util
from typing import Any

import numpy as np

from .base import BaseOCREngine


class PaddleOCREngine(BaseOCREngine):
    name = "paddleocr"
    display_name = "PaddleOCR"
    preferred_preprocess = "enhanced"

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self._reader: Any = None

    def available(self) -> bool:
        return importlib.util.find_spec("paddleocr") is not None

    def _extract(self, image: np.ndarray) -> str:
        from paddleocr import PaddleOCR  # optional dependency - imported only when used

        if self._reader is None:
            self._reader = PaddleOCR(
                use_angle_cls=False,
                lang=str(self.options.get("language", "en")),
                use_gpu=bool(self.options.get("use_gpu", False)),
            )
        result = self._reader.ocr(image, cls=False)
        lines: list[str] = []
        for page in result or []:
            for entry in page or []:
                # PaddleOCR returns (box, (text, score)) across versions.
                try:
                    text = entry[1][0]
                except (IndexError, TypeError):
                    continue
                if text:
                    lines.append(str(text))
        return "\n".join(lines)
