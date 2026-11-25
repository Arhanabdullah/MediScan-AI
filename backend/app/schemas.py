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


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HistoryMedicine(BaseModel):
    id: str
    name: str
    strength: str | None = None
    frequency: str | None = None
    confidence: float = Field(ge=0, le=1)
    confirmed: bool = False


class HistoryItem(BaseModel):
    scan_id: str
    filename: str
    created_at: datetime
    overall_confidence: float = Field(ge=0, le=1)
    medicine_count: int
    verified: bool


class ResultDetail(BaseModel):
    scan_id: str
    filename: str
    raw_text: str
    ocr_engine: str
    overall_confidence: float = Field(ge=0, le=1)
    warnings: list[str]
    medicines: list[HistoryMedicine]
    created_at: datetime
    verified: bool


class ModelInfoResponse(BaseModel):
    name: str
    version: str
    approach: str
    ocr_backend: str
    extraction: str
    matching: str
    confidence: str
    trained_model: bool
    note: str


class EvaluationResponse(BaseModel):
    sample_count: int
    cer: float
    wer: float
    medicine_precision: float
    medicine_recall: float
    medicine_f1: float
    note: str
