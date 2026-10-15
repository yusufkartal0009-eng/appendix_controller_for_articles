#!/usr/bin/env python3
"""Synthetic control paper: the real pipeline on a paper whose answer is known (#synthetic-control).

    python scripts/synthetic_control.py            # needs Docker; writes data/synthetic_control/

A tiny git repository without dependencies is made in a temporary directory. Its script prints a fixed metric
(`accuracy: 0.9000`). The paper goes through the same code as a real pilot paper (`scripts/run_pilot.py run_paper`:
staging, the Docker sandbox, metric extraction) twice with the same settings, and the two runs are compared with
`scripts/hash_run.py`. A true claim (0.9) and a deliberately false claim (0.5) are then scored with `src/score_run.py`.
The seed file is not touched: the entry exists only inside this script.

What it shows: the scoring path works on a real run (a true claim scores high, a false claim low) and a deterministic
run gives the same result twice. What it does not show: that real papers are stable (they train, download, and are
bounded by time and memory) or that a real paper's number is reproduced.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts import run_pilot
from src.score_run import load_run, score_run

PAPER_ID = "synthetic_control"
METRIC = "accuracy"
TRUE_VALUE = 0.9
FALSE_VALUE = 0.5
OUT_DIR = project_root / "data" / "synthetic_control"

TRAIN_PY = f'''"""Synthetic control: no dependencies, no randomness, no network."""
print("{METRIC}: {TRUE_VALUE:.4f}")
'''
README = "# Synthetic control paper\n\nOne script that prints a fixed metric. It exists to test the scoring path.\n"


def make_repository(root: Path) -> tuple[Path, str]:
    """A git repository with the synthetic script. Returns its path and its commit."""
    repo = root / "synthetic_control_repo"
    repo.mkdir(parents=True)
    (repo / "train.py").write_text(TRAIN_PY, encoding="utf-8", newline="\n")
    (repo / "README.md").write_text(README, encoding="utf-8", newline="\n")
    env = ["-c", "user.name=synthetic", "-c", "user.email=synthetic@example.invalid"]
    for args in (["init", "-q", "-b", "main"], ["add", "."], [*env, "commit", "-q", "-m", "synthetic control paper"]):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True,
                            text=True).stdout.strip()
    return repo, commit


def entry_for(repo: Path, commit: str) -> dict[str, Any]:
    return {
        "paper_id": PAPER_ID, "title": "Synthetic control paper", "repo_url": repo.as_posix(), "repo_commit": commit,
        "license": "MIT", "target_script": "train.py", "expected_claims": {METRIC: TRUE_VALUE},
        "run_setup": {"decision": "fix", "reason": "Synthetic control: a script without dependencies that prints a "
                                                   "fixed metric; no data, no network."},
    }


def run_once(entry: dict[str, Any], staging: Path, record_root: Path) -> Path:
    """One run of the synthetic paper through run_paper (Pilot 2 flow, real Docker)."""
    original = run_pilot.load_entry
    run_pilot.load_entry = lambda paper_id: entry if paper_id == PAPER_ID else original(paper_id)  # type: ignore[assignment]
    try:
        run_pilot.run_paper(PAPER_ID, staging, pilot2=True, record_root=record_root)
    finally:
        run_pilot.load_entry = original  # type: ignore[assignment]
    return record_root / PAPER_ID


def compare_runs(run_a: Path, run_b: Path) -> dict[str, Any]:
    """Status, exit code, metrics, and which files the two runs produced identically (src/artifact_hash.py)."""
    from src.artifact_hash import build_manifest, compare_manifests, summarize

    rec_a, rep_a = load_run(run_a)
    rec_b, rep_b = load_run(run_b)
    run_a_info, run_b_info = rec_a.get("run") or {}, rec_b.get("run") or {}
    same = {
        "run_status": run_a_info.get("status") == run_b_info.get("status"),
        "exit_code": run_a_info.get("exit_code") == run_b_info.get("exit_code"),
        "metrics": (rep_a.get("metrics") or {}) == (rep_b.get("metrics") or {}),
    }
    files = compare_manifests(build_manifest(run_a), build_manifest(run_b))
    return {"same": same, "status": run_a_info.get("status"), "exit_code": run_a_info.get("exit_code"),
            "metrics_a": rep_a.get("metrics"), "metrics_b": rep_b.get("metrics"),
            "files": files, "files_summary": summarize(files).splitlines()}


def score_claims(run_dir: Path, repo_dir: Path | None) -> dict[str, Any]:
    """Score the same stored run against a true and a false claim."""
    record, report = load_run(run_dir)
    out: dict[str, Any] = {}
    for label, value in (("true_claim", TRUE_VALUE), ("false_claim", FALSE_VALUE)):
        result = score_run(PAPER_ID, "MIT", {METRIC: value}, record, report, run_dir, repo_dir)
        b = result["breakdown"]
        out[label] = {"claimed": value, "reproduced": result["inputs"]["reproduced_metrics"],
                      "tier1_build": b.tier1_build, "tier2_metrics": b.tier2_metrics, "tier3_stability": b.tier3_stability,
                      "tier4_artifacts": b.tier4_artifacts, "total_score": b.total_score, "status_label": b.status_label,
                      "claim_details": result["claim_details"]}
    return out


def scrub_paths(directory: Path, replacements: dict[Path, str]) -> None:
    """Replace the machine's own paths (home directory, temporary directory, repository) in the text files, so that the
    stored evidence does not carry the user name or the temporary names. Both slash styles and JSON-escaped
    backslashes are replaced."""
    pairs: list[tuple[str, str]] = []
    for path, label in replacements.items():
        text = str(path)
        for variant in {text, text.replace("\\", "/"), text.replace("\\", "\\\\")}:
            pairs.append((variant, label))
    pairs.sort(key=lambda pair: -len(pair[0]))  # the longest path first
    for file in directory.rglob("*"):
        if file.is_file() and file.suffix in {".json", ".log", ".txt", ".md"}:
            body = file.read_text(encoding="utf-8", errors="replace")
            new = body
            for variant, label in pairs:
                new = new.replace(variant, label)
            if new != body:
                file.write_text(new, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(OUT_DIR))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="synthetic_control_") as tmp:
        tmp_path = Path(tmp)
        repo, commit = make_repository(tmp_path)
        entry = entry_for(repo, commit)
        runs = []
        for n in (1, 2):
            staging = tmp_path / f"staging_{n}"
            runs.append(run_once(entry, staging, out / f"run{n}"))
        comparison = compare_runs(*runs)
        scores = score_claims(runs[0], tmp_path / "staging_1" / PAPER_ID)
        scrub_paths(out, {tmp_path.resolve(): "<TMP>", tmp_path: "<TMP>", project_root: "<REPO>", Path.home(): "<HOME>"})
    result = {"paper_id": PAPER_ID, "metric": METRIC, "comparison": comparison, "scores": scores}
    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
