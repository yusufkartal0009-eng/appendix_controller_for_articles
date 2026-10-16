#!/usr/bin/env python3
"""Do repeated runs of the same paper agree? Status, exit code, metrics, and files (#329).

    python scripts/run_stability.py              # print the tables
    python scripts/run_stability.py --json       # the same as JSON
    python scripts/run_stability.py --write      # replace the generated blocks of docs/CPU_RUNS.md and docs/STABILITY_RUNS.md
    python scripts/run_stability.py --check      # exit 1 if a block differs from what the stored runs give

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
CHR_NL = chr(10)
CHR_CRLF = chr(13) + chr(10)
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


def run_seconds(directory: Path) -> tuple[float | None, float | None]:
    """(duration of the run phase, duration of install and run in the sandbox) of a stored run."""
    record, _report = load_run(directory)
    return (record.get("run") or {}).get("duration_seconds"), record.get("sandbox_duration_seconds")


def cpu_effect(data: Path = DATA) -> list[dict[str, Any]]:
    """For every CPU run (`data/cpu_runs/`): the same paper's stored runs with the protocol's 2 CPUs, the durations, and the
    speed-up. Same metrics are checked against the CPU run's."""
    rows = []
    for paper_id, candidates in CANDIDATES.items():
        cpu_dir = data / "cpu_runs" / paper_id
        if not (cpu_dir / "pilot_record.json").is_file():
            continue
        cpu = describe("CPU run", cpu_dir)
        cpu_run, cpu_total = run_seconds(cpu_dir)
        for label, rel in candidates:
            path = data / rel
            if label == "CPU run" or not (path / "pilot_record.json").is_file():
                continue
            ref = describe(label, path)
            if ref["cpus"] != 2.0:
                continue
            ref_run, ref_total = run_seconds(path)
            rows.append({
                "paper_id": paper_id, "cpu_cpus": cpu["cpus"], "reference": label, "reference_cpus": ref["cpus"],
                "reference_run_seconds": ref_run, "cpu_run_seconds": cpu_run,
                "seconds_saved": None if None in (ref_run, cpu_run) else round(ref_run - cpu_run, 1),
                "speedup": None if not (ref_run and cpu_run) else round(ref_run / cpu_run, 2),
                "reference_total_seconds": ref_total, "cpu_total_seconds": cpu_total,
                "total_speedup": None if not (ref_total and cpu_total) else round(ref_total / cpu_total, 2),
                "same_status": ref["status"] == cpu["status"] and ref["exit_code"] == cpu["exit_code"],
                "same_metrics": ref["metrics"] == cpu["metrics"], "metrics": cpu["metrics"],
            })
    return rows


def cpu_markdown(rows: list[dict[str, Any]]) -> str:
    header = ("| Paper | CPU run: CPUs | Compared with (2 CPUs) | Its run phase (s) | CPU run's run phase (s) | Seconds saved | "
              "Run-phase speed-up | Install and run (s): reference / CPU run | Same status and exit code | Same metrics |")
    lines = [header, "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| `{r['paper_id']}` | {r['cpu_cpus']:g} | {r['reference']} | {_cell(r['reference_run_seconds'])} | "
                     f"{_cell(r['cpu_run_seconds'])} | {_cell(r['seconds_saved'])} | {_cell(r['speedup'])}x | "
                     f"{_cell(r['reference_total_seconds'])} / {_cell(r['cpu_total_seconds'])} | "
                     f"{'yes' if r['same_status'] else 'no'} | {'yes' if r['same_metrics'] else 'no'} |")
    return "\n".join(lines) + "\n\n" + cpu_sentence(rows)


def cpu_sentence(rows: list[dict[str, Any]]) -> str:
    """One sentence with the range of the run-phase speed-up, from the rows above."""
    if not rows:
        return "No CPU run is stored."
    speedups = [r["speedup"] for r in rows if r["speedup"] is not None]
    totals = [r["total_speedup"] for r in rows if r["total_speedup"] is not None]
    cpus = sorted({r["cpu_cpus"] for r in rows})
    same = all(r["same_status"] and r["same_metrics"] for r in rows)
    return (f"With {', '.join(f'{c:g}' for c in cpus)} CPUs instead of 2, the run phase was {min(speedups):g} to {max(speedups):g} "
            f"times faster in the {len(rows)} comparisons (install and run together: {min(totals):g} to {max(totals):g} times); "
            f"status, exit code, and metrics were the same in {'all' if same else 'not all'} of them.")


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


BLOCKS = {
    "docs/CPU_RUNS.md": ("<!-- cpu-runs:start -->", "<!-- cpu-runs:end -->"),
    "docs/STABILITY_RUNS.md": ("<!-- stability-runs:start -->", "<!-- stability-runs:end -->"),
}


def block_text(doc: str, data: Path = DATA) -> str:
    if doc == "docs/CPU_RUNS.md":
        return cpu_markdown(cpu_effect(data))
    result = measure(data)
    return to_markdown(result) + CHR_NL * 2 + to_sentence(result)


def apply_block(text: str, doc: str, data: Path = DATA) -> str:
    start, end = BLOCKS[doc]
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"{doc} must hold exactly one generated block")
    a, b = text.index(start) + len(start), text.index(end)
    return text[:a] + CHR_NL + block_text(doc, data) + CHR_NL + text[b:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Do repeated runs of the same paper agree?")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true", help="Replace the generated blocks of the two documents.")
    parser.add_argument("--check", action="store_true", help="Exit 1 if a block differs from the stored runs.")
    args = parser.parse_args(argv)
    if args.write or args.check:
        bad = []
        for doc in BLOCKS:
            path = project_root / doc
            if not path.is_file():
                continue  # a document that has not been written yet (docs/STABILITY_RUNS.md waits for the second runs)
            raw = path.read_bytes().decode("utf-8")
            text = raw.replace(CHR_CRLF, CHR_NL)
            new = apply_block(text, doc)
            if args.check and new != text:
                bad.append(doc)
            elif args.write:
                path.write_bytes((new.replace(CHR_NL, CHR_CRLF) if CHR_CRLF in raw else new).encode("utf-8"))
        if args.check:
            print(json.dumps({"in_sync": not bad, "documents_that_differ": bad}))
            return 1 if bad else 0
        return 0
    result = measure()
    print(json.dumps(result, indent=2) if args.json else to_markdown(result) + CHR_NL * 2 + to_sentence(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
