# Model and Algorithm Notes

## Current system

MediScan-AI currently uses a deterministic, rule-based baseline instead of a trained machine-learning model. This is intentional: the project brief calls for a reliable baseline before ML/DL experiments.

```text
Prescription image
  -> OpenCV preprocessing
  -> Tesseract OCR (or demo fallback)
  -> raw text
  -> regex/rule-based entity extraction
  -> RapidFuzz medicine matching
  -> heuristic confidence score
  -> user verification
```

No clinical accuracy claims are made. Any reported metric must come from an actual evaluation run on a suitable dataset.

## Image preprocessing

Implemented in `backend/app/services/preprocess.py`:

- resize to a configurable maximum dimension
- grayscale conversion
- denoising
- CLAHE contrast enhancement
- adaptive thresholding
- morphological closing

Skew correction and text-region cropping are planned but not implemented.

## OCR

Implemented in `backend/app/services/ocr.py`:

- Tesseract via `pytesseract` when available
- `OCR_BACKEND=auto`: use Tesseract, fall back to synthetic demo text if unavailable
- `OCR_BACKEND=tesseract`: require Tesseract
- `OCR_BACKEND=demo`: always use synthetic demo text

EasyOCR and PaddleOCR are planned comparison candidates, not active dependencies.

## Entity extraction

Implemented in `backend/app/services/nlp.py`:

- medicine names from known vocabulary or line-level heuristics
- strengths such as `500 mg`
- frequencies such as `twice daily`, `every 6 hours`, `at bedtime`
- durations such as `for 7 days`
- forms such as `tablet`, `capsule`, `inhaler`

This stage is replaceable with spaCy NER or a transformer-based extractor without changing the API response shape.

## Medicine matching

Implemented in `backend/app/services/medicines.py`:

- normalization: lowercase, remove punctuation, strip list markers
- RapidFuzz ratio scoring against names, generic names, and aliases
- strength agreement bonus
- alternative suggestions for user review

## Confidence scoring

Implemented in `backend/app/services/confidence.py`. It blends:

- OCR engine reliability
- text length
- entity completeness
- average medicine match confidence
- penalties for processing warnings

This is a heuristic confidence signal, not a calibrated probability.

## Evaluation plan

The evaluation harness lives in `backend/scripts/evaluate.py` and uses synthetic samples from `backend/data/eval_samples.json`.

Implemented metrics:

- OCR: Character Error Rate (CER), Word Error Rate (WER)
- Medicine recognition: precision, recall, F1

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

Planned experiments, in order:

1. Compare Tesseract, EasyOCR, and PaddleOCR on the same printed-prescription samples.
2. Measure preprocessing impact with before/after CER and WER.
3. Compare fuzzy matching with a classifier trained on OCR spelling variants.
4. Evaluate a small NER model for medicine/strength/frequency extraction.
5. Only then explore CNN/Transformer experiments if a suitable labeled dataset exists.

Do not add a model file or accuracy claim until an experiment produces measured results.
