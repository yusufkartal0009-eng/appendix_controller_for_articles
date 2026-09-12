# Repro Radar — Blueprint

> The master plan: what Repro Radar is, why it exists, and how it evolves across milestones.

---

## 1. Vision & Purpose
Repro Radar is an automated replication and verification platform for AI & Machine Learning research papers. Given an empirical paper and its open-source code repository, Repro Radar clones the repo into an isolated container sandbox, installs dependencies, executes the benchmark scripts, extracts empirical claims, and scores the paper's reproducibility using a 4-tier rubric.

### Core Problems Solved
- **Replication Crisis in AI/ML:** Thousands of papers publish claimed metrics without verifiable or reproducible codebases.
- **Unpinned / Broken Environments:** Code that only worked on a specific author's machine with hidden dependencies.
- **Cherry-Picked Random Seeds:** Claims holding true only under a single undisclosed random seed.
- **Manual Verification Bottleneck:** Reviewers lack the time and isolated compute infrastructure to re-run papers.

---

## 2. Key Architecture Pillars
1. **Curated Benchmark Suites:** Focused domains requiring lightweight compute (2–10 minutes on CPU), starting with *Tabular Machine Learning & Light NLP Benchmarks*.
2. **Relational Data Layer:** SQLite backend tracking papers, execution runs, claimed vs reproduced metrics, and composite reproducibility scores.
3. **4-Tier Scoring Rubric:**
   - **Tier 1 (Build & Environment - 35%):** Repo clone + dependency resolution + execution with Exit Code 0.
   - **Tier 2 (Metric Alignment - 35%):** Claim vs reproduced metric match within 5% tolerance.
   - **Tier 3 (Seed Stability - 15%):** Multi-seed evaluation with Coefficient of Variation (CV) < 2%.
   - **Tier 4 (Documentation & License - 15%):** OSI license, pinned requirements, reproducible logs.
4. **AI Decision Layer:** Neutral classification (`Doğrulandı`, `Kısmen Doğrulandı`, `İncelenmeli`, `Tekrarlanamadı`) with diagnostic reasoning.
5. **Secure Sandbox Runner:** Ephemeral Docker containers with CPU/RAM quotas and network restrictions.

---

## 3. Milestones Overview

| Milestone | Scope | Status |
|---|---|:---:|
| **M1: Week 1 Setup & Discovery Infrastructure** | Schema, seed dataset (18 papers), ORM, 4-tier scoring engine, CLI, unit tests | **DONE ✅** |
| **M2: Week 2 Docker Sandbox & Isolation Engine** | Container lifecycle, resource quotas, network isolation, seed matrix execution | **NEXT 🎯** |
| **M3: Week 3 Static Analysis & Dependency Solver** | AST import analyzer, unpinned version resolver, GPU-to-CPU adapter | QUEUED |
| **M4: Week 4 Metric Extraction Engine** | Regex & structured log parsers, stdout claim matchers, LLM fallback parser | QUEUED |
| **M5: Week 5 AI Decision Layer & Pipeline** | Automated orchestration, failure root-cause analysis, report generator | QUEUED |
| **M6: Week 6 Web Dashboard & Badges** | Interactive FastAPI / Web UI, GitHub badges, PDF/Markdown export | QUEUED |
| **M7: Week 7 End-to-End Verification & Release** | Full 18-paper verification run, community protocol, V1.0 release | QUEUED |
