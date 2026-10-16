"""The stored selection of the six new papers (#342): the document shows it, the entries are well formed."""

import json

from scripts import corpus_selection_doc as doc
from src.config import ALLOWED_LICENSES, PROJECT_ROOT, SEED_PAPERS_PATH

OUT = PROJECT_ROOT / "data" / "corpus_expansion"


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_the_document_shows_the_stored_selection():
    text = (PROJECT_ROOT / "docs" / "CORPUS_EXPANSION.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert doc.render(text) == text


def test_the_table_has_one_row_per_paper_with_its_rank_and_the_rejections():
    table = doc.selection_markdown(_load("evaluation.json"), _load("papers.json"))
    evaluation = _load("evaluation.json")
    assert table.count("| `paper_10") == evaluation["selected"] == 6
    assert f"Evaluated {evaluation['evaluated']} candidates" in table
    rejected = sum(1 for c in evaluation["candidates"] if not c["passed"])
    rows = [row for row in table.splitlines() if row.startswith(("| 1 |", "| 2 |", "| 3 |"))]
    assert sum(int(row.rsplit("|", 2)[1]) for row in rows) == rejected


def test_the_six_entries_are_new_allowed_and_free_of_claims():
    papers = _load("papers.json")
    seed = json.loads(SEED_PAPERS_PATH.read_text(encoding="utf-8"))
    assert [p["paper_id"] for p in papers] == [f"paper_{101 + i}" for i in range(6)]
    assert not {p["repo_url"].lower() for p in papers} & {e["repo_url"].lower() for e in seed}
    assert not {p["paper_url"] for p in papers} & {e["paper_url"] for e in seed}
    assert len({p["paper_url"] for p in papers}) == 6 and len({p["repo_url"].lower() for p in papers}) == 6
    for p in papers:
        assert p["license"] in ALLOWED_LICENSES and len(p["repo_commit"]) == 40
        assert p["run_command"].startswith("python ") and p["expected_claims"] == {} and p["source_table_or_section"] == {}
        assert "setup.py" not in p["run_command"].split()[1]


def test_every_candidate_has_a_first_failed_rule_or_passed_and_the_selection_is_in_hash_order():
    evaluation = _load("evaluation.json")
    hashes = []
    for stage in (1, 2):
        pool = _load("pool.json" if stage == 1 else "pool_stage2.json")
        hashes += [c["full_name"] for c in pool["candidates_in_order"]]
    assert [c["full_name"] for c in evaluation["candidates"]] == hashes[:evaluation["evaluated"]]
    for c in evaluation["candidates"]:
        assert c["passed"] or c["failed_rule"] in {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "verify_corpus"}
    verify = _load("verify_corpus.json")
    assert len(verify) == 6 and all(v["ok"] for v in verify)
