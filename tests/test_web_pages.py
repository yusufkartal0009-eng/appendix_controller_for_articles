"""Leaderboard and detail page (#38, #41): search, status filter, sorting, detail, empty states, escaping."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.database import get_engine, get_session, init_db
from src.models import PaperORM, RunORM, ScoreORM
from src.web.app import create_app
from src.web.pages import EMPTY_STATE, NO_MATCH, NOT_SCORED


def _paper(paper_id, title, venue, year=2021):
    return PaperORM(paper_id=paper_id, title=title, year=year, venue=venue, repo_url="https://example.org/r",
                    paper_url=None, license="MIT", target_script="main.py",
                    expected_claims=json.dumps({"rmse": 0.123456}), source_table_or_section="{}")


def _score(paper_id, total, label, run_id=None):
    return ScoreORM(score_id=f"s-{paper_id}", paper_id=paper_id, run_id=run_id, tier1_build=total, tier2_metrics=11.0,
                    tier3_stability=22.0, tier4_artifacts=33.0, total_score=total, status_label=label, summary="because")


@pytest.fixture
def client(tmp_path):
    url = f"sqlite:///{(tmp_path / 'p.db').as_posix()}"
    engine = get_engine(url)
    init_db(engine)
    session = get_session(engine)
    session.add_all([_paper("paper_901", "Alpha Trees", "ICLR", 2020), _paper("paper_902", "Beta Nets <b>", "NeurIPS", 2022),
                     _paper("paper_903", "Gamma Forests", "ICML", 2021)])
    session.add(RunORM(run_id="run-1", paper_id="paper_901", status="COMPLETED", exit_code=0, execution_time=3.5,
                       stdout="\n".join(f"line {i}" for i in range(30)), stderr="<script>x</script>",
                       timestamp=datetime(2026, 10, 1, tzinfo=UTC)))
    session.flush()
    session.add_all([_score("paper_901", 80.0, "Verified", "run-1"), _score("paper_902", 20.0, "Failed")])
    session.commit()
    session.close()
    return TestClient(create_app(url))


def _ids(html):
    import re
    return re.findall(r"href='/papers/(paper_\d+)'", html)


def test_default_order_is_best_score_first_and_unscored_last(client):
    assert _ids(client.get("/").text) == ["paper_901", "paper_902", "paper_903"]
    assert _ids(client.get("/?sort=score&dir=asc").text) == ["paper_902", "paper_901", "paper_903"]  # unscored still last


def test_sort_by_year_and_paper(client):
    assert _ids(client.get("/?sort=year&dir=asc").text) == ["paper_901", "paper_903", "paper_902"]
    assert _ids(client.get("/?sort=paper&dir=desc").text) == ["paper_903", "paper_902", "paper_901"]


def test_search_matches_title_and_venue_ignoring_case(client):
    assert _ids(client.get("/?q=gamma").text) == ["paper_903"]
    assert _ids(client.get("/?q=neurips").text) == ["paper_902"]
    assert NO_MATCH in client.get("/?q=nothing-like-this").text


def test_status_filter_including_not_scored(client):
    assert _ids(client.get("/?status=Verified").text) == ["paper_901"]
    assert _ids(client.get(f"/?status={NOT_SCORED}").text) == ["paper_903"]
    assert _ids(client.get("/?status=Needs Review").text) == []


def test_counts_come_from_the_database(client):
    assert "3 of 3 papers" in client.get("/").text and "2 scored" in client.get("/").text
    assert "1 of 3 papers" in client.get("/?q=alpha").text


def test_invalid_sort_is_rejected(client):
    assert client.get("/?sort=drop").status_code == 422 and client.get("/?dir=up").status_code == 422


def test_search_text_is_escaped_in_the_form_and_titles(client):
    page = client.get("/?q=%22%3E%3Cscript%3E").text
    assert "<script>" not in page and "&lt;script&gt;" in page
    assert "Beta Nets &lt;b&gt;" in client.get("/").text


def test_detail_page_shows_breakdown_and_log_excerpt(client):
    page = client.get("/papers/paper_901").text
    for value in ("Alpha Trees", "80", "11", "22", "33", "because", "COMPLETED", "3.5 s"):
        assert value in page
    assert "line 29" in page and "line 10\n" in page and "line 9\n" not in page  # last 20 lines only
    assert "&lt;script&gt;x&lt;/script&gt;" in page and "<script>x" not in page


def test_detail_page_of_an_unscored_unrun_paper_says_so(client):
    page = client.get("/papers/paper_903").text
    assert "no score is stored" in page and "has not been run" in page and "0.123456" not in page


def test_unknown_paper_gives_404_page(client):
    response = client.get("/papers/paper_000")
    assert response.status_code == 404 and "No paper paper_000" in response.text


def test_empty_database_shows_the_empty_state_not_a_table(tmp_path):
    page = TestClient(create_app(f"sqlite:///{(tmp_path / 'e.db').as_posix()}")).get("/").text
    assert EMPTY_STATE in page and "<table>" not in page
