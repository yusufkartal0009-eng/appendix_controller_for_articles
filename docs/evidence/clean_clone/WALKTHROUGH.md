# Clean-clone walk-through of the README (2026-10-17 and 2026-10-18)

Done for the mentor's to-do for outside use. A fresh `git clone` of `main` at commit `43fb509` into an empty folder, a new
virtual environment, and the README steps in order, on the owner's Windows machine (Docker Desktop with 12 CPUs and 15.5 GiB
visible, 32 GB host). The sandbox images already existed on this machine, so every `docker build` ran from the layer cache.
The full console log is kept outside the repository because it holds local paths.

| Step | Command | Result |
|---|---|---|
| 2 | `py -3.11 -m venv .venv`, `pip install -r requirements-dev.txt` | exit 0 |
| 3 | `python cli.py init-db` | exit 0 |
| 4 | `python cli.py list-papers` | exit 0, 6 papers |
| 5 | `python cli.py inspect paper_001` | **exit 1**, `Paper with ID 'paper_001' not found.` (fixed in #394; `inspect paper_003` exit 0) |
| 6 | the four `docker build` commands of the README | exit 0, all from cache (1 to 2 s each); **a build from scratch was not timed** |
| 6 | `preflight.check_image` with a tag that does not exist, real Docker | `FAIL` with the exact `docker build` command |
| 7 | `python cli.py score paper_008` | exit 0 (the command), run `FAILED` exit 1 after 38 s, status Failed, 65.75; **1,573 s** in all |
| 7 | `python scripts/fetch_data.py paper_006`, `python cli.py score paper_006` | exit 0 (the command), run `TIMEOUT` exit 137 at the 3,600 s limit (killed during epoch 36), status Failed, 65.75; **4,964 s** in all |
| 7 | `python cli.py score paper_006 --from-run data/pilot3_runs/paper_006` | exit 0, run COMPLETED, status Partially Verified, 85.75, Tier 2 = neutral baseline (0 accepted claims) |

## What this shows

1. **`paper_008` can never complete from a clean clone.** Its dataset is a file the paper's README asks the user to download by
   hand (`FileNotFoundError: ./data/forest_cover_type/forest-cover-type.csv`); `fetch_data.py paper_008` reports "no data items".
2. **`paper_006` did not finish under the defaults of `cli.py score`.** It was still training when the 3,600 s run limit
   killed it. The same paper completed in 3,269 s in the memory re-run (`data/memory_runs/paper_006_run2`) and in 1,120 s with 8 CPUs (`docs/MEMORY_RUNS.md`,
   `docs/CPU_RUNS.md`), so on this machine it is close to the limit and depends on the CPUs it gets.
3. **Both scores used no claim.** Each run printed `Accepted claims of this paper (accepted by a person): 0`. The claims that
   the owner accepted are in `data/claims/review_decisions.json` and in `expected_claims` of the seed file, but `cli.py score`
   reads accepted claims from the local database, which is not committed and which `init-db` does not fill with the accepted
   decisions. Tier 2 was therefore the neutral baseline (70), not a measurement.
4. **The scoring and the sandbox did what they should:** the failed run was reported as failed with its category, and the
   scorer said that its 70 for Tier 2 is a baseline.

## Not verified

- No paper was scored against accepted claims from a clean clone: the database holds none (issue #395). Fresh runs of the two
  papers tried did not complete (issue #396 for `paper_006`).
- The sandbox images were not built from scratch.

## Update (issue #395, fixed)

`python cli.py init-db` now restores the 13 claims that the owner accepted, from `data/claims/review_decisions.json`. In a
fresh database, `python cli.py score paper_006 --from-run data/pilot3_runs/paper_006` then reports 2 accepted claims and
Tier 2 = 0 (the Arcene metrics are not found in a run on another dataset), status Needs Review, 58.2, instead of the neutral
baseline. Point 3 above describes the state before this fix.

