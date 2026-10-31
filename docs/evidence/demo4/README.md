# demo4 evidence (dashboard polish)

Screenshots of the local dashboard after the polish change, taken with headless Chrome from `data/dashboard_demo.db`
(built by `python scripts/build_demo_db.py`, served on `127.0.0.1` only).

- `list.png`: the score of a `Failed` run is grey (tooltip: not a measure of reproducibility).
- `paper_003.png`: the venue year is not repeated, the score table is compact, the duplicate summary paragraph is gone,
  and progress-bar lines are hidden in the log excerpt (the count of hidden lines is shown).

These show how stored runs are displayed. They are not a set of reproduced papers and not a success rate.
