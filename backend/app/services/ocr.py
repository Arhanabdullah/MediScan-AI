import shutil

import cv2
import pytesseract

from app.config import settings


def _has_tesseract() -> bool:
    return bool(settings.tesseract_cmd or shutil.which("tesseract"))


def _configure_tesseract() -> None:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


def extract_text(image) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    backend = settings.ocr_backend

    if backend in {"auto", "tesseract"}:
        if not _has_tesseract():
            if backend == "tesseract":
                return "", "tesseract-unavailable", ["Tesseract is not installed; OCR is unavailable."]
            warnings.append("Tesseract was not found; using demo OCR text.")
        else:
            _configure_tesseract()
            try:
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if image.ndim == 3 else image
                text = pytesseract.image_to_string(rgb, config="--psm 6").strip()
                if text:
                    return text, "tesseract", warnings
                warnings.append("OCR returned no readable text.")
                return "", "tesseract", warnings
            except Exception as error:
                warnings.append(f"Tesseract failed: {type(error).__name__}.")
                if backend == "tesseract":
                    return "", "tesseract-error", warnings

    if backend == "demo":
        warnings.append("Demo OCR mode is active; text is synthetic.")

    return settings.demo_text.strip(), "demo-fallback", warnings
