"""The tolerance probe moves hand-made claims away from real runs' own values and records the scorer's decisions (#440)."""

import json

import pytest

from scripts import tolerance_probe
from src import config
from src.scoring import Tier2MetricsEvaluator


def test_the_true_claim_is_matched_on_every_probed_run_and_the_deviations_are_signed_pairs():
    assert tolerance_probe.deviations() == [0.0, -0.5, 0.5, -1.0, 1.0, -2.0, 2.0, -5.0, 5.0, -10.0, 10.0, -20.0, 20.0]
    data = tolerance_probe.build()
    assert len(data["runs"]) >= 6 and data["tolerance"] == config.DEFAULT_TOLERANCE
    for run in data["runs"]:
        zero = run["rows"][0]
        assert zero["deviation_percent"] == 0 and zero["tier2"] == 100.0, run["run_dir"]
        assert zero["labels"]["MATCHED"] == len(run["metrics"]) and run["metrics"], run["run_dir"]


def test_tier_2_never_rises_when_the_claim_moves_further_from_the_run_in_the_same_direction():
    for run in tolerance_probe.build()["runs"]:
        for sign in (-1, 1):
            rows = sorted((r for r in run["rows"] if r["deviation_percent"] * sign >= 0), key=lambda r: abs(r["deviation_percent"]))
            scores = [r["tier2"] for r in rows]
            assert scores == sorted(scores, reverse=True), (run["run_dir"], sign, scores)


def test_the_error_is_relative_to_the_claim_so_a_claim_moved_down_is_judged_harder_than_one_moved_up():
    # an unbounded metric (above 1) has no absolute allowance: claim 10.5 is 4.76 % off, claim 9.5 is 5.26 % off (t = 5 %)
    _, up, _ = Tier2MetricsEvaluator.evaluate({"score": 10.5}, {"score": 10.0})
    _, down, _ = Tier2MetricsEvaluator.evaluate({"score": 9.5}, {"score": 10.0})
    assert up["score"]["matches"] is True and down["score"]["points"] == 0.5
    limits = tolerance_probe.matched_limits({"score": 10.0})["score"]
    assert limits == {"down": 2.0, "up": 5.0}


def test_a_small_value_between_zero_and_one_stays_matched_far_beyond_the_tolerance():
    limits = tolerance_probe.matched_limits({"boundary_conflict": 0.0167})["boundary_conflict"]
    assert limits == {"down": 20.0, "up": 20.0}  # the absolute allowance of 0.05 covers 20 % of 0.0167 many times over


def test_the_perturbation_moves_every_metric_by_the_same_share():
    assert tolerance_probe.perturb({"a": 2.0, "b": 0.5}, -10.0) == pytest.approx({"a": 1.8, "b": 0.45})
    assert tolerance_probe.perturb({"a": 2.0}, 0.0) == {"a": 2.0}


def test_no_accepted_claim_matches_a_probed_run_and_the_document_says_so_and_carries_the_warning():
    data = tolerance_probe.build()
    assert data["accepted_claims_matching_a_probed_run"] == []
    document = tolerance_probe.render(data)
    assert tolerance_probe.WARNING in document and "hand-made claims" in document and "**not verified**" in document


def test_the_committed_files_equal_what_the_stored_runs_give():
    data = tolerance_probe.build()
    committed = json.loads(tolerance_probe.RESULTS_PATH.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(data))
    assert tolerance_probe.DOC_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") == tolerance_probe.render(data)
