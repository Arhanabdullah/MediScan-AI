import cv2
import numpy as np

from app.config import settings


def preprocess_image(data: bytes) -> tuple[np.ndarray, dict[str, int], list[str]]:
    image_array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Unable to decode image. Upload a valid PNG, JPEG, or WEBP image.")

    height, width = image.shape[:2]
    warnings: list[str] = []
    scale = min(1.0, settings.max_image_dimension / max(height, width))

    if scale < 1.0:
        processed_width = int(width * scale)
        processed_height = int(height * scale)
        image = cv2.resize(image, (processed_width, processed_height), interpolation=cv2.INTER_AREA)
        warnings.append("Image was resized for processing.")
    else:
        processed_width = width
        processed_height = height

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(denoised)
    processed = cv2.adaptiveThreshold(
        contrast,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    processed = cv2.morphologyEx(processed, cv2.MORPH_CLOSE, kernel)
    size = {
        "width": int(width),
        "height": int(height),
        "processed_width": int(processed_width),
        "processed_height": int(processed_height),
    }
    return processed, size, warnings
