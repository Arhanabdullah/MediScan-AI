"""Phase 3 tests: repository pattern, validation, loading and enhanced matching."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from app.services.medicines import (
    JsonMedicineRepository,
    Medicine,
    MedicineRepository,
    SqlMedicineRepository,
    get_repository,
    match_medicine,
    normalize,
    phonetic_key,
    set_repository,
    validate_records,
)
from app.services.medicines.loader import export_to_json, load_from_csv, load_from_json
from app.services.nlp import extract_entities
import manage_medicines


@pytest.fixture(autouse=True)
def _restore_repository():
    """Every test starts and ends with the configured default repository."""
    original = get_repository()
    yield
    set_repository(original)


def _record(identifier: str = "test-1", name: str = "Testmed", **extra) -> dict:
    return {"id": identifier, "name": name, "generic_name": name, "strength": "10 mg", "form": "tablet", **extra}


def test_repository_protocol_and_models() -> None:
    repo = get_repository()
    assert isinstance(repo, MedicineRepository)
    medicine = Medicine.model_validate(_record(aliases=["TM", "TM"]))
    assert medicine.search_names == ("Testmed", "TM")
    assert Medicine.model_validate({"id": "x", "name": "X", "aliases": "A|B"}).aliases == ["A", "B"]
    with pytest.raises(ValueError):
        Medicine.model_validate({"id": "", "name": "X"})


def test_validation_duplicates_and_required_generic(tmp_path: Path) -> None:
    duplicate = _record("one", "Paracetamol")
    records = [duplicate, _record("two", "paracetamol", strength="10 MG", form="TABLET")]
    with pytest.raises(ValueError, match="Duplicate medicine"):
        validate_records(records)
    assert len(validate_records(records, check_duplicates=False)) == 2

    with pytest.raises(ValueError, match="generic_name"):
        validate_records([{"id": "x", "name": "X"}], require_generic_name=True)
    with pytest.raises(ValueError, match="Invalid medicine at index 0"):
        validate_records([{"name": "No ID"}])


def test_json_repository_hot_reload(tmp_path: Path) -> None:
    path = tmp_path / "medicines.json"
    path.write_text(json.dumps([_record()]), encoding="utf-8")
    repo = JsonMedicineRepository(path, hot_reload=True)
    assert repo.count() == 1
    assert repo.get("test-1") is not None
    assert repo.get("missing") is None

    path.write_text(json.dumps([_record(), _record("test-2", "Othermed")]), encoding="utf-8")
    assert repo.count() == 2
    assert repo.source == "json"

    stale = JsonMedicineRepository(path, hot_reload=False)
    assert stale.count() == 2
    path.write_text(json.dumps([_record()]), encoding="utf-8")
    assert stale.count() == 2
    stale.reload()
    assert stale.count() == 1


def test_csv_json_loaders_and_export(tmp_path: Path) -> None:
    csv_path = tmp_path / "medicines.csv"
    csv_path.write_text(
        "id,name,generic_name,strength,form,aliases\n"
        "csv-1,Testmed,Testmed,10 mg,tablet,TM|TST\n",
        encoding="utf-8",
    )
    medicines = load_from_csv(csv_path)
    assert medicines[0].aliases == ["TM", "TST"]

    json_path = tmp_path / "medicines.json"
    export_to_json(medicines, json_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))[0]["id"] == "csv-1"
    assert [item.id for item in load_from_json(json_path)] == ["csv-1"]


def test_sqlite_repository_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "medicines.db"
    repo = SqlMedicineRepository(db_path)
    assert repo.source == "sqlite"
    assert repo.count() == 0

    records = [_record("a", "Alpha"), _record("b", "Beta", aliases=["BETA-X"])]
    assert repo.replace_all(records) == 2
    assert repo.count() == 2
    assert repo.get("b") is not None and repo.get("b").aliases == ["BETA-X"]
    names = [item.name for item in repo.all()]
    assert names == ["Alpha", "Beta"]

    assert repo.replace_all([_record("c", "Gamma")]) == 1
    assert [item.id for item in repo.all()] == ["c"]

    with pytest.raises(ValueError):
        repo.replace_all([_record("d", "Gamma"), _record("e", "gamma", strength="10 MG", form="TABLET")])


def test_match_entities_uses_active_repository(tmp_path: Path) -> None:
    path = tmp_path / "medicines.json"
    path.write_text(json.dumps([_record("custom", "Zorblax", strength="20 mg", form="capsule")]), encoding="utf-8")
    set_repository(JsonMedicineRepository(path, hot_reload=False))

    match = match_medicine("Zorblaxx", "20 mg", "capsule")
    assert match is not None
    assert match["id"] == "custom"
    assert isinstance(get_repository().all()[0], Medicine)
    assert normalize("1. Zorblaxx!") == "zorblaxx"
    assert phonetic_key("Zorblax") and phonetic_key("Zorblax") == phonetic_key("Zorblaxx")


def test_nlp_uses_active_repository(tmp_path: Path) -> None:
    path = tmp_path / "medicines.json"
    path.write_text(json.dumps([_record("custom", "Zorblax", aliases=["ZB"])]), encoding="utf-8")
    set_repository(JsonMedicineRepository(path, hot_reload=False))
    entities = extract_entities("1. Zorblax 20 mg tablet twice daily")
    assert any(item["value"] == "Zorblax" for item in entities["medicine_names"])


def test_matcher_protocol_and_thresholds() -> None:
    match = match_medicine("Paracetamol")
    assert match is not None
    assert set(match) >= {"id", "matched_name", "match_score", "confidence", "alternatives"}
    assert match_medicine(" ") is None
    assert match_medicine("Paracetamol", min_score=1.01) is None


def test_per_entry_min_score_is_respected(tmp_path: Path) -> None:
    path = tmp_path / "medicines.json"
    path.write_text(json.dumps([_record("strict", "Zzqqxx", min_score=0.99)]), encoding="utf-8")
    set_repository(JsonMedicineRepository(path, hot_reload=False))
    assert match_medicine("Zzqqyx") is None
    assert match_medicine("Zzqqxx") is not None


def test_cli_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "medicines.json"
    source.write_text(json.dumps([_record("cli-1", "Clinimed")]), encoding="utf-8")
    db_path = tmp_path / "cli.db"

    assert manage_medicines.main(["validate", str(source)]) == 0
    assert "valid medicine record" in capsys.readouterr().out

    assert manage_medicines.main(["migrate", "--source", str(source), "--sqlite-path", str(db_path)]) == 0
    assert SqlMedicineRepository(db_path).count() == 1
    capsys.readouterr()

    assert manage_medicines.main(["migrate", "--source", str(source), "--sqlite-path", str(db_path), "--dry-run"]) == 0
    assert "dry run" in capsys.readouterr().out

    exported = tmp_path / "export.json"
    set_repository(SqlMedicineRepository(db_path))
    assert manage_medicines.main(["export", str(exported)]) == 0
    assert json.loads(exported.read_text(encoding="utf-8"))[0]["id"] == "cli-1"
    capsys.readouterr()

    assert manage_medicines.main(["stats"]) == 0
    assert "backend:" in capsys.readouterr().out

    assert manage_medicines.main(["validate", str(tmp_path / "bad.json")]) == 1
    assert "error:" in capsys.readouterr().err
