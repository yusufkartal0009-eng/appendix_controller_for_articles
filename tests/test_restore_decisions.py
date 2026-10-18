"""A fresh clone gets the claims a person accepted from the committed decisions file (#395)."""

import json

import pytest
from sqlalchemy import event

from src.claim_review import claims_for_scoring
from src.claim_store import (
    accepted_claims,
    get_extracted_claims,
    record_review,
    restore_decisions,
)
from src.config import DATA_DIR
from src.database import get_engine, get_session, init_db, seed_database

DECISIONS = DATA_DIR / "claims" / "review_decisions.json"


@pytest.fixture
def session(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    init_db(engine)
    s = get_session(engine)
    seed_database(session=s)
    yield s
    s.close()


def _entry(**overrides):
    entry = {
        "extracted_claim_id": "paper_003:ft_transformer_rmse", "paper_id": "paper_003", "query_id": "ft_transformer_rmse",
        "metric_name": "rmse", "dataset": "California Housing", "model_variant": "FT-T", "value": 0.459,
        "value_as_printed": "0.459", "page": 7, "table_or_section": "Table 2", "quote": "FT-T 0.459 0 .859 0.391 0.732",
        "source_file": "data/claims/paper_003.json", "extractor_version": "pass A", "verified_by": "human",
        "review_status": "accepted", "review_note": None, "reviewed_at": "2026-10-05T18:04:02",
    }
    entry.update(overrides)
    return entry


def _file(tmp_path, *entries):
    path = tmp_path / "review_decisions.json"
    path.write_text(json.dumps({"claims": list(entries)}), encoding="utf-8")
    return path


def test_accepted_human_decisions_reach_the_scorer(session, tmp_path):
    counts = restore_decisions(session, _file(tmp_path, _entry()))
    session.commit()
    assert counts == {"restored": 1, "kept": 0, "ignored": 0}
    assert claims_for_scoring(session, "paper_003") == {"ft_transformer_rmse": 0.459}
    row = accepted_claims(session, "paper_003")[0]
    assert row.verified_by == "human" and "restored from review_decisions.json" in row.review_note


def test_entries_that_are_not_human_accepted_are_ignored(session, tmp_path):
    path = _file(tmp_path, _entry(review_status="rejected"), _entry(query_id="b", verified_by="auto-consensus"),
                 _entry(query_id="c", review_status="pending", verified_by=None))
    assert restore_decisions(session, path) == {"restored": 0, "kept": 0, "ignored": 3}
    assert get_extracted_claims(session, "paper_003") == []


def test_a_decision_made_in_this_database_is_kept(session, tmp_path):
    path = _file(tmp_path, _entry())
    restore_decisions(session, path)
    record_review(session, "paper_003:ft_transformer_rmse", "rejected", "checked again")
    session.commit()
    assert restore_decisions(session, path) == {"restored": 0, "kept": 1, "ignored": 0}
    assert get_extracted_claims(session, "paper_003")[0].review_status == "rejected"


def test_a_missing_file_restores_nothing(session, tmp_path):
    assert restore_decisions(session, tmp_path / "nope.json") == {"restored": 0, "kept": 0, "ignored": 0}


def test_the_committed_decisions_all_restore(session):
    total = len(json.loads(DECISIONS.read_text(encoding="utf-8"))["claims"])
    counts = restore_decisions(session, DECISIONS)
    session.commit()
    assert counts["restored"] == total and counts["ignored"] == 0
    assert sum(len(accepted_claims(session, pid)) for pid in {c.paper_id for c in get_extracted_claims(session)}) == total
