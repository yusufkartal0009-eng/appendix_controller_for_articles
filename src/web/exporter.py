"""Exportable audit report of one paper, as Markdown and PDF (#40).

Layout chosen by the owner: one page with the summary on top, then the score breakdown, the latest run, the claims, and
the integrity hashes. Markdown and PDF are built from the same `Report` object, which is filled from the database only.
A paper without a score says "Not scored"; nothing is invented. The PDF uses a core font, so characters outside Latin-1
are replaced by "?".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.engine import Engine

from src.database import get_session
from src.models import ClaimORM, PaperORM, RunORM, ScoreORM

NOT_SCORED = "Not scored"
LOG_LINES = 20


@dataclass
class ClaimRow:
    metric: str
    claimed: float
    reproduced: float | None
    tolerance: float
    matches: bool | None


@dataclass
class Report:
    paper_id: str
    title: str
    venue: str
    year: int
    repo_url: str
    paper_url: str | None
    generated_at: datetime
    score_total: float | None = None
    status_label: str | None = None
    tiers: list[tuple[str, float]] = field(default_factory=list)
    score_summary: str | None = None
    run: dict[str, str] | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    claims: list[ClaimRow] = field(default_factory=list)
    hashes: dict[str, str | None] = field(default_factory=dict)

    @property
    def headline(self) -> str:
        if self.score_total is None:
            return NOT_SCORED
        return f"Score {self.score_total:g} / 100 - {self.status_label}"


def _tail(text: str | None) -> str:
    return "\n".join((text or "").splitlines()[-LOG_LINES:])


def build_report(engine: Engine, paper_id: str, generated_at: datetime) -> Report | None:
    """Read everything from the database. None if the paper does not exist."""
    session = get_session(engine)
    try:
        paper = session.get(PaperORM, paper_id)
        if paper is None:
            return None
        report = Report(paper_id=paper.paper_id, title=paper.title, venue=paper.venue, year=paper.year,
                        repo_url=paper.repo_url, paper_url=paper.paper_url, generated_at=generated_at)
        score = session.execute(select(ScoreORM).where(ScoreORM.paper_id == paper_id)).scalar_one_or_none()
        if score is not None:
            report.score_total, report.status_label, report.score_summary = (
                score.total_score, score.status_label, score.summary)
            report.tiers = [("Build (tier 1)", score.tier1_build), ("Metrics (tier 2)", score.tier2_metrics),
                            ("Stability (tier 3)", score.tier3_stability), ("Artifacts (tier 4)", score.tier4_artifacts)]
        run = session.execute(select(RunORM).where(RunORM.paper_id == paper_id)
                              .order_by(RunORM.timestamp.desc(), RunORM.run_id.desc())).scalars().first()
        if run is not None:
            report.run = {
                "Run": run.run_id, "Status": run.status,
                "Exit code": "-" if run.exit_code is None else str(run.exit_code),
                "Duration": "-" if run.execution_time is None else f"{run.execution_time:g} s",
                "Failure category": run.failure_category or "-", "Seed": "-" if run.seed is None else str(run.seed),
                "Started": "-" if run.timestamp is None else run.timestamp.isoformat(sep=" ", timespec="seconds"),
            }
            report.stdout_tail, report.stderr_tail = _tail(run.stdout), _tail(run.stderr)
            report.hashes = {"Outputs SHA-256": run.outputs_sha256, "Run manifest SHA-256": run.artifact_manifest_sha256}
        for claim in session.execute(select(ClaimORM).where(ClaimORM.paper_id == paper_id)
                                     .order_by(ClaimORM.claim_id)).scalars():
            report.claims.append(ClaimRow(claim.metric_name, claim.claimed_value, claim.reproduced_value,
                                          claim.tolerance, None if claim.matches is None else bool(claim.matches)))
        return report
    finally:
        session.close()


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _fence(text: str) -> str:
    """A code fence longer than any backtick run inside the text."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def _match_text(row: ClaimRow) -> str:
    return "not compared" if row.matches is None else ("yes" if row.matches else "no")


def _value(value: float | None) -> str:
    return "-" if value is None else f"{value:g}"


def to_markdown(report: Report) -> str:
    lines = [f"# Reproducibility audit: {report.paper_id}", "",
             f"{report.title} ({report.venue}, {report.year})", "",
             f"Generated {report.generated_at:%Y-%m-%d %H:%M} from the project database.", "",
             "## Summary", "", report.headline, ""]
    if report.score_summary:
        lines += [report.score_summary, ""]
    lines += ["## Score breakdown", ""]
    if report.tiers:
        lines += ["| Part | Score (0-100) |", "|---|---|"]
        lines += [f"| {_cell(name)} | {value:g} |" for name, value in report.tiers]
        lines += [f"| **Total** | **{report.score_total:g}** |"]
    else:
        lines += ["No score is stored for this paper."]
    lines += ["", "## Latest run", ""]
    if report.run is None:
        lines += ["This paper has not been run."]
    else:
        lines += ["| Field | Value |", "|---|---|"] + [f"| {key} | {_cell(value)} |" for key, value in report.run.items()]
        for name, text in (("Standard output", report.stdout_tail), ("Standard error", report.stderr_tail)):
            if text:
                fence = _fence(text)
                lines += ["", f"{name} (last {LOG_LINES} lines):", "", fence, text, fence]
    lines += ["", "## Claims", ""]
    if report.claims:
        lines += ["| Metric | Claimed | Reproduced | Tolerance | Match |", "|---|---|---|---|---|"]
        lines += [f"| {_cell(c.metric)} | {_value(c.claimed)} | {_value(c.reproduced)} | {_value(c.tolerance)} | "
                  f"{_match_text(c)} |" for c in report.claims]
    else:
        lines += ["No claim comparison is stored for this paper."]
    lines += ["", "## Integrity", ""]
    if report.hashes:
        lines += [f"- {key}: `{value or 'not recorded'}`" for key, value in report.hashes.items()]
    else:
        lines += ["No run, so no hashes."]
    lines += ["", "## Links", "", f"- Repository: {report.repo_url}", f"- Paper: {report.paper_url or '-'}", ""]
    return "\n".join(lines)


def _latin1(text: str) -> str:
    return text.encode("latin-1", "replace").decode("latin-1")


def to_pdf(report: Report) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title(_latin1(f"Reproducibility audit: {report.paper_id}"))
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    def heading(text: str) -> None:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(width, 7, _latin1(text), new_x="LMARGIN", new_y="NEXT")

    def paragraph(text: str, size: int = 10, style: str = "") -> None:
        pdf.set_font("Helvetica", style, size)
        pdf.multi_cell(width, 5, _latin1(text), new_x="LMARGIN", new_y="NEXT")

    def table(rows: list[list[str]], widths: list[float]) -> None:
        pdf.set_font("Helvetica", "", 9)
        for i, row in enumerate(rows):
            pdf.set_font("Helvetica", "B" if i == 0 else "", 9)
            for text, w in zip(row, widths, strict=True):
                pdf.cell(width * w, 6, _latin1(text)[:60], border=1)
            pdf.ln()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(width, 9, _latin1(f"Reproducibility audit: {report.paper_id}"), new_x="LMARGIN", new_y="NEXT")
    paragraph(f"{report.title} ({report.venue}, {report.year})")
    paragraph(f"Generated {report.generated_at:%Y-%m-%d %H:%M} from the project database.", 9)
    heading("Summary")
    paragraph(report.headline, 11, "B")
    if report.score_summary:
        paragraph(report.score_summary)
    heading("Score breakdown")
    if report.tiers:
        table([["Part", "Score (0-100)"]] + [[n, f"{v:g}"] for n, v in report.tiers] + [["Total", f"{report.score_total:g}"]],
              [0.6, 0.4])
    else:
        paragraph("No score is stored for this paper.")
    heading("Latest run")
    if report.run is None:
        paragraph("This paper has not been run.")
    else:
        table([["Field", "Value"]] + [[k, v] for k, v in report.run.items()], [0.3, 0.7])
        for name, text in (("Standard output", report.stdout_tail), ("Standard error", report.stderr_tail)):
            if text:
                pdf.ln(2)
                paragraph(f"{name} (last {LOG_LINES} lines):", 9, "B")
                pdf.set_font("Courier", "", 7)
                pdf.multi_cell(width, 3.5, _latin1(text), new_x="LMARGIN", new_y="NEXT")
    heading("Claims")
    if report.claims:
        table([["Metric", "Claimed", "Reproduced", "Tolerance", "Match"]]
              + [[c.metric, _value(c.claimed), _value(c.reproduced), _value(c.tolerance), _match_text(c)]
                 for c in report.claims], [0.3, 0.17, 0.17, 0.17, 0.19])
    else:
        paragraph("No claim comparison is stored for this paper.")
    heading("Integrity")
    if report.hashes:
        for key, value in report.hashes.items():
            paragraph(f"{key}:", 9, "B")
            pdf.set_font("Courier", "", 7)
            pdf.multi_cell(width, 3.5, _latin1(value or "not recorded"), new_x="LMARGIN", new_y="NEXT")
    else:
        paragraph("No run, so no hashes.")
    heading("Links")
    paragraph(f"Repository: {report.repo_url}\nPaper: {report.paper_url or '-'}", 9)
    return bytes(pdf.output())
