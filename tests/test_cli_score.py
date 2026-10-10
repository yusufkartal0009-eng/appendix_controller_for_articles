"""`cli.py score` scores a real run and accepted claims; the simulation flags are labeled and never saved (#136)."""

import json
import sys

import pytest
from sqlalchemy import event

import cli
from scripts import run_pilot
from src.claim_store import import_extraction, record_review
from src.config import DATA_DIR, PROJECT_ROOT
from src.database import get_engine, get_session, init_db, seed_database
from src.models import ScoreORM

CLAIMS_DIR = DATA_DIR / "claims"


@pytest.fixture
def db(tmp_path):
    url = f"sqlite:///{tmp_path / 'score.db'}"
    engine = get_engine(url)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    init_db(engine)
    session = get_session(engine)
    seed_database(session=session)
    import_extraction(session, CLAIMS_DIR / "paper_003.json", CLAIMS_DIR / "guard_report.json", "A", PROJECT_ROOT)
    session.commit()
    yield url, session
    session.close()


def make_run(tmp_path, *, stage="STAGED", install="INSTALLED", exit_code=0, build=None, metrics=None, with_run=True):
    run_dir = tmp_path / "run" / "paper_003"
    run_dir.mkdir(parents=True)
    record = {"paper_id": "paper_003", "protocol": "docs/PILOT_2.md", "repro_radar_commit": "abc",
              "stage": {"status": stage, "requirements_files": ["requirements.txt"], "has_conda_env": False}}
    if build:
        record["build"] = {"status": build}
    if with_run:
        record["run"] = {"status": "COMPLETED" if exit_code == 0 else "FAILED", "exit_code": exit_code,
                         "dependency_install_status": install}
    (run_dir / "pilot_record.json").write_text(json.dumps(record))
    (run_dir / "run_report.json").write_text(json.dumps({"dependency_install_status": install, "metrics": metrics or {}}))
    (run_dir / "stdout.log").write_text("log\n")
    return run_dir


def score(monkeypatch, url, *args):
    monkeypatch.setattr(sys, "argv", ["cli.py", "score", *args, "--db-url", url])
    cli.main()


def saved_scores(session):
    session.expire_all()
    return session.query(ScoreORM).all()


def test_scoring_a_stored_run_uses_accepted_claims_and_the_run(db, tmp_path, monkeypatch, capsys):
    url, session = db
    record_review(session, "paper_003:ft_transformer_rmse", "accepted")
    record_review(session, "paper_003:resnet_rmse", "rejected")  # a rejected claim is not scored
    session.commit()
    run_dir = make_run(tmp_path, metrics={"ft_transformer_rmse": 0.46})
    score(monkeypatch, url, "paper_003", "--from-run", str(run_dir))
    out = capsys.readouterr().out
    assert "Accepted claims of this paper (accepted by a person): 1" in out
    assert "SIMULATION" not in out and "ft_transformer_rmse" in out and "MATCHED" in out
    assert "install=INSTALLED run=COMPLETED exit_code=0" in out
    (row,) = saved_scores(session)
    assert row.paper_id == "paper_003" and row.tier1_build == 100.0 and row.tier2_metrics > 0


def test_a_failed_install_scores_low_and_reproduces_nothing(db, tmp_path, monkeypatch, capsys):
    url, session = db
    record_review(session, "paper_003:ft_transformer_rmse", "accepted")
    session.commit()
    run_dir = make_run(tmp_path, install="FAILED", exit_code=1, metrics={"ft_transformer_rmse": 0.459})
    score(monkeypatch, url, "paper_003", "--from-run", str(run_dir))
    out = capsys.readouterr().out
    assert "install=FAILED" in out and "MATCHED" not in out
    (row,) = saved_scores(session)
    assert row.tier2_metrics == 0.0 and row.tier1_build < 100.0 and row.status_label == "Failed"


def test_a_failed_build_or_staging_is_a_failed_install(db, tmp_path, monkeypatch, capsys):
    url, session = db
    run_dir = make_run(tmp_path, build="FAILED", with_run=False)
    score(monkeypatch, url, "paper_003", "--from-run", str(run_dir))
    out = capsys.readouterr().out
    assert "build=FAILED" in out and "run=not started" in out
    assert "Dependencies installed successfully" not in out and "Target script invoked" not in out
    (row,) = saved_scores(session)
    assert row.tier1_build == 25.0  # the repository was staged; nothing else happened


def test_no_accepted_claim_says_the_baseline_is_not_a_measurement(db, tmp_path, monkeypatch, capsys):
    url, _ = db
    run_dir = make_run(tmp_path)
    score(monkeypatch, url, "paper_003", "--from-run", str(run_dir))
    out = capsys.readouterr().out
    assert "Accepted claims of this paper (accepted by a person): 0" in out
    assert "not a measurement" in out


def test_a_real_run_goes_through_the_pilot_driver_with_the_run_setup(db, tmp_path, monkeypatch, capsys):
    url, _ = db
    calls = {}

    def fake_run_paper(paper_id, staging_dir, pilot2=False, data_cache=None, record_root=None, **kwargs):
        calls.update(paper_id=paper_id, pilot2=pilot2, record_root=record_root)
        (record_root / paper_id).mkdir(parents=True)
        (record_root / paper_id / "pilot_record.json").write_text(json.dumps(
            {"stage": {"status": "FAILED"}, "protocol": "docs/PILOT_2.md"}))

    monkeypatch.setattr(run_pilot, "run_paper", fake_run_paper)
    monkeypatch.setattr(cli, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    score(monkeypatch, url, "paper_003")
    assert calls["pilot2"] is True and calls["record_root"] == tmp_path / "runs" / "score"
    assert "Running the paper in the Docker sandbox" in capsys.readouterr().out


def test_simulation_is_labeled_and_never_saved(db, monkeypatch, capsys):
    url, session = db
    for flag in ("--simulate", "--simulate-failure", "--simulate-divergence"):
        score(monkeypatch, url, "paper_003", flag)
        out = capsys.readouterr().out
        assert "SIMULATION FOR TESTING" in out and "not saved" in out
    assert saved_scores(session) == []


def test_unknown_paper_exits(db, monkeypatch):
    url, _ = db
    with pytest.raises(SystemExit):
        score(monkeypatch, url, "paper_999")
