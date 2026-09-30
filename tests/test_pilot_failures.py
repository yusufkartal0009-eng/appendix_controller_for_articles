"""Pilot failure categories follow docs/PILOT_WEEK2.md section 7 and are stored next to the run (P4, #125)."""

import json

import pytest
from sqlalchemy import create_engine, text

import scripts.categorize_pilot_failures as cpf
import scripts.load_pilot_runs as lpr
from src.database import ensure_failure_category_column


@pytest.mark.parametrize("line, expected", [
    ("ModuleNotFoundError: No module named 'torch'", ("MISSING_DEPENDENCY", None)),
    ("ImportError: cannot import name 'x' from 'y'", ("MISSING_DEPENDENCY", None)),
    ("RuntimeError: Found no NVIDIA driver on your system.", ("HARDWARE_GPU_REQUIRED", None)),
    ("AssertionError: Torch not compiled with CUDA enabled", ("HARDWARE_GPU_REQUIRED", None)),
    ("urllib.error.URLError: <urlopen error [Errno 101] Network is unreachable>", ("DATA_NOT_ACCESSIBLE", None)),
    ("FileNotFoundError: [Errno 2] No such file or directory: './data/forest/x.csv'", ("DATA_NOT_ACCESSIBLE", None)),
    ("FileNotFoundError: [Errno 2] No such file or directory: 'config/model.yaml'", ("OTHER", "MISSING_FILE")),
    ("OSError: [Errno 30] Read-only file system: '/workspace/repo/cache'", ("OTHER", "WRITE_TO_READ_ONLY_REPOSITORY")),
    ("ValueError: something else", ("OTHER", None)),
])
def test_exception_rules(line, expected):
    assert cpf.classify_exception(line) == expected


def _paper(tmp_path, report=None, stage=None, install_log=None, stderr=None):
    d = tmp_path / "paper_001"
    d.mkdir(parents=True)
    (d / "pilot_record.json").write_text(json.dumps(
        {"stage": stage or {"status": "STAGED", "target_script_exists": True}}))
    if report is not None:
        base = {"docker_used": True, "isolated": True, "dependency_install_status": "INSTALLED",
                "status": "FAILED", "exit_code": 1}
        base.update(report)
        (d / "run_report.json").write_text(json.dumps(base))
    if install_log is not None:
        (d / "install.log").write_text(install_log)
    if stderr is not None:
        (d / "stderr.log").write_text(stderr)
    return tmp_path


def test_install_failure_decides_first_and_quotes_the_first_error(tmp_path):
    runs = _paper(tmp_path, {"dependency_install_status": "FAILED"},
                  install_log="Looking in links\nERROR: No matching distribution found for torch==1.9.0\nERROR: later\n",
                  stderr="Traceback\nModuleNotFoundError: No module named 'catboost'\n")
    result = cpf.categorize_paper("paper_001", runs)
    assert (result["category"], result["phase"]) == ("MISSING_DEPENDENCY", "install")
    assert result["evidence"] == {"file": "install.log", "line_number": 2,
                                  "line": "ERROR: No matching distribution found for torch==1.9.0"}


@pytest.mark.parametrize("report, expected", [
    ({"status": "TIMEOUT", "exit_code": 137}, ("TIMEOUT", None)),
    ({"status": "OOM_KILLED", "exit_code": 137}, ("OTHER", "OUT_OF_MEMORY")),
    ({"dependency_install_status": "SKIPPED", "status": "COMPLETED", "exit_code": 0},
     (None, "RAN_WITHOUT_INSTALLED_DEPENDENCIES")),
])
def test_run_phase_statuses(tmp_path, report, expected):
    result = cpf.categorize_paper("paper_001", _paper(tmp_path, report, stderr=""))
    assert (result["category"], result["other_name"]) == expected
    assert result["pilot_success"] is False


def test_staging_failure_and_success(tmp_path):
    failed = cpf.categorize_paper("paper_001", _paper(tmp_path / "a", stage={"status": "FAILED", "error": "clone timed out"}))
    assert (failed["category"], failed["other_name"]) == ("OTHER", "STAGING_FAILED")
    ok = cpf.categorize_paper("paper_001", _paper(tmp_path / "b", {"status": "COMPLETED", "exit_code": 0}))
    assert ok["pilot_success"] is True and ok["category"] is None


def test_stored_categories_match_the_stored_logs():
    """failure_categories.json is regenerated from data/pilot_runs/, and every quoted line exists verbatim."""
    stored = cpf.PILOT_RUNS_DIR / "failure_categories.json"
    if not stored.exists():
        pytest.skip("no pilot results stored yet")
    result = cpf.categorize()
    assert json.loads(stored.read_text(encoding="utf-8")) == result
    for paper in result["papers"]:
        ev = paper["evidence"]
        if ev and ev["line_number"]:
            lines = (cpf.PILOT_RUNS_DIR / paper["paper_id"] / ev["file"]).read_text(encoding="utf-8").splitlines()
            assert lines[ev["line_number"] - 1] == ev["line"]
        if paper["category"] == "OTHER":
            assert paper["other_name"], f"{paper['paper_id']}: every OTHER must be named or explained"


def test_old_databases_get_the_failure_category_column(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE runs (run_id TEXT PRIMARY KEY, paper_id TEXT, status TEXT)"))
        conn.commit()
    assert ensure_failure_category_column(engine) is True
    assert ensure_failure_category_column(engine) is False  # already there
    with engine.connect() as conn:
        assert "failure_category" in [r[1] for r in conn.execute(text("PRAGMA table_info(runs)"))]


def test_loader_stores_the_category_next_to_each_run(tmp_path):
    if not (cpf.PILOT_RUNS_DIR / "failure_categories.json").exists():
        pytest.skip("no pilot results stored yet")
    db_url = f"sqlite:///{tmp_path / 'pilot.db'}"
    loaded = lpr.load(db_url)
    assert len(loaded) == 6
    lpr.load(db_url)  # re-running replaces the same rows
    with create_engine(db_url).connect() as conn:
        rows = conn.execute(text("SELECT paper_id, failure_category FROM runs WHERE run_id LIKE 'pilot-%'")).fetchall()
    stored = json.loads((cpf.PILOT_RUNS_DIR / "failure_categories.json").read_text(encoding="utf-8"))
    assert sorted(rows) == sorted((p["paper_id"], p["category"]) for p in stored["papers"])
