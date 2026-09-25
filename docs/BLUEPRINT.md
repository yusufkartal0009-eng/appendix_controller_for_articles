# Repro Radar — Blueprint

> The master plan: what Repro Radar is, why it exists, and how it evolves across milestones M0 through M7 across 6 key functional areas.

---

## 1. Vision & Purpose
Repro Radar is an automated replication and verification platform for AI & Machine Learning research papers. Given an empirical paper and its open-source code repository, Repro Radar clones the repo into an isolated container sandbox, installs dependencies, executes the benchmark scripts, extracts empirical claims, and scores the paper's reproducibility using a 4-tier rubric.

### Core Problems Solved
- **Replication Crisis in AI/ML:** Thousands of papers publish claimed metrics without verifiable or reproducible codebases.
- **Unpinned / Broken Environments:** Code that only worked on a specific author's machine with hidden dependencies.
- **Cherry-Picked Random Seeds:** Claims holding true only under a single undisclosed random seed.
- **Manual Verification Bottleneck:** Reviewers lack the time and isolated compute infrastructure to re-run papers.

---

## 2. Six Functional Areas (Projectflow Taxonomy)

The codebase and issue tracking are partitioned across 6 areas:
- **`area:corpus`**: Target research paper corpus, metadata schemas, seed datasets, arXiv integrations, and claim definitions.
- **`area:sandbox`**: Container runtime, Docker execution driver, cgroups resource controls, timeouts, filesystem isolation, and local subprocess fallback.
- **`area:scoring`**: 4-Tier reproducibility engine (build, metrics, stability, artifacts), tolerance calculators, and composite weighted scoring.
- **`area:ai`**: AI Decision Layer, automated diagnostic reasoning, crash log classification, and discrepancy explainers.
- **`area:web`**: FastAPI REST API, paper leaderboard UI, SVG badge generator, and PDF/Markdown report exporters.
- **`area:devops`**: CI/CD workflows, GitHub Actions, projectflow conventions, rulesets, and release management.

---

## 3. Four-Tier Scoring Rubric

1. **Tier 1 (Build & Environment - 35%):** Repo clone + dependency resolution + entrypoint execution with clean Exit Code 0.
2. **Tier 2 (Metric Alignment - 35%):** Claim vs reproduced metric match within 5% tolerance.
3. **Tier 3 (Seed Stability - 15%):** Multi-seed evaluation with Coefficient of Variation (CV) < 2%.
4. **Tier 4 (Documentation & License - 15%):** Permissive OSI license, pinned requirements, structured output logs.

Neutral status classifications: `Verified`, `Partially Verified`, `Needs Review`, `Failed`.

---

## 4. Milestones & Backlog Mapping (M0 – M7)

The backlog contains 45 trackable engineering issues mapped across 8 milestones:

### M0: Baseline Hygiene & Audit (Issues #2 – #6)
- `#2` `fix(corpus): remove fabricated entries from the seed paper set` [priority: high]
- `#3` `chore(devops): setup commitlint and branch protection ruleset` [priority: high]
- `#4` `test(corpus): add automated integrity verification for seed paper schemas` [priority: medium]
- `#5` `docs(devops): document projectflow operating rules and living docs cadence` [priority: medium]
- `#6` `chore(corpus): standardize license detection and classification enum` [priority: medium]

### M1: Seed Corpus & Relational Data Foundation (Issues #7 – #12)
- `#7` `feat(corpus): implement arXiv API client for paper metadata fetching` [priority: high]
- `#8` `feat(corpus): automate GitHub repo availability and clone verification` [priority: high]
- `#9` `feat(corpus): add PDF claim parser and text extractor` [priority: medium]
- `#10` `feat(scoring): implement relational persistence for extracted claims` [priority: high]
- `#11` `test(scoring): add claim tolerance and relative error test suite` [priority: high]
- `#12` `feat(devops): add automated database migration script for schema evolution` [priority: medium]

### M2: Isolated Container Sandbox (Issues #13 – #18)
- `#13` `feat(sandbox): create base Dockerfile for tabular ML benchmarks` [priority: high]
- `#14` `feat(sandbox): implement container lifecycle manager with cgroup limits` [priority: high]
- `#15` `feat(sandbox): enforce zero-network isolation during code execution` [priority: high]
- `#16` `feat(sandbox): implement local subprocess fallback runner for non-Docker hosts` [priority: medium]
- `#17` `feat(sandbox): implement execution timeout and memory kill watchdog` [priority: high]
- `#18` `test(sandbox): add end-to-end sandbox execution tests with mock repositories` [priority: high]

### M3: Static Code Analysis & Dependency Solver (Issues #19 – #24)
- `#19` `feat(sandbox): build Python AST import scanner for undeclared packages` [priority: high]
- `#20` `feat(sandbox): implement multi-format manifest parser for requirements and pyproject` [priority: high]
- `#21` `feat(sandbox): build intelligent dependency version solver for unpinned packages` [priority: medium]
- `#22` `feat(sandbox): add GPU-to-CPU execution flag injection module` [priority: medium]
- `#23` `feat(sandbox): implement entrypoint script heuristic detection algorithm` [priority: high]
- `#24` `test(sandbox): test dependency resolution on diverse open-source benchmark repos` [priority: medium]

### M4: Empirical Metric Extraction Engine (Issues #25 – #30)
- `#25` `feat(scoring): implement regex-based metric parser for stdout streams` [priority: high]
- `#26` `feat(scoring): build structured output parsers for Scikit-learn and LightGBM logs` [priority: high]
- `#27` `feat(scoring): implement multi-seed variance and coefficient of variation calculator` [priority: high]
- `#28` `feat(scoring): build partial-credit tolerance scoring for borderline claims` [priority: medium]
- `#29` `feat(scoring): add artifact checksum and reproducibility hash generator` [priority: low]
- `#30` `test(scoring): test metric extraction accuracy against noisy console logs` [priority: high]

### M5: AI Decision Layer & Diagnostics (Issues #31 – #36)
- `#31` `feat(ai): design AI Decision Layer prompt templates for root-cause diagnosis` [priority: high]
- `#32` `feat(ai): implement automated failure classification for sandbox crash logs` [priority: high]
- `#33` `feat(ai): generate neutral diagnostic rationale reports for evaluated papers` [priority: high]
- `#34` `feat(ai): integrate local LLM fallback for unstructured metric matching` [priority: medium]
- `#35` `feat(ai): build discrepancy explainer for hardware and floating-point variance` [priority: medium]
- `#36` `test(ai): validate diagnostic classification accuracy on synthetic failure cases` [priority: high]

### M6: Web Dashboard & Reporting Portal (Issues #37 – #41)
- `#37` `feat(web): scaffold FastAPI backend service with REST endpoints` [priority: high]
- `#38` `feat(web): build interactive paper leaderboard and benchmark search UI` [priority: high]
- `#39` `feat(web): generate dynamic SVG reproducibility badges for GitHub READMEs` [priority: medium]
- `#40` `feat(web): implement exportable PDF and Markdown reproducibility audit reports` [priority: medium]
- `#41` `test(web): add API route tests and schema response validation` [priority: medium]

### M7: Verification Suite & Production Release (Issues #42 – #46)
- `#42` `feat(devops): setup GitHub Actions CI workflow for pull request validation` [priority: high]
- `#43` `feat(corpus): execute full end-to-end verification pilot across all seed papers` [priority: high]
- `#44` `docs(devops): write community contribution guide and paper onboarding specification` [priority: medium]
- `#45` `chore(devops): implement release automation and semantic version tagging` [priority: medium]
- `#46` `feat(devops): conduct comprehensive security audit of container execution boundaries` [priority: high]
