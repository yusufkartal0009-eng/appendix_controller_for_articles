"""D0 dashboard skeleton (#170): one real endpoint and a page, with an explicit empty state and no hard-coded data."""

import json
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from src.database import get_engine, get_session
from src.models import PaperORM, RunORM
from src.web.app import EMPTY_STATE, create_app


def _db(tmp_path):
    return f"sqlite:///{(tmp_path / 'web.db').as_posix()}"


def _add_paper(db_url, with_run=True):
    session = get_session(get_engine(db_url))
    session.add(PaperORM(paper_id="paper_901", title="A Test Paper <b>", year=2021, venue="Test Venue",
                         repo_url="https://example.org/repo", paper_url=None, license="MIT",
                         target_script="main.py", expected_claims=json.dumps({"rmse": 0.123456}),
                         source_table_or_section="{}"))
    if with_run:
        session.add(RunORM(run_id="run-1", paper_id="paper_901", status="FAILED", exit_code=1,
                           failure_category="MISSING_DEPENDENCY", timestamp=datetime(2026, 9, 30, 18, 31)))
    session.commit()
    session.close()


def test_empty_database_gives_an_empty_list_and_the_empty_state(tmp_path):
    client = TestClient(create_app(_db(tmp_path)))
    response = client.get("/api/v1/papers")
    assert response.status_code == 200 and response.json() == []
    page = client.get("/")
    assert page.status_code == 200 and EMPTY_STATE in page.text and "<table>" not in page.text


def test_one_row_database(tmp_path):
    db_url = _db(tmp_path)
    client = TestClient(create_app(db_url))
    _add_paper(db_url)
    papers = client.get("/api/v1/papers").json()
    assert [p["paper_id"] for p in papers] == ["paper_901"]
    assert papers[0]["latest_run"]["status"] == "FAILED"
    assert papers[0]["latest_run"]["failure_category"] == "MISSING_DEPENDENCY"
    page = client.get("/").text
    assert "paper_901" in page and "MISSING_DEPENDENCY" in page and EMPTY_STATE not in page
    assert "A Test Paper &lt;b&gt;" in page  # escaped


def test_paper_without_runs_is_shown_as_not_run(tmp_path):
    db_url = _db(tmp_path)
    client = TestClient(create_app(db_url))
    _add_paper(db_url, with_run=False)
    assert client.get("/api/v1/papers").json()[0]["latest_run"] is None
    assert "NOT RUN" in client.get("/").text


def test_latest_run_is_the_newest(tmp_path):
    db_url = _db(tmp_path)
    client = TestClient(create_app(db_url))
    _add_paper(db_url)
    session = get_session(get_engine(db_url))
    session.add(RunORM(run_id="run-2", paper_id="paper_901", status="COMPLETED", exit_code=0,
                       timestamp=datetime(2026, 10, 2, 9, 0)))
    session.commit()
    session.close()
    assert client.get("/api/v1/papers").json()[0]["latest_run"]["run_id"] == "run-2"


def test_unverified_seed_claims_are_never_exposed(tmp_path):
    db_url = _db(tmp_path)
    client = TestClient(create_app(db_url))
    _add_paper(db_url)
    assert "expected_claims" not in client.get("/api/v1/papers").json()[0]
    assert "0.123456" not in client.get("/api/v1/papers").text and "0.123456" not in client.get("/").text


def test_web_code_contains_no_data():
    source = "".join(p.read_text(encoding="utf-8") for p in Path("src/web").glob("*.py"))
    for seed_id in [e["paper_id"] for e in json.loads(Path("data/seed_papers.json").read_text(encoding="utf-8"))]:
        assert seed_id not in source
    for word in ("TabPFN", "FT-Transformer", "MISSING_DEPENDENCY", "DATA_NOT_ACCESSIBLE"):
        assert word not in source
