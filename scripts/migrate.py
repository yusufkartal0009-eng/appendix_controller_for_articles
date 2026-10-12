#!/usr/bin/env python3
"""Bring a Repro Radar SQLite database to the current schema without losing data (#12).

    python scripts/migrate.py status               # applied and pending migrations; changes nothing
    python scripts/migrate.py up --dry-run         # list what `up` would apply; changes nothing
    python scripts/migrate.py up                   # apply the pending migrations (a copy of the file is made first)
    python scripts/migrate.py up --no-backup

Each migration is one transaction, and running `up` again after it has succeeded does nothing. See
`src/migrations.py` for how to add a migration. The database is the one named by `--db-url`, else
`REPRO_RADAR_DB_URL`, else `data/repro_radar.db`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.database import get_engine
from src.migrations import MigrationError, status, upgrade


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Versioned schema migrations for the SQLite database.")
    parser.add_argument("--db-url", default=None, help="Database URL (default: REPRO_RADAR_DB_URL or data/repro_radar.db).")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show applied and pending migrations.")
    up = sub.add_parser("up", help="Apply the pending migrations.")
    up.add_argument("--dry-run", action="store_true", help="List the pending migrations and change nothing.")
    up.add_argument("--no-backup", action="store_true", help="Do not copy the database file before changing it.")
    args = parser.parse_args(argv)

    engine = get_engine(args.db_url) if args.db_url else get_engine()
    try:
        if args.command == "status":
            print(json.dumps(status(engine), indent=2))
            return 0
        result = upgrade(engine, backup=not args.no_backup, dry_run=args.dry_run)
    except MigrationError as exc:
        print(f"migration error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"applied": result.applied, "pending": result.pending,
                      "backup": str(result.backup_path) if result.backup_path else None}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
