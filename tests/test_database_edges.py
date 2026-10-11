"""Edges of src/database.py and scripts/load_pilot_runs.py that the main tests do not reach (#272)."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

import src.database as db
from src.models import PaperORM, RunORM, ScoreORM

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import load_pilot_runs as lpr


@pytest.fixture
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'edges.sqlite'}", future=True)
    db.init_db(eng)
    return eng


def _paper(**overrides):
    entry = {"paper_id": "paper_900", "title": "A test paper", "year": 2021, "venue": "V", "repo_url": "https://x/y",
             "paper_url": None, "license": "MIT", "target_script": "a.py", "expected_claims": {"acc": 0.9},
             "source_table_or_section": {"acc": "Table 1"}}
    entry.update(overrides)
    return entry


def test_default_engine_creates_the_database_folder_once(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "default.sqlite"
    monkeypatch.setattr(db, "DB_URL", f"sqlite:///{path}")
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", path)
    monkeypatch.setattr(db, "_engine", None)
    first = db.get_engine()
    assert path.parent.is_dir() and db.get_engine() is first


def test_init_db_can_drop_what_exists(engine):
    session = db.get_session(engine)
    session.add(PaperORM(paper_id="paper_900", title="T", year=2021, venue="V", repo_url="https://x", license="MIT",
                         target_script="a.py", expected_claims="{}", source_table_or_section="{}"))
    session.commit()
    session.close()
    db.init_db(engine, drop_existing=True)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM papers")).scalar() == 0


def test_without_schema_sql_the_orm_creates_the_tables(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'orm.sqlite'}", future=True)
    db.init_db(eng, schema_file=tmp_path / "missing.sql")
    with eng.connect() as conn:
        names = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))}
    assert {"papers", "runs", "claims", "scores"} <= names


def test_ensure_failure_category_column_only_touches_sqlite():
    other = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    assert db.ensure_failure_category_column(other) is False


def test_seed_file_must_exist(engine, tmp_path):
    session = db.get_session(engine)
    with pytest.raises(FileNotFoundError, match="Seed file not found"):
        db.seed_database(seed_file=tmp_path / "none.json", session=session)
    session.close()


def test_a_bad_seed_entry_rolls_the_whole_seed_back(engine, tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps([_paper(), _paper(paper_id="paper_901", title="x")]), encoding="utf-8")  # title too short
    session = db.get_session(engine)
    with pytest.raises(ValueError):
        db.seed_database(seed_file=seed, session=session)
    assert db.get_all_papers(session) == []
    session.close()


def test_seed_updates_only_with_overwrite(engine, tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps([_paper()]), encoding="utf-8")
    session = db.get_session(engine)
    assert db.seed_database(seed_file=seed, session=session) == 1
    seed.write_text(json.dumps([_paper(title="A renamed paper")]), encoding="utf-8")
    assert db.seed_database(seed_file=seed, session=session) == 0
    assert db.get_paper_by_id("paper_900", session).title == "A test paper"
    assert db.seed_database(seed_file=seed, session=session, overwrite=True) == 1
    assert db.get_paper_by_id("paper_900", session).title == "A renamed paper"
    session.close()


def test_readers_open_and_close_their_own_session(engine, tmp_path, monkeypatch):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps([_paper(), _paper(paper_id="paper_899", title="Another paper")]), encoding="utf-8")
    session = db.get_session(engine)
    db.seed_database(seed_file=seed, session=session)
    session.close()
    monkeypatch.setattr(db, "_engine", engine)
    monkeypatch.setattr(db, "_SessionFactory", None)
    assert [p.paper_id for p in db.get_all_papers()] == ["paper_899", "paper_900"]
    assert db.get_paper_by_id("paper_900").title == "A test paper"
    assert db.get_paper_by_id("nope") is None


def test_save_score_inserts_updates_and_rolls_back(engine, tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps([_paper()]), encoding="utf-8")
    session = db.get_session(engine)
    db.seed_database(seed_file=seed, session=session)
    score = {"score_id": "s1", "paper_id": "paper_900", "total_score": 50.0, "status_label": "Needs Review"}
    assert db.save_score(score, session).total_score == 50.0
    assert db.save_score({**score, "total_score": 80.0, "status_label": "Partially Verified"}, session).total_score == 80.0
    assert session.query(ScoreORM).count() == 1
    with pytest.raises(Exception):  # noqa: B017 - the database refuses a score without a status label
        db.save_score({"score_id": "s2", "paper_id": "paper_901", "total_score": 10.0}, session)
    assert session.query(ScoreORM).count() == 1  # rolled back, and the session is usable again
    session.close()


def _pilot_dir(root, paper_id="paper_900", environment="run: https://github.com/o/r/actions/runs/4242"):
    paper_dir = root / paper_id
    paper_dir.mkdir(parents=True)
    (paper_dir / "run_report.json").write_text(json.dumps(
        {"status": "FAILED", "duration_seconds": 12.5, "exit_code": 1}), encoding="utf-8")
    (paper_dir / "pilot_record.json").write_text(json.dumps({"started_at": "2026-09-30T10:00:00+00:00"}), encoding="utf-8")
    (paper_dir / "stdout.log").write_text("out", encoding="utf-8")
    if environment is not None:
        (paper_dir / "runner_environment.txt").write_text(environment, encoding="utf-8")
    (root / "failure_categories.json").write_text(json.dumps(
        {"papers": [{"paper_id": paper_id, "category": "MISSING_DEPENDENCY"}]}), encoding="utf-8")
    return paper_dir


def test_workflow_run_id_is_read_from_the_runner_environment(tmp_path):
    paper_dir = _pilot_dir(tmp_path)
    assert lpr.workflow_run_id(paper_dir) == "4242"
    (paper_dir / "runner_environment.txt").write_text("no id here", encoding="utf-8")
    with pytest.raises(ValueError, match="No workflow run ID"):
        lpr.workflow_run_id(paper_dir)


def test_loading_a_pilot_stores_status_logs_and_category(tmp_path):
    root = tmp_path / "pilot"
    _pilot_dir(root, paper_id="paper_003")
    url = f"sqlite:///{tmp_path / 'pilot.sqlite'}"
    loaded = lpr.load(url, root)
    assert loaded == [{"run_id": "pilot-4242-paper_003", "paper_id": "paper_003", "status": "FAILED",
                       "failure_category": "MISSING_DEPENDENCY"}]
    eng = create_engine(url, future=True)
    session = db.get_session(eng)
    row = session.get(RunORM, "pilot-4242-paper_003")
    assert (row.stdout, row.stderr, row.exit_code, row.execution_time) == ("out", None, 1, 12.5)
    session.close()
    assert lpr.load(url, root)[0]["run_id"] == "pilot-4242-paper_003"  # loading again updates, it does not duplicate


def test_command_line_prints_the_loaded_pilot_runs(tmp_path, capsys):
    url = f"sqlite:///{tmp_path / 'cli.sqlite'}"
    assert lpr.main(["--db-url", url]) == 0
    out = capsys.readouterr().out
    assert out.startswith("run_id | paper_id | status | exit_code | failure_category")
    assert out.count("pilot-") >= 1
