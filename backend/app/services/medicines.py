import json
import re
from difflib import SequenceMatcher

from app.config import settings

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


def _load_medicines() -> list[dict]:
    with settings.medicine_db_path.open(encoding="utf-8") as file:
        return json.load(file)


MEDICINES = _load_medicines()


def normalize(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"^\s*(?:\d+[.)]?|[-•*])\s*", "", value)
    value = re.sub(r"[^a-z0-9\s]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _score(left: str, right: str) -> float:
    if fuzz is not None:
        return fuzz.ratio(left, right) / 100
    return SequenceMatcher(None, left, right).ratio()


def match_medicine(text: str, strength: str | None = None) -> dict:
    candidate = normalize(text)
    scored: list[tuple[float, dict]] = []

    for medicine in MEDICINES:
        names = [medicine.get("name", ""), medicine.get("generic_name", ""), *medicine.get("aliases", [])]
        best_score = max((_score(candidate, normalize(name)) for name in names if name), default=0.0)
        scored.append((best_score, medicine))

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_medicine = scored[0]
    alternatives = [medicine["name"] for score, medicine in scored[1:4] if score > 0.35]

    strength_bonus = 0.0
    if strength and best_medicine.get("strength") and normalize(strength) == normalize(best_medicine["strength"]):
        strength_bonus = 0.05

    match_score = round(min(1.0, best_score + strength_bonus), 3)
    confidence = round(min(0.99, 0.45 + 0.55 * match_score), 3)

    return {
        "id": best_medicine["id"],
        "text": text,
        "matched_name": best_medicine["name"],
        "generic_name": best_medicine.get("generic_name"),
        "strength": strength or best_medicine.get("strength"),
        "form": best_medicine.get("form"),
        "match_score": match_score,
        "confidence": confidence,
        "alternatives": alternatives,
    }
