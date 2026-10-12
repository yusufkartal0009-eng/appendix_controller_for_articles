#!/usr/bin/env python3
"""Write a blind packet for an independent extraction pass (#186).

The packet is a folder outside the repository with everything a new agent session needs to answer the claim
questions, and nothing from the existing extractions: the questions, the rules, a schema description without real
values, each pinned PDF's page text, an answer template, and a README with the prompt. After the new session fills
`answers.json`, `scripts/import_pass.py` checks it and stores it as pass B.

A paper's `followup_queries` (questions added after the gold set, #258) go into the packet too, under their own key
in the question file and in the same answer template; the importer keeps their answers apart from the gold set.

usage: python scripts/make_blind_packet.py C:\\path\\outside\\the\\repository
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import DATA_DIR, PROJECT_ROOT
from src.pdf_text import extract_pdf_text

QUERIES_DIR = DATA_DIR / "claim_queries"
PDF_DIR = DATA_DIR / "pdfs"

RULES = """# Extraction rules

You answer fixed questions about scientific papers, using only the page text in `papers/<paper_id>.txt`.
Pages are marked `=== PAGE n ===`; n is the PDF page number.

1. Answer every question exactly once, with status "found" or "not_found".
2. Use only the given text. If the paper does not report the requested value, answer "not_found" with a short
   reason (for example: the dataset, model, or metric does not occur in the paper, or occurs only under another
   name). Never guess, never compute a value, never take a value from a similar dataset, model, or metric.
3. value_as_printed is copied character for character from the page text, including spaces the extraction put
   inside numbers (e.g. "0 .5"), percent signs, and any "±" part.
4. source_quote is one contiguous span copied exactly from that page (at most 300 characters) that contains
   value_as_printed and, where possible, the row or column label.
5. page is the number of the PAGE marker of the page the quote comes from.
6. Tables are flattened: a header line, then one line per row. Find a value's column by counting cells. If the
   column or row cannot be determined with certainty, answer "not_found" with the reason "column or row ambiguous".
7. If the paper prints the requested value in more than one place (for example single model and ensemble, or
   default and tuned hyperparameters), report the one from the paper's main results table for a single model with
   the paper's own recommended setting, and say in "reason" which other values exist.
8. Values measured on different hardware, and different model variants, are separate questions where the question
   says so (for example "on GPU", or a named depth). Ranks that are compared must come from the same table.
9. Do not compute value_normalized; it is computed later.
"""

SCHEMA = """# Answer format

`answers.json` maps paper_id -> query_id -> answer. An answer is:

    {"status": "found" | "not_found", "reason": "<short text>", "claim": <claim> | null}

For "not_found", claim is null and reason is required. For "found", claim has exactly these fields:

| Field | Meaning |
|---|---|
| metric_name | short lower-case snake_case identifier of the metric, e.g. rmse, accuracy, auroc, average_rank |
| value_as_printed | the value exactly as in the page text (rule 3) |
| unit | percent (if printed as a percentage), fraction, seconds, milliseconds, count, or none |
| dataset | the dataset as written in the paper |
| model_variant | the method or row as written in the paper |
| split | test, validation, train, cross_validation, or not_stated |
| higher_is_better | true, false, or null if the paper does not make it clear |
| table_or_figure | e.g. "Table 2", or null for running text |
| page | PDF page number (rule 5) |
| source_quote | exact span from that page containing value_as_printed (rule 4) |
| confidence | your confidence between 0 and 1 |
"""

README = """# Blind extraction packet (pass B)

This folder is self-contained. Work only with the files in this folder.

## For the owner: how to run it

1. Open a NEW terminal (do not continue an existing Claude Code session).
2. Run:

       cd "{folder}"
       claude

3. Paste the prompt below. If the session asks to read or open anything outside this folder, deny it.
4. When it is done, `answers.json` in this folder is filled. Tell the main session: "pass B is ready in {folder}".

## Prompt for the new session

    Read README.md, RULES.md, and SCHEMA.md in this folder. Answer every question in questions/*.json (the "queries"
    and, where a file has them, the "followup_queries") using only
    the page text in papers/<paper_id>.txt, following RULES.md exactly, and write the answers into answers.json in
    the format of SCHEMA.md (start from the template that is already there; keep every paper_id and query_id).
    Work only inside this folder: do not read, search, or open any other folder, repository, website, or earlier
    conversation. Do not look up these papers anywhere else. When finished, check that answers.json is valid JSON
    and that every value_as_printed occurs inside its source_quote, and that every source_quote occurs on the page
    you cite.

## Contents

- RULES.md, SCHEMA.md: how to answer
- questions/<paper_id>.json: the questions ({n_questions} in total; `queries`, and `followup_queries` where a paper has them)
- papers/<paper_id>.txt: page text of the pinned PDF (sha256 in manifest.json)
- answers.json: template to fill
"""


def make_packet(out_dir: Path) -> dict[str, int]:
    out_dir = out_dir.resolve()
    if out_dir == PROJECT_ROOT.resolve() or PROJECT_ROOT.resolve() in out_dir.parents:
        raise ValueError("the packet must be written outside the repository, where pass A cannot be seen")
    (out_dir / "questions").mkdir(parents=True, exist_ok=True)
    (out_dir / "papers").mkdir(parents=True, exist_ok=True)
    template: dict[str, dict] = {}
    manifest: dict[str, dict] = {}
    n_questions = 0
    for qfile in sorted(QUERIES_DIR.glob("paper_*.json")):
        spec = json.loads(qfile.read_text(encoding="utf-8"))
        paper_id = spec["paper_id"]
        questions = [{"query_id": q["query_id"], "question": q["question"]} for q in spec["queries"]]
        followups = [{"query_id": q["query_id"], "question": q["question"]} for q in spec.get("followup_queries", [])]
        content: dict[str, object] = {"paper_id": paper_id, "queries": questions}
        if followups:
            content["followup_queries"] = followups
        (out_dir / "questions" / f"{paper_id}.json").write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
        pdf = extract_pdf_text(PDF_DIR / f"{paper_id}.pdf")
        text = "\n".join(f"=== PAGE {n} ===\n{page}" for n, page in enumerate(pdf.pages, start=1))
        (out_dir / "papers" / f"{paper_id}.txt").write_text(text, encoding="utf-8")
        manifest[paper_id] = {"pdf_url": spec["pdf_url"], "pdf_sha256": pdf.sha256, "pages": len(pdf.pages)}
        template[paper_id] = {q["query_id"]: {"status": None, "reason": "", "claim": None} for q in questions + followups}
        n_questions += len(questions) + len(followups)
    (out_dir / "RULES.md").write_text(RULES, encoding="utf-8")
    (out_dir / "SCHEMA.md").write_text(SCHEMA, encoding="utf-8")
    (out_dir / "README.md").write_text(README.format(folder=out_dir, n_questions=n_questions), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    answers = out_dir / "answers.json"
    if not answers.exists():  # never overwrite answers already filled in
        answers.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    else:  # an older packet: add empty slots for questions it lacks (follow-ups), keep every existing entry as it is
        existing = json.loads(answers.read_text(encoding="utf-8"))
        added = False
        for paper_id, slots in template.items():
            for query_id, empty in slots.items():
                if query_id not in existing.setdefault(paper_id, {}):
                    existing[paper_id][query_id] = empty
                    added = True
        if added:
            answers.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return {"papers": len(manifest), "questions": n_questions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a blind packet for an independent extraction pass.")
    parser.add_argument("folder", help="Folder outside the repository.")
    args = parser.parse_args(argv)
    counts = make_packet(Path(args.folder))
    print(f"Packet written to {Path(args.folder).resolve()}: {counts['papers']} papers, {counts['questions']} questions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
