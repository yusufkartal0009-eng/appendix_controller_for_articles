# External validation: do the system's verdicts agree with referees?

Date written: 2026-10-17. Issue #383. This document is written and committed (its pull request is open and
not merged, because GitHub Actions cannot run; the commit time is the evidence) **before any article, repository, or review
of the pool below has been opened**. What had been looked at when it was written: the list of top-level directory names of
the repository `ReScience/articles` (72 directories), the names of the three files in one directory (`article.pdf`,
`article.yaml`, `article.bib`), and the **field names, not the values**, of one `article.yaml` (`type`, `language`, `code`,
`review`, `replication`, `data`, `domain`, `keywords`, `dates`, and others). No article text, no code repository, no review
thread, and no verdict was read. The rules are mechanical so that a script and a reader can check them, and they leave no
room to prefer an article because it looks likely to run or to agree.

## 1. The question and what is promised

Until now the project measured whether its own tool can install and run papers (Pilots 1 to 4) and whether it scores runs
the way its rubric says. Nobody outside the project has said whether a score is *right*. ReScience C is a journal that
publishes replications; its reviewers are asked to run the authors' code and check that the replication reproduces the
results. An article that was **accepted and published** there is therefore an article for which **external people found the
results reproducible**. This document asks: for such articles, does the system's verdict agree?

Promises:

1. **Whether an article's code installs or runs is never looked at during selection.** An article that passes the rules is
   taken in the order of section 3, and an article whose run fails later is **not replaced** and **not removed from the
   denominator**.
2. The agreement is reported **per article, with its reason, including every disagreement** (section 7). A disagreement is
   investigated and classified (system error, article or setting problem, or unknown); it is not hidden and not tuned away.
3. The settings are fixed here before the runs (section 5). They are not changed after a result.

## 2. The pool and its order

The pool is the set of **top-level directories of `ReScience/articles`** (GitHub, "ReScience C published articles") on the day
of selection, retrieved once and stored unchanged in `data/external_validation/pool.json` with the date and the commit of
that repository. Each directory holds `article.yaml`, `article.pdf`, and `article.bib` of one published article. The
directories are **ordered by the SHA-256 hash of the directory name** (ascending), a fixed pseudo-random order that does not
depend on date, topic, or content. No other pool and no other ordering is used; articles of other venues (for example the
`MLRC` repository) are not in the pool.

## 3. The rules

The articles are checked in the hash order. Each is checked against the rules E1 to E8 in this order; the **first rule it
fails** is recorded as its reason (`data/external_validation/evaluation.json`) and the next article is taken. The first
**eight** articles that pass all rules are the selection (fewer if the pool ends first; the pool is not widened). The rules use
only the files of the article's directory, the metadata of the code repository on GitHub, its README and requirement files,
and the article PDF's text.

| Rule | An article passes when |
|---|---|
| E1 Accepted and reviewed | `article.yaml` parses, has a `review` entry with a `url` that points to GitHub, and has `article.pdf` in its directory. Publication in ReScience C is the evidence that the reviewers found the results reproducible; the review text itself is **not read** for selection. |
| E2 Python | The `language` field of `article.yaml` (a string or a list), in lower case, contains `python`. |
| E3 Code repository | The `code` entry of `article.yaml` has a `url` of the form `https://github.com/<owner>/<repo>` (optionally followed by a path, `.git`, or `/tree/<ref>`); the repository is public; Python is its main language; and it is not archived. The pinned commit is the commit named by `/tree/<ref>` or `/releases/tag/<tag>` in the URL if there is one, otherwise the head of the default branch on the day of selection (full SHA in `papers.json`). |
| E4 Run command | The README at the pinned commit holds a fenced code block with a line that starts with `python ` followed by a path to a `.py` file that exists in the repository at the pinned commit. The **first** such line is the run command, taken verbatim with backslash continuations joined and a trailing shell comment removed; a line whose script is `setup.py` is skipped (`docs/CORPUS_EXPANSION.md` R3 and amendment 4). |
| E5 No GPU | Neither the README nor the repository's requirement files (`requirements*.txt`, `setup.py`, `environment.yml`, `pyproject.toml`) contain `gpu` or `cuda` (case-insensitive), and the run command has no GPU option. |
| E6 Size and license | The GitHub API `size` of the repository is at most 100,000 KB, `.gitattributes` has no `filter=lfs` line, no size stated in the README (a number followed by MB or GB) is 500 MB or more, and GitHub's `license.spdx_id` is in `ALLOWED_LICENSES` of `src/config.py`. |
| E7 Article text | The text of `article.pdf` (pypdf) has at least two table captions of the form `Table <n>` at the start of a line and at least 20 decimal numbers inside the table pages, so that the article has numbers of its own to compare. |
| E8 New | The repository is not in `data/seed_papers.json` or `data/corpus_expansion/papers.json`, and no earlier selected article uses the same repository. |

The data size limit of the task is E6: **at most 100 MB of repository (data included), nothing larger stated in the README**,
and no data download is part of the first attempt (the sandbox has no network).

## 4. After the eight are chosen

- Each selected article becomes an entry of `data/external_validation/papers.json` (a file of its own; `data/seed_papers.json`
  is not touched) with the fields of `data/corpus_expansion/papers.json` plus: `article_yaml_url`, `review_url` (the
  referees' report; this is the **reference** "expected verdict: reproducible"), `article_pdf_url`, and `article_pdf_sha256`.
  The paper ids are `paper_201` and following.
- `scripts/verify_corpus.py data/external_validation/papers.json` is run on the entries. An entry that fails it is
  eliminated with the reason recorded, and the next article in the hash order that passes E1 to E8 takes its place, before any
  run (as in `docs/CORPUS_EXPANSION.md` section 4).
- The selection reason of every article (the rules it passed, and the rank in the order) is written to the document by a
  script, as in `docs/CORPUS_EXPANSION.md` section 7.

## 5. The runs

The protocol is **`docs/PILOT_4.md`** (written before any result was seen), with these two differences, fixed now:

| Setting | Value |
|---|---|
| CPUs | **8** (`--cpus 8`); the record says `cpus_override`. Pilot 4 used 2. |
| Records | `data/external_validation/runs/<paper_id>/` |

Everything else is Pilot 4: the README command as written, Python 3.11, no network, read-only repository, 50% of the host's
RAM, 3600 s for the install phase and **14400 s for the run phase**, one first attempt and at most one correction round limited
to what the first attempt's logs justify. The runs are **sequential**. A failed article stays in the table with its failure
category (`scripts/categorize_pilot_failures.py`).

## 6. Claims

The claims of an article are the numbers of **its own results tables**, taken from `article.pdf` (the replication's numbers, not
the numbers of the original paper that it replicates), with a quote of the page.

- Extraction is `scripts/auto_extract.py` (`docs/AUTO_CONSENSUS.md`): three independent passes in blind packets, in an open
  mode: each pass lists the numeric results of the article's own tables, in table order, at most 12 per article, each with
  metric name, dataset, model variant, page, and an exact quote. The passes **do not see any run output**, and extraction is
  done before the article's run is scored.
- A claim becomes a **candidate** (`verified_by = auto-consensus`) when at least two passes give the same normalized value and
  each passes the quote check. A candidate is **not** an accepted claim and is never marked accepted. These candidates are
  stored in a database file of this validation only (`--db-url`), not in the project database.
- Scoring is `cli.py score <paper_id> --from-run <run folder> --claims auto-consensus`, so the score is labeled as one on
  unreviewed candidates. The comparison of a claim with a run needs the run's own output to name the metric; a claim that the
  output does not contain is not compared, and a run with no compared claim is reported as such (`nothing was compared`).

## 7. What counts as agreement

The expected verdict of every selected article is **reproducible** (the referees' result). The system's verdict is the status
label of its score:

| System status | Reading | Agrees with "reproducible" |
|---|---|---|
| `Verified` or `Partially Verified` | the system found the results reproduced (fully or mostly) | **yes** |
| `Needs Review` with *nothing compared* | the code ran, but no claim could be compared | **inconclusive** (neither agreement nor disagreement) |
| `Needs Review` with claims compared, or `Failed` | the system found the results not reproduced, or the run failed | **no** |

For every article the result table shows: referees' reference (link), the failure category if any, the number of claims
extracted and compared, the status, the reading above, and a **reason**. Every "no" and every "inconclusive" is investigated
and gets one of: *system error* (a defect of this tool: staging, install, metric extraction, matching), *article or setting*
(the article needs something the sandbox does not give: a GPU, network, data, a longer run), or *unknown*. The investigation is
done after the table is fixed and does not change the table.

## 8. Limits stated in advance

- **No negative cases.** Every selected article is expected to be reproducible. The comparison can show that the system fails
  to confirm reproducible work (false alarms); it cannot show that the system would catch work that does **not** reproduce.
  Agreement here is **not** a measure of the system's accuracy.
- **Publication is the reference, not a re-check.** Reviewers of ReScience C are asked to run the code; the review text is not
  read for selection, so an article accepted for another reason would still count. The reference may differ from the pinned
  commit: the reviewed code is the one of the article's snapshot, and the pinned commit may be newer.
- **A small, biased sample.** At most eight articles from one journal, Python only, no GPU, small repositories, a README with
  a `python` line. The result is for articles selected this way.
- **The README command is not the article's experiment.** As in Pilot 4, the first `python` line may run a demo or a data
  step. A run that succeeds then says little about the table of the article.
- **Claims depend on matching.** A claim can be compared only if the run prints it under a name that the metric extractor
  reads. Many articles will print nothing of the kind, which gives "inconclusive", not "agreement".
- **The machine.** Runs are on the owner's Windows machine with 8 CPUs; other work on the machine during a run is not
  controlled and run times are not compared with other pilots.
