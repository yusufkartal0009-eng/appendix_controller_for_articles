"""Suspicions of the bug hunt (docs/BUG_HUNT.md, #498) that were real.

Suspicion 4 was a strict `xfail` (the test states what a reader would expect); it passes since #513, when `cli.py score` began
to record the run it scored and the dashboard to show that run beside the score.
"""

import json

from sqlalchemy import select

from src.models import RunORM, ScoreORM
from src.web.pages import render_detail
from tests.test_cli_score import (  # noqa: F401  (the fixture and helpers of the score tests)
    db,
    make_run,
    score,
)


def test_the_run_shown_beside_a_score_is_the_run_that_was_scored(db, tmp_path, monkeypatch):  # noqa: F811
    url, session = db
    session.add(RunORM(run_id="old-pilot-1", paper_id="paper_003", status="FAILED", exit_code=1))
    session.commit()
    run_dir = make_run(tmp_path, metrics={"rmse": 0.46})
    score(monkeypatch, url, "paper_003", "--from-run", str(run_dir))
    session.expire_all()
    stored = session.execute(select(ScoreORM).where(ScoreORM.paper_id == "paper_003")).scalar_one()
    page = render_detail(session.get_bind(), "paper_003")
    # a reader expects the score row to name its run, and the page not to show a FAILED run next to it (the word FAILED also
    # occurs in the page's style sheet, so the run's own badge and id are looked for)
    assert stored.run_id is not None
    assert "<span class='badge FAILED'>" not in page and "old-pilot-1" not in page


def test_the_page_names_the_scored_run_and_its_start_date(db, tmp_path, monkeypatch):  # noqa: F811
    url, session = db
    run_dir = make_run(tmp_path, metrics={"rmse": 0.46})
    record = json.loads((run_dir / "pilot_record.json").read_text())
    record["started_at"] = "2026-10-16T12:00:00+03:00"
    (run_dir / "pilot_record.json").write_text(json.dumps(record))
    score(monkeypatch, url, "paper_003", "--from-run", str(run_dir))
    session.expire_all()
    stored = session.execute(select(ScoreORM).where(ScoreORM.paper_id == "paper_003")).scalar_one()
    assert stored.run_id == "paper_003@paper_003"  # a directory outside the project is named by its own name
    run = session.get(RunORM, stored.run_id)
    assert run.status == "COMPLETED" and run.timestamp.isoformat() == "2026-10-16T09:00:00"  # UTC, from the run's own record
    page = render_detail(session.get_bind(), "paper_003")
    assert "Run of this score" in page and stored.run_id in page and "<dt>Started</dt><dd>2026-10-16 09:00 UTC</dd>" in page


def test_a_score_without_a_run_falls_back_to_the_latest_run(db):  # noqa: F811
    _, session = db
    session.add(RunORM(run_id="old-pilot-1", paper_id="paper_003", status="FAILED", exit_code=1))
    session.commit()
    page = render_detail(session.get_bind(), "paper_003")
    assert "Latest run" in page and "old-pilot-1" in page and "<dt>Started</dt>" in page


def test_scoring_twice_keeps_one_run_row(db, tmp_path, monkeypatch):  # noqa: F811
    url, session = db
    run_dir = make_run(tmp_path, metrics={"rmse": 0.46})
    score(monkeypatch, url, "paper_003", "--from-run", str(run_dir))
    score(monkeypatch, url, "paper_003", "--from-run", str(run_dir))
    session.expire_all()
    assert session.query(RunORM).filter(RunORM.paper_id == "paper_003").count() == 1


def test_the_run_of_a_stored_pilot_is_named_by_its_directory_inside_the_project():
    from pathlib import Path

    from src.score_run import load_run, scored_run_row

    root = Path(__file__).resolve().parent.parent
    run_dir = root / "data" / "pilot3_runs" / "paper_003"
    record, report = load_run(run_dir)
    row = scored_run_row("paper_003", run_dir, record, report, root)
    assert row["run_id"] == "paper_003@data/pilot3_runs/paper_003" and row["status"] == "COMPLETED"
    assert row["timestamp"] is not None and "rmse = 0.473" in row["stdout"]
