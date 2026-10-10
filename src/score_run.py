"""Score a paper from a real sandbox run and its accepted claims (GA-2, #136).

`cli.py score` used to invent reproduced numbers from the claimed ones. This module scores what really happened:

- Tier 1 inputs come from the pilot record and the run report (`pilot_record.json`, `run_report.json`): staging,
  the dependency install status, whether the run phase started, and its exit code.
- The claims are the ones a person accepted (`src/claim_review.py`, `claims_for_scoring`); no other claim is scored.
- The reproduced metrics are those the metric extractor found in the run's output (`run_report.json`: `metrics`).
  A claim is matched by its question ID, never guessed: a claim whose name does not occur in the output is reported
  as not found, and an unusable run (failed install, failed run) reproduces nothing.

Nothing here is simulated. The simulation flags of the CLI keep their own path and are labeled there.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.scoring import ReproducibilityScorer, Tier4ArtifactsEvaluator

RECORD_NAME = "pilot_record.json"
REPORT_NAME = "run_report.json"


def load_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """The pilot record and the run report of a stored run directory (the report may be missing)."""
    run_dir = Path(run_dir)
    record_path = run_dir / RECORD_NAME
    if not record_path.is_file():
        raise FileNotFoundError(f"{record_path} not found: not a run directory of run_pilot.py")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    report_path = run_dir / REPORT_NAME
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    return record, report


def run_facts(record: dict[str, Any], report: dict[str, Any], run_dir: Path, repo_dir: Path | None = None) -> dict[str, Any]:
    """The Tier 1 and Tier 4 facts of a run, each taken from the stored files. Nothing is assumed in the paper's favor."""
    stage = record.get("stage") or {}
    build = record.get("build")
    run = record.get("run")
    clone_success = stage.get("status") == "STAGED"
    # A failed build counts as a failed install (docs/PILOT_2.md section 5)
    build_ok = build is None or build.get("status") == "BUILT"
    deps_installed = bool(build_ok and run and report.get("dependency_install_status", run.get("dependency_install_status")) == "INSTALLED")
    has_env, has_readme, has_artifacts = Tier4ArtifactsEvaluator.detect_filesystem_artifacts(repo_dir=repo_dir, run_dir=run_dir)
    if repo_dir is None or not Path(repo_dir).is_dir():
        # The staged repository is not available: take the environment file from the record, README is unknown (False)
        has_env = bool(stage.get("requirements_files") or stage.get("has_conda_env"))
        has_readme = False
    metrics = {k: float(v) for k, v in (report.get("metrics") or {}).items() if isinstance(v, (int, float))}
    return {
        "clone_success": clone_success,
        "deps_installed": deps_installed,
        "script_executed": run is not None,
        "exit_code": run.get("exit_code") if run else None,
        "reproduced_metrics": metrics,
        "has_environment_file": has_env,
        "has_readme": has_readme,
        "has_saved_artifacts": has_artifacts,
    }


def score_run(paper_id: str, license_name: str, claims: dict[str, float], record: dict[str, Any],
              report: dict[str, Any], run_dir: Path, repo_dir: Path | None = None) -> dict[str, Any]:
    """Score one stored run. `claims` are the accepted claims only (question ID -> normalized value)."""
    facts = run_facts(record, report, run_dir, repo_dir)
    result = ReproducibilityScorer.evaluate_paper_run(
        paper_id=paper_id,
        claimed_metrics=claims,
        license_name=license_name,
        seed_results=None,  # one run per paper: multi-seed execution is not implemented (#48)
        **facts,
    )
    result["inputs"] = {**facts, "claims": dict(claims), "run_status": (record.get("run") or {}).get("status"),
                        "protocol": record.get("protocol"), "repro_radar_commit": record.get("repro_radar_commit")}
    if not claims:
        result["diagnostics"]["tier2_notes"].append(
            "No claim of this paper has been accepted by a person: the 70.0 of Tier 2 is the scorer's neutral "
            "baseline for 'no claims', not a measurement.")
    return result
