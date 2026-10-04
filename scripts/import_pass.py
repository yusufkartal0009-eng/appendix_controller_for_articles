#!/usr/bin/env python3
"""Check a filled blind packet's answers and store them as pass B (#186).

Every answer must cover the packet's questions; every found claim must follow the W1 schema and have its quote on
the cited page of the pinned PDF (the same checks as the quote guard's quote rule). Nothing is written unless every
answer passes. The new pass B replaces the earlier, dependent pass B and records that it came from an independent
session.

usage: python scripts/import_pass.py C:\\path\\to\\packet
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from pydantic import ValidationError

from src.claim_schema import ExtractedClaim
from src.config import DATA_DIR
from src.pdf_text import extract_pdf_text
from src.quote_guard import find_on_page

CLAIMS_DIR = DATA_DIR / "claims"
QUERIES_DIR = DATA_DIR / "claim_queries"
PDF_DIR = DATA_DIR / "pdfs"

METHOD = ("Independent pass B: a new Claude Code session that worked only in a blind packet folder "
          "(scripts/make_blind_packet.py: questions, rules, page texts; no access to pass A), run by the owner. "
          "Imported and checked by scripts/import_pass.py.")


def check_answers(answers: dict[str, Any], pdf_dir: Path = PDF_DIR) -> list[str]:
    problems: list[str] = []
    for qfile in sorted(QUERIES_DIR.glob("paper_*.json")):
        spec = json.loads(qfile.read_text(encoding="utf-8"))
        paper_id = spec["paper_id"]
        expected = {q["query_id"] for q in spec["queries"]}
        given = answers.get(paper_id, {})
        if set(given) != expected:
            problems.append(f"{paper_id}: answers {sorted(given)} != questions {sorted(expected)}")
            continue
        pdf = extract_pdf_text(pdf_dir / f"{paper_id}.pdf")
        for qid, answer in given.items():
            where = f"{paper_id}/{qid}"
            status = answer.get("status")
            if status == "not_found":
                if answer.get("claim") is not None or not answer.get("reason"):
                    problems.append(f"{where}: not_found needs a reason and no claim")
            elif status == "found":
                try:
                    claim = ExtractedClaim(**{k: v for k, v in answer["claim"].items() if k != "value_normalized"})
                except (ValidationError, TypeError, ValueError) as exc:
                    problems.append(f"{where}: invalid claim: {str(exc).splitlines()[0]}")
                    continue
                if not 1 <= claim.page <= len(pdf.pages):
                    problems.append(f"{where}: page {claim.page} does not exist")
                elif find_on_page(claim.source_quote, pdf.page(claim.page)) is None:
                    problems.append(f"{where}: source_quote not on page {claim.page}")
            else:
                problems.append(f"{where}: status must be found or not_found, got {status!r}")
    return problems


def import_pass(packet: Path, label: str = "B") -> list[str]:
    answers = json.loads((packet / "answers.json").read_text(encoding="utf-8"))
    problems = check_answers(answers)
    if problems:
        return problems
    made_at = datetime.now().astimezone().isoformat(timespec="seconds")
    for paper_id, given in answers.items():
        for answer in given.values():
            if answer["status"] == "found":
                claim = ExtractedClaim(**{k: v for k, v in answer["claim"].items() if k != "value_normalized"})
                answer["claim"]["value_normalized"] = claim.value_normalized
        path = CLAIMS_DIR / f"{paper_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["extractions"][label] = {"method": METHOD, "made_at": made_at, "answers": given}
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import a filled blind packet as pass B.")
    parser.add_argument("packet", help="The packet folder with a filled answers.json.")
    args = parser.parse_args(argv)
    problems = import_pass(Path(args.packet))
    if problems:
        print("NOT IMPORTED. Problems:", *problems, sep="\n  - ")
        return 1
    print("Imported as pass B. Next: python scripts/compare_extractions.py and python scripts/check_claims.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
