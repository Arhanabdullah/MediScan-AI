"""Central settings, loaded from environment variables and YAML config files."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from config.loader import (
    load_confidence_config,
    load_matching_config,
    load_medicines_config,
    load_model_config,
    load_nlp_config,
    load_ocr_config,
    load_patterns,
)

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent

# Load backend/.env without overriding variables already set in the environment.
load_dotenv(BACKEND_DIR / ".env")

# Last-resort fallback so the API still boots if the fixture file is missing.
_MINIMAL_DEMO_TEXT = "Rx\n1. Paracetamol 500 mg tablet twice daily\n"


def _env_weights(name: str = "CONFIDENCE_WEIGHTS") -> dict[str, float]:
    raw = os.getenv(name)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {key: float(value) for key, value in parsed.items() if isinstance(value, (int, float))}


def _load_demo_text() -> str:
    path = Path(os.getenv("DEMO_TEXT_PATH", str(BACKEND_DIR / "tests" / "fixtures" / "demo_prescription.txt")))
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return _MINIMAL_DEMO_TEXT


class Settings:
    def __init__(self) -> None:
        self.project_name: str = os.getenv("PROJECT_NAME", "MediScan-AI API")
        self.max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
        self.max_image_dimension: int = int(os.getenv("MAX_IMAGE_DIMENSION", "1800"))
        self.ocr_backend: str = os.getenv("OCR_BACKEND", "auto").lower()
        self.tesseract_cmd: str | None = os.getenv("TESSERACT_CMD") or None
        self.medicine_db_path: Path = Path(
            os.getenv("MEDICINE_DB_PATH", str(BASE_DIR / "data" / "medicines.json"))
        )
        # Persistence and authentication (Level 8).
        self.database_url: str = os.getenv(
            "DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'mediscan.db'}"
        )
        self.jwt_secret_key: str = os.getenv(
            "JWT_SECRET_KEY", "dev-only-change-me-to-a-long-random-value-before-production"
        )
        self.jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
        self.upload_dir: Path = Path(os.getenv("UPLOAD_DIR", str(BACKEND_DIR / "uploads")))
        self.cors_origins: list[str] = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if origin.strip()
        ]

        # YAML-backed configuration (see backend/config/).
        self.patterns: dict[str, Any] = load_patterns()
        self.nlp: dict[str, Any] = load_nlp_config()
        self.ocr_engines: dict[str, Any] = load_ocr_config()["engines"]
        self.ocr_fallback: str = str(load_ocr_config().get("fallback", "demo"))

        confidence = load_confidence_config()
        weights: dict[str, float] = {**confidence["weights"], **_env_weights()}
        total = sum(max(0.0, value) for value in weights.values())
        self.confidence_weights: dict[str, float] = (
            {key: max(0.0, value) / total for key, value in weights.items()} if total else confidence["weights"]
        )
        self.confidence_penalties: dict[str, float] = confidence["penalties"]
        self.ocr_scores: dict[str, float] = confidence["ocr_scores"]
        self.text_length_reference: int = int(confidence.get("text_length_reference", 300))
        self.confidence_min: float = float(confidence.get("min_score", 0.05))
        self.confidence_max: float = float(confidence.get("max_score", 0.99))
        self.confidence_models: dict[str, Any] = confidence["models"]
        self.confidence_v2_weights: dict[str, float] = {
            **dict(confidence["models"]["variants"].get("weighted-v2", {}).get("weights", {})),
            **_env_weights("CONFIDENCE_WEIGHTS_V2"),
        }

        self.matching: dict[str, Any] = load_matching_config()
        self.model: dict[str, Any] = load_model_config()

        medicine_config = load_medicines_config()
        self.medicines_repository: dict[str, Any] = {
            **medicine_config["repository"],
            "backend": os.getenv("MEDICINE_REPO", medicine_config["repository"]["backend"]).lower(),
            "sqlite_path": os.getenv(
                "MEDICINE_SQLITE_PATH", medicine_config["repository"]["sqlite_path"]
            ),
            "hot_reload": str(medicine_config["repository"].get("hot_reload", True)).lower() == "true",
        }
        self.medicines_validation: dict[str, Any] = medicine_config["validation"]

        # Synthetic development text now lives in a test fixture, not in config.
        self.demo_text: str = _load_demo_text()


settings = Settings()
