"""The dashboard database is built from stored runs in an otherwise empty directory (#496)."""

import json
import sqlite3

from scripts import build_demo_db as bd


def write_run(root, rel, status, exit_code, metrics, install="INSTALLED"):
    folder = root / rel
    folder.mkdir(parents=True)
    record = {"stage": {"status": "STAGED", "requirements_files": ["requirements.txt"], "has_conda_env": False},
              "run": {"status": status, "exit_code": exit_code, "dependency_install_status": install}}
    (folder / "pilot_record.json").write_text(json.dumps(record))
    (folder / "run_report.json").write_text(json.dumps({"dependency_install_status": install, "metrics": metrics,
                                                        "duration_seconds": 12.5}))
    (folder / "stdout.log").write_text("line one\nline two\n")
    return folder


def make_data(root):
    paper = {"year": 2024, "venue": "Test", "repo_url": "https://example.invalid/r", "paper_url": None, "license": "MIT",
             "target_script": "run.py", "expected_claims": {}, "source_table_or_section": {}}
    (root / "seed_papers.json").write_text(json.dumps([{**paper, "paper_id": "paper_001", "title": "First test paper"},
                                                       {**paper, "paper_id": "paper_002", "title": "Second test paper"},
                                                       {**paper, "paper_id": "paper_009", "title": "Never run paper"}]))
    write_run(root, "pilot_runs/paper_001", "FAILED", 1, {}, install="FAILED")
    write_run(root, "pilot3_runs/paper_001", "COMPLETED", 0, {"accuracy": 0.9})
    write_run(root, "pilot3_runs/paper_002", "FAILED", 1, {}, install="FAILED")
    write_run(root, "synthetic_control/run1/synthetic_control", "COMPLETED", 0, {"accuracy": 0.9})


def test_an_empty_directory_gives_an_empty_database_with_the_schema(tmp_path):
    rows = bd.build(tmp_path / "data", tmp_path / "out" / "demo.db")
    assert rows == []
    with sqlite3.connect(tmp_path / "out" / "demo.db") as db:
        assert db.execute("select count(*) from papers").fetchone() == (0,)


def test_one_best_record_per_paper_and_the_run_names_its_directory(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    make_data(data)
    out = tmp_path / "demo.db"
    rows = bd.build(data, out)
    # three papers in the seed file, but a paper without a stored run is not listed; the synthetic control is added
    assert [r["paper_id"] for r in rows] == ["paper_001", "paper_002", "synthetic_control"]
    by_id = {r["paper_id"]: r for r in rows}
    assert by_id["paper_001"]["run_id"] == "paper_001@pilot3_runs/paper_001" and by_id["paper_001"]["stored_runs"] == 2
    assert by_id["paper_001"]["status"] != "Failed" and by_id["paper_002"]["status"] == "Failed"
    with sqlite3.connect(out) as db:
        assert db.execute("select count(*) from papers").fetchone() == (3,)
        assert db.execute("select count(*) from runs").fetchone() == (3,)
        assert db.execute("select count(*) from scores").fetchone() == (3,)
        summary, run_id = db.execute("select summary, run_id from scores where paper_id = 'paper_001'").fetchone()
        assert "Pilot 3" in summary and "best of 2" in summary and run_id == "paper_001@pilot3_runs/paper_001"
        assert db.execute("select stdout, execution_time from runs where paper_id = 'paper_001'").fetchone() == ("line one\nline two\n", 12.5)


def test_the_synthetic_control_is_labeled_and_scores_its_true_claim(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    make_data(data)
    bd.build(data, tmp_path / "demo.db")
    with sqlite3.connect(tmp_path / "demo.db") as db:
        title, tier2 = db.execute("select p.title, s.tier2_metrics from papers p join scores s using (paper_id) "
                                  "where paper_id = 'synthetic_control'").fetchone()
    assert "not a paper" in title and tier2 == 100.0


def test_building_again_replaces_the_file(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    make_data(data)
    out = tmp_path / "demo.db"
    bd.build(data, out)
    assert len(bd.build(data, out)) == 3


def test_the_project_database_is_not_the_default_output():
    assert bd.DEFAULT_OUT.name == "dashboard_demo.db" and bd.DEFAULT_OUT.name != "repro_radar.db"
