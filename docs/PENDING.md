# Pending steps (2026-10-22)

This document lists what is still open: decisions that only the owner can make, work that an assistant can do, open
issues, and things that were done only partly or not verified. It is a snapshot. The evidence for each item is named; when
an item is closed, its entry is removed or marked in the same pull request that closes it. State of `main` when this was
written: no open pull request, 973 tests passed and 11 skipped, `ruff check .` clean.

How to read it: **Decision** means a choice that belongs to the owner. **Work** means a task that can be done without a
decision. **Not verified** means a statement in the project that has no evidence yet.

## 1. Decisions that belong to the owner

### D1. Repository access (private or public)
- **State:** the repository is private. Collaborators can read it; nobody else can clone it. A person outside the project cannot
  follow the README today.
- **What is needed:** decide whether and when to make it public. Before that, the audit in W1 should be done: a scan of the files
  and the history for keys, passwords, e-mail addresses and local paths, and a check of the licence and authorship text.
- **Not decided here:** the choice itself. No setting of the account or the repository was changed by an assistant.

### D2. Gold set 2 (the owner's own answers)
- **State:** 18 new questions (3 for each of 6 papers: 2 table values and 1 negative control) were answered by two independent
  passes (pass A and a blind pass B), and the passes agree on 18 of 18 (`docs/GOLD_SET_EXPANSION.md`, `data/gold_expansion/`).
  The owner's own answers do not exist yet: the form is outside the repository and has 1 box ticked.
- **Effect of waiting:** without the owner's answers the precision and recall of the two passes on these questions cannot be
  computed, and agreement of two passes is not correctness (in the first gold set three passes chose the same wrong row).
- **Cost:** about 45 minutes. After it, the passes are scored with `scripts/evaluate_gold.py`.

### D3. Claims of the demo paper
- **State:** the demo-set run (`docs/DEMO_SET.md`) passed its measurement for one paper only (`demo_020`). A form with 6 questions
  is outside the repository. Three independent passes found "not found" for 2 of the 6; the right cell is among the candidates.
- **Caveat:** the paper passed the measurement through a line that prints a set-up value, not a result. Its output has an RMSE
  table, but none of the 48 printed numbers was found in the paper's text, so it is **not** shown that the program reproduces
  the paper's table. Filling the form is worth less than D6.

### D4. `paper_004` and `paper_005`
- **`paper_004`:** completed with a memory limit of 13.93 GiB (peak 10.64 GiB, 9,202 s). It has no accepted claim, so it cannot be
  scored beyond the neutral baseline. Decide whether to pick a claim to accept.
- **`paper_005`:** was killed for memory at 13.93 GiB as well (step 187 of 540 of its grid search). Docker sees 15.5 GiB.
  Options: more memory (give WSL more), or mark it out of scope (needs more than about 14 GiB). The assistant's suggestion was out of
  scope, with the reason recorded; it is the owner's call.
- **Evidence:** `docs/MEMORY_RUNS.md`.

### D5. External validation (ReScience C)
- **State:** the selection rule was applied three times (strict rule, a first relaxation, a second relaxation, `docs/EXTERNAL_VALIDATION.md`
  sections 9 and 11). Of 65 articles evaluated, **0** were selected; no run was made. The protocol (`docs/EXTERNAL_VALIDATION_PROTOCOL.md`) is
  written and waits for papers. The rejections are mostly a README without a run command in the accepted forms (25), a language other
  than Python (23), and a missing or unusable code repository (11).
- **Options:** relax the rule again (`python3`, `sh` forms), choose by hand, use another pool, or go on without an outside reference.
  Another relaxation made after seeing the result must be written down as such. Choosing by hand loses the "not chosen because it runs"
  property.
- **Why it matters:** this was the only planned source of outside ground truth for the verdicts of the tool.

### D6. How to get demo papers
- **State:** the automatic search found 22 candidates that passed the static rules, of which 1 passed the run test. Most failures were
  a repository that is mounted read-only in the sandbox (the program writes into it), requirements that could not be installed, and
  commands that need a network, a key or data.
- **Options:** (A) tighten the measurement pattern and continue with the 48 candidates that were not run; (B) pick 3 to 5 papers by hand,
  fetch their data beforehand, and label the set as hand-picked; (C) use the evidence that already exists (`paper_003` and `paper_006`
  with four identical runs, the synthetic true/false claim, `paper_102`). The assistant suggested C first, then B.
- **Also open:** a prompt for another assistant to search papers exists outside the repository; its results must be checked with
  `scripts/verify_corpus.py` and a sandbox run before use.

### D7. The rule that decides Tier 3
- **State:** the metric with the largest coefficient of variation decides Tier 3. For `paper_003` that made a training loss decide
  (Tier 3 = 65.0), while `rmse` alone gives 100.0. For `paper_006` it is 100.0.
- **Decide:** keep the rule, or use only the headline or claimed metric. Evidence: `docs/MULTI_SEED.md`.

### D8. Questions for the mentors
- Issue `#165`, named in the plan file and in old pull request texts, does not exist in this repository ("could not resolve"); which source did it come
  from, and is the "no AI attribution" question it carries still open? The pull request template has an "AI use" section; is it wanted?
- Were Tier 3 and the AI diagnosis layer expected? They are done in a rule-based form (no real model run).
- Which claim should the final report defend: a **rate** (how many papers install and run; with 12 papers the 95% interval is wide, 1 of 6 gives 3% to 56%) or the
  **correctness of the verdict** on papers with a known answer? This decides how many papers are enough.

## 2. Work that an assistant can do without a decision

### W1. Readiness audit for publication (not the decision itself)
Scan the tracked files and the history for secrets and personal data, replace local paths in tracked files, list large files, check licence and
authorship text, and write `docs/PUBLIC_READINESS.md`. A real secret found in the history would need to be rotated; the history is not rewritten without the owner.

### W2. Build the six sandbox images from scratch
The README commands for the compiler image and the Python 3.8 and 3.9 images ran only from the layer cache. Build all six with `--no-cache`, record time and
size, and update `docs/ENVIRONMENT.md` and the README note ("have not been run from this README yet").

### W3. A fresh run from a clean clone, with the fixes
In the earlier clean-clone test (`docs/evidence/clean_clone/WALKTHROUGH.md`) no fresh run completed: `paper_008` cannot (manual data), and `paper_006`
was stopped by the 3,600 s limit. Repeat with `cli.py score paper_006 --cpus 8 --timeout 7200` after `fetch_data.py`, with the accepted claims now restored by
`init-db`, then `cli.py diagnose`. Record the result as it is.

### W4. Demo script
`docs/DEMO_SCRIPT.md`: a 4 to 5 minute flow that uses only evidence that exists (dashboard, synthetic true and false claim, the four identical runs of two papers,
Tier 3, a diagnosis report, and the honest limits), with each command and its real output and a line "what this does not show".

### W5. Bug hunt on the code of the last weeks
Read `src/diagnosis`, `restore_decisions`, the multi-seed code, `scripts/demo_set.py`, `scripts/field_analysis.py` and `cli.py score` for real defects. A finding needs a failing test
first; suspicions without a test go to `docs/BUG_HUNT.md`.

The five tasks above are written in a prompt file outside the repository (`diger_isler_prompt.txt`); it had not been started when this was written.

## 3. Open issues and their state

| Issue | Title (short) | State (source) |
|---|---|---|
| #34 | local model fallback | Done: backends with a number lock, fallback to the rule-based report. **Left:** a model that extracts claims as validated JSON was not built. **Not verified:** nothing was run against a real model (no key, no local server) (comment of 2026-10-20). |
| #35 | discrepancy explainer | Done: rule-based comparison of two runs. **Left:** nothing writes `Needs Review` to the database (a `review_suggested` flag only); the 0.1% and 5% lines are conventions, not shown to separate floating-point jitter from divergence (comment of 2026-10-20). |
| #30 | metric extraction on noisy logs | Partly done; fixtures with ANSI escape codes and noisy multi-line logs missing (status comment). |
| #23 | entry-point detection | Partly done (`Stager.detect_candidate_scripts`); see the comment of 2026-10-15. |
| #20 | manifest parser | Partly done in other places (`requirements*.txt` parsing); see the comment of 2026-10-15. |
| #18 | end-to-end sandbox tests | Partly done; see the comment of 2026-10-15. |
| #19, #21, #22, #24, #45 | AST import scanner, version solver, GPU-to-CPU flag injection, dependency tests on diverse repositories, release automation | Not started; no related module (review of 2026-10-20). |
| #3 | commitlint and branch protection | Not started. Branch protection cannot be set: GitHub answers 403 ("upgrade to GitHub Pro or make this repository public") for this private repository on its plan. |
| #13, #14, #15, #17 | base image, container lifecycle, zero-network isolation, timeout and memory watchdog | Open; each has a status comment of 2026-10-15 that was checked again on 2026-10-20 and is still correct. They were not closed for lack of new evidence. #13 stays open for the missing `xgboost` and `lightgbm` packages in the image. |
| #115 | working agreement | Standing issue; never closed. |


## 4. Things the project does not do (and nobody has decided to do)

- **Demo video** (2 to 3 minutes): not made. The owner records it; W4 prepares the script.
- **Pool of 16 papers:** the corpus has 12 papers (6 seed papers and 6 of Pilot 4). Without D5 the number does not grow. The 16 were not reached.
- **Audit log of automatic decisions and an objection mechanism**, and **ranking of papers by impact or citations**: not built, and the owner's plan does not
  include them.
- **Repository public:** see D1.

## 5. Known limits and statements without evidence

- **Success rate:** Pilot 4 gave pilot success 1 of 6 on new papers (install 3 of 6 after one correction round, run 2 of 6). Pilot 3 (2 of 6) used settings chosen after the
  failures of Pilots 1 and 2 and says nothing about new papers. No rate over 12 papers is claimed.
- **No paper has completed a fresh run from a clean clone** (W3).
- **The diagnosis classifier:** its validation set (46 real and 12 synthetic runs) was labeled by hand but not blind; after the gaps were closed (PR #425) the
  set no longer measures anything on new logs (`docs/DIAGNOSIS.md`).
- **Model paths of the diagnosis layer** (`anthropic`, `local`) were never run against a real model.
- **Field analysis (week 6):** 12 papers, exploratory, no significance claimed (`docs/FIELD_ANALYSIS.md`).
- **The demo set** is chosen to be easy; it is not a sample of papers and must not be reported as a success rate.
- **Estimated times** in `docs/WORKFLOW.md` (adding a paper, source check, data fetch, claim extraction, claim acceptance) were not timed.
- **Documentation conflicts:** `docs/PROGRESS.md` and `docs/DECISIONS.md` hold both entries where merge conflicts were resolved by keeping both sides (see
  the pull requests #367 to #387); the order of some entries may be mixed.
- **No CI** (D-010): checks run locally before a merge and the result is written in the pull request.

## 6. How a long job is started (so that it is not cut)

A prompt written inline on the command line was cut at its first paragraph and its Turkish letters were damaged (a Day 1 job did nothing for that reason). Write the
prompt into a file and start the session with a short ASCII sentence that names the file, from a new PowerShell window (not from inside a Claude chat box):

```
claude --dangerously-skip-permissions "Read the file <path to the prompt file> in full and do everything it says, in order, until the end. Do not wait for me."
```

After starting it, check that it is running by evidence (a session file written in the last minutes, a heartbeat line in `sabah_bekleyenler.md`, a new branch or pull
request), not by trusting a message.
