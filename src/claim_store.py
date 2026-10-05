"""Extracted claims with their provenance and their human review (W6, #10; review step W7, #134).

An extracted claim is stored with where it comes from: paper, page, table or section, the quote, the extraction
file, and the extractor version. `verified_by` records who checked it:

- `auto-quote-match`: the quote guard (`src/quote_guard.py`) found the quote and the value in the paper text.
  This is not an approval; the claim stays `pending`.
- `human`: a person accepted or rejected the claim (`review_status` `accepted` or `rejected`).

Only claims with `review_status == "accepted"` and `verified_by == "human"` reach the scorer (`accepted_claims`).
Importing never accepts anything.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.models import ClaimORM, ExtractedClaimORM

REVIEW_STATUSES = ("pending", "accepted", "rejected")
VERIFIED_BY = ("auto-quote-match", "human")
# Fields that define what a person reviewed: if one changes on re-import, the review no longer applies.
REVIEWED_FIELDS = ("value_as_printed", "page", "quote", "table_or_section", "model_variant", "dataset")


def claim_key(paper_id: str, query_id: str) -> str:
    return f"{paper_id}:{query_id}"


def save_extracted_claim(session: Session, data: dict[str, Any]) -> tuple[ExtractedClaimORM, str]:
    """Insert or update one extracted claim. Returns the row and what happened: added, updated, unchanged.

    An update keeps a human review only if none of the reviewed fields changed; otherwise the claim goes back to
    `pending`, because the person reviewed a different claim.
    """
    key = claim_key(data["paper_id"], data["query_id"])
    row = session.get(ExtractedClaimORM, key)
    if row is None:
        row = ExtractedClaimORM(extracted_claim_id=key, review_status="pending", **data)
        session.add(row)
        session.flush()  # sessions do not autoflush (src/database.py); later lookups must find the row
        return row, "added"
    changed = {name for name, value in data.items() if getattr(row, name) != value}
    reviewed = row.review_status != "pending"
    review_reset = reviewed and bool(changed & set(REVIEWED_FIELDS))
    if reviewed and not review_reset:
        changed.discard("verified_by")  # a person's decision outranks the quote guard
    if not changed:
        return row, "unchanged"
    for name in changed:
        setattr(row, name, data[name])
    if review_reset:
        row.review_status, row.reviewed_at, row.review_note = "pending", None, None
        row.verified_by = data.get("verified_by")
        return row, "updated, review reset"
    return row, "updated"


def import_extraction(session: Session, claims_file: Path, guard_report: Path, pass_name: str = "A",
                      project_root: Path | None = None) -> dict[str, int]:
    """Import the found claims of one extraction pass as `pending` claims.

    Every found claim is stored; `verified_by` is `auto-quote-match` only when the quote guard matched it.
    """
    data = json.loads(Path(claims_file).read_text(encoding="utf-8"))
    guard = {(r["paper_id"], r["pass"], r["query_id"]): r
             for r in json.loads(Path(guard_report).read_text(encoding="utf-8"))["rows"]}
    extraction = data["extractions"][pass_name]
    source = Path(claims_file).resolve()
    if project_root is not None:
        source = source.relative_to(Path(project_root).resolve())
    counts: dict[str, int] = {}
    for query_id, answer in extraction["answers"].items():
        if answer.get("status") != "found":
            counts["not found (not stored)"] = counts.get("not found (not stored)", 0) + 1
            continue
        claim = answer["claim"]
        guard_row = guard.get((data["paper_id"], pass_name, query_id), {})
        _, outcome = save_extracted_claim(session, {
            "paper_id": data["paper_id"],
            "query_id": query_id,
            "metric_name": claim["metric_name"],
            "dataset": claim.get("dataset"),
            "model_variant": claim.get("model_variant"),
            "split": claim.get("split"),
            "value": float(claim["value_normalized"]),
            "value_as_printed": claim["value_as_printed"],
            "higher_is_better": claim.get("higher_is_better"),
            "page": int(claim["page"]),
            "table_or_section": claim.get("table_or_figure"),
            "quote": claim["source_quote"],
            "source_file": source.as_posix(),
            "pdf_sha256": data.get("pdf_sha256"),
            "extractor_version": f"{data.get('protocol')} pass {pass_name}; {data.get('pdf_text_extractor')}",
            "verified_by": "auto-quote-match" if guard_row.get("status") == "AUTO_QUOTE_MATCH" else None,
        })
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def get_extracted_claims(session: Session, paper_id: str | None = None,
                         review_status: str | None = None) -> list[ExtractedClaimORM]:
    query = session.query(ExtractedClaimORM)
    if paper_id is not None:
        query = query.filter(ExtractedClaimORM.paper_id == paper_id)
    if review_status is not None:
        if review_status not in REVIEW_STATUSES:
            raise ValueError(f"review_status must be one of {REVIEW_STATUSES}")
        query = query.filter(ExtractedClaimORM.review_status == review_status)
    return query.order_by(ExtractedClaimORM.paper_id, ExtractedClaimORM.query_id).all()


def record_review(session: Session, extracted_claim_id: str, decision: str, note: str | None = None) -> ExtractedClaimORM:
    """Store a person's decision on one claim (`accepted` or `rejected`)."""
    if decision not in ("accepted", "rejected"):
        raise ValueError("decision must be 'accepted' or 'rejected'")
    row = session.get(ExtractedClaimORM, extracted_claim_id)
    if row is None:
        raise KeyError(f"no extracted claim {extracted_claim_id}")
    row.review_status, row.verified_by = decision, "human"
    row.reviewed_at = datetime.now(UTC).replace(tzinfo=None)
    row.review_note = note
    return row


def accepted_claims(session: Session, paper_id: str) -> list[ExtractedClaimORM]:
    """The claims that may reach the scorer: accepted by a person."""
    return [c for c in get_extracted_claims(session, paper_id, "accepted") if c.verified_by == "human"]


def get_claims_by_run(session: Session, run_id: str) -> list[ClaimORM]:
    """Claim-versus-reproduced comparisons of one run."""
    return session.query(ClaimORM).filter(ClaimORM.run_id == run_id).order_by(ClaimORM.metric_name).all()
