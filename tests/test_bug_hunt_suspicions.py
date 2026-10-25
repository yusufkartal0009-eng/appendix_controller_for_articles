"""Suspicions of the bug hunt (docs/BUG_HUNT.md, #498) that are real but need a decision of the owner before a fix.

`xfail(strict=True)`: the test states what a reader would expect; it fails today, and fails the suite loudly (XPASS) the day
the behavior changes, so the document has to be updated then.
"""

import pytest
from sqlalchemy import select

from src.models import RunORM, ScoreORM
from src.web.pages import render_detail
from tests.test_cli_score import (  # noqa: F401  (the fixture and helpers of the score tests)
    db,
    make_run,
    score,
)


@pytest.mark.xfail(strict=True, reason="suspicion 4: the score of a stored run is not linked to a run row; owner decision (UI)")
def test_the_run_shown_beside_a_score_is_the_run_that_was_scored(db, tmp_path, monkeypatch):  # noqa: F811
    url, session = db
    session.add(RunORM(run_id="old-pilot-1", paper_id="paper_003", status="FAILED", exit_code=1))
    session.commit()
    run_dir = make_run(tmp_path, metrics={"rmse": 0.46})
    score(monkeypatch, url, "paper_003", "--from-run", str(run_dir))
    session.expire_all()
    stored = session.execute(select(ScoreORM).where(ScoreORM.paper_id == "paper_003")).scalar_one()
    page = render_detail(session.get_bind(), "paper_003")
    # a reader expects the score row to name its run, and the page not to show a FAILED run next to it
    assert stored.run_id is not None
    assert "FAILED" not in page
