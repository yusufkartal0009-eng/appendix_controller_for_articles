"""REST routes of the local dashboard (#37): papers, scores, and one run. Every value comes from the database.

Seed claim values (`papers.expected_claims`) are not exposed: they are hand-typed and unverified
(docs/CORPUS_VERIFICATION.md). An empty table gives an empty list; an unknown ID gives 404.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from src.database import get_session
from src.models import PaperBase, PaperORM, RunORM, ScoreORM, ScoreRead

STATUS_LABELS = ("Verified", "Partially Verified", "Needs Review", "Failed")

router = APIRouter(prefix="/api/v1")


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


class RunDetail(BaseModel):
    """One run with its logs and hashes, as stored."""

    model_config = ConfigDict(from_attributes=True)

    run_id: str
    paper_id: str
    status: str
    execution_time: float | None
    exit_code: int | None
    stdout: str | None
    stderr: str | None
    seed: int | None
    failure_category: str | None
    artifact_manifest_sha256: str | None
    outputs_sha256: str | None
    timestamp: datetime | None


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


def list_scores(engine: Engine, status_label: str | None = None) -> list[ScoreRead]:
    """All stored scores, best first (ties by paper ID). Optionally only one status label."""
    session = get_session(engine)
    try:
        query = select(ScoreORM).order_by(ScoreORM.total_score.desc(), ScoreORM.paper_id)
        if status_label is not None:
            query = query.where(ScoreORM.status_label == status_label)
        return [ScoreRead.model_validate(row) for row in session.execute(query).scalars()]
    finally:
        session.close()


def get_score(engine: Engine, paper_id: str) -> ScoreRead | None:
    session = get_session(engine)
    try:
        row = session.execute(select(ScoreORM).where(ScoreORM.paper_id == paper_id)).scalar_one_or_none()
        return ScoreRead.model_validate(row) if row is not None else None
    finally:
        session.close()


def get_run(engine: Engine, run_id: str) -> RunDetail | None:
    session = get_session(engine)
    try:
        row = session.get(RunORM, run_id)
        return RunDetail.model_validate(row) if row is not None else None
    finally:
        session.close()


@router.get("/papers", response_model=list[PaperSummary])
def papers(request: Request) -> list[PaperSummary]:
    return list_papers(request.app.state.engine)


@router.get("/scores", response_model=list[ScoreRead])
def scores(request: Request, status: str | None = Query(None, description="One of " + ", ".join(STATUS_LABELS))
           ) -> list[ScoreRead]:
    if status is not None and status not in STATUS_LABELS:
        raise HTTPException(status_code=422, detail=f"status must be one of {', '.join(STATUS_LABELS)}")
    return list_scores(request.app.state.engine, status)


@router.get("/scores/{paper_id}", response_model=ScoreRead)
def score(paper_id: str, request: Request) -> ScoreRead:
    found = get_score(request.app.state.engine, paper_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"No score for {paper_id}")
    return found


@router.get("/runs/{run_id}", response_model=RunDetail)
def run(run_id: str, request: Request) -> RunDetail:
    found = get_run(request.app.state.engine, run_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"No run {run_id}")
    return found
