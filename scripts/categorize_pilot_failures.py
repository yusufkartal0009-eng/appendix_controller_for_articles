#!/usr/bin/env python3
"""Put every pilot failure into one category, following docs/PILOT_WEEK2.md section 7 (P4, #125).

The first failure in the order stage -> install -> run decides the category. The deciding log line is quoted
verbatim with its file and line number, so every category can be checked against the stored logs in
data/pilot_runs/. Writes data/pilot_runs/failure_categories.json.
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

from src.config import SEED_PAPERS_PATH
from src.diagnosis.classifier import (  # noqa: F401 - the rules live in the classifier (#32); re-exported for the tests
    ANSI_RE,
    CATEGORIES,
    DATA_EXTENSIONS,
    GPU_PATTERNS,
    NETWORK_PATTERNS,
    categorize_paper,
    classify_exception,
)

PILOT_RUNS_DIR = project_root / "data" / "pilot_runs"

def categorize(runs_dir: Path = PILOT_RUNS_DIR, corpus: Path | None = None) -> dict[str, Any]:
    paper_ids = [e["paper_id"] for e in json.loads((corpus or SEED_PAPERS_PATH).read_text(encoding="utf-8"))]
    papers = [categorize_paper(pid, runs_dir) for pid in paper_ids]
    counts: dict[str, int] = {c: 0 for c in CATEGORIES}
    for p in papers:
        if p["category"]:
            counts[p["category"]] += 1
    protocol = ("docs/PILOT_3.md section 5" if "pilot3" in runs_dir.name else "docs/PILOT_2.md section 7" if "pilot2" in runs_dir.name
                else "docs/PILOT_WEEK2.md section 7")
    return {"protocol": protocol, "papers": papers, "counts": counts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Categorize pilot failures from data/pilot_runs/.")
    parser.add_argument("--runs-dir", default=str(PILOT_RUNS_DIR))
    parser.add_argument("--corpus", default=None, help="Corpus file with the paper list (default: data/seed_papers.json).")
    parser.add_argument("--paper", default=None,
                        help="Only this paper: write `failure_category.json` into its run folder and print it (Pilot 4, one PR per paper).")
    args = parser.parse_args(argv)
    runs_dir = Path(args.runs_dir)
    if args.paper:
        one = categorize_paper(args.paper, runs_dir)
        (runs_dir / args.paper / "failure_category.json").write_text(json.dumps(one, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(one, indent=2))
        return 0
    result = categorize(runs_dir, Path(args.corpus) if args.corpus else None)
    (runs_dir / "failure_categories.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for p in result["papers"]:
        ev = p["evidence"] or {}
        print(f"{p['paper_id']}: {p['category'] or '-'} {p['other_name'] or ''} [{p['phase']}] "
              f"{ev.get('file')}:{ev.get('line_number')}: {ev.get('line')}")
    print(json.dumps(result["counts"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
