# Model and Algorithm Notes

## Current system

MediScan-AI uses a deterministic, configurable baseline instead of a trained machine-learning model. This is intentional: the project brief calls for a reliable, measurable pipeline before ML/DL experiments.

```text
Prescription image
  -> OpenCV preprocessing (threshold / enhanced)
  -> OCR registry (Tesseract / EasyOCR / PaddleOCR / demo)
  -> raw text
  -> pluggable entity extraction (regex by default; spaCy/transformer optional)
  -> repository-backed fuzzy medicine matching
  -> versioned weighted confidence model with explainable breakdown
  -> user verification
  -> optional private persistence for authenticated users
```

No clinical accuracy claims are made. Any reported metric must come from an actual evaluation run on a suitable dataset.

## Image preprocessing

Implemented in `backend/app/services/preprocess.py`:

- resize to a configurable maximum dimension
- grayscale conversion
- denoising
- CLAHE contrast enhancement
- adaptive thresholding and morphological closing (`threshold` mode)
- grayscale CLAHE output for deep-learning OCR engines (`enhanced` mode)
- structured stage logging with correlation IDs

Skew correction and text-region cropping are planned but not implemented.

## OCR

Implemented in `backend/app/services/ocr/` with a registry and engine implementations:

- `tesseract`: `pytesseract` when available
- `easyocr` / `paddleocr`: optional heavy engines imported lazily when selected
- `demo`: synthetic fixture fallback so the app runs without any OCR engine installed
- `OCR_BACKEND=auto`: try engines in `backend/config/ocr.yaml` priority order, then fall back to demo

Engine priority, options and fallback live in YAML configuration rather than code.

## Entity extraction

Implemented in `backend/app/services/nlp/` with a pluggable pipeline:

- config-driven regex extraction is the default
- strengths such as `500 mg`
- frequencies such as `twice daily`, `every 6 hours`, `at bedtime`
- durations such as `for 7 days`
- forms such as `tablet`, `capsule`, `inhaler`
- post-processing deduplicates values, expands abbreviations and normalizes units
- optional spaCy and transformer extractors are lazy-loaded and never abort a scan if unavailable

Patterns and extractor order live in `backend/config/patterns.yaml` and `backend/config/nlp.yaml`.

## Medicine matching

Implemented in `backend/app/services/medicines/`:

- repository abstraction with JSON (default) and SQLite backends
- normalization: lowercase, remove punctuation, strip list markers
- RapidFuzz ratio scoring against names, generic names and aliases
- optional phonetic fallback with built-in Soundex or `jellyfish` Metaphone
- strength and form agreement bonuses
- per-entry and global score thresholds from `backend/config/matching.yaml`
- alternative suggestions for user review

## Confidence scoring

Implemented in `backend/app/services/confidence/` as versioned models behind a registry. The baseline blends:

- OCR engine reliability
- text length
- entity completeness
- average medicine match confidence
- penalties for processing warnings

`calculate_breakdown()` returns per-component contributions, the selected model and any fallback reason. This is a heuristic signal, not a calibrated probability. Weights and A/B settings live in `backend/config/confidence.yaml`.

## Evaluation plan

Implemented harnesses:

- `backend/scripts/evaluate.py`: CER/WER and medicine precision/recall/F1 on synthetic text samples
- `backend/scripts/benchmark_ocr.py`: CER/WER per available OCR engine on synthetic images
- `backend/scripts/tune_pipeline.py`: matching threshold sweep and confidence calibration

`GET /api/evaluation` exposes the same synthetic baseline as `scripts/evaluate.py`.

Field-level end-to-end exact match is planned once labeled end-to-end samples exist.

### Synthetic baseline run

Command:

```powershell
cd backend
py scripts/evaluate.py
```

Result from the five synthetic samples in `backend/data/eval_samples.json`:

```json
{
  "sample_count": 5,
  "cer": 0.0124,
  "wer": 0.0736,
  "medicine_precision": 1.0,
  "medicine_recall": 1.0,
  "medicine_f1": 1.0,
  "note": "Synthetic baseline evaluation only. Not a clinical accuracy claim."
}
```

These values describe spelling-corrupted synthetic text, not real prescriptions or clinical performance.

## ML/DL roadmap

Service optimization Phases 1–5 are implemented: protocols, structured logging, multi-backend OCR, repository-backed medicine matching, pluggable NLP, confidence model registry and telemetry. See `plan/services-optimization.md` and the phase status reports.

Planned modeling experiments, in order:

1. Compare Tesseract, EasyOCR and PaddleOCR on the same printed-prescription samples with `benchmark_ocr.py`.
2. Measure preprocessing impact with before/after CER and WER.
3. Compare fuzzy matching with a classifier trained on OCR spelling variants.
4. Evaluate a small NER model for medicine/strength/frequency extraction.
5. Only then explore CNN/Transformer experiments if a suitable labeled dataset exists.

Do not add a model file or accuracy claim until an experiment produces measured results.
