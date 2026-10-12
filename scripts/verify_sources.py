#!/usr/bin/env python3
"""Look up every source of the report's related-work section and check it against what the report will cite (#270).

Input: `docs/report/related_work_sources.json`, one entry per source with what the report says it is (`expected_title`,
`first_author_family`, `year`) and where to look it up (`doi` for Crossref, `arxiv_id` for the arXiv API).
Output: `docs/report/related_work_verification.json`, with what each service returned: title, first author, year,
venue, and the abstract when the service has one. A source is VERIFIED only when every lookup that was made agrees on
title (similarity of at least 0.9), first author's family name, and year. Nothing here reads a paper's full text.

    python scripts/verify_sources.py            # look everything up (needs network) and write the output
    python scripts/verify_sources.py --check    # exit 1 unless the stored output covers the input and is all VERIFIED

Exit code 0 = every source verified, 1 = not.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

project_root = Path(__file__).resolve().parent.parent
SOURCES_PATH = project_root / "docs" / "report" / "related_work_sources.json"
OUTPUT_PATH = project_root / "docs" / "report" / "related_work_verification.json"
CROSSREF_API = "https://api.crossref.org/works/"
ARXIV_API = "http://export.arxiv.org/api/query"
USER_AGENT = "repro-radar-source-verifier/1.0 (+https://github.com/yusufkartal0009-eng/appendix_controller_for_articles)"
TITLE_MATCH_THRESHOLD = 0.9
ARXIV_PAUSE_SECONDS = 3.0  # the arXiv API asks for a pause between calls
ATOM = "{http://www.w3.org/2005/Atom}"


def normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def http_get(url: str, timeout: int = 30) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""


def strip_markup(text: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())


def lookup_crossref(doi: str, get=http_get) -> dict[str, Any]:
    status, body = get(CROSSREF_API + urllib.parse.quote(doi, safe="/"))
    if status != 200:
        return {"found": False, "http_status": status}
    message = json.loads(body)["message"]
    issued = (message.get("issued") or {}).get("date-parts") or [[None]]
    authors = message.get("author") or []
    return {
        "found": True,
        "title": (message.get("title") or [""])[0],
        "first_author_family": authors[0].get("family", "") if authors else "",
        "authors": [" ".join(filter(None, [a.get("given"), a.get("family")])) or a.get("name", "") for a in authors],
        "year": issued[0][0],
        "volume": message.get("volume"),
        "issue": message.get("issue"),
        "venue": (message.get("container-title") or [""])[0],
        "pages_or_article": message.get("page") or message.get("article-number") or "",
        "abstract": strip_markup(message["abstract"]) if message.get("abstract") else None,
        "url": message.get("URL"),
    }


def lookup_arxiv(arxiv_id: str, get=http_get) -> dict[str, Any]:
    status, body = get(f"{ARXIV_API}?id_list={urllib.parse.quote(arxiv_id)}")
    if status != 200:
        return {"found": False, "http_status": status}
    entries = ElementTree.fromstring(body).findall(f"{ATOM}entry")
    if not entries or entries[0].findtext(f"{ATOM}title") in (None, "Error"):
        return {"found": False, "http_status": status}
    entry = entries[0]
    names = [(a.text or "").strip() for a in entry.findall(f"{ATOM}author/{ATOM}name")]
    full_name = names[0] if names else ""
    return {
        "found": True,
        "title": " ".join((entry.findtext(f"{ATOM}title") or "").split()),
        "first_author_family": full_name.split()[-1] if full_name else "",
        "authors": names,
        "year": int((entry.findtext(f"{ATOM}published") or "0000")[:4]),
        "venue": "arXiv " + arxiv_id,
        "abstract": " ".join((entry.findtext(f"{ATOM}summary") or "").split()) or None,
        "url": entry.findtext(f"{ATOM}id"),
    }


def check_lookup(expected: dict[str, Any], found: dict[str, Any], year_tolerance: int = 0) -> list[str]:
    """Reasons the lookup disagrees with what the report will cite; empty when it agrees."""
    if not found.get("found"):
        return [f"not found (HTTP {found.get('http_status')})"]
    reasons = []
    similarity = title_similarity(expected["expected_title"], found["title"])
    if similarity < TITLE_MATCH_THRESHOLD:
        reasons.append(f"title differs (similarity {similarity:.2f}): {found['title']!r}")
    if normalize(expected["first_author_family"]) != normalize(found["first_author_family"]):
        reasons.append(f"first author differs: {found['first_author_family']!r}")
    if found["year"] is None or abs(int(found["year"]) - int(expected["year"])) > year_tolerance:
        reasons.append(f"year differs: {found['year']}")
    return reasons


def verify_source(entry: dict[str, Any], get=http_get, pause=time.sleep) -> dict[str, Any]:
    result: dict[str, Any] = {"ref": entry["ref"], "expected": {k: entry[k] for k in ("expected_title", "first_author_family", "year")},
                              "lookups": {}, "reasons": []}
    if entry.get("doi"):
        found = lookup_crossref(entry["doi"], get)
        result["lookups"]["crossref"] = {"doi": entry["doi"], **found}
        result["reasons"] += [f"crossref: {r}" for r in check_lookup(entry, found)]
    if entry.get("arxiv_id"):
        if "crossref" in result["lookups"]:
            pause(ARXIV_PAUSE_SECONDS)
        found = lookup_arxiv(entry["arxiv_id"], get)
        result["lookups"]["arxiv"] = {"arxiv_id": entry["arxiv_id"], **found}
        # an arXiv paper is posted before it is published, so its year may be earlier than the venue's
        # a preprint can carry a longer title than the published paper; the input then says what the preprint is called
        expected = {**entry, "expected_title": entry.get("arxiv_expected_title", entry["expected_title"])}
        result["reasons"] += [f"arxiv: {r}" for r in check_lookup(expected, found, entry.get("arxiv_year_tolerance", 1))]
    if not result["lookups"]:
        result["reasons"].append("no doi or arxiv_id to look up")
    result["status"] = "VERIFIED" if not result["reasons"] else "NOT_VERIFIED"
    return result


def verify_all(entries: list[dict[str, Any]], get=http_get, pause=time.sleep) -> dict[str, Any]:
    sources = []
    for entry in entries:
        sources.append(verify_source(entry, get, pause))
        pause(1.0)
    return {
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool": "scripts/verify_sources.py",
        "what_was_read": "metadata (Crossref, arXiv API) and the arXiv abstract; no full text",
        "sources": sources,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Look up and check the related-work sources.")
    parser.add_argument("--check", action="store_true", help="Only check the stored output against the input.")
    args = parser.parse_args(argv)
    entries = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))["sources"]
    if args.check:
        stored = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        by_ref = {s["ref"]: s for s in stored["sources"]}
        problems = [e["ref"] for e in entries if by_ref.get(e["ref"], {}).get("status") != "VERIFIED"]
        print(json.dumps({"not_verified_or_missing": problems}))
        return 1 if problems else 0
    output = verify_all(entries)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for source in output["sources"]:
        print(f"{source['ref']:6} {source['status']:12} {'; '.join(source['reasons'])[:120]}")
    return 0 if all(s["status"] == "VERIFIED" for s in output["sources"]) else 1


if __name__ == "__main__":
    sys.exit(main())
