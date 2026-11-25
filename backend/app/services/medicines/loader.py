"""Import/export helpers used by the admin CLI and migration script."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

from .models import Medicine
from .validation import validate_records


def load_from_json(path: Path | str) -> list[Medicine]:
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list of medicines.")
    return validate_records(data)


def load_from_csv(path: Path | str, alias_separator: str = "|") -> list[Medicine]:
    """Read a CSV with columns id,name,generic_name,strength,form,aliases[,min_score]."""
    records: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            record: dict[str, Any] = {key: value for key, value in row.items() if key is not None}
            aliases = record.get("aliases") or ""
            record["aliases"] = [item.strip() for item in aliases.split(alias_separator) if item.strip()]
            for optional in ("generic_name", "strength", "form", "min_score"):
                if record.get(optional) == "":
                    record[optional] = None
            records.append(record)
    return validate_records(records)


def export_to_json(medicines: list[Medicine], path: Path | str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = [medicine.model_dump(exclude_none=True) for medicine in medicines]
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
