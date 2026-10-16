#!/usr/bin/env python3
"""Run one seed paper of the Week 2 pilot exactly as docs/PILOT_WEEK2.md specifies (P2, #123).

Stages the paper's repository at its pinned commit, bundles binary wheels on the host (no package code runs),
then runs the install and run phases in the Docker sandbox with the protocol's limits. Writes
`pilot_record.json` next to the sandbox's `run_report.json` in `sandbox_runs/<paper_id>/`.

Pilot 1's mode (the default) runs the frozen commands of docs/PILOT_WEEK2.md. `--pilot2` runs the paper with its
`run_setup` from data/seed_papers.json instead (docs/PILOT_2.md; #205): build phase, bundling with extras and
constraints, working directory, writable copy, data mounts, and command. The data must already be in the cache
(`scripts/fetch_data.py`).

`--pilot3` is Pilot 2 with the four changes of docs/PILOT_3.md, read from `data/pilot3_settings.json` (an overlay: the
run setups of data/seed_papers.json are not edited); its files land in `data/pilot3_runs/<paper_id>/` (#287).

Pilot 2's files land in `data/pilot2_runs/<paper_id>/`, not `sandbox_runs/<paper_id>/` (docs/PILOT_2.md section 6;
#207): the sandbox and stager still write under `sandbox_runs/` (shared with Pilot 1 and real-Docker CI, left
untouched), and `_collect_pilot2_files` copies the protocol's named files from there afterwards, next to
`pilot_record.json`, which is written directly into `data/pilot2_runs/<paper_id>/` for this mode.

`--memory 50%` replaces the memory limit (a size or a share of the host's RAM; the record says `memory_override`) and
`--record-root data/memory_runs` moves the record, so a run with another memory limit does not land among the protocol
runs (#319). Together with `--pilot3` they re-run Pilot 3's settings with only the memory limit changed.

Exit codes: 0 when the paper went through the pipeline, whatever the paper's own result (staging, install, and run
failures are pilot results and are recorded); 1 on a harness error (for example Docker unavailable), so a failed
CI job always means Repro Radar did not run the paper as specified.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import DATA_CACHE_DIR, PROJECT_ROOT, SANDBOX_RUNS_DIR, SEED_PAPERS_PATH
from src.sandbox.resources import resolve_memory_limit
from src.sandbox.run_setup import run_setup_of, sandbox_options
from src.sandbox.runner import DEFAULT_PYTHON_VERSION, SandboxConfig
from src.sandbox.stager import RepoStager, remove_tree

# docs/PILOT_2.md section 6: where a Pilot 2 run's files are collected (#207). The sandbox and stager are
# shared with Pilot 1 and real-Docker CI and are not changed to write here directly.
PILOT2_RUNS_DIR = PROJECT_ROOT / "data" / "pilot2_runs"
PILOT3_RUNS_DIR = PROJECT_ROOT / "data" / "pilot3_runs"
PILOT3_SETTINGS_PATH = PROJECT_ROOT / "data" / "pilot3_settings.json"

# What a Pilot 3 overlay entry may contain (docs/PILOT_3.md section 2): limits that replace Pilot 2's, and two changes of
# the run setup. `reason` and `pilot2_evidence` are documentation. Anything else is a typo and an error.
PILOT3_LIMIT_KEYS = ("memory_limit", "memory_swap", "timeout_seconds", "run_timeout_seconds")
PILOT3_KEYS = (*PILOT3_LIMIT_KEYS, "extra_requirements_add", "data_writable", "reason", "pilot2_evidence")

# Files docs/PILOT_2.md section 6 names, other than pilot_record.json (written directly into the target
# directory, not copied). "build.log" comes from the build phase's own output directory; the rest from the
# run/install phases' output directory.
_PILOT2_RUN_FILES = ("run_report.json", "execution_meta.json", "install.log", "install_meta.json",
                     "stdout.log", "stderr.log")
_PILOT2_BUILD_FILES = ("build.log",)

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


def load_pilot3_change(paper_id: str, settings_path: Path | None = None) -> dict[str, Any]:
    """The Pilot 3 change of one paper from the overlay file; {} for a paper that runs as in Pilot 2."""
    path = settings_path or PILOT3_SETTINGS_PATH
    papers = json.loads(path.read_text(encoding="utf-8"))["papers"]
    change = papers.get(paper_id, {})
    unknown = sorted(set(change) - set(PILOT3_KEYS))
    if unknown:
        raise ValueError(f"{paper_id}: unknown keys in {path.name}: {unknown}")
    if change and not (change.get("reason") and change.get("pilot2_evidence")):
        raise ValueError(f"{paper_id}: a Pilot 3 change needs a reason and the Pilot 2 evidence")
    return change


def apply_pilot3_change(entry: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
    """A copy of the seed entry with the run-setup changes of the overlay; the entry itself is not modified."""
    result = copy.deepcopy(entry)
    setup = result["run_setup"]
    for name in change.get("data_writable", []):
        items = [item for item in setup.get("data", []) if item["name"] == name]
        if not items:
            raise ValueError(f"{entry['paper_id']}: data_writable names {name!r}, which is not a data item of its run setup")
        items[0]["writable"] = True
    for requirement in change.get("extra_requirements_add", []):
        extras = setup.setdefault("extra_requirements", [])
        if requirement not in extras:
            extras.append(requirement)
    return result


def container_command(paper_id: str, target_script: str) -> str:
    """The command as written in the protocol table (an empty argument is shown as "")."""
    parts: list[str] = ["python", f"/workspace/repo/{target_script}", *PILOT_SPECS[paper_id]["args"]]
    return " ".join('""' if part == "" else part for part in parts)


def container_command_for(target_script: str, args: list[str]) -> str:
    parts = ["python", f"/workspace/repo/{target_script}", *args]
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


def _collect_pilot2_files(sandbox_dir: Path, build_dir: Path, target_dir: Path) -> list[str]:
    """Copy the protocol's named files (docs/PILOT_2.md section 6) into `target_dir`, next to where
    `pilot_record.json` is written for this run. A file that does not exist yet (no build happened, or the
    run never reached the install/run phase) is skipped, not an error. Returns the names actually copied."""
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in _PILOT2_BUILD_FILES:
        source = build_dir / name
        if source.is_file():
            shutil.copy2(source, target_dir / name)
            copied.append(name)
    for name in _PILOT2_RUN_FILES:
        source = sandbox_dir / name
        if source.is_file():
            shutil.copy2(source, target_dir / name)
            copied.append(name)
    return copied


def run_paper(paper_id: str, staging_dir: Path, stager: RepoStager | None = None, pilot2: bool = False,
              data_cache: Path | None = None, record_root: Path | None = None, pilot3: bool = False,
              settings_path: Path | None = None, memory_limit: str | None = None) -> dict[str, Any]:
    entry = load_entry(paper_id)
    pilot3_change: dict[str, Any] = {}
    limits = dict(PILOT_LIMITS)
    if pilot3:
        pilot2 = True  # Pilot 3 is Pilot 2 with the overlay
        pilot3_change = load_pilot3_change(paper_id, settings_path)
        entry = apply_pilot3_change(entry, pilot3_change)
        limits.update({k: pilot3_change[k] for k in PILOT3_LIMIT_KEYS if k in pilot3_change})
    memory_override: dict[str, Any] = {}
    if memory_limit:
        # Not a protocol run: the limit replaces the protocol's (cli.py score uses this, #311). The size that a
        # percentage resolves to is recorded, so the record says what the container really got.
        resolved = resolve_memory_limit(memory_limit)
        memory_override = {"requested": memory_limit, "resolved": resolved,
                           "protocol_memory_limit": limits["memory_limit"]}
        limits.update({"memory_limit": resolved, "memory_swap": resolved})
    setup_options: dict[str, Any] | None = None
    if pilot2:
        # Harness error (raised, exit 1) when the setup is malformed or its data is not in the cache
        setup_options = sandbox_options(entry, data_cache or DATA_CACHE_DIR)
        spec = {"args": setup_options["script_args"], "env": setup_options["env_vars"]}
    else:
        spec = PILOT_SPECS[paper_id]
    # The sandbox and stager always write here (shared with Pilot 1 and real-Docker CI). For Pilot 2, the
    # pilot record and the protocol's named files are additionally collected into `record_dir` below (#207).
    sandbox_dir = SANDBOX_RUNS_DIR / paper_id
    build_dir = SANDBOX_RUNS_DIR / f"{paper_id}.build"
    default_root = PILOT3_RUNS_DIR if pilot3 else PILOT2_RUNS_DIR
    record_dir = (record_root or default_root) / paper_id if pilot2 else sandbox_dir
    if pilot2:
        # An earlier attempt is evidence (docs/PILOT_2.md section 9) and is never overwritten (#217); and the
        # sandbox directories are cleared so that collected files can only come from this run.
        if record_dir.exists() and any(record_dir.iterdir()):
            raise FileExistsError(
                f"{record_dir} already holds an earlier attempt; move it to {record_dir.parent / 'first_attempts'} "
                "(kept as evidence) before running again")
        for stale in (sandbox_dir, build_dir):
            if stale.exists():
                remove_tree(stale)
    # Pilot 2 bundles inside the paper's sandbox image, so pip evaluates markers for Linux and the paper's Python (#215)
    stager = stager or RepoStager(staging_root=staging_dir, bundle_in_docker=pilot2)
    record: dict[str, Any] = {
        "paper_id": paper_id,
        "protocol": "docs/PILOT_3.md" if pilot3 else "docs/PILOT_2.md" if pilot2 else "docs/PILOT_WEEK2.md",
        "repro_radar_commit": repro_radar_commit(),
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "repo_url": entry["repo_url"],
        "pinned_commit": entry["repo_commit"],
        "target_script": entry["target_script"],
        "container_command": (" ".join(setup_options["command"]) if setup_options and setup_options["command"]
                              else container_command_for(entry["target_script"], spec["args"])),
        "environment": spec["env"],
        "limits": limits,
    }
    if pilot3:
        record["pilot3_change"] = pilot3_change
    if memory_override:
        record["memory_override"] = memory_override

    start = time.time()
    try:
        staged = stager.stage_repository(paper_id=paper_id, source=entry["repo_url"], commit_or_tag=entry["repo_commit"])
    except Exception as exc:  # noqa: BLE001 - a failed clone or checkout is a pilot result, recorded and categorized in P4
        record["stage"] = {"status": "FAILED", "error": str(exc), "duration_seconds": round(time.time() - start, 3)}
        if pilot2:
            record["collected_files"] = _collect_pilot2_files(sandbox_dir, build_dir, record_dir)
        write_record(record, record_dir)
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
    # Python version of the paper's sandbox image (data/seed_papers.json, #158; 3.11 when not set)
    python_version = entry.get("python_version", DEFAULT_PYTHON_VERSION)
    record["python_version"] = python_version
    config_extra: dict[str, Any] = {}
    bundle_extra: dict[str, Any] = {}
    command = None
    if setup_options:
        record["run_setup"] = {k: setup_options[k] for k in
                               ("command", "working_dir", "writable_repo", "extra_requirements", "constraints", "build")}
        record["run_setup"]["decision"] = run_setup_of(entry)["decision"]
        record["run_setup"]["data_mounts"] = sorted(setup_options["data_mounts"])
        config_extra = {k: setup_options[k] for k in
                        ("working_dir", "writable_repo", "data_mounts", "writable_data", "extra_requirements")}
        bundle_extra = {"extra_requirements": setup_options["extra_requirements"],
                        "constraints": setup_options["constraints"]}
        command = setup_options["command"]
    config = SandboxConfig(**limits, env_vars=dict(spec["env"]), python_version=python_version, **config_extra)

    if setup_options and setup_options["build"]:
        build_start = time.time()
        build = stager.build_from_source(staged, setup_options["build"], config)
        record["build"] = {k: v for k, v in build.items() if k != "command_executed"}
        record["build"]["duration_seconds_total"] = round(time.time() - build_start, 3)
        if build.get("status") != "BUILT":
            # Protocol section 5: a failed build counts as a failed install; the run is not started
            record["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            record["collected_files"] = _collect_pilot2_files(sandbox_dir, build_dir, record_dir)
            write_record(record, record_dir)
            return record

    start = time.time()
    bundle = stager.bundle_dependencies(staged, timeout=BUNDLE_TIMEOUT_SECONDS, python_version=python_version,
                                        **bundle_extra)
    record["bundle"] = {**bundle, "duration_seconds": round(time.time() - start, 3)}

    start = time.time()
    run_kwargs = {"command": command} if command else {}
    report = stager.execute_staged(staged, target_script=entry["target_script"], script_args=list(spec["args"]),
                                   config=config, **run_kwargs)
    record["sandbox_duration_seconds"] = round(time.time() - start, 3)
    record["run_report"] = "run_report.json"
    record["run"] = {
        key: report.get(key)
        for key in ("status", "exit_code", "duration_seconds", "docker_used", "isolated", "dependency_install_status")
    }
    # Written by the container entrypoint from the cgroup (null when the kernel does not expose it).
    record["run"]["peak_memory_bytes"] = (report.get("meta") or {}).get("peak_memory_bytes")
    install_meta = sandbox_dir / "install_meta.json"
    if install_meta.exists():
        record["install_meta"] = json.loads(install_meta.read_text(encoding="utf-8"))
    record["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    if pilot2:
        record["collected_files"] = _collect_pilot2_files(sandbox_dir, build_dir, record_dir)
    write_record(record, record_dir)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one pilot paper as specified in docs/PILOT_WEEK2.md.")
    parser.add_argument("paper_id", choices=sorted(PILOT_SPECS))
    parser.add_argument("--staging-dir", default=".sandbox_staging", help="Where repositories are cloned.")
    parser.add_argument("--pilot2", action="store_true", help="Run with the paper's run_setup (docs/PILOT_2.md).")
    parser.add_argument("--pilot3", action="store_true",
                        help="Pilot 2 plus the four changes of docs/PILOT_3.md (data/pilot3_settings.json); "
                             "files go to data/pilot3_runs/.")
    parser.add_argument("--data-cache", default=str(DATA_CACHE_DIR), help="Host data cache (scripts/fetch_data.py).")
    parser.add_argument("--memory", default=None, metavar="LIMIT",
                        help="Replace the memory limit (and the swap limit) with a size such as 8g or a share of the "
                             "host's RAM such as 50%%; the record gets `memory_override`. Not a protocol run (#319).")
    parser.add_argument("--record-root", default=None, metavar="DIR",
                        help="Write the record and the collected files to DIR/<paper_id>/ instead of "
                             "data/pilot2_runs/ or data/pilot3_runs/ (needs --pilot2 or --pilot3), for example "
                             "data/memory_runs.")
    args = parser.parse_args(argv)
    if args.record_root and not (args.pilot2 or args.pilot3):
        parser.error("--record-root needs --pilot2 or --pilot3 (Pilot 1 records stay in sandbox_runs/)")
    try:
        record = run_paper(args.paper_id, Path(args.staging_dir), pilot2=args.pilot2, data_cache=Path(args.data_cache),
                           pilot3=args.pilot3, memory_limit=args.memory,
                           record_root=Path(args.record_root) if args.record_root else None)
    except Exception as exc:  # noqa: BLE001 - harness error: the paper was not run as specified; reported, exit 1
        print(f"HARNESS ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
