"""Server-rendered pages of the local dashboard (#38): the leaderboard and a paper's detail page.

Design chosen by the owner: option A (light colors, plain table, system font), one table, a search box and a status
menu, sorting by column header, and a separate detail page. The markup holds no data; every value comes from the
database through `src/web/routes.py`. Filters and sorting are URL query parameters, so a view can be linked.
"""

from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from pydantic import BaseModel
from sqlalchemy.engine import Engine

from src.web.routes import (
    STATUS_LABELS,
    LatestRun,
    PaperSummary,
    get_run,
    get_score,
    list_papers,
    list_scores,
)

NOT_SCORED = "Not scored"
STATUS_CHOICES = (*STATUS_LABELS, NOT_SCORED)
SORT_KEYS = ("paper", "year", "score")
LOG_EXCERPT_LINES = 20
EMPTY_STATE = "No data yet. Run <code>python cli.py init-db</code> to load the seed papers."
NO_MATCH = "No paper matches this search and filter."

PAGE_CSS = """
body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#f6f7f9;color:#1f2328;margin:0}
header{background:#fff;border-bottom:1px solid #d0d7de;padding:16px 32px}
h1{font-size:20px;margin:0}h1 a{color:inherit;text-decoration:none}
h2{font-size:16px;margin:24px 0 8px}
header p{margin:4px 0 0;color:#57606a;font-size:13px}
main{padding:24px 32px}
form.filters{display:flex;gap:8px;margin-bottom:16px}
form.filters input,form.filters select,form.filters button{font:inherit;font-size:14px;padding:6px 10px;
border:1px solid #d0d7de;border-radius:6px;background:#fff}
form.filters input[type=search]{min-width:280px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #d0d7de}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid #eaeef2;font-size:14px;vertical-align:top}
th{background:#f6f8fa;font-weight:600;color:#57606a}th a{color:inherit;text-decoration:none}
td.num{text-align:right;font-variant-numeric:tabular-nums}
a{color:#0969da}
.badge{white-space:nowrap;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;background:#eaeef2;color:#57606a}
.badge.FAILED,.badge.TIMEOUT,.badge.OOM_KILLED,.badge.OUTPUT_LIMIT_EXCEEDED,.badge.s-Failed{background:#ffebe9;color:#cf222e}
.badge.COMPLETED,.badge.s-Verified{background:#dafbe1;color:#1a7f37}
.badge.s-Partially-Verified{background:#fff8c5;color:#9a6700}
.badge.s-Needs-Review{background:#ddf4ff;color:#0969da}
.cat{display:block;margin-top:4px;color:#57606a;font-size:12px}
.count{margin-top:12px;color:#57606a;font-size:13px}
.empty{background:#fff;border:1px dashed #d0d7de;border-radius:6px;padding:48px;text-align:center;color:#57606a}
dl{display:grid;grid-template-columns:160px 1fr;gap:6px 16px;background:#fff;border:1px solid #d0d7de;padding:16px;margin:0}
dt{color:#57606a;font-size:13px}dd{margin:0;font-size:14px}
pre{background:#fff;border:1px solid #d0d7de;padding:12px;overflow:auto;font-size:12px;max-height:320px}
.back{display:inline-block;margin-bottom:16px;font-size:14px}
"""


class Row(BaseModel):
    """One leaderboard row: a paper, its stored score (or None), and its latest run."""

    paper: PaperSummary
    score_total: float | None
    status: str


def build_rows(engine: Engine) -> list[Row]:
    scores = {s.paper_id: s for s in list_scores(engine)}
    rows = []
    for paper in list_papers(engine):
        score = scores.get(paper.paper_id)
        rows.append(Row(paper=paper, score_total=score.total_score if score else None,
                        status=score.status_label if score else NOT_SCORED))
    return rows


def select_rows(rows: list[Row], q: str = "", status: str = "", sort: str = "score", descending: bool = True
                ) -> list[Row]:
    """Filter by title/venue text and status, then sort. Papers without a score always come last when sorting by score."""
    needle = q.strip().lower()
    if needle:
        rows = [r for r in rows if needle in r.paper.title.lower() or needle in r.paper.venue.lower()]
    if status:
        rows = [r for r in rows if r.status == status]
    if sort == "year":
        return sorted(rows, key=lambda r: (r.paper.year, r.paper.paper_id), reverse=descending)
    if sort == "paper":
        return sorted(rows, key=lambda r: r.paper.paper_id, reverse=descending)
    scored = sorted((r for r in rows if r.score_total is not None),
                    key=lambda r: (r.score_total, r.paper.paper_id), reverse=descending)
    return scored + [r for r in rows if r.score_total is None]


def _run_cell(run: LatestRun | None) -> str:
    if run is None:
        return "<span class='badge'>NOT RUN</span>"
    category = f"<span class='cat'>{escape(run.failure_category)}</span>" if run.failure_category else ""
    return f"<span class='badge {escape(run.status)}'>{escape(run.status)}</span>{category}"


def _status_badge(status: str) -> str:
    css = "s-" + status.replace(" ", "-")
    return f"<span class='badge {escape(css)}'>{escape(status)}</span>"


def _score_text(value: float | None) -> str:
    return "&ndash;" if value is None else f"{value:g}"


def _layout(title: str, body: str) -> str:
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<title>{escape(title)}</title><meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<style>{PAGE_CSS}</style></head><body><header><h1><a href='/'>Repro Radar</a></h1>"
            "<p>Local dashboard &middot; data from the project database</p></header>"
            f"<main>{body}</main></body></html>")


def _header_link(label: str, key: str, q: str, status: str, sort: str, descending: bool) -> str:
    next_desc = not descending if sort == key else key != "paper"
    params = {k: v for k, v in (("q", q), ("status", status)) if v}
    params.update({"sort": key, "dir": "desc" if next_desc else "asc"})
    arrow = (" &#9660;" if descending else " &#9650;") if sort == key else ""
    return f"<a href='/?{escape(urlencode(params))}'>{label}{arrow}</a>"


def render_leaderboard(rows: list[Row], q: str = "", status: str = "", sort: str = "score",
                       descending: bool = True) -> str:
    if not rows:
        return _layout("Repro Radar", f"<div class='empty'><h2>No papers</h2><p>{EMPTY_STATE}</p></div>")
    shown = select_rows(rows, q, status, sort, descending)
    options = "".join(
        f"<option value='{escape(c)}'{' selected' if c == status else ''}>{escape(c)}</option>"
        for c in STATUS_CHOICES)
    form = ("<form class='filters' method='get' action='/'>"
            f"<input type='search' name='q' value='{escape(q)}' placeholder='Search title or venue'>"
            f"<select name='status'><option value=''>Status: All</option>{options}</select>"
            f"<input type='hidden' name='sort' value='{escape(sort)}'>"
            f"<input type='hidden' name='dir' value='{'desc' if descending else 'asc'}'>"
            "<button type='submit'>Apply</button></form>")
    link = lambda label, key: _header_link(label, key, q, status, sort, descending)
    head = (f"<tr><th>{link('Paper', 'paper')}</th><th>Title</th><th>Venue</th><th>{link('Year', 'year')}</th>"
            f"<th>{link('Score', 'score')}</th><th>Status</th><th>Latest run</th></tr>")
    if shown:
        body_rows = "".join(
            f"<tr><td><a href='/papers/{escape(r.paper.paper_id)}'>{escape(r.paper.paper_id)}</a></td>"
            f"<td>{escape(r.paper.title)}</td><td>{escape(r.paper.venue)}</td><td>{r.paper.year}</td>"
            f"<td class='num'>{_score_text(r.score_total)}</td><td>{_status_badge(r.status)}</td>"
            f"<td>{_run_cell(r.paper.latest_run)}</td></tr>" for r in shown)
        table = f"<table>{head}{body_rows}</table>"
    else:
        table = f"<div class='empty'><p>{NO_MATCH}</p></div>"
    scored = sum(1 for r in rows if r.score_total is not None)
    count = f"<p class='count'>{len(shown)} of {len(rows)} papers &middot; {scored} scored</p>"
    return _layout("Repro Radar", form + table + count)


def _safe_link(url: str | None) -> str:
    if not url or not url.startswith(("https://", "http://")):
        return "&ndash;"
    return f"<a href='{escape(url)}' rel='noopener noreferrer'>{escape(url)}</a>"


def _excerpt(text: str | None) -> str:
    lines = (text or "").splitlines()
    return "\n".join(lines[-LOG_EXCERPT_LINES:])


def render_detail(engine: Engine, paper_id: str) -> str | None:
    """The detail page of one paper, or None if the paper does not exist."""
    paper = next((p for p in list_papers(engine) if p.paper_id == paper_id), None)
    if paper is None:
        return None
    score = get_score(engine, paper_id)
    facts = (f"<dl><dt>Paper</dt><dd>{escape(paper.paper_id)}</dd><dt>Venue</dt><dd>{escape(paper.venue)}, {paper.year}</dd>"
             f"<dt>License</dt><dd>{escape(paper.license)}</dd><dt>Paper link</dt><dd>{_safe_link(paper.paper_url)}</dd>"
             f"<dt>Repository</dt><dd>{_safe_link(paper.repo_url)}</dd></dl>")
    if score is None:
        score_html = f"<div class='empty'><p>{NOT_SCORED}: no score is stored for this paper yet.</p></div>"
    else:
        tiers = (("Build (tier 1)", score.tier1_build), ("Metrics (tier 2)", score.tier2_metrics),
                 ("Stability (tier 3)", score.tier3_stability), ("Artifacts (tier 4)", score.tier4_artifacts),
                 ("Total", score.total_score))
        cells = "".join(f"<tr><td>{label}</td><td class='num'>{value:g}</td></tr>" for label, value in tiers)
        summary = f"<p>{escape(score.summary)}</p>" if score.summary else ""
        score_html = (f"<p>{_status_badge(score.status_label)}</p><table><tr><th>Part</th><th>Score (0-100)</th></tr>"
                      f"{cells}</table>{summary}")
    run_html = "<div class='empty'><p>This paper has not been run.</p></div>"
    if paper.latest_run is not None:
        run = get_run(engine, paper.latest_run.run_id)
        if run is not None:
            seconds = "&ndash;" if run.execution_time is None else f"{run.execution_time:g} s"
            run_html = (f"<dl><dt>Run</dt><dd>{escape(run.run_id)}</dd><dt>Status</dt><dd>{_run_cell(paper.latest_run)}</dd>"
                        f"<dt>Exit code</dt><dd>{'&ndash;' if run.exit_code is None else run.exit_code}</dd>"
                        f"<dt>Duration</dt><dd>{seconds}</dd></dl>")
            for name, text in (("Standard output", run.stdout), ("Standard error", run.stderr)):
                if text:
                    run_html += f"<h2>{name} (last {LOG_EXCERPT_LINES} lines)</h2><pre>{escape(_excerpt(text))}</pre>"
    body = (f"<a class='back' href='/'>&larr; Back to the list</a><h2 style='margin-top:0'>{escape(paper.title)}</h2>"
            f"{facts}<p><a href='/api/v1/papers/{escape(paper.paper_id)}/report.md'>Download report (Markdown)</a> &middot; "
            f"<a href='/api/v1/papers/{escape(paper.paper_id)}/report.pdf'>Download report (PDF)</a></p>"
            f"<h2>Score</h2>{score_html}<h2>Latest run</h2>{run_html}")
    return _layout(f"{paper.paper_id} - Repro Radar", body)


def render_not_found(paper_id: str) -> str:
    return _layout("Not found - Repro Radar",
                   f"<a class='back' href='/'>&larr; Back to the list</a><div class='empty'><h2>Not found</h2>"
                   f"<p>No paper {escape(paper_id)}.</p></div>")
