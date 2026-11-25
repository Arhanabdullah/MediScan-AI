"""Scan a local image through the MediScan pipeline, no server required.

Run from backend/ (or with an absolute path from anywhere):

    python scripts/scan_image.py "C:\\path\\to\\image.png"
    python scripts/scan_image.py "C:\\path\\to\\image.png" --engine tesseract
    python scripts/scan_image.py "C:\\path\\to\\image.png" --summary
    python scripts/scan_image.py "C:\\path\\to\\image.png" --text-only
    python scripts/scan_image.py "C:\\path\\to\\image.png" --output "$env:TEMP\\scan.json"

Reports go to stdout by default. Do not commit real prescriptions or patient
data; save outputs outside the repository (for example under $env:TEMP).
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

os.environ.setdefault("MEDISCAN_LOG_LEVEL", "ERROR")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("image", help="Path to a PNG/JPEG/WEBP/BMP/TIFF image")
    parser.add_argument(
        "--engine",
        help="Force an OCR backend (auto, tesseract, easyocr, paddleocr, demo)",
    )
    parser.add_argument(
        "--medicine-repo",
        choices=("json", "sqlite"),
        help="Override the configured medicine repository backend",
    )
    parser.add_argument("--sqlite-path", help="SQLite file to use with --medicine-repo sqlite")
    parser.add_argument("--correlation-id", help="Correlation ID to send/echo in the response")
    parser.add_argument("--summary", action="store_true", help="Print a short human-readable summary")
    parser.add_argument("--text-only", action="store_true", help="Print only the OCR text")
    parser.add_argument("--output", type=Path, help="Also write the full JSON response to this file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    path = Path(args.image).expanduser()
    if not path.is_file():
        print(f"error: image not found: {path}", file=sys.stderr)
        return 2
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        print(
            f"error: unsupported image type '{path.suffix or '(none)'}'; "
            f"use one of {', '.join(sorted(ALLOWED_SUFFIXES))}",
            file=sys.stderr,
        )
        return 2
    size = path.stat().st_size
    if size == 0 or size > MAX_UPLOAD_BYTES:
        print(f"error: image must be non-empty and under {MAX_UPLOAD_BYTES} bytes (got {size})", file=sys.stderr)
        return 2

    # Settings are built at import time, so apply overrides before importing app.
    if args.engine:
        os.environ["OCR_BACKEND"] = args.engine.lower()
    if args.medicine_repo:
        os.environ["MEDICINE_REPO"] = args.medicine_repo
    if args.sqlite_path:
        os.environ["MEDICINE_SQLITE_PATH"] = args.sqlite_path

    from fastapi.testclient import TestClient

    from app.main import app

    headers = {"X-Correlation-ID": args.correlation_id} if args.correlation_id else None
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    try:
        response = TestClient(app).post(
            "/api/scan",
            headers=headers,
            files={"file": (path.name, path.read_bytes(), content_type)},
        )
    except Exception as error:
        print(f"error: pipeline failed: {error}", file=sys.stderr)
        return 1

    if response.status_code != 200:
        detail = response.json().get("detail", response.text)
        print(f"error: API returned {response.status_code}: {detail}", file=sys.stderr)
        return 1

    result = response.json()
    if args.text_only:
        print(result["raw_text"])
    elif args.summary:
        print(f"engine:      {result['ocr_engine']}")
        print(f"confidence:  {result['overall_confidence']}")
        print(f"image size:  {result['image_size']}")
        print("medicines:")
        for medicine in result["medicines"]:
            print(f"  - {medicine['matched_name']} ({medicine['confidence']})")
        if result["warnings"]:
            print("warnings:")
            for warning in result["warnings"]:
                print(f"  - {warning}")
        print(result["disclaimer"])
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.output:
        target = args.output.expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\n[saved to {target}]", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
