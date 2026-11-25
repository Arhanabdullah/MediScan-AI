# Phase 3 Implementation Status & Model-Optimization Process

This document records Phase 3 of `services-optimization.md` (Medicine DB &
Matching Enhancement), what was actually necessary at the current project
stage, and how the changes were verified. It complements `CLAUDE.md` and
`plan/phase1-2-status.md`.

---

## 1. What was implemented

| Plan task | Implementation |
|-----------|----------------|
| 3.1 Repository pattern | `backend/app/services/medicines/` package: `repository.py` (protocol), `json_repo.py`, `sql_repo.py`, `models.py`, `matcher.py`, `loader.py`, `provider.py`, `validation.py` |
| 3.2 Enhanced matching | Configurable phonetic fallback (Metaphone via optional `jellyfish`, otherwise built-in Soundex), `form_bonus`, global + per-medicine `min_score`, normalized vocabulary index, cached scores |
| 3.3 Validation & migration | Pydantic validation, duplicate detection by name+strength+form, optional `require_generic_name`, JSON→SQLite migration via CLI |
| 3.4 Admin CLI | `backend/scripts/manage_medicines.py`: `validate`, `stats`, `migrate`, `import` (JSON/CSV), `export` |

Additional decoupling:
- `nlp.py` now reads the active repository instead of a module-level
  `MEDICINES` snapshot, so hot-reload and the SQLite backend apply everywhere.
- `config/medicines.yaml` + `MEDICINE_REPO` / `MEDICINE_SQLITE_PATH` /
  `MEDICINE_DB_PATH` env overrides select the backend without code changes.
- `backend/.gitignore` ignores generated `data/*.db` and `reports/`.

The API contract is unchanged: `GET /api/health` reports the active
repository's medicine count, and `POST /api/scan` still returns the same JSON
shape with the medical disclaimer.

---

## 2. Necessity check

| Item | Necessary now? | Reason |
|------|----------------|--------|
| Repository interface + JSON default | Yes | Removes hardcoded coupling, keeps existing deployments working; foundation for PostgreSQL. |
| SQLite implementation | Yes (opt-in) | Phase 3 deliverable; zero-setup SQL backend for a growing catalogue. JSON remains authoritative. |
| Validation on load | Yes | Prevents silent bad data (missing ids, duplicates) from reaching the matcher. |
| Migration + import/export CLI | Yes | Required to populate/maintain SQLite without hand-editing SQL. |
| Phonetic fallback | Yes, opt-in | Recovers OCR spelling errors; blended at weight 0.2, measured on synthetic typos. |
| Form-aware bonus | Yes | Cheap discrimination between same-name products; config-driven. |
| Per-entry `min_score` | Yes | Lets curators suppress ambiguous catalogue entries without code changes. |
| Embedding-based similarity | No - defer | Phase 5/6 territory; needs real labelled data and a model artifact. |
| PostgreSQL backend | No - defer | README places DB at week 8; the `MedicineRepository` protocol makes it a drop-in addition later. |
| Async/HTTP medicine service | No - defer | No demonstrated bottleneck; the catalogue is small and local. |

---

## 3. Model-optimization process (repeatable)

1. Validate the authoritative catalogue:
   `cd backend && python -m scripts.manage_medicines validate`
2. Refresh the SQL copy (only when using SQLite):
   `python -m scripts.manage_medicines migrate`
3. Select the backend: keep JSON as default, or set
   `MEDICINE_REPO=sqlite` and `MEDICINE_SQLITE_PATH=data/medicines.db`.
4. Re-measure matching after any catalogue/config change:
   `python scripts/tune_pipeline.py` (top-1 accuracy, macro P/R/F1, MAE).
5. Re-measure OCR if preprocessing or engine selection changed:
   `python scripts/benchmark_ocr.py`.
6. Run the full suite: `python -m pytest -q`.

### Measured in this environment (2026-11-25)

Environment: Python 3.14.7, OpenCV 4.14.0.94, RapidFuzz 3.14.6,
Tesseract 5.5.3 (English). Synthetic fixtures only - no PHI.

| Check | Result |
|-------|--------|
| Matching (18 synthetic spellings) | baseline `strength_bonus=0.05`: macro F1 1.000, top-1 1.000; sweep best 0.0 (tie) |
| Confidence (4 synthetic cases) | current MAE 0.0385; best synthetic grid 0.0053 (not deployable without real annotations) |
| OCR (3 clean synthetic images, Tesseract) | mean CER 0.0000, WER 0.0000 - machine-rendered fixtures, not a real-prescription accuracy claim |
| Migration | 12 JSON records → 12 SQLite records; `stats` reports 12 |
| Tests | `python -m pytest -q`: 22 passed |

Raw reports: `backend/reports/ocr_benchmark.json`,
`backend/reports/tuning_report.json` (generated, gitignored).

> The perfect OCR/matching scores reflect clean synthetic data. Per `Readme.md`,
> **no accuracy claim is made for real prescriptions**. Re-run the harnesses
> after adding representative labelled data.

---

## 4. Verification commands

```powershell
cd C:\Users\User\OneDrive\Desktop\github\MediScan-AI\backend
python -m scripts.manage_medicines validate
python -m scripts.manage_medicines stats
python -m scripts.manage_medicines migrate --dry-run
python -m pytest -q
```

To exercise SQLite end-to-end:
```powershell
python -m scripts.manage_medicines migrate
$env:MEDICINE_REPO = "sqlite"
$env:MEDICINE_SQLITE_PATH = "data/medicines.db"
python -c "from fastapi.testclient import TestClient; from app.main import app; print(TestClient(app).get('/api/health').json())"
```
