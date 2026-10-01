"""CLI Utility for Repro Radar."""

import argparse
import os
import sys
import uuid

from tabulate import tabulate

# Ensure UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.config import DATA_DIR, PROJECT_ROOT, SANDBOX_RUNS_DIR, SANDBOX_TEMP_DIR
from src.database import (
    get_all_papers,
    get_paper_by_id,
    init_db,
    save_score,
    seed_database,
)
from src.scoring import ReproducibilityScorer, Tier4ArtifactsEvaluator


def cmd_init_db(args):
    """Initialize database and seed target papers."""
    print("==================================================")
    print("Repro Radar - Database Initialization & Seeding")
    print("==================================================")
    init_db(drop_existing=args.reset)
    print("SQLite database schema initialized from data/schema.sql.")
    count = seed_database(overwrite=True)
    print(f"Successfully seeded {count} papers from data/seed_papers.json.")


def cmd_list_papers(args):
    """List all papers currently in the database."""
    papers = get_all_papers()
    if not papers:
        print("No papers found in the database. Run 'python cli.py init-db' first.")
        return

    table_data = []
    for p in papers:
        claims_count = len(p.get_expected_claims_dict())
        table_data.append([
            p.paper_id,
            p.title[:45] + ("..." if len(p.title) > 45 else ""),
            p.year,
            p.venue,
            p.license,
            p.target_script,
            claims_count,
        ])

    headers = ["Paper ID", "Title", "Year", "Venue", "License", "Script", "Claims"]
    print("\nCurated Papers in Repro Radar:")
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print(f"Total Papers: {len(papers)}\n")


def cmd_inspect_paper(args):
    """Inspect metadata and claims of a specific paper."""
    paper = get_paper_by_id(args.paper_id)
    if not paper:
        print(f"Paper with ID '{args.paper_id}' not found.")
        sys.exit(1)

    claims = paper.get_expected_claims_dict()
    print("==================================================")
    print(f"Paper Details: {paper.paper_id}")
    print("==================================================")
    print(f"Title        : {paper.title}")
    print(f"Year / Venue : {paper.year} ({paper.venue})")
    print(f"Repository   : {paper.repo_url}")
    print(f"Paper URL    : {paper.paper_url or 'N/A'}")
    print(f"License      : {paper.license}")
    print(f"Target Script: {paper.target_script}")
    print("\nExpected Numerical Claims:")
    for k, v in claims.items():
        print(f"  • {k}: {v}")
    print("==================================================")


def cmd_score_paper(args):
    """Simulate execution output and calculate 4-tier reproducibility score."""
    paper = get_paper_by_id(args.paper_id)
    if not paper:
        print(f"Paper with ID '{args.paper_id}' not found.")
        sys.exit(1)

    expected_claims = paper.get_expected_claims_dict()
    print(f"\nEvaluating reproducibility for: [{paper.paper_id}] {paper.title}")

    # Simulated realistic output matching expected claims closely (reproduced within ~1-3% error)
    simulated_reproduced = {}
    for metric, val in expected_claims.items():
        if args.simulate_failure:
            # Simulate high error
            simulated_reproduced[metric] = round(val * 0.65, 4)
        elif args.simulate_divergence:
            # Simulate partial match
            simulated_reproduced[metric] = round(val * 1.08, 4)
        else:
            # High fidelity match within 1.5%
            simulated_reproduced[metric] = round(val * 1.012, 4)

    exit_code = 1 if args.simulate_build_error else 0
    clone_success = not args.simulate_clone_error
    deps_installed = not args.simulate_deps_error
    script_executed = (exit_code == 0 or args.simulate_divergence or args.simulate_failure)
    execution_succeeded = bool(
        exit_code == 0 and script_executed and clone_success and deps_installed
    )

    # Dynamically detect environment file, README, and artifacts via filesystem checks (os.path.exists)
    target_repo_dir = SANDBOX_TEMP_DIR / paper.paper_id
    target_run_dir = SANDBOX_RUNS_DIR / paper.paper_id

    if target_repo_dir.exists():
        has_environment_file, has_readme, has_saved_artifacts = (
            Tier4ArtifactsEvaluator.detect_filesystem_artifacts(
                repo_dir=target_repo_dir,
                run_dir=target_run_dir,
            )
        )
    else:
        # Dynamic filesystem fallback for Week 1 simulated mode: check repository root files
        has_environment_file = os.path.exists(PROJECT_ROOT / "requirements.txt") or os.path.exists(PROJECT_ROOT / "pyproject.toml")
        has_readme = os.path.exists(PROJECT_ROOT / "README.md")
        has_saved_artifacts = execution_succeeded and os.path.exists(DATA_DIR / "seed_papers.json")

    # If simulation flags specify clone or execution failure, reflect dynamically
    if not clone_success:
        has_environment_file = False
        has_readme = False
        has_saved_artifacts = False
    elif not execution_succeeded:
        has_saved_artifacts = False

    eval_result = ReproducibilityScorer.evaluate_paper_run(
        paper_id=paper.paper_id,
        clone_success=clone_success,
        deps_installed=deps_installed,
        script_executed=script_executed,
        exit_code=exit_code,
        claimed_metrics=expected_claims,
        reproduced_metrics=simulated_reproduced if execution_succeeded else {},
        license_name=paper.license,
        seed_results=[0.842, 0.844, 0.841] if (execution_succeeded and not args.simulate_failure) else None,
        has_environment_file=has_environment_file,
        has_readme=has_readme,
        has_saved_artifacts=has_saved_artifacts,
    )

    bd = eval_result["breakdown"]

    # Save to database
    score_record = {
        "score_id": str(uuid.uuid4()),
        "paper_id": paper.paper_id,
        "tier1_build": bd.tier1_build,
        "tier2_metrics": bd.tier2_metrics,
        "tier3_stability": bd.tier3_stability,
        "tier4_artifacts": bd.tier4_artifacts,
        "total_score": bd.total_score,
        "status_label": bd.status_label,
        "summary": bd.summary,
    }
    save_score(score_record)

    print("\n----------------- SCORING BREAKDOWN -----------------")
    print(f"Tier 1 (Build & Environment)  : {bd.tier1_build:>5.1f} / 100 (Weight: 35%)")
    print(f"Tier 2 (Metrics Alignment)    : {bd.tier2_metrics:>5.1f} / 100 (Weight: 35%)")
    print(f"Tier 3 (Seed Stability)       : {bd.tier3_stability:>5.1f} / 100 (Weight: 15%)")
    print(f"Tier 4 (Artifacts & License)  : {bd.tier4_artifacts:>5.1f} / 100 (Weight: 15%)")
    print("-----------------------------------------------------")
    print(f"TOTAL COMPOSITE SCORE         : {bd.total_score:>5.1f} / 100")
    print(f"STATUS CLASSIFICATION         : [{bd.status_label}]")
    print(f"SUMMARY / AI RATIONALE        : {bd.summary}")
    print("-----------------------------------------------------\n")


def main():
    parser = argparse.ArgumentParser(description="Repro Radar CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init-db
    p_init = subparsers.add_parser("init-db", help="Initialize SQLite DB and seed target papers")
    p_init.add_argument("--reset", action="store_true", help="Drop existing tables before recreating")
    p_init.set_defaults(func=cmd_init_db)

    # list-papers
    p_list = subparsers.add_parser("list-papers", help="List all papers in Repro Radar")
    p_list.set_defaults(func=cmd_list_papers)

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect a specific paper")
    p_inspect.add_argument("paper_id", help="Paper ID (e.g. paper_001)")
    p_inspect.set_defaults(func=cmd_inspect_paper)

    # score
    p_score = subparsers.add_parser("score", help="Evaluate and score a paper")
    p_score.add_argument("paper_id", help="Paper ID (e.g. paper_001)")
    p_score.add_argument("--simulate-failure", action="store_true", help="Simulate failed metric reproduction")
    p_score.add_argument("--simulate-divergence", action="store_true", help="Simulate divergent metric reproduction")
    p_score.add_argument("--simulate-build-error", action="store_true", help="Simulate execution build error")
    p_score.add_argument("--simulate-clone-error", action="store_true", help="Simulate clone failure")
    p_score.add_argument("--simulate-deps-error", action="store_true", help="Simulate dependency failure")
    p_score.set_defaults(func=cmd_score_paper)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
