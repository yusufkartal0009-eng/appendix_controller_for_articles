#!/usr/bin/env python3
"""Choose six new papers by the rules of docs/CORPUS_EXPANSION.md (#335).

    python scripts/corpus_expansion.py pool       # run the four searches of stage 1 once; write data/corpus_expansion/pool.json
    python scripts/corpus_expansion.py pool --stage 2    # stage 2 (and 3): only when fewer than six passed (document section 6)
    python scripts/corpus_expansion.py evaluate   # apply R1 to R7 in the hash order; write evaluation.json and papers.json

Set GH_TOKEN (or GITHUB_TOKEN) to avoid GitHub's API limits. The rules look only at metadata, the README, a few named files,
and the paper's text. Whether a paper installs or runs is never looked at.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.verify_corpus import (
    GITHUB_API,
    USER_AGENT,
    UrlHttp,
    _extract_page_title,
    verify_entry,
)
from src.config import ALLOWED_LICENSES, SEED_PAPERS_PATH

OUT_DIR = project_root / "data" / "corpus_expansion"
# Stage 1 is the pool of docs/CORPUS_EXPANSION.md section 2; stages 2 and 3 are its amendment (section 6), used in order only
# while fewer than six papers have passed.
STAGES = [
    [
        "topic:tabular-data language:Python arxiv.org in:readme",
        "topic:tabular-deep-learning language:Python arxiv.org in:readme",
        "topic:gradient-boosting language:Python arxiv.org in:readme",
        "topic:scikit-learn language:Python arxiv.org in:readme",
    ],
    [
        "topic:machine-learning language:Python arxiv.org in:readme",
        "topic:classification language:Python arxiv.org in:readme",
        "topic:regression language:Python arxiv.org in:readme",
        "topic:xgboost language:Python arxiv.org in:readme",
    ],
    [
        "topic:deep-learning language:Python arxiv.org in:readme",
        "topic:data-science language:Python arxiv.org in:readme",
        "topic:random-forest language:Python arxiv.org in:readme",
        "topic:feature-selection language:Python arxiv.org in:readme",
    ],
]
QUERIES = [q for stage in STAGES for q in stage]
POOL_PER_QUERY = 100
SELECT_COUNT = 6
MAX_REPO_SIZE_KB = 100_000
MAX_STATED_SIZE_MB = 500
MIN_TABLE_CAPTIONS = 2
MIN_DECIMAL_NUMBERS = 20
REQUIREMENT_FILE = re.compile(r"(^|/)(requirements[^/]*\.txt|setup\.py|environment\.yml|pyproject\.toml)$")
MAX_REQUIREMENT_FILES = 20
BACKSLASH = chr(92)
RULES = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")
FIRST_ID = 101  # new entries are paper_101, paper_102, ...: apart from the seed corpus


class Fetcher(Protocol):
    def search(self, query: str) -> list[str]: ...
    def meta(self, full_name: str) -> dict[str, Any] | None: ...
    def readme(self, full_name: str) -> str | None: ...
    def head_sha(self, full_name: str, branch: str) -> str | None: ...
    def tree(self, full_name: str, sha: str) -> list[dict[str, Any]]: ...
    def file(self, full_name: str, sha: str, path: str) -> str | None: ...
    def arxiv(self, arxiv_id: str) -> dict[str, Any] | None: ...


def candidate_hash(full_name: str) -> str:
    return hashlib.sha256(full_name.lower().encode("utf-8")).hexdigest()


def order_candidates(names: list[str]) -> list[str]:
    """Unique names (case-insensitive) in the ascending SHA-256 order of the lower-case name."""
    unique = {n.lower(): n for n in names}
    return [unique[k] for k in sorted(unique, key=candidate_hash)]


def find_run_command(readme: str, paths: set[str]) -> tuple[str, str] | None:
    """(command line, script path) of the first README line in a fenced block that starts with `python ` and a `.py` path
    that exists. The first non-option token after `python` must be the path (R3)."""
    for block in re.findall(r"```[^\n]*\n(.*?)```", readme, re.DOTALL):
        lines = block.splitlines()
        for index, raw in enumerate(lines):
            line = raw.strip()
            line = line[2:].strip() if line.startswith("$ ") else line
            if not line.startswith("python "):
                continue
            # a line that ends with a backslash continues on the next line; a trailing shell comment is not part of the command
            following = index + 1
            while line.endswith(BACKSLASH) and following < len(lines):
                line = line[:-1].rstrip() + " " + lines[following].strip()
                following += 1
            line = re.sub(r"\s+#.*$", "", line).rstrip(BACKSLASH).strip()
            tokens = line.split()
            script = next((t for t in tokens[1:] if not t.startswith("-")), "")
            path = script.removeprefix("./")
            if path.endswith(".py") and path in paths:
                return line, path
    return None


def stated_sizes_mb(readme: str) -> list[float]:
    sizes = []
    for number, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(MB|GB)\b", readme, re.IGNORECASE):
        sizes.append(float(number) * (1024 if unit.upper() == "GB" else 1))
    return sizes


def find_arxiv_id(readme: str) -> str | None:
    match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", readme)
    return match.group(1) if match else None


def evaluate_candidate(full_name: str, fetcher: Fetcher, seed_repos: set[str], taken_repos: set[str],
                       seed_papers: set[str] = frozenset(), taken_papers: set[str] = frozenset()) -> dict[str, Any]:  # type: ignore[assignment]
    """Apply R1 to R7 in order. The result names the first rule that failed, or carries the entry that passed.

    R7 looks at the repository and at the paper (its arXiv id): both must be new."""
    result: dict[str, Any] = {"full_name": full_name, "hash": candidate_hash(full_name), "passed": False,
                              "failed_rule": None, "detail": ""}

    def fail(rule: str, detail: str) -> dict[str, Any]:
        result.update(failed_rule=rule, detail=detail)
        return result

    meta = fetcher.meta(full_name)
    if meta is None:
        return fail("R1", "repository metadata not available")
    if meta.get("private") or meta.get("language") != "Python" or meta.get("archived") or meta.get("fork"):
        return fail("R1", f"language {meta.get('language')}, archived {meta.get('archived')}, fork {meta.get('fork')}")
    spdx = (meta.get("license") or {}).get("spdx_id")
    if spdx not in ALLOWED_LICENSES:
        return fail("R2", f"license {spdx}")
    readme = fetcher.readme(full_name)
    sha = fetcher.head_sha(full_name, meta.get("default_branch") or "main")
    if readme is None or sha is None:
        return fail("R3", "README or head commit not available")
    tree = fetcher.tree(full_name, sha)
    paths = {item["path"] for item in tree if item.get("type") == "blob"}
    command = find_run_command(readme, paths)
    if command is None:
        return fail("R3", "no `python <script>.py` line in a fenced README block with a script that exists")
    run_command, script = command
    texts = {"README": readme}
    required = sorted(p for p in paths if REQUIREMENT_FILE.search(p))[:MAX_REQUIREMENT_FILES]
    for path in required:
        texts[path] = fetcher.file(full_name, sha, path) or ""
    gpu = sorted(name for name, text in texts.items() if re.search(r"gpu|cuda", text, re.IGNORECASE))
    if gpu or re.search(r"gpu|cuda", run_command, re.IGNORECASE):
        return fail("R4", f"gpu or cuda mentioned in {', '.join(gpu) or 'the run command'}")
    if (meta.get("size") or 0) > MAX_REPO_SIZE_KB:
        return fail("R5", f"repository size {meta.get('size')} KB")
    attributes = fetcher.file(full_name, sha, ".gitattributes") if ".gitattributes" in paths else ""
    if "filter=lfs" in (attributes or ""):
        return fail("R5", "Git LFS files")
    big = [s for s in stated_sizes_mb(readme) if s >= MAX_STATED_SIZE_MB]
    if big:
        return fail("R5", f"README states a size of {max(big):g} MB")
    arxiv_id = find_arxiv_id(readme)
    if arxiv_id is None:
        return fail("R6", "no arXiv link in the README")
    paper = fetcher.arxiv(arxiv_id)
    if paper is None or not paper.get("title"):
        return fail("R6", f"arXiv {arxiv_id} not available")
    text = paper.get("text") or ""
    captions = len(re.findall(r"^Table \d+", text, re.MULTILINE))
    decimals = len(re.findall(r"\b\d+\.\d+\b", text))
    if captions < MIN_TABLE_CAPTIONS or decimals < MIN_DECIMAL_NUMBERS:
        return fail("R6", f"{captions} table captions and {decimals} decimal numbers in the paper's text")
    if full_name.lower() in seed_repos or full_name.lower() in taken_repos:
        return fail("R7", "repository already in the corpus or already selected")
    if arxiv_id in seed_papers or arxiv_id in taken_papers:
        return fail("R7", f"paper arXiv:{arxiv_id} already in the corpus or already selected")
    result.update(passed=True, detail=f"{captions} table captions, {decimals} decimal numbers",
                  entry={"title": paper["title"], "year": paper.get("year"), "venue": "arXiv preprint",
                         "repo_url": f"https://github.com/{meta['full_name']}", "repo_commit": sha,
                         "paper_url": f"https://arxiv.org/abs/{arxiv_id}", "license": spdx, "target_script": script,
                         "run_command": run_command,
                         "readme_url": f"https://github.com/{meta['full_name']}/blob/{sha}/README.md"})
    return result


def seed_repo_names(path: Path = SEED_PAPERS_PATH) -> set[str]:
    names = set()
    for entry in json.loads(path.read_text(encoding="utf-8")):
        match = re.match(r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", entry["repo_url"])
        if match:
            names.add(match.group(1).lower())
    return names


def seed_arxiv_ids(path: Path = SEED_PAPERS_PATH) -> set[str]:
    ids = {find_arxiv_id(entry.get("paper_url") or "") for entry in json.loads(path.read_text(encoding="utf-8"))}
    return {i for i in ids if i}


def select(candidates: list[str], fetcher: Fetcher, seed_repos: set[str], http: Any = None,
           count: int = SELECT_COUNT, seed_papers: set[str] = frozenset()) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(all evaluations in order, the selected evaluations). A passing candidate that fails `verify_corpus` is
    recorded as eliminated and the next candidate takes its place (docs/CORPUS_EXPANSION.md section 4)."""
    evaluations: list[dict[str, Any]] = []
    chosen: list[dict[str, Any]] = []
    for full_name in candidates:
        if len(chosen) == count:
            break
        taken = {c["full_name"].lower() for c in chosen}
        taken_papers = {find_arxiv_id(c["entry"]["paper_url"]) for c in chosen}
        result = evaluate_candidate(full_name, fetcher, seed_repos, taken, seed_papers, taken_papers)
        if result["passed"] and http is not None:
            entry = dict(result["entry"], paper_id=f"paper_{FIRST_ID + len(chosen)}")
            report = verify_entry(entry, http)
            if not report.ok:
                failed = [f"{c.name}: {c.detail}" for c in report.checks if not c.ok]
                result.update(passed=False, failed_rule="verify_corpus", detail="; ".join(failed))
                result.pop("entry", None)
        evaluations.append(result)
        if result["passed"]:
            chosen.append(result)
    return evaluations, chosen


def papers_json(chosen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = []
    for index, result in enumerate(chosen):
        e = result["entry"]
        entries.append({"paper_id": f"paper_{FIRST_ID + index}", "title": e["title"], "year": e["year"], "venue": e["venue"],
                        "repo_url": e["repo_url"], "repo_commit": e["repo_commit"], "paper_url": e["paper_url"],
                        "license": e["license"], "target_script": e["target_script"], "run_command": e["run_command"],
                        "readme_url": e["readme_url"], "expected_claims": {}, "source_table_or_section": {}})
    return entries


class NetFetcher:
    """The real fetcher: the GitHub API, raw files, and arXiv. Every call is a plain GET."""

    def __init__(self, token: str | None) -> None:
        self.http = UrlHttp(token=token)
        self.token = token

    def _json(self, url: str) -> Any:
        status, body = self.http.get(url)
        return json.loads(body) if status == 200 and body else None

    def search(self, query: str) -> list[str]:
        url = f"{GITHUB_API}/search/repositories?q={urllib.parse.quote(query)}&per_page={POOL_PER_QUERY}"
        data = self._json(url)
        return [item["full_name"] for item in (data or {}).get("items", [])]

    def meta(self, full_name: str) -> dict[str, Any] | None:
        return self._json(f"{GITHUB_API}/repos/{full_name}")

    def readme(self, full_name: str) -> str | None:
        data = self._json(f"{GITHUB_API}/repos/{full_name}/readme")
        return base64.b64decode(data["content"]).decode("utf-8", "replace") if data else None

    def head_sha(self, full_name: str, branch: str) -> str | None:
        data = self._json(f"{GITHUB_API}/repos/{full_name}/commits/{branch}")
        return data.get("sha") if data else None

    def tree(self, full_name: str, sha: str) -> list[dict[str, Any]]:
        data = self._json(f"{GITHUB_API}/repos/{full_name}/git/trees/{sha}?recursive=1")
        return (data or {}).get("tree", [])

    def file(self, full_name: str, sha: str, path: str) -> str | None:
        status, body = self.http.get(f"https://raw.githubusercontent.com/{full_name}/{sha}/{path}")
        return body if status == 200 else None

    def arxiv(self, arxiv_id: str) -> dict[str, Any] | None:
        status, page = self.http.get(f"https://arxiv.org/abs/{arxiv_id}")
        if status != 200:
            return None
        title = _extract_page_title(page)
        date = re.search(r'<meta name="citation_date" content="(\d{4})', page)
        request = urllib.request.Request(f"https://arxiv.org/pdf/{arxiv_id}", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                pdf = response.read()
        except (urllib.error.URLError, OSError):
            return {"title": title, "year": int(date.group(1)) if date else None, "text": ""}
        import pypdf

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "paper.pdf"
            path.write_bytes(pdf)
            try:
                text = "\n".join((page_.extract_text() or "") for page_ in pypdf.PdfReader(str(path)).pages)
            except Exception:  # noqa: BLE001 - an unreadable PDF fails R6 with an empty text
                text = ""
        return {"title": title, "year": int(date.group(1)) if date else None, "text": text}


def pool_path(out_dir: Path, stage: int) -> Path:
    return out_dir / ("pool.json" if stage == 1 else f"pool_stage{stage}.json")


def command_pool(fetcher: Fetcher, out_dir: Path, stage: int = 1) -> dict[str, Any]:
    """Run the searches of one stage and store them. Names found in an earlier stage's pool are left out of this one."""
    searches = []
    names: list[str] = []
    for query in STAGES[stage - 1]:
        found = fetcher.search(query)
        searches.append({"query": query, "results": found})
        names.extend(found)
    earlier = {c["full_name"].lower() for s in range(1, stage) if pool_path(out_dir, s).is_file()
               for c in json.loads(pool_path(out_dir, s).read_text(encoding="utf-8"))["candidates_in_order"]}
    ordered = [n for n in order_candidates(names) if n.lower() not in earlier]
    pool = {"stage": stage, "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"), "per_query_limit": POOL_PER_QUERY,
            "searches": searches, "candidates_in_order": [{"full_name": n, "hash": candidate_hash(n)} for n in ordered]}
    out_dir.mkdir(parents=True, exist_ok=True)
    pool_path(out_dir, stage).write_text(json.dumps(pool, indent=2) + "\n", encoding="utf-8")
    return pool


def command_evaluate(fetcher: Fetcher, out_dir: Path, http: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[str] = []
    stage_of: dict[str, int] = {}
    for stage in range(1, len(STAGES) + 1):
        if pool_path(out_dir, stage).is_file():
            for c in json.loads(pool_path(out_dir, stage).read_text(encoding="utf-8"))["candidates_in_order"]:
                candidates.append(c["full_name"])
                stage_of[c["full_name"]] = stage
    evaluations, chosen = select(candidates, fetcher, seed_repo_names(), http, seed_papers=seed_arxiv_ids())
    for result in evaluations:
        result["stage"] = stage_of[result["full_name"]]
    document = {"evaluated_at": datetime.now(UTC).isoformat(timespec="seconds"), "rules": "docs/CORPUS_EXPANSION.md",
                "selected": len(chosen), "evaluated": len(evaluations), "candidates": evaluations}
    (out_dir / "evaluation.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    (out_dir / "papers.json").write_text(json.dumps(papers_json(chosen), indent=2) + "\n", encoding="utf-8")
    return evaluations, chosen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Choose six new papers by the rules of docs/CORPUS_EXPANSION.md.")
    parser.add_argument("command", choices=["pool", "evaluate"])
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    parser.add_argument("--stage", type=int, choices=[1, 2, 3], default=1, help="pool: which stage's searches to run")
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    fetcher = NetFetcher(token)
    out_dir = Path(args.out_dir)
    if args.command == "pool":
        pool = command_pool(fetcher, out_dir, args.stage)
        print(f"pool stage {args.stage}: {len(pool['candidates_in_order'])} candidates from {len(pool['searches'])} searches")
        return 0
    evaluations, chosen = command_evaluate(fetcher, out_dir, fetcher.http)
    print(f"evaluated {len(evaluations)} candidates, selected {len(chosen)}")
    return 0 if len(chosen) == SELECT_COUNT else 1


if __name__ == "__main__":
    sys.exit(main())
