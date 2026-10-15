"""Scoring a run whose repository lists no requirements (install status SKIPPED): found by the synthetic control."""

from src.score_run import run_facts, score_run


def _run(status, exit_code=0, metrics=None):
    record = {"stage": {"status": "STAGED"}, "run": {"status": "COMPLETED" if exit_code == 0 else "FAILED", "exit_code": exit_code}}
    report = {"dependency_install_status": status, "metrics": metrics if metrics is not None else {"accuracy": 0.9}}
    return record, report


def test_a_run_with_nothing_to_install_counts_as_installed(tmp_path):
    record, report = _run("SKIPPED")
    assert run_facts(record, report, tmp_path)["deps_installed"] is True


def test_a_failed_install_is_still_a_failed_install(tmp_path):
    record, report = _run("FAILED")
    assert run_facts(record, report, tmp_path)["deps_installed"] is False


def test_a_true_claim_scores_high_and_a_false_claim_low_without_requirements(tmp_path):
    record, report = _run("SKIPPED")
    true = score_run("p", "MIT", {"accuracy": 0.9}, record, report, tmp_path)["breakdown"]
    false = score_run("p", "MIT", {"accuracy": 0.5}, record, report, tmp_path)["breakdown"]
    assert true.tier2_metrics == 100.0
    assert false.tier2_metrics < true.tier2_metrics
    assert true.total_score > false.total_score


def test_a_script_that_failed_reproduces_nothing_even_when_nothing_was_to_install(tmp_path):
    record, report = _run("SKIPPED", exit_code=1)
    result = score_run("p", "MIT", {"accuracy": 0.9}, record, report, tmp_path)
    assert result["breakdown"].tier2_metrics == 0.0
