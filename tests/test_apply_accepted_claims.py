"""scripts/apply_accepted_claims.py: only claims a person accepted reach data/seed_papers.json (#135, tests #272)."""

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import event

from src.claim_store import record_review, save_extracted_claim
from src.database import get_engine, get_session, init_db, seed_database

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import apply_accepted_claims as aac


def _claim(paper_id="paper_003", query_id="ft_transformer_rmse", value=0.459, **extra):
    row = {"extracted_claim_id": f"{paper_id}:{query_id}", "paper_id": paper_id, "query_id": query_id,
           "value": value, "value_as_printed": str(value), "page": 7, "table_or_section": "Table 2",
           "review_status": "accepted", "verified_by": "human"}
    row.update(extra)
    return row


def _entries():
    return [
        {"paper_id": "paper_003", "expected_claims": {"old": 1.0}, "source_table_or_section": {"old": "Table 9"}},
        {"paper_id": "paper_005", "expected_claims": {"gone": 2.0}, "source_table_or_section": {"gone": "Fig. 4"}},
    ]


def test_only_accepted_claims_checked_by_a_person_are_taken():
    decisions = {"claims": [
        _claim(),
        _claim(query_id="resnet_rmse", review_status="pending", verified_by="auto-quote-match"),
        _claim(query_id="x", review_status="rejected"),
        _claim(query_id="y", verified_by="auto-quote-match"),  # accepted but not by a person
    ]}
    assert {p: [c["query_id"] for c in cs] for p, cs in aac.accepted_by_paper(decisions).items()} == {
        "paper_003": ["ft_transformer_rmse"]}


def test_expected_values_are_sorted_and_the_source_names_table_page_and_printed_value():
    values, sources = aac.expected_for([_claim(query_id="b", value=2.0), _claim(query_id="a", value=1.0)])
    assert list(values) == ["a", "b"] and values == {"a": 1.0, "b": 2.0}
    assert sources["a"] == "Table 2, p. 7: 1.0 (quote-matched, accepted by a person)"


def test_apply_replaces_claims_and_keeps_the_old_ones_once():
    decisions = {"claims": [_claim()]}
    entries = aac.apply(decisions, _entries())
    by_id = {e["paper_id"]: e for e in entries}
    assert by_id["paper_003"]["expected_claims"] == {"ft_transformer_rmse": 0.459}
    assert by_id["paper_005"]["expected_claims"] == {} and by_id["paper_005"]["source_table_or_section"] == {}
    assert by_id["paper_003"]["seed_claims_before_extraction"]["expected_claims"] == {"old": 1.0}
    assert by_id["paper_005"]["seed_claims_before_extraction"]["expected_claims"] == {"gone": 2.0}
    again = aac.apply({"claims": [_claim(value=0.5)]}, entries)  # a second apply must not overwrite the history
    assert again[0]["seed_claims_before_extraction"]["expected_claims"] == {"old": 1.0}
    assert again[0]["expected_claims"] == {"ft_transformer_rmse": 0.5}


def test_mismatches_names_the_papers_that_disagree():
    decisions = {"claims": [_claim()]}
    assert aac.mismatches(decisions, _entries()) == ["paper_003", "paper_005"]
    applied = aac.apply(decisions, _entries())
    assert aac.mismatches(decisions, applied) == []
    applied[0]["expected_claims"]["ft_transformer_rmse"] = 0.999  # a hand edit
    assert aac.mismatches(decisions, applied) == ["paper_003"]


@pytest.fixture
def files(tmp_path, monkeypatch):
    seed = tmp_path / "seed_papers.json"
    seed.write_text(json.dumps(_entries(), indent=2) + "\n", encoding="utf-8")
    decisions = tmp_path / "review_decisions.json"
    decisions.write_text(json.dumps({"claims": [_claim()]}), encoding="utf-8")
    monkeypatch.setattr(aac, "SEED_PAPERS_PATH", seed)
    return seed, decisions


def test_command_line_check_then_apply_then_check(files, capsys):
    seed, decisions = files
    assert aac.main(["check", "--decisions", str(decisions)]) == 1
    assert json.loads(capsys.readouterr().out) == {"consistent": False, "papers": ["paper_003", "paper_005"]}
    assert aac.main(["apply", "--decisions", str(decisions)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"paper_003": {"ft_transformer_rmse": 0.459}, "paper_005": {}}
    stored = json.loads(seed.read_text(encoding="utf-8"))
    assert stored[0]["expected_claims"] == {"ft_transformer_rmse": 0.459}
    assert aac.main(["check", "--decisions", str(decisions)]) == 0
    assert json.loads(capsys.readouterr().out) == {"consistent": True, "papers": []}


def test_apply_keeps_the_line_endings_of_the_seed_file(files):
    seed, decisions = files
    seed.write_bytes(seed.read_bytes().replace(b"\n", b"\r\n"))
    assert aac.main(["apply", "--decisions", str(decisions)]) == 0
    raw = seed.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")


def test_export_writes_every_claim_with_its_review_and_a_summary(tmp_path):
    url = f"sqlite:///{tmp_path / 'claims.db'}"
    engine = get_engine(url)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    init_db(engine)
    session = get_session(engine)
    seed_database(session=session)
    base = {"paper_id": "paper_003", "metric_name": "rmse", "dataset": "California Housing", "model_variant": "FT-T",
            "split": "not_stated", "value_as_printed": "0.459", "higher_is_better": False, "page": 7,
            "table_or_section": "Table 2", "quote": "FT-T 0.459", "source_file": "data/claims/paper_003.json",
            "pdf_sha256": "f2fa", "extractor_version": "pass A", "verified_by": "auto-quote-match"}
    save_extracted_claim(session, {**base, "query_id": "q1", "value": 0.459})
    save_extracted_claim(session, {**base, "query_id": "q2", "value": 0.486})
    session.commit()
    record_review(session, "paper_003:q1", "accepted", note="checked")
    session.commit()
    session.close()
    out = tmp_path / "decisions.json"
    assert aac.main(["export", "--db-url", url, "--decisions", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"] == {"accepted": 1, "pending": 1}
    by_id = {c["extracted_claim_id"]: c for c in data["claims"]}
    assert by_id["paper_003:q1"]["verified_by"] == "human" and by_id["paper_003:q1"]["reviewed_at"]
    assert by_id["paper_003:q1"]["review_note"] == "checked"
    assert by_id["paper_003:q2"]["reviewed_at"] is None and by_id["paper_003:q2"]["review_status"] == "pending"
