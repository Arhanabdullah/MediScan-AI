import io
import os

os.environ["OCR_BACKEND"] = "demo"

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (120, 80), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["medicine_count"] > 0


def test_correlation_id_is_echoed() -> None:
    response = client.post(
        "/api/scan",
        headers={"X-Correlation-ID": "abc123"},
        files={"file": ("prescription.png", _image_bytes(), "image/png")},
    )
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "abc123"


def test_scan_and_verify() -> None:
    scan_response = client.post(
        "/api/scan",
        files={"file": ("prescription.png", _image_bytes(), "image/png")},
    )
    assert scan_response.status_code == 200
    data = scan_response.json()
    assert data["ocr_engine"] == "demo-fallback"
    assert data["raw_text"]
    assert data["medicines"]

    verify_response = client.post(
        "/api/verify",
        json={
            "scan_id": data["scan_id"],
            "medicines": [
                {
                    "id": medicine["id"],
                    "name": medicine["matched_name"],
                    "strength": medicine["strength"],
                    "frequency": "once daily",
                    "confirmed": True,
                }
                for medicine in data["medicines"]
            ],
            "raw_text": data["raw_text"],
        },
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["status"] == "verified"
    assert verify_response.json()["final_result"]["overall_confidence"] == 1.0
