"""Edge cases of the command line: empty database, unknown ids, Unicode, stored-run diagnosis, bad backends (#557)."""

import json
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import event

import cli
from src.config import PROJECT_ROOT
from src.database import get_engine, get_session, init_db, seed_database


def run_cli(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["cli.py", *argv])
    cli.main()


def paper(**overrides):
    data = {"paper_id": "paper_x", "title": "A very long title about reproducibility " * 3, "year": 2026, "venue": "ICLR",
            "license": "MIT", "target_script": "train.py", "repo_url": "https://example.org/r", "paper_url": None,
            "get_expected_claims_dict": lambda: {"accuracy": 0.9}}
    data.update(overrides)
    return SimpleNamespace(**data)


def test_list_papers_on_an_empty_database_names_the_command_to_run(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_all_papers", list)
    run_cli(monkeypatch, "list-papers")
    assert "Run 'python cli.py init-db' first." in capsys.readouterr().out


def test_list_papers_cuts_a_long_title_and_counts_claims(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_all_papers", lambda: [paper(), paper(paper_id="paper_é", title="Título 准确率", get_expected_claims_dict=dict)])
    run_cli(monkeypatch, "list-papers")
    out = capsys.readouterr().out
    assert "..." in out and "Título 准确率" in out and "Total Papers: 2" in out


def test_inspect_an_unknown_paper_exits_with_1(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_paper_by_id", lambda paper_id: None)
    with pytest.raises(SystemExit) as exit_info:
        run_cli(monkeypatch, "inspect", "paper_999")
    assert exit_info.value.code == 1
    assert "paper_999" in capsys.readouterr().out


def test_inspect_shows_the_claims_and_a_missing_paper_url(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_paper_by_id", lambda paper_id: paper())
    run_cli(monkeypatch, "inspect", "paper_x")
    out = capsys.readouterr().out
    assert "accuracy: 0.9" in out and "Paper URL    : N/A" in out


def test_a_command_is_required(monkeypatch):
    with pytest.raises(SystemExit) as exit_info:
        run_cli(monkeypatch)
    assert exit_info.value.code == 2


def test_an_unknown_command_is_refused(monkeypatch):
    with pytest.raises(SystemExit) as exit_info:
        run_cli(monkeypatch, "launch")
    assert exit_info.value.code == 2


def test_diagnose_a_missing_folder_exits_with_1(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit) as exit_info:
        run_cli(monkeypatch, "diagnose", str(tmp_path / "absent"))
    assert exit_info.value.code == 1
    assert "Error" in capsys.readouterr().err


def test_diagnose_a_stored_run_as_json_is_valid_json(monkeypatch, capsys):
    run_cli(monkeypatch, "diagnose", str(PROJECT_ROOT / "data" / "pilot3_runs" / "paper_004"), "--json")
    assert isinstance(json.loads(capsys.readouterr().out), dict)


def test_diagnose_explain_with_an_unknown_backend_exits_with_1(monkeypatch, capsys):
    monkeypatch.setenv("REPRO_RADAR_DIAGNOSIS_BACKEND", "no_such_backend")
    with pytest.raises(SystemExit) as exit_info:
        run_cli(monkeypatch, "diagnose", str(PROJECT_ROOT / "data" / "pilot3_runs" / "paper_004"), "--explain")
    assert exit_info.value.code == 1
    assert "Error" in capsys.readouterr().err


def test_review_claims_list_on_a_database_without_claims(monkeypatch, tmp_path, capsys):
    url = f"sqlite:///{tmp_path / 'empty.db'}"
    engine = get_engine(url)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    init_db(engine)
    session = get_session(engine)
    seed_database(session=session)
    session.close()
    run_cli(monkeypatch, "review-claims", "--list", "--db-url", url)
    assert "No extracted claims" in capsys.readouterr().out


def test_score_a_simulation_is_labeled_and_not_saved(monkeypatch, tmp_path, capsys):
    url = f"sqlite:///{tmp_path / 'sim.db'}"
    engine = get_engine(url)
    init_db(engine)
    session = get_session(engine)
    seed_database(session=session)
    session.close()
    run_cli(monkeypatch, "score", "paper_003", "--simulate-failure", "--db-url", url)
    out = capsys.readouterr().out
    assert "SIMULATION FOR TESTING" in out and "not saved" in out
