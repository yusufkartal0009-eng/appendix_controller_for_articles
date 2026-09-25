# Repro Radar — Living Progress Log

> This document is updated after every milestone, issue, or PR to maintain full project memory.

---

## Current Status: M0 Baseline & Projectflow Adoption

- **Active Milestone:** M0 — Baseline Hygiene & Audit
- **Planned Milestones:** M0 to M7 (45 trackable issues cataloged in `docs/BLUEPRINT.md`)
- **Functional Areas:** `corpus`, `sandbox`, `scoring`, `ai`, `web`, `devops`
- **Total Unit Tests Passing:** 49 / 49 tests green

---

## Milestone Roadmap & Progress

| Milestone | Focus | Issues | Status |
|---|---|:---:|:---:|
| **M0: Baseline Hygiene & Audit** | Seed audit, projectflow adoption, hygiene tests | #1 – #5 | COMPLETED 🟢 |
| **M1: Seed Corpus & Relational Data Foundation** | ArXiv ingestion, repo verification, claims schema | #6 – #11 | COMPLETED 🟢 |
| **M2: Isolated Container Sandbox** | Docker runner, cgroups, network isolation, timeout | #12 – #17, #48 | COMPLETED 🟢 |
| **M3: Static Code Analysis & Dependency Solver** | AST scanner, manifest parser, unpinned solver, GPU flags | #18 – #23, #49 | QUEUED |
| **M4: Empirical Metric Extraction Engine** | Regex log parsers, stdout extraction, multi-seed CV, rubric | #24 – #29, #50, #55 | COMPLETED 🟢 |
| **M5: AI Decision Layer & Diagnostics** | Failure classifier, neutral reports, discrepancy explainer | #30 – #35, #51 | QUEUED |
| **M6: Web Dashboard & Reporting Portal** | FastAPI REST API, leaderboard UI, SVG badges, PDF reports | #36 – #40 | QUEUED |
| **M7: Verification Suite & Production Release** | Pilot verification, contribution guide, CI/CD, v1.0 release | #41 – #45, #53 | QUEUED |

---

## Changelog & Completed Work

### M0 / DevOps: Setup & Verification Docs for the New Environment (2026-09-25, Issue #72)
- `README.md`: Quickstart installs `requirements-dev.txt` (runtime-only alternative noted), adds the Windows `py` launcher note, lint step, an accurate simulation note (G2), and a refreshed directory layout (G12).
- `docs/ENVIRONMENT.md`: separate runtime and development package tables, updated Windows and Linux/macOS setup, sandbox image smoke test with `dependency_install_status`, and a new verified baseline (52 tests, ruff clean).
- `docs/SANDBOX_GUIDE.md`: actual `execution_meta.json` fields and the new `meta_error` report field.
- `docs/gap_analysis.md`: status column tracking which gaps are fixed, partly fixed, or open.

### M0 / DevOps: Gap Remediation — Sandbox, Dependency, and Safety Fixes (2026-09-25, Issue #70)
- **CI (G3):** workflow prepared (lint, tests on Ubuntu and Windows, sandbox image build and smoke test) but not yet pushed: the GitHub token lacks the `workflow` scope. Follows in a separate PR.
- **Dependencies (G6):** `requirements.txt` now holds runtime packages only (`pydantic`, `sqlalchemy`, `tabulate`); tests, lint, and document tooling moved to `requirements-dev.txt`; unused `pandas`, `pyyaml`, and `requests` removed. `pyproject.toml` defines the ruff correctness gate.
- **Sandbox image (G7):** version constraints in `Dockerfile.sandbox` are quoted, so they are no longer parsed as shell redirections.
- **Entrypoint (G8):** `execution_meta.json` gains `dependency_install_status` (`SKIPPED` / `INSTALLED` / `FAILED`) instead of hiding install failures behind `|| true`.
- **Error handling (G9):** the metric extractor logs skipped non-JSON blocks; `execute_staged` reports an unreadable `execution_meta.json` as `meta_error`.
- **Security (G10):** `setup_github_backlog.py` passes argument lists without a shell and sends issue bodies on stdin.
- **Docker hygiene (G14):** `.dockerignore` limits the build context; obsolete Compose `version` key removed.
- 52 / 52 tests green (3 new), verified in a clean venv built from `requirements-dev.txt`.

### M0 / DevOps: Repository Gap Analysis (2026-09-24, Issue #67)
- Added `docs/gap_analysis.md`: 15 gaps (3 high, 7 medium, 5 low) across tracking, product, CI, tests, dependencies, sandbox, code quality, security, and docs, each with evidence, remedy, and related issue.
- Measured baseline: 60% line coverage (`cli.py` 0%), 281 `ruff` findings, 49 / 49 tests green.
- Highest-impact findings: living docs disagree with GitHub milestone/issue state (G1), `cli.py score` still runs on simulated outputs (G2), no CI (G3).
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
- **Reproducibility Scoring Engine:**
  - 4-Tier rubric (%35 Build, %35 Metrics, %15 Stability, %15 Artifacts) in `src/scoring.py`.
- **CLI & Test Suite:**
  - Built `cli.py` with `init-db`, `list-papers`, `inspect`, and `score` commands.
  - 20 unit tests in `tests/` passing.
