"""Human review of extracted claims (W7, #134).

`python cli.py review-claims [paper_id]` shows each pending claim with its provenance and asks the person to
accept or reject it. Every decision is stored at once with `verified_by: human` (src/claim_store.py), so an
interrupted review keeps the decisions made so far. Only accepted claims reach the scorer (`claims_for_scoring`).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from sqlalchemy.orm import Session

from src.claim_store import (
    accepted_claims,
    consensus_candidates,
    get_extracted_claims,
    record_review,
)
from src.models import ExtractedClaimORM

CHOICES = {"a": "accepted", "r": "rejected", "s": "skip", "q": "quit"}
PROMPT = "[a]ccept / [r]eject / [s]kip / [q]uit: "


def format_claim(claim: ExtractedClaimORM, position: str = "") -> str:
    lines = [
        f"{position} {claim.extracted_claim_id}".strip(),
        f"  metric        : {claim.metric_name}  (higher is better: {claim.higher_is_better})",
        f"  dataset       : {claim.dataset}",
        f"  model variant : {claim.model_variant}",
        f"  value         : {claim.value_as_printed}  (normalized: {claim.value})",
        f"  where         : page {claim.page}, {claim.table_or_section}",
        f"  quote         : {claim.quote}",
        f"  quote check   : {claim.verified_by or 'not matched'}",
        f"  extraction    : {claim.source_file} ({claim.extractor_version})",
    ]
    return "\n".join(lines)


def review_claims(session: Session, paper_id: str | None = None, input_fn: Callable[[str], str] | None = None,
                  out: Callable[[str], None] = print) -> Counter[str]:
    """Ask for a decision on every pending claim; returns how many were accepted, rejected, and skipped."""
    input_fn = input_fn or input  # looked up at call time, so the console input can be replaced
    pending = get_extracted_claims(session, paper_id, "pending")
    counts: Counter[str] = Counter()
    if not pending:
        out("No pending claims." + ("" if paper_id is None else f" (paper {paper_id})"))
        return counts
    for i, claim in enumerate(pending, start=1):
        out("")
        out(format_claim(claim, f"[{i}/{len(pending)}]"))
        while (answer := input_fn(PROMPT).strip().lower()[:1]) not in CHOICES:
            out("Please answer a, r, s, or q.")
        decision = CHOICES[answer]
        if decision == "quit":
            out("Stopped; the remaining claims stay pending.")
            break
        if decision == "skip":
            counts["skipped"] += 1
            continue
        note = input_fn("Note (optional, Enter to skip): ").strip() or None
        record_review(session, claim.extracted_claim_id, decision, note)
        session.commit()  # store each decision at once
        counts[decision] += 1
    counts["still pending"] = len(get_extracted_claims(session, paper_id, "pending"))
    out(f"Review summary: {dict(counts)}")
    return counts


def claims_for_scoring(session: Session, paper_id: str, include_auto_consensus: bool = False) -> dict[str, float]:
    """The claimed values the scorer may use: only claims a person accepted, keyed by question id.

    `include_auto_consensus=True` adds the candidates that independent extraction passes agree on (#381). A person's
    accepted claim wins over a candidate for the same question. The caller must label the score as one that used
    unreviewed candidates (`cli.py score --claims auto-consensus` does).
    """
    claims = {claim.query_id: claim.value for claim in accepted_claims(session, paper_id)}
    if include_auto_consensus:
        for claim in consensus_candidates(session, paper_id):
            claims.setdefault(claim.query_id, claim.value)
    return claims
