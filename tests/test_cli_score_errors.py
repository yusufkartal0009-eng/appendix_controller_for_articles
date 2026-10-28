"""`cli.py score --from-run` with a missing or unreadable run folder is a message and exit code 1, not a traceback (#557)."""

import sys

import pytest
from sqlalchemy import event

import cli
from src.database import get_engine, get_session, init_db, seed_database


@pytest.fixture
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    engine = get_engine(url)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    init_db(engine)
    session = get_session(engine)
    seed_database(session=session)
    session.close()
    return url


def run_score(monkeypatch, url, *args):
    monkeypatch.setattr(sys, "argv", ["cli.py", "score", *args, "--db-url", url])
    cli.main()


def test_a_missing_run_folder_is_a_message_and_exit_1(monkeypatch, db_url, tmp_path, capsys):
    with pytest.raises(SystemExit) as exit_info:
        run_score(monkeypatch, db_url, "paper_003", "--from-run", str(tmp_path / "no_such_run"))
    assert exit_info.value.code == 1
    assert "Cannot read the run" in capsys.readouterr().out


@pytest.mark.parametrize("content", ["", "{not json", "[1, 2"])
def test_a_corrupt_run_record_is_a_message_and_exit_1(monkeypatch, db_url, tmp_path, capsys, content):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "pilot_record.json").write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit) as exit_info:
        run_score(monkeypatch, db_url, "paper_003", "--from-run", str(run_dir))
    assert exit_info.value.code == 1
    assert "Cannot read the run" in capsys.readouterr().out


def test_a_corrupt_run_report_is_a_message_and_exit_1(monkeypatch, db_url, tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "pilot_record.json").write_text("{}", encoding="utf-8")
    (run_dir / "run_report.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(SystemExit) as exit_info:
        run_score(monkeypatch, db_url, "paper_003", "--from-run", str(run_dir))
    assert exit_info.value.code == 1
    assert "Cannot read the run" in capsys.readouterr().out


def test_an_unknown_paper_is_exit_1(monkeypatch, db_url, tmp_path, capsys):
    with pytest.raises(SystemExit) as exit_info:
        run_score(monkeypatch, db_url, "paper_999", "--from-run", str(tmp_path))
    assert exit_info.value.code == 1
    assert "not found" in capsys.readouterr().out
