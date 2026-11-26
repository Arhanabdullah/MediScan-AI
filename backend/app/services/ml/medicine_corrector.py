"""Lazy inference for the synthetic OCR-typo medicine classifier."""

from __future__ import annotations

import importlib.util
import json
import re
import threading
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR, settings
from app.services.logging import get_logger

logger = get_logger("ml")

CONFIG: dict[str, Any] = settings.model["medicine_corrector"]
_lock = threading.Lock()
_instance: MedicineCorrector | None = None  # type: ignore[name-defined]
_injected: Any | None = None


def _normalize(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"^\s*(?:\d+[.)]?|[-•*])\s*", "", value)
    value = re.sub(r"[^a-z0-9\s]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _load_metadata() -> dict[str, Any]:
    path = BACKEND_DIR / str(CONFIG.get("metadata", "data/models/medicine_corrector.json"))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


class MedicineCorrector:
    """Thin wrapper around the persisted sklearn pipeline."""

    def __init__(
        self,
        pipeline: Any | None,
        metadata: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.metadata = dict(metadata or {})
        self.config = dict(config or CONFIG)

    def available(self) -> bool:
        return self.pipeline is not None and hasattr(self.pipeline, "predict_proba")

    def predict(self, text: str) -> tuple[str, float] | None:
        """Return (canonical_name, probability) when confident, else None."""
        if not self.available():
            return None
        normalized = _normalize(text)
        if not normalized:
            return None
        try:
            probabilities = self.pipeline.predict_proba([normalized])[0]
            index = int(probabilities.argmax())
            score = float(probabilities[index])
            label = str(self.pipeline.classes_[index])
        except Exception as error:
            logger.warning("medicine_corrector_failed", extra={"output_summary": str(error)})
            return None
        if score < float(self.config.get("min_score", 0.6)):
            return None
        return label, round(score, 3)

    def info(self) -> dict[str, Any]:
        return {
            "name": self.metadata.get("name", "medicine-corrector"),
            "version": self.metadata.get("version", "untrained"),
            "enabled": bool(self.config.get("enabled", False)),
            "available": self.available(),
            "method": self.metadata.get("method", "not trained"),
            "metrics": self.metadata.get("metrics", {}),
            "note": self.metadata.get(
                "note", "No trained medicine corrector artifact is loaded."
            ),
        }


def _load_pipeline() -> Any | None:
    if not CONFIG.get("enabled", False):
        return None
    if importlib.util.find_spec("sklearn") is None or importlib.util.find_spec("joblib") is None:
        logger.warning("medicine_corrector_unavailable", extra={"output_summary": "sklearn/joblib missing"})
        return None
    artifact = BACKEND_DIR / str(CONFIG.get("artifact", "data/models/medicine_corrector.joblib"))
    if not artifact.is_file():
        return None
    try:
        import joblib

        payload = joblib.load(artifact)
        return payload.get("pipeline") if isinstance(payload, dict) else payload
    except Exception as error:
        logger.warning("medicine_corrector_load_failed", extra={"output_summary": str(error)})
        return None


def get_medicine_corrector() -> MedicineCorrector:
    global _instance
    with _lock:
        if _instance is None:
            pipeline = _injected if _injected is not None else _load_pipeline()
            _instance = MedicineCorrector(pipeline, _load_metadata())
        return _instance


def set_medicine_corrector(corrector: Any | None) -> None:
    """Inject a corrector for tests/custom deployments."""
    global _instance, _injected
    with _lock:
        _injected = corrector
        _instance = None


def reset_medicine_corrector() -> None:
    """Clear cached inference state (called after training or config changes)."""
    global _instance
    with _lock:
        _instance = None
