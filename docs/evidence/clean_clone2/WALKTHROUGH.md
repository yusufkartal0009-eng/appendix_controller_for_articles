# Second clean-clone walk-through (2026-10-28, issue #565)

A fresh `git clone` of the public repository (at `main` after PR #564, commit `a6774fb`) into an empty temporary directory, with its
own virtual environment. Every command of the README was run in the order and with the arguments the README gives. The commands that
need Docker or the network were not run. The earlier walk-through (`docs/evidence/clean_clone/WALKTHROUGH.md`) ran a real paper
through Docker; this one covers everything else and finds out whether the README still matches what the commands print.

Machine: Windows 11, Python 3.11.9, Git, no Docker started for this test. The times were measured with a stopwatch around each
command (one run each, on a machine that was doing nothing else heavy); they are not guarantees.

## Commands

| README step | Command | Result | Seconds |
|---|---|---|---|
| 1 | `git clone https://github.com/yusufkartal0009-eng/appendix_controller_for_articles.git` | exit 0 | 3.2 |
| 2 | `python -m venv .venv` | exit 0 (but see finding 2) | 6.4 |
| 2 | `pip install -r requirements-dev.txt` | exit 0 | 54 |
| 3 | `python cli.py init-db` | exit 0; "Successfully seeded 6 papers", "Restored 13 claims that a person accepted" | 1.0 |
| 4 | `python cli.py list-papers` | exit 0; a table of 6 papers, "Total Papers: 6" | 0.6 |
| 5 | `python cli.py inspect paper_003` | exit 0; three claims (0.459, 0.486, 0.433) | 0.6 |
| 6 | `docker build ...` (four commands) | **skipped: needs Docker** | |
| 7 | `python cli.py score paper_008` (real run) | **skipped: needs Docker** | |
| 7 | `python cli.py score paper_008 --from-run data/pilot2_runs/paper_008` | exit 0; `Failed`, total 62.75, Tier 2 70 (both claims have no counterpart: the dataset is missing) | 0.8 |
| 7 | `python cli.py score paper_006 --from-run data/pilot3_runs/paper_006` (the example in the README note) | exit 0; `Needs Review`, total 86.5, Tier 2 70, Tier 3 100 (see finding 1) | 0.7 |
| 7 | `python cli.py score paper_003 --from-run data/pilot3_runs/paper_003` | exit 0 | 0.7 |
| 7a | `python cli.py diagnose data/pilot3_runs/paper_004` | exit 0; report whose phases end with `OOM_KILLED`, exit code 137 | 0.6 |
| 7a | `python scripts/run_multi_seed.py paper_006 --pilot3 ...` | **skipped: needs Docker** | |
| 7a | `python scripts/field_analysis.py --check` | exit 0; prints nothing when the files agree | 0.2 |
| (README, review) | `python cli.py review-claims --list` | exit 0; a table of the 13 accepted claims | 0.6 |
| 8 | `ruff check .` | "All checks passed!" | 0.7 |
| 8 | `pytest tests/ -v` | exit 0: **1705 passed, 16 skipped** | 44.8 |
| 9 | `python scripts/build_demo_db.py` | exit 0; prints a table of 13 rows (12 papers and the synthetic control) and the command to start the dashboard | 1.0 |
| 9 | `python -m src.web` (default database), then HTTP requests | started in 1.6 s; `/`, `/papers/paper_003`, `/failures`, `/api/v1/papers`, `/api/v1/badges/paper_003.svg` answer 200; `/papers/nope` answers 404 | |
| 9 | `python -m src.web --db-url sqlite:///data/dashboard_demo.db`, then HTTP requests | started in 1.6 s; `/`, `/papers/paper_003`, `/papers/paper_006`, `/failures`, `/api/v1/scores/paper_003`, the badge, `report.md` and `report.pdf` answer 200; `/papers/nope` answers 404 | |

Not run: `python scripts/stage_and_bundle_repo.py ...` (clones an outside repository and uses Docker), `python scripts/verify_corpus.py`
and `python scripts/verify_sources.py` (network), `python scripts/preflight.py` (Docker). Skipped: needs Docker or the network.

## Findings

1. **A stale sentence in the README (fixed).** The note before step 7 said that scoring `paper_006` from the stored run gives "Tier 2 is
   0 (the metric is not found)". The command prints Tier 2 = 70 (the neutral baseline), total 86.5 and `Needs Review`, with both claims
   listed as having no counterpart in the run. The sentence predates the claim map (#507, #509) and the label rule (#540). The README
   now states what the command prints.
2. **`python -m venv .venv` failed in a long path (README note added).** The first attempt cloned into a folder whose path is 174
   characters long (the scratch folder of this session); `python -m venv` ended with an error of `ensurepip` (exit 1). Cloning into a
   short path (`<TEMP>\rr_clean2`) worked. Long paths are disabled on this machine
   (`LongPathsEnabled = 0`), which is the likely cause; it was not tested further. The README now tells Windows users to keep the path
   short.
3. **Test counts differ between a clean clone and the working copy.** The clean clone gives 1705 passed and 16 skipped; the working copy
   of the author, with the same commit, gives 1711 passed and 10 skipped. The skips in the clean clone, by the reason the tests give:
   6 network tests of `test_seed_integrity.py` (set `REPRO_RADAR_NETWORK_TESTS=1`), 6 tests that need the papers' PDFs, which are not
   tracked by git (`test_auto_search4.py` 4, `test_gold_expansion.py` 2), 2 POSIX permission tests of `test_sandbox.py` (skipped on
   Windows), and 2 symbolic-link tests (`test_artifact_hash.py`, `test_env_cache_edges.py`; Windows allows links only with a privilege).
   The working copy has the PDFs, so it skips fewer. The README does not state a test count, so nothing there is wrong. Not verified:
   which of these the author's working copy skips; the counts of the working copy are from a run on 2026-10-28.
4. **No other step failed or misled.** Every other command did what the README says. `field_analysis.py --check` prints nothing on
   success, which the README does not say; the exit code 0 is the signal.
5. **Tier 4 of a stored run reads "Missing README or instructions".** `cli.py score --from-run` has no staged repository, so the README
   of the paper's repository cannot be seen and counts as absent (this is in the code, `src/score_run.py`). It is correct but can look
   like a defect of the paper; not changed.

## Cleanup

The temporary directory and its virtual environment were created by this test only and were removed at the end. Nothing in the
author's working copy, the local database `data/repro_radar.db` or any stored run was touched by the clone.
