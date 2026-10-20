#!/usr/bin/env python3
"""Two synthetic papers for multi-seed execution: one metric ignores the seed, one comes from `random.Random(seed)` (#48).

    python scripts/synthetic_seeds.py            # needs Docker; writes data/synthetic_seeds/

Two tiny git repositories without dependencies are made in a temporary directory. Each has a `train.py --seed N` that prints
one metric:

- `synthetic_seed_free`: `accuracy: 0.9000` whatever the seed;
- `synthetic_seeded`: `accuracy: <random.Random(seed).uniform(0.60, 0.95)>`, 4 decimals.

Both go through `scripts/run_multi_seed.py` (the real pipeline, real Docker) with 5 seeds. The expected mean and standard
deviation are computed on the host from the same seeds, without the sandbox, and compared with the summary of the runs. The
point is to show that the multi-seed path measures a difference that is known beforehand: Tier 3 must be 100 for the seed-free
paper and lower for the seeded one. It does not show that a real paper is stable; the two papers are not real.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.run_multi_seed import run_seeds
from scripts.synthetic_control import scrub_paths
from src.multi_seed import summarize_seed_runs

SEEDS = [1, 2, 3, 4, 5]
LOW, HIGH = 0.60, 0.95
OUT_DIR = project_root / "data" / "synthetic_seeds"
TOLERANCE = 1e-9  # the metric is printed with 4 decimals on both sides, so the values are the same numbers

PAPERS = {
    "synthetic_seed_free": {
        "train": ('"""Synthetic paper whose metric does not depend on the seed."""\n'
                  "import argparse\n\n"
                  "parser = argparse.ArgumentParser()\n"
                  "parser.add_argument('--seed', type=int, default=0)\n"
                  "parser.parse_args()\n"
                  "print('accuracy: 0.9000')\n"),
    },
    "synthetic_seeded": {
        "train": ('"""Synthetic paper whose metric is drawn from random.Random(seed)."""\n'
                  "import argparse\n"
                  "import random\n\n"
                  "parser = argparse.ArgumentParser()\n"
                  "parser.add_argument('--seed', type=int, default=0)\n"
                  "args = parser.parse_args()\n"
                  f"print(f'accuracy: {{random.Random(args.seed).uniform({LOW}, {HIGH}):.4f}}')\n"),
    },
}


def seeded_value(seed: int) -> float:
    """The metric of `synthetic_seeded` for one seed, as the script prints it (4 decimals)."""
    return float(f"{random.Random(seed).uniform(LOW, HIGH):.4f}")


def expected_metrics(paper_id: str, seeds: list[int]) -> dict[int, dict[str, float]]:
    """What each seed run must print, computed on the host without the sandbox."""
    if paper_id == "synthetic_seed_free":
        return {s: {"accuracy": 0.9} for s in seeds}
    return {s: {"accuracy": seeded_value(s)} for s in seeds}


def make_repository(root: Path, paper_id: str) -> tuple[Path, str]:
    repo = root / f"{paper_id}_repo"
    repo.mkdir(parents=True)
    (repo / "train.py").write_text(PAPERS[paper_id]["train"], encoding="utf-8", newline="\n")
    (repo / "README.md").write_text(f"# {paper_id}\n\nOne script that prints one metric. It tests multi-seed execution.\n",
                                    encoding="utf-8", newline="\n")
    env = ["-c", "user.name=synthetic", "-c", "user.email=synthetic@example.invalid"]
    for args in (["init", "-q", "-b", "main"], ["add", "."], [*env, "commit", "-q", "-m", f"{paper_id}"]):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True,
                            text=True).stdout.strip()
    return repo, commit


def entry_for(paper_id: str, repo: Path, commit: str) -> dict[str, Any]:
    return {
        "paper_id": paper_id, "title": paper_id, "repo_url": repo.as_posix(), "repo_commit": commit, "license": "MIT",
        "target_script": "train.py", "expected_claims": {"accuracy": 0.9},
        "run_setup": {"decision": "fix", "reason": "Synthetic paper: a script without dependencies that prints one metric."},
    }


def compare_with_expected(summary: dict[str, Any], paper_id: str, seeds: list[int]) -> dict[str, Any]:
    """The summary of the runs against the mean and standard deviation computed on the host."""
    expected = summarize_seed_runs(expected_metrics(paper_id, seeds))["accuracy"]
    measured = summary["metrics"]["accuracy"]
    fields = {}
    for key in ("mean", "std_population", "std_sample", "cv"):
        fields[key] = {"expected": expected[key], "measured": measured[key],
                       "match": math.isclose(expected[key], measured[key], rel_tol=0, abs_tol=TOLERANCE)}
    per_seed = {str(s): {"expected": v, "measured": next(r["metrics"].get("accuracy") for r in summary["runs"] if r["seed"] == s)}
                for s, v in zip(seeds, expected["values"], strict=True)}
    return {"fields": fields, "per_seed": per_seed,
            "per_seed_match": all(p["expected"] == p["measured"] for p in per_seed.values()),
            "all_match": all(f["match"] for f in fields.values()) and all(
                p["expected"] == p["measured"] for p in per_seed.values())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(OUT_DIR))
    parser.add_argument("--memory", default="50%")
    parser.add_argument("--cpus", type=float, default=4)
    args = parser.parse_args(argv)
    from scripts import preflight

    preflight.ensure_ready()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="synthetic_seeds_") as tmp:
        tmp_path = Path(tmp)
        for paper_id in PAPERS:
            repo, commit = make_repository(tmp_path, paper_id)
            spec = {"values": SEEDS, "arg": "--seed", "source": "scripts/synthetic_seeds.py: train.py --seed"}
            summary = run_seeds(entry_for(paper_id, repo, commit), spec, out, tmp_path / f"staging_{paper_id}",
                                memory_limit=args.memory, cpus=args.cpus)
            results[paper_id] = {"tier3": summary["tier3"], "successful_seed_runs": summary["successful_seed_runs"],
                                 "comparison": compare_with_expected(summary, paper_id, SEEDS)}
        scrub_paths(out, {tmp_path.resolve(): "<TMP>", tmp_path: "<TMP>", project_root: "<REPO>", Path.home(): "<HOME>"})
    t3 = {p: r["tier3"]["score"] for p, r in results.items()}
    result = {"seeds": SEEDS, "papers": results, "tier3_differs": t3["synthetic_seed_free"] != t3["synthetic_seeded"],
              "note": "synthetic papers; this shows that the multi-seed path measures a known difference, not that a real "
                      "paper is stable"}
    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if all(r["comparison"]["all_match"] for r in results.values()) and result["tier3_differs"] else 1


if __name__ == "__main__":
    sys.exit(main())
