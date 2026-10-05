"""Extracted claims stored with provenance; only human-accepted claims reach the scorer (W6, #10)."""

import json
import sys

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from src.claim_store import (
    accepted_claims,
    claim_key,
    get_claims_by_run,
    get_extracted_claims,
    import_extraction,
    record_review,
    save_extracted_claim,
)
from src.config import DATA_DIR, PROJECT_ROOT
from src.database import get_engine, get_session, init_db, seed_database
from src.models import ClaimORM, ExtractedClaimORM, PaperORM, RunORM

CLAIMS_DIR = DATA_DIR / "claims"


@pytest.fixture
def session(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    init_db(engine)
    s = get_session(engine)
    seed_database(session=s)
    yield s
    s.close()


def _claim(**overrides):
    data = {
        "paper_id": "paper_003", "query_id": "ft_transformer_rmse", "metric_name": "rmse",
        "dataset": "California Housing", "model_variant": "FT-T", "split": "not_stated", "value": 0.459,
        "value_as_printed": "0.459", "higher_is_better": False, "page": 7, "table_or_section": "Table 2",
        "quote": "FT-T 0.459 0 .859 0.391 0.732", "source_file": "data/claims/paper_003.json",
        "pdf_sha256": "f2fa", "extractor_version": "docs/AGENT_EXTRACTION.md pass A; pypdf 6.19.0",
        "verified_by": "auto-quote-match",
    }
    data.update(overrides)
    return data


def test_import_stores_every_found_claim_as_pending_with_provenance(session):
    total = 0
    for path in sorted(CLAIMS_DIR.glob("paper_*.json")):
        counts = import_extraction(session, path, CLAIMS_DIR / "guard_report.json", "A", PROJECT_ROOT)
        total += counts.get("added", 0)
    session.commit()
    rows = get_extracted_claims(session)
    assert total == len(rows) == 12  # 12 found claims in pass A (data/claims/guard_report.json)
    assert {r.review_status for r in rows} == {"pending"}
    assert {r.verified_by for r in rows} == {"auto-quote-match"}
    assert accepted_claims(session, "paper_003") == []  # importing never accepts
    row = session.get(ExtractedClaimORM, claim_key("paper_003", "ft_transformer_rmse"))
    assert (row.page, row.table_or_section, row.value_as_printed, row.source_file) == (
        7, "Table 2", "0.459", "data/claims/paper_003.json")
    assert row.quote and "pass A" in row.extractor_version and row.pdf_sha256


def test_reimport_is_idempotent(session):
    path = CLAIMS_DIR / "paper_003.json"
    import_extraction(session, path, CLAIMS_DIR / "guard_report.json", "A", PROJECT_ROOT)
    counts = import_extraction(session, path, CLAIMS_DIR / "guard_report.json", "A", PROJECT_ROOT)
    assert set(counts) == {"unchanged"}


def test_only_human_accepted_claims_reach_the_scorer(session):
    save_extracted_claim(session, _claim())
    save_extracted_claim(session, _claim(query_id="resnet_rmse", value=0.486, value_as_printed="0.486"))
    session.commit()
    record_review(session, "paper_003:ft_transformer_rmse", "accepted", note="checked Table 2")
    record_review(session, "paper_003:resnet_rmse", "rejected")
    session.commit()
    accepted = accepted_claims(session, "paper_003")
    assert [c.query_id for c in accepted] == ["ft_transformer_rmse"]
    assert accepted[0].verified_by == "human" and accepted[0].reviewed_at is not None
    assert [c.query_id for c in get_extracted_claims(session, "paper_003", "rejected")] == ["resnet_rmse"]


def test_reimport_keeps_a_review_unless_the_claim_changed(session):
    save_extracted_claim(session, _claim())
    record_review(session, "paper_003:ft_transformer_rmse", "accepted")
    _, outcome = save_extracted_claim(session, _claim())
    assert outcome == "unchanged"
    assert session.get(ExtractedClaimORM, "paper_003:ft_transformer_rmse").verified_by == "human"
    _, outcome = save_extracted_claim(session, _claim(value=0.448, value_as_printed="0.448", page=8))
    row = session.get(ExtractedClaimORM, "paper_003:ft_transformer_rmse")
    assert outcome == "updated, review reset"
    assert (row.review_status, row.verified_by, row.reviewed_at) == ("pending", "auto-quote-match", None)


def test_invalid_review_is_refused(session):
    save_extracted_claim(session, _claim())
    with pytest.raises(ValueError):
        record_review(session, "paper_003:ft_transformer_rmse", "maybe")
    with pytest.raises(KeyError):
        record_review(session, "paper_003:missing", "accepted")


def test_database_refuses_an_accepted_claim_without_a_human(session):
    session.add(ExtractedClaimORM(extracted_claim_id="x", review_status="accepted", **_claim(query_id="x")))
    with pytest.raises(IntegrityError):
        session.commit()


def test_cascade_delete_with_the_paper(session):
    save_extracted_claim(session, _claim())
    session.commit()
    session.delete(session.get(PaperORM, "paper_003"))
    session.commit()
    assert get_extracted_claims(session, "paper_003") == []


def test_claims_by_run(session):
    session.add(RunORM(run_id="run_1", paper_id="paper_003", status="FAILED"))
    session.add(ClaimORM(claim_id="c1", paper_id="paper_003", run_id="run_1", metric_name="rmse", claimed_value=0.459))
    session.add(ClaimORM(claim_id="c2", paper_id="paper_003", run_id=None, metric_name="rmse", claimed_value=0.486))
    session.commit()
    assert [c.claim_id for c in get_claims_by_run(session, "run_1")] == ["c1"]


def test_import_script_reports_counts(session, capsys):
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    import import_claims

    db_url = str(session.get_bind().url)
    assert import_claims.main(["--db-url", db_url]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["stored"] == 12 and out["review_status"] == {"pending": 12}
