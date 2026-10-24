#!/usr/bin/env python3
"""Run the candidates of data/candidates/run_plan.json once each in the sandbox, by docs/CANDIDATE_RUNS.md (#437).

    python scripts/candidate_runs.py run                 # every candidate of the plan that has no result yet
    python scripts/candidate_runs.py run --only cand_001 # one candidate (a candidate that has a result is never run again)

For each runnable candidate the corpus entry is built from data/candidates/papers.json and the plan, and the run is made as
`scripts/run_pilot.py --pilot4` makes it (the Docker sandbox, no network, the repository's own requirement files), with the limits
of the protocol. The result of the run is classified by `classify_run` of scripts/demo_set.py. The record of every run is
data/candidates/runs/<paper_id>/ (local paths replaced by <REPO> and <HOME>, long logs shortened) and the results are
data/candidates/runs/evaluation.json, written after every candidate. Downloaded code is only ever executed inside the sandbox.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts import demo_set
from src.sandbox.stager import remove_tree

CANDIDATES_DIR = project_root / "data" / "candidates"
PAPERS_PATH = CANDIDATES_DIR / "papers.json"
PLAN_PATH = CANDIDATES_DIR / "run_plan.json"
RUNS_DIR = CANDIDATES_DIR / "runs"
RUN_TIMEOUT_SECONDS = 1800
MEMORY = "50%"
CPUS = 4.0
LOG_LIMIT_BYTES = 60_000  # a log longer than this keeps its first and last halves
LOG_NAMES = ("stdout.log", "stderr.log", "install.log")
NOTE = "selected list of candidates, not a sample; the share that passed is not a success rate"

Runner = Callable[[dict[str, Any], Path, Path, Path], dict[str, Any]]


def load_plan(plan_path: Path = PLAN_PATH, papers_path: Path = PAPERS_PATH) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(paper, plan step) for every step of the plan, in the order of the plan."""
    papers = {p["paper_id"]: p for p in json.loads(papers_path.read_text(encoding="utf-8"))}
    return [(papers[step["paper_id"]], step) for step in json.loads(plan_path.read_text(encoding="utf-8"))["runs"]]


def corpus_entry(paper: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
    """The corpus entry that `run_pilot.pilot4_entry` reads: the plan's command and folder, and `sh -c` for a shell command."""
    entry = copy.deepcopy(paper)
    entry["run_command"] = step["command"]
    entry["working_dir"] = step["working_dir"]
    if step["shell"]:
        entry["shell_command"] = step["command"]
    return entry


def shorten_logs(folder: Path, limit: int = LOG_LIMIT_BYTES) -> None:
    """A log longer than `limit` bytes keeps its first and last half, with a line that says how much was cut."""
    for name in LOG_NAMES:
        path = folder / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        if len(data) <= limit:
            continue
        half = limit // 2
        cut = len(data) - 2 * half
        marker = f"\n[... {cut} bytes cut by scripts/candidate_runs.py; the first and last {half} bytes are kept ...]\n".encode()
        path.write_bytes(data[:half] + marker + data[-half:])


def harness_result(message: str) -> dict[str, Any]:
    return {"k1_passed": False, "category": "harness", "log_line": message[:300], "install_status": None,
            "run_status": None, "exit_code": None, "duration_seconds": None, "metric_lines": []}


def sandbox_runner(entry: dict[str, Any], corpus_path: Path, record_root: Path, staging_dir: Path) -> dict[str, Any]:
    """Run one candidate once in the sandbox with the limits of docs/CANDIDATE_RUNS.md section 3 and classify the run."""
    from scripts import run_pilot

    paper_id = entry["paper_id"]
    try:
        record = run_pilot.run_paper(paper_id, staging_dir, pilot4=True, corpus_path=corpus_path, memory_limit=MEMORY,
                                     cpus=CPUS, run_timeout=RUN_TIMEOUT_SECONDS, record_root=record_root)
    except Exception as exc:  # noqa: BLE001 - a harness error is recorded as the candidate's result, never retried
        return harness_result(f"{type(exc).__name__}: {exc}")
    finally:
        for leftover in (staging_dir / paper_id, staging_dir / f"{paper_id}_packages"):
            if leftover.exists():
                remove_tree(leftover)
    return demo_set.classify_run(record, record_root / paper_id)


def not_run_result(step: dict[str, Any]) -> dict[str, Any]:
    reason = step["not_runnable_reason"]
    return {**harness_result(reason), "category": reason.split(":")[0]}


def read_results(out_dir: Path) -> list[dict[str, Any]]:
    path = out_dir / "evaluation.json"
    return json.loads(path.read_text(encoding="utf-8"))["results"] if path.is_file() else []


def write_results(out_dir: Path, results: list[dict[str, Any]]) -> None:
    document = {"written_at": datetime.now(UTC).isoformat(timespec="seconds"), "protocol": "docs/CANDIDATE_RUNS.md",
                "note": NOTE, "limits": {"memory": MEMORY, "cpus": CPUS, "run_timeout_seconds": RUN_TIMEOUT_SECONDS},
                "results": results}
    (out_dir / "evaluation.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def run_all(out_dir: Path, staging_dir: Path, runner: Runner = sandbox_runner, plan_path: Path = PLAN_PATH,
            papers_path: Path = PAPERS_PATH, only: set[str] | None = None) -> list[dict[str, Any]]:
    """Run the candidates of the plan in order, once each. A candidate that already has a result (or a record) is skipped:
    there is no second attempt. evaluation.json is rewritten after every candidate, so that a crash loses nothing."""
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = load_plan(plan_path, papers_path)
    results = read_results(out_dir)
    done = {r["paper_id"] for r in results}
    corpus_path = out_dir / "run_corpus.json"
    corpus = [corpus_entry(paper, step) for paper, step in plan if step["runnable"]]
    corpus_path.write_text(json.dumps(corpus, indent=2) + "\n", encoding="utf-8")
    entries = {e["paper_id"]: e for e in corpus}
    for paper, step in plan:
        paper_id = paper["paper_id"]
        if paper_id in done or (only and paper_id not in only):
            continue
        record_dir = out_dir / paper_id
        started = datetime.now(UTC).isoformat(timespec="seconds")
        if not step["runnable"]:
            result = not_run_result(step)
        elif record_dir.exists() and any(record_dir.iterdir()):
            result = harness_result(f"{record_dir.name} already holds an attempt; there is no second attempt")
        else:
            result = runner(entries[paper_id], corpus_path, out_dir, staging_dir)
            if record_dir.is_dir():
                shorten_logs(record_dir)
                demo_set.sanitize_tree(record_dir)
        passed = bool(result.pop("k1_passed"))
        results.append({"paper_id": paper_id, "repository": paper["repo_url"], "command": step["command"],
                        "working_dir": step["working_dir"], "started_at": started,
                        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"), "passed": passed, **result})
        write_results(out_dir, results)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the candidates of docs/CANDIDATE_RUNS.md once each.")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--out-dir", default=str(RUNS_DIR))
    parser.add_argument("--staging-dir", default=".sandbox_staging")
    parser.add_argument("--only", action="append", default=None, help="run only this candidate (repeatable)")
    args = parser.parse_args(argv)
    results = run_all(Path(args.out_dir), Path(args.staging_dir), only=set(args.only) if args.only else None)
    print(json.dumps({"selected": len(results), "passed": sum(1 for r in results if r["passed"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
