#!/usr/bin/env python3
"""Choose ReScience C articles by the rules of docs/EXTERNAL_VALIDATION.md (#383).

    python scripts/external_validation.py pool        # list the article directories of ReScience/articles, store them
    python scripts/external_validation.py evaluate    # apply E1 to E8 in the hash order, write papers.json and evaluation.json
    python scripts/external_validation.py doc         # print the generated selection table

Needs `GITHUB_TOKEN` or `GH_TOKEN` in the environment (read-only calls; the token is never stored). The pool is stored
unchanged with its date and the commit of the articles repository; the evaluation reads it, so it can be repeated.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import yaml

from scripts.corpus_expansion import (
    BACKSLASH,
    MAX_REPO_SIZE_KB,
    MAX_REQUIREMENT_FILES,
    MAX_STATED_SIZE_MB,
    MIN_DECIMAL_NUMBERS,
    MIN_TABLE_CAPTIONS,
    REQUIREMENT_FILE,
    NetFetcher,
    find_run_command,
    seed_repo_names,
    stated_sizes_mb,
)
from scripts.verify_corpus import (
    GITHUB_API,
    UrlHttp,
    check_repo_and_license,
    check_script,
    title_similarity,
)
from src.config import ALLOWED_LICENSES, PROJECT_ROOT

OUT_DIR = PROJECT_ROOT / "data" / "external_validation"
ARTICLES_REPO = "ReScience/articles"
SELECT_COUNT = 4  # 8 in the rules as first written; amendment 4 (docs/EXTERNAL_VALIDATION.md section 11) makes it 4
FIRST_ID = 201
RULES = ("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8")
CODE_URL = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?(?:/(?:tree|releases/tag)/([^\s#?]+))?/?$")
RAW = "https://raw.githubusercontent.com"
NOTEBOOK_RUNNERS = ("jupyter nbconvert", "jupyter-nbconvert", "jupyter execute", "papermill")
NOT_RUN_TARGETS = {"install", "clean", "setup", "env", "deps"}  # `make` targets that prepare or tidy, like `setup.py` (amendment 4)


class ArticleFetcher(Protocol):
    def article_dirs(self) -> tuple[str, list[str]]: ...
    def article_yaml(self, commit: str, directory: str) -> str | None: ...
    def article_pdf(self, commit: str, directory: str) -> bytes | None: ...
    def meta(self, full_name: str) -> dict[str, Any] | None: ...
    def resolve(self, full_name: str, ref: str) -> str | None: ...
    def readme_at(self, full_name: str, sha: str) -> str | None: ...
    def tree(self, full_name: str, sha: str) -> list[dict[str, Any]]: ...
    def file(self, full_name: str, sha: str, path: str) -> str | None: ...


def directory_hash(name: str) -> str:
    return hashlib.sha256(name.lower().encode("utf-8")).hexdigest()


def order_directories(names: list[str]) -> list[str]:
    return sorted(set(names), key=directory_hash)


def pdf_text(pdf: bytes) -> list[str]:
    import pypdf

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "article.pdf"
        path.write_bytes(pdf)
        try:
            return [(page.extract_text() or "") for page in pypdf.PdfReader(str(path)).pages]
        except Exception:  # noqa: BLE001 - an unreadable PDF fails E7 with no text
            return []


def table_statistics(pages: list[str]) -> tuple[int, int]:
    """(table captions, decimal numbers on the pages that hold a caption) of the article text (E7)."""
    captions = 0
    decimals = 0
    for page in pages:
        found = len(re.findall(r"^Table \d+", page, re.MULTILINE))
        captions += found
        if found:
            decimals += len(re.findall(r"\b\d+\.\d+\b", page))
    return captions, decimals


def mappings(value: Any) -> list[dict[str, Any]]:
    """The mappings of a field that article.yaml writes as one mapping or as a list of one-key mappings."""
    return [value] if isinstance(value, dict) else [v for v in (value if isinstance(value, list) else []) if isinstance(v, dict)]


def field(article: dict[str, Any], key: str, name: str) -> Any:
    """The first non-empty `name` among the mappings of article[key]."""
    return next((m[name] for m in mappings(article.get(key)) if m.get(name)), None)


def code_entry(article: dict[str, Any]) -> dict[str, Any] | None:
    """The first `code` mapping with a GitHub URL."""
    return next((m for m in mappings(article.get("code")) if CODE_URL.match(str(m.get("url") or "").strip())), None)


def readme_command_lines(readme: str) -> list[str]:
    """The logical command lines of the fenced README blocks, in document order: a leading `$ ` is dropped, backslash
    continuations are joined and a trailing shell comment is removed."""
    commands = []
    for block in re.findall(r"```[^\n]*\n(.*?)```", readme, re.DOTALL):
        lines = block.splitlines()
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            index += 1
            line = line[2:].strip() if line.startswith("$ ") else line
            while line.endswith(BACKSLASH) and index < len(lines):
                line = line[:-1].rstrip() + " " + lines[index].strip()
                index += 1
            commands.append(re.sub(r"\s+#.*$", "", line).rstrip(BACKSLASH).strip())
    return commands


def find_widened_run_command(readme: str, paths: set[str]) -> tuple[str, str, str] | None:
    """(command line, target file, kind) of the first README command that runs the code (E4 after amendment 4): a
    `python <script>.py` line (R3), `python -m <module>` of a module in the repository, `make [target]` with a Makefile at
    the root, or a notebook run (`jupyter nbconvert --execute`, `jupyter execute`, `papermill`) of a notebook in the
    repository. The target is a file at the pinned commit."""
    for line in readme_command_lines(readme):
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] == "python":
            if len(tokens) > 2 and tokens[1] == "-m":
                base = tokens[2].replace(".", "/")
                target = next((c for c in (f"{base}.py", f"{base}/__main__.py") if c in paths), None)
                if target:
                    return line, target, "python_module"
                continue
            found = find_run_command(f"```\n{line}\n```", paths)
            if found:
                return found[0], found[1], "python_script"
        elif tokens[0] == "make":
            makefile = next((p for p in ("Makefile", "makefile", "GNUmakefile") if p in paths), None)
            targets = [t for t in tokens[1:] if not t.startswith("-") and "=" not in t]
            if makefile and not set(targets) & NOT_RUN_TARGETS:
                return line, makefile, "make"
        elif line.startswith(NOTEBOOK_RUNNERS):
            converts_only = line.startswith(("jupyter nbconvert", "jupyter-nbconvert")) and "--execute" not in tokens
            notebook = next((t.removeprefix("./") for t in tokens if t.endswith(".ipynb") and t.removeprefix("./") in paths), None)
            if notebook and not converts_only:
                return line, notebook, "notebook"
    return None


def evaluate_article(directory: str, commit: str, fetcher: ArticleFetcher, seed_repos: set[str],
                     taken_repos: set[str]) -> dict[str, Any]:
    """Apply E1 to E8 in order. The result names the first rule that failed, or carries the entry that passed."""
    result: dict[str, Any] = {"directory": directory, "hash": directory_hash(directory), "passed": False, "failed_rule": None,
                              "detail": ""}

    def fail(rule: str, detail: str) -> dict[str, Any]:
        result.update(failed_rule=rule, detail=detail)
        return result

    raw = fetcher.article_yaml(commit, directory)
    try:
        article = yaml.safe_load(raw) if raw else None
    except yaml.YAMLError:
        article = None
    if not isinstance(article, dict):
        return fail("E1", "article.yaml missing or not a mapping")
    review_url = str(field(article, "review", "url") or "").strip()
    if "github.com" not in review_url:
        return fail("E1", "no review url that points to GitHub")
    pdf = fetcher.article_pdf(commit, directory)
    if not pdf:
        return fail("E1", "article.pdf missing")
    language = article.get("language")
    if "python" not in json.dumps(language).lower():
        return fail("E2", f"language {language!r}")
    code = code_entry(article)
    if code is None:
        return fail("E3", "no code entry with a GitHub repository URL")
    owner, repo, ref = CODE_URL.match(str(code["url"]).strip()).groups()  # type: ignore[union-attr]
    full_name = f"{owner}/{repo}"
    meta = fetcher.meta(full_name)
    if meta is None or meta.get("private") or meta.get("archived") or meta.get("language") != "Python":
        return fail("E3", f"repository {full_name}: " + ("not available" if meta is None else
                                                          f"language {meta.get('language')}, archived {meta.get('archived')}"))
    sha = fetcher.resolve(full_name, ref or meta.get("default_branch") or "main")
    fallback = None
    if sha is None and ref:
        # Amendment 2 (docs/EXTERNAL_VALIDATION.md section 9): a ref named in the URL that does not exist is replaced by the
        # head of the default branch.
        fallback = f"the ref {ref} named in the code URL does not exist; the head of the default branch is used"
        sha = fetcher.resolve(full_name, meta.get("default_branch") or "main")
    if sha is None:
        return fail("E3", f"commit of {ref or 'the default branch'} not available")
    readme = fetcher.readme_at(full_name, sha)
    if readme is None:
        return fail("E4", "README not available at the pinned commit")
    paths = {item["path"] for item in fetcher.tree(full_name, sha) if item.get("type") == "blob"}
    command = find_widened_run_command(readme, paths)
    if command is None:
        return fail("E4", "no `python <script>.py`, `python -m`, `make`, or notebook run line in a fenced README block "
                          "that names a file of the repository")
    run_command, script, kind = command
    texts = {"README": readme}
    for path in sorted(p for p in paths if REQUIREMENT_FILE.search(p))[:MAX_REQUIREMENT_FILES]:
        texts[path] = fetcher.file(full_name, sha, path) or ""
    gpu = sorted(name for name, text in texts.items() if re.search(r"gpu|cuda", text, re.IGNORECASE))
    if gpu or re.search(r"gpu|cuda", run_command, re.IGNORECASE):
        return fail("E5", f"gpu or cuda mentioned in {', '.join(gpu) or 'the run command'}")
    if (meta.get("size") or 0) > MAX_REPO_SIZE_KB:
        return fail("E6", f"repository size {meta.get('size')} KB")
    attributes = fetcher.file(full_name, sha, ".gitattributes") if ".gitattributes" in paths else ""
    if "filter=lfs" in (attributes or ""):
        return fail("E6", "Git LFS files")
    big = [s for s in stated_sizes_mb(readme) if s >= MAX_STATED_SIZE_MB]
    if big:
        return fail("E6", f"README states a size of {max(big):g} MB")
    spdx = (meta.get("license") or {}).get("spdx_id")
    if spdx not in ALLOWED_LICENSES:
        return fail("E6", f"license {spdx}")
    captions, decimals = table_statistics(pdf_text(pdf))
    if captions < MIN_TABLE_CAPTIONS or decimals < MIN_DECIMAL_NUMBERS:
        return fail("E7", f"{captions} table captions and {decimals} decimal numbers on the pages with a caption")
    if full_name.lower() in seed_repos or full_name.lower() in taken_repos:
        return fail("E8", "repository already in a corpus or already selected")
    zenodo = re.fullmatch(r"10\.5281_zenodo\.(\d+)", directory)
    year = re.search(r"(\d{4})", str(field(article, "dates", "published") or ""))
    result.update(
        passed=True, detail=f"{captions} table captions, {decimals} decimal numbers" + (f"; {fallback}" if fallback else ""),
        entry={"title": str(article.get("title", "")).strip(), "year": int(year.group(1)) if year else None,
               "venue": "ReScience C", "repo_url": f"https://github.com/{meta['full_name']}", "repo_commit": sha,
               "paper_url": f"https://zenodo.org/records/{zenodo.group(1)}" if zenodo else
               "https://doi.org/" + directory.replace("_", "/", 1),
               "license": spdx, "target_script": script, "run_command": run_command, "command_kind": kind,
               "readme_url": f"https://github.com/{meta['full_name']}/blob/{sha}/README.md",
               "article_yaml_url": f"{RAW}/{ARTICLES_REPO}/{commit}/{directory}/article.yaml",
               "review_url": review_url, "article_pdf_url": f"{RAW}/{ARTICLES_REPO}/{commit}/{directory}/article.pdf",
               "article_pdf_sha256": hashlib.sha256(pdf).hexdigest()})
    return result


def verify_selected(entry: dict[str, Any], http: Any, pdf: bytes | None = None) -> list[tuple[str, bool, str]]:
    """The checks of `scripts/verify_corpus.py` for repository, license and script, plus a check that the stored PDF's
    text carries the article's title (the paper check of `verify_corpus` reads arXiv or Crossref and does not know every
    DOI of the articles repository)."""
    repo, license_check, full_name = check_repo_and_license(entry, http)
    script = check_script(entry, full_name, http)
    checks = [(c.name, c.ok, c.detail) for c in (repo, license_check, script)]
    if pdf is not None:
        text = " ".join(pdf_text(pdf)[:1])
        words = re.sub(r"[^a-z0-9]+", " ", entry["title"].lower()).split()
        found = bool(words) and sum(w in re.sub(r"[^a-z0-9]+", " ", text.lower()).split() for w in words) / len(words) >= 0.8
        checks.append(("article", found, "the title words are on the first page of article.pdf" if found else
                       f"title not found on the first page (similarity {title_similarity(entry['title'], text[:300]):.2f})"))
    return checks


def select(directories: list[str], commit: str, fetcher: ArticleFetcher, seed_repos: set[str], http: Any = None,
           count: int = SELECT_COUNT) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(all evaluations in order, the selected ones). A passing article that fails `verify_selected` is eliminated and the
    next one takes its place (docs/EXTERNAL_VALIDATION.md section 4)."""
    evaluations: list[dict[str, Any]] = []
    chosen: list[dict[str, Any]] = []
    for directory in directories:
        if len(chosen) == count:
            break
        taken = {c["entry"]["repo_url"].removeprefix("https://github.com/").lower() for c in chosen}
        result = evaluate_article(directory, commit, fetcher, seed_repos, taken)
        if result["passed"] and http is not None:
            checks = verify_selected(dict(result["entry"], paper_id=f"paper_{FIRST_ID + len(chosen)}"), http,
                                     fetcher.article_pdf(commit, directory))
            failed = [f"{name}: {detail}" for name, ok, detail in checks if not ok]
            if failed:
                result.update(passed=False, failed_rule="verify", detail="; ".join(failed))
                result.pop("entry", None)
        evaluations.append(result)
        if result["passed"]:
            chosen.append(result)
    return evaluations, chosen


def papers_json(chosen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = ("title", "year", "venue", "repo_url", "repo_commit", "paper_url", "license", "target_script", "run_command",
            "readme_url", "command_kind", "article_yaml_url", "review_url", "article_pdf_url", "article_pdf_sha256")
    return [{"paper_id": f"paper_{FIRST_ID + i}", **{k: c["entry"][k] for k in keys},
             "expected_verdict": "reproducible", "expected_claims": {},
             "source_table_or_section": {}} for i, c in enumerate(chosen)]


class RetryHttp(UrlHttp):
    """`UrlHttp` that tries again when the connection fails (the owner's network drops now and then)."""

    ATTEMPTS = 6

    def get(self, url: str) -> tuple[int, str]:
        for attempt in range(1, self.ATTEMPTS + 1):
            try:
                return super().get(url)
            except OSError:
                if attempt == self.ATTEMPTS:
                    raise
                time.sleep(5 * attempt)
        raise AssertionError("unreachable")


class ReScienceFetcher(NetFetcher):
    """The real fetcher: GitHub API and raw files."""

    def __init__(self, token: str | None) -> None:
        super().__init__(token)
        self.http = RetryHttp(token=token, timeout=60)

    def article_dirs(self) -> tuple[str, list[str]]:
        head = self._json(f"{GITHUB_API}/repos/{ARTICLES_REPO}/commits/HEAD")
        commit = head["sha"]
        tree = self._json(f"{GITHUB_API}/repos/{ARTICLES_REPO}/git/trees/{commit}")
        return commit, [i["path"] for i in tree["tree"] if i["type"] == "tree"]

    def article_yaml(self, commit: str, directory: str) -> str | None:
        status, body = self.http.get(f"{RAW}/{ARTICLES_REPO}/{commit}/{urllib.parse.quote(directory)}/article.yaml")
        return body if status == 200 else None

    def article_pdf(self, commit: str, directory: str) -> bytes | None:
        import urllib.request

        request = urllib.request.Request(f"{RAW}/{ARTICLES_REPO}/{commit}/{urllib.parse.quote(directory)}/article.pdf",
                                         headers={"User-Agent": "repro-radar"})
        for attempt in range(1, RetryHttp.ATTEMPTS + 1):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    return response.read()
            except urllib.error.HTTPError:
                return None
            except (OSError, http.client.HTTPException):  # a dropped connection (IncompleteRead) is tried again
                time.sleep(5 * attempt)
        return None

    def resolve(self, full_name: str, ref: str) -> str | None:
        data = self._json(f"{GITHUB_API}/repos/{full_name}/commits/{urllib.parse.quote(ref, safe='')}")
        return data.get("sha") if data else None

    def readme_at(self, full_name: str, sha: str) -> str | None:
        import base64

        data = self._json(f"{GITHUB_API}/repos/{full_name}/readme?ref={sha}")
        return base64.b64decode(data["content"]).decode("utf-8", "replace") if data else None


def command_pool(fetcher: ArticleFetcher, out_dir: Path) -> dict[str, Any]:
    commit, directories = fetcher.article_dirs()
    pool = {"retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"), "repository": ARTICLES_REPO, "commit": commit,
            "directories_in_order": [{"directory": d, "hash": directory_hash(d)} for d in order_directories(directories)]}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pool.json").write_text(json.dumps(pool, indent=2) + "\n", encoding="utf-8")
    return pool


def command_evaluate(fetcher: ArticleFetcher, out_dir: Path, http: Any, seed_paths: list[Path] | None = None):
    pool = json.loads((out_dir / "pool.json").read_text(encoding="utf-8"))
    seed: set[str] = set()
    for path in seed_paths or [project_root / "data" / "seed_papers.json", project_root / "data" / "corpus_expansion" / "papers.json"]:
        if path.is_file():
            seed |= seed_repo_names(path)
    evaluations, chosen = select([d["directory"] for d in pool["directories_in_order"]], pool["commit"], fetcher, seed, http)
    document = {"evaluated_at": datetime.now(UTC).isoformat(timespec="seconds"), "rules": "docs/EXTERNAL_VALIDATION.md",
                "articles_commit": pool["commit"], "selected": len(chosen), "evaluated": len(evaluations), "articles": evaluations}
    (out_dir / "evaluation.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    (out_dir / "papers.json").write_text(json.dumps(papers_json(chosen), indent=2) + "\n", encoding="utf-8")
    return evaluations, chosen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Choose ReScience C articles by the rules of docs/EXTERNAL_VALIDATION.md.")
    parser.add_argument("command", choices=["pool", "evaluate"])
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args(argv)
    fetcher = ReScienceFetcher(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    out_dir = Path(args.out_dir)
    if args.command == "pool":
        pool = command_pool(fetcher, out_dir)
        print(f"pool: {len(pool['directories_in_order'])} article directories at {pool['commit'][:12]}")
        return 0
    evaluations, chosen = command_evaluate(fetcher, out_dir, fetcher.http)
    print(f"evaluated {len(evaluations)} articles, selected {len(chosen)}")
    return 0 if chosen else 1


if __name__ == "__main__":
    sys.exit(main())
