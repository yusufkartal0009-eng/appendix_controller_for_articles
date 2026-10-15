"""Local dashboard (D0 skeleton #170; API routes in src/web/routes.py, #37; pages in src/web/pages.py, #38). Local only.

Every value the API and the pages show comes from the database. Seed claim values (`papers.expected_claims`) are not
exposed: they are hand-typed and unverified (docs/CORPUS_VERIFICATION.md), and the dashboard must not show such numbers.
"""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from src.database import get_engine, init_db
from src.web.pages import (
    EMPTY_STATE,
    build_rows,
    render_detail,
    render_leaderboard,
    render_not_found,
)
from src.web.routes import router

__all__ = ["EMPTY_STATE", "create_app"]


def create_app(db_url: str | None = None) -> FastAPI:
    engine = get_engine(db_url)
    init_db(engine)  # creates missing tables; never deletes data
    app = FastAPI(title="Repro Radar (local)", docs_url="/docs", redoc_url=None)

    app.include_router(router)

    @app.get("/", response_class=HTMLResponse)
    def index(q: str = Query("", max_length=200), status: str = Query("", max_length=40),
              sort: str = Query("score", pattern="^(paper|year|score)$"),
              dir: str = Query("desc", pattern="^(asc|desc)$")) -> str:
        return render_leaderboard(build_rows(engine), q, status, sort, dir == "desc")

    @app.get("/papers/{paper_id}", response_class=HTMLResponse)
    def paper_detail(paper_id: str) -> HTMLResponse:
        page = render_detail(engine, paper_id)
        if page is None:
            return HTMLResponse(render_not_found(paper_id), status_code=404)
        return HTMLResponse(page)

    app.state.engine = engine
    return app
