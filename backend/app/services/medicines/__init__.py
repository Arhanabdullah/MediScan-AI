"""Medicine repository, validation, loading and fuzzy matching.

Public names are re-exported so existing imports such as
``from app.services.medicines import MEDICINES, match_medicine`` keep working.
"""

from __future__ import annotations

from typing import Any

from .json_repo import JsonMedicineRepository
from .loader import export_to_json, load_from_csv, load_from_json
from .matcher import MATCHING, match_entities, match_medicine, normalize, phonetic_key
from .models import Medicine
from .provider import build_repository, get_repository, set_repository
from .repository import MedicineRepository
from .sql_repo import SqlMedicineRepository
from .validation import validate_records

medicine_repository = get_repository()


def _snapshot() -> list[dict[str, Any]]:
    return [medicine.model_dump() for medicine in medicine_repository.all()]


# Backwards-compatible snapshot. New code should use get_repository() so that
# hot-reload and alternative backends are respected.
MEDICINES: list[dict[str, Any]] = _snapshot()

__all__ = [
    "MEDICINES",
    "MATCHING",
    "JsonMedicineRepository",
    "Medicine",
    "MedicineRepository",
    "SqlMedicineRepository",
    "build_repository",
    "export_to_json",
    "get_repository",
    "load_from_csv",
    "load_from_json",
    "match_entities",
    "match_medicine",
    "normalize",
    "phonetic_key",
    "set_repository",
    "validate_records",
]
