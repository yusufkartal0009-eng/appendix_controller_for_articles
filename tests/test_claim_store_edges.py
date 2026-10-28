"""Edge cases of the claim store: bad decision files, odd values, long and Unicode text, unknown ids (#557)."""

import json
import math

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from src.claim_store import (
    accepted_claims,
    claim_key,
    get_extracted_claims,
    record_review,
    restore_decisions,
    save_extracted_claim,
)
from src.database import get_engine, get_session, init_db, seed_database


@pytest.fixture
def session(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'edges.db'}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    init_db(engine)
    s = get_session(engine)
    seed_database(session=s)
    yield s
    s.close()


def _claim(**overrides):
    data = {
        "paper_id": "paper_003", "query_id": "q1", "metric_name": "rmse", "dataset": None, "model_variant": None, "split": None,
        "value": 0.5, "value_as_printed": "0.5", "higher_is_better": None, "page": 1, "table_or_section": None,
        "quote": "rmse 0.5", "source_file": "data/claims/paper_003.json", "pdf_sha256": None, "extractor_version": "v",
        "verified_by": None,
    }
    data.update(overrides)
    return data


def _decision(**overrides):
    entry = {**_claim(), "review_status": "accepted", "verified_by": "human", "reviewed_at": "2026-10-20T10:00:00", "review_note": None}
    entry.update(overrides)
    return entry


def _write(tmp_path, content) -> "Path":  # noqa: F821
    path = tmp_path / "decisions.json"
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


def test_claim_key_keeps_unicode_and_spaces():
    assert claim_key("paper_é", "q 1") == "paper_é:q 1"


def test_missing_decisions_file_restores_nothing(session, tmp_path):
    assert restore_decisions(session, tmp_path / "absent.json") == {"restored": 0, "kept": 0, "ignored": 0}


def test_empty_claim_list_restores_nothing(session, tmp_path):
    assert restore_decisions(session, _write(tmp_path, {"claims": []})) == {"restored": 0, "kept": 0, "ignored": 0}
    assert restore_decisions(session, _write(tmp_path, {})) == {"restored": 0, "kept": 0, "ignored": 0}


@pytest.mark.parametrize("content", ["", "{not json", "[]", '"text"', '{"claims": null}', '{"claims": {}}', '{"claims": [1]}'])
def test_a_malformed_decisions_file_is_a_clear_error_and_changes_nothing(session, tmp_path, content):
    with pytest.raises(ValueError, match="decisions.json"):
        restore_decisions(session, _write(tmp_path, content))
    assert get_extracted_claims(session) == []


def test_an_entry_without_ids_is_a_clear_error(session, tmp_path):
    with pytest.raises(ValueError, match="paper_id"):
        restore_decisions(session, _write(tmp_path, {"claims": [{"review_status": "accepted", "verified_by": "human"}]}))


def test_an_entry_with_a_bad_date_is_a_clear_error(session, tmp_path):
    with pytest.raises(ValueError, match="reviewed_at"):
        restore_decisions(session, _write(tmp_path, {"claims": [_decision(reviewed_at="yesterday")]}))
    assert get_extracted_claims(session) == []  # the claim was not half stored


def test_only_accepted_human_entries_are_restored(session, tmp_path):
    entries = [_decision(), _decision(query_id="q2", review_status="rejected"), _decision(query_id="q3", verified_by="auto-consensus")]
    assert restore_decisions(session, _write(tmp_path, {"claims": entries})) == {"restored": 1, "kept": 0, "ignored": 2}
    assert [c.query_id for c in accepted_claims(session, "paper_003")] == ["q1"]


def test_restoring_twice_keeps_the_first_review(session, tmp_path):
    path = _write(tmp_path, {"claims": [_decision()]})
    restore_decisions(session, path)
    assert restore_decisions(session, path) == {"restored": 0, "kept": 1, "ignored": 0}


def test_unknown_paper_and_unknown_claim(session):
    assert accepted_claims(session, "no_such_paper") == []
    with pytest.raises(KeyError):
        record_review(session, "paper_003:absent", "accepted")
    with pytest.raises(ValueError):
        record_review(session, "paper_003:absent", "maybe")
    with pytest.raises(ValueError):
        get_extracted_claims(session, None, "bogus")


def test_long_unicode_quote_and_negative_value_are_stored_as_they_are(session):
    quote = "é准确率μ" * 2000
    row, outcome = save_extracted_claim(session, _claim(quote=quote, value=-3.5))
    session.commit()
    assert outcome == "added" and row.quote == quote and row.value == -3.5
    assert save_extracted_claim(session, _claim(quote=quote, value=-3.5))[1] == "unchanged"


def test_a_nan_value_cannot_be_stored(session):
    """SQLite keeps NaN as NULL and the column is NOT NULL, so a NaN claim is refused instead of stored."""
    with pytest.raises(IntegrityError):
        save_extracted_claim(session, _claim(value=math.nan))
        session.commit()
    session.rollback()


def test_a_claim_of_an_unknown_paper_is_refused_by_the_foreign_key(session):
    with pytest.raises(IntegrityError):
        save_extracted_claim(session, _claim(paper_id="no_such_paper"))
        session.commit()
    session.rollback()
