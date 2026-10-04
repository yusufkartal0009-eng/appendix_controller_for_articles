"""Agent-assisted extractions (plan step 1.1, #131): data/claims/<paper_id>.json is complete and follows the schema.

The page-level quote check needs the PDFs, which are not committed; it is done by the quote guard (W4) and by the
writer of these files. Here the files are checked for form and consistency with the questions.
"""

import json

import pytest

from src.claim_schema import ExtractedClaim
from src.config import DATA_DIR

CLAIMS_DIR = DATA_DIR / "claims"
SEED = json.loads((DATA_DIR / "seed_papers.json").read_text(encoding="utf-8"))
PAPERS = [e["paper_id"] for e in SEED]


def _load(paper_id):
    return json.loads((CLAIMS_DIR / f"{paper_id}.json").read_text(encoding="utf-8"))


def test_every_seed_paper_has_a_claim_file():
    assert sorted(p.stem for p in CLAIMS_DIR.glob("paper_*.json")) == sorted(PAPERS)


@pytest.mark.parametrize("paper_id", PAPERS)
def test_both_passes_answer_every_question(paper_id):
    record = _load(paper_id)
    questions = json.loads((DATA_DIR / "claim_queries" / f"{paper_id}.json").read_text(encoding="utf-8"))
    assert record["pdf_url"] == questions["pdf_url"] and len(record["pdf_sha256"]) == 64
    assert set(record["extractions"]) == {"A", "B"}
    for label, extraction in record["extractions"].items():
        assert extraction["method"] and extraction["made_at"]
        assert set(extraction["answers"]) == {q["query_id"] for q in questions["queries"]}, label


@pytest.mark.parametrize("paper_id", PAPERS)
def test_answers_follow_the_schema(paper_id):
    for label, extraction in _load(paper_id)["extractions"].items():
        for qid, answer in extraction["answers"].items():
            assert answer["status"] in ("found", "not_found"), (label, qid)
            assert answer["reason"], (label, qid)
            if answer["status"] == "found":
                claim = ExtractedClaim(**answer["claim"])  # raises if value_normalized breaks the rule
                assert claim.value_as_printed in claim.source_quote
            else:
                assert answer["claim"] is None


def test_questions_do_not_contain_the_seed_values():
    for entry in SEED:
        questions = (DATA_DIR / "claim_queries" / f"{entry['paper_id']}.json").read_text(encoding="utf-8")
        q = json.loads(questions)["queries"]
        # Every seed claim has at least one question; split questions (owner decisions, #184) name their seed claim.
        seed_claims = [x.get("seed_claim", x["query_id"]) for x in q]
        assert sorted(set(seed_claims)) == sorted(entry["expected_claims"])
        for x in q:
            if "seed_claim" in x:
                assert x["query_id"].startswith(x["seed_claim"] + "__") and x["split_note"]
        for value in entry["expected_claims"].values():
            assert str(value) not in json.dumps(q), (entry["paper_id"], value)
