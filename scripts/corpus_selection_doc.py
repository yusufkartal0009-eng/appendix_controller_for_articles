#!/usr/bin/env python3
"""Write the selection table into docs/CORPUS_EXPANSION.md from the stored evaluation (#342).

    python scripts/corpus_selection_doc.py            # replace the block between the selection markers
    python scripts/corpus_selection_doc.py --check    # exit 1 if the block differs from the stored evaluation

Reads `data/corpus_expansion/evaluation.json` and `papers.json`. Nothing in the table is typed by hand.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
OUT_DIR = project_root / "data" / "corpus_expansion"
DOC_PATH = project_root / "docs" / "CORPUS_EXPANSION.md"
START, END = "<!-- selection:start -->", "<!-- selection:end -->"


def selection_markdown(evaluation: dict[str, Any], papers: list[dict[str, Any]]) -> str:
    """Why each paper was chosen, and the rejections by stage and first failed rule."""
    candidates = evaluation["candidates"]
    by_name = {c["full_name"].lower(): (rank, c) for rank, c in enumerate(candidates, start=1)}
    intro = (f"Evaluated {evaluation['evaluated']} candidates in the hash order and selected {evaluation['selected']} "
             f"(evaluation of {evaluation['evaluated_at']}).")
    lines = [intro, "",
             "| Paper | Repository | Stage | Rank in the order | License | Run command (README) | Why it was chosen |",
             "|---|---|---|---|---|---|---|"]
    for paper in papers:
        name = paper["repo_url"].split("github.com/")[1]
        rank, result = by_name[name.lower()]
        command = paper["run_command"].replace("|", "/")
        lines.append(f"| `{paper['paper_id']}` | `{name}` | {result['stage']} | {rank} | {paper['license']} | `{command}` | "
                     f"passed R1 to R7 ({result['detail']}) and the checks of `verify_corpus.py` |")
    counts: dict[tuple[int, str], int] = {}
    for result in candidates:
        if not result["passed"]:
            key = (result["stage"], result["failed_rule"])
            counts[key] = counts.get(key, 0) + 1
    lines += ["", "| Stage | First failed rule | Candidates |", "|---|---|---|"]
    lines += [f"| {stage} | {rule} | {count} |" for (stage, rule), count in sorted(counts.items())]
    return "\n".join(lines)


def render(text: str, out_dir: Path = OUT_DIR) -> str:
    evaluation = json.loads((out_dir / "evaluation.json").read_text(encoding="utf-8"))
    papers = json.loads((out_dir / "papers.json").read_text(encoding="utf-8"))
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("the document must hold exactly one selection block")
    a, b = text.index(START) + len(START), text.index(END)
    return text[:a] + "\n" + selection_markdown(evaluation, papers) + "\n" + text[b:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the selection table into docs/CORPUS_EXPANSION.md.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--doc", default=str(DOC_PATH))
    args = parser.parse_args(argv)
    path = Path(args.doc)
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    new = render(text)
    if args.check:
        print(json.dumps({"in_sync": new == text}))
        return 0 if new == text else 1
    path.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
