"""Run the local dashboard: python -m src.web  (binds to 127.0.0.1 only; docs/DECISIONS.md, D-006).

    python -m src.web --demo    # builds data/dashboard_demo.db from the stored runs, starts the dashboard on it, opens the page
"""

import argparse
import threading
import webbrowser

import uvicorn

from src.web.app import create_app

HOST = "127.0.0.1"


def build_demo_db() -> str:
    """Write the demo database from the stored runs (scripts/build_demo_db.py) and return its SQLAlchemy URL."""
    from scripts import (
        build_demo_db as demo,  # `python -m src.web` run from the project root has it on sys.path
    )

    rows = demo.build()
    print(f"Demo database: {demo.DEFAULT_OUT} ({len(rows)} papers, one score each; the project database is not touched).")
    return f"sqlite:///{demo.DEFAULT_OUT.as_posix()}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Repro Radar dashboard on localhost.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db-url", default=None, help="SQLAlchemy URL (default: the project database).")
    parser.add_argument("--demo", action="store_true",
                        help="build the demo database from the stored runs, show it, and open the page in the browser.")
    parser.add_argument("--no-browser", action="store_true", help="with --demo: do not open the page.")
    args = parser.parse_args(argv)
    if args.demo and args.db_url:
        parser.error("--demo builds its own database; do not combine it with --db-url.")
    if args.no_browser and not args.demo:
        parser.error("--no-browser only goes with --demo.")
    db_url = build_demo_db() if args.demo else args.db_url
    if args.demo and not args.no_browser:
        threading.Timer(1.5, webbrowser.open, [f"http://{HOST}:{args.port}/"]).start()
    uvicorn.run(create_app(db_url), host=HOST, port=args.port)
    return 0


if __name__ == "__main__":
    main()
