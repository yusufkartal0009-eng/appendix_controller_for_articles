# Repro Radar — Living Progress Log

> This document is updated after every milestone, issue, or PR to maintain full project memory.

---

## Current Status: M0 Baseline & Projectflow Adoption

- **Active Milestone:** M0 — Baseline Hygiene & Audit
- **Planned Milestones:** M0 to M7 (45 trackable issues cataloged in `docs/BLUEPRINT.md`)
- **Functional Areas:** `corpus`, `sandbox`, `scoring`, `ai`, `web`, `devops`
- **Total Unit Tests Passing:** 86 / 86 on Linux (1 POSIX-permission test is skipped on Windows); CI: Ubuntu, Windows, sandbox image, corpus verification, real-Docker sandbox acceptance with 7 checks

---

## Milestone Roadmap & Progress

Issue numbers and open/closed counts match GitHub as of 2026-09-27 (issues only, not PRs; counted with #92 closed by PR #95). Backlog ranges are the per-issue items listed in `docs/BLUEPRINT.md`; partly implemented open issues carry a status note on GitHub. Open/closed also includes issues added after the backlog (e.g. M2: #48, #80, #86, #88, #90, #92).

| Milestone | Focus | Backlog issues | Open / closed | Status |
|---|---|:---:|:---:|:---:|
| **M0: Baseline Hygiene & Audit** | Seed audit, projectflow adoption, hygiene tests | #2 – #6 | 4 / 8 | IN PROGRESS |
| **M1: Seed Corpus & Relational Data Foundation** | ArXiv ingestion, repo verification, claims schema | #7 – #12 | 6 / 3 | IN PROGRESS |
| **M2: Isolated Container Sandbox** | Docker runner, cgroups, network isolation, timeout | #13 – #18 | 6 / 6 | IN PROGRESS |
| **M3: Static Code Analysis & Dependency Solver** | AST scanner, manifest parser, unpinned solver, GPU flags | #19 – #24 | 6 / 1 | QUEUED |
| **M4: Empirical Metric Extraction Engine** | Regex log parsers, stdout extraction, multi-seed CV, rubric | #25 – #30, #55 | 2 / 5 | IN PROGRESS |
| **M5: AI Decision Layer & Diagnostics** | Failure classifier, neutral reports, discrepancy explainer | #31 – #36 | 6 / 1 | QUEUED |
| **M6: Web Dashboard & Reporting Portal** | FastAPI REST API, leaderboard UI, SVG badges, PDF reports | #37 – #41 | 5 / 0 | QUEUED |
| **M7: Verification Suite & Production Release** | Pilot verification, contribution guide, CI/CD, v1.0 release | #42 – #46 | 4 / 3 | IN PROGRESS |

The weekly "Hafta 1–7" milestones were retired on 2026-09-25: their umbrella issues (#47 – #53) were closed as completed or as duplicates of the backlog above and moved into the matching M milestones.

---

## Changelog & Completed Work

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
