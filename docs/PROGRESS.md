# Repro Radar — Living Progress Log

> This document is updated after every milestone, issue, or PR to maintain full project memory.

---

## Current Status (2026-10-25 20:27 +03:00): Pilots 1-4, Tier 3, Diagnosis Layer, GPU Check, and Field Analysis Written Up; Candidate Runs, Tolerance Probe, Clean-Clone Run, Demo Script and Bug Hunt Done

- **Work order:** `docs/PLAN_2026-10-01.md` (continues `docs/ROADMAP_2026-09-27.md`). The stages are recorded in the entries below; the final report is `docs/report/REPORT.md` and its numbers are generated (`python scripts/report_numbers.py --check`).
- **Pilots** (12 papers: 6 seed papers in Pilots 1 to 3, 6 new papers in Pilot 4): pilot success 0 / 6 (Pilot 1), 1 / 6 (Pilot 2), 2 / 6 (Pilot 3, with four settings chosen after Pilot 2's failures), and 1 / 6 for the new papers at their first attempt (Pilot 4). `docs/FIELD_ANALYSIS.md` section 8 (generated) has the pool-wide rates, the human-intervention table, the autonomy rate, and a descriptive factor table (exploratory, n = 12).
- **Claim extraction:** 13 claims accepted by the owner. No run has been shown to reproduce an accepted claim: through `cli.py score` the claims (question IDs) never match the run's metrics (names), and aligned by hand only `paper_003` is close to one claim (`docs/REAL_VERDICTS.md`, REPORT section 6.11).
- **Tier 3 (stability):** implemented (#48, `docs/MULTI_SEED.md`): a paper with a seed parameter of its own is run once per seed. Two synthetic papers check the path against values computed on the host; `paper_003` and `paper_006` ran with three seeds each (`data/multi_seed_runs/`; not protocol runs). Tier 3 is 65.0 for `paper_003` (decided by its training loss; `rmse` alone would give 100.0) and 100.0 for `paper_006`.
- **AI Decision Layer:** a rule-based diagnosis (#31 to #36, `docs/DIAGNOSIS.md`, `python cli.py diagnose <run dir>`): input schema, failure classifier, template report, run comparison, optional model backends, and a hand-labeled validation. #34 and #35 stay open with a done/left comment. Not tried with a real language model.
- **GPU:** one synthetic paper with `torch==2.8.0` (CUDA 12.8) ran with `--gpus all` on the RTX 5070 through the real pipeline (`data/gpu_check/`, `docs/ENVIRONMENT.md`); no real paper was run with the GPU.
- **External reference:** the ReScience C selection evaluated 65 articles and selected none (`docs/EXTERNAL_VALIDATION.md`); no external run was made.
- **Open:** the release (#45), the old M3 issues (#19 to #24), #34 and #35, the standing issue #115, and `docs/PLAN_2026-10-01.md` question Y2 (the AI-attribution rule; issue #165 does not exist in this repository).
- **Since 2026-10-20 (issues #435 to #452):** the six images rebuilt from scratch with time and size (`docs/ENVIRONMENT.md`); the protocol of the candidate runs written before the runs and the 14 candidates run once each, **0 of 14 passed** (`docs/CANDIDATE_RUNS.md`, `docs/CANDIDATES.md`; a selected list, not a success rate); a fresh run of `paper_006` from a clean clone of the public repository completed (2,490 s, Update 2 of the walk-through); the tolerance probe (`docs/TOLERANCE_PROBE.md`; hand-made claims, not a real error); the demo script (`docs/DEMO_SCRIPT.md`); the bug hunt (three bugs fixed in #448 to #450, seven suspicions in `docs/BUG_HUNT.md`); the report has two new generated sections (6.8 and 6.9). Open: `docs/PENDING.md` (D9 candidate papers and D10 two scorer rules are new).
- **Automatic search of round 3 (2026-10-25, #469 to #473):** protocol merged before the first search (`docs/AUTO_SEARCH_ROUND3.md`), then `scripts/auto_search3.py`; seven topic stages; 3,399 candidates checked, 135 run once; K1 passed 2, K2 (output numbers found in the paper's text) 0, both 0 (Wilson intervals in the report, section 6.10, generated). Selected, non-representative list, not a success rate. Nothing accepted; no match candidate.
- **Candidate repair round (2026-10-24, #455 to #465):** a separate round with a protocol written before the runs (`docs/CANDIDATE_RUNS_ROUND2.md`): first attempt 0 of 14, with repair 1 of 14 (`cand_002`; its output matches no table of its paper); the others stopped because the failure needs a forbidden repair. Selected list, not a success rate. No claim accepted.
- **Night 5 (2026-10-25, issues #494 to #505):** verdicts on the real stored runs and the K2 positive control (`docs/REAL_VERDICTS.md`, #494; the expected K2 positive control was not obtained); a dashboard database from the stored runs (`scripts/build_demo_db.py`, #496, screenshots in `docs/evidence/demo2/`); the seven bug-hunt suspicions tried (#498: three real bugs fixed in #499, #500 and #501, one real and left to the owner, three owner decisions); the report brought to its final state with a new section 6.11 and `docs/PAPER_STATUS.md` (#503).
- **Tests:** 1,165 passed, 9 skipped, 1 expected failure (a strict `xfail`, `tests/test_bug_hunt_suspicions.py`) locally (2026-10-25) (Windows; network and POSIX-only tests skip). There is no CI at the moment (D-010): every PR records its local `ruff check .` and `pytest` run.

---

## Milestone Roadmap & Progress

Issue numbers and open/closed counts match GitHub as of 2026-10-20 06:03 +03:00 (issues only, not PRs), counted with #48 closed by this PR. Backlog ranges are the per-issue items listed in `docs/BLUEPRINT.md`; partly implemented open issues carry a status note on GitHub. Open/closed also includes issues added after the backlog (e.g. M2: #48, #80, #86, #88, #90, #92).

| Milestone | Focus | Backlog issues | Open / closed | Status |
|---|---|:---:|:---:|:---:|
| **M0: Baseline Hygiene & Audit** | Seed audit, projectflow adoption, hygiene tests | #2 – #6 | 1 / 32 | IN PROGRESS |
| **M1: Seed Corpus & Relational Data Foundation** | ArXiv ingestion, repo verification, claims schema | #7 – #12 | 3 / 29 | IN PROGRESS |
| **M2: Isolated Container Sandbox** | Docker runner, cgroups, network isolation, timeout | #13 – #18 | 5 / 28 | IN PROGRESS |
| **M3: Static Code Analysis & Dependency Solver** | AST scanner, manifest parser, unpinned solver, GPU flags | #19 – #24 | 6 / 5 | IN PROGRESS |
| **M4: Empirical Metric Extraction Engine** | Regex log parsers, stdout extraction, multi-seed CV, rubric | #25 – #30, #55 | 1 / 9 | IN PROGRESS |
| **M5: AI Decision Layer & Diagnostics** | Failure classifier, neutral reports, discrepancy explainer | #31 – #36 | 2 / 5 | IN PROGRESS |
| **M6: Web Dashboard & Reporting Portal** | FastAPI REST API, leaderboard UI, SVG badges, PDF reports | #37 – #41 | 0 / 6 | DONE (local dashboard) |
| **M7: Verification Suite & Production Release** | Pilot verification, contribution guide, CI/CD, v1.0 release | #42 – #46 | 1 / 18 | IN PROGRESS |

The weekly "Hafta 1–7" milestones were retired on 2026-09-25: their umbrella issues (#47 – #53) were closed as completed or as duplicates of the backlog above and moved into the matching M milestones.

---

## Changelog & Completed Work

### feat(scoring): claim-to-run-metric map file (2026-10-27 00:25 +03:00, Issue #507)
- `data/claim_metric_map.json` and `docs/CLAIM_METRIC_MAP.md`: for each of the 13 accepted claims, `map` (1: `paper_003` / `ft_transformer_rmse` -> `rmse`) or `no_counterpart` (12), each with evidence from stored run files; `tests/test_claim_metric_map.py` checks coverage and the evidence strings.
- A proposal: the owner may revise the map. The scorer is not connected yet (next issue).
### docs: status documents updated after night 5 (2026-10-25 20:28 +03:00, Issue #505)
- `docs/PENDING.md` (new D12 on how claims meet a run's metrics; the bug-hunt item and the done list updated), the Current Status of `README.md` and of this file.
- Not verified: that the owner's summary outside the repository says the same.
### docs(report): the report brought to its final state, and a paper status page (2026-10-25 20:26 +03:00, Issue #503)
- `docs/report/REPORT.md`: new generated blocks `realverdicts`, `pilotintervals` and `cleanclone` in `scripts/report_numbers.py` (tests added); new section 6.11 (what the scorer decides on real runs, K2 control, the pilot as an estimate with Wilson intervals) and a clean-clone paragraph in 6.4; the abstract states the two claims (a right decision on a known example; how many papers run); nine contradictions and stale sentences fixed; three limitations added (README commands mostly do not produce the paper's table, a label without a comparison, no K2 positive control). `python scripts/report_numbers.py --check`, `python scripts/verify_sources.py --check` and the tests pass.
- `docs/PAPER_STATUS.md`: which sections are final, what waits for the owner, and the result of the consistency scan.
- Not verified: that no stale sentence remains outside the phrases the scan searched for; the clean-clone numbers are read from the walk-through document, because the run record is not in the repository.
### test: the seven suspicions of the bug hunt, outcome (2026-10-25 20:19 +03:00, Issue #498)
- `docs/BUG_HUNT.md` section 3: for each suspicion a failing test was tried first. None was disproved; three were real bugs and are fixed (#499 quote guard, #500 classifier path rule, #501 README at the pinned commit); suspicion 4 is real but its fix is an interface decision (a strict `xfail` test, `tests/test_bug_hunt_suspicions.py`); suspicions 1, 5 and 7 are owner decisions and were not touched.
- Not verified: that any of the three fixed bugs ever changed a stored result.
### fix(corpus): the README of a candidate is read at its pinned commit (2026-10-25 20:18 +03:00, Issue #498, suspicion 6 of the bug hunt)
- `scripts/candidates_build.py` (`read_repo`) read the README of the head of the default branch, also when the list supplied a commit, so "the README names the paper" could describe a newer README than the one at the pinned commit. Proven first (two new cases in `tests/test_candidates.py` failed on the old code); the README is now requested with `?ref=<commit>`. The stored candidate records (`data/candidates/`) were not regenerated: they were made with the old rule, and a re-run would need the network.
- Also corrected here: the times of the entries of #494, #496, #498 (suspicions 2 and 3) in this file were estimates; they now follow the merge times of the pull requests.
- Not verified: that any stored 'README names the paper' answer differs at the pinned commit.
### fix(diagnosis): a missing path is a data file only when it has the word data (2026-10-25 20:17 +03:00, Issue #498, suspicion 3 of the bug hunt)
- `src/diagnosis/classifier.py` (`classify_exception`): `data` anywhere in a missing path made it DATA_NOT_ACCESSIBLE, so `metadata_utils/config.yaml`, `database.yml` and `src/metadata.py` were classified as missing data files. Proven first (three cases in `tests/test_diagnosis_classifier.py` failed on the old code); the rule now needs `data`, `dataset` or `datasets` as a word of the path (`data/x`, `datasets/a`, `data_dir`); the extension rule is unchanged. Eight positive cases and the tests against the stored categories of Pilots 1 to 4 still pass, so no stored category changes.
- Not verified: that any stored run was misclassified by the old rule (none is known).
### fix(corpus): the quote guard finds a value as a whole number (2026-10-25 20:16 +03:00, Issue #498, suspicion 2 of the bug hunt)
- `src/quote_guard.py`: `value_as_printed` was looked up as a plain substring of the page, so `0.5` was 'found' inside `10.55`, `0.52` or `1.5.2`. Proven first (three new cases in `tests/test_quote_guard.py` failed on the old code); now `find_value_on_page` requires a whole number (the quote itself is still a verbatim substring). Whole values, values with a spread, percents and numbers split before the decimal point still pass (five positive cases).
- Evidence that nothing stored changed: the guard was re-run on all 36 answers of `data/claims/paper_*.json` against `data/pdfs/`; status and value match are identical to `data/claims/guard_report.json` (not rewritten).
- Not verified: that the old rule ever let a wrong claim through (the owner's review of every claim is the other safeguard).
### feat(web): a dashboard database built from the real stored runs (2026-10-25 20:13 +03:00, Issue #496)
- `scripts/build_demo_db.py` writes `data/dashboard_demo.db` (ignored by git; the project database is not touched): 12 papers and the synthetic control (a known-answer test, labeled as such), one score each, the best of the stored runs scored with `src/score_run.py` against the accepted claims; the run ID names the directory and the summary names the setting. Start it with `python -m src.web --db-url sqlite:///data/dashboard_demo.db`. Tests: `tests/test_build_demo_db.py` (an empty directory gives an empty database; one best record per paper). Screenshots of the list, three detail pages, a badge and a report: `docs/evidence/demo2/`.
- What the rows are: the scorer's output, not a validation. Because claims are matched by question ID, Tier 2 is 0 for every paper with accepted claims (`docs/REAL_VERDICTS.md` section 2).
- Not verified: the layout was not changed (UI decisions are the owner's); no other browser than headless Chrome was used.

### docs(scoring): verdicts on the real stored runs and the K2 positive control (2026-10-25 20:08 +03:00, Issue #494)
- `scripts/real_verdicts.py` scores the stored runs of `paper_003` (six conditions), `paper_004`, `paper_006` (three conditions), `paper_102` and the synthetic control with `src/score_run.py` (no database is written) and applies K2 to their outputs; `docs/REAL_VERDICTS.md` is rendered from `data/real_verdicts/verdicts.json`. Tests: `tests/test_real_verdicts.py`.
- Findings (all in the document): the CLI path never matches a real claim (claims are keyed by question ID, metrics by extracted name: Tier 2 0.0 everywhere); `paper_003` aligned by hand is 0.473 against 0.459 (3.05%, Tier 2 100, `Verified`); the `paper_006` claims are Arcene numbers and the run reads bank-marketing (meaningless); `paper_102` has no accepted claim yet gets `Partially Verified`; K2 passed `paper_003` only by coincidence of dense numbers and failed `paper_006` (fraction against percent scale) and `paper_102` (its quick start uses random toy data). The expected K2 positive control was not obtained.
- Not verified: that any real run reproduces a printed table value; the owner's decision on the three scorer questions listed in section 5 of the document.

### docs(report): AI assistance statement (2026-10-25 20:10 +03:00, Issue #492)
- The report ends with a short "AI assistance statement" in section 10: the work was compiled with AI assistance; claims are accepted by a person only; numbers come from stored records through scripts. The conversation with the assistant is not included anywhere. This follows the owner's decision of 2026-10-25.
- Not verified: whether the universities or venues to which the report is sent require a specific wording.

### docs: results of the automatic search of round 3 (2026-10-25 08:55 +03:00, Issue #489)
- `docs/AUTO_SEARCH_ROUND3.md` section 10 (generated by `scripts/auto_search3.py report`, with hand notes), the generated `autosearch3` block and section 6.10 of the report (`scripts/report_numbers.py`; `--check` passes), D11 in `docs/PENDING.md`, the README and this status. The search stopped because the pool of stage 7 was used up (not on a stop condition of the protocol). Task 4 of the night (blind extraction and form) was skipped: no candidate passed both K1 and K2.
- Evidence: ruff and pytest in the pull request; one new test for the report block.
- Not verified: that K2 can pass on a real reproduction (no known positive case was run).

### data(corpus): automatic search of round 3, runs a3_132 to a3_135 (2026-10-25 08:42 +03:00, Issue #473)
- 4 new runs from `data/auto_search3/` (snapshot of the search that started 2026-10-24T20:59:14+00:00; 3399 candidates checked in all so far, 135 run, K1 passed 2, K2 passed 0, both 0). Outcomes of this batch: run 4. K2 passed in this batch: none.
- Protocol: `docs/AUTO_SEARCH_ROUND3.md`. Selected, non-representative list, not a success rate; a K2 pass is a match candidate, not a verified result. Local paths replaced by `<REPO>` and `<HOME>`.
- Evidence: ruff and pytest below in the pull request.
- Not verified: that any matched number means the same thing as the paper's number.

### data(corpus): automatic search of round 3, runs a3_112 to a3_131 (2026-10-25 08:28 +03:00, Issue #473)
- 20 new runs from `data/auto_search3/` (snapshot of the search that started 2026-10-24T20:59:14+00:00; 3375 candidates checked in all so far, 131 run, K1 passed 2, K2 passed 0, both 0). Outcomes of this batch: install 4, run 16. K2 passed in this batch: none.
- Protocol: `docs/AUTO_SEARCH_ROUND3.md`. Selected, non-representative list, not a success rate; a K2 pass is a match candidate, not a verified result. Local paths replaced by `<REPO>` and `<HOME>`.
- Evidence: ruff and pytest below in the pull request.
- Not verified: that any matched number means the same thing as the paper's number.

### docs(corpus): stage 7 topics for the automatic search of round 3 (2026-10-25 07:30 +03:00, Issue #473)
- Stages 1 to 6 were used up (2,992 candidates checked, 118 run, 2 passed K1, none K2). The protocol gets a seventh stage of 16 domain topics, added before its search and without looking at any candidate; `scripts/auto_search3.py` lists them. Rules unchanged. Correction: the stage 6 paragraph of the protocol says it was added at 06:45; the pull request was made at about 06:30.
- Evidence: ruff and pytest in the pull request.
- Not verified: how many new candidates stage 7 yields.

### data(corpus): automatic search of round 3, runs a3_098 to a3_111 (2026-10-25 07:03 +03:00, Issue #473)
- 14 new runs from `data/auto_search3/` (snapshot of the search that started 2026-10-24T20:59:14+00:00; 2821 candidates checked in all so far, 111 run, K1 passed 2, K2 passed 0, both 0). Outcomes of this batch: install 5, no_metric_line 1, run 8. K2 passed in this batch: none.
- Protocol: `docs/AUTO_SEARCH_ROUND3.md`. Selected, non-representative list, not a success rate; a K2 pass is a match candidate, not a verified result. Local paths replaced by `<REPO>` and `<HOME>`.
- Evidence: ruff and pytest below in the pull request.
- Not verified: that any matched number means the same thing as the paper's number.

### docs(corpus): stage 6 topics for the automatic search of round 3 (2026-10-25 06:45 +03:00, Issue #473)
- Stages 1 to 5 were used up (2,508 candidates checked, 106 run, 2 passed K1, none K2). The protocol gets a sixth stage of 16 algorithm and method topics, added before its search and without looking at any candidate; `scripts/auto_search3.py` lists them. Rules unchanged.
- Evidence: ruff and pytest in the pull request.
- Not verified: how many new candidates stage 6 yields.

### data(corpus): automatic search of round 3, runs a3_088 to a3_097 (2026-10-25 05:59 +03:00, Issue #473)
- 10 new runs from `data/auto_search3/` (snapshot of the search that started 2026-10-24T20:59:14+00:00; 2364 candidates checked in all so far, 97 run, K1 passed 2, K2 passed 0, both 0). Outcomes of this batch: install 1, passed K1 2, run 7. K2 passed in this batch: none.
- Protocol: `docs/AUTO_SEARCH_ROUND3.md`. Selected, non-representative list, not a success rate; a K2 pass is a match candidate, not a verified result. Local paths replaced by `<REPO>` and `<HOME>`.
- Evidence: ruff and pytest below in the pull request.
- Not verified: that any matched number means the same thing as the paper's number.

### data(corpus): automatic search of round 3, runs a3_068 to a3_087 (2026-10-25 04:49 +03:00, Issue #473)
- 20 new runs from `data/auto_search3/` (snapshot of the search that started 2026-10-24T20:59:14+00:00; 1924 candidates checked in all so far, 87 run, K1 passed 0, K2 passed 0, both 0). Outcomes of this batch: install 2, no_metric_line 2, run 16. K2 passed in this batch: none.
- Protocol: `docs/AUTO_SEARCH_ROUND3.md`. Selected, non-representative list, not a success rate; a K2 pass is a match candidate, not a verified result. Local paths replaced by `<REPO>` and `<HOME>`.
- Evidence: ruff and pytest below in the pull request.
- Not verified: that any matched number means the same thing as the paper's number.

### fix(corpus): the search survives a folder that cannot be deleted and a crash of the runner (2026-10-25 04:40 +03:00, Issue #473)
- The search stopped after 76 runs: deleting the installed packages of candidate a3_077 failed (`FileNotFoundError`, a path longer than Windows allows) in `cleanup_run`, and the error ended the process. `force_remove` now falls back to emptying the folder with robocopy; a folder that still cannot be deleted is reported and the search goes on; an exception of the runner is recorded as a `harness` result. The candidate a3_077 had no stored result, so it is run again from the start (it never produced a result). Tests for the three cases.
- Evidence: ruff and pytest in the pull request.
- Not verified: other causes of an ended process.

### docs(corpus): stage 5 topics for the automatic search of round 3 (2026-10-25 04:00 +03:00, Issue #473)
- 76 candidates were run and none passed K1; stage 4 is nearly used up. The protocol gets a fifth stage of 16 method and library topics, added before its search and without looking at any candidate; `scripts/auto_search3.py` lists them. Rules unchanged.
- Evidence: ruff and pytest in the pull request.
- Not verified: how many new candidates stage 5 yields.

### data(corpus): automatic search of round 3, runs a3_050 to a3_067 (2026-10-25 03:23 +03:00, Issue #473)
- 18 new runs from `data/auto_search3/` (snapshot of the search that started 2026-10-24T20:59:14+00:00; 1630 candidates checked in all so far, 67 run, K1 passed 0, K2 passed 0, both 0). Outcomes of this batch: install 2, no_metric_line 2, run 14. K2 passed in this batch: none.
- Protocol: `docs/AUTO_SEARCH_ROUND3.md`. Selected, non-representative list, not a success rate; a K2 pass is a match candidate, not a verified result. Local paths replaced by `<REPO>` and `<HOME>`.
- Evidence: ruff and pytest below in the pull request.
- Not verified: that any matched number means the same thing as the paper's number.

### docs(corpus): stage 4 topics for the automatic search of round 3 (2026-10-25 02:35 +03:00, Issue #473)
- Stages 1 to 3 were used up (1,381 candidates checked, 54 run, none passed K1). The protocol gets a fourth stage of 16 general and paper-related topics, added before its search and without looking at any candidate; `scripts/auto_search3.py` lists them. Rules unchanged.
- Evidence: ruff and pytest in the pull request.
- Not verified: how many new candidates stage 4 yields.

### data(corpus): automatic search of round 3, runs a3_039 to a3_049 (2026-10-25 02:21 +03:00, Issue #473)
- 11 new runs from `data/auto_search3/` (snapshot of the search that started 2026-10-24T20:59:14+00:00; 1223 candidates checked in all so far, 49 run, K1 passed 0, K2 passed 0, both 0). Outcomes of this batch: install 5, run 6. K2 passed in this batch: none.
- Protocol: `docs/AUTO_SEARCH_ROUND3.md`. Selected, non-representative list, not a success rate; a K2 pass is a match candidate, not a verified result. Local paths replaced by `<REPO>` and `<HOME>`.
- Evidence: ruff and pytest below in the pull request.
- Not verified: that any matched number means the same thing as the paper's number.

### data(corpus): automatic search of round 3, runs a3_026 to a3_038 (2026-10-25 02:13 +03:00, Issue #473)
- 13 new runs from `data/auto_search3/` (snapshot of the search that started 2026-10-24T20:59:14+00:00; 1031 candidates checked in all so far, 38 run, K1 passed 0, K2 passed 0, both 0). Outcomes of this batch: install 1, run 12. K2 passed in this batch: none.
- Protocol: `docs/AUTO_SEARCH_ROUND3.md`. Selected, non-representative list, not a success rate; a K2 pass is a match candidate, not a verified result. Local paths replaced by `<REPO>` and `<HOME>`.
- Evidence: ruff and pytest below in the pull request.
- Not verified: that any matched number means the same thing as the paper's number.

### data(corpus): automatic search of round 3, runs a3_015 to a3_025 (2026-10-25 01:11 +03:00, Issue #473)
- 11 new runs from `data/auto_search3/` (snapshot of the search that started 2026-10-24T20:59:14+00:00; 794 candidates checked in all so far, 25 run, K1 passed 0, K2 passed 0, both 0). Outcomes of this batch: install 3, run 8. K2 passed in this batch: none.
- Protocol: `docs/AUTO_SEARCH_ROUND3.md`. Selected, non-representative list, not a success rate; a K2 pass is a match candidate, not a verified result. Local paths replaced by `<REPO>` and `<HOME>`.
- Evidence: ruff and pytest below in the pull request.
- Not verified: that any matched number means the same thing as the paper's number.

### docs(corpus): stage 3 topics for the automatic search of round 3 (2026-10-25 01:10 +03:00, Issue #473)
- Stages 1 and 2 were used up (780 candidates checked, 22 run, none passed K1). The protocol gets a third stage of 16 general topics, added before its search and without looking at any candidate; `scripts/auto_search3.py` lists them. Rules unchanged.
- Evidence: ruff and pytest in the pull request.
- Not verified: how many new candidates stage 3 yields.

### data(corpus): automatic search of round 3, runs a3_001 to a3_014 (2026-10-25 00:42 +03:00, Issue #473)
- 14 new runs from `data/auto_search3/` (snapshot of the search that started 2026-10-24T20:59:14+00:00; 442 candidates checked in all so far, 14 run, K1 passed 0, K2 passed 0, both 0). Outcomes of this batch: install 4, run 10. K2 passed in this batch: none.
- Protocol: `docs/AUTO_SEARCH_ROUND3.md`. Selected, non-representative list, not a success rate; a K2 pass is a match candidate, not a verified result. Local paths replaced by `<REPO>` and `<HOME>`.
- Evidence: ruff and pytest below in the pull request.
- Not verified: that any matched number means the same thing as the paper's number.

### feat(corpus): script of the automatic search of round 3 with the K2 match test (2026-10-25 00:40 +03:00, Issue #471)
- `scripts/auto_search3.py` (`pool`, `run`, `report`) and `tests/test_auto_search3.py` (84 cases): the two-stage pool without the repositories of earlier rounds; S1 to S6 and K1 from `scripts/demo_set.py`; K2 (meaningful numbers of `stdout.log`, same-spelling match on the PDF pages, at least 2 different numbers and one on a `Table <n>` page); arXiv requests at most once in 3 seconds; static checks of the next candidates run in a thread while the sandbox is busy; cleanup of the staging, wheel and sandbox output folders of a candidate after its run; the stop conditions of `docs/AUTO_SEARCH_ROUND3.md` section 6; a second start skips candidates that have a result. No run was made.
- Evidence: ruff clean; 1,123 passed, 9 skipped.
- Not verified: the script against the real GitHub search, a real PDF and a real sandbox run (the first real use is the search itself).

### docs(corpus): protocol of the automatic search of round 3, written before any pool was searched (2026-10-25 00:05 +03:00, Issue #469)
- `docs/AUTO_SEARCH_ROUND3.md`: GitHub pool by topic (two stages) in SHA-256 order, static rules S1 to S6 as in `docs/DEMO_SET.md`, run test K1 (install limit 1200 s, run limit 600 s), the new match test K2 (at least 2 different meaningful numbers of the run output found in the paper's text, one of them on a page with a `Table <n>` line), stop conditions (9 hours, 150 runs, 8 passing both, free disk under 30 GB), reporting with Wilson intervals. Written without looking at any candidate list. A K2 pass is a match candidate, never verified; the list is selected and not a success rate.
- Evidence: documentation only; no run, no pool, no candidate.
- Not verified: that K2 is a good filter (not tested on any run yet).

### docs: Round 2 results in the candidate documents, PENDING, README and the report (2026-10-24 23:40 +03:00, Issue #465)
- `scripts/candidates_build.py --doc` now also writes the generated Round 2 results (tables, Wilson intervals, outcomes) into `docs/CANDIDATES.md` and section 12 of `docs/CANDIDATE_RUNS_ROUND2.md`; `scripts/report_numbers.py` has the block `candidateround2` (`--check` passes); PENDING D9, README and this file updated.
- Not verified: any table match of the passing candidate.

### data(corpus): blind claim extraction for cand_002, the one candidate that passed (2026-10-24 23:38 +03:00, Issue #464)
- Three independent fresh `claude -p` passes (tools Read, Write, Edit, Glob, Grep) over a blind packet asked for the paper values that match the five metrics of the run output; stored under `data/candidates/round2/cand_002/blind_extraction/`. No question has two agreeing passes with a value; one pass found only the simulation settings (FP 0.1 %, FN 30 %), which are settings and not results. No claim candidate exists and no claim is accepted. The form for the owner is outside the repository.
- Not verified: the paper PDF (not downloadable; the Europe PMC full-text XML was used, so `page` is a text chunk number).

### data(corpus): repair round closed: 1 of 14 passed after repair (2026-10-24 23:35 +03:00, Issue #457)
- cand_020 recorded as not repairable (four pins exist only as source distributions on PyPI; the README takes them from an extra wheel index). The round-2 evaluation (`python scripts/candidate_round2.py summary`, `data/candidates/round2/evaluation.json`): 15 repair logs (the 14 of round 1 and cand_020); passed: cand_002 only. cand_011 ran to exit 0 but printed no `name: number` line. No other risky candidate qualified.
- Not verified: any table match for cand_002 (none found in the paper text).

### data(corpus): eligibility of the risky candidates for the repair round (2026-10-24 23:35 +03:00, Issue #457)
- `data/candidates/round2/eligibility.json`, written before any risky candidate is run: of the 11 risky candidates one is eligible (cand_020, data inside the repository), two are `command_incomplete` (cand_015, cand_016), and eight are not eligible, each with the reason (no README address, an account needed, a 5.3 GB file, a client that is not available, a compile step). Download total: 0 GB of the 20 GB.
- Not verified: sizes of cand_016, cand_017 and cand_022 (not found).

### data(corpus): repair round, cand_011; requirements_file filter fixed (2026-10-24 23:34 +03:00, Issue #457)
- cand_011 ran with the README's Python 3.8 and requirements file: install INSTALLED, run COMPLETED, exit 0, but the output is a dict of values with no 'name: number' line, so by the protocol it did not pass (recorded as `no_metric_line`, noted as a limit of the pattern). The first attempt was a harness fault (the install phase read all requirement files) and is kept as `attempt_1_harness_fault`, not counted; `FilteredStager` now removes the unnamed files from the staged copy (section 11 of the protocol).
- Not verified: a table match for cand_011.

### feat(corpus): sixth repair kind of the repair round, requirements_file (2026-10-24 23:25 +03:00, Issue #457)
- Section 10 of `docs/CANDIDATE_RUNS_ROUND2.md` (dated amendment, written before the run of cand_011) and `FilteredStager` in `scripts/candidate_round2.py`: only the requirement file the README names is installed, the files are not edited. Two tests. 1,039 tests pass, 9 skipped.

### data(corpus): repair round, first 11 candidates (cand_001 to cand_010 and cand_013) (2026-10-24 23:24 +03:00, Issue #457)
- Records under `data/candidates/round2/` (a `repair_log.json` per candidate). cand_002 passed after one repair (Python 3.9 image); cand_009 stopped at the third error; cand_001, 003, 004, 005, 006, 007, 008, 010 and 012 are not repairable by the five allowed repairs, each with the log line and the reason; cand_013 stays `command_incomplete`. cand_011 is not in this batch. `summary` also reports the `stopped` entry.
- Not verified: that cand_002's output is comparable with any table of its paper (no printed value occurs in a table).

### feat(corpus): run mechanism of the candidate repair round (2026-10-24 22:16 +03:00, Issue #457)
- `scripts/candidate_round2.py` (`fetch`, `run`, `summary`) and `tests/test_candidate_round2.py`: one repair attempt per call, from the `repair_log.json` of the candidate; the rules of `docs/CANDIDATE_RUNS_ROUND2.md` are checked in code (allowed repair kinds, a log line for every repair, at most two repairs, no writable copy of the repository, an attempt is never run twice, round 1 records are not touched). Run limit 3600 s, install 1800 s, `--memory 50% --cpus 4`. 1,037 tests pass, 9 skipped.
- Not verified: the runner against a real container (the first real attempt is the check).

### docs(corpus): protocol of the candidate repair round, written before any round-2 run (2026-10-24 22:14 +03:00, Issue #455)
- `docs/CANDIDATE_RUNS_ROUND2.md`: scope (the 14 round-1 candidates and the risky candidates whose README data can be downloaded within 20 GB, 3 GB per file), the five allowed repairs and the forbidden ones, at most two repair rounds per candidate, the pass definition of round 1 plus the paper-table match, limits (run 3600 s, install 1800 s, one sandbox run at a time), and the three separate counts with Wilson intervals from a script. Round 1 and its records are not touched.
- Not verified: nothing has been run in round 2 yet.

### docs: status documents and the report brought up to date (2026-10-24 21:06 +03:00, Issue #452)
- `docs/PENDING.md` (done items marked with their pull requests; new D9 candidate papers and D10 two scorer rules; the repository is public), the Current Status of `README.md` and of this file, and two new sections of `docs/report/REPORT.md` (6.8 candidate runs, 6.9 tolerance probe) whose numbers are generated blocks (`candidateruns`, `toleranceprobe` in `scripts/report_numbers.py`; `--check` passes). 1,028 tests pass, 9 skipped.
- Not verified: that the owner's summary outside the repository says the same; that every other document that quotes a number (for example the introduction document) is current.

### docs(devops): a fresh run from a clean clone completed, paper_006 end to end (2026-10-24 21:04 +03:00, Issue #441)
- `docs/evidence/clean_clone/WALKTHROUGH.md` Update 2: a clone of the public repository followed through the README to `cli.py score paper_006 --cpus 8 --timeout 7200` and `cli.py diagnose`. `init-db` restored 13 accepted claims; the run COMPLETED (exit 0, run phase 1,092.54 s, `accuracy 0.8886`, `auroc 0.892`); the score used 2 accepted claims, none found in the output, so Tier 2 = 0 ("nothing was compared") and the total is 61.25, Needs Review. The whole walk-through took 2,490 s. Not a protocol run (CPUs and time limit set by hand); no accepted claim was reproduced.

### docs: bug hunt, three proven bugs fixed, seven suspicions listed (2026-10-24 20:37 +03:00, Issue #447)
- `docs/BUG_HUNT.md`: what was read, the three proven bugs with their pull requests (#448 time-metric names, #449 substring number match, #450 half-even score display; each with a test that failed on the old code first), and seven suspicions that could not be proven without a decision of the owner (the 0.05 absolute allowance for small values, the substring test of the quote guard, the `data` rule of the classifier, the dashboard's score and latest run of different runs, Tier 3 never fed by `cli.py score`, the README read at the head commit, the text pattern of the pass rule). Not every line of every file was traced.

### fix(cli): the printed score is the stored score (2026-10-24 20:36 +03:00, Issue #447)
- Found by the bug hunt (seen in the demo output): `cli.py score` printed the tiers and the total with one decimal, which rounds half to even, so a stored 58.25 was printed as 58.2 (and 93.25 as 93.2, 91.75 as 91.8) while the summary line, the database and the dashboard say 58.25. Proven first (`tests/test_cli_score.py`, written before the fix; it failed on the old code). The breakdown now prints two decimals. The demo script's step 5 output was re-captured. No stored score changed.

### fix(corpus): a printed number is looked up as a whole number in the paper's text (2026-10-24 20:35 +03:00, Issue #447)
- Found by the bug hunt: `scripts/demo_set.py` (`locate_numbers`) looked a printed number up with a plain substring search, so `1.5` matched inside `21.55`, `10.5`, `1.52` or a version `1.5.2`. Proven first (`tests/test_demo_set.py`, written before the fix; it failed on the old code). New `pages_with_number`: the number must not be part of a longer number. For `demo_020` (arXiv 2511.16760) the number `1.5` is on PDF pages 23, 39 and 40 with the new rule, not on page 41 (checked against the downloaded PDF). The generated block of `docs/DEMO_SET.md` 7.3 was not regenerated and carries a dated correction note; the run records of the demo set are untouched.

### fix(scoring): a metric is a time metric by the words of its name, not by letters inside other words (2026-10-24 20:33 +03:00, Issue #447)
- Found by the bug hunt: `Tier2MetricsEvaluator` took any metric whose name contains the letters `ms` or `sec` as a time metric, so `rmse`, `num_params` and `n_items` were judged by the relative rule only and lost the absolute allowance that any other metric between 0 and 1 gets. Proven first: with claimed 0.5 and reproduced 0.54, `accuracy` is MATCHED and `rmse` is PARTIAL. New `is_time_metric` (long words anywhere in the name; `sec`, `secs`, `ms`, `msec` only as a whole part of the name); `tests/test_time_metric_names.py` (22 cases, written first). No stored real score changes (no accepted claim is named like these metrics). The tolerance probe was regenerated: for `paper_003` (`rmse` 0.473) the status now leaves Verified at -20 % / +20 % instead of -5 % / +10 % (the numbers of the earlier #442 entry for `paper_003` are superseded); `paper_006` and `paper_102` are unchanged.

### docs: demo script with proven examples only (2026-10-24 20:29 +03:00, Issue #444)
- New `docs/DEMO_SCRIPT.md` (9 steps, about 4 min 40 s): dashboard, the synthetic true/false claim (91.75 / 56.75), four stored runs of `paper_003` and `paper_006` with the same metrics, Tier 3 (three seeds of `paper_006`), a stored run scored as "nothing was compared", `cli.py diagnose`, the tolerance probe, the candidate runs (0 of 14, so no candidate example), and the limits with Wilson intervals (Pilot 4 = 1 of 6, 3.0 % to 56.4 %; ReScience C 0 of 65). Every command was run for real and its output is pasted; each step says what it shows and does not show. Two dashboard screenshots are in `docs/evidence/demo/` (headless Chrome, localhost only).
- Found while preparing it: the dashboard page of `paper_006` shows the score of the stored Pilot 3 run next to the "Latest run" of the Pilot 1 record in the database, so the two do not belong to the same run (the database loads the Pilot 1 records only). The demo says so. Running `cli.py score ... --from-run` stored one score row in the local, git-ignored database. Not verified: how the dashboard looks in another browser.

### fix(scoring): tolerance probe covers all four stored runs of paper_003 (2026-10-24 20:26 +03:00, Issue #442)
- The first version probed one of the four stored completed runs of `paper_003` (the stability table lists four, as for `paper_006`). `scripts/tolerance_probe.py` now probes all four; their metrics are identical, so the tables of `docs/TOLERANCE_PROBE.md` are unchanged and the document lists the four run folders. No other number changed.

### feat(scoring): tolerance probe on real runs with hand-moved claims (2026-10-24 20:25 +03:00, Issue #442)
- New `scripts/tolerance_probe.py`, `data/tolerance_probe/results.json`, `docs/TOLERANCE_PROBE.md` (generated; `--check` compares the files with the stored runs). The stored runs of paper_003, paper_006 (four runs, identical values) and paper_102 are scored by the Tier 2 calculation of `src/scoring.py` with the run's own value (a true claim) and with every metric moved by 0.5, 1, 2, 5, 10 and 20 % up and down. For paper_006 the status leaves Verified at -10 % / +10 %; for paper_003 at -5 % / +10 %; for paper_102 at -10 % / +10 % (read from the generated tables). A small value between 0 and 1 (for example `boundary_conflict` = 0.0167) stays MATCHED at 20 % because of the absolute allowance.
- The claims are hand-made, not an error of a real paper; the real-world false-positive and false-negative rates are not measured. No accepted claim of the owner has the question ID of a metric of any probed run, so there is no row with a real accepted claim (not verified whether a run's value belongs to one). 7 new tests.

### data(corpus): the 14 candidate papers run once in the sandbox, 0 of 14 passed (2026-10-24 20:25 +03:00, Issue #437)
- Protocol `docs/CANDIDATE_RUNS.md` (#438), mechanism `scripts/candidate_runs.py` (#439). Result (`data/candidates/runs/evaluation.json`, records in `data/candidates/runs/<id>/`): 14 selected candidates, 1 not run because its listed command holds only placeholders (cand_013), 13 run once, **0 passed**; Wilson 95 % interval of 0 / 14 is 0.0 % to 21.5 % (0 / 13: 0.0 % to 22.8 %), computed by `scripts/candidates_build.py --doc`. Failures: 6 installation failed (pinned versions not available for Python 3.11 or unresolvable), 3 module missing at run time (the installation status was SKIPPED, that is, no requirements file was found), 2 wrote into the read-only repository, 1 data file missing, 1 file path missing (a .png path), 1 command incomplete.
- `docs/CANDIDATES.md` now has a generated Run results section (counts, causes by the classifier rules, every run). This is a selected list, not a sample, and not a success rate. Not verified: whether a repair (extra requirements, Python version, a writable copy) would make any of them run; the protocol forbids repairing.
- No candidate passed, so no PDF was fetched and no blind claim extraction was made for the candidates (step d of the task is not applicable).

### feat(corpus): run mechanism for the candidate runs (2026-10-24 19:27 +03:00, Issue #437)
- `scripts/run_pilot.py` (`pilot4_entry`): a corpus entry may name a `working_dir` and a `shell_command` (run by `sh -c`); none of the existing corpora has either key, so their behavior does not change. New `scripts/candidate_runs.py` runs the candidates of `data/candidates/run_plan.json` once each with the limits of `docs/CANDIDATE_RUNS.md` (50% memory, 4 CPUs, 1800 s run limit), classifies each run with `classify_run` of the demo set, shortens long logs, replaces local paths, and never runs a candidate that already has a result. 9 new tests; no candidate has been run by this change.

### docs(corpus): protocol of the candidate runs, written before any run (2026-10-24 19:25 +03:00, Issue #437)
- New `docs/CANDIDATE_RUNS.md` and `data/candidates/run_plan.json`: the 14 candidates of status ready, fixable and two_step are run once each in the sandbox (`--memory 50% --cpus 4`, run limit 1800 s, no network, no retry, no correction after a result); the 11 risky and 4 excluded are not run. The commands are the lists' commands; a placeholder is completed only from the README at the pinned commit, and `cand_013` (README gives only placeholders) is recorded as `command_incomplete` and not run. Pass = install INSTALLED/SKIPPED, run COMPLETED with exit 0, and a numeric metric line.
- Not verified: no candidate has been run yet; whether the printed numbers match a table of a paper is decided later by string match plus a person.

### docs(devops): the six sandbox images rebuilt from scratch, with time and size (2026-10-24 19:20 +03:00, Issue #435)
- All six images of the README section "Build the Sandbox Image" were built with `docker build --no-cache`; every build exited with code 0, 43 to 90 s each, 401 s in total. The table (time, size, command) is in `docs/ENVIRONMENT.md`; the README no longer says that the compiler and Python 3.8/3.9 commands have not been run.
- Not verified: the build time on a machine without the base images, and on Linux or macOS. One measurement per image.

### data(corpus): 29 candidate papers from the owner's lists, checked but not run (2026-10-23 00:30 +03:00, Issue #433)
- New `data/candidates/` (`input.json` from the lists, `papers.json` in the seed format, `evaluation.json`, `verify_corpus.json`), `scripts/candidates_build.py`, and the generated `docs/CANDIDATES.md`. For each of the 29 candidates the head commit, license, size and archive/fork state were read from GitHub, the paper title and year from the paper's page, and the README was searched for the paper's id: all 29 READMEs name the paper. `scripts/verify_corpus.py` on the candidates file: 29 of 29 passed (paper page, repository, allowed license, script at the pinned commit).
- Status given by the lists: ready 9, fixable 4, two_step 1, risky 11, excluded 4. They are NOT in `data/seed_papers.json` (the evaluation set of the pilots; its tests expect 6 papers from 2020 to 2024).
- Not verified: no candidate was run; run time, offline installation, writes into the read-only repository, and the table of the paper that the output matches are unknown for all of them.

### docs: publication readiness audit (2026-10-22 23:50 +03:00, Issue #431)
- New `docs/PUBLIC_READINESS.md`: a scan of 1,045 tracked files, 423 commits, 220 issues and 210 pull requests for keys, tokens, e-mail addresses, local paths, large files and copyrighted files. No key, token or private key was found; no local path is left in the current files. The owner's e-mail address is in the metadata of 228 commits (a decision, since only a history rewrite or a new repository removes it). A table lists what to decide before publishing.
- Nothing was changed in the history, the account settings, or the visibility of the repository.
- Not verified: no dedicated secret scanner was run; issue and pull request comments and 11 of 12 screenshots were not read; the size of the stored paper quotes was not measured.

### docs: list of pending steps, owner decisions and open work (2026-10-22 00:40 +03:00, Issue #429)
- New `docs/PENDING.md`: eight owner decisions (repository access, gold set 2, demo claims, `paper_004` and `paper_005`, ReScience, demo papers, the Tier 3 rule, questions for the mentors), five tasks that need no decision, the state of every open issue, what the project does not do, known limits, and how to start a long job without it being cut.
- Evidence: every item names its source (documents, issue comments, records). Test and lint results are in the pull request.
- Not verified: the document is a snapshot of 2026-10-22; the owner's own state (forms, decisions) was taken from the assistants' records, not from the owner.

### docs: the path of one paper through the tool, with times (2026-10-22 00:10 +03:00, Issue #427)
- New `docs/WORKFLOW.md`: 13 steps from adding a paper to the dashboard, who does each step, and how long it takes. Each time is marked measured (with the record it comes from) or estimate. Examples: `paper_102` about 6 to 7 min of machine time, `paper_003` 2,660 s cold and 1,549 s with the environment cache.
- Not verified: the estimated steps (adding a paper, source check, data fetch, claim extraction, claim acceptance) were not timed; the build phase has no recorded time.

### data(corpus): demo set run and results (2026-10-21 22:34 +03:00, Issue #421)
- `scripts/demo_set.py report` (results section generator) and the run itself: `data/demo_set/{pool.json, evaluation.json, papers.json, runs/}`, `docs/DEMO_SET.md` section 7.
- Result (from `evaluation.json`): the pool of 464 candidates was checked up to the 2.5-hour limit (416 checked), 22 candidates passed S1 to S6 and were run once, and 1 passed K1: `demo_020` (`skimeur/pioneer-detection-method`, arXiv 2511.16760). The set is smaller than five. This is a hand-picked demo set, not a success rate.
- `demo_020` passed on a setup value (`True post-break alpha: 1.5`); none of its 48 printed decimals (three or more decimals) was found in the paper's text, so a match with a paper table is not verified.
- Evidence: full suite below; `ruff check .` clean.
- Not verified: that any output number equals a number of the paper.

### feat(ai): six gaps of the failure classifier closed (2026-10-21 19:54 +03:00, Issue #424)
- `src/diagnosis/classifier.py`: rules for `PermissionError` (`PERMISSION_DENIED`), CUDA out of memory (`GPU_OUT_OF_MEMORY`), no space left on device (`NO_SPACE_LEFT`), `HTTPError` and `ConnectionRefusedError` (both `DATA_NOT_ACCESSIBLE`), and a missing `.pt` file (`DATA_NOT_ACCESSIBLE`). `tests/test_diagnosis_gaps.py` holds one case per line plus six unchanged-behaviour cases.
- Validation set (labels not edited): before, real runs 45 / 46 and probes 7 / 12 right at all levels; after, 46 / 46 and 12 / 12 (`scripts/evaluate_diagnosis_classifier.py`). The rules were written from these very lines, so the set no longer measures the classifier on new logs; `docs/DIAGNOSIS_VALIDATION.md` section 5 says so. The hand-written analyses of the six answers moved from `analysis.json` to `closed_gaps.json`; `docs/report/REPORT.md` prose and the generated block were updated.
- Evidence: full suite 968 passed, 11 skipped (worktree without ignored data); `ruff check .` clean; `report_numbers.py --check` in sync.
- Not verified: the rules on any log that is not in the set; a real run that ends in one of these errors was not made.

### feat(corpus): demo set script (S1 to S6 and the run test K1) (2026-10-21 19:48 +03:00, Issue #421)
- `scripts/demo_set.py` (`pool` and `run`), 26 tests in `tests/test_demo_set.py`; `scripts/corpus_expansion.py` gets one option (`stated_size_rule`, default unchanged) so that the demo set can skip the README size statement that `docs/DEMO_SET.md` does not have. The run uses `run_pilot.run_paper(pilot4=True)` with `--memory 50%`, 4 CPUs, and a 600 s run limit.
- Evidence: full suite 954 passed, 9 skipped; `ruff check .` clean.
- Not verified: the script has not been run against GitHub or Docker yet (the tests use fakes).

### docs(corpus): demo set rules (written before any candidate was listed) (2026-10-21 19:45 +03:00, Issue #421)
- `docs/DEMO_SET.md`: the mechanical rules S1 to S6, the run test K1, the pool (eight GitHub searches), the hash order, and the stop rule. The set is hand-picked for the dashboard; it is not a random sample and no number of it is a success rate.
- Evidence: documentation only; no search was run and no candidate was opened before this file was written.
- Not verified: the rules have not been applied yet.

### docs(report): final consistency pass (2026-10-20 06:03 +03:00, Issues #48 and #413)
- Final consistency pass: `docs/report/REPORT.md` (new sections 6.4a, 6.5a, 6.6, 6.7; abstract, limitations, conclusion, and reproducibility statement updated; five new generated blocks in `scripts/report_numbers.py`), `README.md` (status, AI layer, quickstart, layout), the Current Status and the milestone counts of this file, and a note in `docs/INTRODUCTION_SOURCES.md` (#48, #413).
- Checks: `report_numbers.py --check` in sync; `verify_sources.py` all verified; `verify_corpus.py` 6 of 6; Turkish-letter scan 0 lines in 889 files.
- Evidence: 2 new tests.
- Not verified: a second reader; the new sections are not in the claim-to-source tables.

### data(scoring): real seed runs of paper_006 (2026-10-20 06:00 +03:00, Issue #48)
- Real seed runs: `paper_006`, seeds 1, 2, 3 (`data/multi_seed_runs/paper_006/`, `multi_seed_summary.json`), `docs/MULTI_SEED.md` section 9, `docs/DIAGNOSIS_COMPARISONS.md` regenerated. Correction: the Progress entry of PR #418 said 7 new tests; it was 6.
- Result (from the summary): `accuracy` 0.8886, 0.8944, 0.8929 (CV 0.276%); `auroc` 0.892, 0.911, 0.905 (CV 0.879%); Tier 3 = 100.0, decided by `auroc`. Seed 1 equals the earlier single runs.
- Evidence: the test file now has 14 cases; full suite below.
- Not verified: more seeds; the data split's own seed; Tier 2 (claims concern Arcene).

### data(scoring): real seed runs of paper_003 (2026-10-20 04:43 +03:00, Issue #48)
- First real seed runs: `paper_003`, seeds 0, 1, 2 (`data/multi_seed_runs/paper_003/`, `multi_seed_summary.json`), `docs/MULTI_SEED.md` section 9, `docs/DIAGNOSIS_COMPARISONS.md` regenerated.
- Result (from the summary): `loss` 0.106, 0.127, 0.119 (CV 7.375%); `rmse` 0.473, 0.47, 0.465 (CV 0.703%); Tier 3 = 65.0 decided by `loss`; `rmse` alone would give 100.0. Seed 0 equals the earlier single runs.
- Evidence: 6 new tests in `tests/test_multi_seed_real.py` (corrected from 7 on 2026-10-20; the count of the full suite went from 912 to 918).
- Not verified: more seeds; Tier 2 (the claim names do not equal the metric names).

### feat(scoring): per-metric Tier 3 in the seed summary (2026-10-20 04:09 +03:00, Issue #48)
- `scripts/run_multi_seed.py`: `tier3.decided_by`, `tier3_by_metric`, `--summarize-only`, `summarize_stored`; `docs/MULTI_SEED.md` says why (a noisy side metric such as a training loss can decide Tier 3). The score rule is unchanged.
- Evidence: 2 new tests; the earlier 29 tests of the file pass unchanged.
- Not verified: on the real seed folders (still running).

### feat(sandbox): GPU check with a modern PyTorch on the RTX 5070 (2026-10-20 03:45 +03:00, Issue #169)
- `scripts/gpu_paper_check.py`, `run_pilot.py --gpus`, `data/gpu_check/` and `docs/ENVIRONMENT.md`: a synthetic paper with `torch==2.8.0` (CUDA 12.8) ran through the real pipeline with `--gpus all` on the RTX 5070.
- Real output (`data/gpu_check/result.json`): torch 2.8.0+cu128, tensor on `cuda:0`, GPU result equal to the CPU result, run report `gpu.used` true (peak 2530 MiB over 1793 MiB before), COMPLETED exit 0 in 45.156 s, isolation intact. Bundled wheels 3.65 GiB, bundling 575.403 s, sandbox install and run 563.407 s.
- Evidence: 8 new tests.
- Not verified: any real paper with the GPU (the seed papers pin PyTorch 1.x); `gpu.used` is a memory-sampling heuristic.

### feat(corpus): week 6 field analysis over 12 papers (2026-10-20 03:30 +03:00, Issue #413)
- `scripts/field_analysis.py`, `data/field_analysis/features.json` and `result.json`, and the generated section 8 of `docs/FIELD_ANALYSIS.md`: setup/run/pilot success rates, human interventions I1 to I4 per paper, the AI autonomy rate, and a descriptive factor table over the 12 papers (#413).
- Result (from the script): pilot success 1 / 12 at the first protocol run and 3 / 12 at the final one; autonomy of the expansion papers 5 / 6 concluded and 1 / 6 succeeded at the final run; seed papers 0 / 6 by construction. Exploratory, n = 12; no significance claimed.
- Evidence: 15 new tests.
- Not verified: the factors against a second extraction.

### docs(corpus): definitions of the week 6 field analysis (2026-10-20 03:27 +03:00, Issue #413)
- `docs/FIELD_ANALYSIS.md`: definitions of the week 6 analysis (pool of 12, reference runs, success rates, human intervention I1 to I4, AI autonomy rate, three descriptive factors), written before the script (#413).
- Evidence: documentation only.
- Not verified: the definitions against the script and the data (next PRs).

### test(ai): validation of the failure classifier on hand-labeled runs (2026-10-20 03:23 +03:00, Issue #36)
- `data/diagnosis_validation/` (46 hand-labeled stored runs, 12 synthetic probes, a written analysis of every wrong answer, generated results), `scripts/evaluate_diagnosis_classifier.py`, and `docs/DIAGNOSIS_VALIDATION.md`.
- Result (from the script): real runs 45 / 46 correct on category, name, and phase together (category 46 / 46); synthetic probes 7 / 12. The labels are not blind; the accuracy is an upper bound. The classifier was not changed.
- Evidence: 10 new tests.
- Not verified: papers outside these logs.

### feat(ai): diagnosis backends with a locked-number check (2026-10-20 03:18 +03:00, Issue #34)
- `src/diagnosis/backends.py` (NullBackend default; optional Anthropic or local backend chosen by environment variables; number lock; graceful fallback), `cli.py diagnose --explain`, and `docs/DIAGNOSIS.md` section 6.
- Evidence: 18 new tests with mock clients only.
- Not verified: any real model (no key and no local model were available).

### feat(ai): explainer of the difference between two runs (2026-10-20 03:16 +03:00, Issue #35)
- `src/diagnosis/compare.py`, `scripts/diagnosis_comparisons.py`, `docs/DIAGNOSIS_COMPARISONS.md`, and `docs/DIAGNOSIS.md` section 8 (rules R1 to R6): the difference between two runs, with "same metrics, different time" kept apart from "different metrics", and no cause named.
- Evidence: 16 new tests; the generated document is checked against the records by a test (9 pairs).
- Not verified: the shift thresholds; the database tag `Needs Review` (not done).

### feat(ai): template-based diagnosis report and cli.py diagnose (2026-10-20 03:12 +03:00, Issue #33)
- `src/diagnosis/report.py` (statements with fields and sources, unknown written as unknown), `cli.py diagnose <run_dir>`, `scripts/diagnosis_examples.py`, and `docs/DIAGNOSIS_EXAMPLES.md` (31 stored runs of Pilots 1 to 4, memory runs, and CPU runs).
- Evidence: 17 new tests; the examples document is checked against the records by a test.
- Not verified: a human reading for clarity and neutrality; no language model is involved.

### feat(ai): rule-based failure classifier (2026-10-20 03:10 +03:00, Issue #32)
- `src/diagnosis/classifier.py` takes over the rules of `scripts/categorize_pilot_failures.py` (the script imports them) and adds `classify_run` and `classify_log_text`.
- Evidence: 18 new tests; the classifier reproduces the stored categories of Pilots 1 to 4 (same category, name, phase, and quoted line); the 35 older failure tests pass unchanged.
- Not verified: correctness against independent labels (#36).

### feat(ai): diagnosis input schema and prompt templates (2026-10-20 03:09 +03:00, Issue #31)
- `docs/DIAGNOSIS.md`, `src/diagnosis/schema.py` (input schema with a source for every value), `src/diagnosis/prompts.py`, and `docs/prompts/` (system prompt and one template per status). Rule-based; no model, network, or key.
- Evidence: 16 new tests in `tests/test_diagnosis_schema.py`.
- Not verified: any use with a real model.

### feat(scoring): multi-seed execution for Tier 3 and synthetic evidence (2026-10-20 03:06 +03:00, Issue #48)
- `src/multi_seed.py` (seed spec, `apply_seed`, per-metric summary), `scripts/run_multi_seed.py` (one real sandbox run per seed, one record per seed in `data/multi_seed_runs/<paper>/seed_<N>/`, `multi_seed_summary.json`), `Tier3StabilityEvaluator.evaluate_by_metric` and `seed_metric_results` in `src/scoring.py` / `src/score_run.py`, `run_setup.seed` validation, and `data/multi_seed_settings.json` (the seed parameters of `paper_003` and `paper_006`, each with the place in the paper's code where it was read; `data/seed_papers.json` is not edited).
- Synthetic evidence (`scripts/synthetic_seeds.py`, real Docker, 5 seeds each, `data/synthetic_seeds/result.json`): the seed-free paper gave mean 0.9, standard deviation 0, Tier 3 = 100; the `random.Random(seed)` paper gave mean 0.7531, population standard deviation 0.1079, CV 14.333%, Tier 3 = 40. Both summaries equal the values computed on the host from the same seeds; Tier 3 differs between the two.
- Evidence: 29 new tests in `tests/test_multi_seed.py` (written first and seen failing); full suite 792 passed, 9 skipped; ruff clean.
- Not verified: the real papers (their seed runs follow); the host-side expected values use the same summary function as the runs, the hand calculation is in the unit tests.

### docs(scoring): design of multi-seed execution for Tier 3 (2026-10-20 03:01 +03:00, Issue #48)
- `docs/MULTI_SEED.md`: how Tier 3 gets real seed results. A paper's own seed parameter goes in an optional `run_setup.seed` object (`values`, `arg` or `args` with `{seed}`, and a required `source`); the runner makes one record per seed; the summary holds mean, standard deviation, and CV per metric; `src/scoring.py` takes `seed_metric_results` and scores the metric with the largest CV; the single-run baseline of 75.0 stays only when fewer than two seed runs succeeded.
- Evidence: documentation only; nothing is implemented in this PR. The implementation and its runs follow in separate PRs.
- Not verified: that `paper_003` and `paper_006` really take their seed as the design assumes (read from the staged code before the runs).

### docs(validation): run protocol for the external-validation articles (2026-10-18 21:00 +03:00, Issue #402)
- `docs/EXTERNAL_VALIDATION_PROTOCOL.md`: Pilot 4's protocol with `--memory 50% --cpus 4`, a 14400 s run phase, one attempt, no correction round and no retry, records in `data/external_validation/runs/`. It replaces the 8 CPUs of `docs/EXTERNAL_VALIDATION.md` section 5 before any run, and states that the runner only runs `python <script>` commands.
- Evidence: documentation only. No article is selected (#400, 0 of 65), so no run was made and #403 (run the articles) had nothing to run.
- Not verified: that the image or the staging step can run `make` or a notebook command.

### feat(corpus): external validation, E4 widened to python -m, make, and notebook commands; selection of at most 4 (2026-10-18 20:55 +03:00, Issue #400)
- `docs/EXTERNAL_VALIDATION.md` section 11 (marked "written after the results were seen"): E4 accepts `python -m <module>`, `make [target]` with a Makefile, and notebook runs; the selection count is 4; entries carry `expected_verdict` and `review_url`. `scripts/external_validation.py` implements it, and a dropped PDF download is tried again.
- Evidence: 41 tests in `tests/test_external_validation.py` (10 new, written first and seen failing). The selection run of 2026-10-18T17:48:50+00:00 evaluated 65 articles and selected **0**: E4 25, E2 23, E3 11, E1 5, E6 1 (`data/external_validation/evaluation.json`, previous result in `third_attempt/`).
- Not verified: how many articles would run with a command the README does not state; whether `python3` or `sh` forms should be admitted (the owner's decision, not made).

### feat(cli): `cli.py score --cpus` and `--timeout` (2026-10-18 02:40 +03:00, Issue #396)
- In the clean-clone test `cli.py score paper_006` was killed by the 3,600 s run limit during epoch 36. `score` now takes `--cpus N` and `--timeout SECONDS` (run phase only); `run_paper` records `cpus_override` and `timeout_override`, so such a run is not mistaken for a protocol run.
- Evidence: 3 new tests in `tests/test_pilot3.py` (override applied and recorded, nothing recorded without it, non-positive value refused).
- Not verified: a fresh `cli.py score paper_006 --cpus 8 --timeout 7200` run from a clean clone.

### fix(cli): init-db restores the accepted claims of the committed decisions (2026-10-18 02:10 +03:00, Issue #395)
- A fresh clone scored every paper with 0 accepted claims, because the claim review lives in a database that is not committed. `restore_decisions` (`src/claim_store.py`) re-applies the 13 `accepted` / `human` decisions of `data/claims/review_decisions.json` after `init-db` seeds the papers; anything else in the file is ignored, and a review made in this database is kept. This does not accept anything new: it restores decisions that the owner made (`review_note` says "restored from review_decisions.json").
- Evidence: 5 tests (`tests/test_restore_decisions.py`); in a new database `cli.py init-db` printed "Restored 13 claims" and `cli.py score paper_006 --from-run data/pilot3_runs/paper_006` used 2 accepted claims (Tier 2 0, Needs Review, 58.2). `pytest` and `ruff check .` below in the pull request.
- Not verified: a fresh run (not a stored run) scored against the restored claims from a clean clone.

### docs: clean-clone walk-through of the README and what it found (2026-10-18 01:30 +03:00, Issues #395, #396)
- A fresh clone of `main`, a new virtual environment, and the README steps in order (`docs/evidence/clean_clone/WALKTHROUGH.md`). Steps 2 to 4 and 6 worked; step 5 named a paper that does not exist (fixed in #394). `cli.py score paper_008` ends Failed after 38 s (its data is a manual download); `cli.py score paper_006` was killed by the 3,600 s run limit during epoch 36 (issue #396); both scored with 0 accepted claims because a fresh database holds none (issue #395). A stored run (`--from-run`) scored 85.75, Partially Verified, with Tier 2 as the neutral baseline.
- README: a warning before the scoring step states exactly this.
- Not verified: no paper completed a fresh run from a clean clone; the images were built from cache, not from scratch.

### docs(readme): the inspect example names a paper that exists (2026-10-18 00:05 +03:00, Issue #393)
- Found by following the README in a clean clone: step 5 inspected `paper_001`, which is not in the corpus (`paper_002` to `paper_008` are). The example now uses `paper_003`. Evidence: the walk-through log of the clean clone (outside the repository).

### docs(readme): accurate limits, options, requirements, and what a result means (2026-10-17 23:58 +03:00, Issue #391)
- README: the memory and CPU statement now says that `cli.py score` uses 50% of the host's RAM by default; the claim that a CI job runs the corpus check is replaced (there is no CI, D-010); the options of `cli.py score`, the preflight, and the existing-run-folder stop are described; new sections "Requirements" (RAM, disk, time, Docker, network, GPU) and "What a Result Means (and What It Does Not)". Every number is copied from a stored record or generated table (`docs/MEMORY_RUNS.md`, `docs/CPU_RUNS.md`, `docs/ENV_CACHE_RUNS.md`, `docs/STABILITY_RUNS.md`, `data/pilot4_runs/summary.md`).
- Evidence: `pytest` and `ruff check .` clean (see the pull request).
- Not verified: the RAM advice for light papers is an estimate; the README walk-through on a clean clone is still to do.

### fix(sandbox): say how to build the sandbox image (2026-10-17 23:45 +03:00, Issue #389)
- The mentor's clean-clone test of the README stopped at `cli.py score` with Docker's `pull access denied for repro-radar-sandbox`: the image is built locally and the quickstart never said so. README: new step 6 "Build the Sandbox Image" (later steps renumbered 7 to 9) with the build commands, including the compiler image and the Python 3.8/3.9 images. `scripts/preflight.py`: new `image` check that fails with the exact build command and skips the container check when the image is missing; 3 tests.
- Evidence: `pytest` 736 passed, 11 skipped; `ruff check .` clean.
- Not verified: the compiler-image and Python 3.8/3.9 build commands have not been run from the README; the clean-clone walk-through is the last step of the mentor's list and is still to do.

### Pilot 3 Results: Three Pilots Side by Side (2026-10-13 08:08 +03:00, Issue #293)
- pilot_compare.py --pilot3-dir and four report_numbers blocks (pilot3, pilot3measurements, pilot3summary, pilot3failures); docs/PILOT_3.md results and docs/report/REPORT.md section 6.1a, all numbers generated. Pilot 3: install 6/6, run 2/6, pilot success 2/6. The text says the four settings were chosen after Pilot 2's failures, so the rates measure the settings, not the papers.

### data(pilot3): Pilot 3 records (2026-10-13 08:04 +03:00, Issue #289)
- Six papers run once each in real Docker (2026-10-13). Install 6/6, run 2/6 (paper_003, paper_006), pilot success 2/6. paper_004 and paper_005 ended OOM_KILLED at the pre-set values (6 GiB, 12 GiB); paper_002 stopped at an OpenML network request. The first paper_002 attempt (killed by my own output-limit defect, #290) is kept in first_attempts.

### fix(sandbox): output limit counts growth, not the runner's copies (2026-10-13 02:00 +03:00, Issue #290)
- Found by the first Pilot 3 run: paper_002 was killed at start because deps, repository copy and data copies in the output directory were over the limit. The limit now applies to growth since the container started. Real Docker: 3 of 3 writers still killed.

### feat(corpus): Pilot 3 harness (2026-10-13 01:40 +03:00, Issue #287)
- run_pilot.py --pilot3 reads data/pilot3_settings.json (overlay, seed_papers.json not edited) and writes data/pilot3_runs/; SandboxConfig.run_timeout_seconds keeps build and install at 3600 s while paper_004's run phase gets 14400 s; tool labels. Real Docker: run timeout 6 s of a 3600 s config ended TIMEOUT at 6.1 s. No paper run yet.

### docs(corpus): Pilot 3 protocol (2026-10-13 01:33 +03:00, Issue #285)
- docs/PILOT_3.md: four per-paper settings (paper_003 writable data copy, paper_005 12 GiB memory, paper_004 4-hour run timeout, paper_002 lightgbm), all six papers re-run. States that these are settings chosen after the failures, not a better result about the papers. Pilot 1 and 2 stay as they are. Written before any run.

### feat(extraction): follow-up questions in the blind packet (2026-10-13 01:28 +03:00, Issue #283)
- make_blind_packet.py writes followup_queries into the packet and import_pass.py stores their answers as pass B in data/claims/followup/<paper_id>.json, apart from the gold set. No pass B was run and nothing is accepted. An older partly filled answers.json only gets empty slots. Real packet: 6 papers, 19 questions.

### fix(sandbox): watchdog killed by the paper is not a timeout (security audit F-3) (2026-10-13 01:24 +03:00, Issue #262)
- The entrypoint reports TIMEOUT only when the elapsed time reached the limit (within 1 s); an earlier exit 137 is FAILED with killed_before_timeout true in execution_meta.json. New acceptance check 21. Real Docker: acceptance 21 of 21, audit kill_parent PASS (41 PASS, 0 FAIL, 2 INFO). The paper can still kill its watchdog; only the label is fixed.

### fix(sandbox): output directory limit (security audit F-2) (2026-10-13 01:19 +03:00, Issue #261)
- The runner watches the size of the output directory every 0.5 s during the run container and kills the container above SandboxConfig.output_limit_mb (default 1024 MiB, 0 = off). New run status OUTPUT_LIMIT_EXCEEDED (schema CHECK, migration 6, badge, categorizer). Real Docker: a 4096 MiB writer was stopped in 9 of 9 runs, 18 to 122 MiB past the limit. Audit row output_disk now PASS. Not a hard bound.

### Report Section 3: Related Work Draft (2026-10-12 01:14 +03:00, Issue #270)
- Drafted section 3 from 9 sources looked up in Crossref and arXiv (scripts/verify_sources.py, 9 of 9 verified; abstracts only, no full text); claim-to-source table in docs/report/RELATED_WORK_SOURCES.md. PR left unmerged for the owner's review.

### Final Report: Results, Limitations, and Lessons (for the owner's review) (2026-10-10 22:09 +03:00, Issue #120)
- `docs/report/REPORT.md` sections 6 (Results), 7 (Limitations and threats to validity), and 8 (Lessons learned) are written from the Pilot 1 and Pilot 2 evidence and the claim-extraction files; every number is a block generated by `scripts/report_numbers.py`. Two statements that were no longer true (the Introduction's 'no paper has been run' and section 4.3's 'cli.py score is still simulated') were updated. Abstract, Related work, Conclusion, and References are not written. **Not merged: the owner reviews the sections first.**

### docs: CI is on again; README and CONTRIBUTING say what CI really runs (2026-10-13 00:53 +03:00, Issue #277)
- CI re-enabled by the owner (the Pilot workflow stays disabled). README no longer claims CI enforces the corpus check in the abstract; it names the corpus job. CONTRIBUTING no longer says CI is off.

### fix(ci): executable bit for 5 scripts with a shebang (2026-10-13 00:56 +03:00, Issue #279)
- The first CI run after re-enabling found ruff EXE001 on Linux for scripts/apply_accepted_claims.py, hash_run.py, migrate.py, report_numbers.py and security_audit.py (shebang, but mode 100644). Mode set to 100755 in git; no content change.

### Tests for the Small Tool Scripts (2026-10-12 01:21 +03:00, Issue #272)
- Added 9 tests: record_pilot2_environment.py 0% to 97%, extract_claims.py 0% to 96% (no API call), src/web/__main__.py 0% to 100%. Whole project src+scripts 81% to 87% after the four test PRs of #272.

### Tests for the Stager and the Staging CLI (2026-10-12 01:20 +03:00, Issue #272)
- Added 27 tests with fakes for git, pip and the runner: stager.py 77% to 100%, stage_and_bundle_repo.py 82% to 98% coverage. Tests only.

### Tests for the Database Module and Pilot Loader (2026-10-12 01:18 +03:00, Issue #272)
- Added 12 tests: src/database.py from 81% to 94% and scripts/load_pilot_runs.py from 78% to 97% coverage. Tests only.

### Tests for the Claim Scripts (2026-10-12 01:16 +03:00, Issue #272)
- Added 9 tests: apply_accepted_claims.py went from 0% to 97% coverage and import_pass.py from 66% to 97%. Tests only.

### Artifact Checksums and Reproducibility Summary (2026-10-12 01:09 +03:00, Issue #29)
- Added src/artifact_hash.py (manifest, verify, compare), scripts/hash_run.py, runs.artifact_manifest_sha256 and runs.outputs_sha256 (migration 5). Symbolic links and unreadable files are skipped and listed. The runner does not call it yet.

### runs Table Accepts OOM_KILLED (2026-10-12 01:07 +03:00, Issue #267)
- Schema CHECK on runs.status now includes OOM_KILLED, with migration 4 rebuilding the table and keeping its rows. Pilot 2 records are not loaded (no loader for that layout).

### Versioned Database Migrations (2026-10-12 01:04 +03:00, Issue #12)
- Added src/migrations.py (versioned, transactional, backed up, idempotent, table-rebuild helper) and scripts/migrate.py; init_db upgrades through it. Tested on temp databases and on a copy of the real local database; schema equals data/schema.sql.

### Contribution Guide and Paper Onboarding Specification (2026-10-12 00:59 +03:00, Issue #44)
- Added CONTRIBUTING.md and docs/PAPER_ONBOARDING.md (eligibility, entry template, steps, review criteria), checked against the scripts and tests; not rehearsed end to end.

### Sandbox Containers Drop All Capabilities (2026-10-12 00:56 +03:00, Issue #260)
- Added --cap-drop ALL to the run/install/build command, the bundling container and the compose file. Audit: CapBnd 0; 20/20 acceptance checks (3.11) and the GPU check still pass.

### Container Security Audit Against Real Docker (2026-10-12 00:53 +03:00, Issue #46)
- scripts/security_audit.py runs 43 hostile probes through the real sandbox runner (38 PASS, 3 FAIL, 2 INFO); evidence in data/security_audit/ and docs/SECURITY_AUDIT.md. Findings: missing --cap-drop ALL (#260), no output-directory quota (#261, needs a decision), watchdog can be killed by the paper (#262).

### paper_005 EP300 Speedup Question (Pass A Only) (2026-10-12 00:47 +03:00, Issue #258)
- Added followup question ep300_avg_kernel_speedup; pass A found 16 (Table 1, p. 10) and the quote guard matched it. Not accepted, seed file untouched, no pass B.

### README Claim Count and Corpus Verification Date (2026-10-12 00:44 +03:00, Issue #256)
- README now states the 12 accepted claims in 5 of 6 papers and points to Pilot 2 for runnability; CORPUS_VERIFICATION.md has the current date and marks the 2 of 16 count as the 2026-09-27 history.

### Removed the Unused validation_rubric Module (2026-10-12 00:43 +03:00, Issue #254)
- Deleted src/validation_rubric.py, docs/VALIDATION_RUBRIC.md and tests/test_validation_rubric.py (nothing imported them); the report now describes the tolerance rules scoring.py really applies. Coverage of src/ went from 2267 statements / 232 missed to 2076 / 201 (90% both).

### Python 3.11.4 Floor for fetch_data.py (2026-10-12 00:42 +03:00, Issue #252)
- Added requires-python >=3.11.4 and an early, clear stop in scripts/fetch_data.py when tar extraction filters are missing; the Pilot 2 environment record now includes python --version. Not verified on a real older Python.

### cli.py score Scores Real Runs and Accepted Claims (stage 3) (2026-10-10 22:07 +03:00, Issue #136)
- `python cli.py score <paper>` now runs the paper in the Docker sandbox with its run setup (the Pilot 2 flow of `scripts/run_pilot.py`) and scores the stored record and run report against the claims a person accepted; `--from-run <dir>` scores a stored run without Docker. No reproduced number is made up: a claim is matched by its question ID and is 'not found' otherwise, and a paper with no accepted claim gets the scorer's neutral Tier 2 baseline with an explicit note. The `--simulate*` flags are labeled `SIMULATION FOR TESTING` and never saved. End to end: a live `cli.py score paper_005` run (OOM_KILLED at the memory limit, scored) and the six stored Pilot 2 runs.

### Container Output Is Decoded as UTF-8 (2026-10-10 21:58 +03:00, Issue #248)
- `subprocess.run(text=True)` in the runner and stager decoded the output of `docker run` and `pip` with the Windows code page (cp1254), so a progress bar in a paper's output broke the capture (`UnicodeDecodeError` in the console logs of `paper_004` and `paper_005`; empty `stdout_preview` and `stderr_preview`). They now decode as UTF-8 with replacement. Status, exit codes, and the complete `stdout.log` and `stderr.log` of the Pilot 2 runs were not affected; the Limits of `docs/PILOT_2.md` say so.

### Pilot Comparison Stores Repository-relative Paths (2026-10-10 21:54 +03:00, Issue #246)
- `scripts/pilot_compare.py` wrote the absolute paths of its source files into `data/pilot2_runs/comparison.json`, so the committed file differed when regenerated in another checkout (and carried a local path). It now stores repository-relative POSIX paths; the file is regenerated and a test checks it.

### Pilot 2: Run, Evidence, and Report (2026-10-10 21:49 +03:00, Issue #171)
- Pilot 2 ran on the owner's machine in real Docker (Docker Desktop, WSL2) per `docs/PILOT_2.md`, GPU off. Records and the earlier attempts are in `data/pilot2_runs/`; the report is section 12 of `docs/PILOT_2.md`, with every number a generated block (`scripts/report_numbers.py`, checked by a test). Result: install success 6 / 6 (Pilot 1: 1 / 6), run success 1 / 6 (0 / 6), pilot success 1 / 6 (0 / 6; `paper_006`). The other five stopped at their own obstacles: an undeclared dependency (`paper_002`), a cache written into a read-only mount (`paper_003`), the time limit (`paper_004`), the memory limit (`paper_005`), and unpublished split files (`paper_008`). The earlier attempts were stopped by defects in Repro Radar (#211, #215, #217, #223, #225, #229, #231, #233, #243), each fixed in its own PR.

### Failure Categorizer Ignores Terminal Colors (2026-10-10 21:46 +03:00, Issue #243)
- `scripts/categorize_pilot_failures.py` strips ANSI color codes from log lines before classifying and quoting them. `paper_002`'s Jupyter traceback ends with a colored `ModuleNotFoundError` line, which was filed under `OTHER` instead of `MISSING_DEPENDENCY` (`docs/PILOT_2.md` section 7). Pilot 1's committed categories are unchanged.

### Report Block for the Pilot 2 Measurements Table (2026-10-10 21:03 +03:00, Issue #241)
- `scripts/report_numbers.py` gained `pilot2measurements`: the rates and the per-paper table (times, peak memory, statuses) copied from `data/pilot2_runs/measurements.md`; a hand edit makes `--check` fail.

### Report Number Blocks for the Pilot 2 Summary and Failures (2026-10-10 21:02 +03:00, Issue #239)
- `scripts/report_numbers.py` gained `pilot2summary` (one sentence with the three rates of Pilot 2 next to Pilot 1's) and `pilot2failures` (per paper: category, phase, and the deciding log line from `failure_categories.json`); a hand edit of either makes `--check` fail.

### Index of the Earlier Pilot 2 Attempts (2026-10-10 20:50 +03:00, Issue #237)
- `scripts/pilot2_attempts.py` writes `data/pilot2_runs/first_attempts/index.json` and `README.md` from the stored `pilot_record.json` and `run_report.json` of each earlier attempt (commit, stage, build, install, run, exit code), with the reason each was superseded taken from a hand-written `reasons.json` (an explanation and an issue number, not a result).

### Pilot Tools Name Their Own Directory and Tolerate a Missing Record (2026-10-10 18:33 +03:00, Issue #235)
- `pilot_measurements.py` writes the directory it read into the `measurements.md` header (Pilot 1's committed file keeps its text), and `categorize_pilot_failures.py` reports a paper without a record as `OTHER` / `NOT_RUN` instead of failing.

### Conda faiss Maps to faiss-cpu (2026-10-10 18:01 +03:00, Issue #233)
- Found by the Pilot 2 run of `paper_004` after its conda lock installed (1671 s): `import faiss` failed because the environment's CUDA build `faiss=1.7.2` was reported as conda-only. The CPU-only sandbox now gets PyPI `faiss-cpu` at the pinned version (`faiss-gpu` stays skipped). This is a substitution (CPU build for the CUDA build) and the report lists it.

### Writable Data Mounts Under the Sandbox Home Are Mounted Through Their Top-level Directory (2026-10-10 17:21 +03:00, Issue #231)
- Found by the Pilot 2 run of `paper_006` after its install finally succeeded: `import openml` failed with `PermissionError: '/workspace/home/.openml/config'`. Docker created the missing parent `.openml` of the cache mount as root inside the home tmpfs, so the sandbox user could not create openml's config beside the cache. A writable data copy whose target is under `/workspace/home` is now placed at its nested path in a per-run directory that is mounted at `/workspace/home/<top>` (the paper's setting is unchanged). Acceptance check 19 also creates a file next to the data; 20/20 checks pass on the Python 3.11 image on this machine.

### A Conda Lock Is Installed as Pinned, Not Resolved (2026-10-10 16:43 +03:00, Issue #229)
- Correction of #227/#228: the resolver pass over the conda pins was a wrong diagnosis. Re-running `paper_006` showed `ResolutionImpossible` (conda's `mkl-random` has different dependency metadata than the same-named PyPI package) and, after removing it, the next gap (`promise`, source-only, needed by `wandb`). A conda environment file is a lock that pins every transitive dependency, so the install phase of a conda-only repository now runs `pip install --no-deps` over exactly the bundled pins; a pin without a wheel is simply absent. The `_fill_dependency_gaps` pass is removed; the `python-graphviz` mapping stays. Acceptance check 13 now pins `requests` without its dependencies; 20/20 checks pass on the Python 3.11 image on this machine.

### Conda-only Bundles Get the Dependencies the Environment Did Not Provide (2026-10-10 16:33 +03:00, Issue #227)
- Found by the Pilot 2 runs of the two conda-only papers: `paper_006` failed to install because `jsonschema` needs `pyrsistent` and the environment's `pyrsistent==0.17.3` has no wheel (first attempts kept in `data/pilot2_runs/first_attempts/`); `paper_004` because `catboost` needs the PyPI `graphviz` package, which conda calls `python-graphviz`. After the per-pin downloads, one resolver pass over the exact pins (binary wheels only) now adds the missing dependencies and lists them as `gap_fill` in the bundle report; `python-graphviz` maps to `graphviz` and conda's own `graphviz` (a C tool) is skipped.

### Conda Conversion Keeps setuptools, wheel, and certifi (2026-10-10 15:24 +03:00, Issue #225)
- Found by the Pilot 2 run of `paper_006` (first attempt kept in `data/pilot2_runs/first_attempts/paper_006_attempt1/`): `openml` and `liac-arff` were built in the sandbox, but the offline install failed with `Could not find a version that satisfies the requirement setuptools>=18.5 (from ipython)`. `src/sandbox/conda_env.py` skipped `setuptools`, `wheel`, and `certifi`, which other packages require. They are now converted when the environment pins them; `python`, `pip`, and system libraries are still skipped.

### Pilot 2 Driver Passes the Extra Requirements to the Install Phase (2026-10-10 15:17 +03:00, Issue #223)
- Found by the Pilot 2 run of `paper_005` (first attempt kept in `data/pilot2_runs/first_attempts/paper_005_attempt1/`): the `fastsk` wheel was built in the sandbox and bundled, but never installed, so the run stopped with `ModuleNotFoundError: No module named 'fastsk'`. `run_paper(pilot2=True)` gave `extra_requirements` to the bundling step but not to `SandboxConfig`. It does now (also `paper_002`'s `nbconvert` and `ipykernel`).

### Report Numbers from a Script (2026-10-10 15:12 +03:00, Issue #221)
- `scripts/report_numbers.py` renders the numbers of the final report from the stored files (blocks `pilot1`, `pilot2`, `extraction`); `--write` fills the `<!-- numbers:NAME:start/end -->` blocks of `docs/report/REPORT.md`, `--check` fails if one was edited by hand, and a test runs the check (AGENTS.md §6.5).
### Pilot 2 Measurement Tools (2026-10-10 15:00 +03:00, Issue #219)
- `scripts/categorize_pilot_failures.py` follows the Pilot 2 order build, install, run: a failed build is `MISSING_DEPENDENCY` in phase `build` with the deciding line from `build.log`; a missing run report is `NO_RUN_REPORT`. `scripts/pilot_measurements.py` adds `build_status` only to records that have a build, so Pilot 1's stored files are unchanged. New `scripts/pilot_compare.py` writes `data/pilot2_runs/comparison.{json,md}` with Pilot 1 and Pilot 2 side by side from their stored measurements.

### Re-staging on Windows and Stale Files in Pilot 2 Records (2026-10-10 14:53 +03:00, Issue #217)
- Found when the Pilot 2 run of `paper_008` was started a second time: (1) `stage_repository` could not delete the old clone on Windows (`WinError 5`, git's read-only pack files); `remove_tree` clears the read-only bit and retries, and every directory the stager clears now uses it. (2) A failed Pilot 2 record listed `collected_files` copied from an older run. In `--pilot2` mode `sandbox_runs/<paper_id>` and `<paper_id>.build` are now cleared before the run, and the driver refuses to start if `data/pilot2_runs/<paper_id>/` already holds an earlier attempt (it is evidence; move it to `data/pilot2_runs/first_attempts/`).

### Bundling Inside the Sandbox Image (found by the first Pilot 2 attempt) (2026-10-10 14:49 +03:00, Issue #215)
- First Pilot 2 attempt on the owner's Windows machine (`paper_008`, kept in `data/pilot2_runs/first_attempts/paper_008_attempt1/`): the install phase failed with `Could not find a version that satisfies the requirement cuda-toolkit==13.0.3; platform_system == "Linux"`. Host-side `pip download` evaluated environment markers for Windows and the host's Python, not the sandbox's. With `RepoStager(bundle_in_docker=True)` (used by `run_pilot.py --pilot2`) the download runs inside the paper's sandbox image (binary wheels only), and the bundle for `paper_008` went from 34 to 52 wheels, now including `cuda_toolkit-13.0.3.0`. Pilot 1's mode and the host path are unchanged. `.sandbox_staging/` is git-ignored.

### Pilot 2 Environment and the Real GPU Check (2026-10-10 14:30 +03:00, Issues #213 and #169)
- `scripts/record_pilot2_environment.py` wrote `data/pilot2_runs/environment.txt` from command output (commit, `docker version` and `info`, `nvidia-smi`, `gpu_check.py`, images, disk). On this machine `gpu_check.py` showed the RTX 5070 (driver 591.86) inside the sandbox container with uid 1000, the network blocked, and a read-only root: `GPU visible with isolation intact: YES`. `data/pilot2_runs/` is no longer git-ignored, so the Pilot 2 evidence can be committed.

### Entrypoint Kept in LF; First Real-Docker Run on Windows (2026-10-10 14:29 +03:00, Issue #211)
- On the owner's Windows machine (`core.autocrlf=true`) the container entrypoint was CRLF and every container failed with `env: 'bash
': No such file or directory` (19 of 20 acceptance checks failed). `.gitattributes` now keeps `*.sh` and `docker/Dockerfile*` in LF, and a test fails on CRLF. After rebuilding the six images, the acceptance checks pass on this machine: 20/20 on Python 3.11, 3.9, and 3.8. GitHub Actions is disabled by the owner, so these local runs are the evidence.

### Report Sections Written: Introduction, Method, Experimental Setup (2026-10-07 19:47 +03:00, Issue #120)
- `docs/report/REPORT.md` sections 2, 4, and 5 are written from evidence already in the repository: the
  sourced introduction draft (#118/#119), the sandbox threat model and four-tier score (`docs/SANDBOX_ACCEPTANCE.md`,
  `src/config.py`, `src/scoring.py`, `src/validation_rubric.py`), the claim extraction pipeline (W1-W7, gold-set
  precision/recall 1.0/1.0), and the corpus's 18→8→6 history with its automated verification (6/6 pass).
- Corrected section 6 (Results)'s own needs list: the gold set (#133) is filled now, so Results is blocked on
  Pilot 2 alone, not three things.
- Not written: Related work (needs a separately verified external source list) and anything needing Pilot 2
  data (Results, Limitations, Lessons learned, Conclusion).

### Stale Umbrella Issue #9 Closed (2026-10-07 19:39 +03:00, Issue #9, housekeeping)
- All 8 checklist items (#129 W1, #130 W2, #131 W3, #132 W4, #133 W5, #10 W6, #134 W7, #135 closing step) were
  already closed; the Definition of Done (claims extracted and quote-verified, gold-set precision/recall,
  EP3602/HIGGS regression cases returning "not found") is satisfied. Closed as done, no code change. This also
  clears one of the two issues #136 names as a precondition (the other, #43, was already closed).

### Pilot 2 Output Location Fixed (2026-10-07 19:31 +03:00, Issue #207)
- `--pilot2` now writes `pilot_record.json` into `data/pilot2_runs/<paper_id>/`, as `docs/PILOT_2.md` section 6
  asks, instead of `sandbox_runs/<paper_id>/` (where PR #206 left it — that gap was not named in #205 or #206).
  `scripts/run_pilot.py`'s new `_collect_pilot2_files` copies the protocol's other named files (`run_report.json`,
  `execution_meta.json`, `install.log`, `install_meta.json`, `build.log`, `stdout.log`, `stderr.log`) from their
  sandbox locations into the same directory, skipping any that do not exist yet. `src/sandbox/runner.py` and
  `stager.py` are untouched: they still write under `sandbox_runs/`, shared with Pilot 1 and real-Docker CI.
- Pilot 1's output location and mode are unchanged.
- Tests: 2 new (full completion copies exactly the files the protocol names, plus a staging failure); the 3
  existing Pilot 2 tests updated to assert the new location; all 18 Pilot 1 tests untouched. Full suite:
  319 passed, 6 skipped; `ruff check` clean.
- `data/pilot2_runs/` added to `.gitignore` (next to `sandbox_runs/`): run output, not something to commit.
- **Not verified:** no real Docker run (no Docker on this machine yet, #172). While testing, an intermediate
  (uncommitted) run of the old test file wrote real files into `data/pilot2_runs/`; found via `git status`
  (untracked) and deleted before committing.

### Pilot 2 Driver (no run) (2026-10-05 22:36 +03:00, Issue #205, plan step 2.9)
- `python scripts/run_pilot.py <paper_id> --pilot2` runs a paper with its `run_setup` (build phase, extras and constraints, working directory, writable copy, data mounts, command); Pilot 1's mode is unchanged. A missing data cache is a harness error naming `scripts/fetch_data.py`; a failed build ends the paper before install and is recorded. Fake-stager tests only: no paper was run.

### Seed Claim Values Replaced by Accepted Claims (2026-10-05 22:12 +03:00, Issue #135, plan step 1.8)
- The owner accepted all 12 extracted claims one by one (`data/claims/review_decisions.json`). `scripts/apply_accepted_claims.py` wrote them into `expected_claims` of `data/seed_papers.json` (old values kept under `seed_claims_before_extraction`; `check` fails on disagreement). `paper_005` has no accepted claim (all its questions were answered "not in the paper") and stays in the corpus. `docs/CORPUS_VERIFICATION.md` section 6 replaces the UNVERIFIED/SUSPECT status. Three tests were adjusted to accepted-only claims.

### Gold Set and Extraction Precision/Recall (W5) (2026-10-05 21:02 +03:00, Issue #133, plan step 1.5)
- The owner filled the gold set form question by question (18 questions, 6 papers): `tests/data/gold_claims/paper_*.json` (`made_by: owner`, written by `scripts/evaluate_gold.py from-form`, no `needs_decision`). Pass A scored by `scripts/evaluate_gold.py score --pass A` (`data/claims/gold_score_pass_A.json`): TP 12, FP 0, FN 0, TN 6, precision 1.0, recall 1.0; the regression cases EP3602 (AUROC, accuracy) and HIGGS are all TN. Caveat: the form's candidate values were listed by the same agent that extracted pass A, so a value it never found could only enter through "other"; pass B is not independent yet.

### Final Report Skeleton (2026-10-05 18:22 +03:00, Issue #120, step R2)
- `docs/report/REPORT.md`: the 10 sections of #120, each with its one-line purpose, what it needs, and its status. No section body is written; sections are written only when their evidence exists.

### Pilot 2 Protocol (no run) (2026-10-05 18:17 +03:00, Issue #171, plan step 2.9)
- `docs/PILOT_2.md`: Pilot 1's definitions, limits, and failure categories unchanged; runs on the owner's machine (Docker Desktop, WSL2) with each paper's `run_setup`; counted run CPU-only; build phase added to the failure order; Pilot 1's 0 / 6 shown alongside. Written before any Pilot 2 run. STOP before the first run: the owner confirms Docker (#172) and approves the protocol; `paper_002`'s network question (#193) is open.

### Opt-in Local GPU (code only) (2026-10-05 18:09 +03:00, Issue #169, plan step 2.6)
- `SandboxConfig.gpus` (`all`, a count, or `device=<ids>`; validated) adds `docker run --gpus` and nothing else; the default stays without a GPU, and the local fallback refuses a GPU run. The entrypoint records the visible GPUs and samples GPU memory during the run; `run_report.json` gets a `gpu` summary (available, used). `scripts/gpu_check.py` shows the GPU inside the sandbox with the isolation checks; acceptance check 20 shows the GPU is off by default. **Not verified:** no real GPU run (this machine has no Docker; GitHub's runners have no GPU).

### Gold Set Form Reader and Precision/Recall (W5) (2026-10-05 18:05 +03:00, Issue #133, plan step 1.5)
- `scripts/evaluate_gold.py from-form` reads the owner's filled gold set form by its structure (checkboxes, backtick values, the free "other" answer, "not in the paper") into `tests/data/gold_claims/<paper_id>.json`, reporting unclear answers as `needs_decision`; `score` gives TP/FP/FN/TN, precision, recall, and the EP3602/HIGGS regression cases. On the real form it found all 18 questions, none filled yet. No gold value was chosen and no precision/recall number exists yet.

### Human Review of Extracted Claims (W7) (2026-10-05 17:50 +03:00, Issue #134, plan step 1.7)
- `python cli.py review-claims [paper_id]` shows each pending claim with its provenance and asks accept / reject / skip / quit (optional note); each decision is committed at once with `verified_by = human`. `--list` shows the review status without asking. `claims_for_scoring` (`src/claim_review.py`) returns only accepted claims. No claim has been accepted or rejected; that is the owner's step.

### Extracted Claims Stored with Provenance (W6) (2026-10-05 17:49 +03:00, Issue #10, plan step 1.6)
- New table `extracted_claims` (`data/schema.sql`, `ExtractedClaimORM`): page, table or section, quote, source file, PDF hash, extractor version, `verified_by` (`auto-quote-match` = quote guard matched, not an approval; `human` = a person decided), and the review status. The database refuses a non-pending claim without `verified_by = 'human'`. `src/claim_store.py` saves, updates, queries (by paper, review status, and run), and records reviews; `accepted_claims` is what may reach the scorer. `scripts/import_claims.py` imports pass A as 12 `pending` claims. No claim has been accepted.

### Build Phase and the Open Run-Setup Items (#193) (2026-10-05 17:41 +03:00, Issue #193)
- Finding: `openml` (0.11.0 and 0.12.2) and `liac-arff` exist on PyPI only as sdists, so `paper_002` and `paper_006` could not install with the binary-only install phase. New isolated **build phase** (D-008): sdists downloaded from the PyPI JSON API with a SHA-256 check (never run on the host), built into wheels in the build image (`docker build --target build`) with the network off; the install phase stays binary-only. Run setups gained `build`, `extra_requirements`, `constraints`, and writable data copies; OpenML datasets are fetched over HTTP (MD5-checked). `paper_005`: Python 3.8, `fastsk` built from the repository, unpinned packages limited to their newest release before the pinned commit's date (resolves for Python 3.8, pip dry run). `paper_006`: offline load of dataset 1461 by openml 0.11.0 shown on the host with sockets blocked. Real-Docker acceptance checks 18 (build phase) and 19 (writable data copy). Still open: `paper_002` lists its datasets through the OpenML API at run time, which needs network (owner decision). Not verified: no paper run (Pilot 2, #171).

### Docker Detection Tolerates Slow Runners (2026-10-05 17:15 +03:00, Issue #164, plan step 2.8)
- `DockerSandboxRunner.is_docker_available` asks `docker info` up to 3 times (15 s each, 2 s apart) instead of once for 5 s; worst case 49 s for a daemon that never answers. A missing Docker CLI still fails at once, and a daemon that stays unavailable is still refused (`tests/test_docker_detection.py`; real-Docker check 6 unchanged).

### Image Size and CPU Limit Measured (2026-10-04 21:58 +03:00, Issue #163, plan step 2.7)
- Real-Docker acceptance checks 16 and 17 (CI run 37224145290). Image sizes: 477.1 MiB (Python 3.11), 451.2 MiB (3.9), 417.1 MiB (3.8). Under `--cpus=0.5`, two busy workers got 0.49 CPUs together; the control at the runner's 2 CPUs got 1.97. `docs/SANDBOX_ACCEPTANCE.md` regenerated from that run (it now also lists check 15 from #166).

### Paper Run Setups: Fix, Do Not Replace (2026-10-04 21:15 +03:00, Issue #166, plan step 2.5)
- Owner decision: no paper is replaced. `paper_002`–`paper_006` get a `run_setup` in `data/seed_papers.json`; `paper_008` is kept and reported as `DATA_NOT_ACCESSIBLE` (its split files are not published). The decisions and what is still open are in `docs/CORPUS_VERIFICATION.md` section 5. The sandbox gained a repository-relative working directory, a writable per-run copy of the repository, read-only data mounts from a host cache (`scripts/fetch_data.py`), and a command that replaces the target script (real-Docker acceptance check 15). Not verified: no paper has been run with its run setup (Pilot 2, #171). Open: `paper_002` (nbconvert, OpenML-CC18 list), `paper_005` (C++ build, dateutil conflict), and `paper_006` (offline OpenML cache).

### Installed Versions Recorded (2026-10-04 19:08 +03:00, Issue #161, plan step 2.4)
- The install phase writes `installed_packages.json` (`pip list --path /workspace/deps`). `run_report.json` gets `installed_packages` and `requested_vs_installed`: per requirement (or converted conda pin), the requested specifier, the installed version, whether it satisfies the request, and whether it was pinned. This makes drift like `paper_008`'s `torch>=1.4.0` → `2.7.1` visible. `packaging` is now a runtime dependency. Real-Docker acceptance check 14.

### Dependency Conflicts Named in the Reports (2026-10-04 19:04 +03:00, Issue #160, plan step 2.3)
- `src/sandbox/dependency_conflicts.py` parses pip's "Cannot install ... conflicting dependencies" blocks and their "caused by" lines; `-r <file> (line N)` is replaced by that line's text from the staged repository. The bundle report (from the full pip output; pip prints the cause lines to stdout) and `run_report.json` (from `install.log`) now carry `dependency_conflicts`. On Pilot 1's real `paper_005` log: `pandas 3.0.6 depends on python-dateutil>=2.8.2` vs. the pinned `python-dateutil==2.8.1`.

### Conda-Only Repositories Bundled Offline (2026-10-04 18:53 +03:00, Issue #159, plan step 2.2)
- `src/sandbox/conda_env.py` converts a conda environment file into pinned pip requirements (conda-to-pip name map; system, CUDA, and `_`-internal packages skipped with reasons; the file's Python version read). Conda itself is not run. A conda-only repository is bundled one requirement at a time with `pip download --no-deps` (binary only); packages without a wheel are reported as `conda_only`. Real files: `paper_004` → Python 3.9, 300 requirements (114 skipped); `paper_006` → Python 3.8, 156 requirements (37 skipped).
- Python 3.9 image added (`paper_004`); `paper_004` → 3.9 and `paper_006` → 3.8 in `data/seed_papers.json`. `pyyaml` is now a runtime dependency. New real-Docker acceptance check 13 (conda-only repository: bundle, offline install, import). Re-running `paper_004`/`paper_006` is left for Pilot 2 (#171).

### Python Version per Paper (2026-10-04 18:48 +03:00, Issue #158, plan step 2.1)
- `docker/Dockerfile.sandbox` takes `--build-arg PYTHON_VERSION` (3.11 and 3.8). `SandboxConfig.python_version` selects the image (`repro-radar-sandbox:latest` for 3.11, `repro-radar-sandbox:py3.8`) and the site-packages path; bundling downloads wheels for that version; `run_report.json` records `python_version` and `image`.
- `data/seed_papers.json`: `paper_002` and `paper_003` run on Python 3.8 (`python_version` with its source); the others stay on 3.11 (`paper_004`/`paper_006` are conda-only, #159). The pilot runner follows the field.
- CI runs the real-Docker acceptance checks for both images. Re-running `paper_002`/`paper_003` in real Docker is left for Pilot 2 (#171): no local Docker yet (#172).

### Blind Packet for an Independent Pass B (2026-10-04 18:41 +03:00, Issue #186)
- `scripts/make_blind_packet.py` writes a self-contained folder outside the repository (questions, rules, a schema description without real values, the pinned PDFs' page text, an answer template, and a README with the prompt) for a new session that cannot see pass A. `scripts/import_pass.py` checks the filled answers (schema, quote on the cited page) and stores them as pass B. A packet was generated at `C:\Users\USER\blind_pass_b` (6 papers, 18 questions); a leak check found none of the 12 stored answer values outside the paper texts.

### Owner Decisions Applied to the Extractions (2026-10-04 18:35 +03:00, Issue #184)
- TabPFN time split into GPU (`0.6172`) and CPU (`37.59`) claims; DANet Forest split into DANet-20 (`97.23%`) and DANet-32 (`97.27%`); TabR's rank moved to Table 4 (`1.3± 0.9`), the table that also ranks XGBoost (`2.5± 0.9`); XGBoost RMSE `0.433` accepted by the owner. 18 questions now; both passes revised; 18/18 agree; 24/24 found claims `AUTO_QUOTE_MATCH`. Decisions recorded in `data/claims/owner_decisions.json` and as rule 9 of `docs/AGENT_EXTRACTION.md`.

### Quote Guard Run on the Extractions (2026-10-04 15:32 +03:00, Issue #182, plan step 1.4)
- `scripts/check_claims.py` runs the W4 guard (with the #162 repair) on every found claim of passes A and B against the pinned PDFs and writes `data/claims/guard_report.json`/`.md`. Result: 18 of 18 found claims `AUTO_QUOTE_MATCH` (all `exact`), 0 `UNVERIFIED`; all 18 come from tables, so all go to the owner in W7. A pass shows the quote is on the page, not that the value answers the question.

### Split Numbers Repaired, Table Claims Flagged (2026-10-04 15:29 +03:00, Issue #162, plan step 1.3)
- `src/pdf_text.py`: `repair_split_numbers()` joins numbers pypdf split before the decimal point (`0 .850` → `0.850`); 1,213 occurrences in the seed PDFs (`paper_003` 226, `paper_004` 986, `paper_006` 1). The quote guard compares after the repair on both sides (match mode `split_numbers_repaired`), so a correctly retyped value is no longer rejected.
- Table claims are flagged (`from_table`) and always go to the owner in W7; table structure is not reconstructed. Documented in `docs/PDF_TEXT_EXTRACTION.md` and `docs/CLAIM_SCHEMA.md`.

### Extraction Passes Compared (2026-10-04 15:25 +03:00, Issue #179, plan step 1.2)
- `scripts/compare_extractions.py` compares passes A and B by normalized value (D-005) and writes `data/claims/consistency.json`/`.md`. Result: 16 of 16 questions agree, 0 disagreements. Because pass B is not independent of A (#178), this agreement is expected and weak evidence; correctness is decided in steps 1.4, 1.5, and 1.7.

### Agent-Assisted Claim Extraction, Two Passes (2026-10-04 15:22 +03:00, Issue #131, plan step 1.1)
- 16 questions (one per seed claim, written without the seed values) in `data/claim_queries/` for all 6 papers; pinned PDFs (arXiv `2207.01848v6`, `2106.11959v5`, `2307.14338v2`, `2106.01342v1`, `2112.02962v4`; bioRxiv `2020.04.21.053975v2`).
- `docs/AGENT_EXTRACTION.md`: the rules (same as the API prompt, plus a rule for values printed in several places) and how independent the two passes are.
- `data/claims/<paper_id>.json`: passes A and B. Both: 9 found, 7 not found (EP3602 x2, Figure 4 speedup, FT-Transformer rank in TabR, Bank accuracy in SAINT, DANet Forest row ambiguous, HIGGS). **Pass B is not independent:** same agent, same session (owner's instruction, no subagent); its re-search confirmed every A answer, so its values were taken over from A. Not approved: the quote guard (W4) and the owner (W5, W7) decide.

### D0 Dashboard Skeleton (2026-10-04 13:00 +03:00, Issue #170, plan stage 0b)
- `src/web/app.py`: FastAPI app with `GET /api/v1/papers` (a real SQLAlchemy query: catalog fields plus each paper's latest run; an empty database gives `[]`) and a server-rendered page in the owner's chosen design (option A: light, plain table, system font). Seed claim values are never exposed (unverified). `python -m src.web` serves it on `127.0.0.1` only (D-006).
- The owner chose option A out of three previews on 2026-10-04 (`AGENTS.md` §6.9). Screenshots of an empty, a one-row, and the local database are in `docs/evidence/d0/`.
- The local database was rebuilt from the current `data/seed_papers.json` (`cli.py init-db --reset`, then `scripts/load_pilot_runs.py`): 6 papers and their 6 pilot runs; the removed `paper_001` and `paper_007` are gone. The database file is not tracked.
- `fastapi`, `uvicorn` (runtime) and `httpx` (tests) added. 6 tests in `tests/test_web_app.py`.

### Agents Point at the 2026-10-01 Plan (2026-10-03 20:55 +03:00, Issue #175)
- `AGENTS.md` (living docs list, traceability line, §6.1 and §6.3) and `CLAUDE.md` now point at `docs/PLAN_2026-10-01.md` as the current work order; §6.3 states the plan's stage order. The status summary above, the milestone counts, and the `docs/DECISIONS.md` header were refreshed.
- On the owner's decision: the unmerged gold-set branch `test/issue-133-gold-set` (`7b3dcbc`) was closed without merging; the merged old branches `chore/devops/adopt-projectflow` (PR #1) and `feature/issue-0-translate-to-english` (PR #56) were deleted; #131 was reopened for plan steps 1.1-1.2.

### 2026-10-01 Plan Decisions Recorded (2026-10-02 12:22 +03:00, Issue #168, plan item 0.2)
- `docs/DECISIONS.md` D-004 to D-007: agent-assisted extraction without an API key (the API code stays); "temperature 0" replaced by the rule that two independent extractions must agree on the normalized numbers, with every mismatch going to the owner in W7; everything runs locally (dashboard on `localhost`, paper runs on the owner's machine, GitHub Actions only for CI); papers that cannot run may be replaced, with a recorded reason and Pilot 1's 0 / 6 kept. D-003 is marked as partly superseded.

### 2026-10-01 Plan Recorded (2026-10-02 12:18 +03:00, Issue #167, plan item 0.1)
- `docs/PLAN_2026-10-01.md`: complete English translation of the 2026-10-01 work plan (decisions, owner tasks Y1-Y5, stages 0-5, the work loop, the summary order), with the issue number next to every item. `docs/ROADMAP_2026-09-27.md` now starts with a link to it; nothing else there changed.
- New issues opened for the items without a number: #167 (0.1), #168 (0.2), #169 (0.3, local GPU), #170 (D0 dashboard skeleton), #171 (Pilot 2), #172 (Y1, owner installs Docker).

### Verbatim Quote Guard (2026-10-01 21:04 +03:00, Issue #132, W4)
- `src/quote_guard.py`: a claim becomes `AUTO_QUOTE_MATCH` only if its PDF hash matches, its page exists, its quote and printed value occur on that page with identical characters (whitespace runs count as one space), and its dataset and model occur in the paper as whole words. Otherwise it stays `UNVERIFIED` with the reasons. `scorable_claims()` returns only verified claims.
- Rules documented in `docs/CLAIM_SCHEMA.md` section 5; 11 tests, including a matching and a non-matching quote, the `0.859`/`0 .859` case, and the invented `EP3602` dataset.

### Claim Extraction with Claude (2026-10-01 20:57 +03:00, Issue #131, W3)
- `src/claim_extraction.py`: query-driven extraction with Claude Opus 5.5 (owner's choice), JSON-schema output, a mandatory verbatim quote and PDF page, and an explicit "not found" instead of guessing. `value_normalized` is computed by the schema rule. Responses are cached by a hash of model, prompt, schema, PDF, and queries (`data/llm_cache/`, not committed). Usage and estimated cost are recorded, and a server-side refusal fallback is enabled and recorded.
- `docs/DECISIONS.md` D-003: why there is no temperature setting (Opus 5.5 rejects it) and what gives repeatability instead (cache, W4 quote guard, W7 human check).
- `scripts/extract_claims.py` with `data/claim_queries/paper_003.json` (pinned PDF `2106.11959v5`; queries without the seed values). `anthropic` is a runtime dependency. Tests use a fake client; no API call was made yet, because `ANTHROPIC_API_KEY` was not visible to the session.

### Lint Backlog Cleared (2026-10-01 20:39 +03:00, Issue #139, GA-11)
- The CI lint gate is now ruff's default rule set plus the first gate's rules (`pyproject.toml`). Findings went from 393 (ruff 0.16.9 defaults) to 0. `ruff --fix` applied 375 fixes; the remaining 38 were handled by hand: 12 explicit `check=False`, 10 renamed unused test variables, 7 small simplifications, and 9 deliberate broad exception handlers marked `# noqa: BLE001` with their reason.
- Behavior unchanged: 164 passed, 8 skipped before and after. The untested `cli.py` and scripts compile and run `--help` (and `cli.py list-papers`).
- Started ahead of the binding order (`AGENTS.md` §6.3) at the owner's explicit request.

### Coverage Re-measured (2026-10-01 20:32 +03:00, Issue #138)
- Line coverage on the GA-5 baseline scope (`src`, `cli.py`, `scripts`) is 79% (2598 statements, 557 missed), up from 60%; `src/` alone is 87% (1379 statements, 180 missed), locally and in CI. `cli.py` is still 0%. Recorded in `docs/gap_analysis.md` (section 2 and GA-5).
- Started ahead of the binding order (`AGENTS.md` §6.3) at the owner's explicit request.

### Generated Introduction No Longer Committed (2026-10-01 20:28 +03:00, Issue #137, GA-15)
- `docs/repro_radar_introduction.docx` and `docs/assets/repro_radar_banner.png` are build outputs of `scripts/generate_academic_introduction_doc.py`: removed from version control and ignored. The script has an `--output-dir` option.
- `tests/test_academic_doc.py` generates the document into a temporary directory on every run, and the CI test job uploads the generated `.docx` as the `introduction-docx` artifact.
- Started ahead of the binding order (`AGENTS.md` §6.3: section 6 comes last) at the owner's explicit request.

### PDF Text Extractor (2026-10-01 19:18 +03:00, Issue #130, W2)
- `src/pdf_text.py`: page-by-page text with 1-based PDF page numbers (`pypdf`, now in `requirements.txt`), cached as `data/pdf_text_cache/<sha256>.json` keyed by the PDF bytes (not committed). `PdfText.find()` lists the pages that contain a string verbatim.
- Real paper check (`paper_003`, arXiv 2106.11959v5, 25 pages): `FT-T 0.459` is on PDF page 7, as recorded in `docs/CORPUS_VERIFICATION.md`. First extraction 0.56 s, cached 0.010 s.
- `docs/PDF_TEXT_EXTRACTION.md` documents the limitations, with that page as the example: table rows become single lines without column structure, `pypdf` inserts spaces inside numbers (`0 .850`), formatting is lost, scanned pages have no text, and figures are not read.

### Claim Schema (2026-10-01 19:06 +03:00, Issue #129, W1)
- `docs/CLAIM_SCHEMA.md`: the twelve fields of an extracted claim with type and meaning, the normalization rule (`96.99 %` → `0.9699`, computed in decimal), the claim set per exact PDF (`pdf_sha256`), explicit "not found" answers (regression cases EP3602 and HIGGS), and what W4/W6 add later.
- `src/claim_schema.py`: the same schema as Pydantic models (`ExtractedClaim`, `ClaimSet`, `NotFound`) and `normalize_value()`. A claim is rejected if its normalized value does not follow the rule or its quote does not contain the printed value.
- `tests/test_claim_schema.py`: the documented fields, units, splits, and examples equal the code; invalid values and claims are rejected.

### UI Decision Rule (2026-10-01 18:53 +03:00, Issue #149)
- `AGENTS.md` §6.9: UI decisions (layout, colors, fonts, leaderboard, filters, detail page, badge design, report layout) are asked to the owner with 2-3 options and a preview before they are implemented.

### Pilot Cleanup (2026-09-30 21:54 +03:00, Issue #128, P7; closes the pilot umbrella #43)
- Evidence review of #48 and #13-#18 against the 12 acceptance checks and the pilot runs; each issue has a comment with its status. Only #16 gained a tick: the timeout watchdog, backed by `test_process_sandbox_runner_timeout`. Its "automatic driver detection" box is annotated as replaced by design in #80.
- Still open, with the missing evidence named: #48 (multi-seed execution not implemented), #13 (image size not recorded), #14 (logs reach SQLite only after the run, via the loader), #15 (blocked network attempts are not logged), #17 (no kill at the 600 s default, no stored `TIMEOUT` row), #18 (no automated test for a failing exit code).
- Status and milestone counts at the top of this file refreshed from GitHub.

### Pilot Report (2026-09-30 21:50 +03:00, Issue #127, P6)
- `docs/PILOT_WEEK2.md` section 11: pilot success 0 / 6, install success 1 / 6, run success 0 / 6, all 6 runs valid. Most frequent category `MISSING_DEPENDENCY` (5 of 6), with three causes: old pins without Python 3.11 wheels, a conflict inside the requirements, and conda-only repositories. What was surprising, proposed sandbox changes (Python version per paper first), and limits (n = 6 is anecdotal).
- The tables are pasted from the generated files, and `tests/test_pilot_report.py` fails if they drift. The document's status note was updated; the frozen protocol text is unchanged.

### Pilot Dataset Findings (2026-09-30 21:47 +03:00, Issue #126, P5)
- `docs/PILOT_WEEK2.md` section 10: for each paper, whether it downloads data, what, how large, under which license, and what happened in the pilot, each with its source. Largest downloads: `paper_003` 4.07 GiB (Dropbox) and `paper_004` 2.88 GiB (Hugging Face). `paper_005` ships 41.3 MiB in the repository.
- `paper_008`'s loader needs split files (`train_idx.csv`, `valid_idx.csv`, `test_idx.csv`) that are not published.
- Pre-cache input: a data cache would have changed no pilot outcome (five papers stopped at dependencies first), so it is not worth building before the dependency problems are addressed. No cache was built.

### Pilot Failure Categories (2026-09-30 21:42 +03:00, Issue #125, P4)
- `scripts/categorize_pilot_failures.py` applies protocol section 7 to the stored runs. The first failure (stage → install → run) decides, and the deciding log line is quoted verbatim. Result: 5 × `MISSING_DEPENDENCY` (002, 003, 005 at install; 004, 006 at run), 1 × `DATA_NOT_ACCESSIBLE` (008), no `OTHER` (`data/pilot_runs/failure_categories.json`).
- `runs.failure_category` column (ORM, `data/schema.sql`; `init_db` adds it to older SQLite databases). `scripts/load_pilot_runs.py` stores the 6 pilot runs with their category next to each run.
- Tests: the rules, the verbatim evidence lines, the column upgrade, and the loader.

### Pilot Run and Measurements (2026-09-30 21:36 +03:00, Issues #123 P2 and #124 P3)
- Pilot run: workflow run 36759195752 (commit `dbcbe5a`, 2026-09-30 18:31 UTC), all 6 papers, 1-4 minutes per job. Every `run_report.json` shows `docker_used: true` and `isolated: true`, and every repository was checked out at its pinned commit. The raw files are stored unchanged in `data/pilot_runs/`.
- `scripts/pilot_measurements.py` (committed before the results were read) applies the protocol definitions: install success 1 / 6, run success 0 / 6, pilot success 0 / 6 (`data/pilot_runs/measurements.md`). A test fails if the stored measurements stop matching the stored runs.

### Peak Memory and Install Duration Recorded (2026-09-30 20:53 +03:00, Issue #124, P3 part 1)
- `docker/entrypoint.sh`: `execution_meta.json` gets `peak_memory_bytes` (cgroup `memory.peak`, `null` if not exposed); `install_meta.json` gets `duration_seconds` and `peak_memory_bytes`. `scripts/run_pilot.py` copies the run peak into `pilot_record.json`. Done before the pilot runs, so the protocol's peak-memory measurement (section 6) is possible.
- Acceptance check 12 (real Docker, CI run 36754386741): a probe holding 200 MiB reported `peak_memory_bytes: 221929472`, and the install phase reported `duration_seconds: 0.784`. 12 of 12 checks pass; `docs/SANDBOX_ACCEPTANCE.md` was regenerated from that run.

### Pilot Runner and Workflow (2026-09-30 00:09 +03:00, Issue #123, P2 — not run yet)
- `scripts/run_pilot.py`: runs one seed paper exactly as `docs/PILOT_WEEK2.md` specifies. It stages at the pinned commit, bundles binary wheels on the host, and runs the install and run phases with the protocol limits (2 CPUs, 6 GB, 100 processes, 3600 s per phase). It writes `pilot_record.json` next to `run_report.json`, exits 0 when the paper went through the pipeline, and exits 1 on a harness error.
- `.github/workflows/pilot.yml`: started by hand only, one job per paper, `contents: read`, no secrets, no persisted credentials. It records the runner environment and uploads each paper's output (without installed dependencies) as an artifact.
- `tests/test_run_pilot.py`: commands, environment variables, and limits equal the protocol table; staging failures are recorded; the workflow stays manual and read-only. `pyyaml` added to the dev requirements for the workflow check.
- Local check without Docker: `paper_006` was cloned at its pinned commit and then refused to run (`SandboxUnavailableError`, exit 1). No paper code has run yet; the pilot run waits for the owner's approval of the Actions minutes.

### Pilot Protocol Written Before Any Run (2026-09-28 21:28 +03:00, Issue #122, P1)
- `docs/PILOT_WEEK2.md`: the pilot runs on GitHub-hosted runners (the development machine has no Docker) through a hand-started workflow built in P2 (#123); fixed limits (2 CPUs, 6 GB memory, 100 processes, 3600 s per phase, no network, CPU only); one exact command per paper, taken from each README at the pinned commit with no change to the repositories; the definitions of install success, run success, and pilot success rate; the failure categories with their evidence; and what may change after the runs start.
- Found while reading the repositories: `paper_002`'s target script has no entry point, `paper_004` and `paper_006` have no pip requirements file (conda only), and `paper_005` needs a C++ extension the sandbox does not build. Recorded in the protocol, not fixed.
- `tests/test_pilot_protocol.py`: the protocol has one command row per seed paper, with the same repository, commit, and target script as `data/seed_papers.json`.
- No paper code was run.

### Roadmap Recorded and Tracked (2026-09-28 20:33 +03:00, Issue #121)
- `docs/ROADMAP_2026-09-27.md`: complete English translation of the 2026-09-27 plan (sections 0-8, P1-P7, W1-W7), with the tracking issue next to every item. The binding order: pilot (#43) and claim extraction (#9) first and in parallel; the CLI (#136) and the report (#120) only after both; low-priority cleanup (#137, #138, #139) last.
- New issues: #122-#128 (P1-P7), #129-#133 (W1-W5), #134 (W7), #135 (section 3 closing step), #136 (GA-2), #137 (GA-15), #138 (coverage), #139 (GA-11). Updated instead of duplicated: #43 (pilot, now the current corpus), #9 (LLM extraction with quote verification), #10 (= W6), #120 (report order).
- `AGENTS.md` §6: permanent roadmap rules (English only, binding order, one topic per PR, script-generated report numbers, no simulated data as results, no committed API keys, working loop, read the roadmap first). `CLAUDE.md` points agents to `AGENTS.md`.
- `docs/gap_analysis.md`: GA-2, GA-5, GA-11, and GA-15 now link to their issues.
- No roadmap work item (pilot, extraction, CLI) was started.

### Docs: Introduction Draft Corrected and Sourced (2026-09-27, Issue #118)
- `docs/repro_radar_introduction.docx` is now marked DRAFT (title, header, banner) and scoped to a pilot study on tabular ML benchmarks.
- Unsourced claims (the 35% figure, the 1995 Claerbout date and long quote, dependency decay in 6–18 months, hardware drift) and out-of-scope claims (domain-agnostic scope, AI Decision Layer, "resolves") were removed.
- References [1]–[7] are cited in the text and checked against Crossref or the publisher page; the Claerbout quote uses the wording read in Donoho (2010).
- `docs/INTRODUCTION_SOURCES.md` maps each statement to its source and says how much of each source was read.
- Tests: the draft marking, the removed phrases, and the reference/citation match are checked in `tests/test_academic_doc.py`.

### M0 / DevOps: PR Template and Working Agreement (2026-09-27, Issues #115, #116)
- `.github/PULL_REQUEST_TEMPLATE.md`: what/why, how I tested it, what I did NOT verify, AI use, self-review checklist.
- Standing, pinned issue #115 holds the working agreement and a per-session checklist.

### M2 / Sandbox: Output Directory Writable by the Container on Any Host UID (2026-09-27, Issue #96)
- Reproduced by removing the acceptance script's `chmod` workaround: on the uid 1001 CI runner, 10 of 11 Docker checks failed with `execution_meta.json: <not written>`.
- The runner now opens the output directory only while the containers run and restores 0755 afterwards; all 11 acceptance checks pass without the workaround.
- 1 new POSIX test (runs on Linux CI).

### M2 / Sandbox: Acceptance Checks 8-11 (2026-09-27, Issue #110)
- New real-Docker checks: OOM kill under a 256 MiB limit (`OOM_KILLED` after 0.165 s), PID limit (thread creation stops after 95 extra threads), numpy 2.4.6 vs the Dockerfile floor `>=1.24.0`, and a non-existent requirement (install `FAILED`, run still completes). **11 of 11 pass** in CI run 36319286095.
- Check 8 first failed and exposed that OOM kills were reported as `TIMEOUT`; fixed separately in #113.
- Note: the numpy "bound" is only a floor; the version in the image is not pinned (GA-6).

### M2 / Sandbox: OOM Kills No Longer Reported as Timeouts (2026-09-27, Issue #112)
- Found by the new acceptance check 8: an OOM kill after 0.185 s was reported as `TIMEOUT` (exit 137 is SIGKILL for both the timeout watchdog and the OOM killer).
- The entrypoint compares the cgroup `oom_kill` counter before and after the run and writes `OOM_KILLED`; the runner reports the entrypoint's status instead of re-deriving it from the exit code.
- 2 new tests; CI checks both an OOM kill and a real timeout on Docker.

### M0 / DevOps: Gap Analysis Addendum (2026-09-27, Issue #108)
- GA-22: `pip download --prefer-binary` on the host ran an sdist's `setup.py`; reproduced with a marker-writing probe package (old command: marker written; current command: rejected, no marker). Fixed by #95 and #103.
- GA-17 updated with the claim check (2 of 16 found, #101) and the removed TabNet entry's wrong claims.

### M2 / Sandbox: Install Status at the Top of the Run Report (2026-09-27, Issue #106)
- `run_report.json` has a top-level `dependency_install_status` (`UNKNOWN` without execution metadata) for Tier 1 scoring.
- New test follows a failed install phase through the run into the report (`FAILED`); 89 tests green, 7 skipped on Windows.
- Not done: `ReproducibilityScorer` does not consume run reports yet (it is only fed by the simulated `cli.py score`, GA-2).

### M2 / Sandbox: Decision Log (2026-09-27, Issue #104)
- `docs/DECISIONS.md`: D-001 records that PR #64's removal of `noexec` from `/workspace/home` had no effect (Docker's tmpfs default), why `noexec` is kept, and the risk that `exec` would add; D-002 records the two-phase, read-only dependency mount. Each fact cites a PR or CI output.

### M2 / Sandbox: Bundle Every Requirements File; Flag Packages Without Wheels (2026-09-27, Issue #102)
- `bundle_dependencies()` downloads from every `*requirements*.txt` (previously only the first). If the download fails, each requirement is probed alone (binary-only, `--no-deps`) and the ones without a wheel are reported as `NEEDS_SDIST_BUILD`; nothing is built on the host.
- The install phase installs from the same files.
- 2 new tests; CI adds a real `pip download` check (`docopt==0.6.2`, sdist-only, is flagged) and a two-file install-phase check.

### M1 / Corpus: Claims Checked Against Papers; Seed Integrity Test (2026-09-27, Issue #100)
- Every seed claim was searched in its paper's PDF text (all printable forms, tolerant of `pypdf` spacing) and read in context: **2 of 16 claims found** (`paper_003` FT-T and ResNet, Table 2, p. 7). `paper_002`'s 0.895 is AutoGluon's value, not TabPFN's (0.894); `paper_005` cites a dataset "EP3602" and `paper_008` a HIGGS result that their papers do not contain. Details in `docs/CORPUS_VERIFICATION.md`; claim values were not changed.
- `tests/test_seed_integrity.py`: repository reachable, license allowed and matching, script at the pinned commit, one case per entry; network-only (`REPRO_RADAR_NETWORK_TESTS=1`), run in the CI corpus job. It fails for all 8 entries of the pre-fix corpus and passes for the current 6.
- No entry is called verified: each still has unverified claims and unchecked runnability.

### M2 / Sandbox: Compiled Dependencies Without Loosening Isolation (2026-09-27, Issue #92)
- Dependencies are installed by a separate install-phase container (network off, `--only-binary=:all:`, so no package code runs) into `sandbox_runs/<paper_id>/deps`, which the paper run mounts read-only at `/workspace/deps`. Compiled extensions load; `/workspace/home` and `/tmp` stay `noexec`, so paper code has no location that is both writable and executable.
- Rejected: `exec` on the home tmpfs (paper code could write and run binaries) and pre-installing packages into the image (papers pin different, large versions such as old PyTorch).
- Bundling now downloads binary wheels for the sandbox platform (manylinux, CPython 3.11) instead of the host OS.
- New acceptance check 7: `ujson` (C extension, not in the image) installs offline and loads from `/workspace/deps`; writes there fail with `Read-only file system`; the same `.so` copied to the noexec home fails to load. 7 of 7 checks pass in CI.
- The `deps` directory is world-writable only while the install container writes to it and is restored to 0755 before the run.
- Found during review and left open: the acceptance script makes the output directory world-writable, which may hide an output-permission problem on hosts not running as uid 1000 (#96).
- 7 new tests; 86 / 86 green on Linux.

### M0 / DevOps: Gap Analysis Cleanup (2026-09-27, Issue #93)
- Gap IDs renamed `G<n>` → `GA-<n>` in `docs/gap_analysis.md`, `docs/PROGRESS.md`, and `README.md`, so they no longer collide with the maintainer's TODO items `G1`-`G6`.
- Added gaps missed by the analysis: GA-17 (broken seed corpus labelled "verified", fixed in #85) and GA-18 (out-of-order work; PRs #56-#63 each merged 3-12 seconds after opening with no review), plus GA-19 to GA-21 found by the acceptance checks.
- Status references now point to the PRs that did the work.
- Checked: no "Hafta" milestones remain (removed in #76).

### M2 / Sandbox: Acceptance Evidence and Tracking Aligned (2026-09-27, Issue #86)
- `scripts/sandbox_acceptance.py` runs six checks through `DockerSandboxRunner` against a real Docker daemon in CI; **6 of 6 pass** (non-root uid 1000, network blocked, read-only root, `TIMEOUT` with duration > 0, offline install of a package not in the image, refusal without Docker). Output recorded verbatim in `docs/SANDBOX_ACCEPTANCE.md`.
- Building the evidence found and fixed two runner bugs (#88/#89, #90/#91), replaced a check that proved nothing (`six` was already in the image), and found that `/workspace/home` is `noexec` by Docker default (open: #92).
- Issue #48 rewritten in English with evidence for 4 of 5 goals and reopened (multi-seed execution is not implemented). M2 issues #13, #14, #15, #17, #18: boxes ticked only where evidence exists, with evidence notes.
- `docs/SANDBOX_GUIDE.md`: home mount, `noexec` finding, timeout defaults, and offline install status corrected.

### M2 / Sandbox: Home tmpfs Writable by the Sandbox User (2026-09-27, Issue #90)
- Found by the real-Docker acceptance run: the `/workspace/home` tmpfs was root-owned, so uid 1000 could not write to it and the offline wheel install could never succeed (`mkdir: cannot create directory '/workspace/home': Permission denied`).
- The runner and `docker/docker-compose.sandbox.yml` now mount it with `uid`/`gid` of the sandbox user.
- 1 new test; 79 / 79 tests green.

### M2 / Sandbox: Docker Runs Misreported as FAILED on Non-1000 UIDs (2026-09-26, Issue #88)
- Found by the first real-Docker acceptance run (Ubuntu CI runner, uid 1001): the runner re-wrote `stdout.log`/`stderr.log` that the container had already written as uid 1000, hit `PermissionError`, and reported every successful run as `FAILED` with its output dropped.
- The runner now keeps logs the entrypoint wrote and never lets a log write change a run's result.
- 1 new regression test; 78 / 78 tests green.

### M1 / Corpus: Seed Corpus Repaired and Verified by CI (2026-09-26, Issue #84)
- `data/seed_papers.json`: 6 entries, **6 of 6 pass `scripts/verify_corpus.py`**; every entry now pins a `repo_commit`. Removed `paper_001` (no license) and `paper_007` (community reimplementation with no runnable script).
- Fixed script paths (3 entries), renamed or mistyped repositories (3), licenses (4), titles (4), and `paper_005`'s paper link, year, and venue.
- CI corpus job is now blocking.
- `docs/CORPUS_VERIFICATION.md` records per-entry checks; runnability and all claim values are **UNVERIFIED**, and the claims of `paper_005` and `paper_008` are flagged SUSPECT.
- README no longer calls the corpus "8 verified" papers or promises short CPU-only runs.

### M1 / Corpus: Automated Corpus Verifier (2026-09-26, Issue #82)
- `scripts/verify_corpus.py` checks every seed entry: paper page title matches, GitHub repository exists (renames followed and reported), GitHub license is allowed and equals the declared license, and `target_script` exists at a pinned `repo_commit`. Any failure, including a network error, exits 1.
- First run against `data/seed_papers.json`: **0 of 8 entries pass**. Beyond the missing pinned commits, it found 4 license mismatches or unrecognized licenses, 4 title mismatches (including `paper_005` pointing to an unrelated physics paper), 2 renamed repositories, and 1 missing repository (`paper_006`).
- CI runs the verifier as a non-blocking job until the corpus is fixed in the next step.
- 16 new offline unit tests (fake HTTP client); 73 / 73 tests green.

### M2 / Sandbox: No Silent Unisolated Fallback (2026-09-26, Issue #80)
- `DockerSandboxRunner.run()` now raises `SandboxUnavailableError` and executes nothing when Docker is unavailable; previously it silently ran paper code on the host.
- Unisolated local execution requires the explicit `--allow-unsafe-local` flag (`SandboxConfig.allow_unsafe_local`); such runs print a red warning and are recorded as `"isolated": false` in `run_report.json`. Docker runs record `"isolated": true`.
- `scripts/stage_and_bundle_repo.py` exits with code 4 when execution is refused.
- Docs aligned (`README.md`, `docs/SANDBOX_GUIDE.md`, `docs/ENVIRONMENT.md`, `docs/ARCHITECTURE.md`); gap added to `docs/gap_analysis.md` as GA-16.
- 57 / 57 tests green: 5 new tests, the old fallback test rewritten for the new behavior, and the stager execution test extended to assert `isolated: false`.

### M0 / DevOps: Side-Effect Approval Gate Restored (2026-09-26, Issue #78)
- `AGENTS.md` §5.6 restored verbatim to its wording before PR #75: explicit go-ahead before git pushes, PR merges, or DB drops.
- Reason: a project review found that the relaxed gate removed the human check where the most serious problems originated (PRs merged minutes after opening without a diff review, completion claims without evidence). Green tests did not catch those problems. The maintainer and mentor decided to keep the original rule.
- The #69 entry below is kept as history; this entry supersedes it.

### M0 / DevOps: Tracking Reconciled with GitHub (2026-09-25, Issue #76)
- GitHub: closed implemented issues #5, #16, #27, #28, #47 with evidence; closed weekly umbrella issues #49, #51, #52, #53 as duplicates of the per-issue backlog; added done/missing status notes to #2, #4, #10, #11, #13, #14, #15, #17, #18, #30; removed the seven empty "Hafta" milestones.
- `docs/BLUEPRINT.md`: all 45 backlog references renumbered by title match against GitHub (they were one lower than the real issue numbers).
- This file: milestone table rebuilt from GitHub open/closed counts; no milestone is marked completed while it has open issues.
- Resolves gap analysis GA-1 and GA-4.

### M0 / DevOps: Relaxed Side-Effect Approval Gate (2026-09-25, Issue #69)
- `AGENTS.md` §5.6: after an approved proposal and a green suite, push, PR, merge, and merged-branch deletion no longer need a separate go-ahead.
- Force-pushes, direct commits to `main`, closing issues without a merged PR, settings changes, and destructive operations still require explicit approval.

### M7 / DevOps: Continuous Integration (2026-09-25, Issue #42, PR #74)
- `.github/workflows/ci.yml`: `ruff` and `pytest --cov` on Ubuntu and Windows (Python 3.11), plus a sandbox image job that builds `Dockerfile.sandbox`, checks for stray redirect files, and asserts `dependency_install_status` values. Resolves GA-3 and verifies the GA-7/GA-8 fixes from #71 on Docker.
- First CI run exposed a host-dependent test: `test_execute_staged_produces_report_and_metrics` assumed Docker was absent and failed on Ubuntu runners, where Docker is installed. The test now forces the process runner, like the other sandbox tests.

### M0 / DevOps: Setup & Verification Docs for the New Environment (2026-09-25, Issue #72)
- `README.md`: Quickstart installs `requirements-dev.txt` (runtime-only alternative noted), adds the Windows `py` launcher note, lint step, an accurate simulation note (GA-2), and a refreshed directory layout (GA-12).
- `docs/ENVIRONMENT.md`: separate runtime and development package tables, updated Windows and Linux/macOS setup, sandbox image smoke test with `dependency_install_status`, and a new verified baseline (52 tests, ruff clean).
- `docs/SANDBOX_GUIDE.md`: actual `execution_meta.json` fields and the new `meta_error` report field.
- `docs/gap_analysis.md`: status column tracking which gaps are fixed, partly fixed, or open.

### M0 / DevOps: Gap Remediation — Sandbox, Dependency, and Safety Fixes (2026-09-25, Issue #70)
- **CI (GA-3):** workflow prepared (lint, tests on Ubuntu and Windows, sandbox image build and smoke test) but not yet pushed: the GitHub token lacks the `workflow` scope. Follows in a separate PR.
- **Dependencies (GA-6):** `requirements.txt` now holds runtime packages only (`pydantic`, `sqlalchemy`, `tabulate`); tests, lint, and document tooling moved to `requirements-dev.txt`; unused `pandas`, `pyyaml`, and `requests` removed. `pyproject.toml` defines the ruff correctness gate.
- **Sandbox image (GA-7):** version constraints in `Dockerfile.sandbox` are quoted, so they are no longer parsed as shell redirections.
- **Entrypoint (GA-8):** `execution_meta.json` gains `dependency_install_status` (`SKIPPED` / `INSTALLED` / `FAILED`) instead of hiding install failures behind `|| true`.
- **Error handling (GA-9):** the metric extractor logs skipped non-JSON blocks; `execute_staged` reports an unreadable `execution_meta.json` as `meta_error`.
- **Security (GA-10):** `setup_github_backlog.py` passes argument lists without a shell and sends issue bodies on stdin.
- **Docker hygiene (GA-14):** `.dockerignore` limits the build context; obsolete Compose `version` key removed.
- 52 / 52 tests green (3 new), verified in a clean venv built from `requirements-dev.txt`.

### M0 / DevOps: Repository Gap Analysis (2026-09-24, Issue #67)
- Added `docs/gap_analysis.md`: 15 gaps (3 high, 7 medium, 5 low) across tracking, product, CI, tests, dependencies, sandbox, code quality, security, and docs, each with evidence, remedy, and related issue.
- Measured baseline: 60% line coverage (`cli.py` 0%), 281 `ruff` findings, 49 / 49 tests green.
- Highest-impact findings: living docs disagree with GitHub milestone/issue state (GA-1), `cli.py score` still runs on simulated outputs (GA-2), no CI (GA-3).
- Report only; each gap is to be filed and fixed through the normal issue loop.

### M0 / DevOps: Environment & Dependency Inventory (2026-09-24, Issue #65)
- Added `docs/ENVIRONMENT.md`: system tools (required vs optional), Python packages mapped to importing modules, sandbox image contents, environment variables, runtime paths, and fresh-machine setup steps for Windows and Linux/macOS.
- Verified on a clean Windows 11 machine with Python 3.11.9: fresh `.venv`, `requirements.txt` installed, 49 / 49 tests green, `cli.py init-db` seeds 8 papers.
- Found that `pandas`, `pyyaml`, and `requests` are declared in `requirements.txt` but not imported anywhere yet (flagged for the gap analysis).
- Linked the inventory from the README Quickstart.

### M4 / Core: Model Validation Rubric & Statistical Stability Analyzer (2026-09-18, PR #60)
- **Model Validation Framework (`src/validation_rubric.py`, `docs/VALIDATION_RUBRIC.md`):**
  - Formulated `MetricCategory` separating bounded rate metrics (accuracy, AUC, F1) from unbounded loss (MSE, RMSE, cross-entropy) and hardware runtime latencies.
  - Implemented dual relative/absolute tolerance checks, asymmetric loss improvements, and hardware variance allowance.
  - `MultiSeedStabilityAnalyzer`: Computes sample variance, standard deviation, Coefficient of Variation (CV <= 2% threshold), and 95% confidence intervals.
  - `detect_anomalies`: Flags NaN/Inf values, suspicious 1.0000 accuracy scores (data leakage guard), and metric sign inversions.
  - 41 unit tests verified green.

### Documentation: Cover Hero Banner & Academic Introduction Word Document (2026-09-18, PR #61)
- **Cover Visual Hero Asset (`docs/assets/repro_radar_banner.png`):**
  - High-resolution 1200x420 dark-mode project banner with radar grid motif, typography, and architecture badges.
- **Academic Publication Deliverable (`docs/repro_radar_introduction.docx`):**
  - Formal publication-grade Word document authored via `scripts/generate_academic_introduction_doc.py`.
  - Includes executive abstract, 5 structured academic sections, 3 styled comparison tables, callout blocks, and formal references (Claerbout, Donoho, Pineau, Stodden, Baker).

### M4: Empirical Metric Extraction & Log Parsing Engine (2026-09-18, PR #62)
- **Log Parsing Engine (`src/metric_extractor.py`):**
  - Scikit-learn classification report parser (accuracy, macro/weighted precision, recall, F1).
  - JSON and JSONL dictionary parser for HuggingFace/Lightning outputs.
  - Framework log parser for LightGBM, XGBoost, and PyTorch training iterations.
  - Multi-pattern regex extractor with attached unit handling (`ms`, `sec`, `qps`, `mb`, `gb`, `%\`).
  - Seamless integration into `RepoStager.execute_staged()` to automatically extract metrics directly from sandbox logs.
  - 49 unit tests verified green.

### M2 / Core: Isolated Container Sandbox & Staging Subsystem (2026-09-17)
- **Hardened Docker Sandbox (`docker/Dockerfile.sandbox`, `docker/docker-compose.sandbox.yml`, `docker/entrypoint.sh`):**
  - Ephemeral unprivileged `sandboxuser` (UID: 1000).
  - Strict security constraints: `--network none`, `--read-only` root, `tmpfs` mounts with `noexec,nosuid`.
  - Hard quotas: 2.0 CPUs, 8192 MB RAM, 100 PIDs, signal-trapped timeout termination.
- **Python Execution Engine (`src/sandbox/runner.py`):**
  - `DockerSandboxRunner`: Automated command builder, volume mounter, and metadata collector.
  - Automatic host detection with graceful fallback to `ProcessSandboxRunner`.
- **Repository Staging & Offline Wheel Bundler (`src/sandbox/stager.py`, `scripts/stage_and_bundle_repo.py`):**
  - Git cloning (GitHub / IEEE open repositories) with commit/tag pinning.
  - Manifest discovery for `requirements.txt`, `pyproject.toml`, `setup.py`, `environment.yml`.
  - Offline wheel compilation via `pip download` for network-isolated containers.
  - Automated CLI script outputting structured run reports and metrics JSON.
- **Documentation & Test Suite (`docs/SANDBOX_GUIDE.md`, `tests/test_sandbox.py`, `tests/test_stager.py`):**
  - Complete architecture documentation and CLI manual.
  - 34/34 tests passing with zero failures.

### M0: Baseline Hygiene & Projectflow Adoption (2026-09-13)
- **Git Identity & Contribution Profile:**
  - Configured Git author identity to `yusufkartal0009-eng <yusufkartal0009@gmail.com>`.
- **Projectflow Methodology Setup:**
  - Standardized taxonomy to 6 core functional areas: `corpus`, `sandbox`, `scoring`, `ai`, `web`, `devops`.
  - Defined 8 milestones (M0 through M7) and 45 engineering issues in `docs/BLUEPRINT.md`.
  - Created branch `chore/devops/adopt-projectflow` and pull request.
  - Updated `AGENTS.md` and living documents (`docs/BLUEPRINT.md`, `docs/ARCHITECTURE.md`, `docs/PROGRESS.md`, `docs/STACK.md`).
- **Language Standard:**
  - Verified 100% English compliance across all repository files and database schemas.

### Pre-M0 Foundations (2026-09-10)
- **Repository Setup:**
  - Clean repository with `.gitignore`, MIT `LICENSE`, and Python 3.11 environment.
- **Relational Data Layer:**
  - SQLite DDL schema in `data/schema.sql` (`papers`, `runs`, `claims`, `scores`).
  - SQLAlchemy ORM & Pydantic v2 schemas in `src/models.py`.
  - Database initialization and seeding engine in `src/database.py`.
- **Target Paper Dataset:**
  - Seed dataset of 18 tabular ML & light NLP benchmark papers in `data/seed_papers.json`.
  - *18 → 8 (2026-09-13, commit `7a7d9ac`):* the 18 Week 1 entries were placeholders ("mock seed papers" in that commit's title); several paired paper titles with general-purpose library repositories (e.g. `optuna/optuna`, `huggingface/transformers`, `scikit-learn/scikit-learn`). They were replaced by 8 entries meant to map to real paper repositories. That commit called them "verified", which a later check disproved: see the 2026-09-26 entries for issues #82 and #84 (now 6 entries).
- **Reproducibility Scoring Engine:**
  - 4-Tier rubric (%35 Build, %35 Metrics, %15 Stability, %15 Artifacts) in `src/scoring.py`.
- **CLI & Test Suite:**
  - Built `cli.py` with `init-db`, `list-papers`, `inspect`, and `score` commands.
  - 20 unit tests in `tests/` passing.

### 2026-10-15 12:20: D1 backend API (#37, #41)
- `src/web/routes.py`: `GET /api/v1/papers` (moved from `app.py`), `GET /api/v1/scores` (best first, optional `?status=`), `GET /api/v1/scores/{paper_id}`, `GET /api/v1/runs/{run_id}`. All values come from the database; empty tables give `[]`, unknown IDs give 404, seed claim values stay hidden. OpenAPI at `/docs`.
- `tests/test_web_api.py`: 11 test cases (D5 for this slice). Full suite 506 passed, 9 skipped; ruff clean.
- Real local database: 6 papers, 6 runs, **0 scores** (nothing has been scored yet), so `/api/v1/scores` is honestly `[]`. Output in `docs/evidence/d1/curl.txt`. No UI decision in this step.

### 2026-10-15 12:38: D2 leaderboard and detail page (#38, #41)
- Owner's choices (asked with previews before building): one table, a search box plus a status menu, a separate detail page, option A style (light, plain, system font).
- `src/web/pages.py`: leaderboard with search (title, venue), status filter (4 labels + "Not scored"), sorting by Paper / Year / Score (unscored papers always last), counts from the database; detail page `/papers/{paper_id}` with the score breakdown, latest run, and the last 20 log lines; explicit empty states and a 404 page. Filters are URL query parameters. No new dependency, so no Jinja template file (`templates/leaderboard.html` of the issue was not created).
- `tests/test_web_pages.py`: 11 tests (order, sort, search, filter, counts, escaping, detail, 404, empty). Suite: 517 passed, 9 skipped; ruff clean.
- Evidence: `docs/evidence/d2/`. The real database has 0 scores, so its screenshot shows only "Not scored"; the scored screens use a labeled DEMO database with invented numbers (not results).

### 2026-10-15 13:52: D3 SVG badges (#39, #41)
- Owner's choice (asked with previews): shields.io style, two parts, gray "repro radar" and a colored "<score> · <status>"; gray "not scored" when a paper has no score.
- `src/web/badge_generator.py` (pure function, all text escaped) and `GET /api/v1/badges/{paper_id}.svg` (404 for an unknown paper; `Cache-Control: public, max-age=300` and a content ETag with 304).
- `tests/test_badge_generator.py`: 15 test cases. Suite: 533 passed, 9 skipped; ruff clean.
- Evidence: `docs/evidence/d3/`. The real database has 0 scores, so its badge is "not scored"; the four colored badges come from the labeled DEMO database (invented numbers).

### 2026-10-15 14:21: D4 report export, Markdown and PDF (#40, #41)
- Owner's choices (asked with previews): one-page layout with the summary on top; PDF with the new dependency `fpdf2` (pure Python, added to `requirements.txt`).
- `src/web/exporter.py`: one `Report` object from the database, rendered as Markdown and PDF (summary, score breakdown, latest run with the last 20 log lines, claims, integrity hashes, links). No score says "Not scored"; seed claim values are never exported; a code fence in a log cannot break out of the Markdown block; the PDF uses a core font, so characters outside Latin-1 become "?".
- Routes `GET /api/v1/papers/{paper_id}/report.md` and `.pdf` (attachment downloads, 404 for an unknown paper); two download links on the detail page.
- `tests/test_web_exporter.py`: 8 tests (PDF text is read back with pypdf). Suite: 541 passed, 9 skipped; ruff clean.
- Evidence: `docs/evidence/d4/`; the real database has 0 scores, the scored example is the labeled DEMO database.

### 2026-10-15 14:27: report sections 1, 9 and 10 drafted (#299), not merged
- Abstract (199 words; its numbers are the generated block `abstractnumbers`, a new name for the same sentence as `pilot3summary` because a block name can be used once per document), Conclusion and future work, and References [1]-[14] with a reproducibility statement. All text is marked "drafted, for the owner's review".
- References: the five that had no title in the repository (1 to 5) were checked against Crossref (titles, authors, container) before they were written down; [6]-[14] come from `docs/report/RELATED_WORK_SOURCES.md`. No new source. No release tag exists (#45 open), which the statement says.
- `scripts/report_numbers.py --check` in sync; suite 542 passed, 9 skipped; ruff clean.

### 2026-10-15 18:51: review of the report sections 1, 9, 10 (#299, #120)
- Rechecked: the rates of the three pilots against `data/pilot_runs`, `pilot2_runs`, `pilot3_runs` `measurements.json` (1/6, 0/6, 0/6; 6/6, 1/6, 1/6; 6/6, 2/6, 2/6); references [6]-[14] by re-running `scripts/verify_sources.py` (9 of 9 VERIFIED; only `checked_at` changed) and [1]-[5] against Crossref (year, volume, pages, authors); the conclusion against sections 6 and 7 (no claim beyond them).
- Fixed in the same PR: the introduction said "two pilots" (now three), and the report's banner and four section statuses said "skeleton" or "not merged" (now "written").

### 2026-10-15 18:56: docs: clean-install test of the README steps; fix stale CONTRIBUTING text
- Followed the README steps in a fresh clone (commit c8a99f8): install, init-db, ruff, 542 tests, dashboard, badge, report all worked without a manual step. Recorded in `docs/ENVIRONMENT.md`.
- Fixed `CONTRIBUTING.md`: it still said GitHub Actions was disabled.

### 2026-10-15 18:59: docs(readme): add a dashboard section
- README: new step 8 "Open the Local Dashboard" (command, localhost only, address table, empty states, where the screenshots are, no numbers) and a `src/web/` line in the directory layout.
- Fixed the escaped backticks in the previous PROGRESS entry.

### 2026-10-15 19:04: chore: review the old corpus, sandbox and scoring issues
- Closed #6 with evidence (SPDX allow-list in `src/config.py`, the check in `scripts/verify_corpus.py`, two tests, the `corpus` CI job).
- Status comments (what is done, what is missing) on #7, #8, #13, #14, #15, #17, #18, #20, #23.
- Left alone: #19, #21, #22, #24, #30 (no code, or nothing new to add); #16 was already closed.

### 2026-10-15 21:06 +03:00: Independent Pass B imported (issue to be linked in the PR)
- **What:** the 2026-10-04 pass B, made by the same agent that made pass A, is replaced by a blind pass B. A fresh Claude Code process (`claude -p`, no conversation history, tools limited to Read, Write, Edit, Glob, Grep) worked in a blind packet folder (`make_blind_packet.py`, 19 questions) and wrote its answers with the Write tool. It had no access to pass A, the gold set, the owner's decisions, or the repository. `scripts/import_pass.py` imported the answers.
- **Result:** `scripts/compare_extractions.py`: 18 of 18 questions agree by normalized value, 0 disagree (12 values, 6 "not found"). The follow-up question for `paper_005` (EP300 average speedup, Table 1, page 10) was also answered by both passes with `16`; it is not accepted, not scored, and not in `data/seed_papers.json`.
- **Quote guard on pass B (`scripts/check_claims.py`):** 7 of pass B's 12 found claims are UNVERIFIED, only because the dataset or model **labels** pass B wrote (for example "California Housing (CA)", "TabPFN (GPU)") do not occur verbatim in the paper. Their values and quotes match exactly. Pass A's accepted claims are unchanged.
- **Limits:** both passes are the same model. The packet was started by the main session, which knew pass A, not by the owner in a separate terminal. A gold-set precision/recall was not re-run for pass B.
- `tests/test_followup_claims.py` updated for two passes; `docs/report/REPORT.md` numbers regenerated and its statements about independence corrected; `docs/AGENT_EXTRACTION.md` section 3 rewritten.

### 2026-10-15 21:30 +03:00: paper_005 follow-up claim accepted (EP300 average speedup)
- The owner accepted the follow-up claim of `paper_005`: EP300 average kernel speedup `16` (Table 1, page 10, row `EP300 2000 2000 4000 16 92`). Both passes (A, and the blind pass B) found it and the quote guard matched it; the value was also checked in the PDF text. Stored through `claim_store` as `verified_by: human`, exported with `scripts/apply_accepted_claims.py export`, applied to `data/seed_papers.json` (`apply`; `check`: consistent).
- It is not one of the 18 gold-set questions, so precision and recall (12 / 0 / 0 / 6) are unchanged. 13 claims are accepted in total.
- Not verified: no run has reproduced this value; the `paper_005` run stopped at the memory limit in Pilot 2 and Pilot 3. Its Tier 2 score still needs a run that produces the speedup.

### 2026-10-15 22:34 +03:00: Memory limit as a share of the host's RAM (Issue #311)
- `src/sandbox/resources.py`: `resolve_memory_limit` turns `50%` into a Docker size from the host's physical memory (Windows, Linux, macOS), capped at 90 percent of the memory Docker can see; a fixed size passes through. `DockerSandboxRunner` resolves it when it builds the command.
- `scripts/run_pilot.py run_paper(memory_limit=...)` records `memory_override` (requested, resolved, protocol size); `cli.py score --memory` defaults to `50%`. The pilot protocols and the library default keep fixed sizes (D-009 in `docs/DECISIONS.md`).
- `tests/test_sandbox_memory.py`: 13 cases with mocked memory sizes. Full suite 555 passed, 9 skipped; ruff clean. On the owner's machine the host reads 31.7 GiB and `50%` resolves to 16238m with Docker off; with Docker running at 15.5 GiB it is capped at about 14.3 GiB.
- Not verified: a real paper run with `50%`; the effect on run time.

### 2026-10-15 23:09 +03:00: Synthetic control paper (Issue #313)
- `scripts/synthetic_control.py` runs a dependency-free synthetic paper (prints `accuracy: 0.9000`) through the real pipeline in real Docker twice and scores the stored run against a true claim (0.9) and a false claim (0.5). Evidence: `data/synthetic_control/`.
- **Found a scoring bug:** both claims scored Tier 2 = 0 because a repository without requirements has install status SKIPPED, which `src/score_run.py` counted as a failed install, so the scorer ignored the reproduced metric. Fixed (SKIPPED means nothing to install; a failed script still reproduces nothing). Now: true claim Tier 2 100 (91.75, Verified), false claim Tier 2 0 (56.75, Needs Review). `tests/test_score_run_skipped.py` (4 cases). The first result is kept in `result_before_fix.json`.
- Two runs of the synthetic paper agree on status, exit code, and metrics; the two log files are identical.
- Not verified: real papers (the control is deterministic and has no training, data, or network); Tier 3.

### 2026-10-15 23:25 +03:00: Gold set expansion: 18 more questions, two passes (Issue #315)
- `docs/GOLD_SET_EXPANSION.md` (selection rule written first), `data/gold_expansion/` (18 questions, candidates, pass A, pass B), `scripts/gold_expansion.py` (`packet`, `form`, `import-pass`), `tests/test_gold_expansion.py` (8 cases).
- Pass A: the main session (not blind). Pass B: a fresh `claude -p` process on a blind packet. **18 of 18 agree** by normalized value (12 values, 6 "not found" including all 6 negative controls); every quote of both passes occurs on its page.
- The owner's gold set for these questions does not exist yet: the form is outside the repository; **no precision or recall is claimed** until the owner has filled it and `evaluate_gold.py` has scored both passes.
- Not verified: correctness of the values against the owner's own reading; same-model passes; the packet was started by the main session, not by the owner.

### 2026-10-16 14:23 +03:00: fix(scoring): 'not found' is no longer reported as a divergence (Issue #317)
- `ReproducibilityScorer.calculate_composite_score` has a new flag `nothing_compared`; `evaluate_paper_run` sets it when the run succeeded, claims exist, and none of them was found in the output. The two summaries that blamed the claims ("significant divergence" and "fell short of claims") then say "claimed metrics not found in the output (nothing was compared)". "Divergence" stays for claims that were found and differ.
- Tests: `tests/test_scoring.py` (two new cases: nothing found, including an empty output; found and different). `tests/`: 569 passed, 9 skipped; ruff clean.
- Not verified: the stored summary of the earlier `paper_006` score run was not rewritten; this change only affects scores computed from now on.

### 2026-10-16 14:26 +03:00: feat(pilot): --memory and --record-root for run_pilot.py (Issue #319)
- `scripts/run_pilot.py` has two new options. `--memory` (a size or a share such as `50%`) replaces the memory and swap limits and writes `memory_override` (requested, resolved size, the protocol's limit) into the record. `--record-root DIR` writes the record and the collected files to `DIR/<paper_id>/` (needs `--pilot2` or `--pilot3`). `run_paper` already took both values (#311); only the command line was missing.
- With `--pilot3` the settings of `data/pilot3_settings.json` are used as they are; only the memory limit is replaced. For `paper_004` the 14400 s run phase stays. Long re-runs can go to `data/memory_runs/`, so `data/pilot2_runs/` and `data/pilot3_runs/` are not touched.
- Tests: `tests/test_pilot3.py` (4 new cases: only memory and directory change, Pilot 3's own limit is replaced and recorded, the command line passes both options, `--record-root` alone is refused). `tests/`: 573 passed, 9 skipped; ruff clean.
- Not verified: a real Docker run with the new options (that is the next job of the plan).

### 2026-10-16 15:15 +03:00: test(pilot): paper_003 re-run with Pilot 3 settings and a 50% memory limit (Issue #321)
- Command: `python scripts/run_pilot.py paper_003 --pilot3 --memory 50% --record-root data/memory_runs` (Docker 29.8.2, 12 CPUs, 16.6 GB seen by Docker). The record is `data/memory_runs/paper_003/` (unchanged files, plus `hash_compare.txt`). **Not a protocol run:** the memory limit is 14265m (50% of the host's RAM, capped to the Docker share) instead of 6g; every other setting is Pilot 3's.
- Result: status COMPLETED, exit code 0, 1497.4 s, peak memory 1165963264 bytes (about 1.09 GiB). Pilot 3 (6g): COMPLETED, exit code 0, 1516.7 s, peak 1190248448 bytes (about 1.11 GiB).
- Comparison with Pilot 3: the final lines are identical (train rmse 0.363, val rmse 0.473, test rmse 0.473). `stdout.log` is identical line by line after the epoch clock times and the line endings (the stored Pilot 3 copy has CRLF) are ignored. `scripts/hash_run.py --compare` reports 0 of 3 log files and 0 of 4 metadata files byte-identical (clock times, durations, paths and the progress bar in `stderr.log` differ), and no paper output files exist to compare.
- Not verified: that the logs differ only by timing (only `stdout.log` was compared after normalization); a second run under the same limit; any claim of the paper (the run is not scored).

### 2026-10-16 15:38 +03:00: test(pilot): paper_005 re-run with Pilot 3 settings and a 50% memory limit (Issue #323)
- Command: `python scripts/run_pilot.py paper_005 --pilot3 --memory 50% --record-root data/memory_runs`. Record: `data/memory_runs/paper_005/` (unchanged files). **Not a protocol run:** memory and swap limit 14265m (50% of the host's RAM, capped to the Docker share) instead of Pilot 3's 12g; all other settings are Pilot 3's. No retry.
- Result: **OOM_KILLED, exit code 137**, 1178.5 s, peak memory 14957936640 bytes (equal to the limit, 13.93 GiB). Pilot 3 (12g): OOM_KILLED, exit code 137, 972.7 s, peak 12884901888 bytes.
- Cause as logged: `execution_meta.json` says `"status": "OOM_KILLED"`, `"killed_before_timeout": false`. The last progress line of `stderr.log` is `1.1 grid search:  34%|███▍      | 187/540 [19:27<20:50,  3.54s/it]`; the last line of `stdout.log` is `Thread 0 finished in 15 iterations...` (a string-kernel computation with `g = 6, k = 4, 540056 features`). The grid search reached step 187 of 540 here, step 161 in Pilot 3 (12g) as counted from its `stderr.log`, and 76 in Pilot 2 (6g, from the task note).
- So the paper did not finish with 14265m either; more memory moved the kill later but did not remove it. Not verified: how much memory the full grid needs, and why it grows (the log shows the kill, not the allocation).

### 2026-10-16 18:57 +03:00: test(pilot): paper_004 re-run with Pilot 3 settings and a 50% memory limit (Issue #325)
- Command: `python scripts/run_pilot.py paper_004 --pilot3 --memory 50% --record-root data/memory_runs`. Record: `data/memory_runs/paper_004/` (unchanged files). **Not a protocol run:** memory and swap limit 14265m (50% of the host's RAM, capped to the Docker share) instead of 6g; the run phase keeps Pilot 3's 14400 s. No retry.
- Result: **COMPLETED, exit code 0**, 9202.2 s (about 2 h 33 min), peak memory 11420688384 bytes (about 10.64 GiB), `killed_before_timeout` false. Pilot 3 (6g): OOM_KILLED, exit code 137, 9018.1 s, peak 6442450944 bytes.
- The paper's own last output: `'best_epoch': 61`, `'scores': {'train': -0.3519..., 'val': -0.4187..., 'test': -0.3994...}`, `'time': '2:32:04'`. This run is **not scored**: no accepted claim of `paper_004` was compared with it, and the value above is the log's, not a result of this project.
- So the earlier kill was the 6g memory limit: with 14265m the same run finished. Peak memory (about 10.64 GiB) is above 6 GiB and below 12 GiB. Not verified: the smallest limit that suffices; a second run; whether the printed score matches the paper's claim.

### 2026-10-16 19:02 +03:00: docs: memory re-runs next to Pilot 3 and a paragraph in the report (Issue #327)
- `docs/MEMORY_RUNS.md`: how the three re-runs were made, why they are not protocol runs, a side-by-side table with Pilot 3 (status, exit code, duration, peak memory, memory limit, last grid-search step), whether each paper ran, what the records say about the sandbox's memory limit, and the limits of the evidence. The table is generated by `scripts/memory_runs.py` (`--write`, `--check`; 10 tests in `tests/test_memory_runs.py`).
- Result in one line each: `paper_003` COMPLETED at 6 and at 14265m (peak about 1.1 GiB); `paper_004` OOM_KILLED at 6 GiB in Pilot 3, COMPLETED at 14265m (peak 10.64 GiB); `paper_005` OOM_KILLED at 12 GiB (step 161/540) and again at 14265m (step 187/540).
- `docs/report/REPORT.md`: a "Memory re-runs" paragraph at the end of section 6.1a with a generated block `memoryruns` (new in `scripts/report_numbers.py`), and a sentence in the Resources limitation of section 7.
- **Defect found and fixed on the way:** four numbers blocks of the report (`pilot3summary`, `pilot3`, `pilot3failures`, and the new one) had their two markers on adjacent lines, which the block pattern never matches, so `report_numbers.py --check` passed on blocks that were empty. Section 6.1a therefore showed no Pilot 3 table until now. The blocks now hold a blank line between the markers and are filled (rates 6/6, 2/6, 2/6 as in `data/pilot3_runs/comparison.json`); `tests/test_memory_runs.py` fails if a block is empty or its markers touch.
- `tests/`: 583 passed, 9 skipped; ruff clean; `report_numbers.py --check` in sync.
- Not verified: single runs only; the smallest sufficient memory limit; the peak against another tool; a Linux host.

### 2026-10-16 21:01 +03:00: docs(report): checks after the pilots (Issue #329)
- `docs/report/REPORT.md`: new section 6.4 "Checks made after the pilots" (synthetic control paper and the SKIPPED-install bug it found; repeated runs of `paper_003` and `paper_006`; pointer to the memory re-runs; the extended gold set with no owner answers) and three limitation bullets (Tier 2 exercised only on the synthetic control; stability seen, not measured; extended gold set without answers).
- Numbers come from three new blocks in `scripts/report_numbers.py` (`syntheticcontrol`, `stability`, `goldexpansion`); the stability table is `scripts/run_stability.py` (status, exit code, metrics, duration, peak memory, limits; logs compared by SHA-256 with line endings normalized because the repository is checked out with `core.autocrlf`). `tests/test_run_stability.py` (5 cases); `tests/`: 588 passed, 9 skipped; ruff clean; `report_numbers.py --check` in sync.
- Findings in the numbers: `paper_003` (Pilot 3, memory re-run) and `paper_006` (Pilot 2, Pilot 3) have the same status, exit code, and metrics in every listed run (rmse 0.473 and loss 0.106; accuracy 0.8886 and auroc 0.892). The pairs were made at different commits of the tool, and the memory limit differs for `paper_003`; no different seeds. Synthetic control: Tier 2 0 before the fix and 100 after for the true claim, 0 for the false claim; two runs identical in status, exit code, metrics, and logs.
- Not verified: repeatability under a protocol with the tool commit and limits fixed (that is the next job); stability across seeds.

### 2026-10-16 21:04 +03:00: feat(pilot): --cpus for run_pilot.py (Issue #331)
- `scripts/run_pilot.py --cpus N` replaces the protocol's CPU limit (2) and writes `cpus_override` (requested, protocol value, and the note "not a protocol run") into the record; a non-positive value is a harness error. With `--pilot3` the other settings stay. `tests/test_pilot3.py`: 4 new cases (only the CPU limit changes, nothing changes without the option, non-positive values are refused, the command line passes it on). Ruff clean.
- Not verified: a real Docker run with `--cpus` (the next job of the plan).

### 2026-10-16 21:07 +03:00: docs(corpus): selection rules for six new papers (Issue #333)
- `docs/CORPUS_EXPANSION.md`, written and merged **before any candidate was listed or opened**: the pool (four GitHub repository searches, first 100 results each, stored unchanged with the date), the fixed order (SHA-256 of the lower-case `owner/name`), seven mechanical rules R1 to R7 (open Python repository, allowed license, a README run command whose script exists, no GPU or CUDA mention, size caps, an arXiv paper whose text has table captions and decimal numbers, not already in the corpus), the promise that whether a paper installs or runs is never considered, how a candidate that fails `scripts/verify_corpus.py` is replaced (the next in the order, before any run), and the limits (the pool is biased; the rate is for papers selected this way).
- The six papers will go to `data/corpus_expansion/papers.json`, not to `data/seed_papers.json`. `scripts/verify_corpus.py` already takes the corpus file as its argument, so no new option is needed.
- Not verified: nothing has been selected yet; the rules have not been applied.

### 2026-10-16 21:12 +03:00: feat(corpus): script for the corpus expansion selection (Issue #335)
- `scripts/corpus_expansion.py`: `pool` runs the four searches of `docs/CORPUS_EXPANSION.md` once and stores them with the date and the SHA-256 order (`data/corpus_expansion/pool.json`); `evaluate` applies R1 to R7 in that order, records the first failed rule of every candidate (`evaluation.json`), runs `scripts/verify_corpus.py`'s checks on a passing candidate (a failing one is eliminated and the next takes its place), and stops at six (`papers.json`, ids `paper_101` to `paper_106`, apart from the seed corpus).
- `tests/test_corpus_expansion.py` (28 cases, no network): the order, each rule rejecting and naming itself (including `python3` not counting as `python `, a missing script, GPU or CUDA in the README, a requirement file, or the run command, size caps, LFS, table captions and decimal numbers), R7, the selection loop, the elimination by the verifier, and a check that the queries, rule names and caps in the code occur in the document. `tests/`: 621 passed, 9 skipped; ruff clean.
- Not verified: the script has not been run against GitHub and arXiv yet (next step); the rules have not been applied.

### 2026-10-16 21:22 +03:00: fix(corpus): R7 checks the paper, command continuation lines, stages for a small pool (Issue #338)
- Applying `docs/CORPUS_EXPANSION.md` once (issue #337, before any run) showed: (1) the script checked only the repository in R7, and one candidate selected was the SAINT paper of `paper_006` (arXiv 2106.01342) in another repository, against the document; (2) a README command that continues with a backslash or ends with a comment was taken as a raw line; (3) the pool of the four searches (89 candidates) gave 3 papers (2 after the R7 fix), fewer than six, and the document had no rule for that.
- Fix: section 6 "Amendments" of the document (R7 means the paper too; continuation lines are joined and a trailing comment is not part of the command, neither changing any pass or fail of R3; stages 2 and 3 with eight queries fixed before they were run, used in order only while fewer than six papers have passed; if still short, Pilot 4 runs what passed and says so). The amendment says that it was written after stage 1's result was seen and before stages 2 and 3 were retrieved. Script: R7 compares arXiv ids, `STAGES`, `pool --stage N`, stage recorded in the evaluation. The first output is kept in `data/corpus_expansion/first_attempt/`; the stage 1 pool is stored as `data/corpus_expansion/pool.json` (retrieved 2026-10-16T18:15:36Z, 89 candidates: 44, 1, 5, and 45 results of the four searches before de-duplication).
- `tests/test_corpus_expansion.py`: 34 cases (6 new). `tests/`: green; ruff clean.
- Not verified: stages 2 and 3 have not been retrieved; the evaluation with the fixed script has not been repeated yet (next step).

### 2026-10-16 21:34 +03:00: fix(corpus): R3 skips install commands; stage 2 pool stored (Issue #340)
- Stages 1 and 2 were evaluated with the fixed script (stage 2 retrieved once, 234 new candidates, stored unchanged as `data/corpus_expansion/pool_stage2.json`): 137 candidates evaluated, 6 selected (2 from stage 1, 4 from stage 2). Two of the six had `python setup.py install` as their first README line, which installs a package and runs no experiment; the first lines of two others are a documentation style checker and a data preparation step.
- Amendment 4 of `docs/CORPUS_EXPANSION.md` (written after that result was seen, and saying so): a line whose script is `setup.py` is an install command and is skipped; nothing else changes (the docs checker and the data preparation are what the README says to run). `scripts/corpus_expansion.py` and one test follow. The output before this amendment is kept in `data/corpus_expansion/first_attempt/`. The evaluation will be repeated on the stored pools in the next PR (stage 3 only if fewer than six pass).
- `tests/`: green; ruff clean. Not verified: how many papers pass after the amendment.

### 2026-10-16 21:46 +03:00: data(corpus): the six selected papers and the reasons (Issue #342)
- Applied `docs/CORPUS_EXPANSION.md` after amendments 1 to 4 on the stored pools (stage 1: 89 candidates; stage 2: 234 more; stage 3 not needed): **263 candidates evaluated in the hash order, 6 selected** (2 from stage 1, 4 from stage 2), all 6 pass `scripts/verify_corpus.py data/corpus_expansion/papers.json`. Stored: `evaluation.json` (first failed rule of every candidate), `papers.json` (`paper_101` to `paper_106`), `verify_corpus.json`. The earlier outputs stay in `first_attempt/`.
- Rejections by first failed rule: stage 1: R1 3, R2 26, R3 45, R4 11, R6 1, R7 1; stage 2: R1 10, R2 64, R3 83, R4 10, R6 3 (table in section 7 of the document, generated by `scripts/corpus_selection_doc.py`; `tests/test_corpus_selection_doc.py`, 4 cases).
- The selected set, as the rules gave it: `lairnet` (run command: `python docs/check_styles.py`), `gmr-imbalanced-learning` (`python code/examples/quick_start.py`), `distinction-maximization-loss` (`python example.py`), `Legal-Contract-Classification` (`python src/prepare_data.py`), `GRACE` (`python train.py --dataset Cora`), `facies_classification_benchmark` (`python patch_train.py --batch_size 32 --aug True`). The scope drifted from tabular data (graph learning, legal text, geoscience), and some first README lines are not the paper's main experiment; both are stated in section 7.
- `tests/`: green; ruff clean. Not verified: whether any of the six installs or runs (not looked at, by design).

### 2026-10-16 21:49 +03:00: docs(pilot): Pilot 4 protocol for six new papers (Issue #344)
- `docs/PILOT_4.md`, written and merged **before any of the six papers (`paper_101` to `paper_106`) is installed or run**: Tier 1 only (no claim extraction, no scoring, no metrics); fixed settings (the README command as written, Python 3.11 image, no network, 2 CPUs, 50% of the host's RAM as memory and swap with the resolved size recorded, 3600 s install and 14400 s run phase, read-only repository, no data cache); the definitions of Pilot 1 (`docs/PILOT_WEEK2.md` section 5) with the denominator always 6; **at most one correction round** after a first attempt that ends in an error (allowed changes only for the cause in the first attempt's logs: extra requirements or constraints, another Python image, working directory or writable copy, environment variables, data fetched from a URL named in the README or paper up to 2 GB; forbidden: editing the paper, wrappers, changing the limits, a second round), every change recorded in `correction.json` with the log line that motivated it; both the strict (first attempt) and the corrected rates reported; no paper dropped or replaced because it fails; one pull request per paper; side-by-side tabulation of Pilots 1 to 4 afterwards; known limits.
- Not verified: nothing has been run; the tool does not yet run papers from `data/corpus_expansion/papers.json` (a following PR adds that mode).

### 2026-10-16 21:53 +03:00: feat(pilot): Pilot 4 run mode (Issue #346)
- `scripts/run_pilot.py --pilot4 <paper_id>` runs a paper of `data/corpus_expansion/papers.json` as `docs/PILOT_4.md` specifies: the README command as written (`python <script> <arguments>`, an interpreter option before the script is a harness error), derived run setup with the read-only repository and no data, Python 3.11, 2 CPUs, memory and swap 50% of the host's RAM (resolved size in `memory_override`), 3600 s install and 14400 s run phase, record in `data/pilot4_runs/<paper_id>/` with `pilot4` (command, attempt, correction). `--correction FILE` is the one correction round: only the allowed keys (extra requirements, constraints with a source, Python version 3.8/3.9/3.11, working directory, writable repository, environment, data) and every change with the first attempt's log line; limits, command and CPUs cannot be changed. `--corpus FILE` selects another corpus file.
- `scripts/categorize_pilot_failures.py` and `scripts/pilot_measurements.py` take `--corpus` (the paper list; the protocol label `docs/PILOT_4.md` for a `pilot4` directory).
- `tests/test_pilot4.py` (17 cases): the fixed settings, the correction applied and refused outside the protocol, all six corpus commands, the command line, the tools' paper list, and code against protocol text. `tests/`: green; ruff clean.
- Not verified: a real Docker run of a Pilot 4 paper (the next step). The data fetch of a correction round with `scripts/fetch_data.py` reads the seed corpus; it will be adapted if a paper needs it.

### 2026-10-16 21:56 +03:00: test(pilot): paper_006 with 8 CPUs (Issue #348)
- Command: `python scripts/run_pilot.py paper_006 --pilot3 --memory 50% --cpus 8 --record-root data/cpu_runs`. Record: `data/cpu_runs/paper_006/` (unchanged files). **Not a protocol run:** 8 CPUs instead of 2 and a memory limit of 14265m instead of 6g; every other setting is Pilot 3's. The record says so in `cpus_override` and `memory_override`.
- Result: COMPLETED, exit code 0. Run phase **1119.8 s**; install and run in the sandbox 1711.1 s; peak memory 687140864 bytes (about 0.64 GiB).
- Side by side (same paper settings, 2 CPUs): Pilot 2: run phase 3122.7 s, sandbox total 3688.7 s, peak 696434688 bytes; Pilot 3: run phase 3435.4 s, sandbox total 4065.4 s, peak 694714368 bytes. The run phase was **2002.8 s shorter than Pilot 2's (2.79 times faster) and 2315.5 s shorter than Pilot 3's (3.07 times faster)**; the sandbox total (bundling, install and run) was 2.16 and 2.38 times faster. The final metrics stored in `run_report.json` are the same in all three runs (accuracy 0.8886, auroc 0.892).
- So 4 times the CPUs gave about 3 times a shorter run phase for this paper; the bundling step (host-side download in the image, 197 s, 207 s and 227 s) did not get shorter.
- Not verified: that CPUs alone caused the difference (the tool commit, the memory limit and other work on the machine differ between the runs; short test and CI jobs ran on the machine during the CPU run); a repeat of the CPU run; the effect for other papers.

### 2026-10-16 22:04 +03:00: feat(pilot): Pilot 4 report script (Issue #351)
- `scripts/pilot4_report.py` writes `data/pilot4_runs/summary.json` and `summary.md` from the stored Pilot 4 records: the three rates of `docs/PILOT_4.md` section 5 over the 6 papers for the **first attempt** (read from `first_attempts/<paper_id>_attempt1/`, or from the final record when there was no correction round) and **after the correction round**, the failure categories of both (`scripts/categorize_pilot_failures.py`), a per-paper table with the README command and every correction, and Pilots 1 to 4 side by side from the stored `measurements.json` of each. `--check` fails if the stored summary is out of date. A paper without a record counts in the denominator.
- `tests/test_pilot4_report.py` (5 cases on synthetic records, including that the first-attempt directory is not modified). Ruff clean.
- Not verified: it has not been run on real Pilot 4 records (none exist yet).

### 2026-10-16 22:07 +03:00: test(pilot): paper_003 with 8 CPUs (Issue #353)
- Command: `python scripts/run_pilot.py paper_003 --pilot3 --memory 50% --cpus 8 --record-root data/cpu_runs`. Record: `data/cpu_runs/paper_003/` (unchanged files). **Not a protocol run:** 8 CPUs instead of 2 and a memory limit of 14265m instead of 6g; every other setting is Pilot 3's (recorded in `cpus_override` and `memory_override`).
- Result: COMPLETED, exit code 0. Run phase **465.8 s**; install and run in the sandbox 1514.0 s; peak memory 1233285120 bytes (about 1.15 GiB).
- Side by side (same paper settings, 2 CPUs): Pilot 3: run phase 1516.7 s, sandbox total 2635.4 s, peak 1190248448 bytes; memory re-run (14265m): run phase 1497.4 s, sandbox total 2563.2 s, peak 1165963264 bytes. The run phase was **1050.9 s shorter than Pilot 3's (3.26 times faster) and 1031.7 s shorter than the memory re-run's (3.21 times faster)**; the sandbox total was 1.74 and 1.69 times faster. The final metrics in `run_report.json` are the same in all three runs (loss 0.106, rmse 0.473). The bundling step (50 to 56 s) did not get shorter.
- Together with `paper_006` (#348): 4 times the CPUs gave a run phase about 3.2 times (`paper_003`) and 3.1 times (`paper_006`) shorter, with the same status, exit code and metrics.
- `docs/report/REPORT.md`: the stability block is regenerated (the new run is in the table).
- Not verified: that CPUs alone caused the difference (the tool commit differs, and short test and CI jobs and the corpus evaluation ran on the machine during this run); a repeat of the CPU run; other papers.

### 2026-10-16 22:11 +03:00: docs: CPU runs of paper_003 and paper_006 (Issue #350)
- `docs/CPU_RUNS.md`: how the two 8-CPU runs were made, why they are not protocol runs, a generated table next to the same papers' 2-CPU runs (run phase, seconds saved, speed-up, install and run, same status and metrics), how to read it, and the limits. `scripts/run_stability.py` gets `cpu_effect`, `--write` and `--check` for the generated blocks (the stability document waits for the second runs); 3 new tests in `tests/test_run_stability.py`. `tests/`: 657 passed, 9 skipped; ruff clean.
- What the generated table says: with 8 CPUs instead of 2 the run phase was 2.79 to 3.26 times faster in the 4 comparisons (`paper_003`: 3.26 and 3.21 times, 1050.9 and 1031.7 s shorter; `paper_006`: 2.79 and 3.07 times, 2002.8 and 2315.5 s shorter); install and run together 1.69 to 2.38 times; status, exit code and metrics the same in all of them. Four times the CPUs gave less than four times the speed-up; the reason was not investigated.
- `docs/report/REPORT.md`: the sentence on the repeated runs now names both CPU runs.
- Not verified: that the CPUs alone caused the difference (tool commit, memory limit and other work on the machine differ); other papers; a repeat of a CPU run.

### 2026-10-16 22:47 +03:00: test(pilot): paper_003 second run, 50% memory, 2 CPUs (Issue #356)
- Command: `python scripts/run_pilot.py paper_003 --pilot3 --memory 50% --record-root data/_tmp_second_runs`, the record moved unchanged to `data/memory_runs/paper_003_run2/` (the first memory run `data/memory_runs/paper_003/` is untouched). Same settings as the first memory run: Pilot 3's, memory 14265m, 2 CPUs. Not a protocol run (memory limit).
- Result: COMPLETED, exit code 0, run phase 1390.6 s, peak memory 1103171584 bytes. Metrics in `run_report.json`: loss 0.106, rmse 0.473, **the same in all four runs** of the paper (Pilot 3, first memory run, this run, the 8-CPU run). `stdout.log` of this run equals Pilot 3's line by line once the epoch clock times and the line endings are ignored (0 differing lines). Tool commits differ (`602a322`, `7bd86cc`, `f9b909c`, `a189063`).
- Hash comparison (`scripts/hash_run.py --compare`, output in `data/memory_runs/hash_compare_paper_003_run2.txt`): against Pilot 3 and against the first memory run, 0 of 3 log files and 0 of 4 metadata files byte-identical (clock times, durations and paths differ, as before), no paper output files; so no run is byte-identical to another, while status, exit code and metrics are.
- `scripts/memory_runs.py` only takes the first memory run of a seed paper (a folder such as `paper_003_run2` caused an error in the report block); a test covers it. `docs/CPU_RUNS.md` and the report's stability block are regenerated (the new run is a further 2-CPU reference).
- Not verified: stability across seeds (the code's seed use was not examined); the variation of the run time (1497.4 s and 1390.6 s with the same limits, 1516.7 s in Pilot 3 with 6g).

### 2026-10-16 23:56 +03:00: test(pilot): paper_006 second run and docs/STABILITY_RUNS.md (Issue #358)
- Command: `python scripts/run_pilot.py paper_006 --pilot3 --memory 50% --record-root data/_tmp_second_runs`, the record moved unchanged to `data/memory_runs/paper_006_run2/` (the first run of this kind, a `cli.py score` run of 2026-10-15, was never stored in the repository). Pilot 3 settings, memory 14265m, 2 CPUs; not a protocol run (memory limit).
- Result: COMPLETED, exit code 0, run phase 3268.9 s, peak memory 695590912 bytes; metrics accuracy 0.8886 and auroc 0.892, **the same as Pilot 2, Pilot 3 and the 8-CPU run**; `stdout.log` equals Pilot 3's line by line (0 differing lines after ignoring line endings). Pilot 2 and Pilot 3 (same limits, different tool commits) took 3122.7 s and 3435.4 s.
- `scripts/hash_run.py --compare` against Pilot 2 and Pilot 3 (`data/memory_runs/hash_compare_paper_006_run2.txt`): no paper output files, 0 of 4 metadata files byte-identical, 1 of 4 or 5 log files byte-identical (`stdout.log` differs only by the line endings of the checked-out copy).
- `docs/STABILITY_RUNS.md`: the runs of `paper_003` (4) and `paper_006` (4) side by side from a generated table, the byte comparison, and what it shows: the same exit code and metrics in every run, run times that vary (up to about 107 s for `paper_003` and 313 s for `paper_006` with the same limits), and that this is not the stability tier of the score (no different seeds; the code's seed use was not examined). `tests/test_run_stability.py` checks the document block and that the stored second runs agree with the earlier runs. The report's stability block is regenerated.
- Not verified: seed behaviour; stability on other papers or machines.

### 2026-10-17 00:00 +03:00: feat(pilot): categorize one paper into its own folder (Issue #360)
- `scripts/categorize_pilot_failures.py --runs-dir <dir> --paper <id>` writes `failure_category.json` into that paper's run folder and prints it (the file for the whole directory is not written). It is for Pilot 4, where each paper's pull request holds its record and its category (`docs/PILOT_4.md` section 7). `tests/test_pilot_compare.py`: one new case. Ruff clean.

### 2026-10-17 00:05 +03:00: test(pilot4): paper_101 first attempt (Issue #362)
- `python scripts/run_pilot.py paper_101 --pilot4`; record and `failure_category.json` in `data/pilot4_runs/paper_101/` (unchanged files). Paper: LAIR-Net (`yuvrajiro/lairnet`, commit af5d5e1, matches the pin). README command, as written: `python docs/check_styles.py` (a documentation style checker; the first `python` line of the README, see `docs/CORPUS_EXPANSION.md` section 7).
- Result: **COMPLETED, exit code 0**, run phase 1.0 s, peak memory 26738688 bytes. The repository has no requirements file, so the bundling was SKIPPED and the install status is `SKIPPED`. Last output line: `all 21 classes styled`.
- By the definitions of `docs/PILOT_4.md` section 5: **not a pilot success** (install SKIPPED is not install success) and category `RAN_WITHOUT_INSTALLED_DEPENDENCIES`; run success yes. No correction round (the first attempt ended without an error). Strict and final result are the same.
- What it does not show: the command is a docs checker, so this run says nothing about the paper's model (LAIR-Net) running.
- Not verified: whether the paper's own experiment runs.

### 2026-10-17 00:09 +03:00: test(pilot4): paper_102 first attempt (Issue #364)
- `python scripts/run_pilot.py paper_102 --pilot4`; record and `failure_category.json` in `data/pilot4_runs/paper_102/` (unchanged files). Paper: Geometric Manifold Rectification for Imbalanced Learning (`wangxb96/gmr-imbalanced-learning`, matches the pin). README command, as written: `python code/examples/quick_start.py`.
- Result: **COMPLETED, exit code 0**; the repository's `requirements.txt` was bundled (10 wheels, 18.4 s) and the install status is **INSTALLED**; run phase 12.7 s, install and run in the sandbox 362.0 s, peak memory 175353856 bytes. The script printed `Baseline AUPRC: 0.7131` and `GMR AUPRC: 0.7461` (the program's output, not compared with the paper and not scored).
- By the definitions of `docs/PILOT_4.md` section 5: **pilot success** (install success and run success). No failure category. No correction round was needed. Strict and final result are the same.
- Not verified: that the printed numbers match the paper (out of scope for Pilot 4).

### 2026-10-17 03:03 +03:00: feat(sandbox): installed-environment cache, paper_003 run twice (Issue #380)
- `src/sandbox/env_cache.py`, `SandboxConfig.env_cache_dir`, `run_pilot.py --env-cache DIR`: the output of the install phase is stored per key (image ID, SHA-256 of every bundled wheel, requirement files, extras, mode); a second run verifies the SHA-256 digest of the stored tree, skips the install container and mounts the stored directory read-only. Only an install that ended INSTALLED is stored. Off by default; the record gets `env_cache` and says it is not a protocol run. Reasoning and safety: `docs/DECISIONS.md` D-010. The pip download cache already existed (`.pip-cache` in the staging directory, 9.3 GB) and is unchanged.
- Measured (`docs/ENV_CACHE_RUNS.md`, `scripts/env_cache_runs.py`, `data/env_cache_runs/`): `paper_003`, Pilot 3 settings, 50% memory, 2 CPUs. Install phase 179 s on the hit against 1,055 s and 1,000 s without the cache; whole run 1,549 s against 2,660 s and 2,455 s. 177 s of the hit went into verifying the 5 GB environment. The first run with the cache is slower (268 s to store). Same status, exit code and metrics (`loss` 0.106, `rmse` 0.473) in all four runs.
- No gain is claimed for the run phase (its spread between repeated runs is 107 s). Not measured: other papers, memory pressure, disk use of many environments. The first cached run overlapped with tests and downloads on the machine. 16 new tests (`test_env_cache.py`, `test_env_cache_runs.py`); local: ruff clean, 673 passed, 9 skipped.
### 2026-10-17 02:03 +03:00: docs(validation): rules for choosing ReScience C articles, written before any is opened (Issue #383)
- `docs/EXTERNAL_VALIDATION.md`: the pool (top-level directories of `ReScience/articles`, ordered by the SHA-256 of the directory name), rules E1 to E8 (accepted and reviewed, Python, GitHub code repository with a pinned commit, a README `python` command, no GPU, size at most 100 MB and an allowed license, article tables with numbers, new), at most eight articles, the run protocol (`docs/PILOT_4.md` with 8 CPUs, 50% memory, 14400 s run phase), how claims are taken (three passes, auto-consensus candidates only, scored with `--claims auto-consensus`), and what counts as agreement (Verified or Partially Verified agrees; Needs Review with nothing compared is inconclusive; the rest disagrees).
- What was looked at before writing: the 72 directory names, the three file names in one directory, and the field names (not values) of one `article.yaml`. No article, repository or review was opened.
- Stated limits: every article is expected to be reproducible, so the comparison shows false alarms only and is not a measure of accuracy; the reference is publication, not a re-check.

### 2026-10-17 02:06 +03:00: feat(corpus): selection script for ReScience C articles (Issue #385)
- `scripts/external_validation.py pool|evaluate` applies rules E1 to E8 of `docs/EXTERNAL_VALIDATION.md` in the SHA-256 order of the article directory names of `ReScience/articles`, pins the code commit (the `/tree/<ref>` or tag of the code URL, else the default branch head), eliminates a selected article that fails the repository, license, script or title check, and writes `pool.json`, `evaluation.json` and `papers.json` (ids from `paper_201`). It needs `GITHUB_TOKEN`/`GH_TOKEN` in the environment for read-only calls. Not run yet when this entry was written.
- 24 tests with a fake fetcher (every rule, the pinned ref, the order, elimination, the entries). Local: ruff clean.

### 2026-10-17 02:34 +03:00: test(validation): ReScience C selection gives 0 of 65 articles (Issue #385)
- Ran `scripts/external_validation.py pool` and `evaluate` (pool of 65 article directories of `ReScience/articles`). Three evaluations: (1) 0 of 65, a script defect (the `review`, `code` and `dates` fields are lists of one-key mappings); (2) 0 of 65 with the defect fixed (E2 23, E3 27, E4 9, E1 5, E6 1; 14 articles name a release tag that does not exist); (3) 0 of 65 after amendment 3 (a missing ref falls back to the default branch head): E4 25, E2 23, E3 11, E1 5, E6 1. All outputs are stored (`first_attempt/`, `second_attempt/`, `evaluation.json`).
- **No article passed**, so the runs, claim extraction, scoring and the agreement table were not done. The bottleneck is E4: 25 Python/GitHub articles have no README `python <script>.py` line. The rules were not widened a fourth time; a different command rule (`python -m`, `make`, notebooks) is a decision for the owner. Amendments are in section 9 and the result in section 10 of `docs/EXTERNAL_VALIDATION.md`, marked as written after results were seen.
- Not verified: whether those 25 articles would run with another command. Local: ruff clean, 683 passed, 11 skipped.
### 2026-10-17 02:00 +03:00: feat(ai): auto-consensus candidates from three independent passes (Issue #381)
- `scripts/auto_extract.py` starts three fresh `claude -p` passes per paper in blind packets outside the repository (tools Read, Write, Edit, Glob, Grep only; permission mode `dontAsk`), checks each answer (schema, page, quote on the page), and makes a claim a **candidate** when at least two passes give the same normalized value. Candidates are stored (`import`) as `pending` with `verified_by = auto-consensus`; migration 7 and `data/schema.sql` allow the value, the existing CHECK still refuses `accepted` without `human`. `cli.py score --claims auto-consensus` is the only way a score uses candidates and it labels the score. No claim was accepted and nothing was imported into the project database.
- Measured on the 18 gold questions (`data/auto_extract/gold18/`, `docs/AUTO_CONSENSUS.md`): consensus decided 18 of 18, precision 0.833, recall 0.833 as printed (10 TP, 2 FP, 2 FN, 6 TN); single passes 0.833 to 0.917. Two differences: `paper_003:xgboost_rmse` (same number, spread left out by two passes) and `paper_004:tabr_average_rank` (all three passes took the default-hyperparameters row `1.3± 0.6`, the gold set has `1.3± 0.9`: agreement does not protect against a systematic misreading). No threshold set.
- Not verified: variation between repeated runs (one run of three passes), open-ended extraction, passes with a different model. Local checks: ruff clean, 675 passed, 11 skipped (the worktree has no PDFs).
### 2026-10-17 01:44 +03:00: feat(devops): preflight check before real runs (Issue #378)
- `scripts/preflight.py` checks Docker (starts Docker Desktop and waits up to 240 s if it does not answer), free disk (FAIL under 10 GiB, WARN under 30), available memory (FAIL under 2 GiB, WARN under 8), the sleep setting of the power plan (WARN if the machine sleeps on mains power), what Docker sees (FAIL under 2 CPUs or 4 GiB), and a real hello-world container of the sandbox image (no network, read-only root, all capabilities dropped). `run_pilot.py` (before a run) and `cli.py score` (real run, not `--from-run`) call `ensure_ready()`; `REPRO_RADAR_SKIP_PREFLIGHT=1` skips it and says so. `tests/conftest.py` sets that variable for the tests.
- Evidence: `python scripts/preflight.py` on this machine printed six PASS lines (330.7 GiB free, 15.2 GiB available, no sleep on mains, Docker sees 12 CPUs and 15.5 GiB, hello-world container ran). 12 new tests in `tests/test_preflight.py`; full suite 676 passed, 9 skipped; ruff clean.
- Not verified: the path that starts Docker Desktop was tested with mocks only (Docker was already running); the thresholds are my choices, not measured limits.
### 2026-10-17 00:13 +03:00: test(pilot4): paper_103 first attempt (Issue #366)
- `python scripts/run_pilot.py paper_103 --pilot4`; record and `failure_category.json` in `data/pilot4_runs/paper_103/` (unchanged files). Paper: Distinction Maximization Loss (`dlmacedo/distinction-maximization-loss`, matches the pin). README command, as written: `python example.py`.
- Result: the bundling of the repository's `requirements.txt` was **PARTIAL** (12 wheels, 98.0 s): the host-side resolution stopped with `ERROR: Could not find a version that satisfies the requirement visdom (from torchnet) (from versions: none)` / `ERROR: No matching distribution found for visdom` (`bundle.stderr` in the record). In the sandbox the install phase therefore **FAILED** (`install.log` line 15: `ERROR: Could not find a version that satisfies the requirement filelock (from torch) (from versions: none)`, which is the offline install missing a wheel the partial bundle did not collect), and the run ended with **exit code 1** (`ModuleNotFoundError: No module named 'torch'`), 0.6 s.
- By the definitions of `docs/PILOT_4.md` section 5: **no install success, no run success, no pilot success**. Category (`scripts/categorize_pilot_failures.py`): `MISSING_DEPENDENCY` in the install phase; the deciding line is the `filelock` line above, and the cause visible in the record is the `visdom` requirement of `torchnet`.
- **No correction round was made.** The first attempt ended in an error, so the paper had the right to one round, but the cause in the logs (`visdom`, a requirement of `torchnet` that PyPI offers only as a source archive, and no binary wheel) cannot be changed by any change that section 4 of the protocol allows (extra requirements and constraints are pip requirements that must be binary wheels; building from source is not among the allowed changes; a Python image does not change the availability of a source-only package). I checked on PyPI that `torchnet` 0.0.2 requires `visdom`, 0.0.4 has only a source archive, and `visdom` has only source archives. Strict and final result are the same.
- Not verified: that a build from source would make the paper install (not allowed by the protocol, so not tried); whether the example runs.

### 2026-10-17 00:14 +03:00: test(pilot4): paper_104 first attempt (Issue #368)
- `python scripts/run_pilot.py paper_104 --pilot4`; record and `failure_category.json` in `data/pilot4_runs/paper_104/` (unchanged files). Paper: CUAD (`10div10/Legal-Contract-Classification`, matches the pin). README command, as written: `python src/prepare_data.py` (a data preparation step).
- Result: the `requirements.txt` was bundled (26 wheels, 67.5 s) and the install status is **INSTALLED**; the run ended with **exit code 1** after 6.0 s (peak memory 75247616 bytes). Output: `Downloading CUAD master clauses CSV...`, then `requests.exceptions.ConnectionError: HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /datasets/theatticusproject/cuad/raw/main/CUAD_v1/master_clauses.csv (Caused by NameResolutionError(...Failed to resolve 'huggingface.co' ([Errno -3] Temporary failure in name resolution)`. The sandbox has no network by design.
- By the definitions of `docs/PILOT_4.md` section 5: **install success yes, run success no, no pilot success**. Category: `DATA_NOT_ACCESSIBLE` in the run phase (`stderr.log` line 70).
- **No correction round was made.** The cause is a download, and section 4 allows fetching data on the host from a URL and mounting it, but a mount needs the path where the code expects the file, and the first attempt's logs show only the call `download_csv(raw_path)` (`stderr.log`: `File "/workspace/repo/src/prepare_data.py", line 103, in main`), not the value of `raw_path`. The protocol forbids choosing a change after looking at anything other than the first attempt's logs, and I did not read the paper's code. Strict and final result are the same.
- Not verified: whether mounting the file would make the step run; the paper's own experiment.

### 2026-10-17 00:15 +03:00: test(pilot4): paper_105 first attempt (Issue #370)
- `python scripts/run_pilot.py paper_105 --pilot4`; record and `failure_category.json` in `data/pilot4_runs/paper_105/` (unchanged files). Paper: Deep Graph Contrastive Representation Learning (`CRIPAC-DIG/GRACE`, matches the pin). README command, as written: `python train.py --dataset Cora`.
- Result: the bundling of the repository's `requirements.txt` was **PARTIAL** (4 wheels, 31.0 s): `torch-scatter`, `torch-sparse`, `torch-cluster`, `torch-spline` and `sklearn` are reported as `NEEDS_SDIST_BUILD` (`bundle.needs_sdist_build`: `ERROR: No matching distribution found for torch-scatter` and the same for the others). In the sandbox the install phase **FAILED** (`install.log` line 3: `ERROR: Could not find a version that satisfies the requirement torch-scatter (from versions: none)`), and the run ended with **exit code 1** after 0.7 s (`ModuleNotFoundError: No module named 'yaml'`).
- By the definitions of `docs/PILOT_4.md` section 5: **no install success, no run success, no pilot success**. Category: `MISSING_DEPENDENCY` in the install phase (deciding line: the `torch-scatter` line above).
- **No correction round was made.** The cause in the logs is five requirements that have no binary wheel on the index (they are source archives, or wheels hosted elsewhere). Section 4 allows only binary-wheel requirements and constraints, a Python image, paths, environment, and data; none of them provides these packages. Strict and final result are the same.
- Not verified: whether building them from source (not allowed by the protocol) would work; whether the training script runs.

### 2026-10-17 00:17 +03:00: fix(sandbox): bundle the extra requirements when there is no requirements file (Issue #372)
- Found in Pilot 4 (`paper_106`): the correction round's extra requirement `torch` was not installed, because `RepoStager.bundle_dependencies` returned `SKIPPED` ("No requirements.txt found to bundle") for a repository without requirements and ignored `extra_requirements`; the container entrypoint can install them (`SANDBOX_EXTRA_REQUIREMENTS`). The corrected run failed again with the same `ModuleNotFoundError: No module named 'torch'`. This is a defect of the tool, not a result about the paper.
- Fix: with no requirements file and no conda environment file but extra requirements, they are downloaded with their dependencies (`source: extra_requirements`, status `SUCCESS` or `PARTIAL` with `extra_requirements_error`); with neither, still `SKIPPED`. `tests/test_stager_edges.py`: 3 new cases. Section 8 of `docs/PILOT_4.md` allows this fix and a re-run that does not use up the correction round; the first output is kept (`data/pilot4_runs/first_attempts/paper_106_attempt2_tool_defect/`, in the data PR of `paper_106`).
- `tests/`: green; ruff clean. Not verified: the corrected run itself (running now).

### 2026-10-17 00:30 +03:00: test(pilot4): paper_106 first attempt and correction round (Issue #374)
- Paper: A Machine Learning Benchmark for Facies Classification (`yalaudah/facies_classification_benchmark`, matches the pin). README command, as written: `python patch_train.py --batch_size 32 --aug True`. The repository has no requirements file.
- **First attempt** (`data/pilot4_runs/first_attempts/paper_106_attempt1/`): bundling SKIPPED, install `SKIPPED`, **exit code 1** after 1.1 s: `ModuleNotFoundError: No module named 'torch'` (`stderr.log` line 4). Category `MISSING_DEPENDENCY` (run). Strict result: no install success, no run success, no pilot success.
- **Correction round** (one, allowed by section 4): `correction.json` has one change, the extra requirement `torch`, motivated by that log line. The first correction run (`first_attempts/paper_106_attempt2_tool_defect/`) hit a defect of the tool: extra requirements were ignored without a requirements file (fixed in #372, PR #373); by section 8 it was re-run and the correction round was not used up. The run was made with the fix in the working tree (the record's `repro_radar_commit` is the commit before the fix; the fix is commit e6b6378).
- **Corrected result** (`data/pilot4_runs/paper_106/`): bundling of the extra requirement SUCCESS (29 wheels, 79.8 s), install **INSTALLED**, run **exit code 1** after 24.6 s (peak memory 910131200 bytes): `ModuleNotFoundError: No module named 'tensorboardX'` (`patch_train.py`, line 11). Category `MISSING_DEPENDENCY` (run). So the correction fixed the first missing module and exposed the next; the protocol allows one round, so the result stands: install success yes, run success no, **no pilot success** after the correction round.
- Not verified: whether the paper would run with further missing modules added (not allowed by the protocol).

### 2026-10-17 00:32 +03:00: docs(report): Pilot 4 results, four pilots side by side (Issue #376)
- `scripts/pilot4_report.py` run on the six records: `data/pilot4_runs/summary.json` and `summary.md`. **Rates over 6 (README command as written): first attempt: install 2/6, run 2/6, pilot success 1/6; after the correction round: install 3/6, run 2/6, pilot success 1/6** (Pilot 1: 1/6, 0/6, 0/6; Pilot 2: 6/6, 1/6, 1/6; Pilot 3: 6/6, 2/6, 2/6; different papers and limits, and Pilots 2 and 3 ran hand-written setups).
- Per paper: `paper_102` pilot success; `paper_101` ran without installed dependencies (a docs checker); `paper_104` install INSTALLED and a download failed (DATA_NOT_ACCESSIBLE); `paper_103`, `paper_105` install FAILED (requirements without a binary wheel), `paper_106` failed with `torch` and then `tensorboardX` missing even after the correction round. Categories: MISSING_DEPENDENCY 3, DATA_NOT_ACCESSIBLE 1 (first attempt and after the round).
- `docs/report/REPORT.md`: section 6.5 "Pilot 4: six papers the tool had not seen" with a generated block (`report_numbers.py` block `pilot4`, read from `data/pilot4_runs/summary.md`), a short paragraph that says what the table shows and its limits, and a limitation bullet. `tests/test_pilot4_report.py` checks that the stored summary is in sync with the records; `tests/`: 664 passed, 9 skipped; ruff clean.
- Not verified: anything about claims or scores (Pilot 4 is Tier 1 only); CI could not start (billing), so this pull request is not merged.
