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


## Update 2 (2026-10-24, issue #441): a fresh run from a clean clone completed

A fresh `git clone` of the public repository at commit `9b35d5c` into an empty folder, then the README steps in the order of its
Quickstart, on the same machine (Docker Desktop, 12 CPUs and 15.5 GiB visible). The six sandbox images were already on the machine
(rebuilt from scratch earlier the same day, `docs/ENVIRONMENT.md`, #435), so no image was built in this walk-through. Every step was timed by a
script with `date`; the console log is kept outside the repository because it holds local paths. Other work (tests, document edits) ran on the
same machine while the paper trained, so the times are not those of an idle machine.

| Step | Command | Result | Time |
|---|---|---|---|
| clone | `git clone <public URL> <folder>` | exit 0 | 2 s |
| venv, pip | `py -3.11 -m venv .venv`, `pip install -r requirements-dev.txt` | exit 0 | 55 s |
| 3 | `python cli.py init-db` | exit 0, `Restored 13 claims that a person accepted (data/claims/review_decisions.json); 0 already reviewed here, 0 not accepted and ignored.` | 1 s |
| 4 | `python cli.py list-papers` | exit 0, 6 papers | under 1 s |
| 6 | `python scripts/preflight.py` | exit 0, 7 checks passed | 1 s |
| 7 | `python scripts/fetch_data.py paper_006` | exit 0, `openml_1461` FETCHED (3,688,243 bytes) | 8 s |
| 7 | `python cli.py score paper_006 --cpus 8 --timeout 7200` | exit 0; run COMPLETED, exit code 0, run phase 1,092.54 s; stage STAGED, build BUILT, install INSTALLED | **2,423 s** |
| 7a | `python cli.py diagnose sandbox_runs/score/paper_006` | exit 0, "The classifier found no failure", metrics `accuracy 0.8886, auroc 0.892` | 1 s |

Total from the clone to the end of `diagnose`: **2,490 s** (41.5 minutes). Of the 2,423 s of `cli.py score`, 1,092.54 s are the run phase; the rest is
staging, the build of wheels and the install phase (the split of the remaining 1,330 s was not measured separately).

**Result of the score** (`cli.py score` printed, before the display fix of #450, `61.2` for the total; the stored value is 61.25):

| Tier | Score |
|---|---|
| Tier 1 (build) | 100 |
| Tier 2 (metrics) | 0 |
| Tier 3 (stability) | 75 (single-run baseline) |
| Tier 4 (artifacts) | 100 (the staged repository was present, so its README counts) |
| Total | 61.25, status Needs Review |

**Accepted claims used: 2** (`arcene_auroc`, `xgboost_arcene_auroc`, both accepted by the owner). **Neither was found in the output** (the program
printed `accuracy` and `auroc` of the Bank dataset, 1461, while the claims concern Arcene), so Tier 2 = 0 is "nothing was compared", and the
summary says so: "claimed metrics not found in the output (nothing was compared)". This run reproduces the numbers of the earlier completed runs of
this paper (`accuracy 0.8886`, `auroc 0.892`).

### What this shows, and what it does not

- Shows: a person who clones the public repository can follow the README to a fresh, completed run of a real paper (`paper_006`) with the 8-CPU
  setting and the 7,200 s limit given on the command line, and to a score that uses the owner's accepted claims restored by `init-db`.
- Does **not** show: that a claim of the paper is reproduced (no accepted claim was compared), that the default settings of `cli.py score`
  (2 CPUs, 3,600 s) are enough (they were not enough in the walk-through of 2026-10-17; this run changed both, so it is not a protocol run, and the
  record says so), or that other papers complete (`paper_008` still needs a dataset downloaded by hand).
- Not verified: the time on an idle machine, on another operating system, or with the images built in the same walk-through.
