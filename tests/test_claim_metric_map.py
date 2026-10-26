"""data/claim_metric_map.json covers every accepted claim and its evidence is still in the stored runs (#507)."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAP = json.loads((ROOT / "data" / "claim_metric_map.json").read_text(encoding="utf-8"))
ACCEPTED = [c for c in json.loads((ROOT / "data" / "claims" / "review_decisions.json").read_text(encoding="utf-8"))["claims"]
            if c.get("review_status") == "accepted"]


def entries():
    return [(p, q, e) for p, qs in MAP["papers"].items() for q, e in qs.items()]


def test_every_accepted_claim_has_a_decision_and_nothing_else_is_listed():
    accepted = {(c["paper_id"], c["query_id"]) for c in ACCEPTED}
    listed = {(p, q) for p, q, _ in entries()}
    assert listed == accepted


def test_decisions_are_map_or_no_counterpart_with_a_reason_and_evidence():
    for paper, query, entry in entries():
        assert entry["decision"] in ("map", "no_counterpart"), (paper, query)
        assert entry["reason"].strip() and entry["evidence"], (paper, query)
        if entry["decision"] == "map":
            assert entry["run_metric"].strip(), (paper, query)
        else:
            assert "run_metric" not in entry, (paper, query)


def test_the_map_is_a_single_metric_claim_of_paper_003():
    mapped = [(p, q) for p, q, e in entries() if e["decision"] == "map"]
    assert mapped == [("paper_003", "ft_transformer_rmse")]


@pytest.mark.parametrize("paper,query,entry", entries())
def test_the_evidence_string_occurs_in_the_stored_file(paper, query, entry):
    for item in entry["evidence"]:
        path = ROOT / item["file"]
        assert path.is_file(), f"{item['file']} is missing"
        assert item["contains"] in path.read_text(encoding="utf-8", errors="replace"), (paper, query, item["file"])


def test_the_mapped_metric_is_what_the_stored_runs_report():
    runs = ["pilot3_runs/paper_003", "memory_runs/paper_003", "memory_runs/paper_003_run2", "cpu_runs/paper_003",
            "env_cache_runs/first_run/paper_003", "env_cache_runs/second_run/paper_003"]
    for run in runs:
        report = json.loads((ROOT / "data" / run / "run_report.json").read_text(encoding="utf-8"))
        assert report["metrics"]["rmse"] == 0.473, run
        last = [ln for ln in (ROOT / "data" / run / "stdout.log").read_text(encoding="utf-8", errors="replace").splitlines()
                if "rmse" in ln][-1]
        assert last == "[test ] score = -0.473 | rmse = 0.473", run
