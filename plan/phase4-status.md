# Phase 4 Implementation Status & Model-Optimization Process

Phase 4 of `services-optimization.md` (NLP Pipeline Modularization) is
implemented. This document records what was built, the necessity check, and
how it was verified. It complements `CLAUDE.md`, `plan/phase1-2-status.md` and
`plan/phase3-status.md`.

---

## 1. What was implemented

| Plan task | Implementation |
|-----------|----------------|
| 4.1 Extractor pipeline | `backend/app/services/nlp/` package: `base.py`, `regex_extractor.py`, `spacy_extractor.py`, `transformer_extractor.py`, `pipeline.py`, `postprocess.py`, `__init__.py` (stable `extract_entities` facade) |
| 4.2 Config-driven regex | `config/patterns.yaml` (regexes, labels, hints) + `config/nlp.yaml` (`extractors` order, `strategy`, `entity_keys`). Custom entity types require only YAML entries. |
| 4.3 Post-processing | `postprocess.py`: within-category deduplication, strength unit normalization (`500mg` → `500 mg`, `µg` → `mcg`), frequency abbreviation expansion (`bd`, `tds`, `qid`, `od`, `sos`), plural form canonicalisation, optional medicine-name validation against the active repository |
| 4.4 spaCy / transformer | Optional extractors with lazy imports and label maps from `config/nlp.yaml`; skipped when the library or configured model is unavailable. Fallback chain: first available extractor with entities wins; `merge` strategy also supported. |

Notes:
- `config/patterns.yaml` is the plan's `nlp_patterns.yaml`; keeping the existing
  filename avoids breaking the Phase 1 loader and `settings.patterns`.
- `extract_entities(text)` and all HTTP response shapes are unchanged.
- Unavailable or failing extractors are logged and skipped, so an optional
  dependency can never abort a scan.
- Custom extractors can be added at runtime with `register_extractor(name, factory)`
  and injected with `set_pipeline(pipeline)`.

---

## 2. Necessity check

| Item | Necessary now? | Reason |
|------|----------------|--------|
| Extractor abstraction + pipeline | Yes | Enables swapping regex for NER without touching `main.py`; Phase 4 deliverable. |
| Config-driven custom entity types | Yes | New prescription fields can be added without code edits. |
| Post-processing (dedupe/units) | Yes | Cheap, deterministic improvement to downstream matching and displayed results. |
| Optional spaCy wrapper | Yes, latent | Required for the README's NER experiments; imports stay lazy so the app still boots without it. |
| Optional transformer wrapper | Yes, latent | Same reasoning; disabled until a real model is configured. |
| `validate_medicine_names` | No - off by default | Filtering unknown names would discard OCR typos that fuzzy matching currently recovers; enable only when precision matters more than recall. |
| Training a custom NER model | No - defer | Needs labelled real prescription data; not available under the no-PHI constraint. |
| Multi-model A/B voting | No - defer | Phase 5/6 territory; no measured benefit yet. |

---

## 3. Model-optimization process (repeatable)

1. Change extractor order, strategy or post-processing in `backend/config/nlp.yaml`.
2. Add/extend patterns in `backend/config/patterns.yaml`; map new regexes to
   entity keys under `nlp.entity_keys`.
3. Re-run the full suite: `cd backend && python -m pytest -q`.
4. Re-measure downstream effects: `python scripts/tune_pipeline.py` and
   `python scripts/benchmark_ocr.py`.
5. Check one image end-to-end:
   `python scripts/scan_image.py tests/fixtures/ocr/demo_prescription.png --summary`.

### Measured in this environment (2026-11-25)

Environment: Python 3.14.7, OpenCV 4.14.0.94, RapidFuzz 3.14.6,
Tesseract 5.5.3 (English). Synthetic fixtures only - no PHI.

| Check | Result |
|-------|--------|
| Tests | `python -m pytest -q`: 31 passed (9 new NLP tests) |
| Regex config extraction | Custom `allergy` entity extracted from a synthetic line |
| Pipeline strategies | `fallback` selects the first non-empty extractor; `merge` combines + deduplicates; unavailable/failing extractors skipped |
| Post-processing | `500mg` → `500 mg`, `bd` → `twice daily`, duplicate values removed, plural forms canonicalised |
| End-to-end (typo fixture) | Tesseract selected, medicines `Paracetamol` and `Azithromycin` matched, confidence 0.874 |
| Matching sweep | macro F1 1.000, top-1 1.000 on 18 synthetic spellings (unchanged) |
| Confidence calibration | current MAE 0.0385, best synthetic grid 0.0053 (unchanged) |
| OCR (3 clean synthetic images) | Tesseract CER/WER 0.0000 (unchanged) |

> These are synthetic-fixture measurements, **not** real-prescription accuracy
> claims. spaCy and transformers are not installed, so those extractors were
> verified only through their availability/skip behaviour.

---

## 4. Verification commands

```powershell
cd C:\Users\User\OneDrive\Desktop\github\MediScan-AI\backend
python -m pytest -q
python scripts/scan_image.py tests/fixtures/ocr/demo_prescription.png --summary
python scripts/tune_pipeline.py
```
