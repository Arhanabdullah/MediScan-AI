"""SQLite medicine repository (same interface as the JSON repository).

The schema and queries use only stdlib sqlite3 and parameterised statements,
so a PostgreSQL implementation can reuse the repository interface later.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Medicine
from .validation import validate_records

SCHEMA = """
CREATE TABLE IF NOT EXISTS medicines (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    generic_name TEXT,
    strength     TEXT,
    form         TEXT,
    aliases      TEXT NOT NULL DEFAULT '[]',
    min_score    REAL
);
CREATE INDEX IF NOT EXISTS idx_medicines_name ON medicines(name);
CREATE INDEX IF NOT EXISTS idx_medicines_generic ON medicines(generic_name);
"""


class SqlMedicineRepository:
    source = "sqlite"

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _row_to_medicine(row: tuple) -> Medicine:
        try:
            aliases = json.loads(row[5])
        except (TypeError, ValueError):
            aliases = []
        return Medicine(
            id=row[0],
            name=row[1],
            generic_name=row[2],
            strength=row[3],
            form=row[4],
            aliases=aliases,
            min_score=row[6],
        )

    @staticmethod
    def _medicine_to_row(medicine: Medicine) -> tuple:
        return (
            medicine.id,
            medicine.name,
            medicine.generic_name,
            medicine.strength,
            medicine.form,
            json.dumps(medicine.aliases, ensure_ascii=False),
            medicine.min_score,
        )

    def all(self) -> list[Medicine]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, generic_name, strength, form, aliases, min_score "
                "FROM medicines ORDER BY name"
            ).fetchall()
        return [self._row_to_medicine(row) for row in rows]

    def get(self, medicine_id: str) -> Medicine | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, name, generic_name, strength, form, aliases, min_score "
                "FROM medicines WHERE id = ?",
                (medicine_id,),
            ).fetchone()
        return self._row_to_medicine(row) if row else None

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM medicines").fetchone()[0])

    def reload(self) -> None:
        """SQL reads are live, so no in-memory cache needs invalidating."""

    def replace_all(self, medicines: list[Medicine]) -> int:
        """Atomically replace the table contents; used by the migration CLI."""
        records = [
            medicine.model_dump() if isinstance(medicine, Medicine) else dict(medicine)
            for medicine in medicines
        ]
        validated = validate_records(records)
        rows = [self._medicine_to_row(medicine) for medicine in validated]
        with self._connect() as connection:
            connection.execute("DELETE FROM medicines")
            connection.executemany(
                "INSERT INTO medicines (id, name, generic_name, strength, form, aliases, min_score) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)
