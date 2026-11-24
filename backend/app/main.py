import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import (
    Entity,
    HealthResponse,
    ImageSize,
    MedicineMatch,
    ScanResponse,
    VerificationRequest,
    VerificationResponse,
)
from app.services.confidence import calculate_confidence
from app.services.medicines import MEDICINES, match_medicine
from app.services.nlp import extract_entities
from app.services.ocr import extract_text
from app.services.preprocess import preprocess_image

app = FastAPI(title=settings.project_name, version="0.1.0")

origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DISCLAIMER = (
    "MediScan-AI is an educational prescription digitization and medicine-name extraction "
    "prototype. It is not a diagnostic system, prescribing system, or substitute for "
    "professional medical advice. Verify all extracted information with a qualified professional."
)

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/bmp", "image/tiff"}
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

SCANS: dict[str, dict] = {}
VERIFICATIONS: dict[str, dict] = {}


async def _read_upload(upload: UploadFile) -> bytes:
    content_type = (upload.content_type or "").lower()
    suffix = Path(upload.filename or "").suffix.lower()

    if content_type not in ALLOWED_TYPES and suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Upload a PNG, JPEG, WEBP, BMP, or TIFF image.")

    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded file is too large.")
    return data


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.project_name,
        ocr_backend=settings.ocr_backend,
        medicine_count=len(MEDICINES),
    )


@app.get("/health", response_model=HealthResponse, include_in_schema=False)
async def root_health() -> HealthResponse:
    return await health()


@app.post("/api/scan", response_model=ScanResponse)
async def scan(file: UploadFile = File(...)) -> ScanResponse:
    data = await _read_upload(file)

    try:
        processed, size, warnings = preprocess_image(data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    raw_text, ocr_engine, ocr_warnings = extract_text(processed)
    warnings.extend(ocr_warnings)
    entities = extract_entities(raw_text)
    strength_values = [entity["value"] for entity in entities["strengths"]]
    medicines: list[MedicineMatch] = []

    for index, entity in enumerate(entities["medicine_names"]):
        strength = None
        if strength_values:
            strength = strength_values[index] if index < len(strength_values) else strength_values[0]
        match = match_medicine(entity["value"], strength)
        match["confidence"] = round(
            0.7 * match["confidence"] + 0.3 * entity["confidence"],
            3,
        )
        medicines.append(MedicineMatch(**match))

    overall_confidence = calculate_confidence(
        raw_text,
        entities,
        [medicine.model_dump() for medicine in medicines],
        ocr_engine,
        warnings,
    )

    response = ScanResponse(
        scan_id=str(uuid.uuid4()),
        filename=file.filename or "prescription",
        image_size=ImageSize(**size),
        ocr_engine=ocr_engine,
        raw_text=raw_text,
        entities={key: [Entity(**entity) for entity in value] for key, value in entities.items()},
        medicines=medicines,
        overall_confidence=overall_confidence,
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
    SCANS[response.scan_id] = response.model_dump()
    return response


@app.get("/api/scan/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: str) -> ScanResponse:
    scan_result = SCANS.get(scan_id)
    if not scan_result:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return ScanResponse(**scan_result)


@app.post("/api/verify", response_model=VerificationResponse)
async def verify(payload: VerificationRequest) -> VerificationResponse:
    scan_result = SCANS.get(payload.scan_id)
    if not scan_result:
        raise HTTPException(status_code=404, detail="Scan not found.")

    submitted = {item.id: item for item in payload.medicines}
    final_medicines = []

    for medicine in scan_result["medicines"]:
        update = submitted.get(medicine["id"])
        if update:
            final_medicines.append(
                {
                    **medicine,
                    "name": update.name,
                    "matched_name": update.name,
                    "strength": update.strength if update.strength is not None else medicine["strength"],
                    "frequency": update.frequency,
                    "confirmed": update.confirmed,
                    "confidence": 1.0 if update.confirmed else medicine["confidence"],
                }
            )
        else:
            final_medicines.append({**medicine, "confirmed": False})

    saved_at = datetime.now(timezone.utc)
    final_result = {
        "scan_id": payload.scan_id,
        "filename": scan_result["filename"],
        "raw_text": payload.raw_text if payload.raw_text is not None else scan_result["raw_text"],
        "medicines": final_medicines,
        "overall_confidence": 1.0 if all(item["confirmed"] for item in final_medicines) else scan_result["overall_confidence"],
        "disclaimer": DISCLAIMER,
    }
    VERIFICATIONS[payload.scan_id] = final_result
    return VerificationResponse(
        scan_id=payload.scan_id,
        status="verified",
        final_result=final_result,
        saved_at=saved_at,
    )
