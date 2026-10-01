#!/usr/bin/env python3
"""Answer the claim queries of one paper with Claude and store the result (W3, #131).

Reads data/claim_queries/<paper_id>.json (pinned PDF URL + queries), downloads the PDF to data/pdfs/ if needed (not
committed), extracts the page text (src/pdf_text.py), and runs src/claim_extraction.py. The result is written to
data/claim_extractions/<paper_id>.json. A repeated run with the same inputs is answered from data/llm_cache/ and
costs nothing. The API key is read from ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.claim_extraction import ExtractionError, Query, cache_key, extract_claims
from src.config import DATA_DIR
from src.pdf_text import extract_pdf_text

QUERIES_DIR = DATA_DIR / "claim_queries"
PDF_DIR = DATA_DIR / "pdfs"
OUTPUT_DIR = DATA_DIR / "claim_extractions"


def download_pdf(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "repro-radar/claim-extraction"})
    with urllib.request.urlopen(request, timeout=60) as response:  # fixed https URLs from the query files
        data = response.read()
    if not data.startswith(b"%PDF"):
        raise ValueError(f"{url} did not return a PDF")
    dest.write_bytes(data)
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Answer one paper's claim queries with Claude.")
    parser.add_argument("paper_id")
    args = parser.parse_args(argv)

    spec = json.loads((QUERIES_DIR / f"{args.paper_id}.json").read_text(encoding="utf-8"))
    queries = [Query(q["query_id"], q["question"]) for q in spec["queries"]]
    pdf = extract_pdf_text(download_pdf(spec["pdf_url"], PDF_DIR / f"{args.paper_id}.pdf"))

    cached = (DATA_DIR / "llm_cache" / f"{cache_key(pdf, queries)}.json").exists()
    if not cached and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; it is needed for an uncached extraction.", file=sys.stderr)
        return 2
    try:
        result = extract_claims(pdf, args.paper_id, spec["pdf_url"], queries)
    except ExtractionError as exc:
        print(f"EXTRACTION FAILED: {exc}", file=sys.stderr)
        return 1

    output = {
        "paper_id": args.paper_id,
        "queries": [q.to_dict() for q in queries],
        "answers": result.answers,
        "claim_set": result.claim_set.model_dump(),
        "meta": result.meta,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{args.paper_id}.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n",
                                                      encoding="utf-8")
    for q in queries:
        answer = result.answers[q.query_id]
        if answer["status"] == "found":
            claim = result.claim_set.claims[answer["claim_index"]]
            print(f"{q.query_id}: FOUND {claim.value_as_printed!r} (page {claim.page}, {claim.table_or_figure})")
        else:
            print(f"{q.query_id}: {answer['status'].upper()} {answer.get('reason') or answer.get('error')}")
    meta = result.meta
    print(f"model {meta['model_served']} (fallback used: {meta['fallback_used']}), usage {meta['usage']}, "
          f"estimated cost ${meta['estimated_cost_usd']}, from cache: {meta['from_cache']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
