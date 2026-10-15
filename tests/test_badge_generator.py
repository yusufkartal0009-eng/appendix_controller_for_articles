"""SVG badges (#39, #41): colors, text, escaping, 'not scored', caching, 404."""

import json
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from src.database import get_engine, get_session, init_db
from src.models import PaperORM, ScoreORM
from src.web.app import create_app
from src.web.badge_generator import (
    COLORS,
    NOT_SCORED_COLOR,
    badge_etag,
    format_value,
    render_badge,
)


@pytest.mark.parametrize("status", list(COLORS))
def test_each_status_has_its_own_color_and_the_score_in_the_text(status):
    text, color = format_value(72.5, status)
    assert text == f"72.5 · {status}" and color == COLORS[status]
    assert len(set(COLORS.values())) == len(COLORS)


def test_no_score_gives_a_gray_not_scored_badge_without_a_number():
    for args in ((None, None), (None, "Verified"), (50.0, None)):
        text, color = format_value(*args)
        assert text == "not scored" and color == NOT_SCORED_COLOR


def test_whole_scores_have_no_decimal_point():
    assert format_value(80.0, "Verified")[0] == "80 · Verified"


def test_the_badge_is_well_formed_svg_with_an_accessible_label():
    svg = render_badge(80.0, "Verified")
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg") and root.get("role") == "img"
    assert root.get("aria-label") == "repro radar: 80 · Verified"
    assert "repro radar" in svg and COLORS["Verified"] in svg


def test_text_is_escaped():
    svg = render_badge(1.0, "<script>alert(1)</script>")
    assert "<script>" not in svg
    ET.fromstring(svg)  # still well formed


def test_the_badge_is_wider_for_longer_text():
    assert int(ET.fromstring(render_badge(80.0, "Partially Verified")).get("width")) > int(
        ET.fromstring(render_badge(80.0, "Failed")).get("width"))


def test_the_etag_follows_the_content():
    assert badge_etag(render_badge(80.0, "Verified")) == badge_etag(render_badge(80.0, "Verified"))
    assert badge_etag(render_badge(80.0, "Verified")) != badge_etag(render_badge(79.0, "Verified"))


@pytest.fixture
def client(tmp_path):
    url = f"sqlite:///{(tmp_path / 'b.db').as_posix()}"
    engine = get_engine(url)
    init_db(engine)
    session = get_session(engine)
    for paper_id in ("paper_901", "paper_902"):
        session.add(PaperORM(paper_id=paper_id, title="A Test Paper", year=2021, venue="V", repo_url="https://example.org/r",
                             paper_url=None, license="MIT", target_script="m.py", expected_claims=json.dumps({}),
                             source_table_or_section="{}"))
    session.flush()
    session.add(ScoreORM(score_id="s1", paper_id="paper_901", tier1_build=80.0, tier2_metrics=0.0, tier3_stability=0.0,
                         tier4_artifacts=0.0, total_score=80.0, status_label="Verified"))
    session.commit()
    session.close()
    return TestClient(create_app(url))


def test_endpoint_serves_the_stored_score_as_svg(client):
    response = client.get("/api/v1/badges/paper_901.svg")
    assert response.status_code == 200 and response.headers["content-type"].startswith("image/svg+xml")
    assert "80 · Verified" in response.text and COLORS["Verified"] in response.text


def test_a_paper_without_a_score_gets_the_not_scored_badge(client):
    response = client.get("/api/v1/badges/paper_902.svg")
    assert response.status_code == 200 and "not scored" in response.text and NOT_SCORED_COLOR in response.text


def test_unknown_paper_gives_404(client):
    assert client.get("/api/v1/badges/paper_000.svg").status_code == 404


def test_responses_are_cacheable_and_answer_304_for_an_unchanged_badge(client):
    first = client.get("/api/v1/badges/paper_901.svg")
    assert "max-age" in first.headers["cache-control"] and first.headers["etag"]
    second = client.get("/api/v1/badges/paper_901.svg", headers={"If-None-Match": first.headers["etag"]})
    assert second.status_code == 304 and second.content == b""


def test_a_changed_score_changes_the_etag(client, tmp_path):
    first = client.get("/api/v1/badges/paper_901.svg").headers["etag"]
    session = get_session(client.app.state.engine)
    row = session.get(ScoreORM, "s1")
    row.total_score, row.status_label = 20.0, "Failed"
    session.commit()
    session.close()
    changed = client.get("/api/v1/badges/paper_901.svg", headers={"If-None-Match": first})
    assert changed.status_code == 200 and "20 · Failed" in changed.text


def test_the_badge_route_is_in_the_openapi_documentation(client):
    assert "/api/v1/badges/{paper_id}.svg" in client.get("/openapi.json").json()["paths"]
