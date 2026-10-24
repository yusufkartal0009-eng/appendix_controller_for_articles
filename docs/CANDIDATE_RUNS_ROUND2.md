# Candidate runs, round 2 (repair round): protocol

Date written: 2026-10-24. Issue #455. This document is written and merged **before any round-2 run**. Nothing in it is changed
after the first round-2 run. If something is wrong, the fix is a new, dated section, not an edit of the rules below, and the runs
made before it keep the rules they were made under.

## 1. What this is, and what it is not

Round 1 (`docs/CANDIDATE_RUNS.md`) ran 14 of the 29 candidates once, as listed, without any repair: **0 of 14 passed**. Its records
(`data/candidates/runs/`) and its results (`docs/CANDIDATES.md`, "Run results") stay as they are and are **never overwritten**.

Round 2 lets a candidate be **repaired** within the narrow rules of section 3 and run again. It is kept apart from round 1 and
labeled as round 2 everywhere (records under `data/candidates/round2/`, a separate section in the documents). The owner's purpose
is twofold: a pilot count ("how many of the selected papers run"), and a correct decision on a known example in a real paper.
The second one is what matters; a pass of this round is only the first step toward it.

- The candidates are a **selected list**, chosen by other people for being easy. They are **not a sample** of papers, and the share
  that passes is **not a success rate** of anything. It is quoted only as "K of the N selected candidates".
- A pass does not show that the paper is reproduced. It shows that a repaired command ran and printed a number (section 5).
- No claim of a paper is accepted by these runs. Accepting a claim is the owner's decision alone.

## 2. Scope

| Group | Candidates | Rule |
|---|---|---|
| Round-1 candidates | the 14 of round 1 (status `ready` 9, `fixable` 4, `two_step` 1): cand_001 to cand_013 and cand_025 | all 14 are in round 2 |
| Risky candidates | the 11 of status `risky`: cand_014 to cand_024 | in round 2 **only** if their data can be downloaded on the host from an open address (section 4) |
| Excluded | the 4 of status `excluded`: cand_026 to cand_029 | **not run** |

- A candidate whose command was not run in round 1 for being incomplete (`cand_013`, placeholders only) stays `command_incomplete`:
  choosing a dataset name or a parameter value is not one of the repairs of section 3. It counts as not passed.
- The command of a candidate is the command of `data/candidates/run_plan.json` (round 1) for the 14, and, for a risky candidate, the
  command of the lists completed from the README by the rule of round 1 (`docs/CANDIDATE_RUNS.md` section 2: the first README
  line that starts with the listed text; placeholders without a concrete value in the README mean `command_incomplete`).
- The eligibility of every risky candidate (the address, the size, the decision, and the reason) is written to
  `data/candidates/round2/eligibility.json` **before that candidate is run** and in its own pull request. A candidate whose data
  does not qualify is recorded with the reason and is not run.

## 3. The allowed repairs, and only these

Every repair is written to the candidate's `repair_log.json` **with its reason**: the log line that motivated it, the repair kind,
the exact change, and where it is applied in the run setup. A repair that has no log line is not made.

| Kind | What it is | Where it is applied |
|---|---|---|
| `requirements` | an extra requirement, or a version of a requirement, for a package that is missing or incompatible (the logic of the correction round of `docs/PILOT_4.md` section 4). The package and the version are taken from the failing log line, from the repository's own files, or from the README; not guessed | `run_setup.extra_requirements`, `run_setup.constraints` (with `constraints_source`) |
| `readme_pin` | a version pin that the README states (a package version or a Python version among the images 3.8, 3.9, 3.11) | the same keys, or `python_version` |
| `output_redirect` | outputs and intermediate files go to `/workspace/output` instead of into the repository, by a command argument or an environment variable that the repository's own code or README defines. The repository stays read-only | `run_setup.args`, `run_setup.env` |
| `working_dir` | the correct working directory (relative to the repository root) | `run_setup.working_dir` |
| `data` | an open data download that the README names, made beforehand on the host and mounted read-only (the logic of `scripts/fetch_data.py`; a new download is a `data` entry of the run setup) | `run_setup.data` |

**Forbidden, without exception:**

- changing the source code of the paper (code, configuration files in the repository, data in the repository, the README command's
  script);
- shortening anything that the paper's command runs: hyperparameters, epochs, iterations, number of runs, number of samples, size or
  number of data items, early stopping, a smaller model. Not for the time limit and not for any other reason;
- changing the command after seeing a result in order to show that it "ran" (a flag that makes the paper skip its experiment, a
  dry run, a different script);
- a writable copy of the repository, a wrapper script, a patch, or a monkey-patch;
- raising a limit of section 6 (a `TIMEOUT` or an `OOM_KILLED` stays the result), the network in the run phase (the run phase has
  `--network none`), and running third-party code on the host.

A failure that none of the five kinds can address (for example a script that needs a GPU, a hard-coded path in the source, or a
package version that no available Python image can install) is recorded as `not_repairable` with the log line, and the candidate
stops there.

## 4. The data of a risky candidate

A risky candidate qualifies only if **all** hold:

1. the README (at the pinned commit) gives a command or a URL that fetches the data (a plain HTTP(S) address, or Google Drive,
   including a Google Drive folder), without an account, a payment, a form, or a license acceptance;
2. the **size is found out first** (a `HEAD` request, the Google Drive metadata, or the README), before any download;
3. a single file is at most **3 GB**, and the total download over all candidates of round 2 is at most **20 GB**. A candidate that
   would pass either limit is skipped, and the reason (and the size) is written to `eligibility.json`;
4. the download runs **on the host**, into `.data_cache/<paper_id>/` (ignored by git), is unpacked by the safe extractor of
   `scripts/fetch_data.py` (no absolute paths, no `..`), and is mounted **read-only** into the sandbox. Downloaded data is
   untrusted: nothing is unpickled, loaded with `torch.load`, or executed on the host.

The same download rules hold for a `data` repair of a round-1 candidate; the total of 20 GB counts all of them.

## 5. Number of repairs, and the pass definition

**At most two repair rounds per candidate.**

- Repair 1 corrects the error of the first attempt (for the 14 of round 1: the error recorded in round 1).
- Repair 2 corrects the **new** error that appears after repair 1.
- A **third** error stops the candidate: it is recorded as "did not run even with repair", with the three log lines.
- For a risky candidate there is no round-1 attempt. Its first round-2 run is the README command with the README's data mounted;
  that run is reported as its own "first attempt with data" and is followed by at most the same two repairs.
- A `TIMEOUT` and an `OOM_KILLED` are results, not errors to repair (section 6).

**A candidate passes** by the same criterion as round 1 (`docs/CANDIDATE_RUNS.md` section 5), all three of:

1. the dependency installation status is `INSTALLED` or `SKIPPED`;
2. the run phase has status `COMPLETED` and exit code 0 (a valid run: `docker_used` and `isolated` are true);
3. the output has at least one numeric metric line (the pattern of `scripts/demo_set.py`: a name, `:` or `=`, a number with a
   decimal point).

In addition, **for every passing candidate** the record states which table of the paper the output is compared with: the **table,
the row and column, and the number of the paper**, next to the printed value of the output (found in the text of the paper in
`data/pdfs/`, which is ignored by git, by an exact match of the printed number). Two outcomes:

- **table match**: a number of the output equals a number in a table of the paper, with the table, row and column named;
- **metric, no table match**: "metric exists, no table match". This **also counts as a pass**, and it is shown in a separate
  column.

A table match shows that two numbers are equal in text, not that they mean the same thing; whether the output is comparable with
the table is for a person to decide and is "not verified" until then.

## 6. Limits

| Setting | Value |
|---|---|
| Memory | `--memory 50%` of the host's RAM |
| CPUs | `--cpus 4` |
| Run phase time limit | **3600 s** (a real run; round 1 used 1800 s, and a record says which limit it was made under) |
| Install phase time limit | **1800 s** |
| Network | none in the run phase; the install phase bundles wheels on the host and installs them offline, as in round 1 |
| Parallel runs | **one** sandbox run at a time (no CPU contention); preparation of the next candidate (data download, research of requirements) may happen during a run |

A time limit is **not** raised by a repair, and a `TIMEOUT` is recorded as the result of that attempt.

## 7. The order

The 14 round-1 candidates first, in the order of the lists' status: `ready` (cand_001 to cand_009), then `fixable`
(cand_010 to cand_012; cand_013 is `command_incomplete`), then `two_step` (cand_025). Then the qualifying risky candidates in
the order of their ids. Every 3 to 4 candidates are merged in one pull request after `ruff check .` and `pytest`.

## 8. The records

- `data/candidates/round2/<paper_id>/`: the logs of every attempt (local paths replaced by `<REPO>` and `<HOME>`, long logs
  shortened), and **`repair_log.json`**: the list of attempts, each with `attempt` (0, 1, 2), the error line, the repair kind and
  its reason, the change, and the result; plus `table_match` for a pass.
- `data/candidates/round2/evaluation.json`: the result of every candidate, written after each one.
- `data/candidates/runs/` (round 1) is read only and is not touched.
- Third-party code runs only inside the sandbox container. For every passing candidate the PDF of its paper is downloaded to
  `data/pdfs/` (ignored by git, never committed).

## 9. What is reported

Three counts, kept apart, each with its **Wilson 95 % interval computed by a script** from the stored records
(`scripts/candidates_build.py`, the round-2 section):

1. **First attempt** (round 1, no repair): 0 of 14. Fixed; it is not run again.
2. **With repair** (round 2): K of the same 14 that passed after one or two repairs, each listed with the repairs it needed.
3. **Total tried**: K of N, where N is the 14 plus the risky candidates that were run in round 2.

Also: a table of the failure causes (the classifier of `cli.py diagnose`), the candidates stopped as `not_repairable` or by the
third error, the risky candidates that were skipped and why, and for every pass the command, the duration, the metric lines, and the
table match. Every number comes from a script and a stored record.

The sentence that goes with all of it: **"This is a selected list of candidates, not a representative sample; K / N is not a
success rate."**

## 10. Amendment of 2026-10-24 (before the run of cand_011): a sixth repair kind

Round 1 showed that the install phase installs **every** requirements file of a repository together. `cand_011` holds three
(`Real_exp_requirements.txt` and `synthetic_exp_requirements.txt` pin `joblib==1.4.0`, `requirements_pate.txt` pins
`joblib==1.4.2`), and the install fails with `ResolutionImpossible`. Its README says to install `synthetic_exp_requirements.txt`
for the command that is run. The amendment adds one kind to the table of section 3:

| Kind | What it is | Where it is applied |
|---|---|---|
| `requirements_file` | only the requirement file(s) that the README names for the command are installed, instead of every requirement file of the repository. The files are not edited and no pin is changed | `repair_log.json` setup key `requirements_files` (a list of repository paths), applied by `FilteredStager` in `scripts/candidate_round2.py` |

Everything else in this document, including the forbidden list, the limit of two repairs, and the 20 GB and 3 GB data limits,
is unchanged. No round-2 run has been made under this kind before this section was merged, and the 12 candidates already
closed were closed under the five kinds; none of them is re-opened by this kind (their reasons do not involve conflicting files).

## 11. Clarification of 2026-10-24 to section 10

The first implementation of `requirements_file` filtered only the host-side bundling; the install phase of the container installs
every `*requirements*.txt` in the repository folder, so it still read the conflicting files (the first attempt of `cand_011` failed
on `absl-py==2.1.0` of a file the README does not name). That attempt is a **fault of the harness, not a result of the candidate**:
its record is kept as `attempt_1_harness_fault` and is not counted as a repair. The fix: the requirement files that are not named
are removed from the **staged copy** (the clone made for the run, never the repository on GitHub) before the bundling, so that both
phases see the same list. Nothing else in the staged copy is changed.
