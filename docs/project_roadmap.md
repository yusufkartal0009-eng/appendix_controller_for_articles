# Repro Radar: 7-Week Project Roadmap

This document defines the 7-week development schedule, milestones, and concrete task breakdowns for the Repro Radar automated replication and verification platform.

---

```mermaid
gantt
    title Repro Radar 7-Week Development Schedule
    dateFormat  YYYY-MM-DD
    section Week 1
    Setup & Discovery Infrastructure :done, w1, 2026-09-01, 7d
    section Week 2
    Docker Sandbox & Isolation Engine:active, w2, 2026-09-08, 7d
    section Week 3
    Static Analysis & Dependency Solver:w3, 2026-09-15, 7d
    section Week 4
    Metric Extraction Engine         :w4, 2026-09-22, 7d
    section Week 5
    AI Decision Layer & Pipeline     :w5, 2026-09-29, 7d
    section Week 6
    Web Dashboard & Reporting        :w6, 2026-10-06, 7d
    section Week 7
    Integration, Verification & Release:w7, 2026-10-13, 7d
```

---

## Week 1: Setup & Discovery Infrastructure (Completed ✅)
- **Objective:** Establish the core project skeleton, relational data schema, target seed paper dataset, and 4-tier reproducibility scoring engine.
- **Tasks:**
  - [x] Repository architecture & directory hierarchy (`src/`, `data/`, `docs/`, `tests/`).
  - [x] SQLite relational schema via `schema.sql` (`papers`, `runs`, `claims`, `scores`).
  - [x] SQLAlchemy ORM and Pydantic v2 validation models (`src/models.py`).
  - [x] Curate 18-paper "Tabular Machine Learning & Light NLP" seed dataset (`data/seed_papers.json`).
  - [x] Automated database initialization and seeding engine (`src/database.py`).
  - [x] 4-Tier reproducibility scoring engine and neutral status classifier (`src/scoring.py`).
  - [x] Methodology and ethical standards documentation (`docs/methodology.md`).
  - [x] Comprehensive unit tests (20/20 passing) (`tests/`).

---

## Week 2: Docker Sandbox & Isolation Engine
- **Objective:** Execute third-party repositories in ephemeral, resource-constrained container environments isolated from the host machine.
- **Tasks:**
  - [ ] Standardized Python 3.11 base Dockerfile and runtime images (`docker/Dockerfile.sandbox`).
  - [ ] Resource quotas: CPU limits (2 vCPUs), memory caps (8GB max), execution timeout (600s).
  - [ ] Network isolation policy (network permitted during dependency install, disabled with `--network none` during execution).
  - [ ] Container lifecycle runner (`src/sandbox/runner.py`): Launch, log streaming, exit code capture, and cleanup.
  - [ ] Multi-seed execution harness integrated with sandbox and SQLite `runs` table.

---

## Week 3: Static Code Analysis & Dependency Solver
- **Objective:** Pre-analyze cloned repositories to detect implicit dependencies, hardware requirements, and entrypoint scripts before execution.
- **Tasks:**
  - [ ] Python AST (Abstract Syntax Tree) scanner to detect undeclared package imports.
  - [ ] Multi-format manifest parser (`requirements.txt`, `setup.py`, `pyproject.toml`, `environment.yml`).
  - [ ] Intelligent dependency solver for unpinned version constraints.
  - [ ] GPU-to-CPU compatibility adapter (injecting `--cpu`, `device='cpu'` flags).
  - [ ] Entrypoint script heuristic detector (`main.py`, `eval.py`, `run.py`, `test.py`).

---

## Week 4: Metric Extraction Engine
- **Objective:** Parse console logs (`stdout`), structured outputs (JSON/CSV), and model checkpoints to extract empirical values matching paper claims.
- **Tasks:**
  - [ ] Regex-based metric extractor (`accuracy: 0.85`, `AUC = 0.912`, `Loss: 0.42`).
  - [ ] Standardized evaluation parsers for Scikit-learn, PyTorch, and LightGBM output formats.
  - [ ] Local LLM fallback parser for unstructured free-text console logs.
  - [ ] Store extracted metrics in `claims` table and compute relative errors.

---

## Week 5: AI Decision Layer & Automated Pipeline
- **Objective:** Synthesize execution logs, metric discrepancies, and system traces into an objective diagnostic report.
- **Tasks:**
  - [ ] Orchestrate Tier 1, 2, 3, and 4 evaluators under a unified `PipelineController`.
  - [ ] Root-cause diagnostic engine (classify out-of-memory, missing data, version conflict errors).
  - [ ] Automated decision rationale templates.
  - [ ] Structured report generation (Markdown & JSON).

---

## Week 6: Web Dashboard & Verification Badges
- **Objective:** Interactive dashboard for querying evaluated papers, visualizing metrics, and generating embeddable GitHub badges.
- **Tasks:**
  - [ ] FastAPI REST API (`/papers`, `/scores`, `/runs/{id}`).
  - [ ] Lightweight web UI for searching papers and inspecting diagnostic breakdowns.
  - [ ] Dynamic GitHub SVG badge generator (`![Repro Radar: 92/100 Verified]`).
  - [ ] Exportable PDF/Markdown reproducibility reports.

---

## Week 7: End-to-End Verification, Community Protocol & Release
- **Objective:** Execute pilot verification across all 18 seed papers, finalize open documentation, and release version 1.0.
- **Tasks:**
  - [ ] Full sandbox verification runs across the 18-paper seed suite.
  - [ ] Community contribution guidelines (`CONTRIBUTING.md`) and paper onboarding guide.
  - [ ] Automated CI/CD pipeline with GitHub Actions.
  - [ ] V1.0 public release announcement and summary report.
