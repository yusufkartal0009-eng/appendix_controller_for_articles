# Repro Radar — Final Report (skeleton)

> **Status: skeleton only** (#120, created 2026-10-05). Each section holds its one-line purpose, what it needs before it
> can be written, and where that evidence is (or that it does not exist yet). **No section is written before its
> evidence exists in the repository** (a merged PR, a stored run report, or a script output). Every number will come
> from a script, and every factual statement will be listed in a claim → source table.

---

## 1. Abstract

**Purpose:** summarize the problem, the method, and what the evidence supports, in at most 200 words; written last.

- **Needs:** sections 2–10.
- **Status:** not started.

## 2. Introduction

Reproducibility in empirical machine learning rests on being able to re-run a published result from the paper
and its code. The point is not new: Claerbout argued in the early 1990s that a computational result's real
scholarship is the full software environment that produced it, not the paper describing it [1]; Buckheit and
Donoho later put this plainly, that an article is advertising for the scholarship, the scholarship itself is the
code and data [2, 3]. Tool and practice collections followed [4], and so did evidence that the problem had not
gone away: a 2016 *Nature* survey described a "crisis" in research reproducibility across fields [5], and a 2019
NeurIPS program examined the state of reproducibility in machine learning specifically [6]. In deep
reinforcement learning, reproducing a published result is "seldom straightforward," because results vary with
non-deterministic benchmark environments and with variance intrinsic to the methods themselves [7] — the same
caution applies more broadly: a result can differ between runs for reasons that have nothing to do with whether
the original claim was sound.

This project's own seed corpus illustrates the problem at a small scale. Of the first 16 numerical claims
recorded from 6 papers, only 2 could be found, as printed, in the paper they were attributed to; the rest were
either not present or attached to the wrong paper or table (`docs/CORPUS_VERIFICATION.md`). Two of the six
repositories had been renamed or had a target script removed by a later rewrite of the project they belong to.
Re-running a paper is therefore not only a matter of running code: it requires reconstructing the right
environment, the right version of the code, and the right data, and checking numbers against the paper itself
rather than against a value someone wrote down from memory.

Repro Radar is an attempt to do this mechanically and honestly for a small set of tabular machine learning
papers: stage each paper's code at a pinned commit, run it inside an isolated sandbox whose isolation properties
are checked against a real Docker daemon in continuous integration (`docs/SANDBOX_ACCEPTANCE.md`), extract the
paper's own numerical claims with a verbatim-quote guard against invented matches, and score the result on a
four-tier rubric instead of a single pass/fail. As of this writing, the sandbox and the corpus verification are
checked, the six papers of the corpus have been run through the sandbox in two pilots (section 6), and
`cli.py score` scores a stored real run against accepted claims (`docs/gap_analysis.md`, finding GA-2, closed by
#136); but no run has reproduced an accepted claim, so the scoring rubric's agreement tier has not yet been exercised
on real results (section 6.3). The pilot covers tabular
ML benchmarks only; other scientific fields are out of scope for this project.

- **Sources:** [1]–[7] and every other factual statement above are listed with how they were verified in
  `docs/INTRODUCTION_SOURCES.md`, sections 1–2. That file also records what an earlier draft claimed and could
  not source, and was corrected to remove (section 3) — for example an unsourced reproducibility percentage, a
  misdated quotation, and a claim that the project covers "all scientific fields," which it does not.
- **Status:** written, from existing sourced evidence.

## 3. Related work

**Purpose:** place Repro Radar among existing reproducibility efforts and tools, and say how it differs.

- **Needs:** 5–10 sources, each checked against the original.
- **Status:** not started (no verified source list yet).

## 4. Method

### 4.1 Sandbox and threat model

Third-party paper code is untrusted by construction: it is run once, usually without being read first. Every
run happens inside a Docker container built from `docker/Dockerfile.sandbox`, under a non-root user (uid 1000,
verified check 1 of `docs/SANDBOX_ACCEPTANCE.md`), with the network disabled (`--network none`, check 2), the
root filesystem read-only (check 3), and `/tmp` and the user's home directory as size-limited `tmpfs` mounts
(2048 MiB, `noexec` on `/tmp`; `docs/DECISIONS.md` records why the home directory itself needs `exec` for
compiled extensions it loads). Resource limits are enforced and checked against real load: 2 CPUs (check 17),
6–8 GiB of memory with the container killed and the kill reported as `OOM_KILLED` rather than confused with a
timeout (checks 8 and a dedicated acceptance test), 100 processes (check 9), and a wall-clock timeout per phase
(check 4). Dependencies are installed from pre-downloaded binary wheels only — building a source distribution
would run arbitrary `setup.py` code outside the sandbox, so source-only packages are either built inside a
separate, identically isolated build-phase container (check 18) or flagged `NEEDS_SDIST_BUILD` and not built at
all (`docs/gap_analysis.md`, GA-22). A GPU is never attached unless explicitly requested (check 20) and is never
part of the counted pilot run (`docs/PILOT_2.md` section 3). Running without Docker at all is refused by
default; an explicit, logged opt-in is required to fall back to an unisolated local run (check 6). The container
shares the host kernel, so these measures reduce, not eliminate, the risk of running unknown code — this is a
property of container isolation generally, not specific to this project.

### 4.2 Reproducibility score

Each run is scored on four weighted tiers (`src/config.py`): **Tier 1**, build and install success, 35%; **Tier
2**, agreement between the paper's claimed metrics and the reproduced ones, 35%; **Tier 3**, stability across
repeated runs with different seeds, 15%; **Tier 4**, documentation and license completeness, 15%. The composite
score classifies a paper as `Verified` (≥ 85), `Partially Verified` (60–84), or lower tiers below that
(`src/scoring.py`).

Tier 2 compares each claimed metric with the reproduced one using a single default tolerance of 5%
(`DEFAULT_TOLERANCE`, `src/config.py`), applied in `src/scoring.py`: a reproduced value within 5% relative
error earns full points; for a metric claimed inside [0, 1] (accuracy, AUROC, F1) an absolute difference of up
to 0.05 also counts; within twice the tolerance earns half the points; beyond that, none. Runtime and latency
metrics, recognized by name, are judged by relative error only, because an absolute bound would let 0.02 s
become 0.06 s, a 200% error, and still pass. The scorer has no per-category tolerance (for example a tighter
bound for AUROC than for accuracy) and does not separate a hardware difference from a real divergence; a module
that was meant to do this was never connected to the scorer and was removed (#254). Tier 3's stability check uses the coefficient of variation (CV) across seeds: CV ≤ 2% is
scored as deterministic, ≤ 5% as stable, with the score falling as the variance grows.

### 4.3 Claim extraction

A claim is one number a paper reports for one metric, one dataset, one model, and one split, defined precisely
in `docs/CLAIM_SCHEMA.md` (W1, #129): the value is kept exactly as printed (`value_as_printed`, including `%`,
`±`, and any stray spacing inside the number) alongside a normalized value computed by `src/claim_schema.py`,
never typed by hand. Extraction reads the PDF's page text, cached by the file's hash (W2, #130,
`docs/PDF_TEXT_EXTRACTION.md`). No API key is currently used (decision D-004, `docs/DECISIONS.md`); instead, an
agent reads the paper text under a fixed set of rules and answers one prepared question per claim
(`docs/AGENT_EXTRACTION.md`): answer only from the given text, never guess or borrow a value from a similar
dataset or metric, and answer `not_found` with a reason when the paper does not report it. Two extraction passes
are compared by normalized value (D-005); every claim's quote must also occur verbatim in the page text,
checked by the quote guard (W4, #132, `src/quote_guard.py`) — a claim whose quote cannot be found is rejected,
not silently dropped. Accepted claims are stored with their page, quote, and extraction method (W6, #10), and
nothing reaches scoring until a person has reviewed it one by one (W7, #134, `src/claim_review.py`,
`python cli.py review-claims`). Measured against the project owner's own gold set of 18 questions over 6 papers,
this pipeline reached precision 1.0 and recall 1.0 (W5, #133, `data/claims/gold_score_pass_A.json`), including
two cases built specifically to catch a fabricated match: a dataset name ("EP3602") and a metric ("HIGGS") that
do not occur in their papers at all, both correctly answered `not_found`.

- **Sources:** `docs/SANDBOX_ACCEPTANCE.md` (all numbered checks cited above are its own verbatim evidence,
  re-run against a real Docker daemon in CI); `docs/DECISIONS.md` (D-004, D-005, and the home-directory
  `noexec` decision); `src/config.py`, `src/scoring.py` (weights, thresholds,
  tolerance rules, CV bands — read directly from the code, not retyped by hand); `docs/CLAIM_SCHEMA.md`,
  `docs/PDF_TEXT_EXTRACTION.md`, `docs/AGENT_EXTRACTION.md`; `data/claims/gold_score_pass_A.json` (the
  precision/recall numbers and the two regression cases).
- **Status:** written. This section describes the design and is not a results claim: `cli.py score` can score a
  stored real run (#136), but no run has reproduced an accepted claim yet (section 6.3).

## 5. Experimental setup

### 5.1 Corpus

The seed corpus went through two corrections before reaching its current 6 papers. The first 18 entries,
written in Week 1, were placeholders that in several cases paired a paper's title with an unrelated
general-purpose library's repository (`docs/PROGRESS.md`). These were replaced by 8 entries on 2026-09-13, but
that replacement was itself called "verified" without every entry having actually been checked; a later review
found only one paper had been (`docs/PROGRESS.md`, the 18→8 note). Two further entries were then dropped as
not fixable, leaving the 6 papers scored in `docs/CORPUS_VERIFICATION.md` today: TabPFN, FT-Transformer, TabR,
FastSK, SAINT, and DANet, each pinned to one commit of its repository.

An automated check (`scripts/verify_corpus.py`, run in CI on every push) verifies, for every entry, that the
paper title matches its arXiv or Crossref record, that the repository exists, that its declared license matches
GitHub's own license detection and is on an allow-list of open licenses, and that the pinned target script
exists at the pinned commit. As of the last recorded run, 6 of 6 entries pass this check. Passing it proves the
links, license, and script file are real; it does not prove the script runs or reproduces the paper's numbers —
each entry's row in `docs/CORPUS_VERIFICATION.md` separately tracks GPU requirements, whether its data must be
downloaded, and how many of its recorded claims could actually be found in the paper (as low as 0 of 3 for one
entry). No entry in the corpus is called "verified" as a whole; every one still carries at least one open,
explicitly marked item.

### 5.2 Sandbox limits and run setup

Every run, in both pilots, uses the same fixed resource limits: 2 CPUs, 6 GiB of memory (6 GiB swap), 100
processes, and a 3600-second timeout per phase (build, install, run), with the network disabled throughout
(`docs/PILOT_2.md` section 3). The first pilot (Pilot 1, `docs/PILOT_WEEK2.md`) ran each paper's script directly
from the repository root with no paper-specific adjustment; it showed that no paper reached its own experiment
code this way (full accounting in section 6). Each paper's `run_setup` in `data/seed_papers.json` now records,
individually, the fix that pilot found necessary: the entry command (several papers are driven through a
Jupyter notebook via `nbconvert`, not a plain script), the working directory, whether the repository needs a
writable per-run copy, which datasets must be fetched to a local cache before the run (since the sandbox has no
network), and which packages must be built from source inside an isolated build phase rather than installed as
a published wheel. This is also where each paper's Python version comes from (3.8, 3.9, or 3.11, chosen from
its own README or environment file) and where any extra install-time requirements or version constraints are
recorded, each with the reason and source for the choice next to it — not applied silently.

### 5.3 Success definitions

Three outcomes are defined precisely and used consistently across both pilots (`docs/PILOT_WEEK2.md` section
"Definitions"):

| Term | Definition |
|---|---|
| Install success | `dependency_install_status: INSTALLED` in the run report. `FAILED`, `SKIPPED` (nothing to install), and `UNKNOWN` do not count. |
| Run success | Exit code 0 of the run phase, in a run that was actually valid (staged at the pinned commit, isolated, Docker used). `TIMEOUT`, `OOM_KILLED`, and any other non-zero exit code do not count. |
| Pilot success | Install success **and** run success, together. |

Every rate (install success rate, run success rate, pilot success rate) is reported with a denominator of 6 —
every paper in the corpus, including one whose staging or run cannot even start — so a paper is never quietly
excluded from the count. A paper without pilot success is assigned exactly one failure category, decided by the
first failure in the order install → run, with the log line that decided it quoted in the pilot report.

- **Sources:** `docs/CORPUS_VERIFICATION.md` (per-entry status and checks); `scripts/verify_corpus.py` and its
  CI job (automated checks); `docs/PROGRESS.md` (the 18→8 and 8→6 corpus history); `data/seed_papers.json`
  (`run_setup`, `python_version` fields); `docs/PILOT_WEEK2.md` and `docs/PILOT_2.md` (limits and definitions).
- **Status:** written.

## 6. Results

### 6.1 Can the papers be installed and run? Pilot 1 and Pilot 2

Both pilots ran the same six papers in the real Docker sandbox and used the definitions of section 5.3 with a
denominator of 6. Pilot 1 (`docs/PILOT_WEEK2.md`, 2026-09-30, GitHub's Linux runners) ran each paper's script directly
from the repository root, on one Python version, with dependencies from its pip requirement files only. Pilot 2
(`docs/PILOT_2.md`, 2026-10-10, the owner's Windows machine with Docker Desktop and WSL2) ran each paper with its own
run setup (section 5.2), on the Python version its repository names, with the same resource limits and the GPU off.

<!-- numbers:pilot2summary:start -->
<!-- Generated by scripts/report_numbers.py from data/pilot2_runs/comparison.json; do not edit by hand. -->

Install success: 6 / 6 (1.0) (Pilot 1: 1 / 6 (0.167)). Run success: 1 / 6 (0.167) (Pilot 1: 0 / 6 (0.0)). Pilot success: 1 / 6 (0.167) (Pilot 1: 0 / 6 (0.0)).
<!-- numbers:pilot2summary:end -->

<!-- numbers:pilot2:start -->
<!-- Generated by scripts/report_numbers.py from data/pilot2_runs/comparison.json (scripts/pilot_compare.py); do not edit by hand. -->

| Measure | Pilot 1 (`data/pilot_runs/`) | Pilot 2 (`data/pilot2_runs/`) |
|---|---|---|
| Install success | 1 / 6 (0.167) | 6 / 6 (1.0) |
| Run success | 0 / 6 (0.0) | 1 / 6 (0.167) |
| Pilot success | 0 / 6 (0.0) | 1 / 6 (0.167) |
| Valid runs | 6 / 6 (1.0) | 6 / 6 (1.0) |

| Paper | Pilot 1 | Pilot 2 |
|---|---|---|
| `paper_002` | MISSING_DEPENDENCY (install) | MISSING_DEPENDENCY (run) |
| `paper_003` | MISSING_DEPENDENCY (install) | OTHER (run) |
| `paper_004` | MISSING_DEPENDENCY (run) | TIMEOUT (run) |
| `paper_005` | MISSING_DEPENDENCY (install) | OTHER (run) |
| `paper_006` | MISSING_DEPENDENCY (run) | success |
| `paper_008` | DATA_NOT_ACCESSIBLE (run) | DATA_NOT_ACCESSIBLE (run) |

| Failure category | Pilot 1 | Pilot 2 |
|---|---|---|
| `MISSING_DEPENDENCY` | 5 | 1 |
| `DATA_NOT_ACCESSIBLE` | 1 | 1 |
| `HARDWARE_GPU_REQUIRED` | 0 | 0 |
| `TIMEOUT` | 0 | 1 |
| `SCRIPT_NOT_FOUND` | 0 | 0 |
| `LICENSE_BLOCKED` | 0 | 0 |
| `OTHER` | 0 | 2 |
<!-- numbers:pilot2:end -->

What each Pilot 2 paper stopped at, decided by its first failure, with the log line that decided it:

<!-- numbers:pilot2failures:start -->
<!-- Generated by scripts/report_numbers.py from data/pilot2_runs/failure_categories.json; do not edit by hand. -->

| Paper | Category | Phase | Deciding line |
|---|---|---|---|
| `paper_002` | MISSING_DEPENDENCY | run | `ModuleNotFoundError: No module named 'lightgbm'` |
| `paper_003` | OTHER (WRITE_TO_READ_ONLY_REPOSITORY) | run | `OSError: [Errno 30] Read-only file system: '/workspace/repo/data/california_housing/build_X__quantile__mean__new__indices__0.pickle'` |
| `paper_004` | TIMEOUT | run | `status: TIMEOUT` |
| `paper_005` | OTHER (OUT_OF_MEMORY) | run | `status: OOM_KILLED` |
| `paper_006` | success | n/a | n/a |
| `paper_008` | DATA_NOT_ACCESSIBLE | run | `FileNotFoundError: [Errno 2] No such file or directory: './data/forest_cover_type/forest-cover-type.csv'` |
<!-- numbers:pilot2failures:end -->

What changed between the pilots is the sandbox and the run setups, not the papers or the definitions. Pilot 1's
dominant failure, dependencies that could not be installed, is gone: every paper now installs its dependencies, including
the papers that are described only by a conda environment file and those that need a package built from source. What remains are
obstacles that belong to the papers or to the resources given to them: an undeclared dependency (`paper_002`), a cache
file that the paper writes into its data directory (`paper_003`, which this pilot's frozen run setup mounts read-only),
the time limit (`paper_004`, still training when it hit it), the memory limit (`paper_005`), and split files that were
never published (`paper_008`). `paper_006` is the only paper that ran to completion. Per-paper times and peak memory are
in `docs/PILOT_2.md` section 12.

The first Pilot 2 attempts were stopped mostly by defects in Repro Radar itself, which only running the tool on a second
platform (Windows, against Linux CI) and on real papers revealed: a CRLF container entrypoint, dependency markers
evaluated for the host instead of the sandbox, a conda lock resolved instead of installed as pinned, a writable mount
whose parent directory was owned by root, and others. Each was fixed in its own issue and PR, the paper was re-run, and
every earlier attempt is kept with its reason (`data/pilot2_runs/first_attempts/README.md`, generated from the stored
records; the list is in `docs/PILOT_2.md` section 12).

### 6.2 Can the numbers be checked? Claim extraction

<!-- numbers:extraction:start -->
<!-- Generated by scripts/report_numbers.py from data/claims/{guard_report,consistency,review_decisions,gold_score_pass_A}.json; do not edit by hand. -->

| Claim extraction | Value |
|---|---|
| Questions (6 papers) | 18 |
| Answers over both passes | 36 |
| Claims found | 24 (all from a table: 24) |
| Quote guard: quote and value found in the paper text | 24 / 24 (unverified: 0) |
| Passes A and B agree | 18 / 18 (disagreements: 0) |
| Reviewed by the owner | accepted 12, rejected 0, pending 0 |
| Gold set (pass A), scored questions | 18 |
| True positives / false positives / false negatives / true negatives | 12 / 0 / 0 / 6 |
| Precision / recall | 1.0 / 1.0 |
| Regression cases (must be true negatives) | `paper_005:ep3602_auroc`: TN, `paper_005:ep3602_accuracy`: TN, `paper_008:higgs_auroc`: TN |
<!-- numbers:extraction:end -->

These figures describe the extraction pipeline, with three caveats. The two passes are not independent: pass B took its
values over from pass A (`docs/AGENT_EXTRACTION.md` section 3; a blind second pass was prepared and is not yet run). The
candidate values in the gold set form were listed by the same agent that did the extraction, although the owner chose
among them without seeing which one the agent had chosen, so a value the agent never found could enter the gold set only
through the free "other" answer, which the owner did not use. And 18 questions over 6 papers is a small sample, so a
perfect score is weak evidence. What the figures do show: every claim that was accepted has a quote that occurs in the
paper's own text, a person decided on each one, and the two cases built to catch an invented value (a dataset and a
metric that the paper does not contain) were answered "not found".

### 6.3 What Pilot 2 does not show

No Pilot 2 run produced a metric that an accepted claim names. `paper_006` completed, but on the Bank dataset, while its
accepted claims concern Arcene; the other five papers stopped before producing results. `cli.py score` can now score a
stored run against the accepted claims (`python cli.py score <paper> --from-run <run directory>`, #136), but for these
runs its Tier 2 would not be a measurement, so this report lists no composite scores. Pilot 2 measures whether the papers
install and run, not whether their numbers reproduce.

- **Sources:** `docs/PILOT_WEEK2.md` section 11 and `docs/PILOT_2.md` section 12 (the generated blocks above are copied
  from `data/pilot_runs/` and `data/pilot2_runs/` by `scripts/report_numbers.py`); `data/pilot2_runs/first_attempts/`
  (every earlier attempt); `data/claims/` (guard report, A/B agreement, the owner's review decisions, the gold-set
  score); `docs/AGENT_EXTRACTION.md` (section 3, why the passes are not independent).
- **Status:** written. Every number in this section is a generated block; `python scripts/report_numbers.py --check`
  and a test fail if one is edited by hand.

## 7. Limitations and threats to validity

- **Small sample.** Six papers, one counted run each, no seed loop: the results are anecdotal, not statistical. The
  corpus is tabular deep learning and sequence kernels, and it was corrected and reduced before the pilots (section 5.1); no
  paper was replaced because it failed (#166).
- **The run setups were written by us.** The entry command, working directory, data, build, extra requirements, and
  version constraints were chosen by Repro Radar. A paper that runs shows that it *can* be run this way, not that its
  README alone is enough. The per-paper settings were frozen for Pilot 2, so an obstacle caused by a setting (the
  read-only data mount of `paper_003`) stays in the result and is proposed as a change for the next pilot.
- **Defects were fixed during the pilot.** The attempts ran at several Repro Radar commits. The counted runs are at two
  commits that differ only in the measurement tools (`docs/PILOT_2.md` section 12), and every earlier attempt is kept.
- **Substitutions and unpinned versions.** The CPU build of `faiss` replaces conda's CUDA build (`paper_004`), and a
  package that a requirement file leaves unpinned was installed at the newest version that fits, not the version the
  authors used.
- **Resources.** 2 CPUs, 6 GiB, 3600 seconds per phase, and no network were chosen by us; a paper that needs more fails
  here although it might run on the authors' hardware (`paper_005` at the memory limit, `paper_004` at the time limit).
  The counted runs are CPU-only; the machine's RTX 5070 needs a PyTorch built for CUDA 12.8 or newer, which the PyTorch
  1.x pins of several papers cannot use.
- **One platform per pilot.** Pilot 1 ran on Linux runners and Pilot 2 on one Windows machine; some failures may depend
  on the platform, which is also how the Windows-only defects of the tool were found.
- **No numerical reproduction was tested.** No run reproduced an accepted claim, so Tier 2 (agreement with the paper's
  numbers) and Tier 3 (stability across seeds, not implemented, #48) were never exercised on real results.
- **Extraction.** It is agent-assisted; the two passes are not independent; the gold set was built from candidates listed
  by the same agent; and the quote guard proves that a quote occurs in the page text, not that the number means what the
  question asks (`docs/AGENT_EXTRACTION.md`). One paper, `paper_005`, ended with no accepted claim at all.
- **Conclusion bounds.** From these results one can say that the sandbox and the run setups made the papers installable
  and exposed what blocks each of them; one cannot say how reproducible tabular machine learning is in general.

- **Sources:** `docs/PILOT_2.md` section 12 (its Limits, and the proposals); `docs/PILOT_WEEK2.md` section 9;
  `docs/AGENT_EXTRACTION.md`; `docs/CORPUS_VERIFICATION.md` sections 5 and 6; `data/pilot2_runs/first_attempts/`.
- **Status:** written.

## 8. Lessons learned

- **Run the tool on a second platform early.** The real-Docker acceptance checks passed in CI throughout; two defects only
  appeared on a Windows host (a CRLF entrypoint, dependency markers evaluated for the host), and several more only when
  real papers were run.
- **A conda environment file is a lock.** The first answer to the conda failures was a resolver pass over the pins
  (#227/#228); it failed on a source-only dependency and on conda's `mkl` packages. Installing the pins as they are,
  without resolving, was the correct model (#229).
- **Fix the tool, not the experiment.** Freezing the per-paper settings and allowing only fixes to Repro Radar's own code
  (`docs/PILOT_2.md` section 9) is what let a failure be told apart: the tool's defects were fixed and re-run, while the
  paper's own cache write and memory use stayed in the result.
- **Keep every attempt and say why it was replaced.** The earlier attempts show which obstacles were the tool's and which
  the papers'; the index is generated from the stored records, so the story is not retold from memory.
- **Generate the numbers and test the generation.** The generated blocks and their tests caught a stored file that
  carried a local path and a log line that a color code hid from the categorizer.
- **What we would change next:** make `paper_003`'s data directory writable, give `paper_005` more memory and `paper_004`
  more time, list `lightgbm` for `paper_002`, and, above all, choose each paper's command so that it produces the metrics
  its accepted claims name (`docs/PILOT_2.md` section 12).

- **Sources:** `docs/PILOT_2.md` section 12; `data/pilot2_runs/first_attempts/README.md`; `docs/DECISIONS.md` (D-008 and
  the earlier decisions); the issues named above.
- **Status:** written.

## 9. Conclusion and future work

**Purpose:** say what the evidence supports and what should come next, no more than section 7 allows.

- **Needs:** sections 6 and 7.
- **Status:** blocked.

## 10. References and reproducibility statement

**Purpose:** list every reference, each checked against its source, and explain how to re-run everything (commit,
commands, data).

- **Needs:** a tagged commit and the verified source list.
- **Status:** not started.
