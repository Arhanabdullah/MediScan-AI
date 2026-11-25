# Backend Services Optimization Plan

## Current State Analysis

### Services Inventory (`backend/app/services/`)
| Service | Lines | Responsibility | Dependencies |
|---------|-------|----------------|--------------|
| `preprocess.py` | 47 | OpenCV image preprocessing pipeline | cv2, numpy, config |
| `ocr.py` | 44 | Tesseract OCR with demo fallback | cv2, pytesseract, config |
| `nlp.py` | 114 | Regex-based entity extraction | re, medicines (for known names) |
| `medicines.py` | 64 | Medicine DB loading + RapidFuzz matching | json, rapidfuzz, config |
| `confidence.py` | 35 | Weighted confidence scoring | — |

### Identified Issues
1. **Tight coupling**: `nlp.py` imports `MEDICINES` from `medicines.py` (circular risk if expanded)
2. **Hardcoded patterns**: Regex patterns in `nlp.py` are not configurable
3. **Single OCR backend**: Only Tesseract supported; EasyOCR/PaddleOCR planned in README
4. **In-memory medicine DB**: Loaded once at import; no hot-reload, no validation
5. **No abstraction layers**: Direct imports make testing and swapping implementations hard
6. **Limited error handling**: Exceptions bubble up as generic HTTP 500s
7. **No logging/observability**: Hard to debug pipeline stages in production
8. **Confidence weights hardcoded**: Not configurable via env/config
9. **No type hints for return tuples**: `(np.ndarray, dict, list[str])` etc.
10. **Demo text in config**: Mixes configuration with test data

---

## Phase 1: Foundation & Abstraction (Week 1-2)

### Goals
- Introduce interfaces/protocols for each service
- Decouple services from concrete implementations
- Add structured logging
- Extract configuration from code

### Tasks

#### 1.1 Create Service Protocols (`services/protocols.py`)
```python
# Define protocols for each pipeline stage
class Preprocessor(Protocol):
    def __call__(self, data: bytes) -> PreprocessResult: ...

class OCREngine(Protocol):
    def extract(self, image: np.ndarray) -> OCRResult: ...

class EntityExtractor(Protocol):
    def extract(self, text: str) -> EntityResult: ...

class MedicineMatcher(Protocol):
    def match(self, text: str, strength: str | None) -> MedicineMatchResult: ...

class ConfidenceCalculator(Protocol):
    def calculate(self, ctx: ConfidenceContext) -> float: ...
```

#### 1.2 Add Structured Logging (`services/logging.py`)
- Use `structlog` or stdlib `logging` with JSON output
- Log each pipeline stage: input hash, timing, warnings, output summary
- Correlation ID for request tracing

#### 1.3 Extract Patterns to Config (`config/patterns.yaml`)
```yaml
regex:
  strength: "..."
  frequency: "..."
  duration: "..."
  form: "..."
skip_prefixes: [...]
entity_labels: {...}
```

#### 1.4 Refactor Config (`config.py`)
- Move `demo_text` to `tests/fixtures/demo_prescription.txt`
- Add `confidence_weights` dict from env
- Add `ocr_engines` config for multi-backend

#### 1.5 Add Type Stubs
- Replace tuple returns with `NamedTuple`/`TypedDict`/`Pydantic` models
- Add `from __future__ import annotations`

### Deliverables
- `services/protocols.py` with all protocols
- `services/logging.py` with pipeline logger
- `config/patterns.yaml` + loader
- Updated `config.py` with confidence weights
- Type hints on all public functions

---

## Phase 2: OCR Multi-Backend Support (Week 2-3)

### Goals
- Implement EasyOCR and PaddleOCR as alternatives
- Add engine selection/fallback strategy
- Benchmark comparison harness

### Tasks

#### 2.1 Create OCR Engine Implementations
```
services/ocr/
  __init__.py          # Engine registry + factory
  base.py              # Abstract base class
  tesseract.py         # Current Tesseract logic
  easyocr.py           # EasyOCR wrapper
  paddleocr.py         # PaddleOCR wrapper
  demo.py              # Demo fallback
```

#### 2.2 Engine Registry Pattern
```python
class OCERegistry:
    engines: dict[str, OCREngine] = {}
    
    @classmethod
    def register(cls, name: str, engine: OCREngine) -> None: ...
    
    @classmethod
    def get(cls, name: str) -> OCREngine: ...
    
    @classmethod
    def best_available(cls, preference: list[str]) -> OCREngine: ...
```

#### 2.3 Config-Driven Selection
```yaml
# config/ocr.yaml
engines:
  tesseract:
    enabled: true
    priority: 1
    config: "--psm 6"
  easyocr:
    enabled: false
    priority: 2
    languages: ["en"]
  paddleocr:
    enabled: false
    priority: 3
    use_gpu: false
fallback: "demo"
```

#### 2.4 Benchmark Script (`scripts/benchmark_ocr.py`)
- Test on sample images
- Output CER/WER per engine
- Generate comparison report

### Deliverables
- `services/ocr/` package with 4 engines
- `config/ocr.yaml` + loader in `config.py`
- Benchmark script + sample images in `tests/fixtures/ocr/`

---

## Phase 3: Medicine DB & Matching Enhancement (Week 3-4)

### Goals
- Move medicine DB to SQLite/PostgreSQL-ready abstraction
- Add validation, indexing, hot-reload
- Improve matching with ML-ready features

### Tasks

#### 3.1 Medicine Repository Pattern
```
services/medicines/
  __init__.py
  repository.py       # Abstract repository interface
  json_repo.py        # Current JSON implementation
  sql_repo.py         # SQLite/PostgreSQL implementation (stub)
  models.py           # Pydantic/SQLModel definitions
  matcher.py          # Matching logic (extracted from medicines.py)
  loader.py           # CSV/JSON import utilities
```

#### 3.2 Enhanced Matching
- Add phonetic matching (Metaphone/Double Metaphone)
- Add embedding-based similarity (optional, for Phase 5)
- Configurable match thresholds per medicine
- Strength/form-aware matching

#### 3.3 Validation & Migration
- JSON Schema validation on load
- Duplicate detection (by name+strength+form)
- Migration script: JSON → SQLite

#### 3.4 Admin CLI (`scripts/manage_medicines.py`)
```bash
python -m scripts.manage_medicines import data/medicines.json
python -m scripts.manage_medicines validate
python -m scripts.manage_medicines stats
```

### Deliverables
- `services/medicines/` package with repository pattern
- SQLite schema + migration script
- Validation on startup
- Admin CLI for DB management

---

## Phase 4: NLP Pipeline Modularization (Week 4-5)

### Goals
- Make entity extraction pluggable and extensible
- Add spaCy/transformer NER as alternative
- Separate pattern config from code

### Tasks

#### 4.1 Extractor Pipeline
```
services/nlp/
  __init__.py
  base.py              # EntityExtractor protocol
  regex_extractor.py   # Current regex logic (config-driven)
  spacy_extractor.py   # spaCy NER wrapper (optional)
  transformer_extractor.py  # HF transformer wrapper (optional)
  pipeline.py          # Chaining multiple extractors
  patterns.yaml        # All regex patterns + labels
  postprocess.py       # Deduplication, normalization, validation
```

#### 4.2 Config-Driven Regex Extractor
- Load patterns from `config/nlp_patterns.yaml`
- Support pattern priority/ordering
- Add custom entity types via config

#### 4.3 Post-Processing
- Deduplicate overlapping entities
- Normalize strength/frequency/forms to standard units
- Validate medicine names against DB (optional)

#### 4.4 spaCy Integration (Optional)
- Add `en_core_web_sm` model
- Train custom NER for prescription entities
- Fallback chain: transformer → spacy → regex

### Deliverables
- `services/nlp/` package with pluggable extractors
- `config/nlp_patterns.yaml`
- Post-processing pipeline

---

## Phase 5: Confidence & Observability (Week 5-6)

### Goals
- Make confidence calculation explainable and tunable
- Add comprehensive pipeline telemetry
- Enable A/B testing of confidence models

### Tasks

#### 5.1 Explainable Confidence
```python
@dataclass
class ConfidenceBreakdown:
    overall: float
    components: dict[str, ComponentScore]
    # e.g., {"ocr": 0.95, "text_length": 0.8, "entities": 0.75, "medicines": 0.82}
    warnings_penalty: float
    metadata: dict[str, Any]
```

#### 5.2 Configurable Weights
```yaml
# config/confidence.yaml
weights:
  ocr_engine: 0.45
  text_length: 0.15
  entity_coverage: 0.20
  medicine_match: 0.20
penalties:
  per_warning: 0.05
  empty_ocr: 0.5
  no_medicines: 0.3
ocr_scores:
  tesseract: 0.95
  easyocr: 0.90
  paddleocr: 0.92
  demo-fallback: 0.55
```

#### 5.3 Pipeline Telemetry
- Structured log per stage: `stage`, `duration_ms`, `input_hash`, `output_summary`, `warnings`
- Metrics export (Prometheus counters/histograms optional)
- Request correlation ID propagation

#### 5.4 Confidence Model Registry
- Version confidence models
- A/B test via config flag
- Fallback to previous version on regression

### Deliverables
- `services/confidence/` with breakdown + registry
- `config/confidence.yaml`
- Structured logging in all services
- Optional: Prometheus metrics endpoint

---

## Phase 6: Pipeline Orchestration & Error Handling (Week 6-7)

### Goals
- Centralize pipeline orchestration
- Add retry, timeout, circuit breaker patterns
- Comprehensive error types with user-friendly messages

### Tasks

#### 6.1 Pipeline Orchestrator
```
services/pipeline/
  __init__.py
  orchestrator.py      # Main pipeline coordinator
  stages.py            # Stage definitions + dependencies
  context.py           # PipelineContext dataclass
  errors.py            # Custom exception hierarchy
  retry.py             # Retry policies per stage
```

#### 6.2 Error Hierarchy
```python
class PipelineError(Exception): ...
class PreprocessError(PipelineError): ...
class OCRError(PipelineError): ...
class EntityExtractionError(PipelineError): ...
class MedicineMatchError(PipelineError): ...
class ConfidenceError(PipelineError): ...
class VerificationError(PipelineError): ...
```

#### 6.3 Stage Retry Policies
- OCR: retry once with different preprocessing
- Medicine match: no retry (deterministic)
- Configurable per stage via `config/pipeline.yaml`

#### 6.4 Pipeline Context
- Carries: image_hash, correlation_id, timings, intermediate results
- Enables debugging/replay of failed requests

### Deliverables
- `services/pipeline/` orchestration package
- Custom exception hierarchy
- `config/pipeline.yaml` with retry/timeouts
- Updated `main.py` to use orchestrator

---

## Phase 7: Testing & Quality Infrastructure (Week 7-8)

### Goals
- Unit tests for each service in isolation
- Integration tests for full pipeline
- Property-based testing for matchers
- Performance benchmarks

### Tasks

#### 7.1 Test Structure
```
tests/
  unit/
    services/
      test_preprocess.py
      test_ocr.py
      test_nlp.py
      test_medicines.py
      test_confidence.py
      test_pipeline.py
  integration/
    test_full_pipeline.py
    test_ocr_engines.py
  fixtures/
    images/           # Sample prescriptions
    prescriptions/    # Ground truth JSON
  property/
    test_matcher_properties.py  # Hypothesis tests
  benchmarks/
    benchmark_pipeline.py
```

#### 7.2 Test Utilities
- `tests/conftest.py`: fixtures for sample images, mock OCR, test medicines
- `tests/helpers.py`: assertion helpers for entity/medicine structures

#### 7.3 CI Integration
- GitHub Actions: run unit + integration on PR
- Benchmark comparison on main branch
- Coverage target: ≥80% for services/

### Deliverables
- Complete test suite with fixtures
- Property-based tests for fuzzy matching
- Benchmark script + CI workflow

---

## Phase 8: Performance & Caching (Week 8-9)

### Goals
- Add caching for expensive operations
- Optimize image preprocessing
- Profile and optimize hot paths

### Tasks

#### 8.1 Caching Layer
- Medicine match results: LRU cache (max 10k entries)
- OCR results for identical images: hash-based cache
- Preprocessed images: optional cache for re-analysis

#### 8.2 Preprocessing Optimization
- Profile OpenCV operations
- Consider: single resize, combined denoise+CLAHE
- Add `preprocess_fast` variant for real-time use

#### 8.3 Async Pipeline
- Make OCR engines async-compatible
- Use `run_in_threadpool` for CPU-bound stages
- Batch processing endpoint for multiple images

#### 8.4 Profiling
- Add `pyinstrument`/`cProfile` integration
- Identify bottlenecks in pipeline stages

### Deliverables
- Caching decorators/utils
- Fast preprocessing variant
- Async-compatible service interfaces
- Profiling report + optimizations

---

## Phase 9: API Evolution & Versioning (Week 9-10)

### Goals
- Version the pipeline API
- Add request/response validation
- Deprecation strategy

### Tasks

#### 9.1 API Versioning
- `/api/v1/scan` → current
- `/api/v2/scan` → with structured entities, multiple OCR engines
- Header-based version negotiation

#### 9.2 Request Validation
- File type/size via middleware
- Image dimension limits
- Rate limiting per IP

#### 9.3 Response Enrichment
- Add `pipeline_version`, `model_versions`, `processing_time_ms`
- Structured error responses with error codes

### Deliverables
- Versioned API routes
- Validation middleware
- Enhanced response metadata

---

## Summary Timeline

| Phase | Focus | Duration | Key Deliverable |
|-------|-------|----------|-----------------|
| 1 | Foundation & Abstraction | 2 weeks | Protocols, logging, config extraction |
| 2 | OCR Multi-Backend | 2 weeks | EasyOCR/PaddleOCR + benchmark |
| 3 | Medicine DB Enhancement | 2 weeks | Repository pattern, SQLite, CLI |
| 4 | NLP Modularization | 2 weeks | Pluggable extractors, spaCy ready |
| 5 | Confidence & Observability | 2 weeks | Explainable confidence, telemetry |
| 6 | Pipeline Orchestration | 2 weeks | Orchestrator, error hierarchy, retry |
| 7 | Testing Infrastructure | 2 weeks | Unit/integration/property tests |
| 8 | Performance & Caching | 2 weeks | Caching, async, profiling |
| 9 | API Versioning | 2 weeks | v2 API, validation, metadata |

**Total: ~18-20 weeks** (can parallelize Phases 2-4, 5-6)

---

## Quick Wins (Do First)

1. **Extract regex patterns to YAML** (1 hour) — decouples config from code
2. **Add structured logging** (2 hours) — immediate debugging value
3. **Type hints on all public functions** (3 hours) — catches bugs early
4. **Move demo_text to test fixture** (30 min) — cleans config
5. **Add confidence weights to config** (1 hour) — enables tuning without code changes

---

## Dependencies Between Phases

```
Phase 1 (Foundation)
    ├──→ Phase 2 (OCR) ──────────────────┐
    ├──→ Phase 3 (Medicines) ────────────┤
    ├──→ Phase 4 (NLP) ──────────────────┼──→ Phase 6 (Orchestration)
    └──→ Phase 5 (Confidence) ───────────┘
                                    │
                           Phase 7 (Testing) ← All phases
                                    │
                           Phase 8 (Performance)
                                    │
                           Phase 9 (API v2)
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking changes to `main.py` | Keep old pipeline working; add new orchestrator alongside |
| OCR engine dependencies heavy | Make optional; lazy import; demo fallback always works |
| Medicine DB migration | JSON repo stays default; SQL repo opt-in |
| Confidence model changes | Version models; A/B test; rollback config flag |
| Timeline slip | Quick wins first; Phase 1 enables parallel work on 2-4 |