"""Evaluate OCR text samples with CER/WER and medicine precision/recall/F1.

Usage (from backend/):
    python scripts/evaluate.py
    python scripts/evaluate.py --data "C:\\path\\to\\my_samples.json"
    python scripts/evaluate.py --data "C:\\path\\to\\my_samples.json" --output reports/custom.json

The default dataset is synthetic. Custom datasets stay wherever you put them;
nothing is copied into the repository and no accuracy claim is made.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.evaluation import evaluate_samples

DEFAULT_DATA = BASE_DIR / "data" / "eval_samples.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA,
        help="JSON list of samples (default: bundled synthetic eval_samples.json)",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args(argv)

    with args.data.open(encoding="utf-8") as file:
        samples: list[dict[str, Any]] = json.load(file)
    result = evaluate_samples(samples)

    if args.data.resolve() != DEFAULT_DATA.resolve():
        result["sample_source"] = str(args.data)
        result["note"] = "Custom dataset evaluation only. Not a clinical accuracy claim."

    print(json.dumps(result, indent=2))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
