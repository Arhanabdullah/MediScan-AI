"""Structured, correlation-aware logging for the processing pipeline."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator

from app.services.telemetry import METRICS

correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_STRUCT_FIELDS = ("stage", "duration_ms", "engine", "input_hash", "output_summary")


class JSONFormatter(logging.Formatter):
    """Minimal JSON formatter - no third-party dependency required."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id.get(),
        }
        for key in _STRUCT_FIELDS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str | None = None) -> logging.Logger:
    """Configure the root 'mediscan' logger once and return it."""
    logger = logging.getLogger("mediscan")
    logger.setLevel((level or os.getenv("MEDISCAN_LOG_LEVEL", "INFO")).upper())
    if not any(getattr(handler, "_mediscan", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JSONFormatter())
        handler._mediscan = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger of the configured 'mediscan' logger."""
    configure_logging()
    return logging.getLogger(f"mediscan.{name}")


def new_correlation_id() -> str:
    """Create and bind a correlation ID for the current request context."""
    value = uuid.uuid4().hex
    correlation_id.set(value)
    return value


def bind_correlation_id(value: str | None) -> str:
    """Bind a supplied correlation ID, or generate one when absent."""
    return value if value else new_correlation_id()


@contextmanager
def log_stage(stage: str, **fields: Any) -> Iterator[None]:
    """Log stage start/end with elapsed milliseconds and extra fields."""
    logger = get_logger("pipeline")
    started = time.perf_counter()
    METRICS.inc("stage_total", stage=stage)
    logger.info("stage_start", extra={"stage": stage, **fields})
    try:
        yield
    except Exception as error:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        METRICS.inc("stage_errors_total", stage=stage)
        METRICS.observe("stage_duration_ms", duration_ms, stage=stage)
        logger.exception(
            "stage_error",
            extra={"stage": stage, "duration_ms": duration_ms, **fields},
        )
        raise
    else:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        METRICS.observe("stage_duration_ms", duration_ms, stage=stage)
        logger.info(
            "stage_end",
            extra={"stage": stage, "duration_ms": duration_ms, **fields},
        )
