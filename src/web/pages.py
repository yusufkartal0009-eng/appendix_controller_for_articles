"""Server-rendered pages of the local dashboard (#38): the leaderboard and a paper's detail page.

Design chosen by the owner: option A (light colors, plain table, system font), one table, a search box and a status
menu, sorting by column header, and a separate detail page. The markup holds no data; every value comes from the
database through `src/web/routes.py`. Filters and sorting are URL query parameters, so a view can be linked.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from pydantic import BaseModel
from sqlalchemy.engine import Engine

from src.score_explanation import get_explanations
from src.web.routes import (
    STATUS_LABELS,
    LatestRun,
    PaperSummary,
    RunDetail,
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
NO_FAILURE_STATISTICS = ("No failure statistics yet. Run <code>python scripts/failure_statistics.py</code> to write "
                         "<code>data/failure_statistics.json</code>.")
CONTROL_BADGE = "not a paper: known-answer control"
NEEDS_REVIEW_NOTE = ("Needs Review also means that no accepted claim of the paper was compared with a number of the run: the run "
                     "may have built and run cleanly, but a person has to look at it, because nothing was checked against the paper.")

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
header nav{margin-top:8px;font-size:13px}header nav a{margin-right:16px}
.why{display:block;margin-top:4px;color:#57606a;font-size:12px}
.badge.control{background:#fff;border:1px dashed #8c959f;color:#57606a}
.note{background:#fff8c5;border:1px solid #d4a72c;border-radius:6px;padding:12px 16px;font-size:13px;margin:0 0 16px}
.note ul{margin:6px 0 0;padding-left:20px}
footer{padding:16px 32px 32px;color:#57606a;font-size:12px;max-width:960px}
.quote{border-left:3px solid #d0d7de;margin:8px 0;padding:4px 12px;color:#1f2328;font-family:ui-monospace,monospace;font-size:12px}
.sub{color:#57606a;font-size:13px;margin:4px 0 8px}
"""


class Row(BaseModel):
    """One leaderboard row: a paper, its stored score (or None), and its latest run."""

    paper: PaperSummary
    score_total: float | None
    status: str
    explanation: dict[str, Any] | None = None

    @property
    def is_control(self) -> bool:
        return bool(self.explanation and self.explanation.get("control"))


def build_rows(engine: Engine) -> list[Row]:
    scores = {s.paper_id: s for s in list_scores(engine)}
    explanations = get_explanations(engine)
    rows = []
    for paper in list_papers(engine):
        score = scores.get(paper.paper_id)
        rows.append(Row(paper=paper, score_total=score.total_score if score else None,
                        status=score.status_label if score else NOT_SCORED,
                        explanation=explanations.get(paper.paper_id) if score else None))
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


def _run_cell(run: LatestRun | RunDetail | None) -> str:
    if run is None:
        return "<span class='badge'>NOT RUN</span>"
    category = f"<span class='cat'>{escape(run.failure_category)}</span>" if run.failure_category else ""
    return f"<span class='badge {escape(run.status)}'>{escape(run.status)}</span>{category}"


def _status_badge(status: str) -> str:
    css = "s-" + status.replace(" ", "-")
    return f"<span class='badge {escape(css)}'>{escape(status)}</span>"


def _score_text(value: float | None) -> str:
    return "&ndash;" if value is None else f"{value:g}"


def short_reason(row: Row) -> str:
    """One short line beside the label: whether a claim was compared and what Tier 2 rests on (from the stored explanation)."""
    ex = row.explanation
    if not ex:
        return ""
    tier2 = ex["tier2"]
    if ex.get("failure"):
        return f"Run failed ({escape(str(ex['failure']['category']))}); no claim compared"
    if ex["claim_compared"]:
        compared = sum(1 for c in ex["claims"] if c["status"] == "compared")
        return f"Claim compared: yes ({compared} of {ex['claims_accepted']}) &middot; Tier 2: {_score_text(tier2['score'])}"
    return f"Claim compared: no &middot; Tier 2: {_score_text(tier2['score'])} (baseline, nothing compared)"


def footer_html(rows: list[Row] | None = None) -> str:
    """How the numbers on the page came about; names the build date when the database was built from stored runs."""
    built = [r.explanation for r in (rows or []) if r.explanation and r.explanation.get("source")]
    when = max((e.get("built_on") or "" for e in built), default="")
    origin = f"Demo database built from stored runs on {escape(when)}; " if built and when else ""
    sentence = (f"{origin}scores are computed by <code>src/scoring.py</code> from the stored runs; this is not a success "
                "rate and not a measure of how reproducible research code is in general.")
    return f"<footer><p>{sentence[0].upper() + sentence[1:]}</p><p>{NEEDS_REVIEW_NOTE}</p></footer>"


def _layout(title: str, body: str, footer: str | None = None) -> str:
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<title>{escape(title)}</title><meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<style>{PAGE_CSS}</style></head><body><header><h1><a href='/'>Repro Radar</a></h1>"
            "<p>Local dashboard &middot; data from the project database</p>"
            "<nav><a href='/'>Papers</a><a href='/failures'>Failure statistics</a></nav></header>"
            f"<main>{body}</main>{footer if footer is not None else footer_html()}</body></html>")


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
    papers = [r for r in shown if not r.is_control]
    controls = [r for r in shown if r.is_control]
    table = f"<table>{head}{_list_rows(papers)}</table>" if papers else f"<div class='empty'><p>{NO_MATCH}</p></div>"
    if controls:  # the known-answer control is not a paper: it is listed apart and says so
        table += (f"<h2>Known-answer control <span class='badge control'>{CONTROL_BADGE}</span></h2>"
                  "<p class='sub'>A script with a fixed output and a true and a false claim. It checks the scorer; it is not a paper "
                  f"and is not counted below.</p><table>{head}{_list_rows(controls)}</table>")
    real = [r for r in rows if not r.is_control]
    scored = sum(1 for r in real if r.score_total is not None)
    apart = sum(1 for r in rows if r.is_control)
    count = (f"<p class='count'>{len(papers)} of {len(real)} papers &middot; {scored} scored"
             + (f" &middot; {apart} known-answer control listed apart" if apart else "") + "</p>")
    return _layout("Repro Radar", form + table + count, footer_html(rows))


def _list_rows(rows: list[Row]) -> str:
    cells = []
    for r in rows:
        reason = short_reason(r)
        why = f"<span class='why'>{reason}</span>" if reason else ""
        badge = f" <span class='badge control'>{CONTROL_BADGE}</span>" if r.is_control else ""
        cells.append(
            f"<tr><td><a href='/papers/{escape(r.paper.paper_id)}'>{escape(r.paper.paper_id)}</a></td>"
            f"<td>{escape(r.paper.title)}{badge}</td><td>{escape(r.paper.venue)}</td><td>{r.paper.year}</td>"
            f"<td class='num'>{_score_text(r.score_total)}</td><td>{_status_badge(r.status)}{why}</td>"
            f"<td>{_run_cell(r.paper.latest_run)}</td></tr>")
    return "".join(cells)


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
    # the run that the score was computed from, when the score names one; otherwise the latest run of the paper
    run = get_run(engine, score.run_id) if score is not None and score.run_id else None
    run_heading = "Run of this score" if run is not None else "Latest run"
    if run is None and paper.latest_run is not None:
        run = get_run(engine, paper.latest_run.run_id)
    if run is not None:
        seconds = "&ndash;" if run.execution_time is None else f"{run.execution_time:g} s"
        started = "&ndash;" if run.timestamp is None else f"{run.timestamp:%Y-%m-%d %H:%M} UTC"
        run_html = (f"<dl><dt>Run</dt><dd>{escape(run.run_id)}</dd><dt>Started</dt><dd>{started}</dd>"
                    f"<dt>Status</dt><dd>{_run_cell(run)}</dd>"
                    f"<dt>Exit code</dt><dd>{'&ndash;' if run.exit_code is None else run.exit_code}</dd>"
                    f"<dt>Duration</dt><dd>{seconds}</dd></dl>")
        for name, text in (("Standard output", run.stdout), ("Standard error", run.stderr)):
            if text:
                run_html += f"<h2>{name} (last {LOG_EXCERPT_LINES} lines)</h2><pre>{escape(_excerpt(text))}</pre>"
    explanation = get_explanations(engine).get(paper_id) if score is not None else None
    why_html = f"<h2>Why this label</h2>{render_why(explanation)}" if explanation else ""
    control = f" <span class='badge control'>{CONTROL_BADGE}</span>" if explanation and explanation.get("control") else ""
    body = (f"<a class='back' href='/'>&larr; Back to the list</a><h2 style='margin-top:0'>{escape(paper.title)}{control}</h2>"
            f"{facts}<p><a href='/api/v1/papers/{escape(paper.paper_id)}/report.md'>Download report (Markdown)</a> &middot; "
            f"<a href='/api/v1/papers/{escape(paper.paper_id)}/report.pdf'>Download report (PDF)</a></p>"
            f"<h2>Score</h2>{score_html}{why_html}<h2>{run_heading}</h2>{run_html}")
    footer = footer_html([Row(paper=paper, score_total=None, status="", explanation=explanation)])
    return _layout(f"{paper.paper_id} - Repro Radar", body, footer)


def _claim_cells(claim: dict[str, Any]) -> str:
    """The right-hand cells of a claim row: the value in the run, the difference, and the outcome or the reason."""
    if claim["status"] == "compared":
        return (f"<td class='num'>{claim['reproduced']:g}</td><td class='num'>{claim['rel_diff_percent']:.2f} %</td>"
                f"<td>compared with <code>{escape(claim['run_metric'])}</code>: {escape(claim['outcome'])}</td>")
    label = "no counterpart" if claim["status"] == "no_counterpart" else "not found in the output"
    return f"<td>&ndash;</td><td>&ndash;</td><td>{label}: {escape(claim['reason'])}</td>"


def render_why(ex: dict[str, Any]) -> str:
    """The reasons behind a stored score, only from the stored explanation (src/score_explanation.py); nothing is recomputed."""
    tier2, tier3 = ex["tier2"], ex["tier3"]
    reason = tier2["reason"][0].upper() + tier2["reason"][1:]
    parts = [f"<p>{escape(ex['summary'])}</p>",
             (f"<p>Claim compared: <strong>{'yes' if ex['claim_compared'] else 'no'}</strong> &middot; accepted claims of this paper: "
             f"{ex['claims_accepted']}. {escape(reason)}.</p>")]
    if ex["claims"]:
        rows = "".join(f"<tr><td><code>{escape(c['claim'])}</code></td><td class='num'>{c['claimed']:g}</td>{_claim_cells(c)}</tr>"
                       for c in ex["claims"])
        parts.append("<table><tr><th>Accepted claim</th><th>Claimed</th><th>In the run</th><th>Difference</th><th>Result</th></tr>"
                     f"{rows}</table>")
    if tier2["baseline"]:
        parts.append(f"<p class='sub'>Tier 2: {_score_text(tier2['score'])} is the scorer's neutral baseline for a run in which nothing was "
                     "compared. It is not a measurement, so the label rests on the build and artifact tiers only.</p>")
    else:
        parts.append(f"<p class='sub'>Tier 2: {_score_text(tier2['score'])}. {escape(ex['tolerance']['rule'])}</p>")
    if tier3["source"] == "multi_seed":
        parts.append(f"<p>Tier 3: {_score_text(tier3['score'])} from {tier3['seeds']} stored seed runs. Deciding metric: "
                     f"<code>{escape(tier3['metric'])}</code> ({escape(tier3['metric_basis'])}), coefficient of variation "
                     f"{tier3['cv_percent']:.2f} %.</p>")
    elif tier3["source"] == "single_run_baseline":
        parts.append(f"<p>Tier 3: {_score_text(tier3['score'])} is the single-run baseline (no multi-seed record); it is not a "
                     "stability measurement.</p>")
    else:
        parts.append(f"<p>Tier 3: {_score_text(tier3['score'])}; not evaluated because the run did not complete cleanly.</p>")
    run = ex.get("run")
    if run:
        count = (f"<dt>Stored runs of this paper</dt><dd>{run['stored_runs']} (this is the best-scoring one; its date, "
                 "duration and status are under &ldquo;Run of this score&rdquo;)</dd>" if run.get("stored_runs") else "")
        parts.append("<dl><dt>Stored run</dt><dd>" + escape(f"{run['setting']} ({run['directory']})") + f"</dd>{count}</dl>")
    failure = ex.get("failure")
    if failure:
        quote = f"<div class='quote'>{escape(failure['line'])}</div>" if failure.get("line") else ""
        parts.append(f"<p>Recorded failure category: <strong>{escape(str(failure['category']))}</strong>. "
                     f"The log line it was read from:</p>{quote}")
    return "".join(parts)


def _inline_code(text: str) -> str:
    """Escape text and turn `code` and **bold** spans into tags (the warning texts use only these two)."""
    out, code, bold, i = [], False, False, 0
    while i < len(text):
        if text.startswith("**", i):
            out.append("</strong>" if bold else "<strong>")
            bold = not bold
            i += 2
        elif text[i] == "`":
            out.append("</code>" if code else "<code>")
            code = not code
            i += 1
        else:
            out.append(escape(text[i]))
            i += 1
    return "".join(out)


def render_failures(path: Path | None) -> str:
    """The failure statistics page: only what `data/failure_statistics.json` holds; no number is computed here."""
    if path is None or not Path(path).is_file():
        return _layout("Failure statistics - Repro Radar", f"<div class='empty'><h2>No data</h2><p>{NO_FAILURE_STATISTICS}</p></div>")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    warning = "".join(f"<li>{_inline_code(item)}</li>" for item in data["selection_warning"])
    body = ["<h2 style='margin-top:0'>Failure statistics</h2>",
            ("<p class='sub'>Why selected runs failed, by the first deciding log line. These are counts, not a success rate. "
            "Generated by <code>scripts/failure_statistics.py</code>; see <code>docs/FAILURE_STATISTICS.md</code>.</p>"),
            f"<div class='note'><strong>Selection bias &mdash; read this first.</strong><ul>{warning}</ul></div>"]
    meaning = {c["name"]: c["meaning"] for c in data["categories"]}
    for table in data["tables"].values():
        counts, shares = table["counts"], table["share_of_failed"]
        rows = "".join(
            f"<tr><td><code>{escape(name)}</code><span class='why'>"
            f"{_inline_code(meaning.get(name, 'the run passed its own check'))}</span></td>"
            f"<td class='num'>{n}</td><td class='num'>{'&ndash;' if shares.get(name) is None else format(shares[name], '.1%')}</td></tr>"
            for name, n in counts.items() if n)
        body.append(f"<h2>{escape(table['title'])}</h2><table><tr><th>Category</th><th>Runs</th><th>Share of the failed runs</th></tr>"
                    f"{rows}</table><p class='count'>{table['attempts']} runs counted &middot; {table['failed']} failed &middot; sources: "
                    f"{escape(', '.join(table['sources']))}</p>")
        listing = [r for r in table["rows"] if r["category"] != "passed"] if table["attempts"] <= 30 else []
        if listing:
            lines = "".join(f"<tr><td>{escape(r['run'])}</td><td><code>{escape(r['category'])}</code></td>"
                            f"<td>{escape(r['line'] or '')}</td></tr>" for r in listing)
            body.append(f"<table><tr><th>Run</th><th>Category</th><th>Deciding line</th></tr>{lines}</table>")
    return _layout("Failure statistics - Repro Radar", "".join(body), footer_html())


def render_not_found(paper_id: str) -> str:
    return _layout("Not found - Repro Radar",
                   f"<a class='back' href='/'>&larr; Back to the list</a><div class='empty'><h2>Not found</h2>"
                   f"<p>No paper {escape(paper_id)}.</p></div>")
