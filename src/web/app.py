"""D0 dashboard skeleton (#170): one endpoint backed by a real database query, local only.

Every value the API returns comes from the database. Seed claim values (`papers.expected_claims`) are not exposed:
they are hand-typed and unverified (docs/CORPUS_VERIFICATION.md), and the dashboard must not show such numbers.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from src.database import get_engine, get_session, init_db
from src.models import PaperBase, PaperORM, RunORM


class LatestRun(BaseModel):
    """The most recent run of a paper, as stored in the `runs` table."""

    model_config = ConfigDict(from_attributes=True)

    run_id: str
    status: str
    exit_code: int | None
    failure_category: str | None
    timestamp: datetime | None


# The catalog fields of src/models.py:PaperBase, without the unverified seed claims.
_CATALOG_FIELDS = ("paper_id", "title", "year", "venue", "repo_url", "paper_url", "license", "target_script")


class PaperSummary(BaseModel):
    """One paper as the dashboard lists it."""

    model_config = ConfigDict(from_attributes=True)

    paper_id: str
    title: str
    year: int
    venue: str
    repo_url: str
    paper_url: str | None
    license: str
    target_script: str
    latest_run: LatestRun | None


assert set(_CATALOG_FIELDS) <= set(PaperBase.model_fields)  # keep the summary in step with the shared schema


def list_papers(engine: Engine) -> list[PaperSummary]:
    """All papers, ordered by ID, each with its latest run (or None). An empty database gives []."""
    session = get_session(engine)
    try:
        latest = (
            select(RunORM.paper_id, func.max(RunORM.timestamp).label("ts")).group_by(RunORM.paper_id).subquery()
        )
        runs = {
            run.paper_id: run
            for run in session.execute(
                select(RunORM).join(latest, (RunORM.paper_id == latest.c.paper_id) & (RunORM.timestamp == latest.c.ts))
            ).scalars()
        }
        papers = session.execute(select(PaperORM).order_by(PaperORM.paper_id)).scalars().all()
        return [
            PaperSummary(
                **{name: getattr(paper, name) for name in _CATALOG_FIELDS},
                latest_run=LatestRun.model_validate(runs[paper.paper_id]) if paper.paper_id in runs else None,
            )
            for paper in papers
        ]
    finally:
        session.close()


def create_app(db_url: str | None = None) -> FastAPI:
    engine = get_engine(db_url)
    init_db(engine)  # creates missing tables; never deletes data
    app = FastAPI(title="Repro Radar (local)", docs_url="/docs", redoc_url=None)

    @app.get("/api/v1/papers", response_model=list[PaperSummary])
    def get_papers() -> list[PaperSummary]:
        return list_papers(engine)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return render_page(list_papers(engine))

    app.state.engine = engine
    return app


# ---------------------------------------------------------------------------------------------------------------------
# Page (owner's choice on 2026-10-04: option A, a light, plain table with the system font). Rendered on the server from
# the same query as the API; the template contains no data.

PAGE_CSS = """
body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#f6f7f9;color:#1f2328;margin:0}
header{background:#fff;border-bottom:1px solid #d0d7de;padding:16px 32px}
h1{font-size:20px;margin:0}
header p{margin:4px 0 0;color:#57606a;font-size:13px}
main{padding:24px 32px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #d0d7de}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid #eaeef2;font-size:14px;vertical-align:top}
th{background:#f6f8fa;font-weight:600;color:#57606a}
.badge{padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;background:#eaeef2;color:#57606a}
.badge.FAILED,.badge.TIMEOUT,.badge.OOM_KILLED,.badge.OUTPUT_LIMIT_EXCEEDED{background:#ffebe9;color:#cf222e}
.badge.COMPLETED{background:#dafbe1;color:#1a7f37}
.cat{display:block;margin-top:4px;color:#57606a;font-size:12px}
.empty{background:#fff;border:1px dashed #d0d7de;border-radius:6px;padding:48px;text-align:center;color:#57606a}
"""

EMPTY_STATE = "No data yet. Run <code>python cli.py init-db</code> to load the seed papers."


def _run_cell(run: LatestRun | None) -> str:
    if run is None:
        return "<span class='badge'>NOT RUN</span>"
    category = f"<span class='cat'>{escape(run.failure_category)}</span>" if run.failure_category else ""
    return f"<span class='badge {escape(run.status)}'>{escape(run.status)}</span>{category}"


def render_page(papers: list[PaperSummary]) -> str:
    if papers:
        rows = "".join(
            f"<tr><td>{escape(p.paper_id)}</td><td>{escape(p.title)}</td><td>{escape(p.venue)}</td>"
            f"<td>{p.year}</td><td>{escape(p.license)}</td><td>{_run_cell(p.latest_run)}</td></tr>"
            for p in papers
        )
        body = ("<table><tr><th>Paper</th><th>Title</th><th>Venue</th><th>Year</th><th>License</th>"
                f"<th>Latest run</th></tr>{rows}</table>")
    else:
        body = f"<div class='empty'><h2>No papers</h2><p>{EMPTY_STATE}</p></div>"
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Repro Radar</title>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'><style>{PAGE_CSS}</style></head>"
            "<body><header><h1>Repro Radar</h1><p>Local dashboard &middot; data from the project database</p></header>"
            f"<main>{body}</main></body></html>")
