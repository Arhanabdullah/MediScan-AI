"""Generate synthetic prescription images from tests/fixtures/ocr/labels.json.

The images contain invented text only - never real patient prescriptions.
Pillow is already a backend dependency; no OCR engine is required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "tests" / "fixtures" / "ocr"


def _font(size: int = 20) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def main() -> int:
    labels = json.loads((FIXTURES / "labels.json").read_text(encoding="utf-8"))
    font = _font()
    lines_spacing = 8

    for sample in labels["samples"]:
        lines = sample["text"].splitlines()
        image = Image.new("RGB", (760, max(160, len(lines) * 34 + 40)), "white")
        draw = ImageDraw.Draw(image)
        for index, line in enumerate(lines):
            draw.text((20, 20 + index * (font.size + lines_spacing)), line, fill="black", font=font)
        target = FIXTURES / sample["image"]
        image.save(target)
        print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
