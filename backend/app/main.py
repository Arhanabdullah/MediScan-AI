from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
from app.services.confidence import calculate_breakdown, get_registry
from app.services.logging import bind_correlation_id, get_logger, log_stage
from app.services.medicines import get_repository, match_entities
from app.services.nlp import extract_entities
from app.services.ocr import extract_text, preferred_preprocess_mode
from app.services.preprocess import preprocess_image
from app.services.telemetry import METRICS
from app.services.protocols import ConfidenceContext

app = FastAPI(title=settings.project_name, version="0.1.0")

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


@app.post("/api/scan", response_model=ScanResponse)
async def scan(request: Request, response: Response, file: UploadFile = File(...)) -> ScanResponse:
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

    METRICS.inc("scans_total", engine=ocr_engine, has_warnings=bool(warnings))
    METRICS.observe("scan_duration_ms", (time.perf_counter() - started) * 1000, engine=ocr_engine)
    METRICS.observe("scan_confidence", overall_confidence, engine=ocr_engine)
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
