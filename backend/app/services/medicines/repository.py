"""Repository interface for medicine persistence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import Medicine


@runtime_checkable
class MedicineRepository(Protocol):
    """Backend-agnostic read interface used by the matcher and API."""

    source: str

    def all(self) -> list[Medicine]: ...

    def get(self, medicine_id: str) -> Medicine | None: ...

    def count(self) -> int: ...

    def reload(self) -> None: ...
