"""Explaining the difference between two stored runs (#35, docs/DIAGNOSIS.md section 8)."""

import json
from pathlib import Path

import pytest

import scripts.diagnosis_comparisons as comparisons
from src.diagnosis.compare import (
    DIFFERENT_METRICS,
    IDENTICAL,
    LARGE,
    MODERATE,
    NOT_COMPARABLE,
    SAME_METRICS,
    SMALL,
    SMALL_SHIFT_METRICS,
    compare_runs,
    shift_size,
)
from src.diagnosis.prompts import check_neutral_language

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"


def make_run(root, name, metrics=None, seconds=100.0, cpus=2.0, memory="6g", seed=None, command="python x.py",
             status="COMPLETED", packages=None, commit="aaaaaaaa11", override=None):
    d = root / name
    d.mkdir(parents=True)
    record = {"paper_id": "p", "limits": {"cpus": cpus, "memory_limit": memory}, "container_command": command,
              "repro_radar_commit": commit, "python_version": "3.8"}
    if seed is not None:
        record["multi_seed"] = {"seed": seed}
    if override:
        record["memory_override"] = override
    report = {"status": status, "exit_code": 0 if status == "COMPLETED" else 1, "duration_seconds": seconds,
              "dependency_install_status": "INSTALLED", "image": "img", "meta": {"peak_memory_bytes": 1024**3},
              "installed_packages": [{"name": n, "version": v} for n, v in (packages or {"numpy": "1.0"}).items()]}
    if metrics is not None:
        report["metrics"] = metrics
    (d / "pilot_record.json").write_text(json.dumps(record))
    (d / "run_report.json").write_text(json.dumps(report))
    return d


@pytest.mark.parametrize("a, b, size", [
    (0.5, 0.5, IDENTICAL), (0.5, 0.5004, SMALL), (0.5, 0.51, MODERATE), (0.5, 0.6, LARGE), (0.0, 0.0, IDENTICAL),
])
def test_shift_size(a, b, size):
    assert shift_size(a, b) == size


def test_same_metrics_different_time_is_rule_r2(tmp_path):
    a = make_run(tmp_path, "a", {"acc": 0.9}, seconds=1500, cpus=2.0)
    b = make_run(tmp_path, "b", {"acc": 0.9}, seconds=450, cpus=8.0)
    report = compare_runs(a, b)
    text = report.to_markdown()
    assert report.metric_outcome == SAME_METRICS and report.differing_factors == ["CPUs"]
    assert "Rule R2, same metrics and a different time" in text
    assert "The records do not show which of them changed the time" in text
    assert "B was 3.33 times faster than A" in text
    assert not report.review_suggested


def test_identical_setup_is_rule_r1(tmp_path):
    report = compare_runs(make_run(tmp_path, "a", {"acc": 0.9}), make_run(tmp_path, "b", {"acc": 0.9}))
    assert "Rule R1" in report.to_markdown() and report.differing_factors == []


def test_different_metrics_with_a_different_seed_is_rule_r3_and_names_no_cause(tmp_path):
    a = make_run(tmp_path, "a", {"acc": 0.9}, seed=1, command="python x.py --seed 1")
    b = make_run(tmp_path, "b", {"acc": 0.7}, seed=2, command="python x.py --seed 2")
    report = compare_runs(a, b)
    text = report.to_markdown()
    assert report.metric_outcome == DIFFERENT_METRICS and report.review_suggested
    assert "Rule R3" in text and "Seed: 1 in A, 2 in B" in text
    assert "does not show whether this paper's seed controls these metrics" in text


def test_different_metrics_with_different_hardware_is_rule_r4(tmp_path):
    report = compare_runs(make_run(tmp_path, "a", {"acc": 0.9}, cpus=2.0), make_run(tmp_path, "b", {"acc": 0.905}, cpus=8.0))
    assert report.metric_outcome == DIFFERENT_METRICS
    assert "Rule R4" in report.to_markdown() and "CPUs" in report.to_markdown()


def test_a_small_shift_is_not_called_different_metrics(tmp_path):
    report = compare_runs(make_run(tmp_path, "a", {"acc": 0.9000}, cpus=2.0),
                          make_run(tmp_path, "b", {"acc": 0.9004}, cpus=8.0))
    assert report.metric_outcome == SMALL_SHIFT_METRICS and not report.review_suggested
    assert "a small shift" in report.to_markdown()


def test_different_metrics_without_a_recorded_factor_is_rule_r5(tmp_path):
    report = compare_runs(make_run(tmp_path, "a", {"acc": 0.9}), make_run(tmp_path, "b", {"acc": 0.5}))
    assert "Rule R5" in report.to_markdown() and "not explained by the stored files" in report.to_markdown()


def test_package_version_changes_are_listed(tmp_path):
    a = make_run(tmp_path, "a", {"acc": 0.9}, packages={"numpy": "1.0", "torch": "1.9"})
    b = make_run(tmp_path, "b", {"acc": 0.9}, packages={"numpy": "1.1", "torch": "1.9", "extra": "2"})
    text = compare_runs(a, b).to_markdown()
    assert "differ for 2 package(s)" in text and "numpy (1.0 / 1.1)" in text and "extra (absent / 2)" in text


def test_different_status_is_rule_r6_and_does_not_compare_metrics(tmp_path):
    report = compare_runs(make_run(tmp_path, "a", {"acc": 0.9}), make_run(tmp_path, "b", None, status="FAILED", seconds=3))
    assert report.metric_outcome == NOT_COMPARABLE
    text = report.to_markdown()
    assert "Rule R6" in text and "times faster" not in text


def test_a_value_missing_from_a_record_is_not_called_equal(tmp_path):
    a = make_run(tmp_path, "a", {"acc": 0.9})
    b = make_run(tmp_path, "b", {"acc": 0.9})
    (b / "run_report.json").write_text(json.dumps({"status": "COMPLETED", "exit_code": 0, "metrics": {"acc": 0.9}}))
    text = compare_runs(a, b).to_markdown()
    assert "Not recorded in at least one of the runs:" in text
    assert "Sandbox image" in text.split("Not recorded")[1]


def test_every_statement_has_fields_and_a_source_and_is_neutral():
    for name in ("memory_runs/paper_003", "cpu_runs/paper_003"):
        report = compare_runs(DATA / "pilot3_runs" / "paper_003", DATA / name)
        assert all(s.fields and s.source for s in report.statements)
        assert check_neutral_language(report.to_markdown()) == []


def test_stored_runs_of_paper_003_and_paper_006_give_same_metrics_and_a_different_time():
    for paper, other in (("paper_003", "cpu_runs/paper_003"), ("paper_006", "cpu_runs/paper_006")):
        report = compare_runs(DATA / "pilot3_runs" / paper, DATA / other)
        assert report.metric_outcome == SAME_METRICS
        assert "CPUs" in report.differing_factors
        assert "Rule R2" in report.to_markdown()


def test_the_stored_failed_and_completed_runs_of_paper_003_are_not_comparable():
    report = compare_runs(DATA / "pilot3_runs" / "paper_003", DATA / "pilot2_runs" / "paper_003")
    assert report.metric_outcome == NOT_COMPARABLE and "Paper settings of Pilot 3" in report.differing_factors


def test_the_synthetic_seed_runs_show_the_known_difference():
    free = compare_runs(DATA / "synthetic_seeds/synthetic_seed_free/seed_1",
                        DATA / "synthetic_seeds/synthetic_seed_free/seed_2")
    seeded = compare_runs(DATA / "synthetic_seeds/synthetic_seeded/seed_1",
                          DATA / "synthetic_seeds/synthetic_seeded/seed_2")
    assert free.metric_outcome == SAME_METRICS and seeded.metric_outcome == DIFFERENT_METRICS
    assert "Seed" in seeded.differing_factors


def test_the_comparisons_document_matches_the_stored_runs():
    assert comparisons.main(["--check"]) == 0
