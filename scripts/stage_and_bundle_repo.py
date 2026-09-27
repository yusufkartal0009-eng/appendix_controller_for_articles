#!/usr/bin/env python3
"""Automation script to clone/stage scientific repositories, bundle dependencies for

offline isolation, execute in the Docker sandbox, and output structured verification metrics.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

# Ensure project src is in sys.path when invoked directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.sandbox.runner import SandboxConfig, SandboxUnavailableError
from src.sandbox.stager import RepoStager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sandbox-stager")

EXIT_SANDBOX_UNAVAILABLE = 4
RED = "\033[91m"
RESET = "\033[0m"
UNSAFE_LOCAL_PRERUN_WARNING = (
    "WARNING: --allow-unsafe-local is set. If Docker is unavailable, the target code will run directly on "
    "this machine with your files and network, NOT ISOLATED. Use only for code you trust."
)
UNSAFE_LOCAL_WARNING = (
    "WARNING: NOT ISOLATED. Docker was unavailable and --allow-unsafe-local was set: the target code ran "
    "directly on this machine with your files and network. Use only for code you trust."
)


def sanitize_paper_id(source: str) -> str:
    """Derive a safe paper/repo identifier from the source URL or directory name."""
    clean = source.rstrip("/").rstrip("\\")
    name = Path(clean).stem
    if name.endswith(".git"):
        name = name[:-4]
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", name).lower()
    return sanitized or "staged_paper"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clone/stage a scientific appendix repo, bundle dependencies, and execute in secure sandbox."
    )
    parser.add_argument(
        "source",
        help="Git repository URL (GitHub/IEEE) or local directory path to stage.",
    )
    parser.add_argument(
        "--paper-id",
        dest="paper_id",
        default=None,
        help="Identifier for the paper/experiment run (default: inferred from source).",
    )
    parser.add_argument(
        "--commit",
        dest="commit",
        default=None,
        help="Specific git commit hash or tag to check out.",
    )
    parser.add_argument(
        "--script",
        dest="target_script",
        default=None,
        help="Script to execute inside the sandbox (default: auto-detected reproduce/main/eval script).",
    )
    parser.add_argument(
        "--script-args",
        nargs=argparse.REMAINDER,
        dest="script_args",
        default=[],
        help="Arguments to forward to the target script.",
    )
    parser.add_argument(
        "--bundle-deps",
        action="store_true",
        default=False,
        help="Pre-download dependency wheels for offline isolated container execution.",
    )
    parser.add_argument(
        "--no-run",
        dest="run_execution",
        action="store_false",
        default=True,
        help="Stage repository and dependencies without running execution.",
    )
    parser.add_argument(
        "--staging-dir",
        dest="staging_dir",
        default=None,
        help="Directory to store staged repositories (default: .sandbox_staging).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Execution timeout limit in seconds (default: 300).",
    )
    parser.add_argument(
        "--memory",
        default="8192M",
        help="Container memory limit (default: 8192M).",
    )
    parser.add_argument(
        "--cpus",
        default="2.0",
        help="Container CPU quota (default: 2.0).",
    )
    parser.add_argument(
        "--allow-unsafe-local",
        dest="allow_unsafe_local",
        action="store_true",
        default=False,
        help=(
            "If Docker is unavailable, run the target script directly on this machine WITHOUT isolation. "
            "Development only, and only for code you trust. The run report is marked isolated=false."
        ),
    )
    parser.add_argument(
        "--output-json",
        dest="output_json",
        default=None,
        help="Path to write the final JSON run report.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paper_id = args.paper_id or sanitize_paper_id(args.source)

    print("================================================================")
    print(f"Repro Radar - Sandbox Staging & Dependency Automation")
    print(f"Target:   {args.source}")
    print(f"Paper ID: {paper_id}")
    print("================================================================")

    stager = RepoStager(staging_root=args.staging_dir)

    # Step 1: Stage repository
    print(f"\n[STAGE 1/4] Staging repository from: {args.source}")
    try:
        staged = stager.stage_repository(
            paper_id=paper_id,
            source=args.source,
            commit_or_tag=args.commit,
        )
        print(f" -> Staged at:   {staged.staged_path}")
        print(f" -> Git commit:  {staged.commit_hash}")
    except Exception as exc:
        logger.error("Failed to stage repository: %s", exc)
        return 1

    # Step 2: Analyze dependencies & entrypoints
    print("\n[STAGE 2/4] Analyzing manifest files & entrypoints")
    print(f" -> Requirements files found: {staged.manifest.requirements_files or 'None'}")
    print(f" -> PyProject: {staged.manifest.has_pyproject} | Setup.py: {staged.manifest.has_setup_py}")
    print(f" -> Detected dependencies count: {len(staged.manifest.parsed_dependencies)}")
    print(f" -> Candidate scripts: {staged.candidate_scripts}")

    # Step 3: Bundle dependencies if requested
    if args.bundle_deps:
        print("\n[STAGE 3/4] Bundling dependency wheels for offline sandbox...")
        bundle_res = stager.bundle_dependencies(staged)
        print(f" -> Status: {bundle_res.get('status')}")
        print(f" -> Wheels downloaded: {bundle_res.get('wheel_count')}")
        print(f" -> Bundle directory: {bundle_res.get('bundle_dir')}")
        for entry in bundle_res.get("needs_sdist_build") or []:
            print(f" -> NEEDS_SDIST_BUILD: {entry['requirement']} ({entry['reason']})")
    else:
        print("\n[STAGE 3/4] Dependency pre-bundling skipped (run with --bundle-deps to bundle).")

    # Step 4: Execute inside sandbox
    if not args.run_execution:
        print("\n[STAGE 4/4] Execution skipped (--no-run was specified). Staging complete.")
        return 0

    print("\n[STAGE 4/4] Executing target script inside isolated sandbox...")
    chosen_script = args.target_script
    if not chosen_script:
        if staged.candidate_scripts:
            chosen_script = staged.candidate_scripts[0]
            print(f" -> Auto-selected entrypoint script: {chosen_script}")
        else:
            logger.error("No target script found or specified. Use --script to designate one.")
            return 2

    config = SandboxConfig(
        timeout_seconds=args.timeout,
        memory_limit=args.memory,
        cpus=args.cpus,
        allow_unsafe_local=args.allow_unsafe_local,
    )
    if args.allow_unsafe_local:
        print(f"{RED}{UNSAFE_LOCAL_PRERUN_WARNING}{RESET}", file=sys.stderr)

    try:
        report = stager.execute_staged(
            staged=staged,
            target_script=chosen_script,
            script_args=args.script_args,
            config=config,
        )
    except SandboxUnavailableError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_SANDBOX_UNAVAILABLE
    except Exception as exc:
        logger.error("Execution failed: %s", exc)
        return 3

    print("\n======================= EXECUTION SUMMARY =======================")
    print(f"Status:          {report.get('status')}")
    print(f"Exit Code:       {report.get('exit_code')}")
    print(f"Duration:        {report.get('duration_seconds')}s")
    print(f"Docker Used:     {report.get('docker_used')}")
    print(f"Isolated:        {report.get('isolated')}")
    if report.get("fallback_reason"):
        print(f"Fallback Reason: {report.get('fallback_reason')}")
    print(f"Output Dir:      {report.get('output_dir')}")
    print(f"Generated Files: {report.get('generated_files')}")
    if "metrics" in report:
        print(f"Metrics:         {json.dumps(report['metrics'], indent=2)}")
    print("=================================================================")
    if not report.get("isolated"):
        print(f"{RED}{UNSAFE_LOCAL_WARNING}{RESET}", file=sys.stderr)

    if args.output_json:
        out_path = Path(args.output_json).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Run report written to: {out_path}")

    return 0 if report.get("status") == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
