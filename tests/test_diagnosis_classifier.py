"""The rule-based failure classifier of the diagnosis layer (#32, docs/DIAGNOSIS.md section 5)."""

import json
from pathlib import Path

import pytest

import scripts.categorize_pilot_failures as cpf
from src.diagnosis.classifier import CATEGORIES, classify_log_text, classify_run

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"


def make_run(root, name, report=None, stage=None, install_log=None, stderr=None):
    d = root / name
    d.mkdir(parents=True)
    (d / "pilot_record.json").write_text(json.dumps({"stage": stage or {"status": "STAGED", "target_script_exists": True}}))
    if report is not None:
        base = {"docker_used": True, "isolated": True, "dependency_install_status": "INSTALLED",
                "status": "FAILED", "exit_code": 1}
        (d / "run_report.json").write_text(json.dumps({**base, **report}))
    if install_log is not None:
        (d / "install.log").write_text(install_log)
    if stderr is not None:
        (d / "stderr.log").write_text(stderr)
    return d


def test_the_script_and_the_classifier_share_one_rule_set():
    assert cpf.categorize_paper is __import__("src.diagnosis.classifier", fromlist=["x"]).categorize_paper
    assert cpf.CATEGORIES is CATEGORIES


@pytest.mark.parametrize("report, stderr, label, phase", [
    ({"status": "OOM_KILLED", "exit_code": 137}, "", "OUT_OF_MEMORY", "run"),
    ({"status": "TIMEOUT", "exit_code": 137}, "", "TIMEOUT", "run"),
    ({}, "Traceback\nModuleNotFoundError: No module named 'delu'\n", "MISSING_DEPENDENCY", "run"),
    ({}, "Traceback\nFileNotFoundError: [Errno 2] No such file or directory: 'data/x.csv'\n", "DATA_NOT_ACCESSIBLE", "run"),
    ({}, "RuntimeError: Found no NVIDIA driver on your system\n", "HARDWARE_GPU_REQUIRED", "run"),
    ({}, "OSError: [Errno 30] Read-only file system: '/workspace/repo/x'\n", "WRITE_TO_READ_ONLY_REPOSITORY", "run"),
    ({}, "ValueError: shape mismatch\n", "OTHER", "run"),
])
def test_run_phase_failures(tmp_path, report, stderr, label, phase):
    result = classify_run(make_run(tmp_path, "r", report, stderr=stderr))
    assert (result.label, result.phase) == (label, phase)
    assert result.pilot_success is False


def test_the_deciding_line_is_quoted_with_file_and_line_number(tmp_path):
    run = make_run(tmp_path, "r", {}, stderr="Traceback (most recent call last):\n  File x\nModuleNotFoundError: No module named 'delu'\n")
    assert classify_run(run).evidence == {"file": "stderr.log", "line_number": 3,
                                          "line": "ModuleNotFoundError: No module named 'delu'"}


def test_install_failure_decides_before_the_run(tmp_path):
    run = make_run(tmp_path, "r", {"dependency_install_status": "FAILED"},
                   install_log="x\nERROR: No matching distribution found for torch==1.9.0\n",
                   stderr="ModuleNotFoundError: No module named 'q'\n")
    result = classify_run(run)
    assert (result.category, result.phase, result.evidence["file"]) == ("MISSING_DEPENDENCY", "install", "install.log")


def test_staging_failure_and_a_clean_run(tmp_path):
    staged = classify_run(make_run(tmp_path, "a", stage={"status": "FAILED", "error": "clone timed out"}))
    assert (staged.label, staged.phase) == ("STAGING_FAILED", "stage")
    ok = classify_run(make_run(tmp_path, "b", {"status": "COMPLETED", "exit_code": 0}))
    assert ok.pilot_success is True and ok.category is None and ok.label is None


def test_a_folder_without_a_record_is_reported_as_not_run(tmp_path):
    (tmp_path / "empty").mkdir()
    assert classify_run(tmp_path / "empty").label == "NOT_RUN"


def test_a_missing_folder_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        classify_run(tmp_path / "nope")


def test_classify_log_text():
    assert classify_log_text("a\nModuleNotFoundError: No module named 'x'\n\n") == (
        "MISSING_DEPENDENCY", None, 2, "ModuleNotFoundError: No module named 'x'")
    assert classify_log_text("  \n") is None


@pytest.mark.parametrize("pilot", ["pilot_runs", "pilot2_runs", "pilot3_runs"])
def test_it_agrees_with_the_stored_categories_of_pilots_1_to_3(pilot):
    stored = json.loads((DATA / pilot / "failure_categories.json").read_text(encoding="utf-8"))
    for entry in stored["papers"]:
        got = classify_run(DATA / pilot / entry["paper_id"])
        assert (got.category, got.other_name, got.phase) == (entry["category"], entry["other_name"], entry["phase"])
        assert got.evidence == entry["evidence"]


def test_it_agrees_with_the_stored_categories_of_pilot_4():
    for folder in sorted((DATA / "pilot4_runs").glob("paper_*")):
        stored = json.loads((folder / "failure_category.json").read_text(encoding="utf-8"))
        got = classify_run(folder)
        assert (got.category, got.other_name, got.phase) == (stored["category"], stored["other_name"], stored["phase"])
