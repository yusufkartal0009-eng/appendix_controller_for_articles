"""Boundary cases of the Tier 2 and Tier 3 evaluators: exact thresholds, zero, negative, NaN, infinity, huge values (#557)."""

import math

import pytest

from src.scoring import (
    Tier2MetricsEvaluator,
    Tier3StabilityEvaluator,
)


def tier2(claimed: float, reproduced: float, name: str = "accuracy") -> tuple[float, dict]:
    score, results, _ = Tier2MetricsEvaluator.evaluate({name: claimed}, {name: reproduced})
    return score, results[name]


@pytest.mark.parametrize("claimed", [round(i / 100, 2) for i in range(5, 96)])
@pytest.mark.parametrize("sign", [1, -1])
def test_absolute_difference_of_exactly_0_05_matches_for_every_claim_in_the_unit_interval(claimed, sign):
    """0.15 - 0.10 and 0.75 - 0.70 are both a difference of 0.05; float noise must not give one of them half points."""
    score, result = tier2(claimed, claimed + sign * 0.05)
    assert score == 100.0
    assert result["matches"] is True


@pytest.mark.parametrize("claimed,reproduced", [(100.0, 105.0), (100.0, 95.0), (-100.0, -105.0), (0.7, 0.735), (20.0, 21.0)])
def test_relative_error_of_exactly_five_percent_matches(claimed, reproduced):
    score, result = tier2(claimed, reproduced)
    assert score == 100.0 and result["matches"] is True


@pytest.mark.parametrize("claimed,reproduced", [(100.0, 110.0), (100.0, 90.0), (0.5, 0.6), (0.5, 0.4)])
def test_exactly_twice_the_tolerance_is_half_points(claimed, reproduced):
    score, result = tier2(claimed, reproduced)
    assert score == 50.0 and result["matches"] is False


@pytest.mark.parametrize("claimed,reproduced,expected", [(100.0, 105.01, 50.0), (0.5, 0.5501, 50.0), (100.0, 110.01, 0.0), (0.5, 0.6001, 0.0)])
def test_just_beyond_a_bound_falls_to_the_next_band(claimed, reproduced, expected):
    """The epsilon (1e-9) is far smaller than any real difference: 0.0001 over a bound still falls to the next band."""
    assert tier2(claimed, reproduced)[0] == expected


def test_time_metric_at_exactly_five_percent_matches_and_just_over_is_half():
    assert tier2(2.0, 2.1, "inference_seconds")[0] == 100.0
    assert tier2(2.0, 2.11, "inference_seconds")[0] == 50.0
    assert tier2(0.02, 0.06, "latency_ms")[0] == 0.0


def test_claim_of_zero_does_not_divide_by_zero():
    assert tier2(0.0, 0.0)[0] == 100.0
    assert tier2(0.0, 0.04)[0] == 100.0  # absolute allowance of a claim inside [0, 1]
    assert tier2(0.0, 0.06)[0] == 50.0
    assert tier2(0.0, 5.0)[0] == 0.0
    assert math.isfinite(tier2(0.0, 5.0)[1]["rel_error"])


@pytest.mark.parametrize("claimed,reproduced", [(math.nan, 0.5), (0.5, math.nan), (math.inf, math.inf), (math.inf, 5.0), (0.5, math.inf), (-math.inf, -math.inf)])
def test_non_finite_values_earn_no_points(claimed, reproduced):
    """A NaN or infinite value is never a match, even when both sides are equal infinities."""
    score, result = tier2(claimed, reproduced)
    assert score == 0.0 and result["matches"] is False


def test_negative_claims_use_the_magnitude_for_relative_error_and_no_absolute_allowance():
    assert tier2(-0.5, -0.52)[0] == 100.0  # 4 % relative
    assert tier2(-0.01, 0.03)[0] == 0.0  # a sign flip is a 400 % error and the claim is outside [0, 1]


def test_very_large_values_and_unicode_names():
    assert tier2(1e300, 1.04e300)[0] == 100.0
    score, results, _ = Tier2MetricsEvaluator.evaluate({"précision_μ": 0.8, "准确率": 0.9}, {"précision_μ": 0.8, "准确率": 0.5})
    assert score == 50.0 and results["précision_μ"]["matches"] is True and results["准确率"]["matches"] is False


def test_empty_and_missing_inputs():
    assert Tier2MetricsEvaluator.evaluate({}, {})[0] == 70.0
    assert Tier2MetricsEvaluator.evaluate({}, {"a": 1.0})[0] == 70.0
    assert Tier2MetricsEvaluator.evaluate({"a": 1.0}, {})[0] == 0.0
    score, results, notes = Tier2MetricsEvaluator.evaluate({"a": 1.0, "b": 1.0}, {"a": 1.0})
    assert score == 50.0 and results["b"]["reproduced"] is None and any("not found" in n for n in notes)


@pytest.mark.parametrize("values,expected", [([100.0, 102.0], 100.0), ([100.0, 105.0], 85.0), ([100.0, 110.0], 85.0), ([100.0, 120.0], 65.0), ([100.0, 150.0], 40.0)])
def test_tier3_bands(values, expected):
    assert Tier3StabilityEvaluator.evaluate(values)[0] == expected


@pytest.mark.parametrize("mean", [0.1, 0.2, 1.0, 7.3, 12.5])
@pytest.mark.parametrize("cv,expected", [(0.02, 100.0), (0.05, 85.0), (0.10, 65.0)])
def test_tier3_cv_exactly_on_a_band_edge_stays_in_the_better_band(mean, cv, expected):
    """Two values mean * (1 -/+ cv) have a population CV of cv; float noise (0.020000000000000018) must not push them down a band."""
    assert Tier3StabilityEvaluator.evaluate([mean * (1 - cv), mean * (1 + cv)])[0] == expected


def test_tier3_zero_mean_negative_and_huge_values():
    assert Tier3StabilityEvaluator.evaluate([0.0, 0.0, 0.0])[0] == 100.0
    assert Tier3StabilityEvaluator.evaluate([1e300, 1e300])[0] == 100.0
    assert Tier3StabilityEvaluator.evaluate([-5.0, -5.1])[0] == 100.0
    assert Tier3StabilityEvaluator.evaluate([-1.0, 1.0])[0] == 40.0  # mean 0: the denominator is floored


def test_tier3_non_finite_seed_values_are_scored_as_high_variance():
    """Current behavior, kept as a record: a NaN or infinite seed value gives CV = NaN, which fails every band."""
    assert Tier3StabilityEvaluator.evaluate([math.nan, 1.0])[0] == 40.0
    assert Tier3StabilityEvaluator.evaluate([math.inf, 1.0])[0] == 40.0


def test_tier3_without_enough_seeds_or_after_a_failed_run():
    assert Tier3StabilityEvaluator.evaluate([])[0] == 75.0
    assert Tier3StabilityEvaluator.evaluate([1.0])[0] == 75.0
    assert Tier3StabilityEvaluator.evaluate(None, single_run_clean=False)[0] == 0.0
    assert Tier3StabilityEvaluator.evaluate([1.0, 1.0], execution_succeeded=False)[0] == 0.0
