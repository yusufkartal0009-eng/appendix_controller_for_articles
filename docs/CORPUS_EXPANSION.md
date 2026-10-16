# Corpus expansion: how six new papers are chosen

Date written: 2026-10-16. Issue #333. This document is written and merged **before any candidate paper has been listed or
opened**. At the time of writing no repository of the pool below has been retrieved. The rules are mechanical on purpose:
they can be checked by a script and re-checked by a reader, and they leave no room to prefer a paper because it looks
likely to run.

## 1. Why, and what is promised

The corpus of the project has six papers (`data/seed_papers.json`), which were corrected and reduced before the pilots
(`docs/report/REPORT.md` section 5.1). A success rate on six papers that were also used to design the tool says little about
new papers. Pilot 4 (`docs/PILOT_4.md`, written after this document) runs **six new papers** once, under fixed limits, and
reports the success rate. That rate is worth reporting only if the papers were **not chosen because they run**.

The promise: **whether a paper installs or runs is never looked at during selection** (no install, no run, no look at issues
or at what others report about the repository). A paper that passes the rules is taken in the order below, and a paper that
fails a run later is not replaced.

The six papers are written to `data/corpus_expansion/papers.json`. They are **not** added to `data/seed_papers.json`.

## 2. The pool and its order

The pool is the union of the first 100 results (default order, "best match") of each of these GitHub repository searches, in
this order, run once on the day of selection and stored unchanged in `data/corpus_expansion/pool.json` with the date:

1. `topic:tabular-data language:Python arxiv.org in:readme`
2. `topic:tabular-deep-learning language:Python arxiv.org in:readme`
3. `topic:gradient-boosting language:Python arxiv.org in:readme`
4. `topic:scikit-learn language:Python arxiv.org in:readme`

Duplicates are removed (section 6 adds stages 2 and 3 for the case that fewer than six papers pass). The candidates are then **ordered by the SHA-256 hash of the lower-case `owner/name`** (ascending), a
fixed pseudo-random order that does not depend on stars, date, or content. No other ordering is used.

## 3. The rules

Candidates are checked in the hash order. Each candidate is checked against every rule in the order R1 to R7; the **first
rule it fails** is recorded as its reason (`data/corpus_expansion/evaluation.json`), and the next candidate is taken. The
first six candidates that pass all rules are the selection. All rules use only the repository's metadata, its README, the
files named by the rules, and the paper's text at the commit and on the date of selection.

| Rule | A candidate passes when |
|---|---|
| R1 Repository | It is public, Python is its main language, and it is neither archived nor a fork. |
| R2 License | GitHub's `license.spdx_id` is in the allowed list of `scripts/verify_corpus.py` (`ALLOWED_LICENSES` in `src/config.py`). |
| R3 Run command | The README holds a fenced code block with a line that starts with `python ` followed by a path to a `.py` file that exists in the repository at the pinned commit. The **first** such line in the README is the run command, taken verbatim with its arguments. |
| R4 No GPU | Neither the README nor the repository's requirement files (`requirements*.txt`, `setup.py`, `environment.yml`, `pyproject.toml`) contain `gpu` or `cuda` (case-insensitive), and the run command has no GPU option. |
| R5 Size | The GitHub API `size` of the repository is at most 100,000 KB, `.gitattributes` has no `filter=lfs` line, and no size stated in the README (a number followed by MB or GB) is 500 MB or more. |
| R6 Paper | The README links an arXiv paper (`arxiv.org/abs/<id>` or `arxiv.org/pdf/<id>`); the arXiv page title is the entry's title; and the paper's text (pypdf) has at least two table captions of the form `Table <n>` at the start of a line and at least 20 numbers with a decimal point. |
| R7 New | The repository and the paper are not in `data/seed_papers.json`, and no earlier selected candidate uses the same repository. |

The pinned commit is the head of the default branch on the day of selection (full SHA in `papers.json`).

## 4. After the six are chosen

- `scripts/verify_corpus.py data/corpus_expansion/papers.json` is run on the six entries (it takes the corpus file as its
  argument; `data/seed_papers.json` is its default). A candidate that fails it (title, repository, license, script) is
  eliminated, the reason is recorded in `evaluation.json`, and **the next candidate in the hash order that passes R1 to R7
  takes its place**. This is done before any run.
- The entries have the fields of `data/seed_papers.json` plus `run_command` (the README line of R3) and `readme_url`. They
  carry no expected claims: Pilot 4 does not extract or score claims (`docs/PILOT_4.md`).

## 5. What is not considered, and the limits

- Not considered: whether the paper installs or runs, how popular the repository is, how recent, how large the paper's
  results are, and whether the topic interests the owner. No candidate is skipped or added by hand.
- **The pool is biased.** It contains repositories that GitHub's search returns for these topics and that mention arXiv in the
  README. It does not contain papers without a topic tag, without a README link to arXiv, or without a Python repository.
  The success rate of Pilot 4 is a rate **for papers selected this way**, not for machine learning papers in general.
- R3 to R6 are text rules. A README line can be stale, incomplete, or need data that the rule does not detect (R5 sees only
  sizes that the README states). Such cases are not filtered: they are the kind of obstacle that the pilot is meant to find.
- R4 rejects any README that merely mentions a GPU, which also rejects papers that run well without one.
- The selection is one draw of six from this pool: another day gives another pool and other papers.

## 6. Amendments (2026-10-16, issue #338)

The rules were applied once (issue #337) and showed three problems **before any paper was installed or run**. This section
amends the document; sections 1 to 5 stay as they were written. The first output is kept unchanged in
`data/corpus_expansion/first_attempt/`. These amendments were written after the author had seen the **stage 1** result
(the pool of 89 candidates, 3 of which passed under the first version of the script), so they are not blind to stage 1; they
are written before **stages 2 and 3** were retrieved.

1. **R7 means the paper too.** Section 3 says the repository **and the paper** must be new. The first version of the script
   checked only the repository, and one selected candidate was the paper of `paper_006` (arXiv 2106.01342, SAINT) in another
   repository. The script now also compares the arXiv id with the papers of `data/seed_papers.json` and with the papers
   already selected.
2. **The run command.** A command line that ends with a backslash continues on the next line, and the lines are joined into
   one command. A shell comment at the end of a line (a space, `#`, and the rest) is not part of the command. Neither
   change alters whether a candidate passes R3: the rule only needs the first line to start with `python ` and a script that
   exists.
3. **Stages for a pool that is too small.** Stage 1 (section 2) gave 89 candidates and fewer than six papers. If fewer than six
   papers have passed after the candidates of a stage, the candidates of the next stage are evaluated, in this order, each
   stage by the same rules and the same hash order (names already in an earlier stage are left out). A stage is retrieved once,
   on the day it is needed, and stored unchanged (`pool_stage2.json`, `pool_stage3.json`). The queries are fixed here, before
   they were run:

   Stage 2:
   - `topic:machine-learning language:Python arxiv.org in:readme`
   - `topic:classification language:Python arxiv.org in:readme`
   - `topic:regression language:Python arxiv.org in:readme`
   - `topic:xgboost language:Python arxiv.org in:readme`

   Stage 3:
   - `topic:deep-learning language:Python arxiv.org in:readme`
   - `topic:data-science language:Python arxiv.org in:readme`
   - `topic:random-forest language:Python arxiv.org in:readme`
   - `topic:feature-selection language:Python arxiv.org in:readme`

   If fewer than six papers have passed after stage 3, Pilot 4 runs the papers that passed and says that the selection was
   short; no further stage is added.

The wider stages reach papers that are less specific to tabular data. That is a change of the scope of the sample, and the
success rate of Pilot 4 is a rate for papers selected this way.
