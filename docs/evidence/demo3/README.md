# demo3 evidence (#548)

Screenshots of the final local dashboard, taken with headless Chrome on 2026-10-28 from a fresh clone of the repository after
`python cli.py init-db`, `python scripts/build_demo_db.py` and `python -m src.web --db-url sqlite:///data/dashboard_demo.db`
(`127.0.0.1` only).

- `list.png`: the list with a reason beside each label, and the synthetic control listed apart ("not a paper: known-answer control").
- `paper_003.png`: "Why this label": 0.459 claimed against 0.473 in the run (3.05 %), two claims without a counterpart, Tier 3 from 3 stored seed runs.
- `paper_006.png`: nothing compared, Tier 2 is the neutral baseline, label `Needs Review`.
- `paper_103.png`: a failed run with its category and a quoted log line.
- `synthetic_control.png`: the known-answer control.
- `failures.png`: the failure statistics page with the selection-bias warning.

These show what the scorer decided on stored runs. They are not a set of reproduced papers and not a success rate.
