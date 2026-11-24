import re

from app.services.medicines import MEDICINES

STRENGTH_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|g|ml|iu|units?)\b", re.IGNORECASE)
FREQUENCY_PATTERN = re.compile(
    r"\b(?:once daily|twice daily|three times daily|four times daily|"
    r"every\s+\d+\s*(?:hours?|hrs?)|at bedtime|as needed|if needed|bd|tds|qid|od|sos)\b",
    re.IGNORECASE,
)
DURATION_PATTERN = re.compile(r"\b(?:for\s+\d+\s+days?|\d+[- ]day(?:\s+course)?)\b", re.IGNORECASE)
FORM_PATTERN = re.compile(
    r"\b(?:tablet|capsule|syrup|suspension|injection|inhaler|drops|cream|ointment|patch)\b",
    re.IGNORECASE,
)
ENTITY_LABELS = {
    "medicine_names": "medicine_name",
    "strengths": "strength",
    "frequencies": "frequency",
    "durations": "duration",
    "forms": "form",
}
SKIP_PREFIXES = (
    "take ",
    "patient",
    "date",
    "rx",
    "ref",
    "sig",
    "q.",
    "diagnosis",
    "advice",
    "contact",
)


def _known_names() -> list[str]:
    names = set()
    for medicine in MEDICINES:
        names.add(medicine.get("name", ""))
        names.add(medicine.get("generic_name", ""))
        names.update(medicine.get("aliases", []))
    return sorted((name for name in names if name), key=len, reverse=True)


def _add(entities: dict[str, list[dict]], key: str, value: str, confidence: float) -> None:
    cleaned = value.strip()
    if not cleaned:
        return
    if any(entity["value"].lower() == cleaned.lower() for entity in entities[key]):
        return
    entities[key].append({"label": ENTITY_LABELS[key], "value": cleaned, "confidence": confidence})


def _looks_like_medicine_line(line: str) -> bool:
    lowered = line.lower().strip()
    if not lowered or lowered.startswith(SKIP_PREFIXES):
        return False
    if len(line) > 90:
        return False
    return bool(STRENGTH_PATTERN.search(line) or FORM_PATTERN.search(line))


def _medicine_candidate(line: str) -> str:
    candidate = re.sub(r"^\s*(?:\d+[.)]?|[-•*])\s*", "", line)
    candidate = STRENGTH_PATTERN.split(candidate, maxsplit=1)[0]
    candidate = FORM_PATTERN.split(candidate, maxsplit=1)[0]
    candidate = re.sub(r"^(?:name|medicine|drug|tab|cap)\s*[:.\-]?\s*", "", candidate, flags=re.IGNORECASE)
    candidate = candidate.strip(" :;,-")
    words = candidate.split()
    return " ".join(words[:5])


def extract_entities(text: str) -> dict[str, list[dict]]:
    entities: dict[str, list[dict]] = {
        "medicine_names": [],
        "strengths": [],
        "frequencies": [],
        "durations": [],
        "forms": [],
    }
    names = _known_names()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        for match in STRENGTH_PATTERN.finditer(line):
            _add(entities, "strengths", match.group(0), 0.92)

        for match in FREQUENCY_PATTERN.finditer(line):
            _add(entities, "frequencies", match.group(0), 0.88)

        for match in DURATION_PATTERN.finditer(line):
            _add(entities, "durations", match.group(0), 0.86)

        for match in FORM_PATTERN.finditer(line):
            _add(entities, "forms", match.group(0), 0.9)

        known_match = next(
            (name for name in names if re.search(rf"\b{re.escape(name)}\b", line, re.IGNORECASE)),
            None,
        )
        if known_match:
            _add(entities, "medicine_names", known_match, 0.95)
            continue

        if _looks_like_medicine_line(line):
            candidate = _medicine_candidate(line)
            if candidate and len(candidate) > 2:
                _add(entities, "medicine_names", candidate, 0.68)

    return entities
