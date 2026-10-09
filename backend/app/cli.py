"""Command-line entry points. Run with: uv run python -m app.cli <command>."""

import argparse
import json
import sys
from pathlib import Path

from app.config import get_settings
from app.db import SessionLocal, make_engine
from app.migrate import upgrade_to_head
from app.seed import seed_properties


def cmd_migrate(_args: argparse.Namespace) -> int:
    direct = make_engine(get_settings().migration_database_url, pooled=False)
    try:
        upgrade_to_head(direct)
    finally:
        direct.dispose()
    with SessionLocal() as db:
        created = seed_properties(db)
    print(f"Migrated to head. Seeded {created} new properties.")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    from app.services.importer import import_file

    path = Path(args.path)
    with SessionLocal() as db:
        result = import_file(db, path.name, path.read_bytes(), default_source=args.source)
    print(json.dumps(result.as_dict(), indent=2, default=str))
    return 0 if result.ok else 1


def cmd_reclassify(_args: argparse.Namespace) -> int:
    from app.services.processing import reclassify_all

    with SessionLocal() as db:
        n = reclassify_all(db)
    print(f"Reclassified {n} reviews.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="Apply migrations and seed properties").set_defaults(
        func=cmd_migrate
    )

    p_import = sub.add_parser("import", help="Import reviews from a CSV or JSON file")
    p_import.add_argument("path")
    p_import.add_argument(
        "--source",
        choices=["import", "synthetic"],
        default="import",
        help="Source label for rows that do not declare one",
    )
    p_import.set_defaults(func=cmd_import)

    sub.add_parser(
        "reclassify", help="Recompute topics and sentiment for all reviews"
    ).set_defaults(func=cmd_reclassify)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
