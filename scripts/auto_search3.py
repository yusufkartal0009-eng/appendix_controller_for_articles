#!/usr/bin/env python3
"""Automatic search, round 3 (#469, #471): run many candidates once and check the run's numbers against the paper's text.

    python scripts/auto_search3.py pool [--stage 2]   # run the searches of one stage once; write data/auto_search3/pool.json
    python scripts/auto_search3.py run                # S1 to S6, K1 in the sandbox, K2 against the paper; resumable
    python scripts/auto_search3.py report             # the results section of docs/AUTO_SEARCH_ROUND3.md, from the stored files

The rules are in docs/AUTO_SEARCH_ROUND3.md. The static rules (S1 to S6) and the run test (K1) are those of scripts/demo_set.py.
K2 is new: numbers printed by the run are looked up in the text of the paper. A K2 pass is a "match candidate", never a
verified result, and the list is selected and not a success rate. Set GITHUB_TOKEN (or GH_TOKEN) to avoid GitHub's API limits.
Downloaded code is only ever executed inside the Docker sandbox.

`run` can be started again at any time: candidates that have a stored result are skipped. A candidate that was staged but has
no stored result (the process stopped while it was running) is run again from the start.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts import candidates_build, demo_set
from scripts import corpus_expansion as ce
from src.config import SANDBOX_RUNS_DIR, SEED_PAPERS_PATH
from src.pdf_text import extract_pdf_text, repair_split_numbers
from src.sandbox.stager import remove_tree

OUT_DIR = project_root / "data" / "auto_search3"
PDF_DIR = project_root / "data" / "pdfs" / "auto_search3"
COMMON = "arxiv.org in:readme language:Python archived:false fork:false size:<30000"
STAGE_TOPICS: dict[int, list[str]] = {
    1: ["statistics", "bayesian", "optimization", "causal-inference", "survival-analysis", "regression", "simulation",
        "signal-processing", "computational-biology", "physics", "graph-algorithms", "recommender-system",
        "symbolic-regression", "feature-selection", "dimensionality-reduction", "probabilistic-programming"],
    2: ["numerical-methods", "monte-carlo", "differential-equations", "econometrics", "bioinformatics", "chemistry",
        "neuroscience", "ecology", "epidemiology", "game-theory", "information-theory", "kernel-methods",
        "ensemble-learning", "time-series-forecasting", "topic-modeling", "nlp"],
}
ID_PREFIX = "a3_"
MAX_SECONDS = 9 * 3600
MAX_RUNS = 150
MAX_BOTH = 8
MIN_FREE_BYTES = 30 * 1024**3
INSTALL_TIMEOUT_SECONDS = 1200
ARXIV_PAUSE_SECONDS = 3.0
SEARCH_PAUSE_SECONDS = 2.5
MAX_NUMBERS = 5000  # distinct numbers of one output that are looked up; a longer output is cut and the record says so
MIN_SIGNIFICANT_DIGITS = 3
MIN_MATCHED_NUMBERS = 2
KEPT_LOG_BYTES = 40_000
KEPT_TAIL_BYTES = 10_000
MAX_PAGES_STORED = 10
EARLIER_ROUND_DIRS = ("data/candidates",)

Runner = Callable[[dict[str, Any], Path, Path], dict[str, Any]]
K2Runner = Callable[[dict[str, Any], Path], dict[str, Any]]


# ---------------------------------------------------------------- the pool


def queries(stage: int) -> list[str]:
    return [f"{COMMON} topic:{topic}" for topic in STAGE_TOPICS[stage]]


def earlier_round_repos(root: Path = project_root) -> set[str]:
    """Lower-case `owner/name` of every repository of the earlier rounds: the whole pool of the demo set, everything under
    data/candidates, the seed corpus and the corpus expansion."""
    names = ce.seed_repo_names(root / "data" / "seed_papers.json") | ce.seed_repo_names(root / "data" / "corpus_expansion" / "papers.json")
    pool = root / "data" / "demo_set" / "pool.json"
    if pool.is_file():
        names |= {c["full_name"].lower() for c in json.loads(pool.read_text(encoding="utf-8"))["candidates_in_order"]}
    pattern = re.compile(r"github\.com/([\w.-]+/[\w.-]+)|\"full_name\":\s*\"([\w.-]+/[\w.-]+)\"")
    for folder in EARLIER_ROUND_DIRS:
        for path in sorted((root / folder).rglob("*.json")):
            for match in pattern.finditer(path.read_text(encoding="utf-8", errors="replace")):
                name = (match.group(1) or match.group(2)).lower()
                names.add(name.removesuffix(".git"))
    return names


def command_pool(fetcher: ce.Fetcher, out_dir: Path, stage: int, excluded: set[str],
                 pause: float = SEARCH_PAUSE_SECONDS, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Run the searches of one stage once and store them unchanged, with the date. The candidates of an earlier round are
    removed before the SHA-256 order; the candidates of this stage come after those of the earlier stages."""
    path = out_dir / "pool.json"
    pool: dict[str, Any] = (json.loads(path.read_text(encoding="utf-8")) if path.is_file()
                            else {"rules": "docs/AUTO_SEARCH_ROUND3.md", "stages": {}, "candidates_in_order": []})
    if str(stage) in pool["stages"]:
        raise ValueError(f"stage {stage} is already stored in {path}; the searches are run once")
    searches, names = [], []
    for query in queries(stage):
        found = fetcher.search(query)
        searches.append({"query": query, "results": found})
        names.extend(found)
        sleep(pause)
    known = {c["full_name"].lower() for c in pool["candidates_in_order"]}
    kept = [n for n in names if n.lower() not in excluded and n.lower() not in known]
    removed = sorted({n.lower() for n in names if n.lower() in excluded})
    ordered = ce.order_candidates(kept)
    pool["stages"][str(stage)] = {"retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
                                  "per_query_limit": ce.POOL_PER_QUERY, "searches": searches,
                                  "removed_as_earlier_round": removed}
    pool["candidates_in_order"] += [{"full_name": n, "hash": ce.candidate_hash(n), "stage": stage} for n in ordered]
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pool, indent=2) + "\n", encoding="utf-8")
    return pool


# ---------------------------------------------------------------- K2: numbers of the output

_MASKS = [re.compile(p, re.IGNORECASE) for p in (
    r"\b\d{4}-\d{2}-\d{2}\b",                                   # a date
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",                              # a date
    r"\b\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?",                     # a time
    r"\b(?:v\d+|version\s*\d+)(?:\.\d+)*",                          # a version
    r"\b\d+(?:\.\d+){2,}\b",                                     # a version or an address
    r"\[\d+\]",                                                  # an index
    r"#\d+",                                                     # an index
    r"\b(?:line|lines|epoch|epochs|step|steps|iter|iteration|iterations|batch|fold|seed|row|col|column)\b\s*[:=]?\s*\d+(?:/\d+)?",
    r":\d+:",                                                    # a line number of a traceback or a file reference
    r"\b0x[0-9a-f]+\b",                                          # an address
)]
_NUMBER = re.compile(r"(?<![\w.])[-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?%?(?!\w|\.\d)")
THOUSANDS = "[,'’   ]"
MINUS = "[-−–‑]"


def significant_digits(canonical: str) -> int:
    """Digits of a number that count: no sign, no separator, no leading zero; the zeros at the end of an integer do not count."""
    mantissa = re.split(r"[eE]", canonical.lstrip("-"))[0]
    digits = mantissa.replace(".", "")
    if "." not in mantissa:
        digits = digits.rstrip("0")
    return len(digits.lstrip("0"))


def is_year(canonical: str) -> bool:
    return re.fullmatch(r"\d{4}", canonical) is not None and 1900 <= int(canonical) <= 2100


def meaningful_numbers(text: str, limit: int = MAX_NUMBERS) -> list[dict[str, Any]]:
    """The distinct meaningful numbers of an output, in order, each with its line (docs/AUTO_SEARCH_ROUND3.md section 5): at
    least 3 significant digits; not a year, a version, a date or a time, an index or a line number. (A single digit has
    fewer than 3 significant digits, so the rule for single digits needs no code of its own.) The number is kept as printed,
    without sign variants, thousands separators and the percent sign."""
    found: dict[str, dict[str, Any]] = {}
    for raw_line in text.splitlines():
        line = raw_line
        for mask in _MASKS:
            line = mask.sub(lambda m: " " * len(m.group(0)), line)
        for match in _NUMBER.finditer(line):
            token = match.group(0)
            percent = token.endswith("%")
            canonical = token.rstrip("%").replace("−", "-").replace(",", "")
            if significant_digits(canonical) < MIN_SIGNIFICANT_DIGITS or is_year(canonical) or canonical in found:
                continue
            found[canonical] = {"number": canonical, "line": raw_line.strip()[:200], "percent": percent}
            if len(found) >= limit:
                return list(found.values())
    return list(found.values())


def paper_pattern(canonical: str) -> re.Pattern[str]:
    """A pattern that finds `canonical` in the text of a paper in the same spelling: the same digits and decimals. A decimal
    comma reads as a decimal point, a thousands separator may stand between groups of three digits, a leading zero may be
    dropped (`.5`), any minus variant counts as a minus, and the number must not be part of a longer number."""
    negative = canonical.startswith("-")
    body = canonical.lstrip("-")
    if re.search(r"[eE]", body):
        core = re.escape(body)
    else:
        whole, dot, fraction = body.partition(".")
        if whole == "0" and dot:
            whole_re = "0?"
        elif len(whole) > 3:
            head = len(whole) % 3 or 3
            groups = [whole[:head]] + [whole[i:i + 3] for i in range(head, len(whole), 3)]
            whole_re = (THOUSANDS + "?").join(groups)
        else:
            whole_re = whole
        core = whole_re + (rf"[.,]{fraction}" if dot else "")
    tail = r"(?!\d|\.\d)"
    if negative:
        return re.compile(r"(?<![\d.])" + MINUS + core + tail)
    thousands_guard = r"(?<!\d,)" if len(canonical.partition(".")[0]) == 3 else ""
    return re.compile(r"(?<![\d.])" + thousands_guard + r"(?<![-−])" + core + tail)


def line_around(text: str, position: int) -> str:
    start = text.rfind("\n", 0, position) + 1
    end = text.find("\n", position)
    return text[start:end if end != -1 else len(text)].strip()[:200]


def table_page(text: str) -> bool:
    return bool(demo_set.table_captions_on(text))


def match_numbers(numbers: list[dict[str, Any]], pages: list[str]) -> list[dict[str, Any]]:
    """The numbers of the output that occur in the paper's text, each with the pages (1-based) and the line of the paper."""
    pages = [repair_split_numbers(p) for p in pages]
    on_table = [table_page(p) for p in pages]
    hits = []
    for item in numbers:
        pattern = paper_pattern(item["number"])
        found = []
        for index, text in enumerate(pages):
            match = pattern.search(text)
            if match:
                found.append({"page": index + 1, "table_page": on_table[index], "line": line_around(text, match.start())})
        if found:
            hits.append({**item, "pages": found[:MAX_PAGES_STORED], "pages_total": len(found),
                         "on_table_page": any(f["table_page"] for f in found)})
    return hits


def evaluate_k2(output: str, pages: list[str]) -> dict[str, Any]:
    """K2: at least 2 different meaningful numbers of the output occur in the paper's text and at least one of them on a
    page with a `Table <n>` line. A pass is a match candidate; it is not a verified result."""
    numbers = meaningful_numbers(output)
    hits = match_numbers(numbers, pages)
    return {"passed": len(hits) >= MIN_MATCHED_NUMBERS and any(h["on_table_page"] for h in hits),
            "numbers_in_output": len(numbers), "numbers_found_in_paper": len(hits),
            "numbers_found_on_table_page": sum(1 for h in hits if h["on_table_page"]), "pdf_pages": len(pages),
            "matches": hits, "note": "match candidate only; a string match, not verified"}


class Throttle:
    """At most one request to arXiv per `pause` seconds."""

    def __init__(self, pause: float = ARXIV_PAUSE_SECONDS, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.pause, self.clock, self.sleep = pause, clock, sleep
        self.last: float | None = None
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            if self.last is not None and (gap := self.pause - (self.clock() - self.last)) > 0:
                self.sleep(gap)
            self.last = self.clock()


def pdf_path(arxiv_id: str, folder: Path = PDF_DIR) -> Path:
    return folder / f"{arxiv_id.replace('/', '_')}.pdf"


def fetch_pdf(arxiv_id: str, throttle: Throttle, folder: Path = PDF_DIR) -> Path:
    path = pdf_path(arxiv_id, folder)
    if path.is_file() and path.stat().st_size > 0:
        return path
    folder.mkdir(parents=True, exist_ok=True)
    throttle.wait()
    request = urllib.request.Request(f"https://arxiv.org/pdf/{arxiv_id}", headers={"User-Agent": ce.USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        path.write_bytes(response.read())
    return path


class ThrottledFetcher(ce.NetFetcher):
    """The real fetcher, with arXiv requests at most once in 3 seconds and the paper's PDF kept under data/pdfs for K2."""

    def __init__(self, token: str | None, throttle: Throttle | None = None, pdf_folder: Path = PDF_DIR) -> None:
        super().__init__(token)
        self.throttle = throttle or Throttle()
        self.pdf_folder = pdf_folder

    def arxiv(self, arxiv_id: str) -> dict[str, Any] | None:
        self.throttle.wait()
        status, page = self.http.get(f"https://arxiv.org/abs/{arxiv_id}")
        if status != 200:
            return None
        title = ce._extract_page_title(page)
        date = re.search(r'<meta name="citation_date" content="(\d{4})', page)
        year = int(date.group(1)) if date else None
        try:
            path = fetch_pdf(arxiv_id, self.throttle, self.pdf_folder)
            text = "\n".join(extract_pdf_text(path, cache_dir=None).pages)
        except Exception:  # noqa: BLE001 - an unreadable or missing PDF fails S5 with an empty text
            text = ""
        return {"title": title, "year": year, "text": text}


def k2_for_run(entry: dict[str, Any], record_dir: Path, throttle: Throttle | None = None, pdf_folder: Path = PDF_DIR) -> dict[str, Any]:
    """K2 for one finished run: the paper's PDF (kept from S5, or downloaded) and the run's stdout.log."""
    arxiv_id = ce.find_arxiv_id(entry["paper_url"]) or ""
    try:
        path = fetch_pdf(arxiv_id, throttle or Throttle(), pdf_folder)
        pages = extract_pdf_text(path, cache_dir=None).pages
    except Exception as exc:  # noqa: BLE001 - the paper could not be read: K2 is not passed and the record says why
        return {"passed": False, "error": f"{type(exc).__name__}: {exc}"[:300], "matches": []}
    stdout = record_dir / "stdout.log"
    output = stdout.read_text(encoding="utf-8", errors="replace") if stdout.is_file() else ""
    return {**evaluate_k2(output, pages), "arxiv_id": arxiv_id}


# ---------------------------------------------------------------- the runs


def cleanup_run(paper_id: str, staging_dir: Path) -> None:
    """Delete the staging, wheel and sandbox output folders that this candidate's run created (and nothing else)."""
    for folder in (staging_dir / paper_id, staging_dir / f"{paper_id}_packages", SANDBOX_RUNS_DIR / paper_id,
                   SANDBOX_RUNS_DIR / f"{paper_id}.build"):
        if folder.exists():
            remove_tree(folder)


def sandbox_runner(entry: dict[str, Any], corpus_path: Path, record_root: Path, staging_dir: Path) -> dict[str, Any]:
    """K1 for one candidate: once, with the limits of docs/AUTO_SEARCH_ROUND3.md section 4."""
    from scripts import candidate_round2

    try:
        with candidate_round2.install_limit(INSTALL_TIMEOUT_SECONDS):
            return demo_set.sandbox_runner(entry, corpus_path, record_root, staging_dir)
    finally:
        cleanup_run(entry["paper_id"], staging_dir)


def shorten_logs(folder: Path) -> None:
    """Keep the head and the tail of a log that is longer than KEPT_LOG_BYTES."""
    for path in folder.glob("*.log"):
        data = path.read_bytes()
        if len(data) > KEPT_LOG_BYTES:
            cut = len(data) - KEPT_LOG_BYTES - KEPT_TAIL_BYTES
            marker = f"\n[... {cut} bytes cut ...]\n".encode()
            path.write_bytes(data[:KEPT_LOG_BYTES] + marker + data[-KEPT_TAIL_BYTES:])


def write_atomic(path: Path, text: str) -> None:
    """Write through a temporary file, so that a reader (the run reads papers.json) never sees a half-written file."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    for attempt in range(40):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:  # Windows: the target is open in a reader for a moment
            time.sleep(0.05 * (attempt + 1) ** 0.5)
    os.replace(temporary, path)


def free_bytes(path: Path = project_root) -> int:
    return shutil.disk_usage(path).free


class Search:
    """The walk over the pool. A producer thread applies S1 to S6 in the hash order and hands the candidates that pass to
    the consumer, which runs them one at a time (K1 and K2); so the sandbox is busy while the next candidates are checked.
    evaluation.json and papers.json are rewritten after every step, so that a crash loses nothing."""

    def __init__(self, names: list[str], fetcher: ce.Fetcher, seed_repos: set[str], seed_papers: set[str], out_dir: Path,
                 runner: Runner, k2_runner: K2Runner, extend_pool: Callable[[], list[str]] | None = None,
                 now: Callable[[], float] = time.time, free: Callable[[], int] = free_bytes, max_seconds: float = MAX_SECONDS,
                 max_runs: int = MAX_RUNS, max_both: int = MAX_BOTH, min_free: int = MIN_FREE_BYTES,
                 started_at: float | None = None, prefetch: int = 2) -> None:
        self.names = list(names)
        self.fetcher, self.seed_repos, self.seed_papers = fetcher, seed_repos, seed_papers
        self.out_dir, self.runner, self.k2_runner, self.extend_pool = out_dir, runner, k2_runner, extend_pool
        self.now, self.free = now, free
        self.max_seconds, self.max_runs, self.max_both, self.min_free = max_seconds, max_runs, max_both, min_free
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.producer_done = threading.Event()
        self.queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=prefetch)
        self.producer_error: BaseException | None = None
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "evaluation.json"
        self.document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"candidates": []}
        papers_path = out_dir / "papers.json"
        self.papers: list[dict[str, Any]] = json.loads(papers_path.read_text(encoding="utf-8")) if papers_path.is_file() else []
        self.evaluations: list[dict[str, Any]] = self.document["candidates"]
        if "started_epoch" not in self.document:
            epoch = started_at if started_at is not None else now()
            self.document["started_epoch"] = epoch
            self.document["started_at"] = datetime.fromtimestamp(epoch, UTC).isoformat(timespec="seconds")
        self.stopped_because = ""
        self.taken_repos = {c["full_name"].lower() for c in self.evaluations if c.get("passed")}
        self.taken_papers = {ce.find_arxiv_id(p["paper_url"]) or "" for p in self.papers}

    # -- counts and stop

    def counts(self) -> dict[str, int]:
        ran = [c for c in self.evaluations if c.get("k1")]
        return {"evaluated": len(self.evaluations), "runs": len(ran),
                "k1_passed": sum(1 for c in ran if c["k1"]["k1_passed"]),
                "k2_passed": sum(1 for c in ran if (c.get("k2") or {}).get("passed")),
                "both_passed": sum(1 for c in ran if c["k1"]["k1_passed"] and (c.get("k2") or {}).get("passed"))}

    def stop_reason(self) -> str:
        counts = self.counts()
        if self.now() - self.document["started_epoch"] >= self.max_seconds:
            return "time_limit_9h"
        if counts["runs"] >= self.max_runs:
            return "run_limit_150"
        if counts["both_passed"] >= self.max_both:
            return "eight_passed_both"
        if self.free() < self.min_free:
            return "disk_below_30gb"
        return ""

    def write(self) -> None:
        with self.lock:
            document = {**self.document, "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
                        "rules": "docs/AUTO_SEARCH_ROUND3.md",
                        "note": "selected, non-representative list; not a success rate; K2 passers are match candidates, not verified",
                        **self.counts(), "stopped_because": self.stopped_because, "candidates": self.evaluations}
            write_atomic(self.out_dir / "evaluation.json", json.dumps(document, indent=2) + "\n")
            write_atomic(self.out_dir / "papers.json", json.dumps(self.papers, indent=2) + "\n")

    # -- the producer: S1 to S6

    def _put(self, item: dict[str, Any]) -> bool:
        while not self.stop.is_set():
            try:
                self.queue.put(item, timeout=0.2)
                return True
            except queue.Full:
                continue
        return False

    def _check(self, name: str) -> dict[str, Any]:
        try:
            result = demo_set.static_check(name, self.fetcher, self.seed_repos, self.seed_papers, self.taken_repos, self.taken_papers)
        except Exception as exc:  # noqa: BLE001 - a network or parse error of one candidate is recorded and the walk goes on
            result = {"full_name": name, "hash": ce.candidate_hash(name), "passed": False, "failed_rule": "static_error",
                      "detail": f"{type(exc).__name__}: {exc}"[:300]}
        return result

    def produce(self) -> None:
        try:
            for item in [c for c in self.evaluations if c.get("passed") and not c.get("k1")]:
                if not self._put(item):  # staged in an earlier session, never finished: run it now
                    return
            index = 0
            while not self.stop.is_set():
                if index >= len(self.names):
                    more = self.extend_pool() if self.extend_pool else []
                    if not more:
                        return
                    self.names += more
                    continue
                name = self.names[index]
                index += 1
                if name.lower() in {c["full_name"].lower() for c in self.evaluations}:
                    continue
                result = self._check(name)
                with self.lock:
                    self.evaluations.append(result)
                    if result["passed"]:
                        paper_id = f"{ID_PREFIX}{len(self.papers) + 1:03d}"
                        entry = demo_set.papers_entry(result, paper_id)
                        self.papers.append(entry)
                        self.taken_repos.add(name.lower())
                        self.taken_papers.add(ce.find_arxiv_id(entry["paper_url"]) or "")
                        result["paper_id"] = paper_id
                self.write()  # the corpus file has to hold the entry before the run reads it
                if result["passed"] and not self._put(result):
                    return
        except BaseException as exc:  # noqa: BLE001 - reported by `run`; the consumer stops
            self.producer_error = exc
        finally:
            self.producer_done.set()

    # -- the consumer: K1 and K2

    def run_one(self, item: dict[str, Any]) -> None:
        paper_id = item["paper_id"]
        entry = next(p for p in self.papers if p["paper_id"] == paper_id)
        runs_dir = self.out_dir / "runs"
        if (runs_dir / paper_id).exists():
            remove_tree(runs_dir / paper_id)  # a partial record of a run that never stored its result
        started = datetime.now(UTC).isoformat(timespec="seconds")
        k1 = self.runner(entry, self.out_dir / "papers.json", runs_dir)
        k2 = None
        if k1.get("run_status") == "COMPLETED" and k1.get("exit_code") == 0 and k1.get("category") != "harness":
            try:
                k2 = self.k2_runner(entry, runs_dir / paper_id)
            except Exception as exc:  # noqa: BLE001 - recorded, never fatal
                k2 = {"passed": False, "error": f"{type(exc).__name__}: {exc}"[:300], "matches": []}
        record_dir = runs_dir / paper_id
        if record_dir.is_dir():
            (record_dir / "k1_k2.json").write_text(json.dumps({"paper_id": paper_id, "k1": k1, "k2": k2}, indent=2) + "\n", encoding="utf-8")
            shorten_logs(record_dir)
            demo_set.sanitize_tree(record_dir)
        with self.lock:
            item["k1"] = {"started_at": started, **json.loads(demo_set.sanitize(json.dumps(k1)))}
            item["k2"] = json.loads(demo_set.sanitize(json.dumps(k2))) if k2 is not None else None
        self.write()

    def consume(self) -> str:
        reason = ""
        while not reason:
            reason = self.stop_reason()
            if reason:
                break
            try:
                item = self.queue.get(timeout=0.2)
            except queue.Empty:
                if self.producer_done.is_set() and self.queue.empty():
                    reason = "producer_failed" if self.producer_error else "pool_used_up"
                continue
            self.run_one(item)
        return reason

    def run(self) -> dict[str, Any]:
        producer = threading.Thread(target=self.produce, name="static-checks", daemon=True)
        producer.start()
        try:
            self.stopped_because = self.consume()
        finally:
            self.stop.set()
            producer.join(timeout=300)
            self.write()
        if self.producer_error is not None:
            print(f"static checks stopped with {type(self.producer_error).__name__}: {self.producer_error}", file=sys.stderr)
        return {**self.counts(), "stopped_because": self.stopped_because}


# ---------------------------------------------------------------- the report


def _interval(passed: int, total: int) -> str:
    if total <= 0:
        return "n/a"
    low, high = candidates_build.wilson_interval(passed, total)
    return f"{candidates_build._percent(low)} - {candidates_build._percent(high)}"


def render_results(document: dict[str, Any], papers: list[dict[str, Any]]) -> str:
    """The results section of docs/AUTO_SEARCH_ROUND3.md, from the stored files only (no hand-typed number)."""
    candidates = document["candidates"]
    ran = [c for c in candidates if c.get("k1")]
    entry = {p["paper_id"]: p for p in papers}
    k1 = [c for c in ran if c["k1"]["k1_passed"]]
    k2 = [c for c in ran if (c.get("k2") or {}).get("passed")]
    both = [c for c in k1 if (c.get("k2") or {}).get("passed")]
    total = len(ran)
    out = [(f"Generated by `scripts/auto_search3.py report` from `data/auto_search3/evaluation.json` (written "
            f"{document['written_at']}, search started {document['started_at']}) and `data/auto_search3/runs/`; do not edit by hand. "
            f"The search stopped because: `{document['stopped_because']}`."), "",
           ("**This is a selected, non-representative list. The shares below describe only the candidates that were run, under these "
            "rules and this pool. They are not a success rate and not the reproducibility of any field. A K2 pass is a match "
            "candidate (a string match), not a verified result.**"), "",
           "### Results 1: What was tried", "",
           f"- Candidates checked against S1 to S6: {len(candidates)}.",
           f"- Candidates that passed S1 to S6 and were run once in the sandbox (tried): {total}.",
           f"- Passed K1: {len(k1)} of {total} (Wilson 95%: {_interval(len(k1), total)}).",
           (f"- Passed K2: {len(k2)} of {total} (Wilson 95%: {_interval(len(k2), total)}); K2 was computed for "
            f"{sum(1 for c in ran if c.get('k2') is not None)} runs that completed with exit code 0."),
           f"- Passed both K1 and K2: {len(both)} of {total} (Wilson 95%: {_interval(len(both), total)}).", ""]
    rules: dict[str, int] = {}
    for c in candidates:
        if c.get("failed_rule"):
            rules[c["failed_rule"]] = rules.get(c["failed_rule"], 0) + 1
    out += ["First failed static rule of the checked candidates:", "", "| Rule | Candidates |", "|---|---|"]
    out += [f"| {r} | {rules[r]} |" for r in (*demo_set.RULES, "static_error") if r in rules] + [""]
    reasons: dict[str, int] = {}
    for c in ran:
        key = "passed K1" if c["k1"]["k1_passed"] else c["k1"]["category"]
        reasons[key] = reasons.get(key, 0) + 1
    out += ["Outcome of the run test K1 (failure reasons):", "", "| Outcome | Candidates |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in sorted(reasons.items())] + [""]
    out += ["### Results 2: Every run", "",
            "| Id | Repository | Command | Install | Run | Exit | Seconds | K1 | K2 | Deciding log line |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for c in ran:
        r = c["k1"]
        e = entry[c["paper_id"]]
        line = (r["log_line"] or "").replace("|", "\\|")
        k2_text = "-" if c.get("k2") is None else ("passed" if c["k2"]["passed"] else "no")
        out.append(f"| {c['paper_id']} | `{c['full_name']}` | `{e['run_command']}` | {r['install_status']} | {r['run_status']} | "
                   f"{r['exit_code']} | {r['duration_seconds']} | {'passed' if r['k1_passed'] else r['category']} | {k2_text} | `{line}` |")
    out += ["", "### Results 3: Match candidates (K2 passed)", ""]
    if not k2:
        out += ["No candidate passed K2.", ""]
    for c in k2:
        e = entry[c["paper_id"]]
        r, m = c["k1"], c["k2"]
        out += [f"#### {c['paper_id']}: {e['title']}", "",
                f"- Paper: {e['paper_url']}", f"- Repository: {e['repo_url']} at commit `{e['repo_commit']}` ({e['license']})",
                f"- Command: `{e['run_command']}`",
                f"- Run phase: {r['duration_seconds']} s; install: {r['install_status']}; K1: {'passed' if r['k1_passed'] else r['category']}",
                (f"- Numbers of the output found in the paper: {m['numbers_found_in_paper']} of {m['numbers_in_output']} "
                 f"({m['numbers_found_on_table_page']} on a page with a `Table <n>` line). A string match; not verified."), "",
                "| Number | Output line | PDF pages | On a table page |", "|---|---|---|---|"]
        for h in m["matches"][:30]:
            pages = ", ".join(str(p["page"]) for p in h["pages"])
            out.append(f"| {h['number']} | `{h['line'][:80].replace('|', chr(92) + '|')}` | {pages} | {'yes' if h['on_table_page'] else 'no'} |")
        out.append("")
    return "\n".join(out) + "\n"


def command_report(out_dir: Path) -> str:
    document = json.loads((out_dir / "evaluation.json").read_text(encoding="utf-8"))
    papers = json.loads((out_dir / "papers.json").read_text(encoding="utf-8"))
    return render_results(document, papers)


# ---------------------------------------------------------------- the command line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automatic search, round 3: docs/AUTO_SEARCH_ROUND3.md.")
    parser.add_argument("command", choices=["pool", "run", "report"])
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    parser.add_argument("--staging-dir", default=".sandbox_staging")
    parser.add_argument("--stage", type=int, choices=sorted(STAGE_TOPICS), default=1, help="pool: which stage to search")
    parser.add_argument("--started-at", default=None, help="run: start of the search as an ISO time with offset (first run only)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)
    if args.command == "report":
        print(demo_set.sanitize(command_report(out_dir)), end="")
        return 0
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    fetcher = ThrottledFetcher(token)
    excluded = earlier_round_repos()
    if args.command == "pool":
        pool = command_pool(fetcher, out_dir, args.stage, excluded)
        stage = pool["stages"][str(args.stage)]
        print(f"stage {args.stage}: {len(stage['searches'])} searches; {len(stage['removed_as_earlier_round'])} repositories "
              f"of earlier rounds removed; {len(pool['candidates_in_order'])} candidates in the pool")
        return 0
    from scripts import preflight

    preflight.ensure_ready()
    pool = json.loads((out_dir / "pool.json").read_text(encoding="utf-8"))
    staging = Path(args.staging_dir)
    stages_left = [s for s in sorted(STAGE_TOPICS) if str(s) not in pool["stages"]]

    def extend_pool() -> list[str]:
        if not stages_left:
            return []
        stored = command_pool(fetcher, out_dir, stages_left.pop(0), excluded)
        return [c["full_name"] for c in stored["candidates_in_order"]]

    def runner(entry: dict[str, Any], corpus: Path, record_root: Path) -> dict[str, Any]:
        return sandbox_runner(entry, corpus, record_root, staging)

    throttle = fetcher.throttle
    search = Search([c["full_name"] for c in pool["candidates_in_order"]], fetcher,
                    ce.seed_repo_names(SEED_PAPERS_PATH) | ce.seed_repo_names(demo_set.CORPUS_EXPANSION_PATH) | excluded,
                    ce.seed_arxiv_ids(SEED_PAPERS_PATH) | ce.seed_arxiv_ids(demo_set.CORPUS_EXPANSION_PATH), out_dir, runner,
                    lambda entry, record_dir: k2_for_run(entry, record_dir, throttle), extend_pool,
                    started_at=datetime.fromisoformat(args.started_at).timestamp() if args.started_at else None)
    summary = search.run()
    for name in ("evaluation.json", "papers.json"):
        path = out_dir / name
        path.write_text(demo_set.sanitize(path.read_text(encoding="utf-8")), encoding="utf-8")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
