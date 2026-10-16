# Pilot 4: six new papers, one documented setup round

Date written: 2026-10-16. Issue #344. This protocol is written and merged **before any of the six papers is installed or
run**. Nothing in it was decided after a result was seen. The papers were selected by the rules of
`docs/CORPUS_EXPANSION.md` (section 7 lists them); whether they run was not looked at.

## 1. What Pilot 4 measures

Pilots 1 to 3 used the six papers that the project corrected and reduced before the pilots (`data/seed_papers.json`), and the
tool was built on them. Pilot 4 runs **six papers that the tool has not seen**, once each, with one documented
correction round, and reports the **success rate on new papers**. It measures Tier 1 only (install and run). It does **no
claim extraction and no scoring**, and it does not read any metric.

The six papers are `paper_101` to `paper_106` of `data/corpus_expansion/papers.json`, each at the pinned commit of that file.
**No paper is dropped, replaced, or removed from the denominator because it fails or cannot be run.** The rate is for papers
selected as `docs/CORPUS_EXPANSION.md` describes; it is not a rate for machine learning papers in general.

## 2. Fixed settings (same for every paper)

| Setting | Value |
|---|---|
| Runner | The owner's Windows machine with Docker Desktop (as Pilots 2 and 3); the tool commit is recorded in every record |
| Image | `repro-radar-sandbox:py3.11` (Python 3.11) for the first attempt |
| Install | The repository's own requirement files (the staging step finds them), bundled in the Python 3.11 image as in Pilot 2; a repository with no requirement file installs as `SKIPPED` |
| Network | `--network none` in both phases |
| CPUs | `--cpus=2.0` |
| Memory | `--memory-swap` equal to `--memory`, both **50% of the host's RAM** (`--memory 50%` of `scripts/run_pilot.py`, resolved by `src/sandbox/resources.py`; the resolved size is in every record as `memory_override`) |
| Processes | `--pids-limit=100` |
| Scratch space | `/tmp` 64 MB and `/workspace/home` 2048 MB, both `noexec` (sandbox defaults) |
| Timeouts | 3600 s for the install phase and **14400 s for the run phase** |
| GPU | None |
| Repository | Mounted read-only; no data cache; no environment variables beyond the sandbox's |
| Repetitions | One first attempt per paper, plus at most one correction round (section 4) |

The limits are not those of Pilot 1 (6 GiB memory, 3600 s run phase); Pilot 4 is shown beside Pilots 1 to 3, not under the
same conditions.

## 3. The first attempt

The command is the entry's `run_command` of `data/corpus_expansion/papers.json`: the first `python <script>.py` line in a
fenced block of the README (`docs/CORPUS_EXPANSION.md` R3), with backslash continuations joined and a trailing shell
comment removed. It is run **as written**, from the repository root: `python <script> <arguments>`. Nothing is added to it, and
nothing is edited in the paper's code or data. The first attempt is the **strict** result.

## 4. The one correction round

If the first attempt **ends in an error** (staging fails, the install phase fails, or the run phase ends with a non-zero
exit code, `TIMEOUT`, or `OOM_KILLED`), the paper gets **one** correction round: one full re-run (install and run) with the
changes below. A first attempt that ends with exit code 0 gets no correction, even if its install was `SKIPPED`.

Allowed in the correction round, and only to address the cause shown in the first attempt's logs:

- extra requirements, or version constraints for a requirement that the repository leaves open;
- a different image (Python 3.8, 3.9, or 3.11), when the logs show a version problem;
- another working directory, or a writable per-run copy of the repository, when the logs show a path or write problem;
- environment variables that the code reads;
- data fetched on the host from a URL or OpenML dataset named in the README or the paper into the data cache
  (`scripts/fetch_data.py`) and mounted read-only (or as a writable copy), when the logs show a missing data file or a
  failed download, up to 2 GB per paper.

Not allowed: editing the paper's code, data, or README command; a wrapper script; changing the limits of section 2 (so an
`OOM_KILLED` or `TIMEOUT` stays a result); a second correction round, even when the corrected run fails; or choosing a
change after looking at anything other than the first attempt's logs.

**Every change is recorded** in `correction.json` of the paper's record: the change, the log line of the first attempt that
motivated it, and its place in the setup. The corrected run is the **corrected** result. Both results are reported.

## 5. Definitions (the same as Pilot 1, `docs/PILOT_WEEK2.md` section 5)

| Term | Definition |
|---|---|
| **Valid run** | `docker_used: true` and `isolated: true` in `run_report.json`. Only valid runs count. |
| **Install success** | `dependency_install_status: INSTALLED`. `FAILED`, `SKIPPED`, and `UNKNOWN` are **not** install success. |
| **Run success** | Exit code 0 of the run phase in a valid run. `TIMEOUT`, `OOM_KILLED`, and any non-zero exit code are not. |
| **Pilot success** | Install success **and** run success. |
| **Rates** | Papers with the property / **6**. The denominator is always 6, including papers whose staging fails. |

A paper that installs as `SKIPPED` and runs with exit code 0 has no pilot success; it is reported as "ran without installed
dependencies", as in Pilot 1. The failure categories are those of `docs/PILOT_WEEK2.md` section 7, decided by
`scripts/categorize_pilot_failures.py` from the first failure in the order install, run, with the deciding log line quoted.

## 6. What is reported

- The three rates of section 5 for the **first attempt** (strict) and for the result **after the correction round**, each over 6.
- Per paper: the command, the status, the exit code, the duration, the peak memory, the failure category with its deciding
  log line, and every correction with the log line that motivated it.
- A section that tabulates Pilots 1, 2, 3, and 4 side by side, with the differences in corpus and limits named in the
  heading (generated by `scripts/pilot_compare.py` from the stored records), and a short paragraph in the report
  (`docs/report/REPORT.md`).
- Nothing about claims, scores, or metrics.

## 7. Records

One pull request per paper. The final record is in `data/pilot4_runs/<paper_id>/` (the pilot record, the run report, and the
logs). When a correction round was made, the first attempt is kept unchanged in
`data/pilot4_runs/first_attempts/<paper_id>_attempt1/` and `correction.json` is in the final record. The failure categories of
the final records and of the first attempts are written by `scripts/categorize_pilot_failures.py` and kept next to them.

## 8. What may change after the runs start

- **Frozen:** the settings (section 2), the first-attempt command (section 3), the correction rules (section 4), the
  definitions (section 5), and the list of papers. If one of them turns out to be wrong, the result stays and the change is
  proposed for a later pilot.
- **Allowed:** fixing a defect in Repro Radar's own code that stops a run from happening as specified here. Each fix is its
  own issue and PR, the paper is re-run (this does not use up the correction round), and the first output is kept.
- **Never:** editing a paper's code or data, a wrapper, or editing a result by hand.

## 9. Known limits of this pilot

- n = 6, one first attempt per paper: anecdotal, not statistical.
- The command is the README's first `python` line. It can be a documentation checker, a data preparation step, or an example;
  a run that succeeds shows that this command ran, not that the paper's main experiment can be reproduced.
- The sample is biased by its pool and drifted from tabular data (`docs/CORPUS_EXPANSION.md` sections 5 and 7).
- One Windows host: the memory limit is a share of its RAM; the result of a memory-bound paper depends on it.
- The correction round is done by the same agent that wrote the tool, using the first attempt's logs; another person could
  correct differently. Every change is recorded so that it can be judged.
- No GPU, so a paper that needs one fails here whatever its merits.
