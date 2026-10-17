#!/usr/bin/env python3
"""Does the installed-environment cache shorten a second run, and does the run stay the same? (#380)

    python scripts/env_cache_runs.py            # print the table
    python scripts/env_cache_runs.py --json     # the same as JSON
    python scripts/env_cache_runs.py --write    # replace the generated block of docs/ENV_CACHE_RUNS.md
    python scripts/env_cache_runs.py --check    # exit 1 if the block differs from what the stored runs give

The table puts the two runs with the cache (`data/env_cache_runs/first_run`: nothing stored yet, so it installs and stores;
`second_run`: the stored environment is verified and mounted, the install container is skipped) next to the earlier stored
runs of `paper_003` with the same settings (Pilot 3 overlay, 50% of the host's RAM, 2 CPUs: `data/memory_runs/`). Every
number is read from the stored records; nothing is typed by hand. The gain is the difference between the second run and the
earlier runs, per phase. The comparison has limits that the document states: one second run, a clock that also ran other work,
and the phases that the cache does not touch (staging, bundling, the run phase) differ from run to run.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.memory_runs import GIB, limit_bytes
from src.score_run import load_run

DATA = project_root / "data"
DOC = project_root / "docs" / "ENV_CACHE_RUNS.md"
START = "<!-- env-cache-runs:start -->"
END = "<!-- env-cache-runs:end -->"
PAPER = "paper_003"
RUNS: list[tuple[str, str]] = [
    ("memory re-run (no cache)", f"memory_runs/{PAPER}"),
    ("memory re-run, second (no cache)", f"memory_runs/{PAPER}_run2"),
    ("with cache, first run (miss, stores)", f"env_cache_runs/first_run/{PAPER}"),
    ("with cache, second run (hit)", f"env_cache_runs/second_run/{PAPER}"),
]


def seconds_between(record: dict[str, Any]) -> float | None:
    try:
        start = datetime.fromisoformat(record["started_at"])
        end = datetime.fromisoformat(record["finished_at"])
    except (KeyError, ValueError):
        return None
    return round((end - start).total_seconds(), 1)


def describe(label: str, directory: Path, base: Path = DATA) -> dict[str, Any]:
    record, report = load_run(directory)
    run = record.get("run") or {}
    install = record.get("install_meta") or {}
    cache = record.get("env_cache") or {}
    limits = record.get("limits") or {}
    return {
        "label": label, "directory": directory.relative_to(base).as_posix(),
        "cache": "hit" if cache.get("hit") else ("miss" if cache.get("enabled") else "off"),
        "cpus": limits.get("cpus"),
        "memory_gib": round(limit_bytes(limits["memory_limit"]) / GIB, 2) if limits.get("memory_limit") else None,
        "bundle_seconds": (record.get("bundle") or {}).get("duration_seconds"),
        "install_seconds": install.get("duration_seconds"),
        "key_and_verify_seconds": (cache.get("verify_seconds") if cache.get("hit") else None),
        "store_seconds": (cache.get("stored") or {}).get("store_seconds") if isinstance(cache.get("stored"), dict) else None,
        "run_seconds": run.get("duration_seconds"),
        "sandbox_seconds": record.get("sandbox_duration_seconds"),
        "wall_seconds": seconds_between(record),
        "status": run.get("status"), "exit_code": run.get("exit_code"), "install_status": run.get("dependency_install_status"),
        "metrics": report.get("metrics") or {},
    }


def measure(data: Path = DATA) -> dict[str, Any]:
    runs = [describe(label, data / rel, data) for label, rel in RUNS if (data / rel / "pilot_record.json").is_file()]
    cached = [r for r in runs if r["cache"] == "hit"]
    uncached = [r for r in runs if r["cache"] == "off"]
    result: dict[str, Any] = {"paper_id": PAPER, "runs": runs}
    if cached and uncached:
        hit = cached[-1]
        result["same_status_and_exit_code"] = all((r["status"], r["exit_code"]) == (hit["status"], hit["exit_code"]) for r in runs)
        result["same_metrics"] = all(r["metrics"] == hit["metrics"] for r in runs)
        result["metrics"] = hit["metrics"]
        gains = []
        for ref in uncached:
            def diff(key: str, ref=ref, hit=hit) -> float | None:
                return None if ref[key] is None or hit[key] is None else round(ref[key] - hit[key], 1)
            gains.append({"reference": ref["label"], "install_seconds_saved": diff("install_seconds"),
                          "sandbox_seconds_saved": diff("sandbox_seconds"), "wall_seconds_saved": diff("wall_seconds"),
                          "run_seconds_difference": diff("run_seconds"), "bundle_seconds_difference": diff("bundle_seconds")})
        result["gains_of_the_second_run"] = gains
    return result


def _cell(value: Any) -> str:
    return "n/a" if value is None else (f"{value:,.1f}" if isinstance(value, float) else str(value))


def markdown(result: dict[str, Any]) -> str:
    header = ("| Run | Cache | Bundling (s) | Install phase (s) | Run phase (s) | Install and run (s) | Whole run, wall clock (s) | "
              "Status | Exit code |")
    lines = [header, "|---|---|---|---|---|---|---|---|---|"]
    for r in result["runs"]:
        lines.append(f"| {r['label']} (`{r['directory']}`) | {r['cache']} | {_cell(r['bundle_seconds'])} | "
                     f"{_cell(r['install_seconds'])} | {_cell(r['run_seconds'])} | {_cell(r['sandbox_seconds'])} | "
                     f"{_cell(r['wall_seconds'])} | {r['status']} | {r['exit_code']} |")
    if "gains_of_the_second_run" not in result:
        return "\n".join(lines) + "\n\nNo run with a cache hit is stored yet.\n"
    gain_header = ("| Compared with | Install phase saved (s) | Install and run saved (s) | Whole run saved (s) | "
                   "Run phase: difference (s) | Bundling: difference (s) |")
    lines += ["", "Difference of the second cached run (hit) from each run without the cache (positive = the cached run is shorter):",
              "", gain_header, "|---|---|---|---|---|---|"]
    for g in result["gains_of_the_second_run"]:
        lines.append(f"| {g['reference']} | {_cell(g['install_seconds_saved'])} | {_cell(g['sandbox_seconds_saved'])} | "
                     f"{_cell(g['wall_seconds_saved'])} | {_cell(g['run_seconds_difference'])} | {_cell(g['bundle_seconds_difference'])} |")
    hit = next(r for r in result["runs"] if r["cache"] == "hit")
    verdict = (f"Same status and exit code in all {len(result['runs'])} runs: **{'yes' if result['same_status_and_exit_code'] else 'no'}**. "
               f"Same metrics in all {len(result['runs'])} runs: **{'yes' if result['same_metrics'] else 'no'}**. "
               f"The second cached run's install phase took {_cell(hit['install_seconds'])} s (key, verification and restore).")
    lines += ["", f"Metrics of the cached second run: {json.dumps(result['metrics'], sort_keys=True)}.", verdict]
    return "\n".join(lines) + "\n"


def block(data: Path = DATA) -> str:
    header = ("<!-- Generated by `python scripts/env_cache_runs.py --write` from data/memory_runs/ and data/env_cache_runs/. "
              "Do not edit by hand. -->")
    return f"{START}\n{header}\n\n{markdown(measure(data))}\n{END}"


def apply_block(text: str, new_block: str) -> str:
    start, end = text.find(START), text.find(END)
    if start < 0 or end < 0:
        raise ValueError(f"{DOC.name} has no {START} ... {END} block")
    return text[:start] + new_block + text[end + len(END):]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Installed-environment cache: what the second run saves (#380).")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.json:
        print(json.dumps(measure(), indent=2))
        return 0
    if args.write or args.check:
        text = DOC.read_bytes().decode("utf-8").replace("\r\n", "\n")
        updated = apply_block(text, block())
        if args.check:
            if updated != text:
                print(f"{DOC.name} is out of date; run with --write", file=sys.stderr)
                return 1
            return 0
        DOC.write_bytes(updated.replace("\n", "\r\n").encode("utf-8"))
        return 0
    print(markdown(measure()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
