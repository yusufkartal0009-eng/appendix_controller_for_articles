#!/usr/bin/env python3
"""Run one repair attempt of a candidate in the sandbox, by docs/CANDIDATE_RUNS_ROUND2.md (#457).

    python scripts/candidate_round2.py fetch cand_003 --attempt 1   # fetch the `data` items of the attempt on the host
    python scripts/candidate_round2.py run cand_003 --attempt 1     # run the attempt in the sandbox and record the result
    python scripts/candidate_round2.py summary                      # data/candidates/round2/evaluation.json from the repair logs

A candidate whose failure none of the allowed repairs can address is closed with a `stopped` entry in the log
(`not_repairable`, with the log line and the reason); no attempt is made for it. The authority of a candidate is `data/candidates/round2/<paper_id>/repair_log.json`. Before a run, the log gets the attempt:
the repairs (each with its kind, reason, the log line that motivated it, and the change) and the cumulative `setup` they make
(only the keys the protocol allows). The runner refuses anything else: a third repair, a repair without a log line, a writable
copy of the repository, a source change. The record of the attempt is `<paper_id>/attempt_<n>/`; attempt 0 of a round-1 candidate
is the round-1 record (`data/candidates/runs/`), which is never run again and never touched. Third-party code only runs in the
sandbox container.
"""

from __future__ import annotations

import argparse
import copy
import json
import posixpath
import shlex
import shutil
import sys
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts import candidate_runs, demo_set
from src.config import DATA_CACHE_DIR
from src.sandbox.stager import RepoStager, remove_tree

ROUND2_DIR = candidate_runs.CANDIDATES_DIR / "round2"
ROUND1_DIR = candidate_runs.RUNS_DIR
RUN_TIMEOUT_SECONDS = 3600  # docs/CANDIDATE_RUNS_ROUND2.md section 6
INSTALL_TIMEOUT_SECONDS = 1800
MEMORY = candidate_runs.MEMORY
CPUS = candidate_runs.CPUS
MAX_REPAIRS = 2
KINDS = ("requirements", "readme_pin", "output_redirect", "working_dir", "data", "requirements_file")
# the keys of a cumulative setup; `writable_repo` is deliberately absent (section 3: the repository stays read-only)
SETUP_KEYS = ("extra_requirements", "constraints", "constraints_source", "python_version", "working_dir", "env", "data", "args_add", "requirements_files")
KIND_KEYS = {"requirements": {"extra_requirements", "constraints", "constraints_source", "python_version"},
             "readme_pin": {"extra_requirements", "constraints", "constraints_source", "python_version"},
             "output_redirect": {"args_add", "env"}, "working_dir": {"working_dir"}, "data": {"data"},
             "requirements_file": {"requirements_files"}}
NOTE = "selected list of candidates, not a sample; the share that passed is not a success rate"

Runner = Callable[[dict[str, Any], dict[str, Any], Path, Path, Path], dict[str, Any]]


def log_path(paper_id: str, root: Path = ROUND2_DIR) -> Path:
    return root / paper_id / "repair_log.json"


def read_log(paper_id: str, root: Path = ROUND2_DIR) -> dict[str, Any]:
    path = log_path(paper_id, root)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"paper_id": paper_id, "round": 2, "attempts": []}


def write_log(log: dict[str, Any], root: Path = ROUND2_DIR) -> None:
    path = log_path(log["paper_id"], root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")


def validate_attempt(log: dict[str, Any], attempt: dict[str, Any], risky: bool) -> None:
    """The rules of section 3 and 5 for one attempt of the log. Raises ValueError when one is broken."""
    number = attempt["attempt"]
    if number > MAX_REPAIRS or number < 0 or (number == 0 and not risky):
        raise ValueError(f"attempt {number}: at most {MAX_REPAIRS} repairs; attempt 0 exists only for a risky candidate")
    unknown = sorted(set(attempt["setup"]) - set(SETUP_KEYS))
    if unknown:
        raise ValueError(f"not allowed in a repair (docs/CANDIDATE_RUNS_ROUND2.md section 3): {unknown}")
    repairs = attempt["repairs"]
    if number > 0 and not repairs:
        raise ValueError("a repair attempt needs at least one repair")
    if len([r for r in repairs if r.get("repair_number") == number]) == 0 and number > 0:
        raise ValueError(f"attempt {number} needs a repair numbered {number}")
    for repair in repairs:
        if repair.get("kind") not in KINDS:
            raise ValueError(f"repair kind must be one of {KINDS}: {repair.get('kind')!r}")
        if not (repair.get("reason") and repair.get("log_line") and repair.get("change")):
            raise ValueError("every repair needs a reason, the log line that motivated it, and the change")
    used = {k for k in attempt["setup"] if k != "constraints_source"}
    allowed = set().union(*(KIND_KEYS[r["kind"]] for r in repairs)) if repairs else ({"data"} if number == 0 else set())
    if used - allowed:
        raise ValueError(f"the setup changes {sorted(used - allowed)} that no repair of the attempt explains")
    earlier = [a for a in log["attempts"] if a["attempt"] < number]
    if any(a.get("result", {}).get("passed") for a in earlier):
        raise ValueError("an earlier attempt passed; there is nothing to repair")
    if any(a.get("result") is None for a in earlier):
        raise ValueError("an earlier attempt has no result yet")
    first = 0 if risky else 1
    missing = [n for n in range(first, number) if not any(a["attempt"] == n for a in earlier)]
    if missing:
        raise ValueError(f"attempt {number}: the earlier attempts {missing} are missing from the log")


def effective_command(step: dict[str, Any], target_script: str, setup: dict[str, Any]) -> tuple[str, str]:
    """(command, working_dir) of an attempt: the plan's command with the extra arguments of `output_redirect` appended, and the
    script path re-based when a `working_dir` repair moves the folder. A shell command only gets the arguments appended."""
    command, working_dir = step["command"], setup.get("working_dir", step["working_dir"])
    if not step["shell"] and working_dir != step["working_dir"]:
        tokens = shlex.split(command)
        tokens[1] = posixpath.relpath(target_script, working_dir or ".")
        command = shlex.join(tokens)
    if setup.get("args_add"):
        command = f"{command} {shlex.join(setup['args_add'])}"
    return command, working_dir


def corpus_entry(paper: dict[str, Any], step: dict[str, Any], setup: dict[str, Any]) -> dict[str, Any]:
    command, working_dir = effective_command(step, paper["target_script"], setup)
    entry = candidate_runs.corpus_entry(paper, {**step, "command": command, "working_dir": working_dir})
    if setup.get("requirements_files"):
        entry["round2_requirements_files"] = list(setup["requirements_files"])
    return entry


class FilteredStager(RepoStager):
    """A stager that installs only the requirement files the README names (kind `requirements_file`, section 10 of the
    protocol), when the repository holds several files whose pins conflict. The files are not edited."""

    def __init__(self, *args: Any, requirements_files: list[str], **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.requirements_files = requirements_files

    def stage_repository(self, *args: Any, **kwargs: Any):
        staged = super().stage_repository(*args, **kwargs)
        unknown = [n for n in self.requirements_files if n not in staged.manifest.requirements_files]
        if unknown:
            raise ValueError(f"requirement files not found in the repository: {unknown}")
        staged.manifest.requirements_files = list(self.requirements_files)
        return staged


def correction_of(attempt: dict[str, Any]) -> dict[str, Any] | None:
    """The correction dict `run_pilot.pilot4_entry` reads (its keys, plus the log lines of `changes`)."""
    keys = ("extra_requirements", "constraints", "constraints_source", "python_version", "env", "data")
    correction = {k: copy.deepcopy(attempt["setup"][k]) for k in keys if k in attempt["setup"]}
    if not attempt["repairs"]:
        return correction or None
    correction["changes"] = [{"change": r["change"], "log_line": r["log_line"]} for r in attempt["repairs"]]
    return correction


@contextmanager
def install_limit(seconds: int):
    """The install phase uses `timeout_seconds` of the pilot limits; the protocol sets it to 1800 s."""
    from scripts import run_pilot

    saved = run_pilot.PILOT_LIMITS
    run_pilot.PILOT_LIMITS = {**saved, "timeout_seconds": seconds}
    try:
        yield
    finally:
        run_pilot.PILOT_LIMITS = saved


def sandbox_runner(entry: dict[str, Any], correction: dict[str, Any] | None, corpus_path: Path, record_root: Path,
                   staging_dir: Path) -> dict[str, Any]:
    from scripts import run_pilot

    paper_id = entry["paper_id"]
    files = entry.get("round2_requirements_files")
    stager = FilteredStager(staging_root=staging_dir, bundle_in_docker=True, requirements_files=files) if files else None
    try:
        with install_limit(INSTALL_TIMEOUT_SECONDS):
            record = run_pilot.run_paper(paper_id, staging_dir, stager=stager, pilot4=True, corpus_path=corpus_path, memory_limit=MEMORY,
                                         cpus=CPUS, run_timeout=RUN_TIMEOUT_SECONDS, record_root=record_root,
                                         correction=correction)
    except Exception as exc:  # noqa: BLE001 - a harness error is recorded as the attempt's result
        return candidate_runs.harness_result(f"{type(exc).__name__}: {exc}")
    finally:
        for leftover in (staging_dir / paper_id, staging_dir / f"{paper_id}_packages"):
            if leftover.exists():
                remove_tree(leftover)
    return demo_set.classify_run(record, record_root / paper_id)


def fetch_attempt_data(paper_id: str, attempt: dict[str, Any], cache_root: Path = DATA_CACHE_DIR) -> list[dict[str, Any]]:
    from scripts import fetch_data

    fetch_data.require_tar_filters()
    return [fetch_data.fetch_item(paper_id, item, cache_root) for item in attempt["setup"].get("data", [])]


def run_attempt(paper_id: str, number: int, runner: Runner = sandbox_runner, root: Path = ROUND2_DIR,
                staging_dir: Path = Path(".sandbox_staging"), plan_path: Path = candidate_runs.PLAN_PATH,
                papers_path: Path = candidate_runs.PAPERS_PATH, risky: bool = False) -> dict[str, Any]:
    """Run attempt `number` of the log once. An attempt that has a result is never run again."""
    plan = {p["paper_id"]: (p, s) for p, s in candidate_runs.load_plan(plan_path, papers_path)}
    paper, step = plan[paper_id]
    log = read_log(paper_id, root)
    attempt = next((a for a in log["attempts"] if a["attempt"] == number), None)
    if attempt is None:
        raise ValueError(f"{paper_id}: attempt {number} is not in the repair log; write the repairs first")
    if attempt.get("result") is not None:
        raise ValueError(f"{paper_id}: attempt {number} already has a result; there is no second run of an attempt")
    validate_attempt(log, attempt, risky)
    record_dir = root / paper_id / f"attempt_{number}"
    if record_dir.exists():
        raise FileExistsError(f"{record_dir} exists; an attempt is never overwritten")
    entry = corpus_entry(paper, step, attempt["setup"])
    work = root / paper_id / f"_work_{number}"
    work.mkdir(parents=True, exist_ok=True)
    corpus_path = work / "corpus.json"
    corpus_path.write_text(json.dumps([entry], indent=2) + "\n", encoding="utf-8")
    started = datetime.now(UTC).isoformat(timespec="seconds")
    result = runner(entry, correction_of(attempt), corpus_path, work, staging_dir)
    produced = work / paper_id
    if produced.is_dir():
        shutil.move(str(produced), str(record_dir))
        candidate_runs.shorten_logs(record_dir)
        demo_set.sanitize_tree(record_dir)
    shutil.rmtree(work, ignore_errors=True)
    passed = bool(result.pop("k1_passed"))
    command, working_dir = effective_command(step, paper["target_script"], attempt["setup"])
    attempt.update({"command": command, "working_dir": working_dir, "started_at": started,
                    "finished_at": datetime.now(UTC).isoformat(timespec="seconds"), "record": record_dir.name,
                    "limits": {"memory": MEMORY, "cpus": CPUS, "run_timeout_seconds": RUN_TIMEOUT_SECONDS,
                               "install_timeout_seconds": INSTALL_TIMEOUT_SECONDS},
                    "result": {"passed": passed, **result}})
    write_log(log, root)
    return attempt


def summarize(root: Path = ROUND2_DIR, round1_dir: Path = ROUND1_DIR) -> dict[str, Any]:
    """The results of round 2 per candidate, read from the repair logs only."""
    round1 = {r["paper_id"]: r for r in json.loads((round1_dir / "evaluation.json").read_text(encoding="utf-8"))["results"]}
    results = []
    for log_file in sorted(root.glob("*/repair_log.json")):
        log = json.loads(log_file.read_text(encoding="utf-8"))
        attempts = [a for a in log["attempts"] if a.get("result")]
        passing = next((a for a in attempts if a["result"]["passed"]), None)
        paper_id = log["paper_id"]
        results.append({"paper_id": paper_id, "in_round_1": paper_id in round1,
                        "round1_passed": round1[paper_id]["passed"] if paper_id in round1 else None,
                        "attempts": len(attempts), "passed": passing is not None,
                        "passed_at_attempt": passing["attempt"] if passing else None,
                        "repairs": [r for a in attempts[-1:] for r in a["repairs"]] if attempts else [],
                        "final_category": None if passing else (attempts[-1]["result"].get("category") if attempts else None),
                        "final_log_line": None if passing else (attempts[-1]["result"].get("log_line") if attempts else None),
                        "stopped": log.get("stopped"), "table_match": log.get("table_match")})
    document = {"written_at": datetime.now(UTC).isoformat(timespec="seconds"), "protocol": "docs/CANDIDATE_RUNS_ROUND2.md",
                "note": NOTE, "results": results}
    (root / "evaluation.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One repair attempt of a candidate, by docs/CANDIDATE_RUNS_ROUND2.md.")
    parser.add_argument("command", choices=["fetch", "run", "summary"])
    parser.add_argument("paper_id", nargs="?")
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--risky", action="store_true", help="the candidate is a risky one (attempt 0 exists)")
    parser.add_argument("--staging-dir", default=".sandbox_staging")
    args = parser.parse_args(argv)
    if args.command == "summary":
        document = summarize()
        print(json.dumps({"candidates": len(document["results"]), "passed": sum(r["passed"] for r in document["results"])}))
        return 0
    if not args.paper_id:
        parser.error("paper_id is required")
    if args.command == "fetch":
        log = read_log(args.paper_id)
        attempt = next(a for a in log["attempts"] if a["attempt"] == args.attempt)
        print(json.dumps(fetch_attempt_data(args.paper_id, attempt), indent=2))
        return 0
    attempt = run_attempt(args.paper_id, args.attempt, staging_dir=Path(args.staging_dir), risky=args.risky)
    print(json.dumps({"paper_id": args.paper_id, "attempt": args.attempt, **attempt["result"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
