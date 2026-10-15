#!/usr/bin/env python3
"""Gold set expansion: blind packet, owner form, and import of a pass (#315, docs/GOLD_SET_EXPANSION.md).

    python scripts/gold_expansion.py packet <folder outside the repository>   # blind packet for pass B
    python scripts/gold_expansion.py form <form.md>                             # the owner's gold set form (Turkish)
    python scripts/gold_expansion.py import-pass <answers.json> --pass A|B     # check and store answers

The 18 questions are in `data/gold_expansion/questions.json`, the candidate values for the form in
`candidates.json`, the passes in `claims/<paper_id>.json` (the same shape as `data/claims/`, so that
`scripts/compare_extractions.py --claims-dir` and `scripts/evaluate_gold.py score --claims-dir` read them).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from pydantic import ValidationError

from scripts.make_blind_packet import RULES, SCHEMA
from src.claim_schema import ExtractedClaim
from src.config import DATA_DIR, PROJECT_ROOT
from src.pdf_text import extract_pdf_text
from src.quote_guard import find_on_page

EXPANSION_DIR = DATA_DIR / "gold_expansion"
CLAIMS_DIR = EXPANSION_DIR / "claims"
PDF_DIR = DATA_DIR / "pdfs"

README = """# Blind extraction packet (gold set expansion, pass B)

This folder is self-contained. Work only with the files in this folder.

## Prompt for the new session

    Read README.md, RULES.md, and SCHEMA.md in this folder. Answer every question in questions/*.json using only
    the page text in papers/<paper_id>.txt, following RULES.md exactly, and write the answers into answers.json in
    the format of SCHEMA.md (start from the template that is already there; keep every paper_id and query_id).
    Work only inside this folder: do not read, search, or open any other folder, repository, website, or earlier
    conversation. Do not look up these papers anywhere else. You cannot run Python or any shell command in this
    session: write answers.json directly with the Write tool. Then re-read answers.json and check by reading that it
    is valid JSON, that every value_as_printed occurs inside its source_quote, and that every source_quote occurs on
    the page you cite (re-open the paper text for each quote).

## Contents

- RULES.md, SCHEMA.md: how to answer
- questions/<paper_id>.json: the questions ({n_questions} in total)
- papers/<paper_id>.txt: page text of the pinned PDF (sha256 in manifest.json)
- answers.json: template to fill
"""

PAPER_TITLES = {
    "paper_002": "TabPFN (arXiv 2207.01848v6)", "paper_003": "FT-Transformer / Revisiting Deep Learning Models (arXiv 2106.11959v5)",
    "paper_004": "TabR (arXiv 2307.14338)", "paper_005": "FastSK (bioRxiv 2020.04.21.053975v2)",
    "paper_006": "SAINT (arXiv 2106.01342)", "paper_008": "DANet (arXiv 2112.02962)",
}


def load_questions() -> dict[str, dict[str, Any]]:
    return json.loads((EXPANSION_DIR / "questions.json").read_text(encoding="utf-8"))["papers"]


def make_packet(out_dir: Path) -> dict[str, int]:
    out_dir = out_dir.resolve()
    if out_dir == PROJECT_ROOT.resolve() or PROJECT_ROOT.resolve() in out_dir.parents:
        raise ValueError("the packet must be written outside the repository, where pass A cannot be seen")
    (out_dir / "questions").mkdir(parents=True, exist_ok=True)
    (out_dir / "papers").mkdir(parents=True, exist_ok=True)
    template: dict[str, dict] = {}
    manifest: dict[str, dict] = {}
    n_questions = 0
    for paper_id, spec in load_questions().items():
        questions = [{"query_id": q["query_id"], "question": q["question"]} for q in spec["queries"]]
        (out_dir / "questions" / f"{paper_id}.json").write_text(
            json.dumps({"paper_id": paper_id, "queries": questions}, indent=2) + "\n", encoding="utf-8")
        pdf = extract_pdf_text(PDF_DIR / f"{paper_id}.pdf")
        text = "\n".join(f"=== PAGE {n} ===\n{page}" for n, page in enumerate(pdf.pages, start=1))
        (out_dir / "papers" / f"{paper_id}.txt").write_text(text, encoding="utf-8")
        manifest[paper_id] = {"pdf_url": spec["pdf_url"], "pdf_sha256": pdf.sha256, "pages": len(pdf.pages)}
        template[paper_id] = {q["query_id"]: {"status": None, "reason": "", "claim": None} for q in questions}
        n_questions += len(questions)
    (out_dir / "RULES.md").write_text(RULES, encoding="utf-8")
    (out_dir / "SCHEMA.md").write_text(SCHEMA, encoding="utf-8")
    (out_dir / "README.md").write_text(README.format(n_questions=n_questions), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    answers = out_dir / "answers.json"
    if not answers.exists():  # never overwrite answers already filled in
        answers.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    return {"papers": len(manifest), "questions": n_questions}


def make_form(path: Path) -> int:
    """The owner's form, in the structure that scripts/evaluate_gold.py reads. It does not show what the passes chose.

    The text is English (everything in the repository is); a translation for the owner is made outside the repository.
    The structure that the evaluator reads is language free: a `**S<n>. `query_id`**` line per question, one checkbox
    option per candidate with the value in backticks, then "Not in the paper" and "Other".
    """
    candidates = json.loads((EXPANSION_DIR / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    lines = [
        "# Gold set form 2 (expansion, #315)", "",
        "This form is for the owner only and stays outside the repository. When it is filled, tell the main session.", "",
        "## How to fill it", "",
        "- For each question, **you** choose the correct answer: tick `[x]` the box of the correct value. If several values",
        "  are correct, tick several.",
        "- If none is correct, tick **\"Not in the paper\"** or **\"Other\"** (write the value and the page).",
        "- The options are candidates listed by an agent. The form does not show which one pass A or pass B chose, and the",
        "  order is shuffled.",
        "- Some questions ask for something that is **not** in the paper (no such dataset or model). The right answer is then",
        "  \"Not in the paper\"; the values listed belong to something else, do not tick them.",
        "- Check each value in the PDF: `data/pdfs/<paper_id>.pdf`. Page numbers are the PDF file's page numbers.",
        "- A question you leave blank is not part of the gold set.", "", "---", "",
    ]
    number = 0
    for paper_id, spec in load_questions().items():
        lines += [f"## {paper_id} - {PAPER_TITLES[paper_id]}", ""]
        for q in spec["queries"]:
            number += 1
            lines.append(f"**S{number}. `{q['query_id']}`: {q['question']}**")
            shuffled = list(candidates[q["query_id"]])
            random.Random(q["query_id"]).shuffle(shuffled)  # the order must not say which candidate is right
            for c in shuffled:
                lines.append(f"- [ ] `{c['value']}` - {c['where']}")
            lines += ["- [ ] Not in the paper", "- [ ] Other: ______ (page: __)", ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return number


def check_answers(answers: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for paper_id, spec in load_questions().items():
        expected = {q["query_id"] for q in spec["queries"]}
        given = answers.get(paper_id, {})
        if set(given) != expected:
            problems.append(f"{paper_id}: answers {sorted(given)} != questions {sorted(expected)}")
            continue
        pdf = extract_pdf_text(PDF_DIR / f"{paper_id}.pdf")
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


def import_pass(answers_path: Path, label: str, method: str) -> list[str]:
    answers = json.loads(answers_path.read_text(encoding="utf-8"))
    problems = check_answers(answers)
    if problems:
        return problems
    made_at = datetime.now().astimezone().isoformat(timespec="seconds")
    CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
    for paper_id, spec in load_questions().items():
        given = answers[paper_id]
        for answer in given.values():
            if answer["status"] == "found":
                claim = ExtractedClaim(**{k: v for k, v in answer["claim"].items() if k != "value_normalized"})
                answer["claim"]["value_normalized"] = claim.value_normalized
        path = CLAIMS_DIR / f"{paper_id}.json"
        pdf = extract_pdf_text(PDF_DIR / f"{paper_id}.pdf")
        record = (json.loads(path.read_text(encoding="utf-8")) if path.exists()
                  else {"paper_id": paper_id, "pdf_url": spec["pdf_url"], "pdf_sha256": pdf.sha256, "extractions": {}})
        record["extractions"][label] = {"method": method, "made_at": made_at, "answers": given}
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("packet").add_argument("folder")
    sub.add_parser("form").add_argument("path")
    p_import = sub.add_parser("import-pass")
    p_import.add_argument("answers")
    p_import.add_argument("--pass", dest="label", choices=["A", "B"], required=True)
    p_import.add_argument("--method", required=True)
    args = parser.parse_args(argv)
    if args.command == "packet":
        print(json.dumps(make_packet(Path(args.folder))))
    elif args.command == "form":
        print(f"{make_form(Path(args.path))} questions written to {args.path}")
    else:
        problems = import_pass(Path(args.answers), args.label, args.method)
        if problems:
            print("NOT IMPORTED. Problems:")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        print(f"Imported as pass {args.label}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
