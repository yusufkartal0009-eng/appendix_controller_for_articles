#!/usr/bin/env python3
"""Import the extracted claims of one pass into the database as `pending` claims (W6, #10).

    python scripts/import_claims.py              # pass A of every data/claims/paper_*.json
    python scripts/import_claims.py --pass B

Every found claim is stored with its provenance (page, table, quote, extraction file, extractor version).
Nothing is accepted here: claims stay `pending` until a person reviews them (`python cli.py review-claims`, #134).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.claim_store import get_extracted_claims, import_extraction
from src.config import DATA_DIR, PROJECT_ROOT
from src.database import get_engine, get_session, init_db, seed_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import extracted claims as pending claims.")
    parser.add_argument("--pass", dest="pass_name", default="A", help="Extraction pass to import (default A).")
    parser.add_argument("--claims-dir", default=str(DATA_DIR / "claims"))
    parser.add_argument("--db-url", default=None, help="Database URL (default: REPRO_RADAR_DB_URL or data/repro_radar.db).")
    args = parser.parse_args(argv)

    engine = get_engine(args.db_url) if args.db_url else get_engine()
    init_db(engine)  # creates the extracted_claims table in older databases
    session = get_session(engine)
    try:
        seed_database(session=session)  # the papers must exist before their claims
        claims_dir = Path(args.claims_dir)
        outcomes: Counter[str] = Counter()
        for path in sorted(claims_dir.glob("paper_*.json")):
            outcomes.update(import_extraction(session, path, claims_dir / "guard_report.json", args.pass_name, PROJECT_ROOT))
        session.commit()
        rows = get_extracted_claims(session)
        print(json.dumps({
            "pass": args.pass_name,
            "outcomes": dict(outcomes),
            "stored": len(rows),
            "review_status": dict(Counter(r.review_status for r in rows)),
            "verified_by": dict(Counter(str(r.verified_by) for r in rows)),
        }, indent=2))
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
