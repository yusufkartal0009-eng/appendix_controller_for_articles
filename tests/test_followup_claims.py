"""Follow-up questions (#258): answered in pass A only, kept apart from the gold-set questions, and never accepted."""

import json

from src.claim_schema import ExtractedClaim
from src.config import DATA_DIR

FOLLOWUP = DATA_DIR / "claims" / "followup"


def _load(name):
    return json.loads((FOLLOWUP / name).read_text(encoding="utf-8"))


def test_followup_questions_are_not_among_the_gold_set_questions():
    questions = json.loads((DATA_DIR / "claim_queries" / "paper_005.json").read_text(encoding="utf-8"))
    assert [q["query_id"] for q in questions["followup_queries"]] == ["ep300_avg_kernel_speedup"]
    assert "ep300_avg_kernel_speedup" not in {q["query_id"] for q in questions["queries"]}


def test_followup_answer_is_pass_a_only_and_follows_the_schema():
    record = _load("paper_005.json")
    assert set(record["extractions"]) == {"A"}
    assert record["status"].startswith("PASS A ONLY")
    answer = record["extractions"]["A"]["answers"]["ep300_avg_kernel_speedup"]
    assert answer["status"] == "found" and answer["reason"]
    claim = ExtractedClaim(**answer["claim"])
    assert claim.value_as_printed in claim.source_quote
    assert record["guard"]["status"] == "AUTO_QUOTE_MATCH"


def test_followup_claim_is_not_accepted_anywhere():
    seed = {e["paper_id"]: e for e in json.loads((DATA_DIR / "seed_papers.json").read_text(encoding="utf-8"))}
    assert seed["paper_005"]["expected_claims"] == {}
    decisions = (DATA_DIR / "claims" / "review_decisions.json").read_text(encoding="utf-8")
    assert "ep300_avg_kernel_speedup" not in decisions
