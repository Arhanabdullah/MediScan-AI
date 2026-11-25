# Phase 5 Implementation Status & Model-Optimization Process

Phase 5 of `services-optimization.md` (Explainable Confidence Model Registry +
Telemetry) is implemented. This document records what was built, the necessity
check, and how it was verified. It complements `CLAUDE.md`,
`plan/phase1-2-status.md`, `plan/phase3-status.md` and `plan/phase4-status.md`.

---

## 1. What was implemented

| Plan task | Implementation |
|-----------|----------------|
| 5.1 Model abstraction | `backend/app/services/confidence/` package: `base.py` (shared weighted formula + `ComponentScore`), `weighted.py` (dynamic default + fixed variants), `registry.py` (versioned registry, deterministic A/B, fallback), `__init__.py` (stable `calculate_breakdown` / `calculate_confidence` facades) |
| 5.2 Versioned models | `config/confidence.yaml` adds `models.default`, `models.fallback`, `models.variants.weighted-v2`, and `models.ab` (disabled by default, 50/50 weights, `max_delta` guard). `CONFIDENCE_WEIGHTS_V2` overrides variant weights; tuning scripts still mutate the live default weights. |
| 5.3 Explainability | `ConfidenceBreakdown.metadata` now includes `model`, `version`, `strategy`, selection/fallback reason, normalised weights, warning count and per-component `value`/`weight`/`contribution`. |
| 5.4 Telemetry | `app/services/telemetry.py`: thread-safe in-process counters and histograms with a Prometheus text exporter. `log_stage` records stage counts/durations/errors; `/api/scan` records scan counts by OCR engine, duration and confidence histograms; the confidence registry counts model selections and fallbacks. |

New endpoints (schema-hidden, no PHI in labels or payloads):
- `GET /api/metrics` — Prometheus text; `?format=json` for a snapshot.
- `GET /api/confidence/models` — registered models, default/fallback and A/B status.

Notes:
- `calculate_breakdown(ctx)` and `calculate_confidence(...)` are unchanged for
  all callers (`app/main.py`, `scripts/tune_pipeline.py`, tests).
- Compatibility choice: `ConfidenceBreakdown.components` stays `dict[str, float]`
  (as in Phases 1-4); the roadmap's `ComponentScore` objects are exposed as
  `breakdown.metadata["component_scores"]` so no existing consumer breaks.
- A/B bucketing is SHA-256 of the request correlation ID (falls back to raw
  text only when no correlation ID is bound), so the same scan selects the same
  variant. For API requests a correlation ID is always present.
- A failing variant or a deviation greater than `models.ab.max_delta` falls
  back to the default model and is logged/counted. A/B is **off** by default, so
  current scores and the calibration harness are unchanged.
- Metrics are in-process: they are reset on restart and are not a persistent
  analytics store. Labels contain only stage, engine, model and boolean flags —
  never raw text, filenames or patient data.

---

## 2. Necessity check

| Item | Necessary now? | Reason |
|------|----------------|--------|
| Confidence model interface + registry | Yes | Lets alternative scoring approaches be compared without rewriting `main.py`; Phase 5 deliverable. |
| Fixed `weighted-v2` variant | Yes, latent | Required for A/B experiments; disabled so production behaviour is unchanged. |
| Deterministic bucketing by correlation ID | Yes | Repeatable experiments and stable per-scan variant without storing assignments. |
| Delta guard + exception fallback | Yes | Prevents an unvalidated variant from silently changing scores. |
| `ComponentScore` contributions | Yes | Cheap, directly explains each score; needed for honest tuning reports. |
| Telemetry (counters/histograms + exporter) | Yes | Needed to observe stage latency/errors and model usage; no new dependency. |
| `/api/confidence/models` endpoint | Yes, small | Makes active model configuration inspectable during experiments. |
| Real-world A/B winner decision | No - defer | Requires labelled real prescriptions, which the no-PHI constraint forbids. |
| Prometheus server / persistent TSDB | No - defer | In-process exporter is enough for local experiments; add later if deployments need it. |
| Online learning / auto-tuning weights | No - defer | Unsafe without clinical validation; offline `tune_pipeline.py` remains authoritative. |

---

## 3. Model-optimization process (repeatable)

1. Keep `models.ab.enabled: false` for baseline runs; tune
   `confidence.yaml` weights or set `CONFIDENCE_WEIGHTS` (and
   `CONFIDENCE_WEIGHTS_V2` for the variant).
2. Re-run the full suite: `cd backend && python -m pytest -q`.
3. Re-measure on synthetic labels: `python scripts/tune_pipeline.py`; confirm
   current MAE/best-grid MAE did not regress.
4. Confirm OCR and matching baselines: `python scripts/benchmark_ocr.py` and
   the matching section of the tuning report.
5. For an A/B experiment: enable `models.ab`, send scans with stable
   `X-Correlation-ID` headers, then inspect `GET /api/metrics` for
   `mediscan_confidence_model_total` and `mediscan_confidence_fallback_total`.
   Keep `max_delta` enabled until a variant is validated on labelled data.

### Measured in this environment (2026-11-25)

Environment: Python 3.14.7, OpenCV 4.14.0.94, RapidFuzz 3.14.6,
Tesseract 5.5.3 (English). Synthetic fixtures only - no PHI.

| Check | Result |
|-------|--------|
| Tests | `python -m pytest -q`: 37 passed (6 new Phase 5 tests) |
| Default score stability | Registry default score is deterministic and matches the explainable component sum (within rounding) |
| A/B behaviour | Deterministic by correlation ID; both variants selected across 20 synthetic IDs; delta guard and exception fallback verified |
| Telemetry | Counter/histogram snapshot + Prometheus text verified; `/api/metrics` exposes scan/model metrics with no filename or raw text |
| Confidence calibration | current MAE 0.0385, best synthetic grid 0.0053 (unchanged) |
| Matching sweep | macro F1 1.000, top-1 1.000 on 18 synthetic spellings (unchanged) |
| OCR (3 clean synthetic images) | Tesseract CER/WER 0.0000 (unchanged) |
| End-to-end (typo fixture) | Tesseract selected, Paracetamol + Azithromycin matched, confidence 0.874 (unchanged) |

> These are synthetic-fixture measurements, **not** real-prescription accuracy
> claims. No A/B winner is claimed; A/B is disabled by default and only 50/50
> deterministic bucketing and safety fallbacks were tested.

---

## 4. Verification commands

```powershell
cd C:\Users\User\OneDrive\Desktop\github\MediScan-AI\backend
python -m pytest -q
python scripts/tune_pipeline.py
python scripts/benchmark_ocr.py
python scripts/scan_image.py tests/fixtures/ocr/typo_prescription.png --summary
```

After starting the API (`uvicorn app.main:app --reload --port 8000`):

```powershell
Invoke-RestMethod http://localhost:8000/api/metrics
Invoke-RestMethod http://localhost:8000/api/confidence/models
```
