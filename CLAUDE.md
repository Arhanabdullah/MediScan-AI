# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MediScan-AI is an educational/research project for prescription digitization and medicine extraction using ML, DL, CV, OCR, and NLP. It processes prescription images through a pipeline: preprocessing → OCR → entity extraction → fuzzy medicine matching → confidence scoring → user verification.

**Tech Stack:**
- Backend: FastAPI (Python), OpenCV, Tesseract/EasyOCR/PaddleOCR, RapidFuzz, pytest
- Frontend: React 18 + Vite, ESLint
- Database: Medicine catalogue in JSON (default) or SQLite (opt-in); scan results in in-memory dicts; PostgreSQL planned

---

## Commands

### Backend
```bash
cd backend
pip install -r requirements.txt

# Run server (from backend/)
uvicorn app.main:app --reload --port 8000

# Run tests
pytest
pytest tests/test_api.py -v

# Scan your own image from the terminal (no server needed)
python scripts/scan_image.py "C:\path\to\image.png" --summary
python scripts/scan_image.py "C:\path\to\image.png" --text-only
python scripts/scan_image.py "C:\path\to\image.png" --output "$env:TEMP\scan.json"

# Model-optimization harnesses (measured on synthetic fixtures only)
python scripts/make_fixtures.py        # regenerate synthetic OCR images
python scripts/benchmark_ocr.py        # CER/WER per available OCR engine
python scripts/tune_pipeline.py        # fuzzy-match sweep + confidence MAE

# Medicine catalogue admin CLI (JSON source stays authoritative)
python -m scripts.manage_medicines validate
python -m scripts.manage_medicines stats
python -m scripts.manage_medicines migrate --dry-run
python -m scripts.manage_medicines migrate     # JSON -> SQLite
python -m scripts.manage_medicines import data/extra.csv
python -m scripts.manage_medicines export data/snapshot.json
```

Reports are written to `backend/reports/` (gitignored) unless `--no-save` is used.

### Frontend
```bash
cd frontend
npm install

# Dev server
npm run dev

# Build
npm run build

# Preview build
npm run preview

# Lint
npm run lint
```

### Environment Variables
- Backend: Copy `.env.example` to `.env` (OCR_BACKEND=auto|tesseract|easyocr|paddleocr|demo, TESSERACT_CMD, MEDICINE_REPO=json|sqlite, MEDICINE_DB_PATH, MEDICINE_SQLITE_PATH, CONFIDENCE_WEIGHTS, CONFIDENCE_WEIGHTS_V2, MEDISCAN_LOG_LEVEL, etc.). `app/config.py` loads `.env` automatically; real environment variables take precedence.
- Frontend: Copy `.env.example` to `.env` (VITE_API_URL)

---

## Architecture

### Backend Structure (`backend/`)
```
app/
  main.py          # FastAPI app, routes (/api/health, /api/scan, /api/scan/{id}, /api/verify, /api/metrics, /api/confidence/models)
  config.py        # Settings: env vars + YAML loaders
  schemas.py       # Pydantic models for requests/responses
  services/
    protocols.py   # Typed contracts (NamedTuple results + Protocol interfaces)
    logging.py     # JSON pipeline logs + correlation IDs + stage metrics
    telemetry.py   # In-process counters/histograms + Prometheus exporter
    preprocess.py  # OpenCV: resize, denoise, CLAHE; 'threshold' / 'enhanced' modes
    ocr/           # Registry + tesseract / easyocr / paddleocr / demo engines
    nlp/           # Pluggable extractor pipeline
      base.py              # Shared helpers + extractor contract
      regex_extractor.py   # Config-driven regex (default), custom entity types
      spacy_extractor.py   # Optional spaCy NER (lazy import)
      transformer_extractor.py # Optional HF token classification (lazy import)
      pipeline.py          # Fallback/merge chaining + extractor registry
      postprocess.py       # Dedupe, unit normalization, optional catalogue check
    medicines/     # Repository pattern + validation + fuzzy matching
      repository.py    # MedicineRepository protocol
      json_repo.py     # JSON backend (default, hot-reload)
      sql_repo.py      # SQLite backend (opt-in, PostgreSQL-ready interface)
      models.py        # Pydantic Medicine model
      validation.py    # Duplicate/missing-field checks
      matcher.py       # RapidFuzz + phonetic + strength/form-aware scoring
      loader.py        # JSON/CSV import + JSON export
      provider.py      # Backend selection + singleton access
    confidence/    # Versioned models + registry/A-B + explainable breakdown
      base.py              # Shared weighted formula + ComponentScore metadata
      weighted.py          # Fixed dynamic/default weighted models
      registry.py          # Model registry, deterministic A/B, safety fallback
      __init__.py          # calculate_breakdown / calculate_confidence facades
  data/medicines.json
config/
  patterns.yaml   # Regexes, labels, skip prefixes, entity confidence hints
  nlp.yaml        # Extractor order/strategy, custom entity keys, post-processing
  ocr.yaml        # Engine priority, options, preprocess mode, fallback
  confidence.yaml # Weights, penalties, per-engine OCR scores, model registry/A-B
  matching.yaml   # Fuzzy-match thresholds, phonetic and bonus weights
  medicines.yaml  # Repository backend, SQLite path, validation flags
  loader.py       # Cached, validated YAML loading
scripts/
  make_fixtures.py     # Synthetic prescription images (no PHI)
  benchmark_ocr.py     # CER/WER comparison per engine
  tune_pipeline.py     # Matching sweep + confidence calibration
  manage_medicines.py  # validate / stats / migrate / import / export CLI
  scan_image.py        # scan one local image via TestClient, no server needed
tests/
  test_api.py        # API integration tests (TestClient, demo OCR)
  test_services.py   # Unit tests for protocols, registry, config, metrics
  test_medicines.py  # Repository, validation, loader, matcher and CLI tests
  test_nlp.py        # Extractor pipeline, strategies and post-processing tests
  test_confidence_models.py # Model registry, A/B safety, telemetry + metrics endpoint tests
  fixtures/          # Synthetic demo text, OCR images, matching/confidence labels
```

### Frontend Structure (`frontend/src/`)
```
main.jsx         # Entry point
App.jsx          # State, handlers (scan, verify, update), layout
components/
  UploadPanel.jsx    # File input, camera, drag-drop, preview, analyze button
  ResultsPanel.jsx   # Raw text, entities, medicine cards, confidence badges, verify
  ConfidenceBadge.jsx# Colored confidence indicator
  Header.jsx         # App title
  Disclaimer.jsx     # Medical disclaimer
services/
  api.js        # fetch wrappers for /scan, /verify
styles.css      # Global styles
```

### Pipeline Flow
1. **Upload** → `POST /api/scan` with image file
2. **Preprocess** → resize, denoise, CLAHE; `threshold` mode for Tesseract, `enhanced` for DL engines
3. **OCR** → registry selects Tesseract / EasyOCR / PaddleOCR (or demo fallback); each stage is logged with a correlation ID
4. **Entity Extraction** → pluggable pipeline (`config/nlp.yaml`): regex by default, optional spaCy/transformer fallback; post-processing deduplicates and normalises units
5. **Medicine Matching** → repository-backed (JSON or SQLite), cached normalisation + RapidFuzz/phonetic scoring; tuning knobs in `config/matching.yaml`
6. **Confidence** → versioned model registry selects an explainable weighted model (`config/confidence.yaml`, A/B optional); breakdown + model choice logged with correlation ID, metrics recorded
7. **Response** → Structured JSON with scan_id, entities, medicines, confidence, disclaimer, `X-Correlation-ID` header
8. **Verify** → `POST /api/verify` with user-confirmed medicines → returns final result

---

## Key Implementation Details

### OCR Backend Selection
Set `OCR_BACKEND` in backend `.env`:
- `auto` (default): try engines in `config/ocr.yaml` priority order, then the fallback engine
- `tesseract`: require Tesseract (returns `tesseract-unavailable` if missing)
- `easyocr` / `paddleocr`: optional heavy engines, imported lazily only when selected
- `demo`: always use the synthetic fixture at `tests/fixtures/demo_prescription.txt`

Use `python scripts/benchmark_ocr.py --engines tesseract,demo,easyocr` to compare CER/WER once engines are installed.

### NLP Pipeline
- `extract_entities(text)` is the stable facade; it delegates to a cached `ExtractorPipeline`.
- `config/nlp.yaml` controls `extractors` order, `strategy` (`fallback` | `merge`), `entity_keys` (regex name → entity key), and post-processing flags/aliases.
- Regex is the default extractor. `spacy` and `transformer` are optional, lazily imported, and skipped when the library/model is absent; a failing extractor never aborts the scan.
- Add a custom entity type by adding a regex in `config/patterns.yaml`, an `entity_labels` entry, and an `entity_keys` entry in `config/nlp.yaml` — no code change needed.
- Custom extractors can be registered with `register_extractor(name, factory)` and injected with `set_pipeline(pipeline)`.
- Post-processing deduplicates values, expands abbreviations (`bd` → `twice daily`), canonicalises units (`500mg` → `500 mg`) and plural forms; `validate_medicine_names` is off by default because it would filter out OCR typos.

### Medicine Matching Logic
1. Normalize input (cached; lowercase, remove punctuation, bullets); the repository vocabulary is normalized once
2. Score against pre-normalised names / generics / aliases using RapidFuzz ratio
3. Optional phonetic fallback (Metaphone via `jellyfish`, otherwise built-in Soundex) blended with `phonetic_weight` (default 0.2)
4. Add `strength_bonus` (0.05) and `form_bonus` (0.02) when both agree with the DB entry
5. Confidence = `base_confidence` + `score_scale` × match_score, capped; `min_score` applies globally and per medicine
6. All thresholds live in `config/matching.yaml`; sweep them with `scripts/tune_pipeline.py`

### Medicine Repository
- `MedicineRepository` protocol with `all()`, `get(id)`, `count()`, `reload()`, `source`
- `JsonMedicineRepository` (default): validates on load and reads the file on every access when `hot_reload=true`
- `SqlMedicineRepository` (opt-in): stdlib `sqlite3`, parameterised queries, `replace_all()` for migration; same interface works for a future PostgreSQL backend
- Select with `MEDICINE_REPO=sqlite` + `MEDICINE_SQLITE_PATH`, or `repository.backend` in `config/medicines.yaml`
- Validation: required `id`/`name`, alias parsing (`|` or list), duplicate detection by name+strength+form, optional `require_generic_name`
- Both NLP known-name lookup and matching read the active repository, so switching backend needs no code change
- Generate/migrate the database with `python -m scripts.manage_medicines migrate` (the source JSON is never overwritten)

### Confidence Calculation
```
weights.ocr_engine       × OCR score (config/confidence.yaml, default tesseract=0.95, demo=0.55)
+ weights.text_length    × min(1, text_len / text_length_reference)
+ weights.entity_coverage × (non-empty entity categories / total categories)
+ weights.medicine_match  × avg(medicine.confidence)
- penalties.per_warning  × warning_count
```
`calculate_breakdown()` returns the individual components for logging/debugging,
plus `component_scores` (value, weight, contribution) and the selected model in `metadata`.
Weights can be overridden at runtime with the `CONFIDENCE_WEIGHTS` JSON env var
(`CONFIDENCE_WEIGHTS_V2` overrides the A/B variant).

### Confidence Models & Telemetry
- `app/services/confidence/` holds versioned models. The default `weighted-v1` reads settings on every call, so `scripts/tune_pipeline.py` still measures the live weights. `weighted-v2` is a fixed config variant (disabled until A/B is enabled).
- `config/confidence.yaml` defines `models.default`, `models.fallback`, `models.variants` and deterministic `models.ab` bucketing (SHA-256 of the request correlation ID, so the same scan always selects the same variant). A/B is **off** by default; current scores are unchanged.
- If a variant fails or deviates from the default by more than `models.ab.max_delta`, the registry falls back to the default and records the reason. Model choice and fallback are logged and counted.
- New models can be added with `register_model(model)` or by building/injecting a `ConfidenceRegistry` with `set_registry(registry)`.
- `app/services/telemetry.py` records stage durations/errors (`log_stage`), scan counts, OCR engine labels, confidence histograms and model selections. Labels never contain raw text, filenames or patient data.
- `GET /api/metrics` returns Prometheus text; `GET /api/metrics?format=json` returns a snapshot. `GET /api/confidence/models` lists registered models and A/B status. Metrics are in-process and lost on restart.

### In-Memory Storage
- `SCANS` dict: scan_id → ScanResponse (persists until server restart)
- `VERIFICATIONS` dict: scan_id → final verified result

### CORS
Configured for `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000`, `http://127.0.0.1:3000` via `CORS_ORIGINS` env var.

---

## Development Notes

### Current Stage
Based on the 10-week plan in README, the project is at **Level 6-7**: FastAPI backend + React frontend working end-to-end. Plan Phases 1-5 (foundation/abstraction, multi-backend OCR, medicine DB/matching, pluggable NLP, confidence models + telemetry) are implemented; see `plan/phase1-2-status.md`, `plan/phase3-status.md`, `plan/phase4-status.md` and `plan/phase5-status.md` for scope, necessity checks and measured optimization results.

### Adding New Medicines
Edit `backend/app/data/medicines.json` (the authoritative source) with entries following the schema:
```json
{
  "id": "unique-id",
  "name": "Brand Name",
  "generic_name": "Generic Name",
  "strength": "500 mg",
  "form": "tablet",
  "aliases": ["alias1", "alias2"],
  "min_score": 0.0
}
```
`min_score` is optional and raises the per-entry rejection threshold. For bulk edits, use a CSV with columns `id,name,generic_name,strength,form,aliases` (pipe-separated aliases) and `python -m scripts.manage_medicines import data/extra.csv`. Validate first with `python -m scripts.manage_medicines validate`; regenerate SQLite with `python -m scripts.manage_medicines migrate`.

### Testing with Real OCR
Tesseract 5.5.3 is installed on this machine at `C:\Program Files\Tesseract-OCR\tesseract.exe` (English data included). `backend/.env` sets `TESSERACT_CMD` to that path and `app/config.py` loads `.env` automatically at startup, so the default `OCR_BACKEND=auto` now selects Tesseract. To force it, set `OCR_BACKEND=tesseract`. For optional deep-learning engines, `pip install easyocr` and/or `pip install paddleocr` (lazy imports; the app runs without them). Then rerun `scripts/benchmark_ocr.py` to compare CER/WER on the synthetic fixtures.

### Frontend API URL
Set `VITE_API_URL` in frontend `.env` (default `/api` works with Vite proxy or same-origin).

---

## Important Constraints

- **Medical Disclaimer**: All responses include disclaimer; UI shows "Not for clinical use"
- **No PHI in repo**: Never commit real prescriptions or patient data
- **Demo mode**: Default OCR uses synthetic text for development without Tesseract
- **Scans in memory only**: scan/verification results are lost on restart (PostgreSQL planned for Level 8); the medicine catalogue persists in JSON/SQLite