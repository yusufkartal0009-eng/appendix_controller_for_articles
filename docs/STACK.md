# Repro Radar — Stack & Environment Map

> Technology choices, runtime requirements, dependencies, and external boundary definitions across the 6 functional areas.

---

## 1. Core Stack Across 6 Areas

| Area | Component | Technology | Version | Purpose |
|---|---|---|---|---|
| **`area:corpus`** | Metadata & Ingestion | Pydantic v2, Requests, SQLite | Python 3.11 | Data validation, JSON parsing, arXiv API ingestion |
| **`area:sandbox`** | Container Sandbox | Docker Engine, cgroups, subprocess | 24.x+ | Hard CPU/RAM resource limits, timeout controls, zero-network mode |
| **`area:scoring`** | Scoring Engine | Pandas, NumPy | >= 2.2.0 | Relative error calculation, multi-seed CV variance, tier weighting |
| **`area:ai`** | Decision & Diagnostics | Local LLM / Prompt templates | Python 3.11 | Automated failure classification and neutral diagnostic summaries |
| **`area:web`** | API & Dashboard | FastAPI, Uvicorn, Jinja2 / SVG | Latest | REST API endpoints, interactive leaderboard, dynamic badges |
| **`area:devops`** | Tooling | Git, Pytest, ruff (no CI service, D-010) | Pytest 8.x | Test execution and PR validation run locally; release automation is not built (#45) |

---

## 2. Directory & Path Layout

- `src/` — Core application code partitioned by domain
- `data/` — SQLite databases (`repro_radar.db`), SQL schemas (`schema.sql`), seed papers (`seed_papers.json`)
- `docs/` — Living documentation (`BLUEPRINT.md`, `ARCHITECTURE.md`, `PROGRESS.md`, `STACK.md`, `methodology.md`, `project_roadmap.md`)
- `tests/` — Automated test suite with Pytest fixtures
- `.github/` — Issue forms, PR templates, and workflow actions
- `.venv/` — Isolated virtual environment (gitignored)

---

## 3. Security & Boundary Controls

- **Network Policy:** Sandbox containers will execute with `--network none` during evaluation.
- **Compute Quotas:** Strict boundaries of 2 vCPUs, 8GB RAM, and 600-second process timeout.
- **Air-gapped Local Data:** No proprietary data leaks; deterministic evaluations conducted locally.
