"""Unit tests for Repro Radar 4-tier reproducibility scoring rubric and AI decision layer."""

import pytest
from src.config import (
    STATUS_FAILED,
    STATUS_NEEDS_REVIEW,
    STATUS_PARTIALLY_VERIFIED,
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
    score, notes = Tier1BuildEvaluator.evaluate(
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
    score, claim_results, notes = Tier2MetricsEvaluator.evaluate(claimed, reproduced, tolerance=0.05)
    assert score == 100.0
    assert claim_results["acc"]["matches"] is True
    assert claim_results["f1"]["matches"] is True


def test_tier2_metrics_evaluator_partial_match():
    """Test partial credit when metric is within 2x tolerance."""
    claimed = {"acc": 0.80}
    reproduced = {"acc": 0.86}  # 7.5% error -> above 5% but below 10%
    score, claim_results, notes = Tier2MetricsEvaluator.evaluate(claimed, reproduced, tolerance=0.05)
    assert score == 50.0
    assert claim_results["acc"]["matches"] is False


def test_tier2_metrics_evaluator_diverged():
    """Test 0% metric score when values diverge significantly."""
    claimed = {"acc": 0.90}
    reproduced = {"acc": 0.50}  # Diverged
    score, claim_results, notes = Tier2MetricsEvaluator.evaluate(claimed, reproduced, tolerance=0.05)
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
    """Test composite calculation leading to 'Doğrulandı'."""
    total, status, summary = ReproducibilityScorer.calculate_composite_score(
        tier1=100.0,
        tier2=95.0,
        tier3=90.0,
        tier4=100.0,
    )
    assert total >= 85.0
    assert status == STATUS_VERIFIED
    assert "Doğrulandı" in summary


def test_composite_score_status_needs_review():
    """Test composite calculation leading to 'İncelenmeli' when build works but metrics diverge."""
    total, status, summary = ReproducibilityScorer.calculate_composite_score(
        tier1=100.0,
        tier2=30.0,  # Diverged metrics
        tier3=75.0,
        tier4=100.0,
    )
    assert status == STATUS_NEEDS_REVIEW
    assert "İncelenmeli" in status


def test_composite_score_status_failed():
    """Test composite calculation leading to 'Tekrarlanamadı' on build failure."""
    total, status, summary = ReproducibilityScorer.calculate_composite_score(
        tier1=25.0,  # Build fail
        tier2=0.0,
        tier3=0.0,
        tier4=30.0,
        tier1_exit_code=1,
    )
    assert status == STATUS_FAILED
    assert "Tekrarlanamadı" in status
