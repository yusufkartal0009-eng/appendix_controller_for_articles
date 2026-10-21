# Demo set: how light, easy-to-analyse papers are chosen

Date written: 2026-10-21. Issue #421. This document is written and merged **before any candidate repository of the pool below
has been listed or opened**. At the time of writing no search of this document has been run. The rules are mechanical on
purpose: a script applies them and a reader can re-check them.

## 1. What this set is, and what it is not

The owner wants papers for the dashboard that **run fast, bring their own data, and are easy to analyse**. This is a
**demo set**. It is chosen on purpose, and it is **not a random sample** of papers. Therefore:

- **Nothing in this set is a success rate.** The share of candidates that pass is a property of these rules and of this pool,
  not of machine learning papers, and it is never to be quoted as the reproducibility of the field.
- Only the papers that pass the run test (K1, section 4) are shown. They are not representative of the pool they came from.
- The candidates are not replaced or repaired after a failed run (section 4).
- Whatever this set shows on the dashboard has to carry this label: "demo set, hand-picked rules, not a success rate".

The set is separate from `data/seed_papers.json` and from `data/corpus_expansion/papers.json`. Neither file is changed.

## 2. The pool and its order

The pool is the union of the first 100 results (default order, "best match") of these eight GitHub repository searches, run
once on the day of selection and stored unchanged, with the date and the exact query strings, in `data/demo_set/pool.json`.
Each query is the topic plus the common part:

    topic:<topic> arxiv.org in:readme language:Python archived:false fork:false size:<20000

with `<topic>` in this order: `scikit-learn`, `tabular-data`, `time-series`, `classification`, `clustering`,
`anomaly-detection`, `gradient-boosting`, `reproducibility`. (`size:<20000` is the GitHub search qualifier, in KB.)

Duplicates are removed (case-insensitive). The candidates are then **ordered by the SHA-256 hash of the lower-case
`owner/name`**, ascending. No other ordering is used: not stars, not date, not content.

## 3. The static rules S1 to S6

Candidates are checked in the hash order. Each candidate is checked against S1 to S6 in this order; the **first rule it fails**
is recorded as its reason in `data/demo_set/evaluation.json`. Only repository metadata, the README, a few named files, and the
paper's text are used.

| Rule | A candidate passes when |
|---|---|
| S1 Repository | It is public, Python is its main language, it is not archived, it is not a fork, and GitHub's `license.spdx_id` is in `ALLOWED_LICENSES` of `src/config.py`. |
| S2 Run command | The README holds a fenced code block with a line that starts with `python ` followed by a path to a `.py` file that exists in the repository at the pinned commit. The **first** such line is the run command, taken verbatim with its arguments (backslash continuations joined, a trailing shell comment removed, `setup.py` lines skipped as install commands: the same function as R3 of `docs/CORPUS_EXPANSION.md`). |
| S3 No GPU | Neither the README nor the repository's requirement files (`requirements*.txt`, `setup.py`, `environment.yml`, `pyproject.toml`) contain `gpu` or `cuda` (case-insensitive), and the run command has no GPU option. |
| S4 Size | The GitHub API `size` is at most 100,000 KB and `.gitattributes` has no `filter=lfs` line. |
| S5 Paper | The README links an arXiv paper (`arxiv.org/abs/<id>` or `arxiv.org/pdf/<id>`) and the paper's text (pypdf) has at least two table captions of the form `Table <n>` at the start of a line and at least 20 numbers with a decimal point (the counting of R6 in `scripts/corpus_expansion.py`). |
| S6 New | The repository is not in `data/seed_papers.json` and not in `data/corpus_expansion/papers.json`, and the paper's arXiv id is not in either file, and no earlier selected candidate uses the same repository or paper. |

The pinned commit is the head of the default branch on the day of selection. A candidate that passes S1 to S6 enters the
run test in the same order.

## 4. The run test K1

Every candidate that passes S1 to S6 is run **once**, in the hash order, **exactly as the README says**: no correction, no
extra requirement, no wrapper, no edit of the paper's code or data. The run is made as `scripts/run_pilot.py --pilot4` makes
it (`docs/PILOT_4.md` sections 2 and 3: the Docker sandbox, `--network none` in both phases, the repository's own requirement
files, the README command), with these settings:

| Setting | Value |
|---|---|
| Corpus file | `data/demo_set/papers.json` (all candidates that passed S1 to S6 are written there, in the order they are run) |
| Memory | `--memory 50%` of the host's RAM |
| CPUs | `--cpus 4` |
| Run time limit | **600 s** for the run phase (instead of the 14400 s of Pilot 4). The install phase keeps its limit. |
| Network | None, in both phases |
| Attempts | One per candidate |

A candidate **passes K1** only when all three hold:

1. the dependency installation status is `INSTALLED` or `SKIPPED`;
2. the run phase has status `COMPLETED` and exit code 0 (a valid run: `docker_used` and `isolated` are true);
3. the run's `stdout.log` or `stderr.log` has at least one **numeric metric line**: a line with a name, a `:` or `=`, and a
   number with a decimal point (the regular expression is in `scripts/demo_set.py`).

A candidate that does not pass K1 is **not replaced, not repaired and not run a second time**. It is skipped, and the reason
is recorded with a category (`install`, `run`, `timeout`, `memory`, `no_metric_line`, `harness`, `staging`) and the deciding
log line.

Downloaded code is untrusted data. It is only ever executed inside the sandbox container, never on the host.

## 5. When the search stops

The run test goes through the passing candidates in the hash order and stops at the first of:

- **5 candidates have passed K1**, or
- **30 runs** have been made, or
- **2.5 hours** have passed since the start of the run test, or
- the candidates that passed S1 to S6 are used up.

If fewer than 5 candidates passed, the document says how many, and the set is smaller. There is no second pool and no
loosening of a rule.

## 6. Limits that are known before the first search

- The pool is biased: repositories that GitHub's search returns for these topics, with `arxiv.org` in the README, small
  (under 20 MB), and without a GPU mention. It misses papers without a topic tag or without a README link.
- K1 selects for papers that run in 10 minutes without help. A paper that fails K1 may be reproducible with a correction;
  this set says nothing about that.
- The first `python` line of a README may be a data preparation step, an example, or a documentation checker; K1 runs it as
  written. A pass shows that this command ran and printed a number, not that the paper's main result is reproduced.
- A "numeric metric line" is a text pattern. It can match a log line that is not a result (a progress bar, a timing). The
  results section therefore names the table and the number of the paper that each shown metric is meant to correspond to,
  and says where that match was **not verified**.
- No claim of any paper is accepted by this set. Accepting a claim is the owner's decision alone.
