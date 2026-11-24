from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent


class Settings:
    project_name: str = os.getenv("PROJECT_NAME", "MediScan-AI API")
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    max_image_dimension: int = int(os.getenv("MAX_IMAGE_DIMENSION", "1800"))
    ocr_backend: str = os.getenv("OCR_BACKEND", "auto").lower()
    tesseract_cmd: str | None = os.getenv("TESSERACT_CMD") or None
    medicine_db_path: Path = Path(
        os.getenv("MEDICINE_DB_PATH", str(BASE_DIR / "data" / "medicines.json"))
    )
    demo_text: str = """Rx
Patient: Demo Patient
Date: 2026-01-15

1. Amoxicillin 500 mg capsule
Take 1 capsule three times daily for 7 days

2. Paracetamol 650 mg tablet
Take 1 tablet every 6 hours if needed

3. Cetirizine 10 mg tablet
Take 1 tablet once daily at bedtime
"""


settings = Settings()
