# MediScan-AI

### AI-Assisted Prescription Digitization & Medicine Extraction

MediScan-AI is an educational and research-oriented project that explores the use of **Machine Learning (ML), Deep Learning (DL), Computer Vision, Optical Character Recognition (OCR), and Natural Language Processing (NLP)** to digitize prescription images and extract medicine-related information.

The goal is to build a system that can take a prescription image as input, process and recognize its contents, identify medicine names, extract relevant information, and present the results in a structured format along with confidence scores and user verification.

> **Important:** MediScan-AI is a prescription digitization and medicine-name extraction system. It is **not a diagnostic system, prescribing system, or substitute for professional medical advice.**

---

## ✅ Implementation status

This repository currently implements Levels 1–3 and 5–10 of the project plan, plus a Level 4 evaluation harness:

- FastAPI backend with scan, verification, health, auth, history, result detail, delete, model info, and evaluation endpoints.
- React frontend with upload/camera input, preview, editable results, confidence display, authentication, and private history.
- SQLAlchemy persistence with SQLite by default and PostgreSQL-compatible `DATABASE_URL`.
- Private per-user image storage, bcrypt password hashing, and JWT access tokens.
- Evaluation harness for CER/WER and medicine precision/recall/F1 on synthetic samples.
- Docker Compose, Dockerfiles, nginx proxy, and GitHub Actions CI.

No trained ML/DL model is active. The baseline approach, measured synthetic results, and experiment roadmap are documented in `MODEL.md`; agent progress is tracked in `CLAUDE.md`.

---

## 👥 Team Members

| # | Team Member |
|---|-------------|
| 1 | **Arhan Abdullah** |
| 2 | **Shreyansh Soumya** |
| 3 | **Soumalya Roy** |
| 4 | **Nayab Nasim** |
| 5 | **Ashish Kumar** |

---

## 🎯 Project Objective

The primary objective of MediScan-AI is to develop an AI-assisted system capable of extracting useful information from prescription images.

The system aims to:

- Accept a prescription image as input.
- Improve the image using computer vision and image preprocessing techniques.
- Extract text from the prescription using OCR.
- Identify medicine names from the extracted text.
- Handle common OCR errors using normalization and fuzzy matching.
- Extract additional prescription entities such as:
  - Medicine name
  - Strength
  - Frequency
  - Instructions
- Assign confidence scores to detected results.
- Allow the user to confirm or edit uncertain results.
- Present the final information in a structured and understandable format.

The project will initially focus on **printed prescriptions**. Handwritten prescription recognition can be introduced progressively as the project develops.

---

## 💡 Problem Statement

Prescription information is often available as an image or handwritten/printed document rather than in a structured digital format. Extracting medicine names and related information manually can be time-consuming and error-prone.

MediScan-AI aims to investigate how AI-based image processing, OCR, NLP, and machine-learning techniques can be combined to convert prescription images into structured information.

The system is intended primarily for **prescription digitization and information extraction**, rather than making medical decisions.

---

## 🔄 System Pipeline

The overall processing pipeline is:

```text
Prescription Image
        ↓
Image Preprocessing
        ↓
OCR / Handwriting Recognition
        ↓
Extracted Text
        ↓
Medicine Entity Detection
        ↓
Fuzzy / ML Matching
        ↓
Medicine Vocabulary / Database
        ↓
Confidence Score
        ↓
User Verification
        ↓
Structured Result
```

### Example

Suppose the OCR engine produces:

```text
Paracetmol 500 mg twice daily after food
```

The system can process it as:

```text
OCR Output
    ↓
"Paracetmol 500 mg twice daily after food"
    ↓
Normalization
    ↓
Medicine Matching
    ↓
"Paracetamol"
    ↓
Entity Extraction
    ↓
Medicine:     Paracetamol
Strength:     500 mg
Frequency:    twice daily
Instruction:  after food
    ↓
Confidence Score
    ↓
User Confirmation
```

---

## 🧠 Core Components

### 1. Image Preprocessing

Prescription images may contain noise, poor lighting, skewed text, low contrast, or other image-quality issues.

The preprocessing stage will use computer vision techniques to improve the input before OCR.

Planned techniques include:

- Image resizing
- Grayscale conversion
- Noise reduction
- Contrast enhancement
- Skew/rotation correction
- Thresholding
- Cropping relevant text regions
- Other suitable image enhancement techniques

Preprocessing should not simply be added for the sake of processing. Its effectiveness will be evaluated by comparing OCR performance before and after preprocessing.

---

### 2. Optical Character Recognition (OCR)

OCR converts text present in an image into machine-readable text.

The initial development can begin with existing OCR engines and compare their performance.

Potential OCR technologies include:

- **Tesseract**
- **EasyOCR**
- **PaddleOCR**

The project can later experiment with deep-learning-based OCR and handwriting recognition.

OCR performance will be evaluated using:

- **Character Error Rate (CER)**
- **Word Error Rate (WER)**

The aim is to determine which OCR approach works best for the project's prescription dataset.

---

### 3. Medicine Recognition

Raw OCR output may contain spelling mistakes.

For example:

```text
OCR Output:
Paracetmol
```

The expected medicine name may be:

```text
Paracetamol
```

The medicine recognition pipeline will initially use normalization and fuzzy matching against a medicine vocabulary.

```text
OCR Text
    ↓
Normalization
    ↓
Fuzzy Similarity Search
    ↓
Medicine Vocabulary
    ↓
Matched Medicine
    ↓
Confidence Score
```

**RapidFuzz** can be used for the initial fuzzy matching implementation.

Later versions may experiment with machine-learning or deep-learning approaches for medicine recognition.

---

### 4. NLP and Entity Extraction

After OCR and medicine recognition, the NLP component will extract structured entities from the prescription text.

For example:

```text
"Paracetamol 500 mg twice daily after food"
```

The system can identify:

```text
Paracetamol  → MEDICINE
500 mg       → STRENGTH
twice daily  → FREQUENCY
after food   → INSTRUCTION
```

Initial development can use:

- Regular expressions
- Normalization rules
- Medicine vocabulary
- Fuzzy matching

Later development can explore:

- spaCy
- Named Entity Recognition (NER)
- Transformer-based models
- Confidence scoring

---

## 🤖 Machine Learning & Deep Learning

Machine Learning and Deep Learning will be introduced progressively rather than attempting to train a complex model from the beginning.

The initial system should establish a reliable baseline using existing OCR and matching techniques.

The development can then progress toward:

```text
Baseline OCR
     ↓
Image Preprocessing
     ↓
OCR Comparison
     ↓
Fuzzy Matching
     ↓
ML/DL Experiments
     ↓
NLP / NER
     ↓
End-to-End Evaluation
```

Potential deep-learning concepts to explore include:

- CNNs
- Transfer Learning
- RNN/LSTM concepts
- Transformer architectures
- Deep-learning-based OCR
- Handwriting recognition

The selected models should be compared using actual experimental results.

> **No accuracy values should be claimed unless they have been measured on an appropriate evaluation dataset.**

---

## 🏗️ High-Level System Architecture

The intended application architecture is:

```text
                         USER
                           ↓
                    WEB INTERFACE
                           ↓
                     REST API
                           ↓
                    FASTAPI BACKEND
                           ↓
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
 Image Preprocessing      OCR             NLP / NER
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ↓
                  Fuzzy / ML Matching
                           ↓
                   Medicine Database
                           ↓
                   Confidence Score
                           ↓
                  User Verification
                           ↓
                  Structured Results
```

The final system is planned to include a web interface, backend API, AI processing pipeline, and database.

---

## 🛠️ Technology Stack

| Area | Technology |
|------|------------|
| Programming | Python |
| Computer Vision | OpenCV, NumPy, Pandas |
| OCR | Tesseract / EasyOCR / PaddleOCR |
| Machine Learning | ML algorithms and model experimentation |
| Deep Learning | CNNs, RNN/LSTM concepts, Transformers |
| NLP | Regex, RapidFuzz, spaCy, NER |
| Backend | FastAPI |
| Frontend | React, HTML, CSS, JavaScript |
| Database | PostgreSQL |
| Version Control | Git / GitHub |

---

## 🚀 Development Approach

The project will be developed in stages.

The initial goal is **not** to build the entire application immediately.

Instead, the team will first establish a small working pipeline:

```text
ONE IMAGE
    ↓
OCR
    ↓
TEXT
    ↓
MEDICINE NAME
```

Once this baseline works reliably, additional components can be introduced.

---

## 📈 Development Levels

### Level 1 — Basic Prototype

Build the first working pipeline:

```text
Prescription Image
        ↓
OCR
        ↓
Extracted Text
        ↓
Simple Medicine Dictionary Matching
```

**Deliverable:** A basic system that can take one prescription image and identify medicine names from OCR output.

---

### Level 2 — Image Processing

Introduce OpenCV-based preprocessing.

The team will experiment with:

- Grayscale conversion
- Noise reduction
- Contrast enhancement
- Skew correction
- Thresholding

**Deliverable:** A preprocessing pipeline and comparison of OCR results before and after preprocessing.

---

### Level 3 — Fuzzy Matching

OCR may produce small spelling errors.

Fuzzy matching will be introduced to match imperfect OCR output against a medicine vocabulary.

**Deliverable:** Improved medicine recognition for common OCR errors.

---

### Level 4 — ML / DL

Experiment with machine-learning and deep-learning approaches.

Possible areas include:

- Deep-learning OCR
- CNN-based recognition
- Transfer learning
- RNN/LSTM concepts
- Transformer-based approaches

**Deliverable:** Experimental comparison of suitable ML/DL approaches.

---

### Level 5 — NLP

Introduce structured extraction of:

- Medicine
- Strength
- Frequency
- Instructions

**Deliverable:** Prescription text converted into structured entities.

---

### Level 6 — Web Backend

Expose the AI pipeline through a FastAPI REST API.

**Deliverable:** Backend endpoints capable of receiving prescription images and returning structured analysis results.

---

### Level 7 — Frontend

Develop a React-based interface containing features such as:

- Home page
- About / How It Works
- Prescription upload
- Camera input
- Image preview
- Processing status
- Results display
- Confidence scores
- Confirm/Edit controls

**Deliverable:** A usable web interface connected to the backend.

---

### Level 8 — Database & Authentication

Introduce PostgreSQL and user-related functionality.

Potential features include:

- User accounts
- Secure authentication
- Prescription history
- Detected medicine records
- Secure storage

**Deliverable:** Persistent and protected application data.

---

### Level 9 — Human Verification

The system should clearly display uncertainty.

For ambiguous medicine recognition:

```text
Detected Medicine: Paracetamol
Confidence: 0.72

[ Confirm ] [ Edit ]
```

**Deliverable:** A user verification workflow for uncertain results.

---

### Level 10 — Testing & Deployment

The complete system will be evaluated for:

- OCR performance
- Medicine extraction
- API behavior
- Security
- Error handling
- Usability
- Edge cases
- Deployment readiness

**Deliverable:** Tested, documented, and deployable application.

---

## 🔌 API

The implemented REST endpoints are:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/health` | Check backend health (`/health` alias also available) |
| `POST` | `/api/auth/register` | Create a user account |
| `POST` | `/api/auth/login` | Obtain a JWT access token |
| `GET` | `/api/me` | Get the authenticated user |
| `POST` | `/api/scan` | Analyze an uploaded prescription image |
| `GET` | `/api/scan/{id}` | Retrieve a scan result by id |
| `POST` | `/api/verify` | Save user-confirmed medicines |
| `GET` | `/api/history` | List the authenticated user's saved scans |
| `GET` | `/api/result/{id}` | Retrieve a saved result |
| `DELETE` | `/api/result/{id}` | Delete a saved result and its private image |
| `GET` | `/api/model-info` | Describe the active pipeline |
| `GET` | `/api/evaluation` | Run the synthetic baseline evaluation |

`/api/prescription/analyze` and `/api/upload` remain as aliases for `/api/scan`.

Example response:

```json
{
  "raw_text": "Paracetamol 500 mg",
  "medicines": [
    {
      "name": "Paracetamol",
      "strength": "500 mg",
      "confidence": 0.94
    }
  ]
}
```

The exact API contract may evolve during development.

---

## 🗄️ Database Schema

The backend uses SQLAlchemy with SQLite by default. Setting `DATABASE_URL` to a PostgreSQL connection string switches the same schema to PostgreSQL. The implemented entities represent:

### Users

```text
id
name
email
password_hash
created_at
```

### Prescriptions

```text
id
user_id
image_path
created_at
```

### Detected Medicines

```text
id
prescription_id
medicine_id
ocr_text
confidence
```

### Medicines

```text
id
name
generic_name
strength
form
manufacturer
```

Relationships:

```text
USER
  ↓
many PRESCRIPTIONS
  ↓
many DETECTED_MEDICINES
  ↓
MEDICINE
```

The database design may be refined as implementation requirements become clearer.

---

## 🧪 Dataset

A synthetic starter dataset can be used during initial software and ML development.

Example medicines include:

- Paracetamol
- Azithromycin
- Amoxicillin
- Cetirizine
- Ibuprofen
- Metformin
- Omeprazole

The starter data can include:

- Prescription-like images
- OCR spelling variations
- Medicine names
- Strength
- Frequency
- Instructions

### Dataset Splitting

The dataset should be separated into:

```text
Training Set
Validation Set
Test Set
```

The test set should remain unseen during model development.

The team should also check:

- Class distribution
- Duplicate images
- Annotation quality
- Data leakage
- Dataset licensing/permissions

If multiple images from the same patient are available and patient grouping is known, those images should be kept within the appropriate split to avoid leakage.

> **Never commit real patient prescriptions or sensitive medical information to GitHub.**

---

## 📊 Evaluation

Evaluation will be based on measurable metrics. The implemented harness is `backend/scripts/evaluate.py`; it reads synthetic samples from `backend/data/eval_samples.json` and is also exposed through `GET /api/evaluation`.

```powershell
cd backend
py scripts/evaluate.py
```

| Component | Suggested Metrics |
|-----------|-------------------|
| OCR | Character Error Rate (CER), Word Error Rate (WER) |
| Medicine Recognition | Precision, Recall, F1-score |
| End-to-End System | Exact-match / field-level accuracy |
| API/System | Latency, upload failure rate, error handling |
| Usability | Usability testing and user feedback |

### OCR Evaluation

OCR will be evaluated using:

- Character Error Rate
- Word Error Rate

### Medicine Recognition Evaluation

Medicine recognition can be evaluated using:

- Precision
- Recall
- F1-score

### End-to-End Evaluation

The complete pipeline can be evaluated based on whether the expected medicine and relevant fields are correctly extracted.

> **All performance values reported in the final project should come from actual experiments.**

---

## 🧩 Testing

Automated checks run locally and in GitHub Actions:

```powershell
cd backend
py -m pytest
py scripts/evaluate.py

cd ../frontend
npm run lint
npm run build
```

Testing should cover both individual components and the complete system.

Important scenarios include:

- Valid prescription uploads
- Invalid file uploads
- Oversized files
- Blurred images
- Poor-quality images
- OCR failure
- No medicine detected
- Incorrect OCR output
- API errors
- API timeouts
- Different handwriting styles
- Different image quality
- Unseen test samples
- User registration/login
- Logout
- Access control
- Prescription history retrieval

---

## 🔐 Privacy & Security

Prescription images may contain sensitive information.

The project should therefore follow appropriate privacy and security practices.

Important principles include:

- Do not commit real patient prescriptions to GitHub.
- Minimize collection of personally identifiable information.
- Protect uploaded prescription images.
- Avoid publicly accessible prescription image URLs.
- Use secure password hashing.
- Validate uploaded files.
- Implement appropriate access control.
- Avoid exposing sensitive information in API responses or logs.
- Keep API keys and passwords outside the repository.

---

## ⚠️ Medical-AI Boundaries

MediScan-AI is intended to **extract information that is written on a prescription**.

It should not independently determine what a patient should take.

The system must:

- Not claim to diagnose medical conditions.
- Not prescribe medicines.
- Not automatically recommend medicine replacements.
- Not automatically recommend doses based only on OCR output.
- Clearly distinguish extracted prescription information from medical advice.
- Display uncertainty for low-confidence predictions.
- Allow users to confirm or edit ambiguous medicine recognition.
- Document limitations of the system.
- Clearly communicate that the system should not replace qualified healthcare professionals.

---



### Contribution Guidelines

- Make small and meaningful commits.
- Use feature branches for new functionality.
- Keep changes focused.
- Test changes before opening a pull request.
- Review code before merging.
- Keep the `main` branch stable.
- Document important implementation decisions.
- Never commit passwords or API keys.
- Never commit private prescription images.
- Avoid committing large raw datasets.

---

## 📅 10-Week Development Plan

| Weeks | Main Work |
|-------|-----------|
| **1–2** | Problem definition, project scope, dataset research, Git setup, Python and basic OCR |
| **3–4** | Image preprocessing, OCR baseline, medicine vocabulary and baseline matching |
| **5** | Fuzzy matching, evaluation and first end-to-end prototype |
| **6** | FastAPI backend and OCR/model integration |
| **7** | React frontend and API integration |
| **8** | PostgreSQL, authentication, history and confidence/user verification |
| **9** | Advanced DL/NLP experiments, testing, security and edge cases |
| **10** | Deployment, documentation, presentation, demo and viva preparation |

---

## 🎬 Final Demo Flow

The intended final demonstration will follow this process:

```text
1. User opens the website
              ↓
2. User uploads a prescription
              ↓
3. Frontend validates and previews the image
              ↓
4. Backend receives the image
              ↓
5. Image preprocessing is performed
              ↓
6. OCR extracts text
              ↓
7. NLP identifies medicine candidates
              ↓
8. Matching engine checks the medicine vocabulary
              ↓
9. System calculates confidence
              ↓
10. User confirms or edits uncertain results
              ↓
11. Structured medicine information is displayed
              ↓
12. Optional history is stored securely
```

---

## 🎯 Initial Milestone

The first milestone is deliberately small.

The team should first make the following pipeline work:

```text
ONE IMAGE
    ↓
OCR
    ↓
TEXT
    ↓
MEDICINE NAME
```

Once this works reliably, the team can proceed toward:

```text
Image Processing
       ↓
OCR Comparison
       ↓
Fuzzy Matching
       ↓
NLP
       ↓
ML/DL
       ↓
FastAPI
       ↓
React
       ↓
PostgreSQL
       ↓
Authentication
       ↓
Testing
       ↓
Deployment
```

This incremental approach allows the team to validate each major component before increasing system complexity.

---

## 🔭 Future Scope

Potential future improvements include:

- Better handwritten prescription recognition
- Deep-learning-based OCR
- Transformer-based NLP
- Improved medicine entity recognition
- Better confidence estimation
- Expanded medicine vocabulary
- Multilingual prescription support
- Improved handling of poor-quality images
- Better handling of handwritten text
- Secure prescription history
- More comprehensive evaluation datasets
- Production deployment

---

## 📚 Learning Goals

By the end of the project, the team should understand not only their individual modules but also how the complete system works.

Every team member should be able to explain:

```text
Image
  ↓
Preprocessing
  ↓
OCR
  ↓
NLP / ML / DL
  ↓
Medicine Matching
  ↓
API
  ↓
Database
  ↓
Frontend
```

The team should also understand:

- How the dataset was created or obtained.
- How preprocessing affects OCR.
- How OCR performance was evaluated.
- How medicine recognition was implemented.
- Which ML/DL approaches were tested.
- Why a particular model or approach was selected.
- How the API communicates with the frontend.
- How data is stored.
- How security and privacy are handled.
- What the system's limitations are.

---

## 🚧 Project Status

**Active Development**

MediScan-AI is currently being developed incrementally, beginning with the core prescription image → OCR → medicine extraction pipeline and progressing toward a complete AI-assisted web application.

---

## ⚖️ Disclaimer

MediScan-AI is an **educational/research project** focused on prescription digitization and medicine-information extraction.

It is **not a medical diagnostic tool, prescribing system, or replacement for a qualified healthcare professional**.

The extracted information should always be verified by an appropriate healthcare professional before being used for medical decisions.

---

## ⭐ MediScan-AI

> **From Prescription Image to Structured Medicine Information.**
