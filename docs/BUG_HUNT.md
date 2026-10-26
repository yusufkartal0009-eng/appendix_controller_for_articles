# Bug hunt of 2026-10-24 (issue #447)

A read of the code of the last weeks, looking for real defects. Rule of the hunt: a finding counts only when a test that fails
on the old code was written first; proven findings are fixed in one small pull request each (at most five); everything else is
listed below as **suspected, not proven** and is not changed.

**Read:** `src/diagnosis/` (classifier, schema, report, compare), `src/claim_store.py` (`restore_decisions`), `src/multi_seed.py` and
`scripts/run_multi_seed.py`, `scripts/demo_set.py`, `scripts/field_analysis.py`, `scripts/candidates_build.py`,
`scripts/candidate_runs.py`, `cli.py` (`score`, `diagnose`), `src/scoring.py`, `src/score_run.py`, `src/web/routes.py`,
`src/sandbox/resources.py`, `src/quote_guard.py`. Not every line of every file was traced; "no finding" is not "no bug".

## 1. Proven and fixed (3)

| # | Bug | Proof before the fix | Fix |
|---|---|---|---|
| 1 | `Tier2MetricsEvaluator` took any metric whose name contains the letters `ms` or `sec` as a time metric, so `rmse`, `num_params`, `n_items` lost the absolute allowance that other metrics between 0 and 1 get. | With claimed 0.5 and reproduced 0.54: `accuracy` matches (1.0 point), `rmse` and `num_params` give 0.5 point. | #448: `is_time_metric` (whole name parts for the short words), `tests/test_time_metric_names.py`. |
| 2 | `scripts/demo_set.py` looked a printed number up in the paper's text as a plain substring, so `1.5` matched inside `21.55`, `1.52` or `1.5.2`; the document calls it an exact string match. | The new test failed on the old code. For `demo_020` the number `1.5` was reported on PDF pages 23, 39, 40, 41 and is on 23, 39, 40. | #449: `pages_with_number`; a dated correction note in `docs/DEMO_SET.md` (the generated block was not regenerated). |
| 3 | `cli.py score` printed the tiers and the total with one decimal (round half to even): a stored 58.25 was printed as 58.2, 93.25 as 93.2, 91.75 as 91.8. | The new test failed on the old code. | #450: two decimals. |

No stored score, record or accepted claim changed. The tolerance probe (`docs/TOLERANCE_PROBE.md`) was regenerated after #448: for
`paper_003` the status now leaves Verified at -20 % / +20 % instead of -5 % / +10 %.

## 2. Suspected, not proven (first pass; see section 3 for the outcome of each)

Each of these was seen in the code or in an output and could not be turned into a failing test without deciding what the rule
should be. They are for the owner.

1. **The absolute allowance for values between 0 and 1 (Tier 2).** A claim between 0 and 1 matches when the absolute difference is at
   most 0.05, whatever the metric. For a small value that is a very wide band: in `docs/TOLERANCE_PROBE.md` the value 0.0167
   (`boundary_conflict`, `paper_102`) is still MATCHED with a claim moved by 20 %, and a reproduced 0.06 would match a claimed 0.0167
   (3.6 times as large). It is the implemented rule, not a coding error; whether it is wanted for losses and error measures is a decision.
2. **`src/quote_guard.py` `find_on_page` is a substring test** for `source_quote` and for `value_as_printed`, and the value is not
   required to lie inside the quote: a value `0.5` is found on a page that only prints `10.55`. The owner's review of every claim
   (W7) is the safeguard; it was not shown that this ever let a wrong claim through.
3. **`classify_exception` takes `data` anywhere in a missing path as a data file:** `No such file or directory: 'metadata_utils/config.yaml'`
   gives DATA_NOT_ACCESSIBLE (checked by hand). The rule is the one of `docs/PILOT_WEEK2.md` section 7, so it may be intended; no
   stored run is known to be misclassified by it.
4. **The dashboard can show a score and a "Latest run" of two different runs.** The score row of `paper_006` has no `run_id`, and
   the runs table holds only the Pilot 1 records, so after `cli.py score ... --from-run data/pilot3_runs/paper_006` the page of the
   paper shows 58.25 beside a FAILED Pilot 1 run (`docs/DEMO_SCRIPT.md` step 1).
5. **`cli.py score` never gives Tier 3 the multi-seed runs:** `score_run(...)` is called without `seed_metric_results`, so the Tier 3
   of a scored paper is the single-run baseline of 75.0 even where `data/multi_seed_runs/<paper>/` holds three seed runs (for
   `paper_006` the coefficient of variation is 0.28 % and 0.88 %, which the scorer would score 100). `docs/MULTI_SEED.md` describes
   the multi-seed script and its summary, not a link from `cli.py score`; whether the link is wanted is a decision.
6. **`candidates_build.py` reads the README of the head of the default branch,** also for the two candidates whose commit was supplied
   by the list, so "the README names the paper" may describe a newer README than the pinned commit. All 29 pass; no wrong answer is known.
7. **The K1 and pass rules read a text pattern** (a name, `:` or `=`, a decimal number): a setup value or a warning line can pass it
   (`demo_020` passed on `True post-break alpha: 1.5`). The protocols say so; it is listed here because the candidate protocol
   (`docs/CANDIDATE_RUNS.md`) uses the same pattern.

## 3. Second pass over the seven suspicions (2026-10-25, issue #498)

For each suspicion a failing test was tried first. A failing test is a real bug (fixed in a small pull request, at most five
fixes); a passing test would have disproved the suspicion; a suspicion whose fix is a decision about scoring semantics or
the interface was not touched. Result: **none was disproved**, three were real bugs and are fixed, four are left to the owner.

| # | Suspicion | Outcome | Evidence |
|---|---|---|---|
| 1 | Absolute allowance of 0.05 for values between 0 and 1 | **Owner decision.** It is the implemented rule; a test would only restate it. Not touched. | `docs/TOLERANCE_PROBE.md` |
| 2 | `quote_guard` finds a value as a substring | **Real bug, fixed in #499.** `0.5` was found inside `10.55`, `0.52` and `1.5.2`; the value must now be a whole number. The 36 stored answers give the same result as before. | three cases in `tests/test_quote_guard.py` failed on the old code |
| 3 | `classify_exception` takes `data` anywhere in a path | **Real bug, fixed in #500.** `metadata_utils/config.yaml`, `database.yml` and `src/metadata.py` were classified as missing data files; `data`/`dataset(s)` must now be a word of the path. | three cases in `tests/test_diagnosis_classifier.py` failed on the old code |
| 4 | The dashboard can show a score and the "Latest run" of two different runs | **Real; fixed in #513 (2026-10-27).** After `cli.py score --from-run` the score row had no `run_id` and the page showed another run beside it. Now `cli.py score` records the run it scored and stores its id in the score row; the page shows that run (heading "Run of this score") with a `Started` row, and falls back to the latest run when a score names none. No label rule, tolerance or list content changed. The `xfail` marker was removed; its last assertion looked for the word `FAILED`, which also occurs in the style sheet, so it now looks for the run's badge and id. | `tests/test_bug_hunt_suspicions.py` (passes) |
| 5 | `cli.py score` never gives Tier 3 the multi-seed runs | **Owner decision.** Whether the link is wanted changes what Tier 3 means for scored papers. Not touched. | - |
| 6 | `candidates_build.py` reads the README at the head of the default branch | **Real bug, fixed in #501.** The README is now requested at the pinned commit. The stored candidate records were not regenerated (they would need the network). | two cases in `tests/test_candidates.py` failed on the old code |
| 7 | K1 and pass rules read a text pattern | **Owner decision.** The pattern is defined by the protocols (`docs/CANDIDATE_RUNS.md`, `docs/AUTO_SEARCH_ROUND3.md`); changing it would change the stored pass counts. Not touched. | - |

Not verified: that bugs 2, 3 and 6 ever changed a stored result (none is known to have).
