from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_optional_user
from app.config import BACKEND_DIR, settings
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
from app.services.confidence import calculate_breakdown, get_registry
from app.services.evaluation import evaluate_samples
from app.services.logging import bind_correlation_id, get_logger, log_stage
from app.services.medicines import get_repository, match_entities
from app.services.ml import get_trained_model_info
from app.services.nlp import extract_entities
from app.services.ocr import extract_text, preferred_preprocess_mode
from app.services.preprocess import preprocess_image
from app.services.protocols import ConfidenceContext
from app.services.security import create_access_token, hash_password, verify_password
from app.services.telemetry import METRICS

app = FastAPI(title=settings.project_name, version="0.2.0")
Base.metadata.create_all(bind=engine)

pipeline_logger = get_logger("pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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
        medicine_count=get_repository().count(),
    )


@app.get("/health", response_model=HealthResponse, include_in_schema=False)
async def root_health() -> HealthResponse:
    return await health()


@app.get("/api/metrics", include_in_schema=False)
async def metrics(format: str = "prometheus") -> Response:
    """In-process pipeline metrics. Labels contain no text, filenames or PHI."""
    if format == "json":
        return JSONResponse(METRICS.snapshot())
    return Response(
        METRICS.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/api/confidence/models", include_in_schema=False)
async def confidence_models() -> dict:
    """Registered confidence models and A/B status (no patient data)."""
    registry = get_registry()
    return {
        "default": registry.default_name,
        "fallback": registry.fallback_name,
        "models": registry.names(),
        "ab_enabled": bool(registry.ab.get("enabled")),
    }


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


def _model_status_note(status: dict) -> str:
    if status["trained_model"]:
        return "Synthetic trained models are active. See MODEL.md for limitations."
    if status.get("artifacts_present"):
        return (
            "Trained models exist but are disabled by default; enable them in "
            "config/model.yaml. See MODEL.md for limitations."
        )
    return "No trained ML/DL model is active. See MODEL.md for the experiment roadmap."


@app.get("/api/model-info", response_model=ModelInfoResponse)
async def model_info() -> ModelInfoResponse:
    model_status = get_trained_model_info()
    return ModelInfoResponse(
        name="MediScan-AI Baseline",
        version="0.3.0",
        approach="modular pipeline with optional synthetic trained models",
        ocr_backend=settings.ocr_backend,
        extraction="pluggable regex/spaCy/transformer/trained-NER entity extraction",
        matching="repository-backed RapidFuzz with phonetic, strength/form and optional trained-corrector scoring",
        confidence="versioned weighted model registry with an explainable breakdown",
        trained_model=model_status["trained_model"],
        note=_model_status_note(model_status),
        trained_models=model_status["models"],
    )


@app.get("/api/evaluation", response_model=EvaluationResponse)
async def evaluation() -> EvaluationResponse:
    sample_path = BACKEND_DIR / "data" / "eval_samples.json"
    with sample_path.open(encoding="utf-8") as file:
        samples = json.load(file)
    return EvaluationResponse(**evaluate_samples(samples))


@app.post("/api/scan", response_model=ScanResponse)
@app.post("/api/prescription/analyze", response_model=ScanResponse, include_in_schema=False)
@app.post("/api/upload", response_model=ScanResponse, include_in_schema=False)
async def scan(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> ScanResponse:
    response.headers["X-Correlation-ID"] = bind_correlation_id(request.headers.get("X-Correlation-ID"))
    started = time.perf_counter()
    data = await _read_upload(file)

    mode = preferred_preprocess_mode(settings.ocr_backend)
    try:
        processed, size, warnings = preprocess_image(data, mode=mode)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    ocr_result = extract_text(processed, settings.ocr_backend)
    raw_text, ocr_engine, ocr_warnings = ocr_result
    warnings.extend(ocr_warnings)
    entities = extract_entities(raw_text)
    medicines: list[MedicineMatch] = []

    with log_stage("medicine_matching", output_summary=f"{len(entities['medicine_names'])} candidates"):
        for match in match_entities(entities):
            medicines.append(MedicineMatch(**match))

    with log_stage("confidence"):
        breakdown = calculate_breakdown(
            ConfidenceContext(
                raw_text=raw_text,
                entities=entities,
                medicines=[medicine.model_dump() for medicine in medicines],
                ocr_engine=ocr_engine,
                warnings=warnings,
            )
        )
        overall_confidence = breakdown.overall
        pipeline_logger.info(
            "confidence_breakdown",
            extra={
                "output_summary": str(
                    {
                        "components": breakdown.components,
                        "model": breakdown.metadata.get("model"),
                        "strategy": breakdown.metadata.get("strategy"),
                        "fallback_used": breakdown.metadata.get("fallback_used", False),
                    }
                )
            },
        )

    scan_result = ScanResponse(
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
    SCANS[scan_result.scan_id] = scan_result.model_dump()

    if current_user:
        image_path = _save_image(current_user.id, scan_result.scan_id, scan_result.filename, data)
        prescription = Prescription(
            id=scan_result.scan_id,
            user_id=current_user.id,
            filename=scan_result.filename,
            image_path=str(image_path),
            raw_text=scan_result.raw_text,
            ocr_engine=scan_result.ocr_engine,
            overall_confidence=scan_result.overall_confidence,
            warnings=scan_result.warnings,
            response_json=scan_result.model_dump(),
        )
        db.add(prescription)
        db.flush()
        for medicine in medicines:
            db.add(
                DetectedMedicine(
                    prescription_id=scan_result.scan_id,
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

    METRICS.inc("scans_total", engine=ocr_engine, has_warnings=bool(warnings))
    METRICS.observe("scan_duration_ms", (time.perf_counter() - started) * 1000, engine=ocr_engine)
    METRICS.observe("scan_confidence", overall_confidence, engine=ocr_engine)
    return scan_result


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
    scan_result = None

    if current_user:
        prescription = (
            db.query(Prescription)
            .filter(Prescription.id == payload.scan_id, Prescription.user_id == current_user.id)
            .first()
        )
        if prescription:
            scan_result = _scan_from_db(prescription)

    if scan_result is None:
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
        if payload.raw_text is not None:
            prescription.raw_text = payload.raw_text
        prescription.verified = all(item["confirmed"] for item in final_medicines)
        db.commit()

    saved_at = datetime.now(timezone.utc)
    final_result = {
        "scan_id": payload.scan_id,
        "filename": scan_result["filename"],
        "raw_text": payload.raw_text if payload.raw_text is not None else scan_result["raw_text"],
        "medicines": final_medicines,
        "overall_confidence": (
            1.0 if all(item["confirmed"] for item in final_medicines) else scan_result["overall_confidence"]
        ),
        "disclaimer": DISCLAIMER,
    }
    VERIFICATIONS[payload.scan_id] = final_result
    return VerificationResponse(
        scan_id=payload.scan_id,
        status="verified",
        final_result=final_result,
        saved_at=saved_at,
    )
