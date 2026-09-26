#!/usr/bin/env python3
"""Verify that every seed corpus entry points at a real paper, repository, and script.

For each entry in the corpus JSON (default: data/seed_papers.json):
  1. paper   - the paper's title matches the entry title (arXiv abstract page; Crossref for DOI
               links such as bioRxiv, whose pages rate-limit automated clients)
  2. repo    - the GitHub repository exists (renames are followed and reported)
  3. license - GitHub's license (spdx_id) is allowed and equals the declared license
  4. script  - target_script exists in the repository at the pinned commit (repo_commit)

Any failure, including a network error, makes the script exit with code 1.
Set GITHUB_TOKEN (or GH_TOKEN) to avoid GitHub API rate limits.
"""

from __future__ import annotations

import argparse
import difflib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import ALLOWED_LICENSES, SEED_PAPERS_PATH  # noqa: E402

GITHUB_API = "https://api.github.com"
CROSSREF_API = "https://api.crossref.org/works"
TITLE_MATCH_THRESHOLD = 0.9
USER_AGENT = "repro-radar-corpus-verifier/1.0 (+https://github.com/yusufkartal0009-eng/appendix_controller_for_articles)"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass
class EntryReport:
    paper_id: str
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)


class UrlHttp:
    """Minimal HTTP GET client. Returns (status, body); raises OSError on network failure."""

    def __init__(self, token: Optional[str] = None, timeout: int = 30):
        self.token = token
        self.timeout = timeout

    def get(self, url: str) -> Tuple[int, str]:
        headers = {"User-Agent": USER_AGENT}
        if url.startswith(GITHUB_API):
            headers["Accept"] = "application/vnd.github+json"
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, ""


def parse_arxiv_id(url: str) -> Optional[str]:
    match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", url or "")
    return match.group(1) if match else None


def parse_doi(url: str) -> Optional[str]:
    match = re.search(r"(?:doi\.org|biorxiv\.org/content|medrxiv\.org/content)/(10\.\d{4,9}/[^\s?#]+?)(?:v\d+)?/?(?:[?#].*)?$", url or "")
    return match.group(1) if match else None


def parse_github_repo(url: str) -> Optional[Tuple[str, str]]:
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url or "")
    return (match.group(1), match.group(2)) if match else None


def _normalize_title(title: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", title.lower()).split())


def title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()


def titles_match(a: str, b: str) -> bool:
    return title_similarity(a, b) >= TITLE_MATCH_THRESHOLD


def _extract_page_title(body: str) -> Optional[str]:
    match = re.search(r'<meta\s+name="citation_title"\s+content="([^"]*)"', body)
    if not match:
        match = re.search(r"<title>(.*?)</title>", body, re.S)
    return html.unescape(match.group(1)).strip() if match else None


def check_paper(entry: dict, http) -> CheckResult:
    url = entry.get("paper_url")
    if not url:
        return CheckResult("paper", False, "no paper_url")
    arxiv_id = parse_arxiv_id(url)
    doi = None if arxiv_id else parse_doi(url)
    if arxiv_id:
        page_url = f"https://arxiv.org/abs/{arxiv_id}"
    elif doi:
        page_url = f"{CROSSREF_API}/{doi}"
    else:
        page_url = url
    try:
        status, body = http.get(page_url)
    except OSError as exc:
        return CheckResult("paper", False, f"network error fetching {page_url}: {exc}")
    if status != 200:
        return CheckResult("paper", False, f"HTTP {status} for {page_url}")
    if doi:
        titles = (json.loads(body).get("message") or {}).get("title") or []
        page_title = html.unescape(titles[0]).strip() if titles else None
    else:
        page_title = _extract_page_title(body)
    if not page_title:
        return CheckResult("paper", False, f"no title found at {page_url}")
    similarity = title_similarity(entry.get("title", ""), page_title)
    if similarity < TITLE_MATCH_THRESHOLD:
        return CheckResult("paper", False, f"title mismatch ({similarity:.2f}): page says '{page_title}'")
    return CheckResult("paper", True, f"title matches ({similarity:.2f})")


def check_repo_and_license(entry: dict, http) -> Tuple[CheckResult, CheckResult, Optional[str]]:
    parsed = parse_github_repo(entry.get("repo_url", ""))
    if not parsed:
        reason = f"not a GitHub repository URL: {entry.get('repo_url')}"
        return CheckResult("repo", False, reason), CheckResult("license", False, "repository not checked"), None
    declared = f"{parsed[0]}/{parsed[1]}"
    api_url = f"{GITHUB_API}/repos/{declared}"
    try:
        status, body = http.get(api_url)
    except OSError as exc:
        reason = f"network error fetching {api_url}: {exc}"
        return CheckResult("repo", False, reason), CheckResult("license", False, "repository not checked"), None
    if status != 200:
        return (
            CheckResult("repo", False, f"HTTP {status} for {declared}"),
            CheckResult("license", False, "repository not found"),
            None,
        )
    data = json.loads(body)
    full_name = data.get("full_name", declared)
    if full_name.lower() != declared.lower():
        repo = CheckResult("repo", True, f"exists, renamed: {declared} -> {full_name} (update repo_url)")
    else:
        repo = CheckResult("repo", True, f"exists: {full_name}")

    spdx = (data.get("license") or {}).get("spdx_id")
    declared_license = entry.get("license", "")
    if not spdx or spdx == "NOASSERTION":
        license_check = CheckResult("license", False, f"GitHub reports no recognized license (declared {declared_license})")
    elif spdx not in ALLOWED_LICENSES:
        license_check = CheckResult("license", False, f"{spdx} is not an allowed license")
    elif spdx.lower() != declared_license.lower():
        license_check = CheckResult("license", False, f"declared {declared_license}, GitHub reports {spdx}")
    else:
        license_check = CheckResult("license", True, spdx)
    return repo, license_check, full_name


def check_script(entry: dict, full_name: Optional[str], http) -> CheckResult:
    if not full_name:
        return CheckResult("script", False, "repository not found")
    commit = entry.get("repo_commit")
    if not commit or not re.fullmatch(r"[0-9a-f]{40}", commit):
        return CheckResult("script", False, "no pinned commit: add a 40-character repo_commit")
    path = urllib.parse.quote(entry.get("target_script", ""))
    api_url = f"{GITHUB_API}/repos/{full_name}/contents/{path}?ref={commit}"
    try:
        status, body = http.get(api_url)
    except OSError as exc:
        return CheckResult("script", False, f"network error fetching {api_url}: {exc}")
    if status != 200:
        return CheckResult("script", False, f"{entry.get('target_script')} not found at {commit[:12]} (HTTP {status})")
    data = json.loads(body)
    if not isinstance(data, dict) or data.get("type") != "file":
        return CheckResult("script", False, f"{entry.get('target_script')} is not a file at {commit[:12]}")
    return CheckResult("script", True, f"{entry.get('target_script')} exists at {commit[:12]}")


def verify_entry(entry: dict, http) -> EntryReport:
    report = EntryReport(paper_id=entry.get("paper_id", "<missing paper_id>"))
    report.checks.append(check_paper(entry, http))
    repo, license_check, full_name = check_repo_and_license(entry, http)
    report.checks.extend([repo, license_check, check_script(entry, full_name, http)])
    return report


def _print_report(reports: List[EntryReport]) -> None:
    for report in reports:
        print(f"{report.paper_id}: {'PASS' if report.ok else 'FAIL'}")
        for check in report.checks:
            print(f"  [{'ok' if check.ok else 'FAIL'}] {check.name:<8} {check.detail}")
    passed = sum(r.ok for r in reports)
    print(f"\n{passed} of {len(reports)} entries passed verification.")


def main(argv: Optional[List[str]] = None, http=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("corpus", nargs="?", default=str(SEED_PAPERS_PATH), help="Corpus JSON file")
    parser.add_argument("--json", dest="json_out", help="Also write the results as JSON to this path")
    args = parser.parse_args(argv)

    entries = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    if http is None:
        http = UrlHttp(token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    reports = [verify_entry(entry, http) for entry in entries]
    _print_report(reports)

    if args.json_out:
        payload = [{"paper_id": r.paper_id, "ok": r.ok, "checks": [asdict(c) for c in r.checks]} for r in reports]
        Path(args.json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0 if reports and all(r.ok for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
