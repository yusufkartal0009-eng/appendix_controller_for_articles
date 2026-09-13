"""Script to provision labels, milestones, and the 45-issue backlog on GitHub."""

import subprocess
import json
import sys
import time

REPO = "yusufkartal0009-eng/appendix_controller_for_articles"

LABELS = [
    ("area:corpus", "5319E7", "Target papers, schemas, datasets, arXiv"),
    ("area:sandbox", "5319E7", "Container runtime, execution drivers, cgroups, timeouts"),
    ("area:scoring", "5319E7", "4-tier scoring, metric alignment, stability, tolerances"),
    ("area:ai", "5319E7", "AI Decision Layer, diagnostics, crash reasoning"),
    ("area:web", "5319E7", "FastAPI REST endpoints, dashboard UI, badges, reports"),
    ("area:devops", "5319E7", "CI/CD pipelines, repository tooling, releases"),
    ("priority:high", "e80707", "Critical path item for current milestone"),
    ("priority:medium", "f3ff47", "Standard milestone priority"),
    ("priority:low", "4fe647", "Non-blocking improvement"),
    ("feat", "0075ca", "New feature or capability"),
    ("fix", "d73a4a", "Bug fix or correction"),
    ("chore", "cfd3d7", "Tooling, maintenance, or configuration"),
    ("testing", "0E8A16", "Test suite or verification coverage"),
]

MILESTONES = [
    "M0: Baseline Hygiene & Audit",
    "M1: Seed Corpus & Relational Data Foundation",
    "M2: Isolated Container Sandbox",
    "M3: Static Code Analysis & Dependency Solver",
    "M4: Empirical Metric Extraction Engine",
    "M5: AI Decision Layer & Diagnostics",
    "M6: Web Dashboard & Reporting Portal",
    "M7: Verification Suite & Production Release",
]

ISSUES = [
    # M0: Baseline Hygiene & Audit (#1 - #5)
    {
        "title": "fix(corpus): remove fabricated entries from the seed paper set",
        "milestone": "M0: Baseline Hygiene & Audit",
        "labels": ["area:corpus", "priority:high", "fix", "bug"],
        "body": """## Problem
Several initial seed paper entries in `data/seed_papers.json` contain synthesized claims or placeholder configurations that must be purged and replaced with 100% genuine, verifiable peer-reviewed paper-repo pairs.

## Wanted
Audit and sanitize the seed paper dataset so that every record maps to an existing, genuine GitHub repository with authentic metrics and reproducible evaluation targets.

## Options
- Option A: Retain only verified papers and replace invalid entries with authentic OpenML/MLSys benchmarks.
- Option B: Drop fabricated entries entirely without replacement.
(Recommendation: Option A - maintain target corpus size while ensuring 100% authenticity).

## Files
- `data/seed_papers.json`
- `tests/test_seed.py`

## Definition of Done
- [ ] Fabricated or synthetic entries purged
- [ ] 100% of papers validated against public arXiv and GitHub links
- [ ] `pytest tests/test_seed.py -v` passes cleanly""",
    },
    {
        "title": "chore(devops): setup commitlint and branch protection ruleset",
        "milestone": "M0: Baseline Hygiene & Audit",
        "labels": ["area:devops", "priority:high", "chore"],
        "body": """## Problem
Commit messages and PR titles require automated grammar enforcement to adhere to conventional commits with declared areas (`feat(area): subject`).

## Wanted
Configure commitlint configuration and GitHub main branch protection ruleset requiring passing checks before merge.

## Options
- Option A: Add commitlint.config.js with projectflow area vocabulary.
- Option B: Shell-based pre-commit git hook.

## Files
- `commitlint.config.js`
- `.github/rulesets/main.json`

## Definition of Done
- [ ] Commitlint grammar configured with `corpus, sandbox, scoring, ai, web, devops`
- [ ] Main branch protection ruleset active""",
    },
    {
        "title": "test(corpus): add automated integrity verification for seed paper schemas",
        "milestone": "M0: Baseline Hygiene & Audit",
        "labels": ["area:corpus", "priority:medium", "testing"],
        "body": """## Problem
Need continuous verification that all records in `data/seed_papers.json` comply with Pydantic v2 schemas and non-empty claim dictionaries.

## Wanted
Automated unit tests validating year ranges, valid HTTP/HTTPS URLs, supported open-source licenses, and numeric metrics.

## Options
- Option A: Dedicated `tests/test_seed.py` test suite.

## Files
- `tests/test_seed.py`

## Definition of Done
- [ ] Schema validation for all seed papers
- [ ] 100% green test execution""",
    },
    {
        "title": "docs(devops): document projectflow operating rules and living docs cadence",
        "milestone": "M0: Baseline Hygiene & Audit",
        "labels": ["area:devops", "priority:medium", "documentation", "chore"],
        "body": """## Problem
Contributors must know the exact cadence for updating living documents (`BLUEPRINT.md`, `PROGRESS.md`, `STACK.md`) and following the propose-approve-implement loop.

## Wanted
Comprehensive operating guidelines codified in `AGENTS.md` and `docs/`.

## Files
- `AGENTS.md`
- `docs/PROGRESS.md`

## Definition of Done
- [ ] Operating rules and guardrails documented in English
- [ ] Living doc cadence approved by maintainer""",
    },
    {
        "title": "chore(corpus): standardize license detection and classification enum",
        "milestone": "M0: Baseline Hygiene & Audit",
        "labels": ["area:corpus", "priority:medium", "chore"],
        "body": """## Problem
Open source licenses need strict SPDX identification to avoid non-compliant or restrictive repositories from being evaluated.

## Wanted
Implement SPDX license validator supporting MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, and CC-BY-4.0.

## Files
- `src/config.py`
- `src/models.py`

## Definition of Done
- [ ] Normalized SPDX license check
- [ ] Unit tests for license validation""",
    },

    # M1: Seed Corpus & Relational Data Foundation (#6 - #11)
    {
        "title": "feat(corpus): implement arXiv API client for paper metadata fetching",
        "milestone": "M1: Seed Corpus & Relational Data Foundation",
        "labels": ["area:corpus", "priority:high", "feat"],
        "body": """## Problem
Paper metadata is currently entered manually; automated ingestion requires querying the public arXiv API for titles, abstracts, published dates, and primary categories.

## Wanted
A resilient arXiv API client with rate-limiting and query caching.

## Files
- `src/corpus/arxiv_client.py`
- `tests/test_arxiv_client.py`

## Definition of Done
- [ ] Fetch paper metadata by arXiv ID
- [ ] Rate-limit compliance (3s interval)
- [ ] Unit tests passing""",
    },
    {
        "title": "feat(corpus): automate GitHub repo availability and clone verification",
        "milestone": "M1: Seed Corpus & Relational Data Foundation",
        "labels": ["area:corpus", "priority:high", "feat"],
        "body": """## Problem
Need to verify whether target GitHub repositories are active, public, and cloneable before scheduling container runs.

## Wanted
HTTP head verification and shallow clone checker for repo availability.

## Files
- `src/corpus/repo_checker.py`
- `tests/test_repo_checker.py`

## Definition of Done
- [ ] Verify HTTP 200 on repo URLs
- [ ] Handle archived or private repos gracefully""",
    },
    {
        "title": "feat(corpus): add PDF claim parser and text extractor",
        "milestone": "M1: Seed Corpus & Relational Data Foundation",
        "labels": ["area:corpus", "priority:medium", "feat"],
        "body": """## Problem
Extracting empirical metric claims from research PDF tables requires structured text extraction.

## Wanted
Lightweight PDF parser extracting numerical claims and table values.

## Files
- `src/corpus/pdf_extractor.py`
- `tests/test_pdf_extractor.py`

## Definition of Done
- [ ] Extract text and tables from paper PDFs
- [ ] Regex extraction of accuracy / loss / F1 metrics""",
    },
    {
        "title": "feat(scoring): implement relational persistence for extracted claims",
        "milestone": "M1: Seed Corpus & Relational Data Foundation",
        "labels": ["area:scoring", "priority:high", "feat"],
        "body": """## Problem
Extracted empirical claims and reproduced values need fine-grained persistence in SQLite `claims` table linked to `runs`.

## Wanted
Complete CRUD operations and ORM relationships for claim records.

## Files
- `src/database.py`
- `src/models.py`

## Definition of Done
- [ ] Save, update, and query claims by paper ID and run ID
- [ ] Cascade delete when paper is removed""",
    },
    {
        "title": "test(scoring): add claim tolerance and relative error test suite",
        "milestone": "M1: Seed Corpus & Relational Data Foundation",
        "labels": ["area:scoring", "priority:high", "testing"],
        "body": """## Problem
Edge cases in relative error calculation (e.g. division by zero, negative values) require thorough test coverage.

## Wanted
Comprehensive pytest coverage for relative and absolute tolerance bounds.

## Files
- `tests/test_scoring.py`

## Definition of Done
- [ ] Zero-division guard tests
- [ ] Exact, partial, and diverged match boundary tests""",
    },
    {
        "title": "feat(devops): add automated database migration script for schema evolution",
        "milestone": "M1: Seed Corpus & Relational Data Foundation",
        "labels": ["area:devops", "priority:medium", "feat"],
        "body": """## Problem
As new tables and columns are added, need a reliable migration mechanism without losing existing benchmark runs.

## Wanted
Lightweight SQLite migration helper or Alembic setup.

## Files
- `src/database.py`
- `scripts/migrate.py`

## Definition of Done
- [ ] Safe idempotent schema evolution
- [ ] Data preservation on table upgrades""",
    },

    # M2: Isolated Container Sandbox (#12 - #17)
    {
        "title": "feat(sandbox): create base Dockerfile for tabular ML benchmarks",
        "milestone": "M2: Isolated Container Sandbox",
        "labels": ["area:sandbox", "priority:high", "feat"],
        "body": """## Problem
Executing paper codebases requires a standardized container image pre-equipped with common Tabular ML and Light NLP runtimes.

## Wanted
Multi-stage Dockerfile based on Python 3.11 with scikit-learn, xgboost, lightgbm, pandas, and numpy.

## Files
- `docker/Dockerfile.sandbox`
- `docker/.dockerignore`

## Definition of Done
- [ ] Optimized image build (< 1GB)
- [ ] Non-root execution user for security""",
    },
    {
        "title": "feat(sandbox): implement container lifecycle manager with cgroup limits",
        "milestone": "M2: Isolated Container Sandbox",
        "labels": ["area:sandbox", "priority:high", "feat"],
        "body": """## Problem
Third-party code must run with hard CPU (2 cores) and memory (8GB) boundaries to prevent resource exhaustion.

## Wanted
Container lifecycle orchestrator handling start, log capture, exit code inspection, and cleanup.

## Files
- `src/sandbox/docker_runner.py`
- `src/sandbox/models.py`

## Definition of Done
- [ ] Launch container with memory and cpu constraints
- [ ] Stream stdout/stderr safely to SQLite logs""",
    },
    {
        "title": "feat(sandbox): enforce zero-network isolation during code execution",
        "milestone": "M2: Isolated Container Sandbox",
        "labels": ["area:sandbox", "priority:high", "feat"],
        "body": """## Problem
Security requires preventing third-party code from communicating externally or leaking host data.

## Wanted
Two-phase execution: network enabled only for dependency downloading, disabled `--network none` during script execution.

## Files
- `src/sandbox/docker_runner.py`

## Definition of Done
- [ ] Network disabled during evaluation phase
- [ ] Outbound connection attempts blocked and logged""",
    },
    {
        "title": "feat(sandbox): implement local subprocess fallback runner for non-Docker hosts",
        "milestone": "M2: Isolated Container Sandbox",
        "labels": ["area:sandbox", "priority:medium", "feat"],
        "body": """## Problem
Development machines lacking Docker Desktop need a functional fallback runner for local execution and testing.

## Wanted
`LocalProcessRunner` operating in a sanitized temporary directory with timeout controls.

## Files
- `src/sandbox/local_runner.py`
- `src/sandbox/runner.py`

## Definition of Done
- [ ] Subprocess execution with timeout watchdog
- [ ] Automatic driver detection (Docker vs Local)""",
    },
    {
        "title": "feat(sandbox): implement execution timeout and memory kill watchdog",
        "milestone": "M2: Isolated Container Sandbox",
        "labels": ["area:sandbox", "priority:high", "feat"],
        "body": """## Problem
Infinite loops or out-of-memory allocations must be terminated promptly at 600s with clear diagnostic messages.

## Wanted
Process watchdog terminating stuck containers and logging `TIMEOUT` or `OOM_KILLED` status.

## Files
- `src/sandbox/watchdog.py`

## Definition of Done
- [ ] Hard kill triggered at 600s timeout
- [ ] SQLite run status updated to `TIMEOUT`""",
    },
    {
        "title": "test(sandbox): add end-to-end sandbox execution tests with mock repositories",
        "milestone": "M2: Isolated Container Sandbox",
        "labels": ["area:sandbox", "priority:high", "testing"],
        "body": """## Problem
Need integration tests validating that container and subprocess runners correctly capture stdout, stderr, and exit codes.

## Wanted
Pytest suite with mock benchmark scripts (success, non-zero exit, timeout).

## Files
- `tests/test_sandbox.py`

## Definition of Done
- [ ] Test clean exit code 0 capture
- [ ] Test failure exit code capture
- [ ] Test timeout termination""",
    },

    # M3: Static Code Analysis & Dependency Solver (#18 - #23)
    {
        "title": "feat(sandbox): build Python AST import scanner for undeclared packages",
        "milestone": "M3: Static Code Analysis & Dependency Solver",
        "labels": ["area:sandbox", "priority:high", "feat"],
        "body": """## Problem
Authors frequently omit dependencies from `requirements.txt` that are imported in Python source files.

## Wanted
AST-based static analyzer scanning target scripts to detect undeclared third-party imports.

## Files
- `src/sandbox/ast_scanner.py`
- `tests/test_ast_scanner.py`

## Definition of Done
- [ ] Scan Python AST for import statements
- [ ] Compare against declared manifests and flag missing packages""",
    },
    {
        "title": "feat(sandbox): implement multi-format manifest parser for requirements and pyproject",
        "milestone": "M3: Static Code Analysis & Dependency Solver",
        "labels": ["area:sandbox", "priority:high", "feat"],
        "body": """## Problem
Research repositories use various dependency formats: `requirements.txt`, `setup.py`, `pyproject.toml`, `environment.yml`.

## Wanted
Unified parser extracting package specifications across all standard formats.

## Files
- `src/sandbox/manifest_parser.py`
- `tests/test_manifest_parser.py`

## Definition of Done
- [ ] Parse `requirements.txt`
- [ ] Parse `pyproject.toml`
- [ ] Parse conda `environment.yml`""",
    },
    {
        "title": "feat(sandbox): build intelligent dependency version solver for unpinned packages",
        "milestone": "M3: Static Code Analysis & Dependency Solver",
        "labels": ["area:sandbox", "priority:medium", "feat"],
        "body": """## Problem
Unpinned packages (e.g. `xgboost` with no version) often break when modern breaking versions are installed.

## Wanted
Solver selecting the closest stable release corresponding to the paper's publication year.

## Files
- `src/sandbox/version_solver.py`

## Definition of Done
- [ ] Pin unversioned packages to release dates matching paper publication year
- [ ] Fallback resolution strategy""",
    },
    {
        "title": "feat(sandbox): add GPU-to-CPU execution flag injection module",
        "milestone": "M3: Static Code Analysis & Dependency Solver",
        "labels": ["area:sandbox", "priority:medium", "feat"],
        "body": """## Problem
Scripts written with hardcoded `cuda` device calls crash in CPU-only evaluation containers.

## Wanted
Static flag injector / environment patcher mapping `device='cuda'` to `device='cpu'`.

## Files
- `src/sandbox/cpu_adapter.py`
- `tests/test_cpu_adapter.py`

## Definition of Done
- [ ] Mock torch.cuda.is_available() -> False or set CUDA_VISIBLE_DEVICES=""
- [ ] Inject `--cpu` argument when supported by script""",
    },
    {
        "title": "feat(sandbox): implement entrypoint script heuristic detection algorithm",
        "milestone": "M3: Static Code Analysis & Dependency Solver",
        "labels": ["area:sandbox", "priority:high", "feat"],
        "body": """## Problem
When no explicit target script is configured, Repro Radar should discover the main benchmark script automatically.

## Wanted
Heuristic discovery prioritizing `run.py`, `main.py`, `eval.py`, `benchmark.py`.

## Files
- `src/sandbox/entrypoint_detector.py`

## Definition of Done
- [ ] Identify executable script from repository file tree
- [ ] Score and rank candidate scripts""",
    },
    {
        "title": "test(sandbox): test dependency resolution on diverse open-source benchmark repos",
        "milestone": "M3: Static Code Analysis & Dependency Solver",
        "labels": ["area:sandbox", "priority:medium", "testing"],
        "body": """## Problem
Dependency resolver must be thoroughly tested across diverse real-world open source projects.

## Wanted
Pytest test cases covering complex manifests and dependency trees.

## Files
- `tests/test_manifest_parser.py`

## Definition of Done
- [ ] Test 5 different real-world manifest formats
- [ ] 100% test pass rate""",
    },

    # M4: Empirical Metric Extraction Engine (#24 - #29)
    {
        "title": "feat(scoring): implement regex-based metric parser for stdout streams",
        "milestone": "M4: Empirical Metric Extraction Engine",
        "labels": ["area:scoring", "priority:high", "feat"],
        "body": """## Problem
Terminal outputs format numbers differently (e.g. `Accuracy: 0.842`, `val_acc=84.2%`, `ROC AUC: 0.89`).

## Wanted
Comprehensive regex pattern matcher extracting common ML evaluation metrics from raw stdout.

## Files
- `src/scoring/regex_extractor.py`
- `tests/test_regex_extractor.py`

## Definition of Done
- [ ] Extract percentage and float formats
- [ ] Normalize keys to standardized metric names""",
    },
    {
        "title": "feat(scoring): build structured output parsers for Scikit-learn and LightGBM logs",
        "milestone": "M4: Empirical Metric Extraction Engine",
        "labels": ["area:scoring", "priority:high", "feat"],
        "body": """## Problem
Many modern benchmarks dump evaluation summaries as JSON, CSV, or MLflow metrics files.

## Wanted
Structured artifact parser inspecting output directories for metric logs.

## Files
- `src/scoring/artifact_parser.py`

## Definition of Done
- [ ] Parse JSON evaluation results
- [ ] Parse CSV metric tables""",
    },
    {
        "title": "feat(scoring): implement multi-seed variance and coefficient of variation calculator",
        "milestone": "M4: Empirical Metric Extraction Engine",
        "labels": ["area:scoring", "priority:high", "feat"],
        "body": """## Problem
Evaluating Tier 3 requires computing mean, standard deviation, and Coefficient of Variation across $N \ge 3$ random seeds.

## Wanted
Statistical utility computing CV and assigning Tier 3 points based on volatility thresholds.

## Files
- `src/scoring.py`
- `tests/test_scoring.py`

## Definition of Done
- [ ] Compute CV = sigma / mu accurately
- [ ] Award points according to rubric tiers (100, 85, 65, 40)""",
    },
    {
        "title": "feat(scoring): build partial-credit tolerance scoring for borderline claims",
        "milestone": "M4: Empirical Metric Extraction Engine",
        "labels": ["area:scoring", "priority:medium", "feat"],
        "body": """## Problem
Borderline results (e.g. 6% error when tolerance is 5%) should earn partial credit rather than dropping to 0.

## Wanted
Linear partial credit decay for errors between tolerance and 2x tolerance.

## Files
- `src/scoring.py`

## Definition of Done
- [ ] Award 0.5 points for results within 2x tolerance
- [ ] Documented in test cases""",
    },
    {
        "title": "feat(scoring): add artifact checksum and reproducibility hash generator",
        "milestone": "M4: Empirical Metric Extraction Engine",
        "labels": ["area:scoring", "priority:low", "feat"],
        "body": """## Problem
Need cryptographic proof that reproduced model weights and evaluation outputs remain immutable.

## Wanted
SHA-256 artifact checksum generator for all generated files and logs.

## Files
- `src/scoring/hasher.py`

## Definition of Done
- [ ] Generate SHA-256 hash manifest for run directory
- [ ] Persist hash in SQLite runs table""",
    },
    {
        "title": "test(scoring): test metric extraction accuracy against noisy console logs",
        "milestone": "M4: Empirical Metric Extraction Engine",
        "labels": ["area:scoring", "priority:high", "testing"],
        "body": """## Problem
Console logs contain warnings, progress bars (tqdm), and debug messages that must not corrupt metric extraction.

## Wanted
Pytest suite validating extraction against noisy, multi-line terminal logs.

## Files
- `tests/test_scoring.py`

## Definition of Done
- [ ] Test extraction with noisy logging and escape codes
- [ ] 100% extraction accuracy on test fixtures""",
    },

    # M5: AI Decision Layer & Diagnostics (#30 - #35)
    {
        "title": "feat(ai): design AI Decision Layer prompt templates for root-cause diagnosis",
        "milestone": "M5: AI Decision Layer & Diagnostics",
        "labels": ["area:ai", "priority:high", "feat"],
        "body": """## Problem
Raw stack traces and metric differences require human-readable synthesis to explain why a reproduction succeeded or failed.

## Wanted
Structured prompts for generating diagnostic summaries based on run logs and metric comparisons.

## Files
- `src/ai/prompts.py`
- `src/ai/diagnostics.py`

## Definition of Done
- [ ] Prompt templates for verified, partial, needs review, and failed runs
- [ ] Neutral language guidelines enforced""",
    },
    {
        "title": "feat(ai): implement automated failure classification for sandbox crash logs",
        "milestone": "M5: AI Decision Layer & Diagnostics",
        "labels": ["area:ai", "priority:high", "feat"],
        "body": """## Problem
Crashes must be categorized automatically into actionable buckets: missing dependency, CUDA error, out of memory, missing dataset.

## Wanted
Rule-based + pattern failure classifier analyzing stderr logs.

## Files
- `src/ai/classifier.py`
- `tests/test_ai_classifier.py`

## Definition of Done
- [ ] Classify common Python runtime errors into failure types
- [ ] Persist failure classification in database""",
    },
    {
        "title": "feat(ai): generate neutral diagnostic rationale reports for evaluated papers",
        "milestone": "M5: AI Decision Layer & Diagnostics",
        "labels": ["area:ai", "priority:high", "feat"],
        "body": """## Problem
Evaluation outcomes must be accompanied by objective explanations that researchers can share with authors.

## Wanted
Automated Markdown rationale generator synthesizing Tier 1-4 results.

## Files
- `src/ai/report_generator.py`

## Definition of Done
- [ ] Markdown summary generated for each evaluated paper
- [ ] Strictly constructive, evidence-based phrasing""",
    },
    {
        "title": "feat(ai): integrate local LLM fallback for unstructured metric matching",
        "milestone": "M5: AI Decision Layer & Diagnostics",
        "labels": ["area:ai", "priority:medium", "feat"],
        "body": """## Problem
Unstructured logs with irregular formatting can elude regex parsers.

## Wanted
Optional local LLM extractor (via llama.cpp / ollama / vLLM) extracting claims as JSON.

## Files
- `src/ai/llm_extractor.py`

## Definition of Done
- [ ] Structured JSON output validation
- [ ] Graceful fallback when local LLM server is offline""",
    },
    {
        "title": "feat(ai): build discrepancy explainer for hardware and floating-point variance",
        "milestone": "M5: AI Decision Layer & Diagnostics",
        "labels": ["area:ai", "priority:medium", "feat"],
        "body": """## Problem
Minor differences between GPU and CPU math or differing BLAS libraries need to be explained neutrally.

## Wanted
Heuristic analyzer flagging likely floating-point or hardware-induced metric shifts.

## Files
- `src/ai/discrepancy_explainer.py`

## Definition of Done
- [ ] Differentiate numerical jitter from systematic algorithm divergence
- [ ] Tag run with `Needs Review` and diagnostic note""",
    },
    {
        "title": "test(ai): validate diagnostic classification accuracy on synthetic failure cases",
        "milestone": "M5: AI Decision Layer & Diagnostics",
        "labels": ["area:ai", "priority:high", "testing"],
        "body": """## Problem
Failure classifier must be tested across real and synthetic error logs to ensure accurate classification.

## Wanted
Pytest suite testing 10+ failure scenarios.

## Files
- `tests/test_ai_classifier.py`

## Definition of Done
- [ ] Correctly classify ModuleNotFoundError, CUDA out of memory, FileNotFoundError
- [ ] 100% test pass rate""",
    },

    # M6: Web Dashboard & Reporting Portal (#36 - #40)
    {
        "title": "feat(web): scaffold FastAPI backend service with REST endpoints",
        "milestone": "M6: Web Dashboard & Reporting Portal",
        "labels": ["area:web", "priority:high", "feat"],
        "body": """## Problem
External clients and web interfaces need REST endpoints to query papers, runs, and reproducibility scores.

## Wanted
FastAPI application exposing `/api/v1/papers`, `/api/v1/scores`, `/api/v1/runs/{id}`.

## Files
- `src/web/app.py`
- `src/web/routes.py`
- `tests/test_web_api.py`

## Definition of Done
- [ ] OpenAPI documentation at `/docs`
- [ ] JSON response schemas matching Pydantic models""",
    },
    {
        "title": "feat(web): build interactive paper leaderboard and benchmark search UI",
        "milestone": "M6: Web Dashboard & Reporting Portal",
        "labels": ["area:web", "priority:high", "feat"],
        "body": """## Problem
Users need a visual interface to search papers, filter by reproducibility status, and view score breakdowns.

## Wanted
Clean web dashboard with sorting, search, and detail modal views.

## Files
- `src/web/static/`
- `src/web/templates/leaderboard.html`

## Definition of Done
- [ ] Search papers by title and venue
- [ ] Filter by status (Verified, Partially Verified, Needs Review, Failed)""",
    },
    {
        "title": "feat(web): generate dynamic SVG reproducibility badges for GitHub READMEs",
        "milestone": "M6: Web Dashboard & Reporting Portal",
        "labels": ["area:web", "priority:medium", "feat"],
        "body": """## Problem
Authors want embeddable badges on their GitHub repositories displaying their verified Repro Radar score.

## Wanted
SVG endpoint `/api/v1/badges/{paper_id}.svg` rendering score and status color.

## Files
- `src/web/badge_generator.py`
- `tests/test_badge_generator.py`

## Definition of Done
- [ ] SVG badge generation with score and color
- [ ] Cached badge responses""",
    },
    {
        "title": "feat(web): implement exportable PDF and Markdown reproducibility audit reports",
        "milestone": "M6: Web Dashboard & Reporting Portal",
        "labels": ["area:web", "priority:medium", "feat"],
        "body": """## Problem
Reviewers need standalone reports for conference submissions or peer review attachments.

## Wanted
Export utility generating self-contained Markdown and PDF audit sheets.

## Files
- `src/web/exporter.py`

## Definition of Done
- [ ] Downloadable Markdown report
- [ ] Complete diagnostic breakdown embedded""",
    },
    {
        "title": "test(web): add API route tests and schema response validation",
        "milestone": "M6: Web Dashboard & Reporting Portal",
        "labels": ["area:web", "priority:medium", "testing"],
        "body": """## Problem
API endpoints must be regression tested for proper status codes and schema fidelity.

## Wanted
FastAPI TestClient test suite testing all endpoints.

## Files
- `tests/test_web_api.py`

## Definition of Done
- [ ] Test GET /papers and GET /scores
- [ ] 100% passing API tests""",
    },

    # M7: Verification Suite & Production Release (#41 - #45)
    {
        "title": "feat(devops): setup GitHub Actions CI workflow for pull request validation",
        "milestone": "M7: Verification Suite & Production Release",
        "labels": ["area:devops", "priority:high", "feat"],
        "body": """## Problem
Pull requests must automatically run unit tests and commitlint checks before merging.

## Wanted
GitHub Actions workflow `.github/workflows/ci.yml` running on push and PR.

## Files
- `.github/workflows/ci.yml`

## Definition of Done
- [ ] Automated test run on PR
- [ ] Commit message linting check""",
    },
    {
        "title": "feat(corpus): execute full end-to-end verification pilot across all seed papers",
        "milestone": "M7: Verification Suite & Production Release",
        "labels": ["area:corpus", "priority:high", "feat"],
        "body": """## Problem
All 18 benchmark papers must undergo live evaluation to validate end-to-end pipeline integrity.

## Wanted
Automated runner executing the 18 seed papers and generating scores in SQLite.

## Files
- `scripts/run_pilot_evaluation.py`

## Definition of Done
- [ ] Complete execution across seed dataset
- [ ] Leaderboard populated with empirical scores""",
    },
    {
        "title": "docs(devops): write community contribution guide and paper onboarding specification",
        "milestone": "M7: Verification Suite & Production Release",
        "labels": ["area:devops", "priority:medium", "documentation"],
        "body": """## Problem
External researchers should be able to submit new papers and reproduction scripts to Repro Radar.

## Wanted
`CONTRIBUTING.md` detailing PR workflow, submission schema, and review expectations.

## Files
- `CONTRIBUTING.md`

## Definition of Done
- [ ] Paper submission template documented
- [ ] Review criteria explained""",
    },
    {
        "title": "chore(devops): implement release automation and semantic version tagging",
        "milestone": "M7: Verification Suite & Production Release",
        "labels": ["area:devops", "priority:medium", "chore"],
        "body": """## Problem
Preparing v1.0 release requires automated changelog generation and Git tagging.

## Wanted
Release script generating release notes from closed milestone issues.

## Files
- `scripts/release.py`

## Definition of Done
- [ ] Semantic version v1.0.0 tagging
- [ ] Automated release notes generated""",
    },
    {
        "title": "feat(devops): conduct comprehensive security audit of container execution boundaries",
        "milestone": "M7: Verification Suite & Production Release",
        "labels": ["area:devops", "priority:high", "feat"],
        "body": """## Problem
Container sandbox must be audited against privilege escalation, disk exhaustion, and unauthorized syscalls.

## Wanted
Security audit report and hardening verification.

## Files
- `docs/SECURITY.md`

## Definition of Done
- [ ] Verify drop-all capabilities in container runtime
- [ ] Document security findings in `docs/SECURITY.md`""",
    },
]


def run_cmd(cmd):
    """Run shell command and return stdout."""
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def main():
    print("=== Step 1: Provisioning GitHub Labels ===")
    for name, color, desc in LABELS:
        code, out, err = run_cmd(f'gh label create "{name}" --color "{color}" --description "{desc}" -R {REPO}')
        if code == 0:
            print(f"  + Created label: {name}")
        else:
            # Try edit if already exists
            run_cmd(f'gh label edit "{name}" --color "{color}" --description "{desc}" -R {REPO}')
            print(f"  = Updated label: {name}")

    print("\n=== Step 2: Provisioning GitHub Milestones ===")
    code, out, err = run_cmd(f'gh api repos/{REPO}/milestones?state=all --jq ".[].title"')
    existing_ms = out.splitlines() if code == 0 and out else []

    for ms in MILESTONES:
        if ms in existing_ms:
            print(f"  = Milestone already exists: {ms}")
        else:
            code, out, err = run_cmd(f'gh api repos/{REPO}/milestones -f title="{ms}"')
            if code == 0:
                print(f"  + Created milestone: {ms}")
            else:
                print(f"  ! Error creating milestone {ms}: {err}")

    print("\n=== Step 3: Creating 45 Backlog Issues on GitHub ===")
    # Fetch current issues to prevent duplicate creation
    code, out, err = run_cmd(f'gh issue list -R {REPO} --state all --limit 100 --json title --jq ".[].title"')
    existing_issues = out.splitlines() if code == 0 and out else []

    created_count = 0
    for idx, item in enumerate(ISSUES, 1):
        title = item["title"]
        if title in existing_issues:
            print(f"  = Issue already exists: #{idx} {title}")
            continue

        milestone = item["milestone"]
        labels_str = " ".join([f'--label "{l}"' for l in item["labels"]])
        body = item["body"].replace('"', '\\"')

        cmd = f'gh issue create -R {REPO} --title "{title}" --milestone "{milestone}" {labels_str} --body "{body}"'
        code, out, err = run_cmd(cmd)
        if code == 0:
            created_count += 1
            print(f"  + Created Issue #{idx}: {title} -> {out}")
        else:
            print(f"  ! Error creating issue #{idx} ({title}): {err}")
        time.sleep(0.5)  # Respect API rate limits

    print(f"\nSuccessfully provisioned {created_count} issues on GitHub repository!")


if __name__ == "__main__":
    main()
