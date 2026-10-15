# D2 evidence (#38)

- `real_database_*.png`: the project database as it is (`python -m src.web`). It holds 6 papers and 0 scores, so every
  paper shows "Not scored"; the latest runs are the stored Pilot 1 runs (the Pilot 2 and 3 records are not loaded into the
  database).
- `demo_*.png`: a throwaway **DEMO database** built by `make_demo_db.py` (invented scores, titles start with "DEMO"). It
  exists only to show what scored rows, the status colors, the filter, and the score breakdown look like. These are not
  results.
- `empty_database.png`: an empty database (explicit empty state).
