import io
import os
import tempfile
import uuid
from pathlib import Path

os.environ["OCR_BACKEND"] = "demo"

_test_db_path = Path(tempfile.gettempdir()) / "mediscan-test.db"
_test_db_path.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"

_test_upload_dir = Path(tempfile.gettempdir()) / "mediscan-test-uploads"
os.environ["UPLOAD_DIR"] = str(_test_upload_dir)

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (120, 80), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _auth_headers() -> dict[str, str]:
    username = f"tester-{uuid.uuid4().hex[:8]}"
    register = client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "strongpass123"},
    )
    assert register.status_code == 200
    login = client.post("/api/auth/login", json={"username": username, "password": "strongpass123"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


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


def test_model_info_and_evaluation() -> None:
    model = client.get("/api/model-info")
    assert model.status_code == 200
    assert model.json()["trained_model"] is False

    evaluation = client.get("/api/evaluation")
    assert evaluation.status_code == 200
    assert evaluation.json()["sample_count"] == 5
    assert 0 <= evaluation.json()["medicine_f1"] <= 1


def test_anonymous_scan_and_verify() -> None:
    scan_response = client.post(
        "/api/scan",
        files={"file": ("prescription.png", _image_bytes(), "image/png")},
    )
    assert scan_response.status_code == 200
    data = scan_response.json()
    assert data["ocr_engine"] == "demo-fallback"
    assert data["raw_text"]
    assert data["medicines"]
    assert client.get(f"/api/scan/{data['scan_id']}").status_code == 200

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


def test_authenticated_scan_history_and_delete() -> None:
    headers = _auth_headers()
    assert client.get("/api/me", headers=headers).status_code == 200

    scan_response = client.post(
        "/api/scan",
        headers=headers,
        files={"file": ("prescription.png", _image_bytes(), "image/png")},
    )
    assert scan_response.status_code == 200
    scan_id = scan_response.json()["scan_id"]

    assert client.get(f"/api/scan/{scan_id}").status_code == 404
    owned_scan = client.get(f"/api/scan/{scan_id}", headers=headers)
    assert owned_scan.status_code == 200
    assert owned_scan.json()["raw_text"]

    history = client.get("/api/history", headers=headers)
    assert history.status_code == 200
    assert any(item["scan_id"] == scan_id for item in history.json())

    result = client.get(f"/api/result/{scan_id}", headers=headers)
    assert result.status_code == 200
    assert result.json()["medicines"]

    delete = client.delete(f"/api/result/{scan_id}", headers=headers)
    assert delete.status_code == 200
    assert delete.json()["status"] == "deleted"


def test_protected_routes_require_auth() -> None:
    assert client.get("/api/history").status_code == 401
    assert client.get("/api/me").status_code == 401
