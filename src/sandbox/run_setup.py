"""Per-paper run setup from `data/seed_papers.json` (#166).

The first pilot showed that several papers cannot run from the repository root with `python <target_script>`.
A paper's `run_setup` records the owner's decision (fix or report as it is), why, and the sandbox options the
fix needs:

- `command`: replaces `python /workspace/repo/<target_script> <args>` (for an entry point that is not a script)
- `args`, `env`: script arguments and environment variables
- `working_dir`: relative to the repository root (the README runs `cd results/ && python ...`)
- `writable_repo`: run on a writable per-run copy (the paper writes next to its own files)
- `data`: datasets fetched on the host into the data cache (`scripts/fetch_data.py`) and mounted read-only,
  because the sandbox has no network; `"writable": true` mounts a per-run copy instead (#193)
- `build`: sdists (`name==version`) and/or the repository itself (`from_repo`) built into wheels in the sandbox's
  build phase, with `build_requirements` as binary wheels (#193)
- `extra_requirements`: installed with the repository's requirements, for an entry point they do not cover
- `constraints`: pip constraints for versions the repository leaves open, with `constraints_source` saying how
  they were chosen
- `seed`: the paper's own seed parameter, so that it can be run once per seed (docs/MULTI_SEED.md)
- `open_items`: what the fix still needs and was not done; a paper with open items is not ready to run

The setup is what Repro Radar will run in Pilot 2 (#171); none of it is a result about the paper.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

DECISIONS = ("fix", "report_as_is")
DATA_KINDS = ("url", "openml")
UNPACK_FORMATS = ("tar", "zip", "none")


def run_setup_of(entry: dict[str, Any]) -> dict[str, Any]:
    """The paper's run setup; raises ValueError when it is missing or malformed."""
    setup = entry.get("run_setup")
    if not isinstance(setup, dict):
        raise ValueError(f"{entry.get('paper_id')}: no run_setup")  # noqa: TRY004 - a data error, like the checks below
    if setup.get("decision") not in DECISIONS:
        raise ValueError(f"{entry['paper_id']}: decision must be one of {DECISIONS}")
    if not setup.get("reason"):
        raise ValueError(f"{entry['paper_id']}: a decision needs a reason")
    for item in setup.get("data", []):
        if item.get("kind") not in DATA_KINDS:
            raise ValueError(f"{entry['paper_id']}: data kind must be one of {DATA_KINDS}: {item}")
        if not item.get("name") or not item.get("target"):
            raise ValueError(f"{entry['paper_id']}: data item needs a name and a target: {item}")
        if item["kind"] == "url" and (not item.get("url") or item.get("unpack") not in UNPACK_FORMATS):
            raise ValueError(f"{entry['paper_id']}: url data needs a url and unpack in {UNPACK_FORMATS}: {item}")
        if item["kind"] == "openml" and not openml_ids(item):
            raise ValueError(f"{entry['paper_id']}: openml data needs integer dataset_ids: {item}")
    build = setup.get("build")
    if build is not None and (not isinstance(build, dict) or not (build.get("sdists") or build.get("from_repo"))):
        raise ValueError(f"{entry['paper_id']}: build needs sdists or from_repo: {build}")
    if setup.get("seed") is not None:
        from src.multi_seed import (
            validate_seed_spec,  # imported here: src.multi_seed imports the scorer
        )

        validate_seed_spec(entry["paper_id"], setup["seed"])
    if setup.get("constraints") and not setup.get("constraints_source"):
        raise ValueError(f"{entry['paper_id']}: constraints need a constraints_source")
    return setup


def openml_ids(item: dict[str, Any]) -> list[int]:
    """Dataset IDs of an openml data item (`dataset_ids`, or a single `dataset_id`); [] if malformed."""
    ids = item.get("dataset_ids", [item["dataset_id"]] if "dataset_id" in item else [])
    return ids if ids and all(isinstance(i, int) and not isinstance(i, bool) for i in ids) else []


def data_dir(cache_root: Path, paper_id: str, item: dict[str, Any]) -> Path:
    """Host directory of one data item in the cache."""
    return Path(cache_root) / paper_id / item["name"]


def mount_source(cache_root: Path, paper_id: str, item: dict[str, Any]) -> Path:
    """The cached directory that is mounted (`path_in_archive` selects a folder of the unpacked archive)."""
    base = data_dir(cache_root, paper_id, item)
    return base / item["path_in_archive"] if item.get("path_in_archive") else base


def is_cached(cache_root: Path, paper_id: str, item: dict[str, Any]) -> bool:
    return (data_dir(cache_root, paper_id, item) / ".complete").exists()


def sandbox_options(entry: dict[str, Any], cache_root: Path) -> dict[str, Any]:
    """SandboxConfig and run options of a paper. Raises ValueError when cached data is missing."""
    setup = run_setup_of(entry)
    missing = [item["name"] for item in setup.get("data", []) if not is_cached(cache_root, entry["paper_id"], item)]
    if missing:
        raise ValueError(f"{entry['paper_id']}: data not in the cache, run scripts/fetch_data.py first: {missing}")
    return {
        "command": setup.get("command"),
        "script_args": list(setup.get("args", [])),
        "env_vars": dict(setup.get("env", {})),
        "working_dir": setup.get("working_dir", ""),
        "writable_repo": bool(setup.get("writable_repo", False)),
        "data_mounts": {
            item["target"]: str(mount_source(cache_root, entry["paper_id"], item)) for item in setup.get("data", [])
        },
        "writable_data": [item["target"] for item in setup.get("data", []) if item.get("writable")],
        "extra_requirements": list(setup.get("extra_requirements", [])),
        "constraints": list(setup.get("constraints", [])),
        "build": setup.get("build"),
    }
