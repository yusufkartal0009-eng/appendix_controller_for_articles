"""Repeated runs of the same paper (#329): agreement on status, exit code, and metrics; log comparison."""

import json

import pytest

from scripts import report_numbers, run_stability
from src.config import PROJECT_ROOT


def _run(directory, status="COMPLETED", exit_code=0, metrics=None, limit="6g", cpus=2.0, log="hello\n"):
    directory.mkdir(parents=True)
    record = {"limits": {"memory_limit": limit, "cpus": cpus},
              "run": {"status": status, "exit_code": exit_code, "duration_seconds": 5.0, "peak_memory_bytes": 1024 ** 3}}
    (directory / "pilot_record.json").write_text(json.dumps(record), encoding="utf-8")
    (directory / "run_report.json").write_text(json.dumps({"metrics": metrics or {"rmse": 0.5}}), encoding="utf-8")
    (directory / "stdout.log").write_bytes(log.encode("utf-8"))


@pytest.fixture
def data(tmp_path):
    _run(tmp_path / "pilot3_runs" / "paper_003")
    _run(tmp_path / "memory_runs" / "paper_003", limit="14265m", log="hello\r\n")  # same text, other line endings
    _run(tmp_path / "pilot3_runs" / "paper_006", metrics={"auroc": 0.9})
    return tmp_path


def test_runs_with_the_same_status_exit_code_and_metrics_agree(data):
    group = run_stability.measure(data)["paper_003"]
    assert (group["same_status"], group["same_exit_code"], group["same_metrics"]) == (True, True, True)
    assert [r["label"] for r in group["runs"]] == ["Pilot 3", "memory re-run"]
    assert group["runs"][1]["memory_limit_gib"] == 13.93 and group["runs"][0]["cpus"] == 2.0


def test_line_endings_do_not_make_a_log_different(data):
    assert run_stability.measure(data)["paper_003"]["logs_identical_with_first"] == [{"files": 1, "identical": 1}]


def test_a_different_metric_status_or_log_is_reported(data):
    _run(data / "memory_runs" / "paper_003_run2", metrics={"rmse": 0.6}, log="other\n")
    group = run_stability.measure(data)["paper_003"]
    assert group["same_metrics"] is False and group["same_status"] is True
    assert group["logs_identical_with_first"][-1] == {"files": 1, "identical": 0}
    assert "metrics different" in run_stability.to_sentence({"paper_003": group})


def test_a_paper_with_a_single_run_is_not_listed(data):
    assert "paper_006" not in run_stability.measure(data)


def test_the_stored_runs_agree_and_the_report_block_is_in_sync():
    stored = run_stability.measure()
    assert {"paper_003", "paper_006"} <= set(stored)
    text = (PROJECT_ROOT / "docs" / "report" / "REPORT.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert report_numbers.mismatches(text) == []
    for name in ("syntheticcontrol", "stability", "goldexpansion"):
        assert f"<!-- numbers:{name}:start -->" in text
