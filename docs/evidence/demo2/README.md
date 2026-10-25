# demo2 evidence (#496)

Screenshots of the local dashboard on `data/dashboard_demo.db`, built by `python scripts/build_demo_db.py` from the real
stored runs and the accepted claims. They are taken with headless Chrome against `python -m src.web --db-url
sqlite:///data/dashboard_demo.db` on `127.0.0.1`.

- `list.png`: the leaderboard, 13 rows (12 papers and the synthetic control, which is a known-answer test and says so in
  its title).
- `paper_003.png`, `paper_006.png`, `paper_102.png`: detail pages. The score summary names the run and the setting the
  row shows and how many stored runs the paper has.
- `badge_paper_003.png`: the badge of `paper_003`.
- `report_paper_003.md`, `report_paper_003.pdf`: the report download of the same paper.

**How to read the numbers.** Every row is the scorer's output on a stored run, not a validation. The claims are matched by
question ID as `cli.py score --from-run` does it, so Tier 2 is 0 for every paper that has accepted claims (the run's metrics
are keyed by another name, `docs/REAL_VERDICTS.md` section 2). A paper without an accepted claim gets the neutral Tier 2
of 70. The "Started" time of a run is the start time in its own record.
