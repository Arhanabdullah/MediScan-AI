"""Repository selection and singleton access."""

from __future__ import annotations

from pathlib import Path

from app.config import BACKEND_DIR, settings

from .json_repo import JsonMedicineRepository
from .repository import MedicineRepository
from .sql_repo import SqlMedicineRepository


def build_repository() -> MedicineRepository:
    """Create the configured repository (JSON by default)."""
    config = settings.medicines_repository
    if config.get("backend") == "sqlite":
        path = Path(str(config.get("sqlite_path", "data/medicines.db")))
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return SqlMedicineRepository(path)

    return JsonMedicineRepository(
        settings.medicine_db_path,
        hot_reload=bool(config.get("hot_reload", True)),
        validation=settings.medicines_validation,
    )


_repository: MedicineRepository = build_repository()


def get_repository() -> MedicineRepository:
    return _repository


def set_repository(repository: MedicineRepository) -> None:
    """Replace the active repository (used by tests and admin tooling)."""
    global _repository
    _repository = repository
