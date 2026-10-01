#!/usr/bin/env python3
"""Run one seed paper of the Week 2 pilot exactly as docs/PILOT_WEEK2.md specifies (P2, #123).

Stages the paper's repository at its pinned commit, bundles binary wheels on the host (no package code runs),
then runs the install and run phases in the Docker sandbox with the protocol's limits. Writes
`pilot_record.json` next to the sandbox's `run_report.json` in `sandbox_runs/<paper_id>/`.

Exit codes: 0 when the paper went through the pipeline, whatever the paper's own result (staging, install, and run
failures are pilot results and are recorded); 1 on a harness error (for example Docker unavailable), so a failed
CI job always means Repro Radar did not run the paper as specified.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import SANDBOX_RUNS_DIR, SEED_PAPERS_PATH
from src.sandbox.runner import SandboxConfig
from src.sandbox.stager import RepoStager

# docs/PILOT_WEEK2.md section 4: script arguments and environment per paper (frozen with the protocol).
PILOT_SPECS: dict[str, dict[str, Any]] = {
    "paper_002": {"args": [], "env": {}},
    "paper_003": {
        "args": ["output/california_housing/ft_transformer/default/0.toml", "-o", "/workspace/output/ft_transformer_default_0"],
        "env": {"PROJECT_DIR": "/workspace/repo", "CUDA_VISIBLE_DEVICES": ""},
    },
    "paper_004": {"args": ["exp/tabr/california/0-evaluation/0.toml", "--force"], "env": {"CUDA_VISIBLE_DEVICES": ""}},
    "paper_005": {"args": [], "env": {}},
    "paper_006": {
        "args": ["--dset_id", "1461", "--task", "binary", "--savemodelroot", "/workspace/output/bestmodels"],
        "env": {},
    },
    "paper_008": {"args": ["-c", "config/forest_cover_type.yaml", "-g", ""], "env": {}},
}

# docs/PILOT_WEEK2.md section 3: limits for every paper.
PILOT_LIMITS: dict[str, Any] = {
    "cpus": 2.0,
    "memory_limit": "6g",
    "memory_swap": "6g",
    "pids_limit": 100,
    "timeout_seconds": 3600,
}

# Host-side `pip download` (binary wheels only). Not a protocol limit: large wheels such as PyTorch take
# longer than the stager's 180 s default, and a slow download is not a result about the paper.
BUNDLE_TIMEOUT_SECONDS = 1800


def load_entry(paper_id: str) -> dict[str, Any]:
    entries = json.loads(SEED_PAPERS_PATH.read_text(encoding="utf-8"))
    for entry in entries:
        if entry["paper_id"] == paper_id:
            return entry
    raise KeyError(f"{paper_id} is not in {SEED_PAPERS_PATH.name}")


def container_command(paper_id: str, target_script: str) -> str:
    """The command as written in the protocol table (an empty argument is shown as "")."""
    parts: list[str] = ["python", f"/workspace/repo/{target_script}", *PILOT_SPECS[paper_id]["args"]]
    return " ".join('""' if part == "" else part for part in parts)


def repro_radar_commit() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_root, capture_output=True, text=True, timeout=10, check=False)
        return res.stdout.strip() or "unknown"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def write_record(record: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "pilot_record.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def run_paper(paper_id: str, staging_dir: Path, stager: RepoStager | None = None) -> dict[str, Any]:
    entry = load_entry(paper_id)
    spec = PILOT_SPECS[paper_id]
    out_dir = SANDBOX_RUNS_DIR / paper_id
    stager = stager or RepoStager(staging_root=staging_dir)
    record: dict[str, Any] = {
        "paper_id": paper_id,
        "protocol": "docs/PILOT_WEEK2.md",
        "repro_radar_commit": repro_radar_commit(),
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "repo_url": entry["repo_url"],
        "pinned_commit": entry["repo_commit"],
        "target_script": entry["target_script"],
        "container_command": container_command(paper_id, entry["target_script"]),
        "environment": spec["env"],
        "limits": PILOT_LIMITS,
    }

    start = time.time()
    try:
        staged = stager.stage_repository(paper_id=paper_id, source=entry["repo_url"], commit_or_tag=entry["repo_commit"])
    except Exception as exc:  # noqa: BLE001 - a failed clone or checkout is a pilot result, recorded and categorized in P4
        record["stage"] = {"status": "FAILED", "error": str(exc), "duration_seconds": round(time.time() - start, 3)}
        write_record(record, out_dir)
        return record
    record["stage"] = {
        "status": "STAGED",
        "checked_out_commit": staged.commit_hash,
        "matches_pinned_commit": staged.commit_hash == entry["repo_commit"],
        "target_script_exists": (staged.staged_path / entry["target_script"]).is_file(),
        "requirements_files": staged.manifest.requirements_files,
        "has_conda_env": staged.manifest.has_conda_env,
        "duration_seconds": round(time.time() - start, 3),
    }

    start = time.time()
    bundle = stager.bundle_dependencies(staged, timeout=BUNDLE_TIMEOUT_SECONDS)
    record["bundle"] = {**bundle, "duration_seconds": round(time.time() - start, 3)}

    start = time.time()
    config = SandboxConfig(**PILOT_LIMITS, env_vars=dict(spec["env"]))
    report = stager.execute_staged(staged, target_script=entry["target_script"], script_args=list(spec["args"]), config=config)
    record["sandbox_duration_seconds"] = round(time.time() - start, 3)
    record["run_report"] = "run_report.json"
    record["run"] = {
        key: report.get(key)
        for key in ("status", "exit_code", "duration_seconds", "docker_used", "isolated", "dependency_install_status")
    }
    # Written by the container entrypoint from the cgroup (null when the kernel does not expose it).
    record["run"]["peak_memory_bytes"] = (report.get("meta") or {}).get("peak_memory_bytes")
    install_meta = out_dir / "install_meta.json"
    if install_meta.exists():
        record["install_meta"] = json.loads(install_meta.read_text(encoding="utf-8"))
    record["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    write_record(record, out_dir)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one pilot paper as specified in docs/PILOT_WEEK2.md.")
    parser.add_argument("paper_id", choices=sorted(PILOT_SPECS))
    parser.add_argument("--staging-dir", default=".sandbox_staging", help="Where repositories are cloned.")
    args = parser.parse_args(argv)
    try:
        record = run_paper(args.paper_id, Path(args.staging_dir))
    except Exception as exc:  # noqa: BLE001 - harness error: the paper was not run as specified; reported, exit 1
        print(f"HARNESS ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
