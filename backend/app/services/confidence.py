OCR_SCORES = {
    "tesseract": 0.95,
    "tesseract-error": 0.25,
    "tesseract-unavailable": 0.2,
    "demo-fallback": 0.55,
}


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def calculate_confidence(
    raw_text: str,
    entities: dict[str, list],
    medicines: list[dict],
    ocr_engine: str,
    warnings: list[str],
) -> float:
    if not raw_text.strip():
        return 0.0

    ocr_score = OCR_SCORES.get(ocr_engine, 0.6)
    text_score = min(1.0, len(raw_text) / 300)
    entity_score = sum(1 for items in entities.values() if items) / max(1, len(entities))
    medicine_score = _average([medicine["confidence"] for medicine in medicines]) if medicines else 0.2

    score = (
        0.45 * ocr_score
        + 0.15 * text_score
        + 0.20 * entity_score
        + 0.20 * medicine_score
    )
    score -= 0.05 * len(warnings)
    return round(max(0.05, min(0.99, score)), 3)
