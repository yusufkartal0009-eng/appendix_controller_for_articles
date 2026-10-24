#!/usr/bin/env python3
"""Choose the demo set by the rules of docs/DEMO_SET.md (#421): light papers that run fast on their own data.

    python scripts/demo_set.py pool   # run the eight searches once; write data/demo_set/pool.json
    python scripts/demo_set.py run    # S1 to S6 in the hash order, then the run test K1 in the sandbox for each candidate that passes
    python scripts/demo_set.py report [--pdf-dir DIR]   # the results section of docs/DEMO_SET.md, from the stored files

This is a hand-picked demo set, not a sample: nothing it prints is a success rate. Set GH_TOKEN (or GITHUB_TOKEN) to avoid
GitHub's API limits. Downloaded code is only ever executed inside the Docker sandbox.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts import corpus_expansion as ce
from src.config import SEED_PAPERS_PATH
from src.sandbox.stager import remove_tree

OUT_DIR = project_root / "data" / "demo_set"
CORPUS_EXPANSION_PATH = project_root / "data" / "corpus_expansion" / "papers.json"
TOPICS = ["scikit-learn", "tabular-data", "time-series", "classification", "clustering", "anomaly-detection",
          "gradient-boosting", "reproducibility"]
COMMON = "arxiv.org in:readme language:Python archived:false fork:false size:<20000"
QUERIES = [f"topic:{topic} {COMMON}" for topic in TOPICS]
RULES = ("S1", "S2", "S3", "S4", "S5", "S6")
RULE_OF = {"R1": "S1", "R2": "S1", "R3": "S2", "R4": "S3", "R5": "S4", "R6": "S5", "R7": "S6"}
MAX_PASSED = 5
MAX_RUNS = 30
MAX_SECONDS = 9000  # 2.5 hours, counted from the start of the run test
RUN_TIMEOUT_SECONDS = 600
MEMORY = "50%"
CPUS = 4.0
INSTALL_OK = ("INSTALLED", "SKIPPED")
# K1, condition 3: a name, a colon or an equals sign, and a number with a decimal point
METRIC_LINE = re.compile(r"[A-Za-z][A-Za-z0-9_@/ ()\-]*\s*[:=]\s*-?\d+\.\d+")
LOG_NAMES = ("stdout.log", "stderr.log")

Runner = Callable[[dict[str, Any], Path, Path], dict[str, Any]]


def queries() -> list[str]:
    return list(QUERIES)


def metric_lines(text: str) -> list[str]:
    """The lines of a log that count as a numeric metric line for K1."""
    return [line.strip() for line in text.splitlines() if METRIC_LINE.search(line)]


def last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""


def sanitize(text: str) -> str:
    """Replace the local paths of this machine (the repository and the home directory), in both slash styles."""
    for path, label in ((project_root, "<REPO>"), (Path.home(), "<HOME>")):
        for form in {str(path), path.as_posix(), str(path).replace("\\", "\\\\")}:
            text = text.replace(form, label)
    return text


def sanitize_tree(folder: Path) -> None:
    for path in folder.rglob("*"):
        if path.is_file():
            original = path.read_text(encoding="utf-8", errors="replace")
            cleaned = sanitize(original)
            if cleaned != original:
                path.write_text(cleaned, encoding="utf-8")


def classify_run(record: dict[str, Any], record_dir: Path) -> dict[str, Any]:
    """K1 for one finished run: the verdict, the category of a failure, and the deciding log line."""

    def read(name: str) -> str:
        path = record_dir / name
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""

    run = record.get("run") or {}
    result: dict[str, Any] = {"k1_passed": False, "category": None, "log_line": "",
                              "install_status": run.get("dependency_install_status"), "run_status": run.get("status"),
                              "exit_code": run.get("exit_code"), "duration_seconds": run.get("duration_seconds"),
                              "metric_lines": []}
    stage = record.get("stage") or {}
    if stage.get("status") != "STAGED":
        return {**result, "category": "staging", "log_line": str(stage.get("error", ""))[:300]}
    if not run:
        return {**result, "category": "harness", "log_line": "the record has no run phase"}
    if not (run.get("docker_used") and run.get("isolated")):
        return {**result, "category": "harness", "log_line": "not a valid run: docker_used and isolated are not both true"}
    if run.get("dependency_install_status") not in INSTALL_OK:
        return {**result, "category": "install", "log_line": last_line(read("install.log"))}
    if run.get("status") == "TIMEOUT":
        return {**result, "category": "timeout", "log_line": last_line(read("stderr.log") or read("stdout.log"))}
    if run.get("status") == "OOM_KILLED":
        return {**result, "category": "memory", "log_line": last_line(read("stderr.log") or read("stdout.log"))}
    if run.get("status") != "COMPLETED" or run.get("exit_code") != 0:
        return {**result, "category": "run", "log_line": last_line(read("stderr.log") or read("stdout.log"))}
    found = [line for name in LOG_NAMES for line in metric_lines(read(name))]
    if not found:
        return {**result, "category": "no_metric_line", "log_line": last_line(read("stdout.log"))}
    return {**result, "k1_passed": True, "metric_lines": found[:20]}


def sandbox_runner(entry: dict[str, Any], corpus_path: Path, record_root: Path, staging_dir: Path) -> dict[str, Any]:
    """Run one candidate once in the sandbox as `run_pilot.py --pilot4` does, with the limits of docs/DEMO_SET.md section 4."""
    from scripts import run_pilot

    paper_id = entry["paper_id"]
    try:
        record = run_pilot.run_paper(paper_id, staging_dir, pilot4=True, corpus_path=corpus_path, memory_limit=MEMORY,
                                     cpus=CPUS, run_timeout=RUN_TIMEOUT_SECONDS, record_root=record_root)
    except Exception as exc:  # noqa: BLE001 - a harness error is recorded as the candidate's result, never retried
        return {"k1_passed": False, "category": "harness", "log_line": f"{type(exc).__name__}: {exc}"[:300],
                "install_status": None, "run_status": None, "exit_code": None, "duration_seconds": None, "metric_lines": []}
    finally:
        for leftover in (staging_dir / paper_id, staging_dir / f"{paper_id}_packages"):
            if leftover.exists():
                remove_tree(leftover)
    return classify_run(record, record_root / paper_id)


def command_pool(fetcher: ce.Fetcher, out_dir: Path) -> dict[str, Any]:
    searches = []
    names: list[str] = []
    for query in QUERIES:
        found = fetcher.search(query)
        searches.append({"query": query, "results": found})
        names.extend(found)
    ordered = ce.order_candidates(names)
    pool = {"retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"), "per_query_limit": ce.POOL_PER_QUERY,
            "rules": "docs/DEMO_SET.md", "searches": searches,
            "candidates_in_order": [{"full_name": n, "hash": ce.candidate_hash(n)} for n in ordered]}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pool.json").write_text(json.dumps(pool, indent=2) + "\n", encoding="utf-8")
    return pool


def static_check(full_name: str, fetcher: ce.Fetcher, seed_repos: set[str], seed_papers: set[str], taken_repos: set[str],
                 taken_papers: set[str]) -> dict[str, Any]:
    """S1 to S6 in order, by the rules of scripts/corpus_expansion.py (R1 to R7) under the names of docs/DEMO_SET.md."""
    result = ce.evaluate_candidate(full_name, fetcher, seed_repos, taken_repos, seed_papers, taken_papers,
                                   stated_size_rule=False)
    if result["failed_rule"]:
        result["failed_rule"] = RULE_OF[result["failed_rule"]]
    return result


def papers_entry(result: dict[str, Any], paper_id: str) -> dict[str, Any]:
    entry = ce.papers_json([result])[0]
    entry["paper_id"] = paper_id
    return entry


def select_and_run(candidates: list[str], fetcher: ce.Fetcher, seed_repos: set[str], seed_papers: set[str], out_dir: Path,
                   runner: Runner, clock: Callable[[], float] = time.monotonic, max_passed: int = MAX_PASSED,
                   max_runs: int = MAX_RUNS, max_seconds: float = MAX_SECONDS) -> dict[str, Any]:
    """Walk the candidates in order: S1 to S6, then K1 for each one that passes. Stops by docs/DEMO_SET.md section 5.
    evaluation.json and papers.json are rewritten after every candidate, so that a crash loses nothing."""
    started = clock()
    evaluations: list[dict[str, Any]] = []
    papers: list[dict[str, Any]] = []
    passed = 0
    stop = "candidates_used_up"
    taken_repos: set[str] = set()
    taken_papers: set[str] = set()

    def write() -> None:
        document = {"written_at": datetime.now(UTC).isoformat(timespec="seconds"), "rules": "docs/DEMO_SET.md",
                    "note": "hand-picked demo set; not a sample and not a success rate", "evaluated": len(evaluations),
                    "runs": len(papers), "k1_passed": passed, "stopped_because": stop, "candidates": evaluations}
        (out_dir / "evaluation.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        (out_dir / "papers.json").write_text(json.dumps(papers, indent=2) + "\n", encoding="utf-8")

    for full_name in candidates:
        if passed >= max_passed:
            stop = "five_passed"
            break
        if len(papers) >= max_runs:
            stop = "thirty_runs"
            break
        if clock() - started >= max_seconds:
            stop = "time_limit"
            break
        result = static_check(full_name, fetcher, seed_repos, seed_papers, taken_repos, taken_papers)
        evaluations.append(result)
        if result["passed"]:
            paper_id = f"demo_{len(papers) + 1:03d}"
            entry = papers_entry(result, paper_id)
            papers.append(entry)
            taken_repos.add(full_name.lower())
            taken_papers.add(ce.find_arxiv_id(entry["paper_url"]) or "")
            write()  # the corpus file has to hold the entry before the run reads it
            result["paper_id"] = paper_id
            started_run = datetime.now(UTC).isoformat(timespec="seconds")
            result["k1"] = {"started_at": started_run, **runner(entry, out_dir / "papers.json", out_dir / "runs")}
            if result["k1"]["k1_passed"]:
                passed += 1
        write()
    if stop == "candidates_used_up" and passed >= max_passed:
        stop = "five_passed"
    write()
    return {"evaluated": len(evaluations), "runs": len(papers), "k1_passed": passed, "stopped_because": stop}


def number_forms(raw: str) -> list[tuple[str, str]]:
    """The strings under which a printed decimal number may appear in a paper: as printed, without a leading zero, and moved
    two places to the right (a fraction printed as a percentage)."""
    forms = [(raw, "as printed")]
    if raw.startswith("0."):
        forms.append((raw[1:], "without the leading zero"))
    whole, _, fraction = raw.partition(".")
    if whole in ("0", "-0") and len(fraction) > 2:
        forms.append((f"{'-' if whole.startswith('-') else ''}{int(fraction[:2])}.{fraction[2:]}", "as a percentage"))
    return forms


def table_captions_on(text: str) -> list[str]:
    return sorted({m.group(0) for m in re.finditer(r"^Table \d+", text, re.MULTILINE)}, key=lambda c: int(c.split()[1]))


def pages_with_number(form: str, pdf: Any) -> list[int]:
    """The PDF pages (1-based) that print `form` as a whole number: not inside a longer number (`1.5` is not in `21.55`,
    `1.52` or the version `1.5.2`), but next to punctuation, a sign, or a bracket."""
    pattern = re.compile(r"(?<![\d.])" + re.escape(form) + r"(?!\d|\.\d)")
    return [number for number, text in enumerate(pdf.pages, start=1) if pattern.search(text)]


def locate_numbers(lines: list[str], pdf: Any) -> list[dict[str, Any]]:
    """For each decimal number of the metric lines: the PDF pages of the paper that hold the same string, and the table
    captions on those pages. A string match only; that the number means the same thing is not checked."""
    found = []
    for line in lines:
        for raw in dict.fromkeys(re.findall(r"-?\d+\.\d+", line)):
            hit: dict[str, Any] = {"line": line, "number": raw, "pages": [], "form": None, "captions": []}
            for form, label in number_forms(raw):
                pages = pages_with_number(form, pdf)
                if pages:
                    hit.update(pages=pages, form=f"{form} ({label})",
                               captions=sorted({c for n in pages for c in table_captions_on(pdf.page(n))}))
                    break
            found.append(hit)
    return found


def download_pdf(arxiv_id: str, folder: Path) -> Path:
    path = folder / f"{arxiv_id}.pdf"
    if not path.is_file():
        request = urllib.request.Request(f"https://arxiv.org/pdf/{arxiv_id}", headers={"User-Agent": "repro-radar-demo-set"})
        with urllib.request.urlopen(request, timeout=120) as response:
            path.write_bytes(response.read())
    return path


def output_numbers(stdout: str, minimum_decimals: int = 3) -> list[str]:
    """The distinct decimal numbers with at least `minimum_decimals` decimals printed anywhere in an output, in order."""
    pattern = rf"(?<![\d.])-?\d+\.\d{{{minimum_decimals},}}"
    return list(dict.fromkeys(re.findall(pattern, stdout)))


def render_results(document: dict[str, Any], papers: list[dict[str, Any]], locations: dict[str, list[dict[str, Any]]],
                   output_hits: dict[str, list[dict[str, Any]]] | None = None) -> str:
    """The results section of docs/DEMO_SET.md, from the stored files only (no hand-typed number)."""
    candidates = document["candidates"]
    ran = [c for c in candidates if c.get("k1")]
    passed = [c for c in ran if c["k1"]["k1_passed"]]
    entry = {p["paper_id"]: p for p in papers}
    out = [(f"Generated by `scripts/demo_set.py report` from `data/demo_set/evaluation.json` (written {document['written_at']}) and "
            "`data/demo_set/runs/`; do not edit by hand. The run stopped because: "
            f"`{document['stopped_because']}`."), "",
           ("**Only the papers that passed K1 are shown in section 7.3. This is a hand-picked demo set: it is not representative of "
            "the pool it came from, and no number below is a success rate.**"), "",
           "### 7.1 What was tried", "",
           f"- Candidates checked against S1 to S6: {document['evaluated']} (the pool holds {document.get('pool_size', 'an unknown number of')}).",
           f"- Candidates that passed S1 to S6 and were run once: {len(ran)}.",
           f"- Candidates that passed K1: {len(passed)}.", ""]
    rules: dict[str, int] = {}
    for c in candidates:
        if c.get("failed_rule"):
            rules[c["failed_rule"]] = rules.get(c["failed_rule"], 0) + 1
    out += ["First failed static rule of the checked candidates:", "", "| Rule | Candidates |", "|---|---|"]
    out += [f"| {r} | {rules[r]} |" for r in RULES if r in rules] + [""]
    reasons: dict[str, int] = {}
    for c in ran:
        key = "passed" if c["k1"]["k1_passed"] else c["k1"]["category"]
        reasons[key] = reasons.get(key, 0) + 1
    out += ["Outcome of the run test K1:", "", "| Outcome | Candidates |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in sorted(reasons.items())] + [""]
    out += ["### 7.2 Every run", "", "| Id | Repository | Command | Install | Run | Exit | Seconds | Outcome | Deciding log line |",
            "|---|---|---|---|---|---|---|---|---|"]
    for c in ran:
        k = c["k1"]
        e = entry[c["paper_id"]]
        line = (k["log_line"] or "").replace("|", "\\|")
        out.append(f"| {c['paper_id']} | `{c['full_name']}` | `{e['run_command']}` | {k['install_status']} | {k['run_status']} | "
                   f"{k['exit_code']} | {k['duration_seconds']} | {'passed' if k['k1_passed'] else k['category']} | `{line}` |")
    out += ["", "### 7.3 Papers that passed K1", ""]
    if not passed:
        out += ["No candidate passed K1.", ""]
    for c in passed:
        e = entry[c["paper_id"]]
        k = c["k1"]
        out += [f"#### {c['paper_id']}: {e['title']}", "",
                f"- Paper: {e['paper_url']}", f"- Repository: {e['repo_url']} at commit `{e['repo_commit']}` ({e['license']})",
                f"- Command: `{e['run_command']}`",
                f"- Duration of the run phase: {k['duration_seconds']} s; install: {k['install_status']}",
                "- Metric lines of the output (first 10):", ""]
        out += [f"  - `{line}`" for line in k["metric_lines"][:10]] + [""]
        out += [("Where the printed numbers occur in the paper's text (exact string match on the PDF pages, `pypdf`; that the "
                 "number means the same thing is **not verified**):"), "",
                "| Printed line | Number | Found as | PDF pages | Table captions on those pages |", "|---|---|---|---|---|"]
        for h in locations.get(c["paper_id"], [])[:20]:
            pages = ", ".join(map(str, h["pages"][:8])) or "not found"
            out.append(f"| `{h['line'][:80]}` | {h['number']} | {h['form'] or '-'} | {pages} | {', '.join(h['captions']) or '-'} |")
        out.append("")
        hits = (output_hits or {}).get(c["paper_id"])
        if hits is not None:
            found = [h for h in hits if h["pages"]]
            out += [(f"Decimal numbers with at least 3 decimals printed anywhere in `stdout.log`: {len(hits)}; found in the paper's "
                     f"text by the same string match: {len(found)}."), ""]
            if found:
                out += ["| Number | Found as | PDF pages | Table captions on those pages |", "|---|---|---|---|"]
                for h in found[:30]:
                    out.append(f"| {h['number']} | {h['form']} | {', '.join(map(str, h['pages'][:8]))} | {', '.join(h['captions']) or '-'} |")
                out.append("")
    return "\n".join(out) + "\n"


def command_report(out_dir: Path, pdf_dir: Path | None) -> str:
    from src.pdf_text import extract_pdf_text

    document = json.loads((out_dir / "evaluation.json").read_text(encoding="utf-8"))
    papers = json.loads((out_dir / "papers.json").read_text(encoding="utf-8"))
    document["pool_size"] = len(json.loads((out_dir / "pool.json").read_text(encoding="utf-8"))["candidates_in_order"])
    entry = {p["paper_id"]: p for p in papers}
    locations: dict[str, list[dict[str, Any]]] = {}
    output_hits: dict[str, list[dict[str, Any]]] = {}
    with tempfile.TemporaryDirectory() as scratch:
        folder = pdf_dir or Path(scratch)
        folder.mkdir(parents=True, exist_ok=True)
        for c in document["candidates"]:
            if c.get("k1", {}).get("k1_passed"):
                arxiv_id = ce.find_arxiv_id(entry[c["paper_id"]]["paper_url"]) or ""
                pdf = extract_pdf_text(download_pdf(arxiv_id, folder), cache_dir=None)
                locations[c["paper_id"]] = locate_numbers(c["k1"]["metric_lines"], pdf)
                stdout = out_dir / "runs" / c["paper_id"] / "stdout.log"
                text = stdout.read_text(encoding="utf-8", errors="replace") if stdout.is_file() else ""
                output_hits[c["paper_id"]] = locate_numbers([f"= {n}" for n in output_numbers(text)], pdf)
    return render_results(document, papers, locations, output_hits)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Choose the demo set by the rules of docs/DEMO_SET.md.")
    parser.add_argument("command", choices=["pool", "run", "report"])
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    parser.add_argument("--staging-dir", default=".sandbox_staging")
    parser.add_argument("--pdf-dir", default=None, help="report: where the PDFs of the papers are kept (outside the repository)")
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    out_dir = Path(args.out_dir)
    if args.command == "report":
        print(sanitize(command_report(out_dir, Path(args.pdf_dir) if args.pdf_dir else None)), end="")
        return 0
    fetcher = ce.NetFetcher(token)
    if args.command == "pool":
        pool = command_pool(fetcher, out_dir)
        print(f"pool: {len(pool['candidates_in_order'])} candidates from {len(pool['searches'])} searches")
        return 0
    from scripts import preflight

    preflight.ensure_ready()
    candidates = [c["full_name"] for c in json.loads((out_dir / "pool.json").read_text(encoding="utf-8"))["candidates_in_order"]]
    staging = Path(args.staging_dir)

    def runner(entry: dict[str, Any], corpus: Path, record_root: Path) -> dict[str, Any]:
        return sandbox_runner(entry, corpus, record_root, staging)

    summary = select_and_run(candidates, fetcher, ce.seed_repo_names(SEED_PAPERS_PATH) | ce.seed_repo_names(CORPUS_EXPANSION_PATH),
                             ce.seed_arxiv_ids(SEED_PAPERS_PATH) | ce.seed_arxiv_ids(CORPUS_EXPANSION_PATH), out_dir, runner)
    if (out_dir / "runs").is_dir():
        sanitize_tree(out_dir / "runs")
    for name in ("evaluation.json", "papers.json"):
        path = out_dir / name
        path.write_text(sanitize(path.read_text(encoding="utf-8")), encoding="utf-8")
    print(json.dumps(summary))
    shutil.rmtree(staging, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
