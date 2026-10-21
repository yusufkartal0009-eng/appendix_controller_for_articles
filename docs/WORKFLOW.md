# The path of one paper through Repro Radar

This document describes what happens to one paper from the moment it is added to the moment its result is shown, and how
long each step takes. **"Measured"** means the number comes from a stored record in this repository (named in the last
column). **"Estimate"** means nobody timed it; it is a rough guess and is labeled so. Times come from one Windows machine
(Docker Desktop, 12 CPUs and 15.5 GiB visible to Docker, a run limit of 4 CPUs unless stated) and are not guarantees.

## The steps

| # | Step | Who | Time | Basis |
|---|---|---|---|---|
| 1 | Add the paper | Owner and an assistant | 30 to 90 min, once per paper | Estimate |
| 2 | Verify the sources | Machine | about 1 min | Estimate |
| 3 | Preflight | Machine | about 6 s | Measured (clean-clone walk-through) |
| 4 | Fetch the data | Machine, network on | seconds to minutes (small dataset); tens of minutes (`paper_003`, 4.37 GB) | Estimate |
| 5 | Clone the repository and collect the packages | Machine, network on | about 50 s (`paper_003`) | Measured (`docs/ENV_CACHE_RUNS.md`) |
| 6 | Build phase (only if a package needs compiling) | Machine, network off | not measured | |
| 7 | Install phase | Machine, network off | about 1,000 to 1,055 s (`paper_003`); 179 s with the environment cache; about 350 s (`paper_102`) | Measured |
| 8 | Run phase | Machine, network off | 12.7 s (`paper_102`); 1,300 to 1,500 s (`paper_003`); 1,120 s on 8 CPUs and 3,269 s on 2 CPUs (`paper_006`); about 9,200 s (`paper_004`) | Measured (`docs/CPU_RUNS.md`, `docs/MEMORY_RUNS.md`) |
| 9 | Collect and score | Machine | seconds | Measured (a stored run is scored at once) |
| 10 | Extract the claims | Machine | 5 to 15 min | Estimate |
| 11 | Accept the claims | Owner | about 15 to 20 min per paper | Estimate |
| 12 | Tier 3, several seeds | Machine | the run phase times the number of seeds; two papers with 3 seeds each, started together, took about 3 hours | Measured (`docs/MULTI_SEED.md`) |
| 13 | Diagnosis report and dashboard | Machine | seconds | Estimate |

## What each step does

**1. Add the paper.** The owner and an assistant write the entry of the paper: the paper's address, the address of its
code, the exact commit (40 characters) of the code, the script to run, the Python version, and the data it needs. The commit
is pinned because a repository that changes later would change the result. See `docs/PAPER_ONBOARDING.md`.

**2. Verify the sources.** `scripts/verify_corpus.py` checks that the paper's title matches its page, that the repository
exists, that its license is open and equals the declared one, and that the script exists at the pinned commit. A paper that
fails stops here.

**3. Preflight.** `scripts/preflight.py` (also run by `cli.py score`) checks that Docker answers, that disk and memory are
enough, that the machine will not sleep, that the sandbox image is built, and that a small test container starts with no
network and a read-only root. If the image is missing it prints the `docker build` command.

**4. Fetch the data.** The sandbox has no network, so the data of a paper is fetched beforehand on the host with
`scripts/fetch_data.py` and mounted read-only into the run. A paper whose data is a file to be downloaded by hand has no
data items and cannot complete (`paper_008`). Papers that fetch data while running fail in the run phase
(`DATA_NOT_ACCESSIBLE`).

**5. Clone and collect packages.** The code is cloned at the pinned commit. The prebuilt packages (wheels) the paper needs
are downloaded on the host into a folder. Large wheels (for example PyTorch) make this step long.

**6. Build phase.** A package without a prebuilt wheel is compiled from its source in a second image that contains a
compiler, with the network off. Most papers do not need this step.

**7. Install phase.** The collected packages are installed inside the sandbox, offline. Conflicts and missing packages show
up here; the most common failure category of the pilots (`MISSING_DEPENDENCY`) is found in this step or the next. The
result of the install can be kept in an environment cache (`docs/ENV_CACHE_RUNS.md`): a second run with the same locked
packages skips most of it.

**8. Run phase.** The paper's own command runs in the sandbox: no network, a read-only root, limits on CPU, memory,
processes and time (default 3,600 s). Whatever the program prints is recorded. When a limit is exceeded the program is
stopped and the result is recorded as `TIMEOUT` or `OOM_KILLED`. This is intended: a paper must not be able to harm the
rest of the system.

**9. Collect and score.** `cli.py score` reads the record of the run, reads the numbers the program printed, and gives four
tier scores: Tier 1 (installed and ran), Tier 2 (the numbers agree with the accepted claims, within a tolerance), Tier 3
(stability over seeds), Tier 4 (license, README, artifacts). The status is one of Verified, Partially Verified, Needs
Review, or Failed. A paper with no accepted claim gets a neutral baseline for Tier 2, and the output says so.

**10. Extract the claims.** The text of the paper's PDF is extracted. Three independent assistant passes look for the
numbers in the paper's tables; each must give a verbatim quote, and a guard checks that the quote exists on the cited page.
A value that all passes agree on becomes a **candidate**, not an accepted claim (`docs/AGENT_EXTRACTION.md`).

**11. Accept the claims.** A person compares each candidate with the PDF and accepts or rejects it (`cli.py review-claims`).
Only claims accepted by a person reach the scorer. This step is manual on purpose: in one test the three passes agreed on
the same wrong row, so agreement is not correctness. The accepted decisions are stored in `data/claims/review_decisions.json`
and restored by `cli.py init-db`.

**12. Tier 3, several seeds.** If the paper offers a seed, the same program runs several times with different seeds; the
mean and the spread of the metrics are computed, and a large spread lowers Tier 3 (`docs/MULTI_SEED.md`).

**13. Diagnosis report and dashboard.** `cli.py diagnose` writes a rule-based report of one run: status, failure
category, the quoted log line, and the comparison with the claims; what is not known is written as "unknown"
(`docs/DIAGNOSIS.md`). `python -m src.web` shows the scores on localhost.

## Totals for the examples

| Paper | Machine time | Owner time | Basis |
|---|---|---|---|
| `paper_102` (light) | about 6 to 7 min (install about 350 s, run 12.7 s) | about 15 to 20 min for the claims | Measured (machine), estimate (owner) |
| `paper_003` | about 44 min without the cache (2,660 s), about 26 min with it (1,549 s) | as above | Measured (`docs/ENV_CACHE_RUNS.md`) |
| `paper_006` | the run alone took 1,120 s on 8 CPUs and 3,269 s on 2 CPUs | as above | Measured |
| A paper that fails early | seconds to minutes (`paper_103`: 0.6 s). A failure after large downloads can be long (`paper_008` in the clean-clone test: 1,573 s in all, of which the run was 38 s) | none | Measured |

## Where papers fail

The step where a paper stops is recorded as a category: missing dependency (steps 5 to 8), data that is not accessible
(steps 4 and 8), memory or time limits (step 8), and a read-only repository that the program tries to write into (step 8).
The pilots (`docs/report/REPORT.md`) give the counts. The only step that needs a person for every paper is step 11.

## Not verified

- The estimates in the table were not timed.
- Step 6 (build phase) has no time in the stored records.
- The times do not include the owner reading the result.
