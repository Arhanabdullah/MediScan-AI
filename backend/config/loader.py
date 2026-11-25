"""Loading and validation for YAML configuration files.

Config files live in backend/config/ (outside app/) so that ``app/config.py``
can keep providing the ``settings`` object used across the codebase.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent

_REQUIRED_PATTERN_KEYS = ("regex", "entity_labels", "skip_prefixes")


@lru_cache(maxsize=None)
def load_yaml(filename: str) -> dict[str, Any]:
    """Load a YAML file from the config directory (cached)."""
    path = CONFIG_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Missing configuration file: {path}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Configuration file {filename} must contain a mapping.")
    return data


@lru_cache(maxsize=1)
def load_patterns() -> dict[str, Any]:
    """Entity-extraction patterns, labels and confidence hints."""
    data = load_yaml("patterns.yaml")
    missing = [key for key in _REQUIRED_PATTERN_KEYS if key not in data]
    if missing:
        raise ValueError(f"patterns.yaml is missing keys: {', '.join(missing)}")
    required_regexes = ("strength", "frequency", "duration", "form", "list_bullet", "label_prefix")
    missing_regexes = [key for key in required_regexes if key not in data["regex"]]
    if missing_regexes:
        raise ValueError(f"patterns.yaml regex section is missing: {', '.join(missing_regexes)}")
    return data


@lru_cache(maxsize=1)
def load_nlp_config() -> dict[str, Any]:
    """Extractor order, custom entity keys and post-processing rules."""
    data = load_yaml("nlp.yaml").get("nlp")
    if not isinstance(data, dict):
        raise ValueError("nlp.yaml must define an 'nlp' mapping.")
    if not isinstance(data.get("extractors"), list) or not data["extractors"]:
        raise ValueError("nlp.yaml must define a non-empty 'extractors' list.")
    if data.get("strategy") not in ("fallback", "merge"):
        raise ValueError("nlp.yaml strategy must be 'fallback' or 'merge'.")
    return data


@lru_cache(maxsize=1)
def load_ocr_config() -> dict[str, Any]:
    """OCR engine registry configuration."""
    data = load_yaml("ocr.yaml")
    if not isinstance(data.get("engines"), dict) or not data["engines"]:
        raise ValueError("ocr.yaml must define at least one engine.")
    return data


@lru_cache(maxsize=1)
def load_confidence_config() -> dict[str, Any]:
    """Weights, penalties and per-engine quality scores for confidence."""
    data = load_yaml("confidence.yaml")
    for key in ("weights", "penalties", "ocr_scores"):
        if not isinstance(data.get(key), dict):
            raise ValueError(f"confidence.yaml must define a '{key}' mapping.")
    models = data.get("models")
    if not isinstance(models, dict) or not isinstance(models.get("variants"), dict):
        raise ValueError("confidence.yaml must define a 'models.variants' mapping.")
    ab = models.get("ab") or {}
    if not isinstance(ab, dict):
        raise ValueError("confidence.yaml models.ab must be a mapping.")
    if ab.get("enabled") and ab.get("variants"):
        total = sum(float(item.get("weight", 0)) for item in ab["variants"] if isinstance(item, dict))
        if total <= 0:
            raise ValueError("confidence.yaml A/B variant weights must sum to a positive number.")
    return data


@lru_cache(maxsize=1)
def load_matching_config() -> dict[str, Any]:
    """Tunable parameters for fuzzy medicine matching."""
    data = load_yaml("matching.yaml")
    if not isinstance(data.get("matching"), dict):
        raise ValueError("matching.yaml must define a 'matching' mapping.")
    return data["matching"]


@lru_cache(maxsize=1)
def load_medicines_config() -> dict[str, Any]:
    """Repository backend, validation and hot-reload settings."""
    data = load_yaml("medicines.yaml")
    for key in ("repository", "validation"):
        if not isinstance(data.get(key), dict):
            raise ValueError(f"medicines.yaml must define a '{key}' mapping.")
    return data
