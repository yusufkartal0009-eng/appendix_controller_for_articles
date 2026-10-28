# Triage of the old open issues (2026-10-28, issue #556)

Each open issue created before the pilots was read (body, definition of done, earlier status comments) and compared with `main` at
`bd188f4`: the files it names, the tests, and the documents. An issue is closed only when its definition of done is met with evidence.
None was closed in this pass: for every one, at least one box of the definition of done, or the file or behavior the issue names, is
missing on `main`. Where an earlier status comment was still correct it was left as it is; a new comment was written only where this
review found something new. "Owner decision" means the issue asks for something the project has not decided to build.

| Issue | State | Evidence (main at `bd188f4`) | Action |
|---|---|---|---|
| #3 commitlint and branch protection | Not started; needs an owner decision | No `commitlint.config.js`, no `.github/rulesets/`. The repository is public now, so the 403 that blocked branch protection while it was private may no longer apply, but GitHub settings are not touched by an assistant. The project has no CI (D-010) and checks locally. | Comment: owner decision (set the ruleset or drop the issue). Left open |
| #7 arXiv API client | Partly done elsewhere | `scripts/verify_sources.py` and `scripts/verify_corpus.py` fetch arXiv metadata with a 3 s pause; `src/corpus/arxiv_client.py` does not exist | Earlier comment (2026-10-15) still correct. Left open |
| #8 GitHub repo verification | Partly done elsewhere | `scripts/verify_corpus.py` `check_repo_and_license` checks status 200 and the pinned script; no `archived` handling, no `src/corpus/repo_checker.py`. The earlier comment says "the corpus CI job runs it"; that CI was removed (#388) | Comment: CI part is stale, the run is local. Left open |
| #11 claim tolerance test suite | Partly done | Boundary tests exist in `tests/test_scoring.py`; no test of a claimed value of 0 (zero-division guard) | Zero-guard test is added in the test-gap work (#557); this row is updated after it merges |
| #13 base Dockerfile | Partly done | Both boxes ticked; image size and non-root user have evidence (`docs/SANDBOX_ACCEPTANCE.md` checks 1, 16). The "Wanted" line names `xgboost` and `lightgbm`, which `docker/Dockerfile.sandbox` does not install (it pre-bakes numpy, scipy, pandas, scikit-learn, tabulate, pytest) | Earlier comment still correct. Left open |
| #14 container lifecycle | Partly done | Memory, CPU, PID and output limits enforced (`src/sandbox/runner.py`, acceptance checks 8, 9, 17). Streaming to SQLite not built: only Pilot 1 logs are loaded (`scripts/load_pilot_runs.py`) | Earlier comment still correct. Left open |
| #15 zero-network isolation | Partly done | `--network none` verified (check 2). Blocked outbound attempts are not logged | Earlier comment still correct. Left open |
| #17 timeout and memory watchdog | Partly done | Real `TIMEOUT` and `OOM_KILLED` records exist (checks 4, 8, 21; pilots). The 600 s hard kill was never observed (pilots used 3600 s and 14400 s); no `src/sandbox/watchdog.py` | Earlier comment still correct. Left open |
| #18 end-to-end sandbox tests | Partly done | Tests cover exit 0, 124 and 137; no test asserts a non-zero exit code of 1 with a mock repository | Earlier comment still correct. Left open |
| #19 AST import scanner | Not started | No `src/sandbox/ast_scanner.py`; no module imports `ast` for this purpose | Comment: not started, owner decision whether it is wanted. Left open |
| #20 manifest parser | Partly done elsewhere | `Stager._parse_requirements_file` (`tests/test_stager.py`), `src/sandbox/conda_env.py` (`tests/test_conda_env.py`); no `manifest_parser.py`, `pyproject.toml` only detected | Earlier comment still correct. Left open |
| #21 version solver | Not started | No `src/sandbox/version_solver.py`; unpinned packages are installed at the newest fitting version (report section 7) | Comment: not started. Left open |
| #22 GPU-to-CPU flag injection | Not started | No `src/sandbox/cpu_adapter.py`; the pilots run CPU-only by not attaching a GPU | Comment: not started. Left open |
| #23 entrypoint detection | Partly done | `Stager.detect_candidate_scripts` (`tests/test_stager.py`); no `entrypoint_detector.py`, no ranking below the root | Earlier comment still correct. Left open |
| #24 dependency tests on diverse repos | Not started as asked | No `tests/test_manifest_parser.py`; the pilots (12 real papers) are real-world evidence but not the test suite the issue asks for | Comment: not started as a test suite. Left open |
| #30 metric extraction on noisy logs | Partly done; a real defect found | `tests/test_metric_extractor.py` has no ANSI or noisy-log fixture. Running `MetricExtractor.extract_metrics` on `\x1b[32maccuracy: 0.85\x1b[0m` returns `{'32maccuracy': 0.85}`: the color code becomes part of the metric name, so a claim for `accuracy` would not match. tqdm progress lines did not corrupt the result | Comment with the finding; a fix and tests are in the test-gap work (#557). Left open until they merge |
| #34 local LLM fallback | Partly done | `src/diagnosis/backends.py` (`NullBackend` default, `anthropic` and `local` backends, fallback to the rule-based report); the extractor that returns claims as validated JSON was not built; nothing was run against a real model | Earlier comment (2026-10-20) still correct. Left open |
| #35 discrepancy explainer | Partly done | `src/diagnosis/compare.py` (rules R1 to R6); nothing writes `Needs Review` to the database | Earlier comment (2026-10-20) still correct. Left open |
| #45 release automation | Not started; owner decision | No `scripts/release.py`; no release is tagged | Comment: owner decision (when to tag v1.0.0). Left open |
| #115 working agreement | Standing issue | Never closed by design | None |

Not verified: whether GitHub would now accept a branch protection ruleset on this public repository (not tried, because settings
are not touched).
