"""The reasons behind a stored score, for the dashboard (#548): which claims were compared, how Tier 3 was decided, which run.

A score row holds the numbers and one summary sentence. The dashboard also has to say *why* a paper has its label: whether a
claim was compared at all, why the other claims were not, which tolerance rule applied, where Tier 3 came from, and which stored
run the score rests on. `build_explanation` collects that from the output of `src/score_run.py` (nothing is recomputed or
guessed), and `save_explanation` / `get_explanations` keep it as JSON in the table `score_explanations`.

The table is created when the first explanation is saved and is not part of `data/schema.sql`: a database that has no explanation
(the project database after `cli.py score` of an older version) simply shows no reasons, and reading never writes. Nothing here
changes a score.
"""

from __future__ import annotations

import json
from collections.abc import Collection
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from src.config import DEFAULT_TOLERANCE
from src.scoring import Tier3StabilityEvaluator, coefficient_of_variation

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS score_explanations (
    paper_id TEXT PRIMARY KEY,
    explanation TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""
VERSION = 1


def tolerance_rule(tolerance: float = DEFAULT_TOLERANCE) -> str:
    """The Tier 2 rule in words, with the numbers of the scorer (src/scoring.py, `Tier2MetricsEvaluator`)."""
    return (f"A claim matches when the reproduced value differs from the claimed one by at most {tolerance:.0%} (relative). "
            f"For a claimed value between 0 and 1 an absolute difference of at most {tolerance:g} also matches. "
            "Time and latency metrics use the relative difference only. A difference of up to twice the limit is a partial match "
            "(half the points).")


def _claim_rows(result: dict[str, Any], claims: dict[str, float]) -> list[dict[str, Any]]:
    mapping = result.get("claim_mapping") or {}
    mapped: dict[str, str] = mapping.get("mapped") or {}
    no_counterpart: dict[str, str] = mapping.get("no_counterpart") or {}
    details: dict[str, dict[str, Any]] = result.get("claim_details") or {}
    rows: list[dict[str, Any]] = []
    for query_id, claimed in claims.items():
        if query_id in no_counterpart:
            rows.append({"claim": query_id, "claimed": claimed, "status": "no_counterpart", "reason": no_counterpart[query_id]})
            continue
        metric = mapped.get(query_id, query_id)
        detail = details.get(metric)
        if detail is None or detail.get("reproduced") is None:
            rows.append({"claim": query_id, "claimed": claimed, "run_metric": metric, "status": "not_found_in_output",
                         "reason": "the metric is not among the numbers that the run printed"})
            continue
        points = detail.get("points")
        outcome = "matches" if detail.get("matches") else ("partial match" if points == 0.5 else "differs")
        rows.append({"claim": query_id, "claimed": claimed, "run_metric": metric, "status": "compared",
                     "reproduced": detail["reproduced"], "abs_diff": detail["abs_diff"],
                     "rel_diff_percent": detail["rel_error"] * 100.0, "outcome": outcome, "points": points})
    return rows


def _tier3(result: dict[str, Any], seeds: dict[str, list[float]] | None, claimed_run_metrics: Collection[str]) -> dict[str, Any]:
    score = result["breakdown"].tier3_stability
    notes = result["diagnostics"]["tier3_notes"]
    decisive = Tier3StabilityEvaluator.decisive_metric(seeds, claimed_run_metrics) if seeds else None
    if decisive is None or score == 0.0:
        failed = score == 0.0
        return {"score": score, "source": "not_evaluated" if failed else "single_run_baseline", "notes": notes}
    metric, basis = decisive
    values = seeds[metric]  # type: ignore[index]
    return {"score": score, "source": "multi_seed", "seeds": len(values), "metric": metric,
            "metric_basis": "the metric of an accepted claim" if basis == "claimed" else "the metric with the largest CV",
            "cv_percent": coefficient_of_variation(values) * 100.0, "values": values, "notes": notes}


def build_explanation(result: dict[str, Any], claims: dict[str, float], *, seed_metric_results: dict[str, list[float]] | None = None,
                      run: dict[str, Any] | None = None, failure: dict[str, Any] | None = None, control: bool = False,
                      built_on: str | None = None, source: str | None = None, tolerance: float = DEFAULT_TOLERANCE) -> dict[str, Any]:
    """The reasons of one score as a JSON-ready dictionary.

    `result` is the output of `score_run`; `claims` are the accepted claims that were scored (question ID -> value). `run`
    describes the stored run the score rests on (setting, directory, status, start, duration), `failure` its recorded failure
    (category and the deciding log line), `control` marks the synthetic known-answer control.
    """
    breakdown = result["breakdown"]
    rows = _claim_rows(result, claims)
    compared = [r for r in rows if r["status"] == "compared"]
    mapped_metrics = list((result.get("claim_mapping") or {}).get("mapped", {}).values())
    if compared:
        tier2_reason = f"{len(compared)} of {len(claims)} accepted claim(s) compared with a metric of the run"
    elif not claims:
        tier2_reason = "no claim of this paper has been accepted, so nothing could be compared"
    elif all(r["status"] == "no_counterpart" for r in rows):
        tier2_reason = "no accepted claim has a counterpart in this run, so nothing was compared"
    else:
        tier2_reason = "no accepted claim was found among the numbers that the run printed, so nothing was compared"
    run_failed = bool(failure) or breakdown.tier1_build < 50.0
    return {
        "version": VERSION, "label": breakdown.status_label, "total": breakdown.total_score, "summary": breakdown.summary,
        "claim_compared": bool(compared), "claims": rows, "claims_accepted": len(claims),
        "tier2": {"score": breakdown.tier2_metrics, "baseline": not compared and not run_failed, "reason": tier2_reason},
        "tolerance": {"relative": tolerance, "rule": tolerance_rule(tolerance)},
        "tier3": _tier3(result, seed_metric_results, mapped_metrics),
        "run": run, "failure": failure, "control": control, "source": source, "built_on": built_on,
    }


def save_explanation(engine: Engine, paper_id: str, explanation: dict[str, Any]) -> None:
    """Store (replace) the explanation of a paper; creates the table on first use."""
    with engine.begin() as conn:
        conn.execute(text(TABLE_SQL))
        conn.execute(text("INSERT OR REPLACE INTO score_explanations (paper_id, explanation, created_at) VALUES (:p, :e, :c)"),
                     {"p": paper_id, "e": json.dumps(explanation, ensure_ascii=False, sort_keys=True),
                      "c": datetime.now(UTC).isoformat(timespec="seconds")})


def get_explanations(engine: Engine) -> dict[str, dict[str, Any]]:
    """All stored explanations by paper ID. A database without the table (or without rows) gives {}; reading never writes."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT paper_id, explanation FROM score_explanations")).all()
    except OperationalError:
        return {}
    return {paper_id: json.loads(payload) for paper_id, payload in rows}
