# Testing with your own datasets

This is a how-to for measuring the existing pipeline and the Phase M1 models on **your**
data. Nothing here copies your files into the repository.

## Rules before you start

- Keep real prescriptions and patient data **outside the repo** (for example
  `C:\Users\User\MyMedData\`). Never commit them; no PHI in git.
- Use `--no-save` where available, or write reports into gitignored
  `backend/reports/`. The training scripts only write to paths you pass explicitly.
- Always keep a **held-out test split** that is not used for training or tuning.
- Numbers measured here are results on your dataset. They are not clinical accuracy claims.

All commands below are run from `backend/`.

## 1. Images + exact ground-truth text → OCR CER/WER

`scripts/benchmark_ocr.py` already accepts `--data`. Create a JSON file next to your images:

```json
{
  "samples": [
    { "image": "rx_001.png", "text": "Paracetamol 500 mg twice daily" },
    { "image": "rx_002.png", "text": "Amoxicillin 500 mg capsule three times daily" }
  ]
}
```

`text` must be the exact transcription of the image. Paths in `image` are relative to the
JSON file's directory.

```powershell
python scripts/benchmark_ocr.py --data "C:\Users\User\MyMedData\ocr_labels.json" --engines tesseract --no-save
```

Output: mean CER and WER per engine, lower is better. Add `easyocr` or `paddleocr` to
`--engines` if installed to compare engines.

## 2. OCR text + expected medicines → pipeline P/R/F1

`scripts/evaluate.py` accepts `--data`. Use a JSON list:

```json
[
  {
    "ocr_text": "Paracetmol 500 mg twice daily",
    "expected_text": "Paracetamol 500 mg twice daily",
    "expected_medicines": ["Paracetamol"]
  }
]
```

- `ocr_text`: the text you want the pipeline to process (can contain OCR errors).
- `expected_text`: clean reference used for CER/WER.
- `expected_medicines`: canonical medicine names from your catalogue.

```powershell
python scripts/evaluate.py --data "C:\Users\User\MyMedData\eval_samples.json" --output reports\my_eval.json
```

Output: `cer`, `wer`, `medicine_precision`, `medicine_recall`, `medicine_f1`. For custom
files the script sets a `sample_source` field and a custom-dataset note; the bundled
synthetic default behaves exactly as before.

The same format is accepted by `evaluate_samples(samples)` in code. `GET /api/evaluation`
still uses the bundled synthetic file only.

## 3. Misspelling → canonical medicine → retrain the corrector

Training data is a JSON list (or `{"samples": [...]}`) with a `split` per item:

```json
{
  "samples": [
    { "text": "amoxcilin", "label": "Amoxicillin", "source_name": "Amoxicillin", "operation": "substitute", "split": "train" },
    { "text": "paracetmol", "label": "Paracetamol", "source_name": "Paracetamol", "operation": "delete", "split": "validation" },
    { "text": "omeprazol", "label": "Omeprazole", "source_name": "Omeprazole", "operation": "delete", "split": "test" }
  ]
}
```

`label` must match a canonical `name` in `backend/app/data/medicines.json` (or your
configured repository). All three splits must be non-empty; the test split is never used
for fitting.

```powershell
python scripts/train_medicine_corrector.py --data "C:\Users\User\MyMedData\typos.json" --artifact "C:\Users\User\MyMedData\corrector.joblib" --metadata "C:\Users\User\MyMedData\corrector_metrics.json"
```

The script prints validation/test/train accuracy, macro precision, recall and F1 and writes
the artifact plus a metrics card to the paths you gave. Point
`model.medicine_corrector.artifact` / `.metadata` in `backend/config/model.yaml` at those
files and set `enabled: true` to use them at runtime.

## 4. NER-labelled text → retrain the extractor

Entity offsets are **character positions** in `text`, inclusive start / exclusive end:

```json
{
  "samples": [
    {
      "text": "Take 1 tablet Paracetamol 500 mg twice daily",
      "entities": [
        [18, 30, "MEDICINE"],
        [31, 37, "STRENGTH"],
        [38, 52, "FREQUENCY"]
      ],
      "split": "train"
    }
  ]
}
```

Supported labels are `MEDICINE`, `STRENGTH`, `FREQUENCY`, `DURATION`, `FORM`. Include
`train`, `validation` and `test` splits.

```powershell
python scripts/train_ner.py --data "C:\Users\User\MyMedData\ner.json" --model-output "C:\Users\User\MyMedData\prescription_ner" --metadata "C:\Users\User\MyMedData\ner_metrics.json"
```

The script writes a spaCy model directory and a metrics card with exact-span
precision/recall/F1 per split. Point `model.ner.model_path` / `.metadata` at those files
and set `enabled: true`. When enabled, the trained extractor is merged with regex output;
missing model files or spaCy cause a safe fallback.

## After training

1. Edit `backend/config/model.yaml` flags/paths for the models you want active.
2. Restart the FastAPI server (`uvicorn app.main:app --reload --port 8000` from `backend/`).
3. Check `GET /api/model-info`: `trained_model` should be `true` and `trained_models` shows
   versions, status and held-out metrics. The React model-status panel shows the same data.
4. Re-run `python scripts/evaluate.py --data ...` to measure the end-to-end pipeline with
   the models enabled, and compare against the disabled baseline.

If you also have label files for matching thresholds or confidence targets, see
`scripts/tune_pipeline.py --matching-fixtures` and `--confidence-fixtures`. Its fixtures use
the shapes in `backend/tests/fixtures/matching.json` and `confidence.json`; those searches
are diagnostics on annotated data, not automatic config updates.

## Sanity check after any change

```powershell
python -m pytest -q
```
