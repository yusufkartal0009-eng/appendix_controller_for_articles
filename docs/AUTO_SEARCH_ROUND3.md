# Automatic search, round 3: runs checked against the paper text

Date written: 2026-10-25. Issue #469. This document is written and merged **before any pool of this round has been searched,
before any candidate has been listed, and before any candidate has been run**. The rules are mechanical on purpose: a script
applies them and a reader can re-check them. They were written without looking at any candidate list.

## 1. Why this round exists, and what it is not

In earlier rounds, no run of a real paper's code produced output that matched the paper's text (demo set: 1 of 22 runs passed
the run test and none of its printed numbers occurred in the paper; the repair round of the 29-candidate list: 1 of 14 passed
after repair, and its output did not match the paper's table). This round runs many more candidates, each exactly as its README
says, and measures automatically whether numbers printed by the run occur in the text of the paper (test K2, section 5).

It is **not** a sample of papers and **not** a success rate (section 9). Nothing here accepts a claim: accepting a claim is the
owner's decision alone. A candidate that passes K2 is a **match candidate**; it is never called verified, because a number can occur
in a paper by chance and because that a printed number means the same thing as the number in the paper is not checked.

The files of earlier rounds (`data/seed_papers.json`, `data/corpus_expansion/`, `data/demo_set/`, `data/candidates/`) are not
changed. This round writes only to `data/auto_search3/`.

## 2. The pool and its order

The pool is the union of the first 100 results (default order, "best match") of GitHub repository searches (`gh api
search/repositories` or the same call through `scripts/corpus_expansion.py`), run once per query on the day of selection and
stored unchanged, with the date and the exact query strings, in `data/auto_search3/pool.json`. Each query is

    arxiv.org in:readme language:Python archived:false fork:false size:<30000 topic:<topic>

(`size:<30000` is the GitHub search qualifier, in KB). The topics, in this order:

- **Stage 1:** `statistics`, `bayesian`, `optimization`, `causal-inference`, `survival-analysis`, `regression`, `simulation`,
  `signal-processing`, `computational-biology`, `physics`, `graph-algorithms`, `recommender-system`, `symbolic-regression`,
  `feature-selection`, `dimensionality-reduction`, `probabilistic-programming`.
- **Stage 2** (used only when the candidates of stage 1 are used up before a stop condition of section 6 holds):
  `numerical-methods`, `monte-carlo`, `differential-equations`, `econometrics`, `bioinformatics`, `chemistry`, `neuroscience`,
  `ecology`, `epidemiology`, `game-theory`, `information-theory`, `kernel-methods`, `ensemble-learning`, `time-series-forecasting`,
  `topic-modeling`, `nlp`.

Duplicates are removed (case-insensitive). The repositories of earlier rounds are **removed from the pool before ordering**: every
repository in `data/demo_set/pool.json` (the whole pool of the demo set, evaluated or not), in `data/candidates/` (all files),
in `data/seed_papers.json` and in `data/corpus_expansion/papers.json`. The remaining candidates are ordered by the **SHA-256 hash of the
lower-case `owner/name`**, ascending. Stage 2 is searched and stored as a second block of the same file only when it is needed; its
candidates are ordered the same way and come after all candidates of stage 1. No other ordering is used: not stars, not date, not
content.

## 3. The static rules S1 to S6

The rules are those of `docs/DEMO_SET.md` section 3, unchanged, applied in this order; the **first rule a candidate fails** is
recorded as its reason. Only repository metadata, the README, a few named files and the paper's text are used.

| Rule | A candidate passes when |
|---|---|
| S1 Repository | Public, Python is the main language, not archived, not a fork, and GitHub's `license.spdx_id` is in `ALLOWED_LICENSES` of `src/config.py`. |
| S2 Run command | The README holds a fenced code block with a line that starts with `python ` followed by a path to a `.py` file that exists in the repository at the pinned commit. The **first** such line, verbatim with its arguments (backslash continuations joined, a trailing shell comment removed, `setup.py` lines skipped), is the run command. |
| S3 No GPU | Neither the README nor the requirement files (`requirements*.txt`, `setup.py`, `environment.yml`, `pyproject.toml`) contain `gpu` or `cuda` (case-insensitive), and the run command has no GPU option. |
| S4 Size | The GitHub API `size` is at most 100,000 KB and `.gitattributes` has no `filter=lfs` line. |
| S5 Paper | The README links an arXiv paper (`arxiv.org/abs/<id>` or `arxiv.org/pdf/<id>`) and the paper's text (pypdf) has at least two lines that start with `Table <n>` and at least 20 numbers with a decimal point. |
| S6 New | The repository is not in the seed, not in an earlier round (section 2), and the paper's arXiv id is not in the seed or in `data/corpus_expansion/papers.json`; no earlier candidate of this round uses the same repository or the same paper. |

The pinned commit is the head of the default branch on the day the candidate is checked. The static rules are applied in the hash
order, one candidate at a time; a candidate that passes S1 to S6 enters the run test at once (section 4). This lets the sandbox work
on one candidate while the next candidates can be checked statically.

## 4. The run test K1

Every candidate that passes S1 to S6 is run **once**, **exactly as the README says**: no correction, no extra requirement, no wrapper,
no edit of the paper's code or data. The run is made as `scripts/run_pilot.py --pilot4` makes it (`docs/PILOT_4.md` sections 2 and 3:
the Docker sandbox, `--network none` in both phases, the repository's own requirement files, the README command), with these
settings:

| Setting | Value |
|---|---|
| Memory | `--memory 50%` |
| CPUs | `--cpus 4` |
| Install time limit | **1200 s** |
| Run time limit | **600 s** |
| Network | None, in both phases |
| Attempts | One per candidate |
| Parallelism | At most one sandbox run at a time |

A candidate **passes K1** only when all three hold:

1. the dependency installation status is `INSTALLED` or `SKIPPED`;
2. the run phase has status `COMPLETED` and exit code 0 (a valid run: `docker_used` and `isolated` are true);
3. `stdout.log` or `stderr.log` has at least one numeric metric line (the pattern of `scripts/demo_set.py`: a name, a `:` or `=`,
   and a number with a decimal point).

A candidate that does not pass K1 is **not replaced, not repaired and not run a second time**. The reason is recorded with a category
(`install`, `run`, `timeout`, `memory`, `no_metric_line`, `harness`, `staging`) and the deciding log line. A run whose mechanism
crashed or hung is recorded as `harness` and the search continues; fixing the mechanism is a separate change and does not re-run the
candidate.

Downloaded code is untrusted data. It is only ever executed inside the sandbox container, never on the host. Downloaded PDFs are kept
under `data/pdfs` (not tracked by git); staging folders are under `.sandbox_staging`. After each candidate, the staging, wheel and
output folders that the run created are deleted.

## 5. The match test K2

K2 is computed for every candidate whose run phase is `COMPLETED` with exit code 0 (so that K2 can be reported next to K1); a candidate
**passes both tests** only when it passes K1 and K2.

**Numbers of the run.** Numbers are taken from `stdout.log` only (not from `stderr.log`, which holds warnings and progress bars). A
number is a **meaningful number** when all of these hold:

- it has at least **3 significant digits**: after removing the sign, thousands separators, the decimal point and leading zeros, at
  least 3 digits remain; for an integer the trailing zeros are also removed first (so `100` and `5000` do not count, `1234` does);
- it is not a **year** (an integer from 1900 to 2100 with no decimal part);
- it is not part of a **version** (two or more dots between digit groups, or a number preceded by `v` or `version`);
- it is not part of a **date or a time** (`2026-10-25`, `25/10/2026`, `12:30:05`, `12:30:05.123`);
- it is not an **index or a line number** (a number in square brackets, after `#`, after the word `line`, `epoch`, `step`, `iter`,
  `iteration`, `batch`, `fold`, `seed`, `row`, `col`, or in the `:<n>:` position of a traceback or file reference);
- it is not a single-digit number (a lone digit `0` to `9`), unless it is followed by `%`.

The distinct meaningful numbers are kept in the order in which they occur, each with its line.

**Text of the paper.** The PDF of the paper (downloaded from the arXiv link of the README) is read with pypdf, page by page. The text
is normalised for the comparison: the minus variants (`−`, `–`, `‑`) are read as `-`; a decimal comma is read as a decimal point; a
thousands separator (`,`, a thin space, or `'`) between digit groups of three is removed. A number of the run occurs in the paper when
its normalised string occurs in the normalised text of a page **in the same spelling** (the same digits, the same number of
decimals; `0.50` does not match `0.5`; a leading zero may be dropped, as in `.5`), and it is **not part of a longer number** (`1.5`
does not match inside `21.55`, `1.52` or `1.5.2`) and, for a negative number, the minus sign is present.

**K2 passes** when at least **2 different** meaningful numbers of the run occur in the paper's text **and** at least one of them
occurs on a page that has a line starting with `Table <n>` (the table pages are those that count for S5). For each number found, the
page numbers (1-based) and the line of the paper around the match are stored together with the line of the run output.

A candidate that passes K2 is called a **match candidate**. A chance match is possible, mostly for numbers with few digits; K2 does
not exclude it, and a match candidate is **not** called verified. Whether a number of the output is the number of the paper's table
is decided by a person, from the stored page and line.

## 6. When the search stops

The search stops at the first of these:

- **(a)** 9 hours have passed since the start of the run (the start is written to `sabah_bekleyenler.md`);
- **(b)** 150 candidates have been run in the sandbox;
- **(c)** 8 candidates have passed both K1 and K2;
- **(d)** the free disk space is under 30 GB.

A pool that is used up is not a stop condition: the queries of the next stage (section 2) are added and the search goes on. The search
is **resumable**: the candidates that were already run are read from the stored records and skipped, so that a restarted session or
background run continues where it stopped. The reason for the stop is stored in the evaluation file.

## 7. Records

For each run candidate, `data/auto_search3/runs/<id>/` keeps `run_report.json`, the K1 and K2 result file, and short logs (long
outputs are truncated; local paths are replaced by `<REPO>` and `<HOME>`). `data/auto_search3/evaluation.json` holds every checked
candidate with its first failed rule or its run result. Records of earlier rounds are not touched.

## 8. Reporting

The report names, from a script and from the stored files only: the number of candidates tried (run in the sandbox), the number that
passed K1, the number that passed K2 and the number that passed both; the Wilson 95% interval for each proportion, computed by the
script; a table of the failure categories; and, for every match candidate, the command, the duration and the matching numbers with
their pages. No number is typed by hand.

## 9. Limits that are known before the first search

- **This is a selected and non-representative list, not a success rate.** The pool is what GitHub's search returns for these topics
  with `arxiv.org` in the README, small, and without a GPU mention; the order is a hash; the rules reject most repositories. The
  shares of candidates that pass K1 or K2 are properties of these rules and this pool, never the reproducibility of a field. The
  Wilson intervals describe only the candidates that were run.
- K1 selects for code that runs in 10 minutes as written. A paper that fails may be reproducible with a correction; this round says
  nothing about that.
- The first `python` line of a README may be a data preparation step, a demo or a help text. A pass shows that the command ran and
  printed numbers, not that the paper's main result is reproduced.
- K2 is a string match. It can match by chance, it can miss a value printed in another spelling (a different number of decimals, a
  percentage, a rounded value), and it does not know what a number means. A K2 pass is therefore a reason for a human to look, not
  evidence.
- Simulated or synthetic data in a run's output (for example a setup parameter) is labelled as simulation wherever it is reported.
- No claim is accepted by this round.
