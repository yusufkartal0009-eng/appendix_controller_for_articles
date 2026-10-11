#!/usr/bin/env python3
"""SHA-256 manifest of a run directory, its verification, and a comparison of two runs (#29).

    python scripts/hash_run.py sandbox_runs/paper_003                    # print the hashes; write nothing
    python scripts/hash_run.py sandbox_runs/paper_003 --write            # also write artifact_manifest.json there
    python scripts/hash_run.py sandbox_runs/paper_003 --verify           # compare the directory with its manifest
    python scripts/hash_run.py run_a --compare run_b                     # which files the two runs share
    python scripts/hash_run.py run_a --store run-id [--db-url URL]       # save the hashes in the runs table

`--verify` exits with 1 when a file was changed, removed, or added. See src/artifact_hash.py for what the two
hashes mean and what is left out.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.artifact_hash import (
    build_manifest,
    compare_manifests,
    load_manifest,
    store_hashes,
    summarize,
    verify_manifest,
    write_manifest,
)
from src.database import get_engine, get_session, init_db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SHA-256 manifest of a run directory.")
    parser.add_argument("run_dir")
    parser.add_argument("--write", action="store_true", help="Write artifact_manifest.json into the run directory.")
    parser.add_argument("--verify", action="store_true", help="Compare the directory with its artifact_manifest.json.")
    parser.add_argument("--compare", metavar="OTHER_RUN_DIR", help="Compare with the manifest of another run.")
    parser.add_argument("--store", metavar="RUN_ID", help="Save the two hashes in this row of the runs table.")
    parser.add_argument("--db-url", default=None, help="Database URL (default: REPRO_RADAR_DB_URL or data/repro_radar.db).")
    args = parser.parse_args(argv)

    try:
        if args.verify:
            report = verify_manifest(args.run_dir, load_manifest(args.run_dir))
            print(json.dumps(report, indent=2))
            return 0 if report["ok"] else 1
        manifest = build_manifest(args.run_dir)
        if args.compare:
            comparison = compare_manifests(manifest, build_manifest(args.compare))
            print(summarize(comparison))
            return 0
        if args.write:
            write_manifest(args.run_dir, manifest)
        if args.store:
            engine = get_engine(args.db_url) if args.db_url else get_engine()
            init_db(engine)
            session = get_session(engine)
            try:
                store_hashes(session, args.store, manifest)
            finally:
                session.close()
    except (OSError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({k: manifest[k] for k in ("file_count", "total_bytes", "manifest_sha256", "outputs_sha256", "skipped")},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
