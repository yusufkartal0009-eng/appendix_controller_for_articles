"""The map from accepted claims to run metrics (#507, #509).

An accepted claim is keyed by its question ID (`ft_transformer_rmse`); a run's metrics are keyed by the name the metric
extractor found (`rmse`). `data/claim_metric_map.json` says, for each accepted claim, which run metric it is compared with
(`map`) or that the run has no counterpart for it (`no_counterpart`). See docs/CLAIM_METRIC_MAP.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "claim_metric_map.json"
DECISIONS = ("map", "no_counterpart")


class ClaimMapError(ValueError):
    """The map file exists but cannot be used."""


def load_claim_map(path: Path | str | None = None) -> dict[str, dict[str, dict[str, Any]]] | None:
    """The `papers` table of the map file, or None when the file does not exist (the scorer then behaves as before)."""
    path = Path(path) if path else DEFAULT_MAP_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ClaimMapError(f"claim map {path} cannot be read as JSON: {exc}") from exc
    papers = data.get("papers") if isinstance(data, dict) else None
    if not isinstance(papers, dict):
        raise ClaimMapError(f"claim map {path} has no 'papers' object")
    for paper_id, entries in papers.items():
        if not isinstance(entries, dict):
            raise ClaimMapError(f"claim map {path}: '{paper_id}' must be an object of question IDs")
        for query_id, entry in entries.items():
            where = f"claim map {path}: {paper_id}/{query_id}"
            if not isinstance(entry, dict) or entry.get("decision") not in DECISIONS:
                raise ClaimMapError(f"{where} needs a 'decision' of {' or '.join(DECISIONS)}")
            if entry["decision"] == "map" and not (isinstance(entry.get("run_metric"), str) and entry["run_metric"].strip()):
                raise ClaimMapError(f"{where} is a 'map' without a 'run_metric'")
            if entry["decision"] == "no_counterpart" and not str(entry.get("reason", "")).strip():
                raise ClaimMapError(f"{where} is a 'no_counterpart' without a 'reason'")
    return papers


def apply_claim_map(paper_id: str, claims: dict[str, float],
                    claim_map: dict[str, dict[str, dict[str, Any]]] | None) -> tuple[dict[str, float], dict[str, str], dict[str, str]]:
    """Split a paper's claims into (claims keyed by run metric, mapped query ID -> run metric, no counterpart query ID -> reason).

    Without a map, or without entries for the paper, the claims come back untouched. A claim without an entry stays keyed
    by its question ID, as before.
    """
    entries = (claim_map or {}).get(paper_id)
    if not entries:
        return dict(claims), {}, {}
    scored: dict[str, float] = {}
    mapped: dict[str, str] = {}
    no_counterpart: dict[str, str] = {}
    for query_id, value in claims.items():
        entry = entries.get(query_id)
        if entry is None:
            scored[query_id] = value
        elif entry["decision"] == "no_counterpart":
            no_counterpart[query_id] = entry["reason"]
        else:
            metric = entry["run_metric"]
            if metric in scored:
                raise ClaimMapError(f"{paper_id}: two claims are mapped to the run metric '{metric}'")
            scored[metric] = value
            mapped[query_id] = metric
    return scored, mapped, no_counterpart
