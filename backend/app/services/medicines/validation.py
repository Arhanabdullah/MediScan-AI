"""Validation applied when medicines are loaded from any backend."""

from __future__ import annotations

from typing import Any, Mapping

from .models import Medicine


def validate_records(
    records: list[Mapping[str, Any]],
    *,
    check_duplicates: bool = True,
    require_generic_name: bool = False,
) -> list[Medicine]:
    """Parse and validate records, raising ValueError with a clear message."""
    medicines: list[Medicine] = []
    for index, record in enumerate(records):
        try:
            medicines.append(Medicine.model_validate(dict(record)))
        except Exception as error:
            raise ValueError(f"Invalid medicine at index {index}: {error}") from error

    if require_generic_name:
        missing = [medicine.id for medicine in medicines if not medicine.generic_name]
        if missing:
            raise ValueError(f"Medicines missing generic_name: {', '.join(missing)}")

    if check_duplicates:
        seen: dict[tuple[str, str, str], str] = {}
        for medicine in medicines:
            key = (
                medicine.name.strip().lower(),
                (medicine.strength or "").strip().lower(),
                (medicine.form or "").strip().lower(),
            )
            if key in seen:
                raise ValueError(
                    f"Duplicate medicine '{medicine.name}' "
                    f"(strength={medicine.strength}, form={medicine.form}); "
                    f"already defined as '{seen[key]}'."
                )
            seen[key] = medicine.id

    return medicines
