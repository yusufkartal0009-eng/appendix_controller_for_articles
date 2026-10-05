#!/usr/bin/env python3
"""Replace the seed claim values with the claims a person accepted (section 3 closing step, #135).

    python scripts/apply_accepted_claims.py export   # database -> data/claims/review_decisions.json
    python scripts/apply_accepted_claims.py apply    # review_decisions.json -> data/seed_papers.json
    python scripts/apply_accepted_claims.py check    # exit 1 if the seed file disagrees with the decisions

`export` stores every extracted claim with its review (accepted or rejected by a person, or still pending) in the
repository, because the local database is not committed. `apply` writes only `accepted` claims with
`verified_by: human` into `expected_claims`, keyed by question ID, with their table and page as the source. The
values that were in the seed file before extraction are kept once, under `seed_claims_before_extraction`, so the
change stays visible.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import DATA_DIR, SEED_PAPERS_PATH

DECISIONS_PATH = DATA_DIR / "claims" / "review_decisions.json"
FIELDS = ("extracted_claim_id", "paper_id", "query_id", "metric_name", "dataset", "model_variant", "value",
          "value_as_printed", "page", "table_or_section", "quote", "source_file", "extractor_version", "verified_by",
          "review_status", "review_note")


def export(db_url: str | None, path: Path) -> dict[str, Any]:
    from src.claim_store import get_extracted_claims
    from src.database import get_engine, get_session

    session = get_session(get_engine(db_url) if db_url else get_engine())
    try:
        rows = get_extracted_claims(session)
        claims = [{**{f: getattr(r, f) for f in FIELDS},
                   "reviewed_at": r.reviewed_at.isoformat(timespec="seconds") if r.reviewed_at else None} for r in rows]
    finally:
        session.close()
    summary: dict[str, int] = {}
    for c in claims:
        summary[c["review_status"]] = summary.get(c["review_status"], 0) + 1
    data = {"source": "extracted_claims table, exported by scripts/apply_accepted_claims.py", "summary": summary,
            "claims": claims}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def accepted_by_paper(decisions: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for c in decisions["claims"]:
        if c["review_status"] == "accepted" and c["verified_by"] == "human":
            out.setdefault(c["paper_id"], []).append(c)
    return out


def expected_for(claims: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, str]]:
    claims = sorted(claims, key=lambda c: c["query_id"])
    values = {c["query_id"]: c["value"] for c in claims}
    sources = {c["query_id"]: f"{c['table_or_section']}, p. {c['page']}: {c['value_as_printed']} "
                              f"(quote-matched, accepted by a person)" for c in claims}
    return values, sources


def apply(decisions: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accepted = accepted_by_paper(decisions)
    for e in entries:
        if "seed_claims_before_extraction" not in e:
            e["seed_claims_before_extraction"] = {
                "expected_claims": e["expected_claims"], "source_table_or_section": e.get("source_table_or_section", {}),
                "note": "Seed values before claim extraction; see docs/CORPUS_VERIFICATION.md (2026-09-27 check)",
            }
        e["expected_claims"], e["source_table_or_section"] = expected_for(accepted.get(e["paper_id"], []))
    return entries


def mismatches(decisions: dict[str, Any], entries: list[dict[str, Any]]) -> list[str]:
    accepted = accepted_by_paper(decisions)
    problems = []
    for e in entries:
        values, sources = expected_for(accepted.get(e["paper_id"], []))
        if e["expected_claims"] != values or e.get("source_table_or_section") != sources:
            problems.append(e["paper_id"])
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed claim values from human-accepted claims (#135).")
    parser.add_argument("command", choices=("export", "apply", "check"))
    parser.add_argument("--db-url", default=None)
    parser.add_argument("--decisions", default=str(DECISIONS_PATH))
    args = parser.parse_args(argv)
    path = Path(args.decisions)
    if args.command == "export":
        print(json.dumps(export(args.db_url, path)))
        return 0
    decisions = json.loads(path.read_text(encoding="utf-8"))
    entries = json.loads(SEED_PAPERS_PATH.read_text(encoding="utf-8"))
    if args.command == "check":
        problems = mismatches(decisions, entries)
        print(json.dumps({"consistent": not problems, "papers": problems}))
        return 1 if problems else 0
    raw = SEED_PAPERS_PATH.read_bytes()
    text = json.dumps(apply(decisions, entries), indent=2, ensure_ascii=False) + "\n"
    SEED_PAPERS_PATH.write_bytes(text.replace("\n", "\r\n").encode("utf-8") if b"\r\n" in raw else text.encode("utf-8"))
    print(json.dumps({e["paper_id"]: e["expected_claims"] for e in entries}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
