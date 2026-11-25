# MediScan-AI Agent Notes

## Purpose

This file is the working plan and progress tracker for coding agents. The authoritative project brief is `Readme.md`.

## Product boundary

MediScan-AI digitizes prescription images and extracts medicine-related information. It does not diagnose, prescribe, recommend doses, or replace professional medical advice. Never add features that make clinical decisions.

## Current progress

Completed:

- Level 1: OCR baseline with Tesseract and a demo fallback.
- Level 2: OpenCV preprocessing: grayscale, denoising, CLAHE, thresholding, morphology.
- Level 3: RapidFuzz medicine matching against a local vocabulary.
- Level 4: evaluation harness with CER/WER and medicine precision/recall/F1 on synthetic text samples. No trained ML/DL model is active; see `MODEL.md`.
- Level 5: rule-based extraction of medicine, strength, frequency, duration, and form.
- Level 6: FastAPI `/api/scan`, `/api/verify`, `/api/health`, `/api/scan/{id}`, auth, history, result detail, delete, model info, and evaluation endpoints.
- Level 7: React upload/camera, preview, results, editable fields, confidence display, auth, and history.
- Level 8: SQLAlchemy persistence, SQLite default, PostgreSQL-compatible `DATABASE_URL`, bcrypt passwords, JWT auth, and private per-user image storage.
- Level 9: user confirmation workflow in the frontend and backend.
- Level 10: Docker Compose, Dockerfiles, nginx proxy, GitHub Actions CI, and expanded tests.

Still out of scope:

- A trained ML/DL model and a real labeled prescription dataset.
- Handwritten prescription recognition.
- Clinical validation or accuracy claims beyond the synthetic baseline evaluation.

## Repository map

- `Readme.md`: project brief, 10-level plan, API concept, database concept, evaluation goals.
- `CLAUDE.md`: agent progress tracker.
- `MODEL.md`: algorithm notes, evaluation method, and ML/DL roadmap.
- `backend/app/main.py`: FastAPI routes.
- `backend/app/auth.py`: JWT dependency and optional/required authentication.
- `backend/app/db.py` and `backend/app/models.py`: SQLAlchemy engine, schema, and sessions.
- `backend/app/services/`: preprocessing, OCR, NLP, fuzzy matching, confidence, security, and evaluation.
- `backend/app/data/medicines.json`: starter medicine vocabulary.
- `backend/data/eval_samples.json`: synthetic evaluation samples.
- `backend/scripts/evaluate.py`: standalone evaluation harness.
- `backend/tests/`: API and evaluation tests.
- `frontend/src/`: React application.
- `frontend/src/services/api.js`: API client with token handling.
- `docker-compose.yml`: backend, frontend, and PostgreSQL services.
- `.github/workflows/ci.yml`: backend tests/evaluation and frontend lint/build.

## Commands

Backend:

```powershell
cd backend
py -m pip install -r requirements.txt
py -m pytest
py scripts/evaluate.py
py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run lint
npm run build
npm run dev
```

Docker:

```powershell
docker compose up --build
```

## Completed work checklist

- [x] Add model documentation and evaluation harness with CER/WER and medicine precision/recall/F1.
- [x] Add SQLAlchemy persistence with SQLite default and PostgreSQL-compatible `DATABASE_URL`.
- [x] Add registration, login, JWT auth, private image storage, history, result detail, and delete endpoints.
- [x] Wire auth and history into React.
- [x] Add Docker/deployment files and CI checks.
- [x] Expand tests for auth, history, model info, and evaluation metrics.
- [x] Update this file and `Readme.md` with final status.

## Rules for future changes

- Do not commit real prescriptions or sensitive data.
- Keep uploaded images private; do not expose them as public static files.
- Do not claim accuracy numbers unless produced by `backend/scripts/evaluate.py` or a real evaluation run.
- Keep the existing demo OCR fallback so the app runs without Tesseract installed.
- Keep `main` stable; use focused commits.
