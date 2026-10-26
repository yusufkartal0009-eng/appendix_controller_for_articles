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

**How to read the numbers.** Every row is the scorer's output on a stored run, not a validation. The claims go through
`data/claim_metric_map.json` as in `cli.py score --from-run` (#507, #509; the screenshots were taken again after it, #511).
Tier 2 is 100 for `paper_003` (one claim compared: 0.459 against 0.473). For a paper whose accepted claims have no counterpart in
the run (`paper_004`, `paper_006`), and for a paper without an accepted claim, Tier 2 is the neutral 70, so the label rests on
the build tiers only; this is not a measurement (`docs/REAL_VERDICTS.md` sections 2 and 5). Before the map Tier 2 was 0 for every
paper that has accepted claims (`docs/REAL_VERDICTS.md` keeps that result). The "Started" time of a run is the start time in its own record.

The detail pages were taken again after #513: the block under the score is headed "Run of this score" and has a `Started` row (the start time of the run's own record, UTC).
