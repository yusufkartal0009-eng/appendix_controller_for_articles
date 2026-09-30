#!/usr/bin/env python3
"""Load the stored Week 2 pilot runs, with their failure categories, into the database (P4, #125).

Reads data/pilot_runs/<paper_id>/ and data/pilot_runs/failure_categories.json and writes one `runs` row per paper,
with `failure_category` next to the run. Re-running replaces the same rows (the run IDs are stable).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlalchemy import text  # noqa: E402

from src.database import get_engine, get_session, init_db, seed_database  # noqa: E402
from src.models import RunORM  # noqa: E402

PILOT_RUNS_DIR = project_root / "data" / "pilot_runs"


def workflow_run_id(paper_dir: Path) -> str:
    env = (paper_dir / "runner_environment.txt").read_text(encoding="utf-8")
    match = re.search(r"/actions/runs/(\d+)", env)
    if not match:
        raise ValueError(f"No workflow run ID in {paper_dir / 'runner_environment.txt'}")
    return match.group(1)


def _text(path: Path) -> Optional[str]:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else None


def load(db_url: Optional[str] = None, runs_dir: Path = PILOT_RUNS_DIR) -> List[Dict[str, Any]]:
    engine = get_engine(db_url)
    init_db(engine)
    session = get_session(engine)
    categories = json.loads((runs_dir / "failure_categories.json").read_text(encoding="utf-8"))
    loaded: List[Dict[str, Any]] = []
    try:
        seed_database(session=session, overwrite=True)
        for item in categories["papers"]:
            paper_id = item["paper_id"]
            paper_dir = runs_dir / paper_id
            report = json.loads((paper_dir / "run_report.json").read_text(encoding="utf-8"))
            record = json.loads((paper_dir / "pilot_record.json").read_text(encoding="utf-8"))
            run_id = f"pilot-{workflow_run_id(paper_dir)}-{paper_id}"
            row = session.get(RunORM, run_id) or RunORM(run_id=run_id, paper_id=paper_id)
            row.status = report["status"]
            row.execution_time = report.get("duration_seconds")
            row.exit_code = report.get("exit_code")
            row.stdout = _text(paper_dir / "stdout.log")
            row.stderr = _text(paper_dir / "stderr.log")
            row.failure_category = item["category"]
            row.timestamp = datetime.fromisoformat(record["started_at"])
            session.merge(row)
            loaded.append({"run_id": run_id, "paper_id": paper_id, "status": row.status,
                           "failure_category": row.failure_category})
        session.commit()
    finally:
        session.close()
    return loaded


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load pilot runs with failure categories into the database.")
    parser.add_argument("--db-url", default=None, help="SQLAlchemy URL (default: the project database).")
    args = parser.parse_args(argv)
    load(args.db_url)
    engine = get_engine(args.db_url)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT run_id, paper_id, status, exit_code, failure_category FROM runs "
            "WHERE run_id LIKE 'pilot-%' ORDER BY paper_id"
        )).fetchall()
    print("run_id | paper_id | status | exit_code | failure_category")
    for r in rows:
        print(" | ".join(str(v) for v in r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
