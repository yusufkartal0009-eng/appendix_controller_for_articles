"""Human accept/reject step for extracted claims (W7, #134)."""

import sys

import pytest
from sqlalchemy import event

from src.claim_review import claims_for_scoring, review_claims
from src.claim_store import get_extracted_claims, import_extraction
from src.config import DATA_DIR, PROJECT_ROOT
from src.database import get_engine, get_session, init_db, seed_database
from src.models import ExtractedClaimORM

CLAIMS_DIR = DATA_DIR / "claims"


@pytest.fixture
def db(tmp_path):
    url = f"sqlite:///{tmp_path / 'review.db'}"
    engine = get_engine(url)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    init_db(engine)
    session = get_session(engine)
    seed_database(session=session)
    import_extraction(session, CLAIMS_DIR / "paper_003.json", CLAIMS_DIR / "guard_report.json", "A", PROJECT_ROOT)
    session.commit()
    yield url, session
    session.close()


def answers(*values):
    it = iter(values)
    return lambda prompt: next(it)


def test_accept_reject_skip_are_stored_and_only_accepted_reach_the_scorer(db):
    _, session = db
    ids = [c.query_id for c in get_extracted_claims(session, "paper_003", "pending")]
    assert ids == ["ft_transformer_rmse", "resnet_rmse", "xgboost_rmse"]
    out = []
    counts = review_claims(session, "paper_003", answers("a", "Table 2 checked", "r", "", "s"), out.append)
    assert counts == {"accepted": 1, "rejected": 1, "skipped": 1, "still pending": 1}
    accepted = session.get(ExtractedClaimORM, "paper_003:ft_transformer_rmse")
    assert (accepted.review_status, accepted.verified_by, accepted.review_note) == ("accepted", "human", "Table 2 checked")
    rejected = session.get(ExtractedClaimORM, "paper_003:resnet_rmse")
    assert (rejected.review_status, rejected.verified_by, rejected.review_note) == ("rejected", "human", None)
    assert session.get(ExtractedClaimORM, "paper_003:xgboost_rmse").review_status == "pending"
    assert claims_for_scoring(session, "paper_003") == {"ft_transformer_rmse": 0.459}
    assert any("page 7, Table 2" in line for line in out)  # provenance is shown before the question


def test_invalid_answer_is_asked_again_and_quit_keeps_the_rest_pending(db):
    _, session = db
    out = []
    counts = review_claims(session, "paper_003", answers("x", "", "q"), out.append)
    assert "Please answer a, r, s, or q." in out
    assert counts == {"still pending": 3}
    assert claims_for_scoring(session, "paper_003") == {}


def test_nothing_is_accepted_without_a_decision(db):
    _, session = db
    assert claims_for_scoring(session, "paper_003") == {}
    review_claims(session, "paper_005", answers(), lambda line: None)  # no claims imported for paper_005 here


def test_cli_review_and_list(db, monkeypatch, capsys):
    url, session = db
    sys.path.insert(0, str(PROJECT_ROOT))
    import cli

    monkeypatch.setattr("builtins.input", answers("r", "wrong table", "q"))
    monkeypatch.setattr(sys, "argv", ["cli.py", "review-claims", "paper_003", "--db-url", url])
    cli.main()
    monkeypatch.setattr(sys, "argv", ["cli.py", "review-claims", "paper_003", "--list", "--db-url", url])
    cli.main()
    out = capsys.readouterr().out
    assert "rejected" in out and "paper_003:ft_transformer_rmse" in out
    session.expire_all()
    assert session.get(ExtractedClaimORM, "paper_003:ft_transformer_rmse").review_status == "rejected"
