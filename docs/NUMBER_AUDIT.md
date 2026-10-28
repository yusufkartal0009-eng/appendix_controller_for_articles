# Number audit (2026-10-28, issue #554)

Every numeric statement that is typed by hand in `docs/report/REPORT.md` (outside the generated `numbers:` blocks), `README.md`,
`docs/PAPER_STATUS.md` and `docs/PENDING.md` was extracted and checked against its source record. Numbers inside the generated
blocks are rendered from stored files by `scripts/report_numbers.py` (`--check` passes); in addition, the Wilson intervals were
recomputed independently (last section). "Section" refers to the report unless a file is named.

Method: read the four documents line by line, list each number, open the source (JSON file, script output, code constant, `git log`),
compare. A row is "yes" only if the source was opened; nothing here is marked verified from memory.

## Result in one line

Seven wrong or stale statements were found and corrected (rows marked **no** or **stale**); all other rows agree with their source.
After the fixes `python scripts/report_numbers.py --check` is in sync and `python scripts/verify_sources.py --check` lists no
unverified source; the test output is in the pull request.

## Table

| Claim | Location | Source | Correct? | Fix |
|---|---|---|---|---|
| Score weights 35 / 35 / 15 / 15 | REPORT 4.2, README table | `src/config.py` (TIER*_WEIGHT) | yes | none |
| Tolerance 5 %, absolute allowance 0.05 for a claim in [0, 1], half points within 2x | REPORT 4.2 | `src/config.py` DEFAULT_TOLERANCE; `src/scoring.py` lines 130-180 | yes | none |
| CV <= 2 % deterministic, <= 5 % stable | REPORT 4.2 | `src/scoring.py` (`cv <= 0.02`, `cv <= 0.05`) | yes | none |
| `Verified` is total >= 85, `Partially Verified` is 60-84 | REPORT 4.2 | `src/scoring.py`: Verified also needs Tier 1 >= 90 and Tier 2 >= 80; the 60+ band is not a 60-84 range | **stale** (incomplete; README already had the full rule) | Section 4.2 now states both extra conditions and the `Needs Review` case |
| Neutral Tier 2 baseline 70, single-run Tier 3 baseline 75 | REPORT 4.2, 6.11 | `src/scoring.py` ("neutral baseline applied (70.0)"); `data/real_verdicts/verdicts.json` (cli_tier2 70.0) | yes | none |
| Sandbox checks 1, 2, 3, 4, 6, 8, 9, 17, 18, 20 and uid 1000 | REPORT 4.1 | `docs/SANDBOX_ACCEPTANCE.md` table | yes | none |
| Checks "re-run in CI", "run in CI on every push", "passed in CI throughout" | REPORT 1, 4, 5.1, 6.1, 8; README; SANDBOX_ACCEPTANCE | `git log -- .github` (commit 6594f32 "remove the CI workflow", #388, D-010); `.github/workflows/` is empty | **stale** (present tense for a service that no longer exists) | Reworded to past tense with the removal noted; README file-tree comment fixed |
| "GitHub Actions runs the CI workflow on every pull request (seven jobs)" | CONTRIBUTING line 5 (contradicted line 69 of the same file) | same as above | **no** | Replaced by "There is no CI service (D-010)" |
| 6 papers, 18 -> 8 -> 6 corpus history | REPORT 5.1 | `docs/PROGRESS.md`, `docs/CORPUS_VERIFICATION.md` | yes | none |
| First 16 claims, only 2 found in their papers | REPORT 2 | `docs/CORPUS_VERIFICATION.md` summary line ("2 of 16") | yes | none |
| "0 of 3" claims found for one entry | REPORT 5.1 | `docs/CORPUS_VERIFICATION.md` rows of `paper_004`, `paper_005`, `paper_006` | yes | none |
| 6 of 6 entries pass `verify_corpus.py` | REPORT 5.1, README | `docs/CORPUS_VERIFICATION.md` (not re-run here: needs the network) | not re-run | none (the report says "as of the last recorded run") |
| 263 candidates evaluated, 6 selected (Pilot 4) | REPORT 6.5 | `docs/CORPUS_EXPANSION.md` line 131 | yes | none |
| Gold set: 18 questions, 6 papers, precision 1.0, recall 1.0, 12 found, 6 not found | REPORT 4.3, 6.2 | `data/claims/gold_score_pass_A.json` (tp 12, fp 0, fn 0, tn 6); `consistency.json` (18 of 18 agree) | yes | none |
| 13 accepted claims, 1 mapped, 12 without counterpart | REPORT 6.11, README | `data/claims/review_decisions.json` (accepted 13); `data/claim_metric_map.json` (map 1, no_counterpart 12) | yes | none |
| "12 claims ... in 5 of the 6 papers (`paper_005` has none)" | README, dataset bullet | `review_decisions.json` (13 accepted); the claim map has one claim for `paper_005`; REPORT 7 says so; README line 156 says 13 | **no** | README now says 13 claims in all 6 papers (`paper_005` has one, a follow-up question) |
| `paper_003`: 0.459 against 0.473, 3.05 % apart, Tier 2 100, total 97, `Verified` | REPORT 1, 6.11, README | `data/real_verdicts/verdicts.json` (rel_diff 0.0305, cli_total 97.0) | yes | none |
| `paper_006` total 86.5, `Needs Review`, Tier 2 70 | REPORT 7 | `verdicts.json` (cli_total 86.5) | yes | none |
| Tier 3 CV 0.70 % (rmse) and 7.4 % (loss) of `paper_003` | README | `data/multi_seed_runs/paper_003/multi_seed_summary.json` (0.00703, 0.07375) | yes | none |
| Memory limit 14265m in the memory re-runs and CPU runs; `paper_004` completed with it | REPORT 7 | `data/memory_runs/*/pilot_record.json`; `docs/MEMORY_RUNS.md` (COMPLETED, exit 0) | yes | none |
| `paper_004` peak 10.6 GiB, `paper_005` killed at 13.9 GiB | README | `docs/MEMORY_RUNS.md` table (10.64, 13.93) | yes | none |
| `paper_006` about 19 min on 8 CPUs; `paper_003` run phase about 25 min; whole run about 44 min cold, about 26 min warm; `paper_102` 12.7 s | README | stability block (1119.8 s); `docs/ENV_CACHE_RUNS.md` (run phase 1305-1497 s; whole run 2455-2839 s cold, 1549 s warm); `data/pilot4_runs/summary.md` (12.746 s) | yes (rounded) | none |
| Clone-to-`diagnose` 2,490 s | README, PENDING | `docs/evidence/clean_clone/WALKTHROUGH.md` line 67 | yes | none |
| Six images built in 43 to 90 s, 401 s in total | README, PENDING | `docs/ENVIRONMENT.md` table | yes | none |
| Images "0.6 to 1.1 GB each" | README requirements table | `docs/ENVIRONMENT.md`: 629 MB to 1.15 GB | **no** (largest image is 1.15 GB) | README now says 0.6 to 1.2 GB (629 MB to 1.15 GB) |
| Pilot 4: install 2/6 (3/6 after correction), run 2/6, pilot success 1/6; Pilot 3 2/6 | README, REPORT 6.5 | `data/pilot4_runs/summary.md` | yes | none |
| Automatic search round 3: 135 run, K1 2, K2 0, both 0 | README | `data/auto_search3/evaluation.json` | yes | none |
| Automatic search round 4: 107 run, K1 3, K2 v1 1, K2 v2 1, both 0; 2,648 checked | README, PENDING | `data/auto_search4/evaluation.json` | yes | none |
| Demo set: 22 run, 1 passed the run test | PENDING D6 | `data/demo_set/evaluation.json` (runs 22, k1_passed 1) | yes | none |
| Candidates: 14 selected, 13 run, 0 passed, Wilson 0.0 % to 21.5 % | PENDING D9, REPORT 6.8 | `data/candidates/runs/evaluation.json` (block); Wilson recomputed | yes | none |
| ReScience C: 65 evaluated, 0 selected | REPORT 7, PAPER_STATUS | `data/external_validation/evaluation.json` | yes | none |
| Related work: 9 of 9 sources verified | REPORT header | `docs/report/related_work_verification.json` (9 sources); `verify_sources.py --check` | yes | none |
| Round 4: 107 runs in `evaluation.json`, 105 folders | PAPER_STATUS 4 | `docs/PAPER_STATUS.md`, `docs/FAILURE_STATISTICS.md`; folders not re-counted here | not re-counted | none |
| Stability: 4 runs of `paper_003`, 4 of `paper_006`, identical metrics | README, REPORT 6.4 | generated block `stability` | yes | none |
| State of `main`: "1,210 tests passed" (dated 2026-10-25) in a document updated 2026-10-28 | PENDING line 6 | `pytest tests` on 2026-10-28: 1304 passed, 9 skipped | **stale** | Updated to 1,304 tests, 9 skipped, dated 2026-10-28 |
| Branch protection impossible "for this private repository" | PENDING section 3 (#3) | PENDING D1 and README: the repository is public | **stale** | Reworded: true while private; not retried because GitHub settings are not touched |
| Dates of the pilots (2026-09-30, 2026-10-10, 2026-10-13) and of the read-throughs | REPORT 6.1, 6.1a, header | headers of `docs/PILOT_WEEK2.md`, `docs/PILOT_2.md`, `docs/PILOT_3.md`; `docs/PAPER_STATUS.md` | yes | none |
| "Five things" added since the third pilot | REPORT 1 | count of the listed items: stability tier, synthetic GPU paper, field analysis, diagnosis layer, ReScience C selection | yes | none |

## Wilson intervals (recomputed)

Computed with the standard Wilson formula (z = 1.959964) in a throwaway script; no stored value was used as input. They agree with the
generated blocks: 0/14 -> 0.0 to 21.5; 1/6 -> 3.0 to 56.4; 2/6 -> 9.7 to 70.0; 3/12 -> 8.9 to 53.2; 1/12 -> 1.5 to 35.4.
For 0/135 and 0/107 the formula gives 0.0 to 2.8 and 0.0 to 3.5.

## Not verified

- Numbers inside the generated blocks other than the ones listed above were not recomputed by hand; they are as correct as the
  stored files and `scripts/report_numbers.py`, which `--check` and its tests tie together.
- Statements about external publications (sections 2 and 3) are covered by `docs/INTRODUCTION_SOURCES.md` and
  `docs/report/RELATED_WORK_SOURCES.md`, not by this audit.
- The 6-of-6 corpus verification and the live Crossref/arXiv lookups need the network and were not re-run here.
