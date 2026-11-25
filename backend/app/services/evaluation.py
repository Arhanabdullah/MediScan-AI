from collections import Counter

from app.services.medicines import match_medicine
from app.services.nlp import extract_entities


def sequence_distance(left: list, right: list) -> int:
    previous = list(range(len(right) + 1))

    for left_index, left_item in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_item in enumerate(right, start=1):
            insertion = current[right_index - 1] + 1
            deletion = previous[right_index] + 1
            substitution = previous[right_index - 1] + (left_item != right_item)
            current.append(min(insertion, deletion, substitution))
        previous = current

    return previous[-1]


def levenshtein_distance(left: str, right: str) -> int:
    return sequence_distance(list(left), list(right))


def character_error_rate(reference: str, hypothesis: str) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return round(levenshtein_distance(reference, hypothesis) / len(reference), 4)


def word_error_rate(reference: str, hypothesis: str) -> float:
    reference_tokens = reference.split()
    hypothesis_tokens = hypothesis.split()
    if not reference_tokens:
        return 0.0 if not hypothesis_tokens else 1.0
    distance = sequence_distance(reference_tokens, hypothesis_tokens)
    return round(distance / len(reference_tokens), 4)


def classification_metrics(expected: Counter, predicted: Counter) -> dict[str, float]:
    true_positive = sum((expected & predicted).values())
    false_positive = sum(predicted.values()) - true_positive
    false_negative = sum(expected.values()) - true_positive
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def evaluate_samples(samples: list[dict]) -> dict:
    cer_values: list[float] = []
    wer_values: list[float] = []
    expected_medicines: Counter = Counter()
    predicted_medicines: Counter = Counter()

    for sample in samples:
        reference = sample.get("expected_text", "")
        hypothesis = sample.get("ocr_text", "")
        cer_values.append(character_error_rate(reference, hypothesis))
        wer_values.append(word_error_rate(reference, hypothesis))

        entities = extract_entities(hypothesis)
        predicted = [match_medicine(entity["value"])["matched_name"] for entity in entities["medicine_names"]]
        expected_medicines.update(sample.get("expected_medicines", []))
        predicted_medicines.update(predicted)

    metrics = classification_metrics(expected_medicines, predicted_medicines)
    return {
        "sample_count": len(samples),
        "cer": round(sum(cer_values) / len(cer_values), 4) if cer_values else 0.0,
        "wer": round(sum(wer_values) / len(wer_values), 4) if wer_values else 0.0,
        "medicine_precision": metrics["precision"],
        "medicine_recall": metrics["recall"],
        "medicine_f1": metrics["f1"],
        "note": "Synthetic baseline evaluation only. Not a clinical accuracy claim.",
    }
