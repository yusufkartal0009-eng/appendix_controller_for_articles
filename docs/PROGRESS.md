# Repro Radar — Living Progress Log

> This document is updated after every milestone, issue, or PR to maintain full project memory.

---

## Current Status: M0 Baseline & Projectflow Adoption

- **Active Milestone:** M0 — Baseline Hygiene & Audit
- **Planned Milestones:** M0 to M7 (45 trackable issues cataloged in `docs/BLUEPRINT.md`)
- **Functional Areas:** `corpus`, `sandbox`, `scoring`, `ai`, `web`, `devops`
- **Total Unit Tests Passing:** 20 / 20 tests green

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
