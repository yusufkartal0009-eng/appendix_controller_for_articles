# Pending steps (2026-10-28)

This document lists what is still open: decisions that only the owner can make, work that an assistant can do, open
issues, and things that were done only partly or not verified. It is a snapshot. The evidence for each item is named; when
an item is closed, its entry is removed or marked in the same pull request that closes it. State of `main` when this was
written (updated 2026-10-28, second night session): no open pull request, 1,722 tests passed, 10 skipped, `ruff check .` clean. Items that were done since 2026-10-22
are marked **DONE** with the pull request that closed them.

How to read it: **Decision** means a choice that belongs to the owner. **Work** means a task that can be done without a
decision. **Not verified** means a statement in the project that has no evidence yet.

## 1. Decisions that belong to the owner

### Defaults chosen by the assistant on 2026-10-28 (the owner did not answer; the owner may revise each one)
The owner could not be asked during the night of 2026-10-28. The recommended option of each of the three open questions was applied and is
marked here and at its place below with "default chosen by the assistant, the owner may revise":

| Code | Question | Default applied | Where | How to revert |
|---|---|---|---|---|
| K-A | Which metric decides Tier 3 | The metric of an accepted claim (through `data/claim_metric_map.json`); without such a claim the largest CV decides as before (#542). `paper_003` Tier 3 = 100 (was 65), `paper_006` = 100 | D7, `docs/MULTI_SEED.md` section 5a | drop `claimed_run_metrics` in `src/score_run.py` |
| K-B | The absolute allowance of 0.05 for a value between 0 and 1 | Kept as it is; written in the report as a known limit | D10, report sections 6.9 and 7, `docs/TOLERANCE_PROBE.md` | restrict the allowance in `src/scoring.py` (`Tier2MetricsEvaluator`) |
| K-C | The attribution rule of `AGENTS.md` (rule 7) | AI use is declared in the AI assistance statement at the end of the report; commits and PR descriptions carry no attribution line (#544) | D8 | edit rule 7 of `AGENTS.md` |

Other choices made on the same night that the owner may revise: the layout of the added dashboard parts (they follow the earlier design, #548;
`AGENTS.md` section 6, rule 9 asks the owner for UI decisions), and the wording of the new report sections 6.12 and 6.13.

### D1. Repository access (private or public)
- **State (2026-10-24):** the repository is **public** (the owner's statement of 2026-10-24; no setting of the account or the repository was changed by an
  assistant). The readiness audit was done (`docs/PUBLIC_READINESS.md`, W1); every pull request since then is scanned for local paths, e-mail addresses
  and keys before the merge. A fresh clone of the public repository followed the README to a completed run (`docs/evidence/clean_clone/WALKTHROUGH.md`, Update 2).
- **Left:** the e-mail address in the git history is left as it is (the owner's decision), and the history was not rewritten.

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
- **State:** the metric with the largest coefficient of variation decided Tier 3. For `paper_003` that made a training loss decide
  (Tier 3 = 65.0), while `rmse` alone gives 100.0. For `paper_006` it is 100.0.
- **Default chosen by the assistant, the owner may revise (K-A, #542):** the metric that an accepted claim of the paper is mapped to
  (`data/claim_metric_map.json`) decides; without such a claim the largest-CV rule stays. `paper_003` is now 100, `paper_006` 100.
  Evidence: `docs/MULTI_SEED.md` section 5a. To revert, drop `claimed_run_metrics` in `src/score_run.py`.

### D8. Questions for the mentors
- Issue `#165`, named in the plan file and in old pull request texts, does not exist in this repository ("could not resolve"); which source did it come
  from, and is the "no AI attribution" question it carries still open? The pull request template has an "AI use" section; is it wanted?
  **Default chosen by the assistant, the owner may revise (K-C, #544):** `AGENTS.md` rule 7 now says that AI use is declared in the AI assistance
  statement at the end of the report and that commits and PR descriptions carry no attribution line. The mentor answer (Y2) is still wanted; the
  "AI use" section of the PR template was not changed.
- Were Tier 3 and the AI diagnosis layer expected? They are done in a rule-based form (no real model run).
- Which claim should the final report defend: a **rate** (how many papers install and run; with 12 papers the 95% interval is wide, 1 of 6 gives 3% to 56%) or the
  **correctness of the verdict** on papers with a known answer? This decides how many papers are enough.

### D9. The candidate papers (new, 2026-10-24; round 2 done 2026-10-24)
- **State:** 29 candidates were collected (`docs/CANDIDATES.md`). The 14 that the lists call ready, fixable or two-step were run once each by a protocol
  written before the runs (`docs/CANDIDATE_RUNS.md`): **0 of 14 passed** (13 run, 1 not run because its listed command holds only placeholders), Wilson 95 %
  interval 0.0 % to 21.5 %. Causes: installation failed 6, a module missing 3, a write into the read-only repository 2, a data file 1, a file path 1, an
  incomplete command 1 (`data/candidates/runs/evaluation.json`). The 11 risky and 4 excluded were not run. None is in `data/seed_papers.json`.
- **Round 2 (repair round, 2026-10-24, #455, #457, #464):** option (a) was done, as a separate labeled round by `docs/CANDIDATE_RUNS_ROUND2.md` (merged before the first run; two dated amendments, sections 10 and 11). First attempt 0 of 14; **with repair 1 of 14** (`cand_002`, Wilson 95 % interval 1.3 % to 31.5 %); of the 11 risky candidates one qualified (`cand_020`, then not repairable) (`docs/CANDIDATES.md`, Round 2 results). The pass printed numbers that occur in no table of its paper (`metric exists, no table match`), and a blind extraction of three passes found no value to propose; no claim is accepted. `cand_011` ran to exit 0 but printed a dict, so by the pattern it did not pass (the pattern misses such output; the rule was not bent after the result).
- **Decide (still open):** (a, done) whether to write a second protocol, before any run, that allows a fixed list of repairs (a Python version, an extra requirement, a writable
  copy of the repository, a data file fetched beforehand) and run the 14 again as a separate, labeled round; (b) whether to run some of the 11 risky ones
  after their data is fetched by hand; (c) whether to stop adding papers and use the evidence that exists (D6, option C). Nothing moves into the seed corpus without
  a decision of the owner.
- **Not done:** no PDF of a candidate paper could be fetched (the one passing candidate's paper only as Europe PMC XML); whether the pass of `cand_002` is comparable with a table of its paper is not verified. New open items: (e) whether the pass pattern should also accept a printed dict of numbers (`cand_011`), decided for future runs only; (f) whether a source build of sdist-only pins (`cand_005`, `cand_020`) and an extra wheel index are allowed repairs in a further round.

### D11. The automatic search of round 3 (new, 2026-10-25; done 2026-10-25)
- **State:** the protocol (`docs/AUTO_SEARCH_ROUND3.md`, merged before the first search) was run with `scripts/auto_search3.py` over seven topic stages: 3,399 candidates checked
  against the static rules and 135 run once in the sandbox. K1 (run test) passed 2, K2 (numbers of the output found in the paper's text) passed 0, both 0 (results section of the
  document, generated; report section 6.10). The search ended because the pool of stage 7 was used up, before the 9-hour limit. The two K1 passes are `a3_095` (one meaningful
  number in the output, so K2 could not pass) and `a3_096` (207 numbers, none in its paper). No claim was extracted for this round: nothing passed both tests.
- **Decide (open):** (a) whether to run a stage 8 with other topics, or to stop adding papers (D6, option C); (b) whether K1 may allow help of the kind that the failures need (a module missing
  from the requirement files, a writable output folder) as a separate, labeled round; (c) whether a known positive case (a paper whose table is known to be reproducible) should be used to
  test whether K2 can pass at all.
- **Not done:** no match candidate exists, so no form (`aday_iddia_formu_3.md`) was made; whether the numbers of `a3_096` come from a simulation is not verified.

### D13. The automatic search of round 4 with K2 v2 (new, 2026-10-27; done 2026-10-27)
- **State:** the protocol (`docs/AUTO_SEARCH_ROUND4.md`, merged before the first run; K2 v1 unchanged, K2 v2 added) was run with `scripts/auto_search4.py` over stages 8 to 21
  (stages 10 to 21 were added by merged changes when the earlier stages were used up): 2,648 candidates checked, 107 run once in the sandbox, K1 passed 3, K2 v1 passed 1, K2 v2 passed 1,
  both K1 and K2 0 (results section of the document, generated; report section 6.10a). The search ended at the 9-hour limit. K2 v2 passes the positive control `paper_006` (one scale-converted
  match, `0.933` as `93.3`, plus a coincidental `256`) and not the negative control `paper_102`. The one K2 pass (`a4_067`, a fuzzing script) failed K1 and matched integers by chance.
  The K2 v2 re-evaluation of the two K1 passers of round 3 found no match. No claim was extracted: nothing passed both tests.
- **Decide (open):** (a) whether to keep K2 v2 (it can match by chance; the guard limits this); (b) whether to run more stages or stop adding papers (D6, option C); (c) whether the index mask of K2 should also cover `[n/m]` progress
  counters (it would have removed the pass of `a4_067`); this would change K2 for future rounds only.
- **Not done:** no match candidate passed K1, so no form (`aday_iddia_formu_4.md`) was made; whether a K1 passer's output has anything to do with a table of its paper is not verified.

### D12. How the claims meet the run's metrics (new, 2026-10-25, `docs/REAL_VERDICTS.md`)
- **State: implemented as a mapping file; owner may revise** (#507, #509, #511). `data/claim_metric_map.json` ties each accepted claim (question ID) to the run
  metric of the same model, dataset, measure and split (`map`: 1 claim, `paper_003` / `ft_transformer_rmse` -> `rmse`) or says that the run has no counterpart
  (`no_counterpart`: 12 claims); `docs/CLAIM_METRIC_MAP.md` has the rule and the evidence of each row. `cli.py score` uses it; a claim without a counterpart stays out of Tier 2
  and the output says so. `paper_003`: 0.459 against 0.473, 3.05 %, Tier 2 100, `Verified` (one claim, one number, not a confirmed reproduction). Before the map: Tier 2 0.0 and
  `Needs Review` for every real run (`docs/REAL_VERDICTS.md` keeps that result as "before the mapping").
- **Decide (still open):** whether this is the way to tie a claim to a run (the alternatives were a mapping beside each paper's run setup, or a metric name in the claim),
  and each row of the map. **Two consequences of the map to confirm:** (1) with every claim `no_counterpart` Tier 2 is the neutral 70; since #540 such a run is labeled `Needs Review`
  (it had been `Partially Verified` from the build tiers alone, like `paper_102`); (2) the same neutral 70 applies to a failed run whose claims all have no counterpart
  (`paper_002`, `paper_005`, `paper_008`), so its total is higher than when Tier 2 was 0 (the label stays `Failed` through Tier 1). Neither rule was changed.
- **Done (#540):** a paper without an accepted claim, or whose claims all have no counterpart, keeps the neutral Tier 2 of 70 but is labeled `Needs Review`, never
  `Verified` or `Partially Verified`; the owner may revise this rule.
- **Also open:** K2 has no positive control (no real run prints a table value of its paper).

### D10. Two rules of the scorer to confirm (new, from the bug hunt, `docs/BUG_HUNT.md` section 2)
- **The absolute allowance of 0.05 for a value between 0 and 1** makes small values lenient (0.0167 matches a reproduced 0.06). Keep it, or use it only for
  named bounded metrics (accuracy, AUC, F1, precision, recall)?
- **Tier 3 was the single-run 75.0 for every paper scored by `cli.py score`**, even where `data/multi_seed_runs/` holds seed runs. **Default chosen by the
  assistant, the owner may revise (#542):** the stored record is read by `cli.py score`, `scripts/real_verdicts.py` and `scripts/build_demo_db.py`;
  a paper without a record keeps 75.0.
- **K-B (default chosen by the assistant, the owner may revise):** the absolute allowance of 0.05 for a value between 0 and 1 stays as it is. It is
  written in the report as a known limit; the tolerance probe (`docs/TOLERANCE_PROBE.md`) shows its effect.

## 2. Work that an assistant can do without a decision

### W1. Readiness audit for publication (not the decision itself) - **DONE** (`docs/PUBLIC_READINESS.md`, #431 and #432)
Scan the tracked files and the history for secrets and personal data, replace local paths in tracked files, list large files, check licence and
authorship text, and write `docs/PUBLIC_READINESS.md`. A real secret found in the history would need to be rotated; the history is not rewritten without the owner.

### W2. Build the six sandbox images from scratch - **DONE** (#435 and #436: 43 to 90 s each, 401 s in all, `docs/ENVIRONMENT.md`)
The README commands for the compiler image and the Python 3.8 and 3.9 images ran only from the layer cache. Build all six with `--no-cache`, record time and
size, and update `docs/ENVIRONMENT.md` and the README note ("have not been run from this README yet").

### W3. A fresh run from a clean clone, with the fixes - **DONE** (#441 and #453: completed, 2,490 s from the clone to the end of `diagnose`)
In the earlier clean-clone test (`docs/evidence/clean_clone/WALKTHROUGH.md`) no fresh run completed: `paper_008` cannot (manual data), and `paper_006`
was stopped by the 3,600 s limit. Repeat with `cli.py score paper_006 --cpus 8 --timeout 7200` after `fetch_data.py`, with the accepted claims now restored by
`init-db`, then `cli.py diagnose`. Record the result as it is.

### W4. Demo script - **DONE** (`docs/DEMO_SCRIPT.md`, #444 and #446)
`docs/DEMO_SCRIPT.md`: a 4 to 5 minute flow that uses only evidence that exists (dashboard, synthetic true and false claim, the four identical runs of two papers,
Tier 3, a diagnosis report, and the honest limits), with each command and its real output and a line "what this does not show".

### W5. Bug hunt on the code of the last weeks - **DONE** (`docs/BUG_HUNT.md`: three proven bugs fixed in #448, #449 and #450, seven suspicions listed)
Read `src/diagnosis`, `restore_decisions`, the multi-seed code, `scripts/demo_set.py`, `scripts/field_analysis.py` and `cli.py score` for real defects. A finding needs a failing test
first; suspicions without a test go to `docs/BUG_HUNT.md`.

The five tasks above were done on 2026-10-24. Also done that day: the tolerance probe on real runs (`docs/TOLERANCE_PROBE.md`, #442, #443 and #445) and the candidate runs (D9).

### W6. Open work after 2026-10-24 (no decision needed)
- Fill the form of the demo paper (D3) and of gold set 2 (D2) when the owner has the time; both are outside the repository.
- D9 (a) is done (round 2); the open items (e) and (f) of D9 need a decision before a third round.
- D11 (the automatic search of round 3) is done; its open decisions (a) to (c) need the owner.
- D13 (the automatic search of round 4) is done; its open decisions (a) to (c) need the owner.
- The bug hunt suspicions were tried on 2026-10-25 (`docs/BUG_HUNT.md` section 3): 2, 3 and 6 were real and are fixed (#499, #500, #501); 4 was real and is fixed
  (#513: the page shows the run that was scored, with its start date); 1, 5 and 7 are decisions of the owner (D10 twice, and the K1 pattern of the protocols).
- **DONE 2026-10-25:** the verdicts on the real stored runs (`docs/REAL_VERDICTS.md`, #495), the dashboard database from the stored runs (`scripts/build_demo_db.py`, #497),
  the second pass of the bug hunt (#499, #500, #501, #502), the report in its final state and `docs/PAPER_STATUS.md` (#504). What the paper still needs from the owner is in `docs/PAPER_STATUS.md`.

- **DONE 2026-10-28 (second night session, quality work, no new feature):** every number of the report, README and status documents checked against its source, with 8 corrections (`docs/NUMBER_AUDIT.md`, #554); the old open issues compared with `main` (`docs/ISSUE_TRIAGE.md`, #556; #11 and #30 closed with evidence, 18 issues stay open); boundary-case tests and four real defects fixed (`docs/COVERAGE.md`, #557, PRs #559 to #563; coverage of `src/` and `cli.py` 94.8 % to 96.8 %); a second clean-clone walk-through (`docs/evidence/clean_clone2/WALKTHROUGH.md`, #565); the report as a PDF (`docs/report/REPORT.pdf`, `scripts/export_report.py`, #567); small cleanups (#569).
- **Open after that session (owner):** the edge behaviors listed in section 5 (metric extractor formats, infinity and NaN in the scorer) are decisions, not defects that were fixed; whether to run `pytest --cov` as a habit; the PDF is not typeset with a conference template (needs the mentor's format, D8).

## 3. Open issues and their state

| Issue | Title (short) | State (source) |
|---|---|---|
| #34 | local model fallback | Done: backends with a number lock, fallback to the rule-based report. **Left:** a model that extracts claims as validated JSON was not built. **Not verified:** nothing was run against a real model (no key, no local server) (comment of 2026-10-20). |
| #35 | discrepancy explainer | Done: rule-based comparison of two runs. **Left:** nothing writes `Needs Review` to the database (a `review_suggested` flag only); the 0.1% and 5% lines are conventions, not shown to separate floating-point jitter from divergence (comment of 2026-10-20). |
| #30 | metric extraction on noisy logs | **Closed 2026-10-28:** ANSI and noisy-log tests exist (`tests/test_metric_extractor_noisy.py`), the color-code defect was fixed (#560). |
| #23 | entry-point detection | Partly done (`Stager.detect_candidate_scripts`); see the comment of 2026-10-15. |
| #20 | manifest parser | Partly done in other places (`requirements*.txt` parsing); see the comment of 2026-10-15. |
| #18 | end-to-end sandbox tests | Partly done; see the comment of 2026-10-15. |
| #19, #21, #22, #24, #45 | AST import scanner, version solver, GPU-to-CPU flag injection, dependency tests on diverse repositories, release automation | Not started; no related module (review of 2026-10-20). |
| #3 | commitlint and branch protection | Not started. Branch protection cannot be set: GitHub answers 403 ("upgrade to GitHub Pro or make this repository public") while this repository was private on its plan; it is public now and the ruleset was not retried (GitHub settings are not touched by an assistant). |
| #13, #14, #15, #17 | base image, container lifecycle, zero-network isolation, timeout and memory watchdog | Open; each has a status comment of 2026-10-15 that was checked again on 2026-10-20 and is still correct. They were not closed for lack of new evidence. #13 stays open for the missing `xgboost` and `lightgbm` packages in the image. |
| #115 | working agreement | Standing issue; never closed. |


## 4. Things the project does not do (and nobody has decided to do)

- **Demo video** (2 to 3 minutes): not made. The owner records it; W4 prepares the script.
- **Pool of 16 papers:** the corpus has 12 papers (6 seed papers and 6 of Pilot 4). Without D5 the number does not grow. The 16 were not reached.
- **Audit log of automatic decisions and an objection mechanism**, and **ranking of papers by impact or citations**: not built, and the owner's plan does not
  include them.
- **Repository public:** see D1.

## 5. Known limits and statements without evidence

- **Scorer behaviors at the edges (found 2026-10-28, #557; owner decision whether to change, `docs/COVERAGE.md`):** a claimed infinity against an equal infinity earns no points; a NaN or infinite seed value gives Tier 3 = 40 with a note that says the variation exceeds 10 %; a boolean in a run report's `metrics` is read as 1.0 or 0.0. All are conservative or cannot occur in a stored run; changing any of them would be a scoring decision.
- **Metric extractor limits (found 2026-10-28, #557; owner decision whether to change):** a decimal comma (`accuracy: 0,85`) is read as `0.0`, which is a wrong value, not a missing one; `.85` and scientific notation (`1e-5`) are not read; a JSON `NaN` is kept as a metric while a log line `nan` is dropped. None of these is known to occur in a stored run; they were found with hand-written probes. The ANSI color-code defect was fixed (`tests/test_metric_extractor_noisy.py`).
- **Success rate:** Pilot 4 gave pilot success 1 of 6 on new papers (install 3 of 6 after one correction round, run 2 of 6). Pilot 3 (2 of 6) used settings chosen after the
  failures of Pilots 1 and 2 and says nothing about new papers. No rate over 12 papers is claimed.
- **Clean clone:** one paper (`paper_006`) completed a fresh run from a clean clone of the public repository (Update 2 of the walk-through); it used set CPU and time limits, so
  it is not a protocol run, and no accepted claim was reproduced. `paper_008` still cannot complete from a clean clone (a dataset downloaded by hand).
- **Automatic search (round 3):** **0 of 135** candidates of the automatic search of round 3 passed both the run test and the match of the output to the paper's text (K1 passed by 2 of 135, K2 by 0 of 135; Wilson 95 % intervals in the report, section 6.10); a selected, non-representative list, not a success rate (D11).
- **Automatic search (round 4, K2 v2):** **0 of 107** candidates passed both the run test and the match of the output to the paper's text (K1 passed by 3 of 107; K2 v1 by 1 and K2 v2 by 1, a chance match of a fuzzing script that failed K1; Wilson 95 % intervals in the report, section 6.10a); a selected, non-representative list, not a success rate (D13).
- **Candidate papers:** 0 of the 14 selected candidates passed a first attempt and 1 of 14 after repair (D9); the list was chosen by others for being easy, so this is not a success rate and it does not say that the papers cannot be reproduced.
- **Tolerance probe:** its claims are hand-made, not errors of real papers; the rates of false positives and false negatives of the scorer in the real world have not been measured.
- **Tier 2 has compared an accepted claim with a result of a real run once** (`paper_003`, through the claim map: one claim, one number, 3.05 % apart); it has not compared more.
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
