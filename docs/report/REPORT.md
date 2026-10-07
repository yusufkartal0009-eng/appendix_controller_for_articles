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
checked; no paper has been run through the full pipeline yet (`docs/PROGRESS.md`), and the scoring rubric has
only been exercised against simulated, not real, outputs (`docs/gap_analysis.md`, finding GA-2). This report
describes the method built so far and will be extended with results once Pilot 2 runs. The pilot covers tabular
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

Tier 2 does not use one fixed tolerance for every metric. `src/validation_rubric.py` categorizes each metric —
a bounded rate such as accuracy or AUROC, an unbounded loss such as RMSE where lower is better, a
hardware-sensitive runtime measurement, or a correlation — and applies a tolerance suited to that category: for
example accuracy is allowed 5% relative or 0.02 absolute error, AUROC a tighter 4% or 0.015 (bounded metrics
near 1.0 can move only a little in absolute terms), and runtime or latency a much wider 30%, with a note that
the difference may be hardware rather than a real divergence, since wall-clock time depends on the machine it
was measured on. Tier 3's stability check uses the coefficient of variation (CV) across seeds: CV ≤ 2% is
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
  `noexec` decision); `src/config.py`, `src/scoring.py`, `src/validation_rubric.py` (weights, thresholds,
  category tolerances, CV bands — read directly from the code, not retyped by hand); `docs/CLAIM_SCHEMA.md`,
  `docs/PDF_TEXT_EXTRACTION.md`, `docs/AGENT_EXTRACTION.md`; `data/claims/gold_score_pass_A.json` (the
  precision/recall numbers and the two regression cases).
- **Status:** written. This section describes the design and is not a results claim: the four-tier score has
  not yet been run against a real pilot execution (`cli.py score` is still simulated, #136), which belongs to
  section 6.

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

**Purpose:** report the pilot rates and failure categories, and the precision and recall of claim extraction.

- **Needs:**
  - Pilot 1 (exists, `docs/PILOT_WEEK2.md` section 11);
  - Pilot 2 runs (#171, not run — this is the only missing piece);
  - the gold set and its precision/recall (exists now: #133, precision 1.0/recall 1.0, `data/claims/gold_score_pass_A.json`; cited in section 4.3 above as design evidence, not repeated here as a result).
- **Status:** blocked on Pilot 2 alone.

## 7. Limitations and threats to validity

**Purpose:** state honestly what the results cannot show: small n, run setups written by us, hardware and seeds,
extraction errors, and what was not done.

- **Needs:** Pilot 2 done; written before the Abstract and the Conclusion.
- **Status:** blocked.

## 8. Lessons learned

**Purpose:** record what surprised us and what we would change.

- **Needs:** Pilot 2 done.
- **Status:** blocked.

## 9. Conclusion and future work

**Purpose:** say what the evidence supports and what should come next, no more than section 7 allows.

- **Needs:** sections 6 and 7.
- **Status:** blocked.

## 10. References and reproducibility statement

**Purpose:** list every reference, each checked against its source, and explain how to re-run everything (commit,
commands, data).

- **Needs:** a tagged commit and the verified source list.
- **Status:** not started.
