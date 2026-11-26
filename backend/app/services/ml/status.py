"""Status-only view of trained models, safe for the public model-info endpoint."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR, settings
from app.services.ml.medicine_corrector import get_medicine_corrector


def _read_metadata(path: str) -> dict[str, Any]:
    target: Path = BACKEND_DIR / path
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def get_trained_model_info() -> dict[str, Any]:
    corrector_config = settings.model["medicine_corrector"]
    ner_config = settings.model["ner"]

    try:
        spacy_installed = importlib.util.find_spec("spacy") is not None
    except (ImportError, ValueError):
        spacy_installed = False

    ner_model_path: Path = BACKEND_DIR / str(ner_config.get("model_path", ""))
    ner_metadata = _read_metadata(str(ner_config.get("metadata", "")))

    corrector = get_medicine_corrector()
    corrector_info = corrector.info()
    ner_available = bool(
        ner_config.get("enabled") and spacy_installed and ner_model_path.exists()
    )
    trained = bool(corrector_info["available"] or ner_available)
    artifacts_present = bool(
        (BACKEND_DIR / str(corrector_config.get("artifact", ""))).is_file()
        or ner_model_path.exists()
    )

    return {
        "trained_model": trained,
        "artifacts_present": artifacts_present,
        "models": {
            "medicine_corrector": corrector_info,
            "ner": {
                "name": ner_metadata.get("name", "prescription-ner"),
                "version": ner_metadata.get("version", "untrained"),
                "enabled": bool(ner_config.get("enabled", False)),
                "available": ner_available,
                "method": ner_metadata.get("method", "not trained"),
                "metrics": ner_metadata.get("metrics", {}),
                "note": ner_metadata.get("note", "No trained NER artifact is loaded."),
            },
        },
    }
