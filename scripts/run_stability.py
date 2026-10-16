#!/usr/bin/env python3
"""Do repeated runs of the same paper agree? Status, exit code, metrics, and files (#329).

    python scripts/run_stability.py              # print the tables
    python scripts/run_stability.py --json       # the same as JSON

For `paper_003` and `paper_006` (the two papers whose runs completed), every stored run directory is listed: the pilots
(`data/pilot2_runs/`, `data/pilot3_runs/`), the memory re-runs (`data/memory_runs/`, #321 and the second runs), and the
CPU runs (`data/cpu_runs/`). The runs differ in their memory and CPU limits where the table says so; they are not all protocol
runs. Agreement is judged on the status, the exit code, and the metrics that the metric extractor stored in
`run_report.json`. The log files (`*.log`) are compared with the first run listed by SHA-256 of their bytes with the line endings
normalized (the repository is checked out with `core.autocrlf`, so a stored log may have CRLF where the fresh one has LF); the
other files (records with clock times, durations, and paths) differ by construction and are compared with
`scripts/hash_run.py`. Nothing is typed by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.memory_runs import GIB, limit_bytes
from src.score_run import load_run

DATA = project_root / "data"
CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "paper_003": [("Pilot 3", "pilot3_runs/paper_003"), ("memory re-run", "memory_runs/paper_003"),
                  ("memory re-run, second", "memory_runs/paper_003_run2"), ("CPU run", "cpu_runs/paper_003")],
    "paper_006": [("Pilot 2", "pilot2_runs/paper_006"), ("Pilot 3", "pilot3_runs/paper_006"),
                  ("memory re-run", "memory_runs/paper_006"), ("memory re-run, second", "memory_runs/paper_006_run2"),
                  ("CPU run", "cpu_runs/paper_006")],
}


def describe(label: str, directory: Path) -> dict[str, Any]:
    record, report = load_run(directory)
    run = record.get("run") or {}
    limits = record.get("limits") or {}
    peak = run.get("peak_memory_bytes")
    return {
        "label": label, "directory": directory.relative_to(directory.parents[1]).as_posix(),
        "status": run.get("status"), "exit_code": run.get("exit_code"), "duration_seconds": run.get("duration_seconds"),
        "peak_memory_gib": None if peak is None else round(peak / GIB, 2),
        "memory_limit_gib": round(limit_bytes(limits["memory_limit"]) / GIB, 2) if limits.get("memory_limit") else None,
        "cpus": limits.get("cpus"), "metrics": report.get("metrics") or {},
    }


def log_hashes(directory: Path) -> dict[str, str]:
    """SHA-256 of every `*.log` file of a run directory, line endings normalized to LF."""
    crlf, lf = bytes([13, 10]), bytes([10])
    return {p.name: hashlib.sha256(p.read_bytes().replace(crlf, lf)).hexdigest() for p in sorted(directory.glob("*.log"))}


def measure(data: Path = DATA) -> dict[str, dict[str, Any]]:
    """Per paper: its stored runs, whether they agree, and the byte-for-byte file comparison with the first run."""
    result: dict[str, dict[str, Any]] = {}
    for paper_id, candidates in CANDIDATES.items():
        found = [(label, data / rel) for label, rel in candidates if (data / rel / "pilot_record.json").is_file()]
        if len(found) < 2:
            continue
        runs = [describe(label, path) for label, path in found]
        first = runs[0]
        first_logs = log_hashes(found[0][1])
        logs_identical = []
        for _label, path in found[1:]:
            logs = log_hashes(path)
            names = sorted(set(first_logs) | set(logs))
            logs_identical.append({"files": len(names),
                                   "identical": sum(1 for n in names if first_logs.get(n) == logs.get(n))})
        result[paper_id] = {
            "runs": runs,
            "same_status": all(r["status"] == first["status"] for r in runs),
            "same_exit_code": all(r["exit_code"] == first["exit_code"] for r in runs),
            "same_metrics": all(r["metrics"] == first["metrics"] for r in runs),
            "metrics": first["metrics"],
            "logs_identical_with_first": logs_identical,
        }
    return result


def _cell(value: Any) -> str:
    return "n/a" if value is None else str(value)


def to_markdown(result: dict[str, dict[str, Any]]) -> str:
    lines = ["| Paper | Run | Status (exit) | Duration (s) | Peak memory (GiB) | Memory limit (GiB) | CPUs | Metrics |",
             "|---|---|---|---|---|---|---|---|"]
    for paper_id, group in result.items():
        for run in group["runs"]:
            metrics = ", ".join(f"{k} {v}" for k, v in run["metrics"].items()) or "none"
            lines.append(f"| `{paper_id}` | {run['label']} (`data/{run['directory']}`) | {run['status']} ({_cell(run['exit_code'])}) | "
                         f"{_cell(run['duration_seconds'])} | {_cell(run['peak_memory_gib'])} | {_cell(run['memory_limit_gib'])} | "
                         f"{_cell(run['cpus'])} | {metrics} |")
    return "\n".join(lines)


def _yes(flag: bool) -> str:
    return "identical" if flag else "different"


def to_sentence(result: dict[str, dict[str, Any]]) -> str:
    parts = []
    for paper_id, group in result.items():
        metrics = ", ".join(f"{k} {v}" for k, v in group["metrics"].items()) or "none stored"
        logs = group["logs_identical_with_first"]
        identical = sum(item["identical"] for item in logs)
        total = sum(item["files"] for item in logs)
        parts.append(f"`{paper_id}`: {len(group['runs'])} runs, status {_yes(group['same_status'])}, exit code "
                     f"{_yes(group['same_exit_code'])}, metrics {_yes(group['same_metrics'])} ({metrics}); "
                     f"{identical} of {total} log files identical (line endings ignored) with the first run's")
    return "; ".join(parts) + "."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Do repeated runs of the same paper agree?")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = measure()
    print(json.dumps(result, indent=2) if args.json else to_markdown(result) + "\n\n" + to_sentence(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
