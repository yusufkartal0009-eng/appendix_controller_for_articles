"""Edge cases of scoring a stored run: empty records, odd metric values, missing parts, thresholds (#557)."""

import json
import math

import pytest

from src.score_run import load_run, run_facts, score_run, scored_run_row


def _record(**overrides):
    record = {"stage": {"status": "STAGED", "requirements_files": ["requirements.txt"]},
              "run": {"status": "COMPLETED", "exit_code": 0, "dependency_install_status": "INSTALLED"},
              "started_at": "2026-10-20T10:00:00+03:00", "protocol": "docs/PILOT_2.md", "repro_radar_commit": "abc"}
    record.update(overrides)
    return record


def test_an_empty_record_and_report_is_a_failed_run_with_no_facts_in_its_favor(tmp_path):
    facts = run_facts({}, {}, tmp_path)
    assert facts["clone_success"] is False and facts["deps_installed"] is False and facts["script_executed"] is False
    assert facts["exit_code"] is None and facts["reproduced_metrics"] == {}


def test_score_of_an_empty_record_is_failed_not_an_error(tmp_path):
    result = score_run("paper_003", "MIT", {}, {}, {}, tmp_path)
    assert result["breakdown"].status_label == "Failed"


@pytest.mark.parametrize("value,kept", [(0.5, True), (3, True), (0, True), (-2.5, True), (1e300, True), ("0.5", False), (None, False), ([0.5], False)])
def test_only_numbers_in_the_report_become_reproduced_metrics(tmp_path, value, kept):
    facts = run_facts(_record(), {"metrics": {"accuracy": value}}, tmp_path)
    assert ("accuracy" in facts["reproduced_metrics"]) is kept


def test_metrics_null_or_missing_in_the_report_is_no_metrics(tmp_path):
    assert run_facts(_record(), {"metrics": None}, tmp_path)["reproduced_metrics"] == {}
    assert run_facts(_record(), {}, tmp_path)["reproduced_metrics"] == {}


def test_a_failed_build_is_a_failed_install_and_skipped_is_not(tmp_path):
    assert run_facts(_record(build={"status": "BUILD_FAILED"}), {}, tmp_path)["deps_installed"] is False
    assert run_facts(_record(build={"status": "BUILT"}), {}, tmp_path)["deps_installed"] is True
    skipped = _record(run={"status": "COMPLETED", "exit_code": 0, "dependency_install_status": "SKIPPED"})
    assert run_facts(skipped, {}, tmp_path)["deps_installed"] is True
    failed = _record(run={"status": "FAILED", "exit_code": 1, "dependency_install_status": "FAILED"})
    assert run_facts(failed, {}, tmp_path)["deps_installed"] is False


def test_the_report_install_status_outranks_the_record(tmp_path):
    assert run_facts(_record(), {"dependency_install_status": "FAILED"}, tmp_path)["deps_installed"] is False


def test_a_missing_repository_directory_means_no_readme(tmp_path):
    assert run_facts(_record(), {}, tmp_path, repo_dir=tmp_path / "absent")["has_readme"] is False


def test_claim_exactly_on_the_tolerance_is_a_match_through_the_whole_path(tmp_path):
    """0.7 against 0.75 is a difference of 0.05 (float: 0.050000000000000044); it must count as inside the allowance."""
    result = score_run("paper_003", "MIT", {"accuracy": 0.7}, _record(), {"dependency_install_status": "INSTALLED", "metrics": {"accuracy": 0.75}}, tmp_path)
    assert result["breakdown"].tier2_metrics == 100.0


def test_a_nan_reproduced_metric_scores_zero_for_that_claim(tmp_path):
    report = {"dependency_install_status": "INSTALLED", "metrics": {"accuracy": math.nan}}
    result = score_run("paper_003", "MIT", {"accuracy": 0.7}, _record(), report, tmp_path)
    assert result["breakdown"].tier2_metrics == 0.0


def test_no_accepted_claim_is_the_neutral_baseline_and_says_so(tmp_path):
    result = score_run("paper_003", "MIT", {}, _record(), {"dependency_install_status": "INSTALLED", "metrics": {"accuracy": 0.9}}, tmp_path)
    assert result["breakdown"].tier2_metrics == 70.0
    assert any("neutral baseline" in note for note in result["diagnostics"]["tier2_notes"])
    assert result["breakdown"].status_label == "Needs Review"


def test_load_run_reads_the_record_and_tolerates_a_missing_report(tmp_path):
    (tmp_path / "pilot_record.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert load_run(tmp_path) == ({"a": 1}, {})
    with pytest.raises(FileNotFoundError):
        load_run(tmp_path / "absent")


def test_load_run_with_unicode_content(tmp_path):
    (tmp_path / "pilot_record.json").write_text(json.dumps({"note": "准确率 é"}, ensure_ascii=False), encoding="utf-8")
    assert load_run(tmp_path)[0]["note"] == "准确率 é"


def test_scored_run_row_without_logs_or_start_time(tmp_path):
    row = scored_run_row("paper_003", tmp_path, {}, {}, tmp_path.parent)
    assert row["status"] == "FAILED" and row["stdout"] is None and row["stderr"] is None and row["timestamp"] is None
    assert row["run_id"] == f"paper_003@{tmp_path.name}"


def test_scored_run_row_keeps_only_the_tail_of_a_huge_log_and_converts_the_start_to_utc(tmp_path):
    (tmp_path / "stdout.log").write_text("x" * 50000 + "END", encoding="utf-8")
    (tmp_path / "stderr.log").write_bytes("hata é\n".encode() + b"\xff\xfe")  # not valid UTF-8 at the end
    row = scored_run_row("paper_003", tmp_path, _record(), {"duration_seconds": 12.5}, tmp_path.parent)
    assert row["stdout"].endswith("END") and len(row["stdout"]) == 20000
    assert "hata" in row["stderr"]
    assert row["timestamp"].hour == 7 and row["timestamp"].tzinfo is None  # 10:00 at +03:00 is 07:00 UTC
    assert row["execution_time"] == 12.5 and row["exit_code"] == 0
