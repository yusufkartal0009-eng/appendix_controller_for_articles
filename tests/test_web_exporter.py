"""Audit report export (#40, #41): Markdown and PDF from one report object, empty states, escaping, downloads."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from src.database import get_engine, get_session, init_db
from src.models import ClaimORM, PaperORM, RunORM, ScoreORM
from src.web.app import create_app
from src.web.exporter import build_report, to_markdown, to_pdf

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def _paper(paper_id, title="A Test Paper | with pipe"):
    return PaperORM(paper_id=paper_id, title=title, year=2021, venue="Test Venue", repo_url="https://example.org/r",
                    paper_url=None, license="MIT", target_script="m.py", expected_claims=json.dumps({"rmse": 0.123456}),
                    source_table_or_section="{}")


@pytest.fixture
def engine(tmp_path):
    e = get_engine(f"sqlite:///{(tmp_path / 'x.db').as_posix()}")
    init_db(e)
    session = get_session(e)
    session.add_all([_paper("paper_901"), _paper("paper_902")])
    session.add(RunORM(run_id="run-1", paper_id="paper_901", status="COMPLETED", exit_code=0, execution_time=3.5,
                       stdout="```\nfence breaker\n```", stderr="warn — dash", outputs_sha256="ab" * 32,
                       timestamp=datetime(2026, 10, 1, tzinfo=UTC)))
    session.flush()
    session.add(ScoreORM(score_id="s1", paper_id="paper_901", run_id="run-1", tier1_build=80.0, tier2_metrics=40.0,
                         tier3_stability=20.0, tier4_artifacts=60.0, total_score=62.5, status_label="Partially Verified",
                         summary="because"))
    session.add(ClaimORM(claim_id="c1", paper_id="paper_901", run_id="run-1", metric_name="RMSE", claimed_value=0.459,
                         reproduced_value=0.473, tolerance=0.05, matches=1))
    session.add(ClaimORM(claim_id="c2", paper_id="paper_901", metric_name="MAE", claimed_value=0.3))
    session.commit()
    session.close()
    return e


def test_unknown_paper_has_no_report(engine):
    assert build_report(engine, "paper_000", NOW) is None


def test_markdown_has_every_section_with_values_from_the_database(engine):
    md = to_markdown(build_report(engine, "paper_901", NOW))
    for text in ("# Reproducibility audit: paper_901", "Generated 2026-10-15 12:00", "Score 62.5 / 100 - Partially Verified",
                 "because", "| Build (tier 1) | 80 |", "| **Total** | **62.5** |", "| Status | COMPLETED |", "| Duration | 3.5 s |",
                 "| RMSE | 0.459 | 0.473 | 0.05 | yes |", "| MAE | 0.3 | - | 0.05 | not compared |", "ab" * 32,
                 r"A Test Paper | with pipe (Test Venue, 2021)"):
        assert text in md, text
    assert "0.123456" not in md  # the unverified seed claim is never exported


def test_a_log_containing_a_code_fence_cannot_break_out(engine):
    md = to_markdown(build_report(engine, "paper_901", NOW))
    assert "````\n```\nfence breaker\n```\n````" in md


def test_unscored_unrun_paper_says_so_without_numbers(engine):
    md = to_markdown(build_report(engine, "paper_902", NOW))
    assert "Not scored" in md and "No score is stored" in md and "has not been run" in md
    assert "No claim comparison" in md and "No run, so no hashes" in md and "/ 100" not in md


def test_pdf_is_a_valid_one_page_document_with_the_same_content(engine):
    pdf = to_pdf(build_report(engine, "paper_901", NOW))
    assert pdf.startswith(b"%PDF")
    reader = PdfReader(__import__("io").BytesIO(pdf))
    text = "".join(page.extract_text() for page in reader.pages)
    assert len(reader.pages) <= 2
    for needle in ("Reproducibility audit: paper_901", "Score 62.5 / 100 - Partially Verified", "RMSE", "0.473", "ab" * 32):
        assert needle in text.replace("\n", ""), needle


def test_pdf_survives_characters_outside_latin1(engine):
    pdf = to_pdf(build_report(engine, "paper_901", NOW))  # stderr holds an em dash
    assert pdf.startswith(b"%PDF")
    pdf2 = to_pdf(build_report(engine, "paper_902", NOW))
    assert pdf2.startswith(b"%PDF")


def test_downloads_have_the_right_types_and_names(engine):
    client = TestClient(create_app(str(engine.url)))
    md = client.get("/api/v1/papers/paper_901/report.md")
    assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown")
    assert 'filename="paper_901_audit.md"' in md.headers["content-disposition"]
    pdf = client.get("/api/v1/papers/paper_901/report.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    assert 'filename="paper_901_audit.pdf"' in pdf.headers["content-disposition"]
    assert client.get("/api/v1/papers/paper_000/report.md").status_code == 404
    assert client.get("/api/v1/papers/paper_000/report.pdf").status_code == 404


def test_the_detail_page_links_to_both_downloads(engine):
    page = TestClient(create_app(str(engine.url))).get("/papers/paper_901").text
    assert "/api/v1/papers/paper_901/report.md" in page and "/api/v1/papers/paper_901/report.pdf" in page
