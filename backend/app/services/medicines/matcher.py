"""Fuzzy medicine matching with optional phonetic and form-aware scoring."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

from app.config import settings
from app.services.protocols import EntityResult, MedicineMatchDict

from .models import Medicine
from .provider import get_repository

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None

try:  # optional - a built-in Soundex fallback is always available
    from jellyfish import metaphone as _metaphone
except ImportError:
    _metaphone = None

MATCHING: dict[str, Any] = settings.matching
_CACHE_SIZE = int(MATCHING.get("score_cache_size", 8192))


@lru_cache(maxsize=_CACHE_SIZE)
def normalize(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"^\s*(?:\d+[.)]?|[-•*])\s*", "", value)
    value = re.sub(r"[^a-z0-9\s]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


@lru_cache(maxsize=_CACHE_SIZE)
def _score(left: str, right: str) -> float:
    if fuzz is not None:
        return fuzz.ratio(left, right) / 100
    return SequenceMatcher(None, left, right).ratio()


_SOUNDEX_CODES = {
    **dict.fromkeys("BFPV", "1"),
    **dict.fromkeys("CGJKQSXZ", "2"),
    **dict.fromkeys("DT", "3"),
    "L": "4",
    "N": "5",
    "R": "6",
}


def _soundex(value: str) -> str:
    letters = [char for char in value.upper() if char.isalpha()]
    if not letters:
        return ""
    output = [letters[0]]
    previous = _SOUNDEX_CODES.get(letters[0], "")
    for char in letters[1:]:
        code = _SOUNDEX_CODES.get(char, "")
        if code:
            if code != previous:
                output.append(code)
            previous = code
        else:
            previous = ""
    return ("".join(output) + "000")[:4]


@lru_cache(maxsize=_CACHE_SIZE)
def phonetic_key(value: str) -> str:
    """Metaphone when jellyfish is installed, otherwise deterministic Soundex."""
    word = normalize(value)
    if not word:
        return ""
    if _metaphone is not None:
        try:
            return str(_metaphone(word)).upper()
        except Exception:
            pass
    return _soundex(word)


_INDEX_CACHE: tuple[tuple, list[tuple[Medicine, tuple[str, ...]]]] | None = None


def _index() -> list[tuple[Medicine, tuple[str, ...]]]:
    """Normalise the vocabulary once, rebuilding when the repository changes."""
    global _INDEX_CACHE
    medicines = get_repository().all()
    signature = tuple(
        (item.id, item.name, item.generic_name, item.strength, item.form, tuple(item.aliases), item.min_score)
        for item in medicines
    )
    if _INDEX_CACHE is None or _INDEX_CACHE[0] != signature:
        # Normalise once so case/punctuation differences never cost similarity.
        _INDEX_CACHE = (
            signature,
            [(item, tuple(dict.fromkeys(normalize(name) for name in item.search_names if normalize(name)))) for item in medicines],
        )
    return _INDEX_CACHE[1]


def _combined_score(candidate: str, names: tuple[str, ...]) -> float:
    best = max((_score(candidate, name) for name in names if name), default=0.0)
    if not MATCHING.get("phonetic_enabled", True) or best >= 1.0:
        return best
    candidate_key = phonetic_key(candidate)
    if not candidate_key:
        return best
    phonetic_match = 1.0 if any(phonetic_key(name) == candidate_key for name in names if name) else 0.0
    weight = min(1.0, max(0.0, float(MATCHING.get("phonetic_weight", 0.2))))
    return (1.0 - weight) * best + weight * phonetic_match


def _bonus(medicine: Medicine, strength: str | None, form: str | None) -> float:
    bonus = 0.0
    if strength and medicine.strength and normalize(strength) == normalize(medicine.strength):
        bonus += float(MATCHING.get("strength_bonus", 0.05))
    if form and medicine.form:
        candidate_form = normalize(form).rstrip("s")
        stored_form = normalize(medicine.form).rstrip("s")
        if candidate_form and candidate_form == stored_form:
            bonus += float(MATCHING.get("form_bonus", 0.02))
    return bonus


def match_medicine(
    text: str,
    strength: str | None = None,
    form: str | None = None,
    min_score: float | None = None,
) -> MedicineMatchDict | None:
    """Return the best eligible fuzzy match, or None below the threshold."""
    candidate = normalize(text)
    if not candidate:
        return None

    scored = sorted(
        ((_combined_score(candidate, names), medicine) for medicine, names in _index()),
        key=lambda item: item[0],
        reverse=True,
    )

    global_min = float(MATCHING.get("min_score", 0.0)) if min_score is None else min_score
    chosen_index = -1
    chosen_score = 0.0
    chosen_medicine: Medicine | None = None

    for index, (raw_score, medicine) in enumerate(scored):
        final_score = min(1.0, raw_score + _bonus(medicine, strength, form))
        threshold = max(global_min, float(medicine.min_score or 0.0))
        if final_score >= threshold:
            chosen_index, chosen_score, chosen_medicine = index, final_score, medicine
            break

    if chosen_medicine is None:
        return None

    alternatives = [
        medicine.name
        for score, medicine in scored[chosen_index + 1 :]
        if score > float(MATCHING.get("alternative_threshold", 0.35))
    ][: int(MATCHING.get("max_alternatives", 3))]

    match_score = round(chosen_score, 3)
    confidence = round(
        min(
            float(MATCHING.get("confidence_cap", 0.99)),
            float(MATCHING.get("base_confidence", 0.45))
            + float(MATCHING.get("score_scale", 0.55)) * match_score,
        ),
        3,
    )

    return {
        "id": chosen_medicine.id,
        "text": text,
        "matched_name": chosen_medicine.name,
        "generic_name": chosen_medicine.generic_name,
        "strength": strength or chosen_medicine.strength,
        "form": form or chosen_medicine.form,
        "match_score": match_score,
        "confidence": confidence,
        "alternatives": alternatives,
    }


def match_entities(entities: EntityResult) -> list[MedicineMatchDict]:
    """Pair detected strengths/forms with medicine candidates and score each."""
    strengths = [entity["value"] for entity in entities["strengths"]]
    forms = [entity["value"] for entity in entities["forms"]]
    matches: list[MedicineMatchDict] = []
    match_weight = float(MATCHING.get("match_confidence_weight", 0.7))
    entity_weight = float(MATCHING.get("entity_confidence_weight", 0.3))

    for index, entity in enumerate(entities["medicine_names"]):
        strength = strengths[index] if index < len(strengths) else (strengths[0] if strengths else None)
        form = forms[index] if index < len(forms) else (forms[0] if forms else None)
        match = match_medicine(entity["value"], strength, form)
        if match is None:
            continue
        match["confidence"] = round(
            match_weight * match["confidence"] + entity_weight * entity["confidence"],
            3,
        )
        matches.append(match)

    return matches
