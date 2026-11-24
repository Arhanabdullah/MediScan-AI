# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MediScan-AI is an educational/research project for prescription digitization and medicine extraction using ML, DL, CV, OCR, and NLP. It processes prescription images through a pipeline: preprocessing → OCR → entity extraction → fuzzy medicine matching → confidence scoring → user verification.

**Tech Stack:**
- Backend: FastAPI (Python), OpenCV, Tesseract/EasyOCR/PaddleOCR, RapidFuzz, pytest
- Frontend: React 18 + Vite, ESLint
- Database: PostgreSQL (planned), currently in-memory dicts

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
```

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
- Backend: Copy `.env.example` to `.env` (OCR_BACKEND=auto|tesseract|demo, TESSERACT_CMD, etc.)
- Frontend: Copy `.env.example` to `.env` (VITE_API_URL)

---

## Architecture

### Backend Structure (`backend/app/`)
```
main.py          # FastAPI app, routes (/api/health, /api/scan, /api/scan/{id}, /api/verify)
config.py        # Settings via env vars
schemas.py       # Pydantic models for requests/responses
services/
  preprocess.py  # OpenCV: resize, grayscale, denoise, CLAHE, adaptive threshold, morphology
  ocr.py         # Tesseract with demo fallback (settings.demo_text)
  nlp.py         # Regex-based entity extraction (medicine, strength, frequency, duration, form)
  medicines.py   # JSON medicine DB + RapidFuzz matching + normalization
  confidence.py  # Weighted scoring: OCR(45%) + text_len(15%) + entities(20%) + medicines(20%)
data/
  medicines.json # 11 medicines with id, name, generic_name, strength, form, aliases
tests/
  test_api.py    # Integration tests using TestClient, demo OCR mode
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
2. **Preprocess** → OpenCV resize, denoise, CLAHE, threshold
3. **OCR** → Tesseract (or demo fallback text)
4. **Entity Extraction** → Regex patterns for medicine, strength, frequency, duration, form
5. **Medicine Matching** → Normalize + RapidFuzz against `medicines.json` + strength bonus
6. **Confidence** → Weighted score with warning penalty
7. **Response** → Structured JSON with scan_id, entities, medicines, confidence, disclaimer
8. **Verify** → `POST /api/verify` with user-confirmed medicines → returns final result

---

## Key Implementation Details

### OCR Backend Selection
Set `OCR_BACKEND` in backend `.env`:
- `auto` (default): Try Tesseract, fallback to demo
- `tesseract`: Require Tesseract (fails if unavailable)
- `demo`: Always use synthetic demo text

### Medicine Matching Logic
1. Normalize input (lowercase, remove punctuation, bullets)
2. Score against each medicine's name, generic_name, aliases using RapidFuzz ratio
3. Add 0.05 bonus if extracted strength matches medicine's strength
4. Confidence = 0.45 + 0.55 × match_score (capped at 0.99)

### Confidence Calculation
```
0.45 × OCR_SCORE (tesseract=0.95, demo=0.55, error=0.2-0.25)
+ 0.15 × min(1, text_len/300)
+ 0.20 × (non-empty entity categories / total categories)
+ 0.20 × avg(medicine.confidence)
- 0.05 × warning_count
```

### In-Memory Storage
- `SCANS` dict: scan_id → ScanResponse (persists until server restart)
- `VERIFICATIONS` dict: scan_id → final verified result

### CORS
Configured for `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000`, `http://127.0.0.1:3000` via `CORS_ORIGINS` env var.

---

## Development Notes

### Current Stage
Based on the 10-week plan in README, the project is at **Level 6-7**: FastAPI backend + React frontend working end-to-end with demo OCR. Tesseract integration is present but optional.

### Adding New Medicines
Edit `backend/app/data/medicines.json` with new entries following the schema:
```json
{
  "id": "unique-id",
  "name": "Brand Name",
  "generic_name": "Generic Name",
  "strength": "500 mg",
  "form": "tablet",
  "aliases": ["alias1", "alias2"]
}
```

### Testing with Real OCR
Install Tesseract system-wide, then set `OCR_BACKEND=tesseract` in backend `.env`. On Windows, also set `TESSERACT_CMD` to the executable path.

### Frontend API URL
Set `VITE_API_URL` in frontend `.env` (default `/api` works with Vite proxy or same-origin).

---

## Important Constraints

- **Medical Disclaimer**: All responses include disclaimer; UI shows "Not for clinical use"
- **No PHI in repo**: Never commit real prescriptions or patient data
- **Demo mode**: Default OCR uses synthetic text for development without Tesseract
- **In-memory only**: Data lost on restart; PostgreSQL planned for Level 8