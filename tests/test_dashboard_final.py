"""The final dashboard (#548): reasons beside the label, 'Why this label', the control apart, /failures, the footer."""

import json

import pytest
from fastapi.testclient import TestClient

from scripts import build_demo_db
from scripts import failure_statistics as fs
from src.database import get_engine, get_session, init_db
from src.models import PaperORM, ScoreORM
from src.score_explanation import build_explanation, get_explanations, save_explanation
from src.web.app import create_app
from src.web.pages import CONTROL_BADGE, NEEDS_REVIEW_NOTE


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    path = tmp_path_factory.mktemp("demo") / "demo.db"
    build_demo_db.build(build_demo_db.DEFAULT_DATA, path)
    return TestClient(create_app(f"sqlite:///{path.as_posix()}"))


def test_the_list_says_whether_a_claim_was_compared(demo):
    html = demo.get("/").text
    assert "Claim compared: yes (1 of 3) &middot; Tier 2: 100" in html
    assert "Claim compared: no &middot; Tier 2: 70 (baseline, nothing compared)" in html
    assert "Run failed (MISSING_DEPENDENCY); no claim compared" in html


def test_a_run_with_nothing_compared_is_needs_review_in_the_list(demo):
    html = demo.get("/").text
    row = html[html.index("paper_006"):]
    assert "Needs Review" in row[:900]


def test_the_control_is_listed_apart_with_its_badge_and_not_counted(demo):
    html = demo.get("/").text
    assert html.count(CONTROL_BADGE) >= 2
    assert html.index("Known-answer control") > html.index("paper_103")
    assert "12 of 12 papers" in html and "1 known-answer control listed apart" in html


def test_the_footer_names_the_build_the_scorer_and_needs_review(demo):
    html = demo.get("/").text
    assert "Demo database built from stored runs on 20" in html and "src/scoring.py" in html and "not a success rate" in html
    assert NEEDS_REVIEW_NOTE in html


def test_the_paper_page_explains_the_label_with_the_numbers_of_paper_003(demo):
    html = demo.get("/papers/paper_003").text
    assert "Why this label" in html and "ft_transformer_rmse" in html
    assert "0.459" in html and "0.473" in html and "3.05 %" in html
    assert "no counterpart" in html and "resnet_rmse" in html
    assert "from 3 stored seed runs" in html and "<code>rmse</code>" in html and "Pilot 3" in html
    assert "Run of this score" in html  # the run panel shows the run that was scored (bug hunt suspicion 4, #513)


def test_the_paper_page_says_when_tier_2_is_only_a_baseline(demo):
    html = demo.get("/papers/paper_006").text
    assert "Claim compared: <strong>no</strong>" in html and "neutral baseline" in html and "not a measurement" in html
    assert "no counterpart" in html


def test_a_failed_paper_shows_its_category_and_a_quoted_line_in_neutral_words(demo):
    html = demo.get("/papers/paper_103").text
    assert "Recorded failure category: <strong>MISSING_DEPENDENCY</strong>" in html and "class='quote'" in html
    assert "Could not find a version" in html


def test_the_control_page_carries_the_badge(demo):
    assert CONTROL_BADGE in demo.get("/papers/synthetic_control").text


def test_unknown_paper_is_still_404_and_the_empty_state_is_kept(tmp_path):
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'e.db').as_posix()}"))
    assert client.get("/papers/nope").status_code == 404
    assert "python cli.py init-db" in client.get("/").text


def test_a_database_without_explanations_still_renders(tmp_path):
    engine = get_engine(f"sqlite:///{(tmp_path / 'x.db').as_posix()}")
    init_db(engine)
    session = get_session(engine)
    session.add(PaperORM(paper_id="paper_1", title="T", year=2021, venue="V", repo_url="https://e.org", paper_url=None, license="MIT",
                         target_script="m.py", expected_claims="{}", source_table_or_section="{}"))
    session.flush()
    session.add(ScoreORM(score_id="s", paper_id="paper_1", tier1_build=1, tier2_metrics=1, tier3_stability=1, tier4_artifacts=1,
                         total_score=1, status_label="Failed", summary="x"))
    session.commit()
    session.close()
    assert get_explanations(engine) == {}  # reading creates no table
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'x.db').as_posix()}"))
    assert client.get("/").status_code == 200 and client.get("/papers/paper_1").status_code == 200
    assert "Why this label" not in client.get("/papers/paper_1").text


def test_failures_page_shows_the_stored_tables_and_the_warning(tmp_path):
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'f.db').as_posix()}"))
    html = client.get("/failures").text
    stored = json.loads(fs.OUT_JSON.read_text(encoding="utf-8"))
    assert "Selection bias" in html and "selected, not sampled" in html and "not a success rate" in html
    for table in stored["tables"].values():
        assert table["title"].replace("&", "&amp;") in html or table["title"] in html
    assert "Pilots 1 to 4" in html and "24 runs counted" in html and "25.0%" in html


def test_failures_page_without_the_file_is_an_empty_state(tmp_path):
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'g.db').as_posix()}", failure_statistics=tmp_path / "missing.json"))
    response = client.get("/failures")
    assert response.status_code == 200 and "No failure statistics yet" in response.text


def test_failures_page_computes_nothing(tmp_path):
    doc = {"selection_warning": ["w"], "categories": [{"name": "x", "meaning": "m"}],
           "tables": {"t": {"title": "T", "attempts": 7, "failed": 3, "counts": {"x": 3}, "share_of_failed": {"x": 0.123456},
                            "sources": ["s"], "rows": []}}}
    path = tmp_path / "f.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    html = TestClient(create_app(f"sqlite:///{(tmp_path / 'h.db').as_posix()}", failure_statistics=path)).get("/failures").text
    assert "12.3%" in html and "7 runs counted" in html and "3 failed" in html


def test_an_explanation_round_trips_and_marks_a_baseline(tmp_path):
    from src.scoring import ReproducibilityScorer
    result = ReproducibilityScorer.evaluate_paper_run("p", True, True, True, 0, {}, {"acc": 0.9}, "MIT")
    result["claim_mapping"] = {"mapped": {}, "no_counterpart": {}}
    ex = build_explanation(result, {}, source="t", built_on="2026-01-01")
    assert ex["tier2"]["baseline"] and not ex["claim_compared"] and ex["tier3"]["source"] == "single_run_baseline"
    engine = get_engine(f"sqlite:///{(tmp_path / 'r.db').as_posix()}")
    save_explanation(engine, "p", ex)
    assert get_explanations(engine)["p"] == ex
