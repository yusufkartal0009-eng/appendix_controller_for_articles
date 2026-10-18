# External validation: run protocol

Date written: 2026-10-18. Issue #402. This protocol is written and merged **before any selected article is installed or run**.
It applies the protocol of `docs/PILOT_4.md` to the articles chosen by the rules of `docs/EXTERNAL_VALIDATION.md` (including
amendment 4, section 11). Nothing in it was decided after a run result was seen. At the time of writing **no article is
selected** (`data/external_validation/papers.json` is an empty list, section 11 of the rules document), so this protocol has
not been used; it is the protocol that applies if articles are selected later.

## 1. What is measured

For each selected article (`paper_201` and following, at most 4), once: does the README command install and run in the
sandbox (Tier 1 of Pilot 4), and what are the install status, the exit code, the duration, and the failure category. The
agreement of the system's verdict with the referees' result ("reproducible") is a separate step, defined in
`docs/EXTERNAL_VALIDATION.md` sections 6 and 7, and is **not** part of this protocol.

**No article is dropped, replaced, or removed from the denominator because it fails, times out, or cannot be run.** A failed
article stays in the table with its failure category (`scripts/categorize_pilot_failures.py`).

## 2. Settings (same as `docs/PILOT_4.md` section 2, with these differences)

| Setting | Pilot 4 | This protocol |
|---|---|---|
| CPUs | `--cpus=2.0` | **`--cpus 4`** (the owner needs the computer for other use during the runs; recorded as `cpus_override`). `docs/EXTERNAL_VALIDATION.md` section 5 said 8; this protocol replaces it before any run |
| Memory | 50% of the host's RAM | **`--memory 50%`** (same; recorded as `memory_override`) |
| Run-phase timeout | 14400 s | 14400 s (same) |
| Install-phase timeout | 3600 s | 3600 s (same) |
| Correction round | one, limited to the first attempt's logs | **none** |
| Retries | none | **none** |
| Records | `data/pilot4_runs/<paper_id>/` | `data/external_validation/runs/<paper_id>/` |

Everything else is Pilot 4: image `repro-radar-sandbox:py3.11`, install from the repository's own requirement files, `--network
none` in both phases, `--pids-limit=100`, no GPU, repository mounted read-only, no data cache, no environment variables beyond
the sandbox's, the command run **as written** from the repository root, nothing in the paper's code, data, or README edited.
The runs are **sequential**. `scripts/preflight.py` must pass before the first run.

## 3. One attempt, no correction

Each article gets **one** attempt. A run that ends with an install failure, a non-zero exit code, `TIMEOUT`, or `OOM_KILLED`
is recorded as it is. There is no correction round and no re-run, even when the logs show an obvious fix; a harness defect
(Repro Radar's own code stops the run from happening as specified) is the only reason to run again, as its own issue and PR,
and the first output is kept (`docs/PILOT_4.md` section 8).

## 4. What the current runner can run

`scripts/run_pilot.py --pilot4` accepts only `python <script> <arguments>` (`command_kind: python_script`). An article selected
with another kind (`python_module`, `make`, `notebook`) cannot be run as specified by the current runner, and neither the
image nor the staging step was checked for `make` or a notebook runner. Such an article is **not run and not replaced**: it is
recorded as `NOT_RUNNABLE_BY_RUNNER` with its command kind, and supporting its kind is a separate issue decided by the owner
before any run of it. This is a statement about the tool, not about the article.

## 5. Definitions and reporting

The definitions are those of `docs/PILOT_4.md` section 5 (valid run, install success, run success, pilot success), with the
denominator always the number of selected articles. Reported per article: the command, its kind, the status, the exit code, the
duration, the peak memory, and the failure category with its deciding log line. Every number in a report comes from the
stored records through a script.

## 6. Known limits

- At most 4 articles from one journal, selected by a rule that was widened after results were seen (`docs/EXTERNAL_VALIDATION.md`
  section 11): anecdotal, not statistical.
- The command is the README's first accepted line; it can be a demo or a data step, so a run that succeeds shows that this command ran,
  not that the article's tables can be reproduced.
- The computer is used for other work during the runs; run times are not compared with other pilots. With 4 CPUs they are not
  comparable with the 2 CPU and 8 CPU runs of `docs/CPU_RUNS.md`.
- No negative cases: every article is expected to be reproducible (`docs/EXTERNAL_VALIDATION.md` section 8).
