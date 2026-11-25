import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_optional_user
from app.config import BASE_DIR, settings
from app.db import Base, engine, get_db
from app.models import DetectedMedicine, Prescription, User
from app.schemas import (
    Entity,
    EvaluationResponse,
    HealthResponse,
    HistoryItem,
    ImageSize,
    MedicineMatch,
    ModelInfoResponse,
    ResultDetail,
    ScanResponse,
    Token,
    UserCreate,
    UserLogin,
    UserOut,
    VerificationRequest,
    VerificationResponse,
)
from app.services.confidence import calculate_confidence
from app.services.evaluation import evaluate_samples
from app.services.medicines import MEDICINES, match_medicine
from app.services.nlp import extract_entities
from app.services.ocr import extract_text
from app.services.preprocess import preprocess_image
from app.services.security import create_access_token, hash_password, verify_password

app = FastAPI(title=settings.project_name, version="0.2.0")
Base.metadata.create_all(bind=engine)

origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,http://localhost:3000,http://127.0.0.1:3000",
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


def _save_image(user_id: int, scan_id: str, filename: str, data: bytes) -> Path:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        suffix = ".png"
    directory = settings.upload_dir / str(user_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{scan_id}{suffix}"
    path.write_bytes(data)
    return path


def _delete_image(path: str) -> None:
    Path(path).unlink(missing_ok=True)


def _scan_from_db(prescription: Prescription) -> dict:
    stored = prescription.response_json or {}
    if stored:
        return stored

    return {
        "scan_id": prescription.id,
        "filename": prescription.filename,
        "raw_text": prescription.raw_text,
        "ocr_engine": prescription.ocr_engine,
        "overall_confidence": prescription.overall_confidence,
        "warnings": prescription.warnings or [],
        "medicines": [
            {
                "id": str(medicine.id),
                "text": medicine.text,
                "matched_name": medicine.matched_name,
                "generic_name": medicine.generic_name,
                "strength": medicine.strength,
                "form": medicine.form,
                "match_score": medicine.match_score,
                "confidence": medicine.confidence,
                "alternatives": [],
            }
            for medicine in prescription.detected_medicines
        ],
    }


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


@app.post("/api/auth/register", response_model=UserOut)
async def register(payload: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    existing = db.query(User).filter((User.username == payload.username) | (User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username or email is already registered.")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/auth/login", response_model=Token)
async def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    return Token(access_token=create_access_token(user.username))


@app.get("/api/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return current_user


@app.get("/api/model-info", response_model=ModelInfoResponse)
async def model_info() -> ModelInfoResponse:
    return ModelInfoResponse(
        name="MediScan-AI Baseline",
        version="0.2.0",
        approach="rule-based pipeline with fuzzy matching",
        ocr_backend=settings.ocr_backend,
        extraction="regex and vocabulary-based entity extraction",
        matching="RapidFuzz ratio with alias and strength handling",
        confidence="heuristic blend of OCR, text, entity, and match signals",
        trained_model=False,
        note="No trained ML/DL model is active. See MODEL.md for the experiment roadmap.",
    )


@app.get("/api/evaluation", response_model=EvaluationResponse)
async def evaluation() -> EvaluationResponse:
    sample_path = BASE_DIR.parent / "data" / "eval_samples.json"
    with sample_path.open(encoding="utf-8") as file:
        samples = json.load(file)
    return EvaluationResponse(**evaluate_samples(samples))


@app.post("/api/scan", response_model=ScanResponse)
@app.post("/api/prescription/analyze", response_model=ScanResponse, include_in_schema=False)
@app.post("/api/upload", response_model=ScanResponse, include_in_schema=False)
async def scan(
    file: UploadFile = File(...),
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> ScanResponse:
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

    if current_user:
        image_path = _save_image(current_user.id, response.scan_id, response.filename, data)
        prescription = Prescription(
            id=response.scan_id,
            user_id=current_user.id,
            filename=response.filename,
            image_path=str(image_path),
            raw_text=response.raw_text,
            ocr_engine=response.ocr_engine,
            overall_confidence=response.overall_confidence,
            warnings=response.warnings,
            response_json=response.model_dump(),
        )
        db.add(prescription)
        db.flush()
        for medicine in medicines:
            db.add(
                DetectedMedicine(
                    prescription_id=response.scan_id,
                    text=medicine.text,
                    matched_name=medicine.matched_name,
                    generic_name=medicine.generic_name,
                    strength=medicine.strength,
                    form=medicine.form,
                    match_score=medicine.match_score,
                    confidence=medicine.confidence,
                )
            )
        db.commit()

    return response


@app.get("/api/scan/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: str,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> ScanResponse:
    prescription = db.query(Prescription).filter(Prescription.id == scan_id).first()
    if prescription:
        if not current_user or prescription.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Scan not found.")
        return ScanResponse(**_scan_from_db(prescription))

    scan_result = SCANS.get(scan_id)
    if not scan_result:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return ScanResponse(**scan_result)


@app.get("/api/history", response_model=list[HistoryItem])
async def history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HistoryItem]:
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.user_id == current_user.id)
        .order_by(Prescription.created_at.desc())
        .all()
    )
    return [
        HistoryItem(
            scan_id=prescription.id,
            filename=prescription.filename,
            created_at=prescription.created_at,
            overall_confidence=prescription.overall_confidence,
            medicine_count=len(prescription.detected_medicines),
            verified=prescription.verified,
        )
        for prescription in prescriptions
    ]


@app.get("/api/result/{result_id}", response_model=ResultDetail)
async def get_result(
    result_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResultDetail:
    prescription = (
        db.query(Prescription)
        .filter(Prescription.id == result_id, Prescription.user_id == current_user.id)
        .first()
    )
    if not prescription:
        raise HTTPException(status_code=404, detail="Result not found.")

    return ResultDetail(
        scan_id=prescription.id,
        filename=prescription.filename,
        raw_text=prescription.raw_text,
        ocr_engine=prescription.ocr_engine,
        overall_confidence=prescription.overall_confidence,
        warnings=prescription.warnings or [],
        medicines=[
            {
                "id": str(medicine.id),
                "name": medicine.matched_name,
                "strength": medicine.strength,
                "frequency": medicine.frequency,
                "confidence": medicine.confidence,
                "confirmed": medicine.confirmed,
            }
            for medicine in prescription.detected_medicines
        ],
        created_at=prescription.created_at,
        verified=prescription.verified,
    )


@app.delete("/api/result/{result_id}")
async def delete_result(
    result_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    prescription = (
        db.query(Prescription)
        .filter(Prescription.id == result_id, Prescription.user_id == current_user.id)
        .first()
    )
    if not prescription:
        raise HTTPException(status_code=404, detail="Result not found.")

    image_path = prescription.image_path
    db.delete(prescription)
    db.commit()
    _delete_image(image_path)
    return {"status": "deleted"}


@app.post("/api/verify", response_model=VerificationResponse)
async def verify(
    payload: VerificationRequest,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> VerificationResponse:
    prescription = None
    if current_user:
        prescription = (
            db.query(Prescription)
            .filter(Prescription.id == payload.scan_id, Prescription.user_id == current_user.id)
            .first()
        )
        scan_result = _scan_from_db(prescription) if prescription else None
    else:
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

    if prescription:
        for medicine in prescription.detected_medicines:
            update = submitted.get(str(medicine.id))
            if update:
                medicine.matched_name = update.name
                medicine.strength = update.strength if update.strength is not None else medicine.strength
                medicine.frequency = update.frequency
                medicine.confirmed = update.confirmed
                medicine.confidence = 1.0 if update.confirmed else medicine.confidence
        prescription.verified = all(item["confirmed"] for item in final_medicines)
        db.commit()

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
