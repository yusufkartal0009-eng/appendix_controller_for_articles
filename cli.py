"""CLI Utility for Repro Radar."""

import argparse
import os
import sys
import uuid
from pathlib import Path

from tabulate import tabulate

# Ensure UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.claim_review import claims_for_scoring, review_claims
from src.claim_store import get_extracted_claims
from src.config import DATA_DIR, PROJECT_ROOT, SANDBOX_RUNS_DIR, SANDBOX_TEMP_DIR
from src.database import (
    get_all_papers,
    get_engine,
    get_paper_by_id,
    get_session,
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


SIMULATION_BANNER = "SIMULATION FOR TESTING: the reproduced numbers below are made up from the claimed ones; this is not a result"


def print_breakdown(bd, simulated: bool = False):
    print("\n----------------- SCORING BREAKDOWN -----------------")
    if simulated:
        print(f"*** {SIMULATION_BANNER} ***")
    print(f"Tier 1 (Build & Environment)  : {bd.tier1_build:>5.1f} / 100 (Weight: 35%)")
    print(f"Tier 2 (Metrics Alignment)    : {bd.tier2_metrics:>5.1f} / 100 (Weight: 35%)")
    print(f"Tier 3 (Seed Stability)       : {bd.tier3_stability:>5.1f} / 100 (Weight: 15%)")
    print(f"Tier 4 (Artifacts & License)  : {bd.tier4_artifacts:>5.1f} / 100 (Weight: 15%)")
    print("-----------------------------------------------------")
    print(f"TOTAL COMPOSITE SCORE         : {bd.total_score:>5.1f} / 100")
    print(f"STATUS CLASSIFICATION         : [{bd.status_label}]")
    print(f"SUMMARY / AI RATIONALE        : {bd.summary}")
    print("-----------------------------------------------------\n")


def cmd_score_paper(args):
    """Score a paper from a real sandbox run and its accepted claims (#136). The --simulate-* flags are a test aid."""
    session = get_session(get_engine(args.db_url) if args.db_url else get_engine())
    paper = get_paper_by_id(args.paper_id, session=session)
    if not paper:
        print(f"Paper with ID '{args.paper_id}' not found.")
        sys.exit(1)
    if any((args.simulate, args.simulate_failure, args.simulate_divergence, args.simulate_build_error, args.simulate_clone_error,
            args.simulate_deps_error)):
        return cmd_score_simulated(args, paper)

    from scripts import run_pilot
    from src.config import DATA_CACHE_DIR
    from src.score_run import load_run, score_run

    print(f"\nEvaluating reproducibility for: [{paper.paper_id}] {paper.title}")
    if args.from_run:
        run_dir = Path(args.from_run)
        print(f"Scoring the stored run in {run_dir} (no new run).")
    else:
        run_root = SANDBOX_RUNS_DIR / "score"
        print(f"Running the paper in the Docker sandbox with its run setup (records in {run_root / paper.paper_id}) ...")
        run_pilot.run_paper(paper.paper_id, Path(args.staging_dir), pilot2=True, data_cache=Path(args.data_cache or DATA_CACHE_DIR),
                            record_root=run_root)
        run_dir = run_root / paper.paper_id
    record, report = load_run(run_dir)

    claims = claims_for_scoring(session, paper.paper_id)
    print(f"Accepted claims of this paper (accepted by a person): {len(claims)}")
    repo_dir = Path(args.staging_dir) / paper.paper_id
    result = score_run(paper.paper_id, paper.license, claims, record, report, run_dir, repo_dir if repo_dir.is_dir() else None)

    bd = result["breakdown"]
    run = record.get("run") or {}
    print(f"Run: stage={record.get('stage', {}).get('status')} build={(record.get('build') or {}).get('status', 'none')} "
          f"install={report.get('dependency_install_status', 'n/a')} run={run.get('status', 'not started')} "
          f"exit_code={run.get('exit_code')}")
    for tier in ("tier1_notes", "tier2_notes", "tier3_notes", "tier4_notes"):
        for note in result["diagnostics"][tier]:
            print(f"  [{tier[:5]}] {note}")
    save_score({
        "score_id": str(uuid.uuid4()), "paper_id": paper.paper_id, "tier1_build": bd.tier1_build,
        "tier2_metrics": bd.tier2_metrics, "tier3_stability": bd.tier3_stability, "tier4_artifacts": bd.tier4_artifacts,
        "total_score": bd.total_score, "status_label": bd.status_label, "summary": bd.summary,
    }, session=session)
    session.close()
    print_breakdown(bd)


def cmd_score_simulated(args, paper):
    """Simulate execution output and calculate 4-tier reproducibility score. FOR TESTING ONLY, never saved."""
    expected_claims = paper.get_expected_claims_dict()
    print(f"\nEvaluating reproducibility for: [{paper.paper_id}] {paper.title}")
    print(f"*** {SIMULATION_BANNER} ***")

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
    print("(The simulated score is not saved to the database.)")
    print_breakdown(bd, simulated=True)


def cmd_review_claims(args):
    """Accept or reject extracted claims one by one (W7, #134); only accepted claims reach the scorer."""
    session = get_session(get_engine(args.db_url) if args.db_url else get_engine())
    try:
        if args.list:
            rows = [[c.extracted_claim_id, c.value_as_printed, f"p. {c.page}, {c.table_or_section}", c.review_status,
                     c.verified_by or "not matched"] for c in get_extracted_claims(session, args.paper_id)]
            if not rows:
                print("No extracted claims. Run 'python scripts/import_claims.py' first.")
                return
            print(tabulate(rows, headers=["Claim", "Value", "Where", "Review", "Verified by"], tablefmt="grid"))
            return
        review_claims(session, args.paper_id)
    finally:
        session.close()


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
    p_score = subparsers.add_parser("score", help="Score a paper from a real sandbox run and its accepted claims")
    p_score.add_argument("paper_id", help="Paper ID (e.g. paper_001)")
    p_score.add_argument("--from-run", default=None, help="Score a stored run directory (pilot_record.json, run_report.json) instead of running")
    p_score.add_argument("--staging-dir", default=".sandbox_staging", help="Where repositories are cloned for a real run")
    p_score.add_argument("--data-cache", default=None, help="Host data cache of the run setups (scripts/fetch_data.py)")
    p_score.add_argument("--db-url", default=None, help="Database URL (default: REPRO_RADAR_DB_URL or data/repro_radar.db)")
    p_score.add_argument("--simulate", action="store_true", help="SIMULATION FOR TESTING: successful run with made-up numbers")
    p_score.add_argument("--simulate-failure", action="store_true", help="SIMULATION FOR TESTING: failed metric reproduction")
    p_score.add_argument("--simulate-divergence", action="store_true", help="SIMULATION FOR TESTING: divergent metric reproduction")
    p_score.add_argument("--simulate-build-error", action="store_true", help="SIMULATION FOR TESTING: execution build error")
    p_score.add_argument("--simulate-clone-error", action="store_true", help="SIMULATION FOR TESTING: clone failure")
    p_score.add_argument("--simulate-deps-error", action="store_true", help="SIMULATION FOR TESTING: dependency failure")
    p_score.set_defaults(func=cmd_score_paper)

    # review-claims
    p_review = subparsers.add_parser("review-claims", help="Accept or reject extracted claims one by one")
    p_review.add_argument("paper_id", nargs="?", default=None, help="Only this paper (default: all papers)")
    p_review.add_argument("--list", action="store_true", help="List the claims and their review status; ask nothing")
    p_review.add_argument("--db-url", default=None, help="Database URL (default: REPRO_RADAR_DB_URL or data/repro_radar.db)")
    p_review.set_defaults(func=cmd_review_claims)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
