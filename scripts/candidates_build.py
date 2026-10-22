#!/usr/bin/env python3
"""Build the candidates corpus from data/candidates/input.json (#433).

The candidates are papers with a public repository that the owner collected; none has been run. For every candidate this
script reads, from GitHub and from the paper's page: the head commit of the default branch (or the commit that the list
supplied), the license, the size, whether the repository is archived or a fork, the paper title and year, and whether the
repository's README names the paper. It writes:

    data/candidates/papers.json       entries in the format of data/seed_papers.json (so that scripts/verify_corpus.py reads
                                      them), with the status and notes of the lists
    data/candidates/evaluation.json   what was read, with the date

The candidates are NOT added to data/seed_papers.json: that file is the evaluation set of the pilots. Run
`python scripts/verify_corpus.py data/candidates/papers.json` afterwards (GITHUB_TOKEN avoids the API rate limit).
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.verify_corpus import CROSSREF_API, GITHUB_API, UrlHttp, _extract_page_title

INPUT_PATH = project_root / "data" / "candidates" / "input.json"
PAPERS_PATH = project_root / "data" / "candidates" / "papers.json"
EVALUATION_PATH = project_root / "data" / "candidates" / "evaluation.json"
ARXIV_DELAY_SECONDS = 3.0  # arXiv asks automated clients for at most one request every three seconds


def _json(http, url: str) -> tuple[int, Any]:
    status, body = http.get(url)
    return status, (json.loads(body) if status == 200 and body else None)


def read_paper(paper: str, http, sleep=time.sleep) -> dict[str, Any]:
    """Title, year, venue and URL of the paper from its page (arXiv abstract page, or Crossref for a DOI)."""
    if paper.startswith("doi:"):
        doi = paper[4:]
        status, data = _json(http, f"{CROSSREF_API}/{doi}")
        if data is None:
            return {"error": f"Crossref HTTP {status} for {doi}", "paper_url": f"https://doi.org/{doi}", "key": doi}
        message = data.get("message") or {}
        titles = message.get("title") or []
        issued = ((message.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        venues = message.get("container-title") or []
        return {"title": html.unescape(titles[0]).strip() if titles else None, "year": issued,
                "venue": venues[0] if venues else "unknown", "paper_url": f"https://doi.org/{doi}", "key": doi}
    sleep(ARXIV_DELAY_SECONDS)
    status, body = http.get(f"https://arxiv.org/abs/{paper}")
    if status != 200:
        return {"error": f"arXiv HTTP {status} for {paper}", "paper_url": f"https://arxiv.org/abs/{paper}", "key": paper}
    date = re.search(r'<meta\s+name="citation_date"\s+content="(\d{4})', body)
    return {"title": _extract_page_title(body), "year": int(date.group(1)) if date else None, "venue": "arXiv",
            "paper_url": f"https://arxiv.org/abs/{paper}", "key": paper}


def read_repo(full_name: str, supplied_commit: str | None, http) -> dict[str, Any]:
    status, repo = _json(http, f"{GITHUB_API}/repos/{full_name}")
    if repo is None:
        return {"error": f"GitHub HTTP {status} for {full_name}"}
    branch = repo.get("default_branch", "main")
    commit = supplied_commit
    head_date = None
    if commit is None:
        status, head = _json(http, f"{GITHUB_API}/repos/{full_name}/commits/{branch}")
        if head is None:
            return {"error": f"GitHub HTTP {status} for the head commit of {full_name}@{branch}"}
        commit, head_date = head["sha"], (head.get("commit", {}).get("committer") or {}).get("date")
    readme = ""
    status, data = _json(http, f"{GITHUB_API}/repos/{full_name}/readme")
    if data and data.get("content"):
        readme = base64.b64decode(data["content"]).decode("utf-8", "replace")
    return {"full_name": repo.get("full_name", full_name), "default_branch": branch, "commit": commit,
            "commit_supplied_by_list": supplied_commit is not None, "head_commit_date": head_date,
            "license": (repo.get("license") or {}).get("spdx_id"), "size_kb": repo.get("size"),
            "archived": repo.get("archived"), "fork": repo.get("fork"), "language": repo.get("language"),
            "pushed_at": repo.get("pushed_at"), "readme": readme}


def build_entry(index: int, item: dict[str, Any], http, sleep=time.sleep) -> tuple[dict[str, Any], dict[str, Any]]:
    """One entry in the seed format and the record of what was read."""
    paper = read_paper(item["paper"], http, sleep)
    repo = read_repo(item["repo"], item.get("supplied_commit"), http)
    key = paper.get("key", "")
    readme_names_paper = bool(repo.get("readme")) and key.lower() in repo["readme"].lower()
    entry = {
        "paper_id": f"cand_{index:03d}",
        "title": paper.get("title") or "",
        "year": paper.get("year"),
        "venue": paper.get("venue", "unknown"),
        "repo_url": f"https://github.com/{repo.get('full_name', item['repo'])}",
        "repo_commit": repo.get("commit", ""),
        "paper_url": paper.get("paper_url", ""),
        "license": repo.get("license") or "",
        "target_script": item["script"],
        "working_dir": item.get("working_dir", ""),
        "run_command": item["command"],
        "status": item["status"],
        "source": item["source"],
        "notes": item["notes"],
        "expected_claims": {},
    }
    record = {"paper_id": entry["paper_id"], "repo": item["repo"],
              "paper_error": paper.get("error"), "repo_error": repo.get("error"),
              "readme_names_the_paper": readme_names_paper,
              **{k: v for k, v in repo.items() if k not in ("readme", "error")}}
    if "title_hint" in item and entry["title"]:
        record["title_hint"] = item["title_hint"]
        record["title_contains_hint"] = item["title_hint"].lower() in entry["title"].lower()
    return entry, record


def render_doc(entries: list[dict[str, Any]], records: list[dict[str, Any]], verify: list[dict[str, Any]], excluded: list[str],
               retrieved_at: str) -> str:
    """docs/CANDIDATES.md from the three data files, so that every number in it is generated."""
    by_status: dict[str, int] = {}
    for entry in entries:
        by_status[entry["status"]] = by_status.get(entry["status"], 0) + 1
    passed = sum(1 for item in verify if item["ok"])
    lines = [
        "<!-- Generated by `python scripts/candidates_build.py --doc` from data/candidates/; do not edit by hand. -->",
        "# Candidate papers (not run)", "",
        (f"Retrieved {retrieved_at}. {len(entries)} candidates with a public repository, collected by the owner from two lists "
         "(a hand-checked scan and 28 parallel GitHub scans) and re-checked once by a third person. **None of them has been run "
         "by this project.** They are kept apart from `data/seed_papers.json`, which is the evaluation set of the pilots; a "
         "candidate moves there only after a run in the sandbox and a decision of the owner (`docs/PAPER_ONBOARDING.md`)."), "",
        "## What was checked", "",
        (f"`scripts/verify_corpus.py` on `data/candidates/papers.json`: the paper's page exists and its title is read, the repository "
         f"exists, the license is one of the allowed ones, and the script exists at the pinned commit. **{passed} of {len(verify)} "
         "passed all four checks.** The pinned commit is the head of the default branch on the day of retrieval (the two entries "
         "from the hand-checked list keep the commit that list supplied). The README of every repository was read and "
         f"{sum(1 for r in records if r['readme_names_the_paper'])} of {len(records)} name the paper (its arXiv id or DOI)."), "",
        ("A passing check does **not** mean that the paper's code runs, that it needs no network, that it does not write into the "
         "repository (read-only in the sandbox), or that its output is a table of the paper. Those are the questions of the run "
         "test."), "",
        "## Status given by the lists", "",
        "| Status | Meaning | Count |", "|---|---|---|",
    ]
    meaning = {"ready": "called ready for a first run", "fixable": "usable after a path or folder is corrected",
               "risky": "needs data or a network at run time, or writes into the repository",
               "two_step": "two commands in order", "excluded": "excluded by the lists (wrong script, cluster only, needs a server)"}
    for status in ("ready", "fixable", "two_step", "risky", "excluded"):
        lines.append(f"| {status} | {meaning[status]} | {by_status.get(status, 0)} |")
    lines += ["", "## The candidates", "",
              "| Id | Repository | Paper | License | Size (KB) | Status | Script |", "|---|---|---|---|---|---|---|"]
    record_of = {r["paper_id"]: r for r in records}
    for entry in entries:
        r = record_of[entry["paper_id"]]
        title = entry["title"].replace("|", "/")
        lines.append(f"| {entry['paper_id']} | `{entry['repo_url'].split('github.com/')[-1]}` | {title[:60]} ({entry['year']}) | "
                     f"{entry['license']} | {r.get('size_kb')} | {entry['status']} | `{entry['target_script']}` |")
    lines += ["", "## Notes of the lists", ""]
    for entry in entries:
        lines.append(f"- **{entry['paper_id']}** (`{entry['repo_url'].split('github.com/')[-1]}`, {entry['status']}): {entry['notes']}")
    lines += ["", "## Excluded without an entry", ""] + [f"- {name}" for name in excluded]
    lines += ["", "## Not verified", "",
              ("- No candidate was run. Run time, offline installation, writes into the repository, and which table of the paper the "
               "output matches are unknown for all of them."),
              ("- The paper title check compares a page title with a title read from the same page; what ties a paper to a repository "
               "is the README naming it."),
              ("- Years are those of the first version on arXiv (or Crossref); several candidates are outside the 2020 to 2024 range "
               "that `data/seed_papers.json` enforces, so they could not be moved there unchanged."), ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None, http=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", default=str(INPUT_PATH))
    parser.add_argument("--doc", action="store_true",
                        help="Only write docs/CANDIDATES.md from the files already in data/candidates/ (no network)")
    args = parser.parse_args(argv)
    if args.doc:
        evaluation = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
        text = render_doc(json.loads(PAPERS_PATH.read_text(encoding="utf-8")), evaluation["candidates"],
                          json.loads((PAPERS_PATH.parent / "verify_corpus.json").read_text(encoding="utf-8")),
                          evaluation["excluded_without_entry"], evaluation["retrieved_at"][:10])
        (project_root / "docs" / "CANDIDATES.md").write_text(text, encoding="utf-8", newline="\n")
        return 0
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    http = http or UrlHttp(token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    entries, records = [], []
    for index, item in enumerate(source["candidates"], start=1):
        entry, record = build_entry(index, item, http)
        entries.append(entry)
        records.append(record)
        print(f"{entry['paper_id']} {item['repo']}: {entry['title'][:60] or 'NO TITLE'} | {entry['license'] or 'NO LICENSE'}"
              f" | readme names paper: {record['readme_names_the_paper']}")
    PAPERS_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    EVALUATION_PATH.write_text(json.dumps(
        {"retrieved_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "input": "data/candidates/input.json",
         "excluded_without_entry": source.get("excluded_without_entry", []), "candidates": records},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
