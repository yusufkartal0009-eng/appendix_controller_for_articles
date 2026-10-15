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


def test_followup_answers_have_both_passes_and_follow_the_schema():
    record = _load("paper_005.json")
    assert set(record["extractions"]) == {"A", "B"}
    assert record["status"].startswith("PASS A AND PASS B IMPORTED, NOT COMPARED")
    normalized = set()
    for name in ("A", "B"):
        answer = record["extractions"][name]["answers"]["ep300_avg_kernel_speedup"]
        assert answer["status"] == "found" and answer["reason"]
        claim = ExtractedClaim(**answer["claim"])
        assert claim.value_as_printed in claim.source_quote
        normalized.add(claim.value_normalized)
    assert len(normalized) == 1, "the two passes disagree on the normalized value"
    assert record["guard"]["status"] == "AUTO_QUOTE_MATCH"


def test_followup_claim_is_not_accepted_anywhere():
    seed = {e["paper_id"]: e for e in json.loads((DATA_DIR / "seed_papers.json").read_text(encoding="utf-8"))}
    assert seed["paper_005"]["expected_claims"] == {}
    decisions = (DATA_DIR / "claims" / "review_decisions.json").read_text(encoding="utf-8")
    assert "ep300_avg_kernel_speedup" not in decisions
