"""Tier 3 from the stored multi-seed record and the claimed metric (#542, docs/MULTI_SEED.md section 5)."""

import json

import pytest

from src.claim_metric_map import load_claim_map
from src.multi_seed import MultiSeedRecordError, load_seed_metric_results
from src.score_run import score_run
from src.scoring import Tier3StabilityEvaluator

# paper_003's stored seed values (data/multi_seed_runs/paper_003): loss is the noisier metric, rmse the claimed one
SEEDS = {"loss": [0.106, 0.127, 0.119], "rmse": [0.473, 0.47, 0.465]}
RECORD = {"stage": {"status": "STAGED"}, "run": {"status": "COMPLETED", "exit_code": 0, "dependency_install_status": "SKIPPED"}}
REPORT = {"metrics": {"rmse": 0.473}, "dependency_install_status": "SKIPPED"}
MAP = {"p": {"q_rmse": {"decision": "map", "run_metric": "rmse", "reason": "r"}}}


def tier3(claims, seeds, claim_map, tmp_path):
    return score_run("p", "MIT", claims, RECORD, REPORT, tmp_path, seed_metric_results=seeds, claim_map=claim_map)


def test_the_claimed_metric_alone_decides_tier_3():
    score, notes = Tier3StabilityEvaluator.evaluate_by_metric(SEEDS, claimed_run_metrics=["rmse"])
    assert score == 100.0
    assert "claims" in notes[0] and "'rmse'" in notes[0]


def test_without_a_claimed_metric_the_largest_cv_decides_as_before():
    score, notes = Tier3StabilityEvaluator.evaluate_by_metric(SEEDS)
    assert score == 65.0
    assert "'loss'" in notes[0] and "largest CV" in notes[0]


def test_a_claimed_metric_without_seed_values_falls_back_to_the_largest_cv():
    assert Tier3StabilityEvaluator.evaluate_by_metric(SEEDS, claimed_run_metrics=["accuracy"])[0] == 65.0
    assert Tier3StabilityEvaluator.evaluate_by_metric(SEEDS, claimed_run_metrics=[])[0] == 65.0


def test_several_claimed_metrics_use_the_largest_cv_among_them():
    assert Tier3StabilityEvaluator.evaluate_by_metric(SEEDS, claimed_run_metrics=["rmse", "loss"])[0] == 65.0


def test_score_run_uses_the_mapped_claim_metric(tmp_path):
    result = tier3({"q_rmse": 0.459}, SEEDS, MAP, tmp_path)
    assert result["breakdown"].tier3_stability == 100.0


def test_score_run_without_a_mapped_claim_keeps_the_old_rule(tmp_path):
    assert tier3({"q_rmse": 0.459}, SEEDS, None, tmp_path)["breakdown"].tier3_stability == 65.0
    assert tier3({}, SEEDS, MAP, tmp_path)["breakdown"].tier3_stability == 65.0
    no_counterpart = {"p": {"q_rmse": {"decision": "no_counterpart", "reason": "r"}}}
    assert tier3({"q_rmse": 0.459}, SEEDS, no_counterpart, tmp_path)["breakdown"].tier3_stability == 65.0


def test_score_run_without_a_seed_record_is_the_single_run_baseline(tmp_path):
    assert tier3({"q_rmse": 0.459}, None, MAP, tmp_path)["breakdown"].tier3_stability == 75.0


def test_the_stored_records_give_paper_003_100_and_paper_006_100(tmp_path):
    seeds_003 = load_seed_metric_results("paper_003")
    assert seeds_003["rmse"] == [0.473, 0.47, 0.465]
    claim_map = load_claim_map()
    claims = {"ft_transformer_rmse": 0.459}
    old = score_run("paper_003", "MIT", claims, RECORD, REPORT, tmp_path, seed_metric_results=seeds_003)
    new = score_run("paper_003", "MIT", claims, RECORD, REPORT, tmp_path, seed_metric_results=seeds_003, claim_map=claim_map)
    assert (old["breakdown"].tier3_stability, new["breakdown"].tier3_stability) == (65.0, 100.0)
    seeds_006 = load_seed_metric_results("paper_006")
    result = score_run("paper_006", "MIT", {}, RECORD, REPORT, tmp_path, seed_metric_results=seeds_006, claim_map=claim_map)
    assert result["breakdown"].tier3_stability == 100.0


def test_a_paper_without_a_record_has_no_seed_results(tmp_path):
    assert load_seed_metric_results("paper_001") is None
    assert load_seed_metric_results("p", tmp_path) is None


def write_summary(tmp_path, text):
    folder = tmp_path / "p"
    folder.mkdir()
    (folder / "multi_seed_summary.json").write_text(text, encoding="utf-8")


@pytest.mark.parametrize("text, message", [
    ("{not json", "cannot be read as JSON"),
    ("[]", "no 'metrics' object"),
    (json.dumps({"metrics": []}), "no 'metrics' object"),
    (json.dumps({"metrics": {"a": {"values": []}}}), "metric 'a'"),
    (json.dumps({"metrics": {"a": {"values": ["x", 1]}}}), "metric 'a'"),
    (json.dumps({"metrics": {"a": {"nope": 1}}}), "metric 'a'"),
])
def test_a_broken_record_raises_a_clear_error(tmp_path, text, message):
    write_summary(tmp_path, text)
    with pytest.raises(MultiSeedRecordError, match=message):
        load_seed_metric_results("p", tmp_path)


def test_a_good_record_is_read(tmp_path):
    write_summary(tmp_path, json.dumps({"metrics": {"a": {"values": [1, 2.5]}}}))
    assert load_seed_metric_results("p", tmp_path) == {"a": [1.0, 2.5]}
