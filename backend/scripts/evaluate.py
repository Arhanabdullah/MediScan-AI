import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.evaluation import evaluate_samples


def main() -> None:
    sample_path = BASE_DIR / "data" / "eval_samples.json"
    with sample_path.open(encoding="utf-8") as file:
        samples = json.load(file)
    print(json.dumps(evaluate_samples(samples), indent=2))


if __name__ == "__main__":
    main()
