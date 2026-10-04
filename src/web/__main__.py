"""Run the local dashboard: python -m src.web  (binds to 127.0.0.1 only; docs/DECISIONS.md, D-006)."""

import argparse

import uvicorn

from src.web.app import create_app

parser = argparse.ArgumentParser(description="Run the Repro Radar dashboard on localhost.")
parser.add_argument("--port", type=int, default=8000)
parser.add_argument("--db-url", default=None, help="SQLAlchemy URL (default: the project database).")
args = parser.parse_args()
uvicorn.run(create_app(args.db_url), host="127.0.0.1", port=args.port)
