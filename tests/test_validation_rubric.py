"""Unit tests for ModelValidationRubric, statistical metric bounds, and stability analysis."""


from src.validation_rubric import (
    MetricCategory,
    ModelValidationRubric,
    ValidationReport,
)


def test_resolve_spec_custom_and_heuristics():
    rubric = ModelValidationRubric()

    # Known bounded rate
    spec_acc = rubric.resolve_spec("accuracy")
    assert spec_acc.category == MetricCategory.BOUNDED_RATE
    assert spec_acc.relative_tolerance == 0.05

    # Known loss
    spec_rmse = rubric.resolve_spec("rmse")
    assert spec_rmse.category == MetricCategory.UNBOUNDED_LOSS
    assert spec_rmse.lower_is_better is True

    # Hardware runtime metric
    spec_lat = rubric.resolve_spec("latency_ms")
    assert spec_lat.category == MetricCategory.RUNTIME_HARDWARE
    assert spec_lat.relative_tolerance == 0.30

    # Heuristic fallback for custom loss
    spec_custom_loss = rubric.resolve_spec("custom_cross_entropy_loss")
    assert spec_custom_loss.category == MetricCategory.UNBOUNDED_LOSS
    assert spec_custom_loss.lower_is_better is True


def test_bounded_rate_evaluations():
    rubric = ModelValidationRubric()

    # Exact / Tight match
    res_tight = rubric.evaluate_single_metric("accuracy", claimed=0.950, reproduced=0.952)
    assert res_tight.is_reproduced is True
    assert res_tight.score == 100.0

    # Boundary match (within 5% tolerance)
    res_bound = rubric.evaluate_single_metric("accuracy", claimed=0.900, reproduced=0.865)
    assert res_bound.is_reproduced is True
    assert res_bound.score == 90.0

    # Borderline divergence (between 5% and 10%)
    res_border = rubric.evaluate_single_metric("accuracy", claimed=0.900, reproduced=0.830)
    assert res_border.is_reproduced is False
    assert res_border.score == 50.0

    # Complete failure
    res_fail = rubric.evaluate_single_metric("accuracy", claimed=0.900, reproduced=0.700)
    assert res_fail.is_reproduced is False
    assert res_fail.score == 0.0


def test_unbounded_loss_lower_is_better():
    rubric = ModelValidationRubric()

    # Reproduced loss is lower than claimed: 100% full credit!
    res_improved = rubric.evaluate_single_metric("mse", claimed=0.450, reproduced=0.410)
    assert res_improved.is_reproduced is True
    assert res_improved.score == 100.0

    # Slight degradation within tolerance: partial credit
    res_deg = rubric.evaluate_single_metric("mse", claimed=0.400, reproduced=0.415)
    assert res_deg.is_reproduced is True
    assert 80.0 <= res_deg.score <= 100.0

    # Severe degradation: zero score
    res_severe = rubric.evaluate_single_metric("mse", claimed=0.400, reproduced=0.600)
    assert res_severe.is_reproduced is False
    assert res_severe.score == 0.0


def test_hardware_metric_tolerance():
    rubric = ModelValidationRubric()

    # Hardware latency diverged by 20% due to CPU clock differences -> Still valid under 30% hardware allowance
    res_lat = rubric.evaluate_single_metric("latency_ms", claimed=100.0, reproduced=120.0)
    assert res_lat.is_reproduced is True
    assert res_lat.score == 100.0


def test_multi_seed_stability_calculations():
    rubric = ModelValidationRubric()

    # Deterministic single seed
    single_res = rubric.analyze_multi_seed_stability("acc", [0.945])
    assert single_res.status == "DETERMINISTIC"
    assert single_res.stability_score == 100.0

    # Multi-seed with ultra-low variance (CV <= 2%)
    stable_res = rubric.analyze_multi_seed_stability("acc", [0.942, 0.945, 0.944, 0.943])
    assert stable_res.status == "DETERMINISTIC"
    assert stable_res.coefficient_of_variation_pct <= 2.0
    assert stable_res.stability_score == 100.0
    assert stable_res.confidence_interval_95[0] <= stable_res.mean <= stable_res.confidence_interval_95[1]

    # Highly unstable seed run (CV > 10%)
    unstable_res = rubric.analyze_multi_seed_stability("acc", [0.95, 0.60, 0.85, 0.50])
    assert unstable_res.status == "UNSTABLE"
    assert unstable_res.stability_score <= 40.0


def test_anomaly_detection():
    rubric = ModelValidationRubric()

    claimed = {"accuracy": 0.92, "loss": 0.25, "f1": 0.88}
    reproduced_clean = {"accuracy": 0.915, "loss": 0.24, "f1": 0.875}
    assert len(rubric.detect_anomalies(claimed, reproduced_clean)) == 0

    # Test NaN / Inf detection
    reproduced_nan = {"accuracy": float("nan"), "loss": 0.25}
    anomalies_nan = rubric.detect_anomalies(claimed, reproduced_nan)
    assert any("invalid numerical" in a for a in anomalies_nan)

    # Test suspicious perfect 1.0000 data leakage alert
    reproduced_leakage = {"accuracy": 1.0000, "loss": 0.01}
    anomalies_leak = rubric.detect_anomalies(claimed, reproduced_leakage)
    assert any("perfect score 1.0000" in a for a in anomalies_leak)

    # Test sign flip
    claimed_corr = {"correlation": 0.75}
    reproduced_corr = {"correlation": -0.65}
    anomalies_sign = rubric.detect_anomalies(claimed_corr, reproduced_corr)
    assert any("Sign inversion" in a for a in anomalies_sign)


def test_validate_submission_composite():
    rubric = ModelValidationRubric()

    claimed = {"accuracy": 0.94, "loss": 0.18}
    reproduced = {"accuracy": 0.938, "loss": 0.175}
    seed_runs = {"accuracy": [0.938, 0.940, 0.937]}

    report = rubric.validate_submission(
        paper_id="paper_test_rubric",
        claimed_metrics=claimed,
        reproduced_metrics=reproduced,
        seed_runs=seed_runs,
    )

    assert isinstance(report, ValidationReport)
    assert report.paper_id == "paper_test_rubric"
    assert report.validation_status == "VERIFIED"
    assert report.overall_validity_score >= 85.0
    assert len(report.anomalies) == 0

    # Ensure report serializes to dict
    report_dict = report.to_dict()
    assert report_dict["validation_status"] == "VERIFIED"
    assert "accuracy" in report_dict["metric_results"]
