"""Extracted claims with their provenance and their human review (W6, #10; review step W7, #134).

An extracted claim is stored with where it comes from: paper, page, table or section, the quote, the extraction
file, and the extractor version. `verified_by` records who checked it:

- `auto-quote-match`: the quote guard (`src/quote_guard.py`) found the quote and the value in the paper text.
  This is not an approval; the claim stays `pending`.
- `auto-consensus`: at least two independent extraction passes gave the same normalized value and each passed the quote
  check (`scripts/auto_extract.py`, #381). It is a candidate, not an approval: the claim stays `pending`.
- `human`: a person accepted or rejected the claim (`review_status` `accepted` or `rejected`).

Only claims with `review_status == "accepted"` and `verified_by == "human"` reach the scorer (`accepted_claims`).
Importing an extraction never accepts anything. The one exception is `restore_decisions`, which re-applies decisions that a
person already made and that are committed in `data/claims/review_decisions.json`, so that a fresh clone has the same
accepted claims as the machine where they were reviewed (#395). `consensus_candidates` lists the `auto-consensus` ones, for a run that asks for them by
name and labels its result as such.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.models import ClaimORM, ExtractedClaimORM

REVIEW_STATUSES = ("pending", "accepted", "rejected")
VERIFIED_BY = ("auto-quote-match", "auto-consensus", "human")
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


def restore_decisions(session: Session, decisions_file: Path) -> dict[str, int]:
    """Re-apply the human `accepted` decisions that are committed in `decisions_file` (the export of `apply_accepted_claims.py`).

    Only entries with `review_status == "accepted"` and `verified_by == "human"` are restored; anything else in the file is
    ignored. A claim that already has a review in this database keeps it (a decision made here outranks the file), and a
    claim whose reviewed fields differ from the file is left alone for the same reason as in `save_extracted_claim`.
    Returns the counts `restored`, `kept` (already reviewed here), and `ignored`.
    """
    counts = {"restored": 0, "kept": 0, "ignored": 0}
    if not decisions_file.is_file():
        return counts
    columns = {column.name for column in ExtractedClaimORM.__table__.columns}
    skip = {"extracted_claim_id", "review_status", "verified_by", "reviewed_at", "review_note", "created_at"}
    for entry in json.loads(decisions_file.read_text(encoding="utf-8")).get("claims", []):
        if entry.get("review_status") != "accepted" or entry.get("verified_by") != "human":
            counts["ignored"] += 1
            continue
        existing = session.get(ExtractedClaimORM, claim_key(entry["paper_id"], entry["query_id"]))
        if existing is not None and existing.review_status != "pending":
            counts["kept"] += 1
            continue
        data = {name: value for name, value in entry.items() if name in columns and name not in skip}
        row, _ = save_extracted_claim(session, data)
        row.review_status, row.verified_by = "accepted", "human"
        row.reviewed_at = datetime.fromisoformat(entry["reviewed_at"]) if entry.get("reviewed_at") else None
        note = f"restored from {decisions_file.name}"
        row.review_note = f"{entry['review_note']} ({note})" if entry.get("review_note") else note
        counts["restored"] += 1
    session.flush()
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


def consensus_candidates(session: Session, paper_id: str) -> list[ExtractedClaimORM]:
    """Pending claims that independent passes agree on (`auto-consensus`); never accepted by a person (#381)."""
    return [c for c in get_extracted_claims(session, paper_id, "pending") if c.verified_by == "auto-consensus"]


def get_claims_by_run(session: Session, run_id: str) -> list[ClaimORM]:
    """Claim-versus-reproduced comparisons of one run."""
    return session.query(ClaimORM).filter(ClaimORM.run_id == run_id).order_by(ClaimORM.metric_name).all()
