"""Admin CLI for medicine data: validate, migrate, import/export, and stats.

Run from backend/ (all paths are resolved relative to backend/ unless absolute):

    python -m scripts.manage_medicines validate
    python -m scripts.manage_medicines stats
    python -m scripts.manage_medicines migrate
    python -m scripts.manage_medicines migrate --dry-run
    python -m scripts.manage_medicines import data/extra_medicines.csv
    python -m scripts.manage_medicines export data/medicines_snapshot.json

The default JSON file stays authoritative; SQLite is opt-in via
``MEDICINE_REPO=sqlite`` (or config/medicines.yaml). This CLI only writes the
SQLite database, never the source JSON file, unless ``export`` is used.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("MEDISCAN_LOG_LEVEL", "WARNING")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import BACKEND_DIR, settings
from app.services.medicines import SqlMedicineRepository, get_repository
from app.services.medicines.loader import export_to_json, load_from_csv, load_from_json
from app.services.medicines.validation import validate_records


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else BACKEND_DIR / candidate


def _read_any(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_from_csv(path)
    if suffix == ".json":
        return load_from_json(path)
    raise ValueError(f"Unsupported file type '{suffix}'; use .json or .csv.")


def command_validate(args: argparse.Namespace) -> int:
    path = _resolve(args.file) if args.file else settings.medicine_db_path
    medicines = _read_any(path)
    validate_records(
        [medicine.model_dump() for medicine in medicines],
        check_duplicates=bool(settings.medicines_validation.get("check_duplicates", True)),
        require_generic_name=bool(settings.medicines_validation.get("require_generic_name", False)),
    )
    print(f"OK: {len(medicines)} valid medicine record(s) in {path}")
    return 0


def command_stats(args: argparse.Namespace) -> int:
    repository = get_repository()
    medicines = repository.all()
    with_generic = sum(1 for medicine in medicines if medicine.generic_name)
    with_strength = sum(1 for medicine in medicines if medicine.strength)
    alias_count = sum(len(medicine.search_names) for medicine in medicines)
    print(f"backend:     {repository.source}")
    print(f"medicines:   {len(medicines)}")
    print(f"with generic name: {with_generic}")
    print(f"with strength:     {with_strength}")
    print(f"search names:      {alias_count}")
    if args.show_ids:
        print("ids:")
        for medicine in medicines:
            print(f"  {medicine.id}: {medicine.name}")
    return 0


def _sqlite_path(args: argparse.Namespace) -> Path:
    path = _resolve(args.sqlite_path or str(settings.medicines_repository.get("sqlite_path", "data/medicines.db")))
    return path


def command_migrate(args: argparse.Namespace) -> int:
    source = _resolve(args.source or str(settings.medicine_db_path))
    medicines = _read_any(source)
    target = _sqlite_path(args)
    print(f"source: {source} ({len(medicines)} record(s))")
    print(f"target: {target}")
    if args.dry_run:
        print("dry run: no database changes made")
        return 0
    repository = SqlMedicineRepository(target)
    written = repository.replace_all(medicines)
    print(f"migrated {written} record(s) into SQLite")
    return 0


def command_import(args: argparse.Namespace) -> int:
    """Import records into SQLite (replace_all), with an optional dry run."""
    source = _resolve(args.file)
    medicines = _read_any(source)
    target = _sqlite_path(args)
    print(f"source: {source} ({len(medicines)} record(s))")
    print(f"target: {target}")
    if args.dry_run:
        print("dry run: no database changes made")
        return 0
    repository = SqlMedicineRepository(target)
    written = repository.replace_all(medicines)
    print(f"imported {written} record(s) into SQLite")
    return 0


def command_export(args: argparse.Namespace) -> int:
    target = _resolve(args.output)
    medicines = get_repository().all()
    export_to_json(medicines, target)
    print(f"exported {len(medicines)} record(s) to {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate a JSON/CSV file (default: configured source)")
    validate.add_argument("file", nargs="?")
    validate.set_defaults(func=command_validate)

    stats = subparsers.add_parser("stats", help="Show counts for the active repository")
    stats.add_argument("--show-ids", action="store_true")
    stats.set_defaults(func=command_stats)

    migrate = subparsers.add_parser("migrate", help="Migrate the JSON source file into SQLite")
    migrate.add_argument("--source")
    migrate.add_argument("--sqlite-path")
    migrate.add_argument("--dry-run", action="store_true")
    migrate.set_defaults(func=command_migrate)

    importer = subparsers.add_parser("import", help="Replace SQLite contents from a JSON/CSV file")
    importer.add_argument("file")
    importer.add_argument("--sqlite-path")
    importer.add_argument("--dry-run", action="store_true")
    importer.set_defaults(func=command_import)

    exporter = subparsers.add_parser("export", help="Export the active repository to JSON")
    exporter.add_argument("output")
    exporter.set_defaults(func=command_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
