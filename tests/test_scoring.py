"""Unit tests for Repro Radar 4-tier reproducibility scoring rubric and AI decision layer."""

from src.config import (
    STATUS_FAILED,
    STATUS_NEEDS_REVIEW,
    STATUS_VERIFIED,
)
from src.scoring import (
    ReproducibilityScorer,
    Tier1BuildEvaluator,
    Tier2MetricsEvaluator,
    Tier3StabilityEvaluator,
    Tier4ArtifactsEvaluator,
)


def test_tier1_build_evaluator_all_pass():
    """Test full score when clone, deps, script, and zero exit code succeed."""
    score, notes = Tier1BuildEvaluator.evaluate(
        clone_success=True,
        deps_installed=True,
        script_executed=True,
        exit_code=0,
    )
    assert score == 100.0
    assert len(notes) == 4


def test_tier1_build_evaluator_partial_fail():
    """Test reduced score on dependency or exit code failure."""
    score, _notes = Tier1BuildEvaluator.evaluate(
        clone_success=True,
        deps_installed=True,
        script_executed=True,
        exit_code=1,  # Runtime error
    )
    assert score == 75.0


def test_tier2_metrics_evaluator_perfect_match():
    """Test 100% score when reproduced metrics are within 5% tolerance."""
    claimed = {"acc": 0.85, "f1": 0.80}
    reproduced = {"acc": 0.852, "f1": 0.798}  # ~0.25% error
    score, claim_results, _notes = Tier2MetricsEvaluator.evaluate(claimed, reproduced, tolerance=0.05)
    assert score == 100.0
    assert claim_results["acc"]["matches"] is True
    assert claim_results["f1"]["matches"] is True


def test_tier2_metrics_evaluator_partial_match():
    """Test partial credit when metric is within 2x tolerance."""
    claimed = {"acc": 0.80}
    reproduced = {"acc": 0.86}  # 7.5% error -> above 5% but below 10%
    score, claim_results, _notes = Tier2MetricsEvaluator.evaluate(claimed, reproduced, tolerance=0.05)
    assert score == 50.0
    assert claim_results["acc"]["matches"] is False


def test_tier2_metrics_evaluator_diverged():
    """Test 0% metric score when values diverge significantly."""
    claimed = {"acc": 0.90}
    reproduced = {"acc": 0.50}  # Diverged
    score, _claim_results, _notes = Tier2MetricsEvaluator.evaluate(claimed, reproduced, tolerance=0.05)
    assert score == 0.0


def test_tier3_stability_multi_seed():
    """Test stability score calculation with multiple seeds."""
    # Low variance (CV < 2%)
    seeds_stable = [0.842, 0.841, 0.843]
    score_stable, _ = Tier3StabilityEvaluator.evaluate(seeds_stable)
    assert score_stable == 100.0

    # High variance (CV > 10%)
    seeds_volatile = [0.90, 0.60, 0.75]
    score_volatile, _ = Tier3StabilityEvaluator.evaluate(seeds_volatile)
    assert score_volatile == 40.0


def test_tier4_artifacts_evaluator():
    """Test documentation, license, and artifacts scoring."""
    # Permissive license + requirements + readme + artifacts
    score_full, _ = Tier4ArtifactsEvaluator.evaluate(
        license_name="MIT",
        has_environment_file=True,
        has_readme=True,
        has_saved_artifacts=True,
    )
    assert score_full == 100.0

    # Missing environment file and proprietary license
    score_low, _ = Tier4ArtifactsEvaluator.evaluate(
        license_name="Proprietary",
        has_environment_file=False,
        has_readme=True,
        has_saved_artifacts=True,
    )
    assert score_low == 40.0


def test_composite_score_status_verified():
    """Test composite calculation leading to 'Verified'."""
    total, status, summary = ReproducibilityScorer.calculate_composite_score(
        tier1=100.0,
        tier2=95.0,
        tier3=90.0,
        tier4=100.0,
    )
    assert total >= 85.0
    assert status == STATUS_VERIFIED
    assert "Verified" in summary


def test_composite_score_status_needs_review():
    """Test composite calculation leading to 'Needs Review' when build works but metrics diverge."""
    _total, status, _summary = ReproducibilityScorer.calculate_composite_score(
        tier1=100.0,
        tier2=30.0,  # Diverged metrics
        tier3=75.0,
        tier4=100.0,
    )
    assert status == STATUS_NEEDS_REVIEW
    assert "Needs Review" in status


def test_composite_score_status_failed():
    """Test composite calculation leading to 'Failed' on build failure."""
    _total, status, _summary = ReproducibilityScorer.calculate_composite_score(
        tier1=25.0,  # Build fail
        tier2=0.0,
        tier3=0.0,
        tier4=30.0,
        tier1_exit_code=1,
    )
    assert status == STATUS_FAILED
    assert "Failed" in status


def test_tier2_latency_metric_avoids_absolute_tolerance_trap():
    """Test that time/latency metrics enforce relative tolerance and avoid the absolute tolerance trap."""
    # 0.02s taking 0.06s is a 200% slowdown. Absolute diff is 0.04 <= 0.05,
    # but for latency metrics this must NOT match.
    claimed = {"inference_latency_sec": 0.02}
    reproduced = {"inference_latency_sec": 0.06}
    score, results, _notes = Tier2MetricsEvaluator.evaluate(claimed, reproduced, tolerance=0.05)
    assert score == 0.0
    assert results["inference_latency_sec"]["matches"] is False


def test_tier3_stability_zero_on_failed_execution():
    """Test that Tier 3 returns 0.0 if execution did not succeed or build failed."""
    score, notes = Tier3StabilityEvaluator.evaluate(
        seed_results=[0.842, 0.844, 0.841],
        execution_succeeded=False,
    )
    assert score == 0.0
    assert "Execution failed" in notes[0]


def test_tier4_detect_filesystem_artifacts(tmp_path):
    """Test dynamic detection of environment file, README, and artifacts via filesystem checks."""
    # Empty directory
    has_env, has_readme, has_art = Tier4ArtifactsEvaluator.detect_filesystem_artifacts(repo_dir=tmp_path)
    assert has_env is False
    assert has_readme is False
    assert has_art is False

    # Directory with requirements.txt and README.md
    (tmp_path / "requirements.txt").write_text("torch>=2.0\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    (run_dir / "metrics.json").write_text("{}", encoding="utf-8")

    has_env, has_readme, has_art = Tier4ArtifactsEvaluator.detect_filesystem_artifacts(
        repo_dir=tmp_path,
        run_dir=run_dir,
    )
    assert has_env is True
    assert has_readme is True
    assert has_art is True


def test_evaluate_paper_run_failed_build_zeros_tier2_and_tier3():
    """Test that a build failure in evaluate_paper_run zeroes downstream metric and stability tiers."""
    eval_res = ReproducibilityScorer.evaluate_paper_run(
        paper_id="paper_001",
        clone_success=True,
        deps_installed=False,
        script_executed=False,
        exit_code=1,
        claimed_metrics={"auc": 0.85},
        reproduced_metrics={"auc": 0.85},
        license_name="MIT",
        seed_results=[0.85, 0.85],
    )
    bd = eval_res["breakdown"]
    assert bd.tier2_metrics == 0.0
    assert bd.tier3_stability == 0.0
    assert bd.status_label == STATUS_FAILED


def _evaluate(claimed, reproduced):
    return ReproducibilityScorer.evaluate_paper_run(
        paper_id="paper_901", clone_success=True, deps_installed=True, script_executed=True, exit_code=0,
        claimed_metrics=claimed, reproduced_metrics=reproduced, license_name="MIT",
    )["breakdown"]


def test_summary_says_nothing_was_compared_when_no_claim_is_found_in_the_output():
    """#317: Tier 2 = 0 because the claims were not found must not be reported as a divergence."""
    for reproduced in ({"other_metric": 0.9}, {}):
        breakdown = _evaluate({"arcene_auroc": 0.8, "xgboost_arcene_auroc": 0.85}, reproduced)
        assert breakdown.tier2_metrics == 0.0
        assert "claimed metrics not found in the output (nothing was compared)" in breakdown.summary
        assert "divergence" not in breakdown.summary


def test_summary_keeps_divergence_for_claims_that_were_found_and_differ():
    breakdown = _evaluate({"auroc": 0.8}, {"auroc": 0.5})
    assert breakdown.tier2_metrics == 0.0
    assert "significant divergence" in breakdown.summary
    assert "nothing was compared" not in breakdown.summary


# A label must rest on evidence: with nothing compared, Tier 2 is a neutral baseline (#540)
def _clean_run(claimed, reproduced, **kwargs):
    return ReproducibilityScorer.evaluate_paper_run(
        paper_id="p", clone_success=True, deps_installed=True, script_executed=True, exit_code=0,
        claimed_metrics=claimed, reproduced_metrics=reproduced, license_name="MIT", **kwargs)["breakdown"]


def test_a_clean_run_with_no_claim_is_needs_review_not_partially_verified():
    breakdown = _clean_run({}, {"rmse": 0.47})
    assert breakdown.tier2_metrics == 70.0
    assert breakdown.status_label == "Needs Review"
    assert "no accepted claim could be compared" in breakdown.summary


def test_a_clean_run_whose_claims_are_not_in_the_output_keeps_its_old_wording():
    breakdown = _clean_run({"auroc": 0.9}, {"rmse": 0.47})
    assert breakdown.status_label == "Needs Review" and "nothing was compared" in breakdown.summary


def test_a_compared_claim_within_tolerance_is_still_verified():
    breakdown = _clean_run({"rmse": 0.459}, {"rmse": 0.473}, tolerance=0.05)
    assert breakdown.tier2_metrics == 100.0 and breakdown.status_label == "Verified"


def test_a_failed_run_with_no_claim_stays_failed():
    result = ReproducibilityScorer.evaluate_paper_run(
        paper_id="p", clone_success=True, deps_installed=True, script_executed=True, exit_code=1,
        claimed_metrics={}, reproduced_metrics={}, license_name="MIT")
    assert result["breakdown"].status_label == "Failed"


def test_the_composite_function_keeps_its_old_behavior_when_the_new_flag_is_not_given():
    total, status, _ = ReproducibilityScorer.calculate_composite_score(
        tier1=100.0, tier2=70.0, tier3=75.0, tier4=80.0, tier1_exit_code=0, has_critical_error=False)
    assert status == "Partially Verified" and total == 82.75

