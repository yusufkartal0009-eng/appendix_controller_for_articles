#!/usr/bin/env python3
"""Build a dashboard database from the real stored runs (#496).

    python scripts/build_demo_db.py                  # writes data/dashboard_demo.db
    python -m src.web --db-url sqlite:///data/dashboard_demo.db

The project database (`data/repro_radar.db`) is never touched. For every paper that has at least one stored run
(`data/pilot_runs`, `pilot2_runs`, `pilot3_runs`, `pilot4_runs`, `memory_runs`, `cpu_runs`, `env_cache_runs`, and the synthetic
control), every stored run is scored with `src/score_run.py` against the claims a person accepted
(`data/claims/review_decisions.json`), exactly as `cli.py score --from-run` does it. The dashboard keeps one score per paper,
so the best record is stored: the highest total score, ties to the first run in the order of `RUN_ROOTS`. The run's
`run_id` names the directory it came from (`paper_003@pilot3_runs/paper_003`), and the score's summary names the setting and
how many stored runs there were, so it is clear which run and which setting a row shows.

Nothing here is simulated and no number is typed by hand. The staged repositories are not part of the repository, so the
README is counted as absent in Tier 4 (the summary says so). The synthetic control is a known-answer test, not a paper; its
title says so.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session

from src.claim_metric_map import load_claim_map
from src.claim_review import claims_for_scoring
from src.claim_store import restore_decisions
from src.database import get_engine, get_session, init_db, save_score
from src.models import PaperCreate, PaperORM, RunORM
from src.multi_seed import load_seed_metric_results
from src.score_run import load_run, score_run

DEFAULT_DATA = project_root / "data"
DEFAULT_OUT = DEFAULT_DATA / "dashboard_demo.db"
# (directory under data/, label of the setting); the order breaks ties between equally good runs
RUN_ROOTS = [
    ("pilot_runs", "Pilot 1"),
    ("pilot2_runs", "Pilot 2"),
    ("pilot3_runs", "Pilot 3"),
    ("pilot4_runs", "Pilot 4"),
    ("memory_runs", "memory run"),
    ("cpu_runs", "CPU run"),
    ("env_cache_runs/first_run", "env-cache run 1"),
    ("env_cache_runs/second_run", "env-cache run 2"),
]
SYNTHETIC_ID = "synthetic_control"
SYNTHETIC_RUN_DIRS = [("synthetic_control/run1/synthetic_control", "synthetic run 1"),
                      ("synthetic_control/run2/synthetic_control", "synthetic run 2")]
SYNTHETIC_CLAIMS = {"accuracy": 0.9}
SYNTHETIC_PAPER = {
    "paper_id": SYNTHETIC_ID, "title": "Synthetic control (a known-answer test, not a paper)", "year": 2026,
    "venue": "Repro Radar test", "repo_url": "https://github.com/yusufkartal0009-eng/appendix_controller_for_articles",
    "paper_url": None, "license": "MIT", "target_script": "train.py", "expected_claims": {}, "source_table_or_section": {}}
PAPER_FILES = ("seed_papers.json", "corpus_expansion/papers.json")
PAPER_ID = re.compile(r"^(paper_\d+)")
LOG_CHARS = 20000


def discover_runs(data_dir: Path) -> dict[str, list[tuple[str, Path]]]:
    """The stored run directories per paper: (setting label, directory). A directory counts when it has a pilot record."""
    found: dict[str, list[tuple[str, Path]]] = {}
    for rel, label in RUN_ROOTS:
        root = data_dir / rel
        if not root.is_dir():
            continue
        for folder in sorted(root.iterdir()):
            match = PAPER_ID.match(folder.name)
            if match and (folder / "pilot_record.json").is_file():
                found.setdefault(match.group(1), []).append((label, folder))
    for rel, label in SYNTHETIC_RUN_DIRS:
        if (data_dir / rel / "pilot_record.json").is_file():
            found.setdefault(SYNTHETIC_ID, []).append((label, data_dir / rel))
    return found


def read_papers(data_dir: Path) -> dict[str, dict[str, Any]]:
    papers: dict[str, dict[str, Any]] = {}
    for name in PAPER_FILES:
        path = data_dir / name
        if path.is_file():
            for item in json.loads(path.read_text(encoding="utf-8")):
                papers[item["paper_id"]] = item
    papers[SYNTHETIC_ID] = SYNTHETIC_PAPER
    return papers


def category_of(run_dir: Path, paper_id: str) -> str | None:
    """The failure category recorded for this run, from its own file or from the pilot's list, if there is one."""
    own = run_dir / "failure_category.json"
    if own.is_file():
        return json.loads(own.read_text(encoding="utf-8")).get("category")
    shared = run_dir.parent / "failure_categories.json"
    if shared.is_file():
        for item in json.loads(shared.read_text(encoding="utf-8")).get("papers", []):
            if item.get("paper_id") == paper_id:
                return item.get("category")
    return None


def started_at(record: dict[str, Any]) -> datetime | None:
    """When the run started according to its own record (UTC, stored without a zone), not when this database was built."""
    value = record.get("started_at")
    if not value:
        return None
    return datetime.fromisoformat(value).astimezone(UTC).replace(tzinfo=None)


def tail(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")[-LOG_CHARS:]


def score_all(paper_id: str, license_name: str, claims: dict[str, float], runs: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    scored = []
    for label, run_dir in runs:
        record, report = load_run(run_dir)
        result = score_run(paper_id, license_name, claims, record, report, run_dir, None, claim_map=load_claim_map(),
                           seed_metric_results=load_seed_metric_results(paper_id))
        scored.append({"label": label, "run_dir": run_dir, "record": record, "report": report, "result": result})
    return scored


def best_of(scored: list[dict[str, Any]]) -> dict[str, Any]:
    """The highest total score; max() keeps the first of equal ones, which is the order of RUN_ROOTS."""
    return max(scored, key=lambda s: s["result"]["breakdown"].total_score)


def store(session: Session, paper_id: str, data_dir: Path, item: dict[str, Any], count: int) -> dict[str, Any]:
    run_dir: Path = item["run_dir"]
    record, report = item["record"], item["report"]
    run = record.get("run") or {}
    rel = run_dir.relative_to(data_dir).as_posix()
    run_id = f"{paper_id}@{rel}"
    session.add(RunORM(run_id=run_id, paper_id=paper_id, status=run.get("status") or "FAILED",
                       execution_time=report.get("duration_seconds"), exit_code=run.get("exit_code"),
                       stdout=tail(run_dir / "stdout.log"), stderr=tail(run_dir / "stderr.log"),
                       failure_category=category_of(run_dir, paper_id), timestamp=started_at(record)))
    session.flush()
    bd = item["result"]["breakdown"]
    summary = (f"[demo database] {item['label']} (data/{rel}), the best of {count} stored run(s) of this paper. "
               f"Claims go through data/claim_metric_map.json as in cli.py score; Tier 4 is computed without the staged repository. {bd.summary}")
    save_score({"score_id": f"demo-{paper_id}", "paper_id": paper_id, "run_id": run_id, "tier1_build": bd.tier1_build,
                "tier2_metrics": bd.tier2_metrics, "tier3_stability": bd.tier3_stability, "tier4_artifacts": bd.tier4_artifacts,
                "total_score": bd.total_score, "status_label": bd.status_label, "summary": summary}, session=session)
    return {"paper_id": paper_id, "run_id": run_id, "label": item["label"], "stored_runs": count,
            "total": bd.total_score, "status": bd.status_label}


def build(data_dir: Path = DEFAULT_DATA, out: Path = DEFAULT_OUT) -> list[dict[str, Any]]:
    """Write the database `out` and return one summary row per paper. An existing `out` is replaced."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-journal", "-wal", "-shm"):
        Path(f"{out}{suffix}").unlink(missing_ok=True)
    engine = get_engine(f"sqlite:///{out.as_posix()}")
    init_db(engine)
    session = get_session(engine)
    rows: list[dict[str, Any]] = []
    try:
        runs_by_paper = discover_runs(data_dir)
        papers = read_papers(data_dir)
        included = {}
        for paper_id in sorted(runs_by_paper):
            if paper_id not in papers:
                continue
            validated = PaperCreate(**{k: v for k, v in papers[paper_id].items() if k in PaperCreate.model_fields})
            session.add(PaperORM(**{**validated.model_dump(), "expected_claims": "{}", "source_table_or_section": "{}"}))
            included[paper_id] = validated
        session.flush()
        restore_decisions(session, data_dir / "claims" / "review_decisions.json")  # needs the papers first
        session.commit()
        for paper_id, validated in included.items():
            claims = dict(SYNTHETIC_CLAIMS) if paper_id == SYNTHETIC_ID else claims_for_scoring(session, paper_id)
            scored = score_all(paper_id, validated.license, claims, runs_by_paper[paper_id])
            rows.append(store(session, paper_id, data_dir, best_of(scored), len(scored)))
        session.commit()
    finally:
        session.close()
        engine.dispose()
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="the sqlite file to write (default: data/dashboard_demo.db)")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA, help="where the stored runs and claims are (default: data/)")
    args = parser.parse_args(argv)
    rows = build(args.data_dir, args.out)
    print(f"Wrote {args.out}: {len(rows)} papers, one score each (the best stored run).")
    for r in rows:
        print(f"  {r['paper_id']:<18} {r['status']:<18} {r['total']:>6.2f}  {r['label']} of {r['stored_runs']} run(s)")
    try:
        shown = Path(args.out).resolve().relative_to(project_root)
    except ValueError:
        shown = Path(args.out).resolve()
    print(f"Start the dashboard: python -m src.web --db-url sqlite:///{shown.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
