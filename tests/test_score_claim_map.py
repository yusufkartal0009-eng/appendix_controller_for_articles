"""Accepted claims reach the run's metrics through the claim map (#509)."""

import json
from pathlib import Path

import pytest

from src.claim_metric_map import ClaimMapError, apply_claim_map, load_claim_map
from src.score_run import load_run, score_run

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ACCEPTED = [c for c in json.loads((DATA / "claims" / "review_decisions.json").read_text(encoding="utf-8"))["claims"]
            if c.get("review_status") == "accepted"]
PAPER_003_RUNS = ["pilot3_runs/paper_003", "memory_runs/paper_003", "memory_runs/paper_003_run2", "cpu_runs/paper_003",
                  "env_cache_runs/first_run/paper_003", "env_cache_runs/second_run/paper_003"]


def claims_of(paper_id):
    return {c["query_id"]: c["value"] for c in ACCEPTED if c["paper_id"] == paper_id}


def score(paper_id, rel, license_name, claim_map):
    record, report = load_run(DATA / rel)
    return score_run(paper_id, license_name, claims_of(paper_id), record, report, DATA / rel, None, claim_map=claim_map)


@pytest.mark.parametrize("rel", PAPER_003_RUNS)
def test_paper_003_real_run_is_verified_on_the_one_claim_it_produces(rel):
    result = score("paper_003", rel, "Apache-2.0", load_claim_map())
    details = result["claim_details"]
    assert list(details) == ["rmse"]
    assert details["rmse"]["claimed"] == 0.459 and details["rmse"]["reproduced"] == 0.473
    assert details["rmse"]["rel_error"] == pytest.approx(0.0305, abs=1e-4)
    bd = result["breakdown"]
    assert bd.tier2_metrics == 100.0 and bd.status_label == "Verified"
    assert set(result["claim_mapping"]["no_counterpart"]) == {"resnet_rmse", "xgboost_rmse"}
    notes = " ".join(result["diagnostics"]["tier2_notes"])
    assert "Claim resnet_rmse has no counterpart in this run:" in notes
    assert "Claim xgboost_rmse has no counterpart in this run:" in notes


def test_the_old_behaviour_is_unchanged_without_a_map():
    result = score("paper_003", PAPER_003_RUNS[0], "Apache-2.0", None)
    assert result["breakdown"].tier2_metrics == 0.0 and result["breakdown"].status_label == "Needs Review"
    assert set(result["claim_details"]) == {"ft_transformer_rmse", "resnet_rmse", "xgboost_rmse"}
    assert result["claim_mapping"] == {"mapped": {}, "no_counterpart": {}}


def test_a_paper_without_an_entry_in_the_map_behaves_as_before():
    claim_map = {"paper_999": {"x": {"decision": "no_counterpart", "reason": "r"}}}
    assert apply_claim_map("paper_003", {"a": 1.0}, claim_map) == ({"a": 1.0}, {}, {})
    result = score("paper_003", PAPER_003_RUNS[0], "Apache-2.0", claim_map)
    assert result["breakdown"].tier2_metrics == 0.0


def test_a_claim_without_an_entry_stays_keyed_by_its_question_id():
    claim_map = {"paper_003": {"ft_transformer_rmse": {"decision": "map", "run_metric": "rmse"}}}
    scored, mapped, none = apply_claim_map("paper_003", {"ft_transformer_rmse": 0.459, "new_claim": 1.0}, claim_map)
    assert scored == {"rmse": 0.459, "new_claim": 1.0} and mapped == {"ft_transformer_rmse": "rmse"} and none == {}


def test_paper_006_has_no_counterpart_and_the_baseline_and_message_are_kept():
    result = score("paper_006", "pilot3_runs/paper_006", "Apache-2.0", load_claim_map())
    bd = result["breakdown"]
    assert result["claim_details"] == {}
    assert set(result["claim_mapping"]["no_counterpart"]) == {"arcene_auroc", "xgboost_arcene_auroc"}
    notes = result["diagnostics"]["tier2_notes"]
    assert "No numeric claims specified; neutral baseline applied (70.0)" in notes
    assert any(n.startswith("Claim arcene_auroc has no counterpart in this run: the claim belongs to the Arcene dataset") for n in notes)
    # with nothing left to compare, Tier 2 is the neutral 70.0 and the label follows the existing rules (recorded, not chosen here)
    assert bd.tier2_metrics == 70.0
    # Recorded for the owner: this label rests on the build tiers only, like `paper_102` (docs/REAL_VERDICTS.md, finding 6)
    assert bd.status_label == "Partially Verified" and bd.total_score == 82.75


def test_two_claims_mapped_to_one_run_metric_are_an_error():
    claim_map = {"p": {"a": {"decision": "map", "run_metric": "m"}, "b": {"decision": "map", "run_metric": "m"}}}
    with pytest.raises(ClaimMapError, match="two claims"):
        apply_claim_map("p", {"a": 1.0, "b": 2.0}, claim_map)


def test_a_missing_map_file_is_none(tmp_path):
    assert load_claim_map(tmp_path / "absent.json") is None


@pytest.mark.parametrize("content,message", [
    ("{not json", "cannot be read as JSON"),
    ('{"version": 1}', "no 'papers' object"),
    ('{"papers": {"p": {"q": {"decision": "guess"}}}}', "needs a 'decision'"),
    ('{"papers": {"p": {"q": {"decision": "map"}}}}', "without a 'run_metric'"),
    ('{"papers": {"p": {"q": {"decision": "no_counterpart"}}}}', "without a 'reason'"),
    ('{"papers": {"p": []}}', "must be an object"),
])
def test_a_broken_map_file_gives_a_clear_error(tmp_path, content, message):
    path = tmp_path / "map.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ClaimMapError, match=message):
        load_claim_map(path)


def test_the_shipped_map_loads():
    assert load_claim_map()["paper_003"]["ft_transformer_rmse"]["run_metric"] == "rmse"
