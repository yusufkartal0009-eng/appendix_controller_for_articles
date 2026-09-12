# Repro Radar — Stack & Environment Map

> Technology choices, runtime requirements, dependencies, and external boundary definitions.

---

## 1. Core Stack

| Component | Technology | Version | Rationale |
|---|---|---|---|
| **Runtime** | Python | 3.11.x | Modern typing features, performance enhancements, CPython stability |
| **Package Manager** | uv / pip | Latest | Blazing fast dependency resolution and isolated venvs |
| **Database** | SQLite | 3.x | Zero-config, ACID-compliant, portable, single-file relational DB |
| **ORM / Query Engine** | SQLAlchemy | >= 2.0.25 | Robust relational mapping, session lifecycle, connection pooling |
| **Data Validation** | Pydantic | >= 2.6.0 | Strict type validation, fast Rust core (`pydantic-core`) |
| **Data & Metrics** | Pandas, NumPy | >= 2.2.0 | Numerical operations, metric variance, coefficient of variation |
| **Testing** | Pytest | >= 8.0.0 | Unit test discovery, fixtures, assertion rewriting |
| **CLI Formatting** | Tabulate | >= 0.9.0 | Clean terminal table layouts for datasets and scores |
| **Sandbox (Week 2)** | Docker / Containerd | Engine 24+ | CPU/RAM cgroups isolation and network sandboxing |

---

## 2. Directory & Path Layout

- `src/` — Production application code
- `data/` — SQLite databases (`repro_radar.db`), SQL schemas (`schema.sql`), seed papers (`seed_papers.json`)
- `docs/` — Living documentation, methodology, architectural decision records (ADRs)
- `tests/` — Automated test suite
- `.venv/` — Virtual environment directory (gitignored)

---

## 3. Security & Boundary Controls

- **Network Restrictions:** Sandbox containers will execute with `--network none` during evaluation.
- **Resource Constraints:** Hard ceiling of 2 vCPUs, 8GB RAM, and 600 seconds per execution run.
- **Local Data Only:** No telemetry, no external LLM data leaks; evaluations are computed deterministically.
