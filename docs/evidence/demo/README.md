# Demo evidence (#444)

- `dashboard_list.png` and `dashboard_paper_006.png`: the local dashboard (`python -m src.web --port 8137`, `127.0.0.1` only) as it was on
  2026-10-24 on the maintainer's machine, taken with headless Chrome. The 58.25 of `paper_006` is the score stored by
  `python cli.py score paper_006 --from-run data/pilot3_runs/paper_006` (tier 2 = 0: no claim of the paper was found in the run's output,
  "nothing was compared"); the "Latest run" panel of that page is the Pilot 1 record of the database, not the run that was scored.
  These are not results of reproduced papers. The database file is local and ignored by git.
