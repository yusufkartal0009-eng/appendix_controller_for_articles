# Repro Radar — Living Progress Log

> This document is updated after every milestone, issue, or PR to maintain full project memory.

---

## Current Status: M0 Baseline & Projectflow Adoption

- **Active Milestone:** M0 — Baseline Hygiene & Audit
- **Planned Milestones:** M0 to M7 (45 trackable issues cataloged in `docs/BLUEPRINT.md`)
- **Functional Areas:** `corpus`, `sandbox`, `scoring`, `ai`, `web`, `devops`
- **Total Unit Tests Passing:** 34 / 34 tests green

---

## Milestone Roadmap & Progress

| Milestone | Focus | Issues | Status |
|---|---|:---:|:---:|
| **M0: Baseline Hygiene & Audit** | Seed audit, projectflow adoption, hygiene tests | #1 – #5 | **IN PROGRESS 🟡** |
| **M1: Seed Corpus & Relational Data Foundation** | ArXiv ingestion, repo verification, claims schema | #6 – #11 | QUEUED |
| **M2: Isolated Container Sandbox** | Docker runner, cgroups, network isolation, timeout | #12 – #17 | QUEUED |
| **M3: Static Code Analysis & Dependency Solver** | AST scanner, manifest parser, unpinned solver, GPU flags | #18 – #23 | QUEUED |
| **M4: Empirical Metric Extraction Engine** | Regex log parsers, stdout extraction, multi-seed CV | #24 – #29 | QUEUED |
| **M5: AI Decision Layer & Diagnostics** | Failure classifier, neutral reports, discrepancy explainer | #30 – #35 | QUEUED |
| **M6: Web Dashboard & Reporting Portal** | FastAPI REST API, leaderboard UI, SVG badges, PDF reports | #36 – #40 | QUEUED |
| **M7: Verification Suite & Production Release** | Pilot verification, contribution guide, CI/CD, v1.0 release | #41 – #45 | QUEUED |

---

## Changelog & Completed Work

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
