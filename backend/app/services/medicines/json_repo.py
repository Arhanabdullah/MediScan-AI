"""JSON medicine repository with validation and optional hot-reload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .models import Medicine
from .validation import validate_records


class JsonMedicineRepository:
    source = "json"

    def __init__(
        self,
        path: Path | str,
        *,
        hot_reload: bool = True,
        validation: Mapping[str, Any] | None = None,
    ) -> None:
        self.path = Path(path)
        self.hot_reload = hot_reload
        self.validation = dict(validation or {})
        self._records: list[Medicine] = []
        self.reload()

    def _refresh(self) -> None:
        # The dataset is small (tens of records). Reloading on access is
        # cheaper and more reliable than depending on filesystem timestamp
        # granularity, which can miss rapid successive writes.
        if self.hot_reload:
            self.reload()

    def reload(self) -> None:
        with self.path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError(f"{self.path} must contain a JSON list of medicines.")
        self._records = validate_records(
            data,
            check_duplicates=bool(self.validation.get("check_duplicates", True)),
            require_generic_name=bool(self.validation.get("require_generic_name", False)),
        )

    def all(self) -> list[Medicine]:
        self._refresh()
        return list(self._records)

    def get(self, medicine_id: str) -> Medicine | None:
        self._refresh()
        return next((item for item in self._records if item.id == medicine_id), None)

    def count(self) -> int:
        self._refresh()
        return len(self._records)
