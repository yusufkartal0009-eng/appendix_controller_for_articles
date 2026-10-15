"""API routes of the local dashboard (#37, #41): status codes, schema fidelity, empty tables, no invented values."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.database import get_engine, get_session, init_db
from src.models import PaperORM, RunORM, ScoreORM, ScoreRead
from src.web.app import create_app


def _db(tmp_path):
    return f"sqlite:///{(tmp_path / 'api.db').as_posix()}"


def _paper(paper_id, title="A Test Paper"):
    return PaperORM(paper_id=paper_id, title=title, year=2021, venue="Test Venue", repo_url="https://example.org/r",
                    paper_url=None, license="MIT", target_script="main.py",
                    expected_claims=json.dumps({"rmse": 0.123456}), source_table_or_section="{}")


def _score(paper_id, total, label, run_id=None):
    return ScoreORM(score_id=f"s-{paper_id}", paper_id=paper_id, run_id=run_id, tier1_build=total, tier2_metrics=0.0,
                    tier3_stability=0.0, tier4_artifacts=50.0, total_score=total, status_label=label, summary="why")


@pytest.fixture
def seeded(tmp_path):
    url = _db(tmp_path)
    engine = get_engine(url)
    init_db(engine)
    session = get_session(engine)
    session.add_all([_paper("paper_901"), _paper("paper_902", "Second"), _paper("paper_903", "Third")])
    session.add(RunORM(run_id="run-1", paper_id="paper_901", status="COMPLETED", exit_code=0, execution_time=12.5,
                       stdout="out", stderr="", seed=42, outputs_sha256="ab" * 32,
                       timestamp=datetime(2026, 10, 1, 8, 0, tzinfo=UTC)))
    session.flush()
    session.add_all([_score("paper_901", 80.0, "Verified", "run-1"), _score("paper_902", 20.0, "Failed")])
    session.commit()
    session.close()
    return TestClient(create_app(url))


@pytest.fixture
def empty(tmp_path):
    return TestClient(create_app(_db(tmp_path)))


@pytest.mark.parametrize("path", ["/api/v1/papers", "/api/v1/scores"])
def test_empty_tables_give_an_empty_list(empty, path):
    response = empty.get(path)
    assert response.status_code == 200 and response.json() == []


@pytest.mark.parametrize("path", ["/api/v1/scores/paper_901", "/api/v1/runs/run-1"])
def test_unknown_ids_give_404(empty, path):
    response = empty.get(path)
    assert response.status_code == 404 and "detail" in response.json()


def test_scores_are_listed_best_first_and_match_the_schema(seeded):
    rows = seeded.get("/api/v1/scores").json()
    assert [r["paper_id"] for r in rows] == ["paper_901", "paper_902"]
    for row in rows:
        ScoreRead.model_validate(row)  # the response is exactly the Pydantic schema
    assert rows[0]["total_score"] == 80.0 and rows[0]["status_label"] == "Verified" and rows[0]["run_id"] == "run-1"


def test_scores_can_be_filtered_by_status(seeded):
    assert [r["paper_id"] for r in seeded.get("/api/v1/scores?status=Failed").json()] == ["paper_902"]
    assert seeded.get("/api/v1/scores?status=Needs Review").json() == []
    assert seeded.get("/api/v1/scores?status=Excellent").status_code == 422


def test_one_score(seeded):
    response = seeded.get("/api/v1/scores/paper_901")
    assert response.status_code == 200 and response.json()["summary"] == "why"
    assert seeded.get("/api/v1/scores/paper_903").status_code == 404  # a paper without a score


def test_one_run_has_logs_and_hashes_as_stored(seeded):
    body = seeded.get("/api/v1/runs/run-1").json()
    assert body["status"] == "COMPLETED" and body["stdout"] == "out" and body["execution_time"] == 12.5
    assert body["outputs_sha256"] == "ab" * 32 and body["artifact_manifest_sha256"] is None


def test_papers_list_has_every_paper_and_hides_seed_claims(seeded):
    rows = seeded.get("/api/v1/papers").json()
    assert [r["paper_id"] for r in rows] == ["paper_901", "paper_902", "paper_903"]
    assert rows[0]["latest_run"]["run_id"] == "run-1" and rows[1]["latest_run"] is None
    assert "0.123456" not in seeded.get("/api/v1/papers").text


def test_openapi_documentation_lists_every_route(seeded):
    assert seeded.get("/docs").status_code == 200
    paths = set(seeded.get("/openapi.json").json()["paths"])
    assert {"/api/v1/papers", "/api/v1/scores", "/api/v1/scores/{paper_id}", "/api/v1/runs/{run_id}"} <= paths
