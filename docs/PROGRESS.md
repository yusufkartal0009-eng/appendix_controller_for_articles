# Repro Radar — Living Progress Log

> This document is updated after every milestone, issue, or PR to maintain full project memory.

---

## Current Status: Week 1 Completed ✅ (Entering Week 2)

- **Active Milestone:** Milestone 2 — Docker Sandbox & Isolation Engine
- **Completed Milestone:** Milestone 1 — Week 1 Setup & Discovery Infrastructure
- **Total Unit Tests Passing:** 20 / 20 tests green

---

## Changelog & Completed Work

### Milestone 1: Week 1 Setup & Discovery Infrastructure (2026-09-10)
- **Repository Setup:**
  - Initialized clean repository with comprehensive `.gitignore` and MIT `LICENSE`.
  - Configured Python 3.11 virtual environment with `uv`.
  - Added dependencies in `requirements.txt` (Pydantic, SQLAlchemy, Pandas, Pytest, PyYAML, Requests, Tabulate).
- **Relational Data Layer:**
  - Designed SQLite DDL schema in `data/schema.sql` (`papers`, `runs`, `claims`, `scores`).
  - Implemented SQLAlchemy ORM & Pydantic v2 schemas in `src/models.py`.
  - Built connection and session manager with idempotent seeding in `src/database.py`.
- **Target Paper Dataset:**
  - Curated 18 high-quality Tabular ML & Light NLP benchmark papers (2021–2024) in `data/seed_papers.json`.
  - Verified open source licenses (MIT, Apache-2.0, BSD-3-Clause) and numerical claims.
- **Reproducibility Scoring Engine:**
  - Implemented 4-tier rubric in `src/scoring.py` (%35 Build, %35 Metrics, %15 Stability, %15 Artifacts).
  - Built AI Decision Layer with neutral status classifications (`Doğrulandı`, `Kısmen Doğrulandı`, `İncelenmeli`, `Tekrarlanamadı`).
- **CLI & Diagnostics:**
  - Built `cli.py` with `init-db`, `list-papers`, `inspect`, and `score` commands (including simulation flags).
- **Documentation & Standards:**
  - Created `docs/methodology.md` with mathematical formulas, rubric definitions, and ethical standards.
  - Created `docs/project_roadmap.md` with 7-week detailed milestones and tasks.
- **Test Suite:**
  - Wrote 20 tests across `test_database.py`, `test_models.py`, `test_scoring.py`, and `test_seed.py`. All passing.
- **Projectflow & Superpowers Integration (2026-09-12):**
  - Globally installed `projectflow` and 14 `superpowers` deep skills into `~/.gemini/config/skills/`.
  - Added `AGENTS.md` and seeded living documentation (`docs/BLUEPRINT.md`, `docs/ARCHITECTURE.md`, `docs/PROGRESS.md`, `docs/STACK.md`).
  - Added GitHub issue and PR templates in `.github/`.

---

## Next Steps (Milestone 2: Week 2)
1. Design Docker sandbox runner (`src/sandbox/runner.py`).
2. Build standardized base Dockerfile for Python 3.10/3.11 lightweight ML.
3. Add container resource limits (2 CPU cores, 8GB RAM, 600s execution timeout).
4. Implement network isolation (allow network during dependency install, restrict during execution).
5. Build multi-seed runner to evaluate Tier 3 variance automatically.
