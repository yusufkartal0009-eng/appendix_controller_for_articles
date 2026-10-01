"""Unit tests for Repro Radar database initialization, seeding, and ORM operations."""

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import (
    get_all_papers,
    get_paper_by_id,
    init_db,
    save_score,
    seed_database,
)
from src.models import PaperORM


@pytest.fixture
def temp_db():
    """Create an isolated temporary SQLite database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{path}"
    engine = create_engine(db_url, echo=False)

    # Initialize schema
    init_db(engine=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield {"engine": engine, "session": session, "path": path}

    session.close()
    engine.dispose()
    if os.path.exists(path):
        try:
            os.remove(path)
        except PermissionError:
            pass


def test_init_db_creates_tables(temp_db):
    """Test that all tables defined in schema.sql exist."""
    session = temp_db["session"]
    papers = session.query(PaperORM).all()
    assert len(papers) == 0


def test_seed_database_loads_papers(temp_db):
    """Test seeding database from data/seed_papers.json."""
    session = temp_db["session"]
    count = seed_database(session=session)
    assert count >= 5

    # Verify query
    all_papers = get_all_papers(session=session)
    assert len(all_papers) == count

    # Check paper_002
    p2 = get_paper_by_id("paper_002", session=session)
    assert p2 is not None
    assert "TabPFN" in p2.title
    claims = p2.get_expected_claims_dict()
    assert "mean_roc_auc" in claims
    assert claims["mean_roc_auc"] == 0.895


def test_save_and_retrieve_score(temp_db):
    """Test inserting and updating reproducibility score."""
    session = temp_db["session"]
    seed_database(session=session)

    score_dict = {
        "score_id": "score_test_01",
        "paper_id": "paper_002",
        "tier1_build": 100.0,
        "tier2_metrics": 90.0,
        "tier3_stability": 85.0,
        "tier4_artifacts": 100.0,
        "total_score": 94.25,
        "status_label": "Verified",
        "summary": "Excellent reproducibility.",
    }
    saved = save_score(score_dict, session=session)
    assert saved.score_id == "score_test_01"
    assert saved.total_score == 94.25

    # Update score
    score_dict["total_score"] = 95.0
    updated = save_score(score_dict, session=session)
    assert updated.total_score == 95.0
