#!/usr/bin/env python3
"""Run one paper once per seed and summarize the seed runs (#48, docs/MULTI_SEED.md).

    python scripts/run_multi_seed.py paper_006 --pilot3 --memory 50% --cpus 4

The paper must have a seed spec (`data/multi_seed_settings.json` or `run_setup.seed`): the paper's own seed parameter is
used, nothing in the paper's code is changed. Every seed is one real sandbox run with the same limits and is stored as its
own record in `data/multi_seed_runs/<paper_id>/seed_<N>/`; `multi_seed_summary.json` holds the mean, standard deviations, and
CV of every metric found in all successful seed runs, and the Tier 3 score computed from them. A failed seed run is kept as
a record and contributes no value. These are not protocol runs: the limits are the ones given on the command line and the
records say so.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts import run_pilot
from src.multi_seed import (
    apply_seed,
    load_seed_settings,
    seed_spec_of,
    summarize_seed_runs,
)
from src.score_run import load_run
from src.scoring import Tier3StabilityEvaluator

OUT_DIR = project_root / "data" / "multi_seed_runs"
SUMMARY_NAME = "multi_seed_summary.json"
PROTOCOL = "docs/MULTI_SEED.md"


def run_seeds(entry: dict[str, Any], spec: dict[str, Any], out_dir: Path, staging_dir: Path,
              seeds: list[int] | None = None, **run_options: Any) -> dict[str, Any]:
    """One sandbox run per seed; returns (and writes) the summary. `run_options` go to `run_pilot.run_paper`."""
    paper_id = entry["paper_id"]
    paper_dir = out_dir / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    seed_list = list(seeds or spec["values"])
    for seed in seed_list:
        seed_dir = paper_dir / f"seed_{seed}"
        if seed_dir.exists():
            raise FileExistsError(f"{seed_dir} already holds a run; a stored run is evidence and is not overwritten")
        scratch = paper_dir / f".scratch_seed_{seed}"
        if scratch.exists():
            shutil.rmtree(scratch)
        extra = {"multi_seed": {"seed": seed, "seeds": seed_list, "seed_source": spec["source"],
                                "note": "not a protocol run (docs/MULTI_SEED.md): one of several runs of the same paper "
                                        "that differ only in the paper's own seed parameter"}}
        run_pilot.run_paper(paper_id, staging_dir, pilot2=True, record_root=scratch,
                            entry_override=apply_seed(entry, spec, seed), record_extra=extra, **run_options)
        shutil.move(str(scratch / paper_id), str(seed_dir))
        shutil.rmtree(scratch, ignore_errors=True)
    return summarize_stored(paper_id, paper_dir, spec, seed_list)


def stored_seeds(paper_dir: Path) -> list[int]:
    """The seeds that have a stored run folder (`seed_<N>/pilot_record.json`), in numeric order."""
    return sorted(int(p.name.split("_")[1]) for p in paper_dir.glob("seed_*") if (p / "pilot_record.json").is_file())


def summarize_stored(paper_id: str, paper_dir: Path, spec: dict[str, Any], seeds: list[int]) -> dict[str, Any]:
    """Read the stored seed folders, write `multi_seed_summary.json`, and return it. Needs no Docker."""
    runs: list[dict[str, Any]] = []
    metrics_by_seed: dict[int, dict[str, float]] = {}
    limits: dict[str, Any] = {}
    for seed in seeds:
        seed_dir = paper_dir / f"seed_{seed}"
        record, report = load_run(seed_dir)
        limits = limits or record.get("limits", {})
        run = record.get("run") or {}
        metrics = {k: float(v) for k, v in (report.get("metrics") or {}).items() if isinstance(v, (int, float))}
        used = run.get("status") == "COMPLETED" and run.get("exit_code") == 0 and bool(metrics)
        if used:
            metrics_by_seed[seed] = metrics
        runs.append({"seed": seed, "record_dir": seed_dir.relative_to(project_root).as_posix()
                     if seed_dir.is_relative_to(project_root) else seed_dir.as_posix(),
                     "stage_status": (record.get("stage") or {}).get("status"), "run_status": run.get("status"),
                     "exit_code": run.get("exit_code"), "duration_seconds": run.get("duration_seconds"),
                     "metrics": metrics, "used": used,
                     "reason_not_used": None if used else "the seed run did not complete with metrics"})
    metrics_summary = summarize_seed_runs(metrics_by_seed)
    measured = len(metrics_by_seed) >= 2
    score, notes = Tier3StabilityEvaluator.evaluate_by_metric(
        {name: m["values"] for name, m in metrics_summary.items()} if measured else None,
        single_run_clean=bool(metrics_by_seed), execution_succeeded=bool(metrics_by_seed))
    by_metric = {name: {"cv": m["cv"], "score_if_this_metric_alone": Tier3StabilityEvaluator.evaluate(m["values"])[0]}
                 for name, m in metrics_summary.items()}
    summary = {
        "paper_id": paper_id, "protocol": PROTOCOL, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seed_spec": spec, "limits": limits, "runs": runs,
        "successful_seed_runs": len(metrics_by_seed), "metrics": metrics_summary,
        "tier3": {"score": score, "notes": notes,
                  "decided_by": max(by_metric, key=lambda n: by_metric[n]["cv"]) if measured else None,
                  "basis": ("measured: the metric with the largest CV decides" if measured
                            else "single-run baseline, not a stability measurement")},
        "tier3_by_metric": by_metric,
        "note": ("std_population (divisor n) is the one Tier 3 uses; std_sample (divisor n - 1) is stored for reading. "
                 "tier3_by_metric shows what each metric alone would score; the score above is that of the metric "
                 "with the largest CV."),
    }
    (paper_dir / SUMMARY_NAME).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("paper_id")
    parser.add_argument("--seeds", default=None, metavar="N,N,...", help="Replace the seeds of the spec (at least two).")
    parser.add_argument("--settings", default=None, metavar="FILE", help="Seed settings (data/multi_seed_settings.json).")
    parser.add_argument("--staging-dir", default=".sandbox_staging")
    parser.add_argument("--data-cache", default=str(run_pilot.DATA_CACHE_DIR))
    parser.add_argument("--record-root", default=str(OUT_DIR), metavar="DIR")
    parser.add_argument("--pilot3", action="store_true", help="Apply data/pilot3_settings.json on top of the run setup.")
    parser.add_argument("--memory", default=None, metavar="LIMIT")
    parser.add_argument("--cpus", type=float, default=None, metavar="N")
    parser.add_argument("--run-timeout", type=int, default=None, metavar="SECONDS")
    parser.add_argument("--summarize-only", action="store_true",
                        help="Rebuild multi_seed_summary.json from the stored seed folders; runs nothing (no Docker).")
    args = parser.parse_args(argv)
    try:
        entry = run_pilot.load_entry(args.paper_id)
        if args.summarize_only:
            spec = seed_spec_of(entry, load_seed_settings(Path(args.settings) if args.settings else None))
            if spec is None:
                raise ValueError(f"{args.paper_id} has no seed spec")
            paper_dir = Path(args.record_root) / args.paper_id
            summary = summarize_stored(args.paper_id, paper_dir, spec, stored_seeds(paper_dir))
            print(json.dumps({k: summary[k] for k in ("paper_id", "successful_seed_runs", "metrics", "tier3", "tier3_by_metric")}, indent=2))
            return 0
        from scripts import preflight

        preflight.ensure_ready()
        spec = seed_spec_of(entry, load_seed_settings(Path(args.settings) if args.settings else None))
        if spec is None:
            print(f"{args.paper_id}: the paper offers no seed parameter that Repro Radar knows of "
                  "(no seed spec); it is not run.", file=sys.stderr)
            return 2
        seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else None
        if seeds is not None and len(seeds) < 2:
            raise ValueError("--seeds needs at least two seeds")
        summary = run_seeds(entry, spec, Path(args.record_root), Path(args.staging_dir), seeds=seeds,
                            data_cache=Path(args.data_cache), pilot3=args.pilot3, memory_limit=args.memory,
                            cpus=args.cpus, run_timeout=args.run_timeout)
    except Exception as exc:  # noqa: BLE001 - harness error: not run as specified; reported, exit 1
        print(f"HARNESS ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: summary[k] for k in ("paper_id", "successful_seed_runs", "metrics", "tier3")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
