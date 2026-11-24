from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ImageSize(BaseModel):
    width: int
    height: int
    processed_width: int
    processed_height: int


class Entity(BaseModel):
    label: str
    value: str
    confidence: float = Field(ge=0, le=1)


class MedicineMatch(BaseModel):
    id: str
    text: str
    matched_name: str
    generic_name: str | None = None
    strength: str | None = None
    form: str | None = None
    match_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    alternatives: list[str] = Field(default_factory=list)


class ScanResponse(BaseModel):
    scan_id: str
    filename: str
    image_size: ImageSize
    ocr_engine: str
    raw_text: str
    entities: dict[str, list[Entity]]
    medicines: list[MedicineMatch]
    overall_confidence: float = Field(ge=0, le=1)
    warnings: list[str]
    disclaimer: str


class VerifiedMedicine(BaseModel):
    id: str
    name: str
    strength: str | None = None
    frequency: str | None = None
    confirmed: bool = True


class VerificationRequest(BaseModel):
    scan_id: str
    medicines: list[VerifiedMedicine]
    raw_text: str | None = None


class VerificationResponse(BaseModel):
    scan_id: str
    status: str
    final_result: dict[str, Any]
    saved_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str
    ocr_backend: str
    medicine_count: int
