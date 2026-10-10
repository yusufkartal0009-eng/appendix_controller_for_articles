# Repro Radar — Living Progress Log

> This document is updated after every milestone, issue, or PR to maintain full project memory.

---

## Current Status (2026-10-03 20:55 +03:00): 2026-10-01 Plan Recorded, Stage 0b and Stage 1 Next

- **Work order:** `docs/PLAN_2026-10-01.md` (continues `docs/ROADMAP_2026-09-27.md`). Stage 0 is done (#167, #168; decisions D-004 to D-007). Next: the D0 dashboard skeleton (#170, stage 0b) and claim extraction steps 1.1-1.3 (#131, #162).
- **Pilot 1** (`docs/PILOT_WEEK2.md`): pilot success 0 / 6, install success 1 / 6, run success 0 / 6. Pilot 2 (#171) runs on the owner's machine once Docker is installed (#172).
- **Claim extraction:** W1 schema (#129), W2 PDF text (#130), W3 API extractor (#131, PR #156; never called, no key), and W4 quote guard (#132) are merged. Extraction is now agent-assisted, with no API key (D-004). No extracted claim has been approved yet.
- **CLI:** `cli.py score` still produces simulated numbers (GA-2, #136, stage 3).
- **Planned Milestones:** M0 to M7 (45 trackable issues cataloged in `docs/BLUEPRINT.md`)
- **Functional Areas:** `corpus`, `sandbox`, `scoring`, `ai`, `web`, `devops`
- **Tests:** 321 passed, 8 skipped locally (Windows; network and POSIX-only tests skip). CI: Ubuntu, Windows, sandbox image, corpus verification, and real-Docker sandbox acceptance with 20 checks for each of the Python 3.11, 3.9, and 3.8 images

---

## Milestone Roadmap & Progress

Issue numbers and open/closed counts match GitHub as of 2026-10-03 20:55 +03:00 (issues only, not PRs), counted with #175 closed by its PR. Backlog ranges are the per-issue items listed in `docs/BLUEPRINT.md`; partly implemented open issues carry a status note on GitHub. Open/closed also includes issues added after the backlog (e.g. M2: #48, #80, #86, #88, #90, #92).

| Milestone | Focus | Backlog issues | Open / closed | Status |
|---|---|:---:|:---:|:---:|
| **M0: Baseline Hygiene & Audit** | Seed audit, projectflow adoption, hygiene tests | #2 – #6 | 4 / 19 | IN PROGRESS |
| **M1: Seed Corpus & Relational Data Foundation** | ArXiv ingestion, repo verification, claims schema | #7 – #12 | 12 / 8 | IN PROGRESS |
| **M2: Isolated Container Sandbox** | Docker runner, cgroups, network isolation, timeout | #13 – #18 | 9 / 12 | IN PROGRESS |
| **M3: Static Code Analysis & Dependency Solver** | AST scanner, manifest parser, unpinned solver, GPU flags | #19 – #24 | 10 / 1 | QUEUED |
| **M4: Empirical Metric Extraction Engine** | Regex log parsers, stdout extraction, multi-seed CV, rubric | #25 – #30, #55 | 3 / 5 | IN PROGRESS |
| **M5: AI Decision Layer & Diagnostics** | Failure classifier, neutral reports, discrepancy explainer | #31 – #36 | 6 / 1 | QUEUED |
| **M6: Web Dashboard & Reporting Portal** | FastAPI REST API, leaderboard UI, SVG badges, PDF reports | #37 – #41 | 6 / 0 | QUEUED |
| **M7: Verification Suite & Production Release** | Pilot verification, contribution guide, CI/CD, v1.0 release | #42 – #46 | 6 / 12 | IN PROGRESS |

The weekly "Hafta 1–7" milestones were retired on 2026-09-25: their umbrella issues (#47 – #53) were closed as completed or as duplicates of the backlog above and moved into the matching M milestones.

---

## Changelog & Completed Work

### Bundling Inside the Sandbox Image (found by the first Pilot 2 attempt) (2026-10-10 14:49 +03:00, Issue #215)
- First Pilot 2 attempt on the owner's Windows machine (`paper_008`, kept in `data/pilot2_runs/first_attempts/paper_008_attempt1/`): the install phase failed with `Could not find a version that satisfies the requirement cuda-toolkit==13.0.3; platform_system == "Linux"`. Host-side `pip download` evaluated environment markers for Windows and the host's Python, not the sandbox's. With `RepoStager(bundle_in_docker=True)` (used by `run_pilot.py --pilot2`) the download runs inside the paper's sandbox image (binary wheels only), and the bundle for `paper_008` went from 34 to 52 wheels, now including `cuda_toolkit-13.0.3.0`. Pilot 1's mode and the host path are unchanged. `.sandbox_staging/` is git-ignored.

### Pilot 2 Environment and the Real GPU Check (2026-10-10 14:30 +03:00, Issues #213 and #169)
- `scripts/record_pilot2_environment.py` wrote `data/pilot2_runs/environment.txt` from command output (commit, `docker version` and `info`, `nvidia-smi`, `gpu_check.py`, images, disk). On this machine `gpu_check.py` showed the RTX 5070 (driver 591.86) inside the sandbox container with uid 1000, the network blocked, and a read-only root: `GPU visible with isolation intact: YES`. `data/pilot2_runs/` is no longer git-ignored, so the Pilot 2 evidence can be committed.

### Entrypoint Kept in LF; First Real-Docker Run on Windows (2026-10-10 14:29 +03:00, Issue #211)
- On the owner's Windows machine (`core.autocrlf=true`) the container entrypoint was CRLF and every container failed with `env: 'bash
': No such file or directory` (19 of 20 acceptance checks failed). `.gitattributes` now keeps `*.sh` and `docker/Dockerfile*` in LF, and a test fails on CRLF. After rebuilding the six images, the acceptance checks pass on this machine: 20/20 on Python 3.11, 3.9, and 3.8. GitHub Actions is disabled by the owner, so these local runs are the evidence.

### Report Sections Written: Introduction, Method, Experimental Setup (2026-10-07 19:47 +03:00, Issue #120)
- `docs/report/REPORT.md` sections 2, 4, and 5 are written from evidence already in the repository: the
  sourced introduction draft (#118/#119), the sandbox threat model and four-tier score (`docs/SANDBOX_ACCEPTANCE.md`,
  `src/config.py`, `src/scoring.py`, `src/validation_rubric.py`), the claim extraction pipeline (W1-W7, gold-set
  precision/recall 1.0/1.0), and the corpus's 18→8→6 history with its automated verification (6/6 pass).
- Corrected section 6 (Results)'s own needs list: the gold set (#133) is filled now, so Results is blocked on
  Pilot 2 alone, not three things.
- Not written: Related work (needs a separately verified external source list) and anything needing Pilot 2
  data (Results, Limitations, Lessons learned, Conclusion).

### Stale Umbrella Issue #9 Closed (2026-10-07 19:39 +03:00, Issue #9, housekeeping)
- All 8 checklist items (#129 W1, #130 W2, #131 W3, #132 W4, #133 W5, #10 W6, #134 W7, #135 closing step) were
  already closed; the Definition of Done (claims extracted and quote-verified, gold-set precision/recall,
  EP3602/HIGGS regression cases returning "not found") is satisfied. Closed as done, no code change. This also
  clears one of the two issues #136 names as a precondition (the other, #43, was already closed).

### Pilot 2 Output Location Fixed (2026-10-07 19:31 +03:00, Issue #207)
- `--pilot2` now writes `pilot_record.json` into `data/pilot2_runs/<paper_id>/`, as `docs/PILOT_2.md` section 6
  asks, instead of `sandbox_runs/<paper_id>/` (where PR #206 left it — that gap was not named in #205 or #206).
  `scripts/run_pilot.py`'s new `_collect_pilot2_files` copies the protocol's other named files (`run_report.json`,
  `execution_meta.json`, `install.log`, `install_meta.json`, `build.log`, `stdout.log`, `stderr.log`) from their
  sandbox locations into the same directory, skipping any that do not exist yet. `src/sandbox/runner.py` and
  `stager.py` are untouched: they still write under `sandbox_runs/`, shared with Pilot 1 and real-Docker CI.
- Pilot 1's output location and mode are unchanged.
- Tests: 2 new (full completion copies exactly the files the protocol names, plus a staging failure); the 3
  existing Pilot 2 tests updated to assert the new location; all 18 Pilot 1 tests untouched. Full suite:
  319 passed, 6 skipped; `ruff check` clean.
- `data/pilot2_runs/` added to `.gitignore` (next to `sandbox_runs/`): run output, not something to commit.
- **Not verified:** no real Docker run (no Docker on this machine yet, #172). While testing, an intermediate
  (uncommitted) run of the old test file wrote real files into `data/pilot2_runs/`; found via `git status`
  (untracked) and deleted before committing.

### Pilot 2 Driver (no run) (2026-10-05 22:36 +03:00, Issue #205, plan step 2.9)
- `python scripts/run_pilot.py <paper_id> --pilot2` runs a paper with its `run_setup` (build phase, extras and constraints, working directory, writable copy, data mounts, command); Pilot 1's mode is unchanged. A missing data cache is a harness error naming `scripts/fetch_data.py`; a failed build ends the paper before install and is recorded. Fake-stager tests only: no paper was run.

### Seed Claim Values Replaced by Accepted Claims (2026-10-05 22:12 +03:00, Issue #135, plan step 1.8)
- The owner accepted all 12 extracted claims one by one (`data/claims/review_decisions.json`). `scripts/apply_accepted_claims.py` wrote them into `expected_claims` of `data/seed_papers.json` (old values kept under `seed_claims_before_extraction`; `check` fails on disagreement). `paper_005` has no accepted claim (all its questions were answered "not in the paper") and stays in the corpus. `docs/CORPUS_VERIFICATION.md` section 6 replaces the UNVERIFIED/SUSPECT status. Three tests were adjusted to accepted-only claims.

### Gold Set and Extraction Precision/Recall (W5) (2026-10-05 21:02 +03:00, Issue #133, plan step 1.5)
- The owner filled the gold set form question by question (18 questions, 6 papers): `tests/data/gold_claims/paper_*.json` (`made_by: owner`, written by `scripts/evaluate_gold.py from-form`, no `needs_decision`). Pass A scored by `scripts/evaluate_gold.py score --pass A` (`data/claims/gold_score_pass_A.json`): TP 12, FP 0, FN 0, TN 6, precision 1.0, recall 1.0; the regression cases EP3602 (AUROC, accuracy) and HIGGS are all TN. Caveat: the form's candidate values were listed by the same agent that extracted pass A, so a value it never found could only enter through "other"; pass B is not independent yet.

### Final Report Skeleton (2026-10-05 18:22 +03:00, Issue #120, step R2)
- `docs/report/REPORT.md`: the 10 sections of #120, each with its one-line purpose, what it needs, and its status. No section body is written; sections are written only when their evidence exists.

### Pilot 2 Protocol (no run) (2026-10-05 18:17 +03:00, Issue #171, plan step 2.9)
- `docs/PILOT_2.md`: Pilot 1's definitions, limits, and failure categories unchanged; runs on the owner's machine (Docker Desktop, WSL2) with each paper's `run_setup`; counted run CPU-only; build phase added to the failure order; Pilot 1's 0 / 6 shown alongside. Written before any Pilot 2 run. STOP before the first run: the owner confirms Docker (#172) and approves the protocol; `paper_002`'s network question (#193) is open.

### Opt-in Local GPU (code only) (2026-10-05 18:09 +03:00, Issue #169, plan step 2.6)
- `SandboxConfig.gpus` (`all`, a count, or `device=<ids>`; validated) adds `docker run --gpus` and nothing else; the default stays without a GPU, and the local fallback refuses a GPU run. The entrypoint records the visible GPUs and samples GPU memory during the run; `run_report.json` gets a `gpu` summary (available, used). `scripts/gpu_check.py` shows the GPU inside the sandbox with the isolation checks; acceptance check 20 shows the GPU is off by default. **Not verified:** no real GPU run (this machine has no Docker; GitHub's runners have no GPU).

### Gold Set Form Reader and Precision/Recall (W5) (2026-10-05 18:05 +03:00, Issue #133, plan step 1.5)
- `scripts/evaluate_gold.py from-form` reads the owner's filled gold set form by its structure (checkboxes, backtick values, the free "other" answer, "not in the paper") into `tests/data/gold_claims/<paper_id>.json`, reporting unclear answers as `needs_decision`; `score` gives TP/FP/FN/TN, precision, recall, and the EP3602/HIGGS regression cases. On the real form it found all 18 questions, none filled yet. No gold value was chosen and no precision/recall number exists yet.

### Human Review of Extracted Claims (W7) (2026-10-05 17:50 +03:00, Issue #134, plan step 1.7)
- `python cli.py review-claims [paper_id]` shows each pending claim with its provenance and asks accept / reject / skip / quit (optional note); each decision is committed at once with `verified_by = human`. `--list` shows the review status without asking. `claims_for_scoring` (`src/claim_review.py`) returns only accepted claims. No claim has been accepted or rejected; that is the owner's step.

### Extracted Claims Stored with Provenance (W6) (2026-10-05 17:49 +03:00, Issue #10, plan step 1.6)
- New table `extracted_claims` (`data/schema.sql`, `ExtractedClaimORM`): page, table or section, quote, source file, PDF hash, extractor version, `verified_by` (`auto-quote-match` = quote guard matched, not an approval; `human` = a person decided), and the review status. The database refuses a non-pending claim without `verified_by = 'human'`. `src/claim_store.py` saves, updates, queries (by paper, review status, and run), and records reviews; `accepted_claims` is what may reach the scorer. `scripts/import_claims.py` imports pass A as 12 `pending` claims. No claim has been accepted.

### Build Phase and the Open Run-Setup Items (#193) (2026-10-05 17:41 +03:00, Issue #193)
- Finding: `openml` (0.11.0 and 0.12.2) and `liac-arff` exist on PyPI only as sdists, so `paper_002` and `paper_006` could not install with the binary-only install phase. New isolated **build phase** (D-008): sdists downloaded from the PyPI JSON API with a SHA-256 check (never run on the host), built into wheels in the build image (`docker build --target build`) with the network off; the install phase stays binary-only. Run setups gained `build`, `extra_requirements`, `constraints`, and writable data copies; OpenML datasets are fetched over HTTP (MD5-checked). `paper_005`: Python 3.8, `fastsk` built from the repository, unpinned packages limited to their newest release before the pinned commit's date (resolves for Python 3.8, pip dry run). `paper_006`: offline load of dataset 1461 by openml 0.11.0 shown on the host with sockets blocked. Real-Docker acceptance checks 18 (build phase) and 19 (writable data copy). Still open: `paper_002` lists its datasets through the OpenML API at run time, which needs network (owner decision). Not verified: no paper run (Pilot 2, #171).

### Docker Detection Tolerates Slow Runners (2026-10-05 17:15 +03:00, Issue #164, plan step 2.8)
- `DockerSandboxRunner.is_docker_available` asks `docker info` up to 3 times (15 s each, 2 s apart) instead of once for 5 s; worst case 49 s for a daemon that never answers. A missing Docker CLI still fails at once, and a daemon that stays unavailable is still refused (`tests/test_docker_detection.py`; real-Docker check 6 unchanged).

### Image Size and CPU Limit Measured (2026-10-04 21:58 +03:00, Issue #163, plan step 2.7)
- Real-Docker acceptance checks 16 and 17 (CI run 37224145290). Image sizes: 477.1 MiB (Python 3.11), 451.2 MiB (3.9), 417.1 MiB (3.8). Under `--cpus=0.5`, two busy workers got 0.49 CPUs together; the control at the runner's 2 CPUs got 1.97. `docs/SANDBOX_ACCEPTANCE.md` regenerated from that run (it now also lists check 15 from #166).

### Paper Run Setups: Fix, Do Not Replace (2026-10-04 21:15 +03:00, Issue #166, plan step 2.5)
- Owner decision: no paper is replaced. `paper_002`–`paper_006` get a `run_setup` in `data/seed_papers.json`; `paper_008` is kept and reported as `DATA_NOT_ACCESSIBLE` (its split files are not published). The decisions and what is still open are in `docs/CORPUS_VERIFICATION.md` section 5. The sandbox gained a repository-relative working directory, a writable per-run copy of the repository, read-only data mounts from a host cache (`scripts/fetch_data.py`), and a command that replaces the target script (real-Docker acceptance check 15). Not verified: no paper has been run with its run setup (Pilot 2, #171). Open: `paper_002` (nbconvert, OpenML-CC18 list), `paper_005` (C++ build, dateutil conflict), and `paper_006` (offline OpenML cache).

### Installed Versions Recorded (2026-10-04 19:08 +03:00, Issue #161, plan step 2.4)
- The install phase writes `installed_packages.json` (`pip list --path /workspace/deps`). `run_report.json` gets `installed_packages` and `requested_vs_installed`: per requirement (or converted conda pin), the requested specifier, the installed version, whether it satisfies the request, and whether it was pinned. This makes drift like `paper_008`'s `torch>=1.4.0` → `2.7.1` visible. `packaging` is now a runtime dependency. Real-Docker acceptance check 14.

### Dependency Conflicts Named in the Reports (2026-10-04 19:04 +03:00, Issue #160, plan step 2.3)
- `src/sandbox/dependency_conflicts.py` parses pip's "Cannot install ... conflicting dependencies" blocks and their "caused by" lines; `-r <file> (line N)` is replaced by that line's text from the staged repository. The bundle report (from the full pip output; pip prints the cause lines to stdout) and `run_report.json` (from `install.log`) now carry `dependency_conflicts`. On Pilot 1's real `paper_005` log: `pandas 3.0.6 depends on python-dateutil>=2.8.2` vs. the pinned `python-dateutil==2.8.1`.

### Conda-Only Repositories Bundled Offline (2026-10-04 18:53 +03:00, Issue #159, plan step 2.2)
- `src/sandbox/conda_env.py` converts a conda environment file into pinned pip requirements (conda-to-pip name map; system, CUDA, and `_`-internal packages skipped with reasons; the file's Python version read). Conda itself is not run. A conda-only repository is bundled one requirement at a time with `pip download --no-deps` (binary only); packages without a wheel are reported as `conda_only`. Real files: `paper_004` → Python 3.9, 300 requirements (114 skipped); `paper_006` → Python 3.8, 156 requirements (37 skipped).
- Python 3.9 image added (`paper_004`); `paper_004` → 3.9 and `paper_006` → 3.8 in `data/seed_papers.json`. `pyyaml` is now a runtime dependency. New real-Docker acceptance check 13 (conda-only repository: bundle, offline install, import). Re-running `paper_004`/`paper_006` is left for Pilot 2 (#171).

### Python Version per Paper (2026-10-04 18:48 +03:00, Issue #158, plan step 2.1)
- `docker/Dockerfile.sandbox` takes `--build-arg PYTHON_VERSION` (3.11 and 3.8). `SandboxConfig.python_version` selects the image (`repro-radar-sandbox:latest` for 3.11, `repro-radar-sandbox:py3.8`) and the site-packages path; bundling downloads wheels for that version; `run_report.json` records `python_version` and `image`.
- `data/seed_papers.json`: `paper_002` and `paper_003` run on Python 3.8 (`python_version` with its source); the others stay on 3.11 (`paper_004`/`paper_006` are conda-only, #159). The pilot runner follows the field.
- CI runs the real-Docker acceptance checks for both images. Re-running `paper_002`/`paper_003` in real Docker is left for Pilot 2 (#171): no local Docker yet (#172).

### Blind Packet for an Independent Pass B (2026-10-04 18:41 +03:00, Issue #186)
- `scripts/make_blind_packet.py` writes a self-contained folder outside the repository (questions, rules, a schema description without real values, the pinned PDFs' page text, an answer template, and a README with the prompt) for a new session that cannot see pass A. `scripts/import_pass.py` checks the filled answers (schema, quote on the cited page) and stores them as pass B. A packet was generated at `C:\Users\USER\blind_pass_b` (6 papers, 18 questions); a leak check found none of the 12 stored answer values outside the paper texts.

### Owner Decisions Applied to the Extractions (2026-10-04 18:35 +03:00, Issue #184)
- TabPFN time split into GPU (`0.6172`) and CPU (`37.59`) claims; DANet Forest split into DANet-20 (`97.23%`) and DANet-32 (`97.27%`); TabR's rank moved to Table 4 (`1.3± 0.9`), the table that also ranks XGBoost (`2.5± 0.9`); XGBoost RMSE `0.433` accepted by the owner. 18 questions now; both passes revised; 18/18 agree; 24/24 found claims `AUTO_QUOTE_MATCH`. Decisions recorded in `data/claims/owner_decisions.json` and as rule 9 of `docs/AGENT_EXTRACTION.md`.

### Quote Guard Run on the Extractions (2026-10-04 15:32 +03:00, Issue #182, plan step 1.4)
- `scripts/check_claims.py` runs the W4 guard (with the #162 repair) on every found claim of passes A and B against the pinned PDFs and writes `data/claims/guard_report.json`/`.md`. Result: 18 of 18 found claims `AUTO_QUOTE_MATCH` (all `exact`), 0 `UNVERIFIED`; all 18 come from tables, so all go to the owner in W7. A pass shows the quote is on the page, not that the value answers the question.

### Split Numbers Repaired, Table Claims Flagged (2026-10-04 15:29 +03:00, Issue #162, plan step 1.3)
- `src/pdf_text.py`: `repair_split_numbers()` joins numbers pypdf split before the decimal point (`0 .850` → `0.850`); 1,213 occurrences in the seed PDFs (`paper_003` 226, `paper_004` 986, `paper_006` 1). The quote guard compares after the repair on both sides (match mode `split_numbers_repaired`), so a correctly retyped value is no longer rejected.
- Table claims are flagged (`from_table`) and always go to the owner in W7; table structure is not reconstructed. Documented in `docs/PDF_TEXT_EXTRACTION.md` and `docs/CLAIM_SCHEMA.md`.

### Extraction Passes Compared (2026-10-04 15:25 +03:00, Issue #179, plan step 1.2)
- `scripts/compare_extractions.py` compares passes A and B by normalized value (D-005) and writes `data/claims/consistency.json`/`.md`. Result: 16 of 16 questions agree, 0 disagreements. Because pass B is not independent of A (#178), this agreement is expected and weak evidence; correctness is decided in steps 1.4, 1.5, and 1.7.

### Agent-Assisted Claim Extraction, Two Passes (2026-10-04 15:22 +03:00, Issue #131, plan step 1.1)
- 16 questions (one per seed claim, written without the seed values) in `data/claim_queries/` for all 6 papers; pinned PDFs (arXiv `2207.01848v6`, `2106.11959v5`, `2307.14338v2`, `2106.01342v1`, `2112.02962v4`; bioRxiv `2020.04.21.053975v2`).
- `docs/AGENT_EXTRACTION.md`: the rules (same as the API prompt, plus a rule for values printed in several places) and how independent the two passes are.
- `data/claims/<paper_id>.json`: passes A and B. Both: 9 found, 7 not found (EP3602 x2, Figure 4 speedup, FT-Transformer rank in TabR, Bank accuracy in SAINT, DANet Forest row ambiguous, HIGGS). **Pass B is not independent:** same agent, same session (owner's instruction, no subagent); its re-search confirmed every A answer, so its values were taken over from A. Not approved: the quote guard (W4) and the owner (W5, W7) decide.

### D0 Dashboard Skeleton (2026-10-04 13:00 +03:00, Issue #170, plan stage 0b)
- `src/web/app.py`: FastAPI app with `GET /api/v1/papers` (a real SQLAlchemy query: catalog fields plus each paper's latest run; an empty database gives `[]`) and a server-rendered page in the owner's chosen design (option A: light, plain table, system font). Seed claim values are never exposed (unverified). `python -m src.web` serves it on `127.0.0.1` only (D-006).
- The owner chose option A out of three previews on 2026-10-04 (`AGENTS.md` §6.9). Screenshots of an empty, a one-row, and the local database are in `docs/evidence/d0/`.
- The local database was rebuilt from the current `data/seed_papers.json` (`cli.py init-db --reset`, then `scripts/load_pilot_runs.py`): 6 papers and their 6 pilot runs; the removed `paper_001` and `paper_007` are gone. The database file is not tracked.
- `fastapi`, `uvicorn` (runtime) and `httpx` (tests) added. 6 tests in `tests/test_web_app.py`.

### Agents Point at the 2026-10-01 Plan (2026-10-03 20:55 +03:00, Issue #175)
- `AGENTS.md` (living docs list, traceability line, §6.1 and §6.3) and `CLAUDE.md` now point at `docs/PLAN_2026-10-01.md` as the current work order; §6.3 states the plan's stage order. The status summary above, the milestone counts, and the `docs/DECISIONS.md` header were refreshed.
- On the owner's decision: the unmerged gold-set branch `test/issue-133-gold-set` (`7b3dcbc`) was closed without merging; the merged old branches `chore/devops/adopt-projectflow` (PR #1) and `feature/issue-0-translate-to-english` (PR #56) were deleted; #131 was reopened for plan steps 1.1-1.2.

### 2026-10-01 Plan Decisions Recorded (2026-10-02 12:22 +03:00, Issue #168, plan item 0.2)
- `docs/DECISIONS.md` D-004 to D-007: agent-assisted extraction without an API key (the API code stays); "temperature 0" replaced by the rule that two independent extractions must agree on the normalized numbers, with every mismatch going to the owner in W7; everything runs locally (dashboard on `localhost`, paper runs on the owner's machine, GitHub Actions only for CI); papers that cannot run may be replaced, with a recorded reason and Pilot 1's 0 / 6 kept. D-003 is marked as partly superseded.

### 2026-10-01 Plan Recorded (2026-10-02 12:18 +03:00, Issue #167, plan item 0.1)
- `docs/PLAN_2026-10-01.md`: complete English translation of the 2026-10-01 work plan (decisions, owner tasks Y1-Y5, stages 0-5, the work loop, the summary order), with the issue number next to every item. `docs/ROADMAP_2026-09-27.md` now starts with a link to it; nothing else there changed.
- New issues opened for the items without a number: #167 (0.1), #168 (0.2), #169 (0.3, local GPU), #170 (D0 dashboard skeleton), #171 (Pilot 2), #172 (Y1, owner installs Docker).

### Verbatim Quote Guard (2026-10-01 21:04 +03:00, Issue #132, W4)
- `src/quote_guard.py`: a claim becomes `AUTO_QUOTE_MATCH` only if its PDF hash matches, its page exists, its quote and printed value occur on that page with identical characters (whitespace runs count as one space), and its dataset and model occur in the paper as whole words. Otherwise it stays `UNVERIFIED` with the reasons. `scorable_claims()` returns only verified claims.
- Rules documented in `docs/CLAIM_SCHEMA.md` section 5; 11 tests, including a matching and a non-matching quote, the `0.859`/`0 .859` case, and the invented `EP3602` dataset.

### Claim Extraction with Claude (2026-10-01 20:57 +03:00, Issue #131, W3)
- `src/claim_extraction.py`: query-driven extraction with Claude Opus 5.5 (owner's choice), JSON-schema output, a mandatory verbatim quote and PDF page, and an explicit "not found" instead of guessing. `value_normalized` is computed by the schema rule. Responses are cached by a hash of model, prompt, schema, PDF, and queries (`data/llm_cache/`, not committed). Usage and estimated cost are recorded, and a server-side refusal fallback is enabled and recorded.
- `docs/DECISIONS.md` D-003: why there is no temperature setting (Opus 5.5 rejects it) and what gives repeatability instead (cache, W4 quote guard, W7 human check).
- `scripts/extract_claims.py` with `data/claim_queries/paper_003.json` (pinned PDF `2106.11959v5`; queries without the seed values). `anthropic` is a runtime dependency. Tests use a fake client; no API call was made yet, because `ANTHROPIC_API_KEY` was not visible to the session.

### Lint Backlog Cleared (2026-10-01 20:39 +03:00, Issue #139, GA-11)
- The CI lint gate is now ruff's default rule set plus the first gate's rules (`pyproject.toml`). Findings went from 393 (ruff 0.16.9 defaults) to 0. `ruff --fix` applied 375 fixes; the remaining 38 were handled by hand: 12 explicit `check=False`, 10 renamed unused test variables, 7 small simplifications, and 9 deliberate broad exception handlers marked `# noqa: BLE001` with their reason.
- Behavior unchanged: 164 passed, 8 skipped before and after. The untested `cli.py` and scripts compile and run `--help` (and `cli.py list-papers`).
- Started ahead of the binding order (`AGENTS.md` §6.3) at the owner's explicit request.

### Coverage Re-measured (2026-10-01 20:32 +03:00, Issue #138)
- Line coverage on the GA-5 baseline scope (`src`, `cli.py`, `scripts`) is 79% (2598 statements, 557 missed), up from 60%; `src/` alone is 87% (1379 statements, 180 missed), locally and in CI. `cli.py` is still 0%. Recorded in `docs/gap_analysis.md` (section 2 and GA-5).
- Started ahead of the binding order (`AGENTS.md` §6.3) at the owner's explicit request.

### Generated Introduction No Longer Committed (2026-10-01 20:28 +03:00, Issue #137, GA-15)
- `docs/repro_radar_introduction.docx` and `docs/assets/repro_radar_banner.png` are build outputs of `scripts/generate_academic_introduction_doc.py`: removed from version control and ignored. The script has an `--output-dir` option.
- `tests/test_academic_doc.py` generates the document into a temporary directory on every run, and the CI test job uploads the generated `.docx` as the `introduction-docx` artifact.
- Started ahead of the binding order (`AGENTS.md` §6.3: section 6 comes last) at the owner's explicit request.

### PDF Text Extractor (2026-10-01 19:18 +03:00, Issue #130, W2)
- `src/pdf_text.py`: page-by-page text with 1-based PDF page numbers (`pypdf`, now in `requirements.txt`), cached as `data/pdf_text_cache/<sha256>.json` keyed by the PDF bytes (not committed). `PdfText.find()` lists the pages that contain a string verbatim.
- Real paper check (`paper_003`, arXiv 2106.11959v5, 25 pages): `FT-T 0.459` is on PDF page 7, as recorded in `docs/CORPUS_VERIFICATION.md`. First extraction 0.56 s, cached 0.010 s.
- `docs/PDF_TEXT_EXTRACTION.md` documents the limitations, with that page as the example: table rows become single lines without column structure, `pypdf` inserts spaces inside numbers (`0 .850`), formatting is lost, scanned pages have no text, and figures are not read.

### Claim Schema (2026-10-01 19:06 +03:00, Issue #129, W1)
- `docs/CLAIM_SCHEMA.md`: the twelve fields of an extracted claim with type and meaning, the normalization rule (`96.99 %` → `0.9699`, computed in decimal), the claim set per exact PDF (`pdf_sha256`), explicit "not found" answers (regression cases EP3602 and HIGGS), and what W4/W6 add later.
- `src/claim_schema.py`: the same schema as Pydantic models (`ExtractedClaim`, `ClaimSet`, `NotFound`) and `normalize_value()`. A claim is rejected if its normalized value does not follow the rule or its quote does not contain the printed value.
- `tests/test_claim_schema.py`: the documented fields, units, splits, and examples equal the code; invalid values and claims are rejected.

### UI Decision Rule (2026-10-01 18:53 +03:00, Issue #149)
- `AGENTS.md` §6.9: UI decisions (layout, colors, fonts, leaderboard, filters, detail page, badge design, report layout) are asked to the owner with 2-3 options and a preview before they are implemented.

### Pilot Cleanup (2026-09-30 21:54 +03:00, Issue #128, P7; closes the pilot umbrella #43)
- Evidence review of #48 and #13-#18 against the 12 acceptance checks and the pilot runs; each issue has a comment with its status. Only #16 gained a tick: the timeout watchdog, backed by `test_process_sandbox_runner_timeout`. Its "automatic driver detection" box is annotated as replaced by design in #80.
- Still open, with the missing evidence named: #48 (multi-seed execution not implemented), #13 (image size not recorded), #14 (logs reach SQLite only after the run, via the loader), #15 (blocked network attempts are not logged), #17 (no kill at the 600 s default, no stored `TIMEOUT` row), #18 (no automated test for a failing exit code).
- Status and milestone counts at the top of this file refreshed from GitHub.

### Pilot Report (2026-09-30 21:50 +03:00, Issue #127, P6)
- `docs/PILOT_WEEK2.md` section 11: pilot success 0 / 6, install success 1 / 6, run success 0 / 6, all 6 runs valid. Most frequent category `MISSING_DEPENDENCY` (5 of 6), with three causes: old pins without Python 3.11 wheels, a conflict inside the requirements, and conda-only repositories. What was surprising, proposed sandbox changes (Python version per paper first), and limits (n = 6 is anecdotal).
- The tables are pasted from the generated files, and `tests/test_pilot_report.py` fails if they drift. The document's status note was updated; the frozen protocol text is unchanged.

### Pilot Dataset Findings (2026-09-30 21:47 +03:00, Issue #126, P5)
- `docs/PILOT_WEEK2.md` section 10: for each paper, whether it downloads data, what, how large, under which license, and what happened in the pilot, each with its source. Largest downloads: `paper_003` 4.07 GiB (Dropbox) and `paper_004` 2.88 GiB (Hugging Face). `paper_005` ships 41.3 MiB in the repository.
- `paper_008`'s loader needs split files (`train_idx.csv`, `valid_idx.csv`, `test_idx.csv`) that are not published.
- Pre-cache input: a data cache would have changed no pilot outcome (five papers stopped at dependencies first), so it is not worth building before the dependency problems are addressed. No cache was built.

### Pilot Failure Categories (2026-09-30 21:42 +03:00, Issue #125, P4)
- `scripts/categorize_pilot_failures.py` applies protocol section 7 to the stored runs. The first failure (stage → install → run) decides, and the deciding log line is quoted verbatim. Result: 5 × `MISSING_DEPENDENCY` (002, 003, 005 at install; 004, 006 at run), 1 × `DATA_NOT_ACCESSIBLE` (008), no `OTHER` (`data/pilot_runs/failure_categories.json`).
- `runs.failure_category` column (ORM, `data/schema.sql`; `init_db` adds it to older SQLite databases). `scripts/load_pilot_runs.py` stores the 6 pilot runs with their category next to each run.
- Tests: the rules, the verbatim evidence lines, the column upgrade, and the loader.

### Pilot Run and Measurements (2026-09-30 21:36 +03:00, Issues #123 P2 and #124 P3)
- Pilot run: workflow run 36759195752 (commit `dbcbe5a`, 2026-09-30 18:31 UTC), all 6 papers, 1-4 minutes per job. Every `run_report.json` shows `docker_used: true` and `isolated: true`, and every repository was checked out at its pinned commit. The raw files are stored unchanged in `data/pilot_runs/`.
- `scripts/pilot_measurements.py` (committed before the results were read) applies the protocol definitions: install success 1 / 6, run success 0 / 6, pilot success 0 / 6 (`data/pilot_runs/measurements.md`). A test fails if the stored measurements stop matching the stored runs.

### Peak Memory and Install Duration Recorded (2026-09-30 20:53 +03:00, Issue #124, P3 part 1)
- `docker/entrypoint.sh`: `execution_meta.json` gets `peak_memory_bytes` (cgroup `memory.peak`, `null` if not exposed); `install_meta.json` gets `duration_seconds` and `peak_memory_bytes`. `scripts/run_pilot.py` copies the run peak into `pilot_record.json`. Done before the pilot runs, so the protocol's peak-memory measurement (section 6) is possible.
- Acceptance check 12 (real Docker, CI run 36754386741): a probe holding 200 MiB reported `peak_memory_bytes: 221929472`, and the install phase reported `duration_seconds: 0.784`. 12 of 12 checks pass; `docs/SANDBOX_ACCEPTANCE.md` was regenerated from that run.

### Pilot Runner and Workflow (2026-09-30 00:09 +03:00, Issue #123, P2 — not run yet)
- `scripts/run_pilot.py`: runs one seed paper exactly as `docs/PILOT_WEEK2.md` specifies. It stages at the pinned commit, bundles binary wheels on the host, and runs the install and run phases with the protocol limits (2 CPUs, 6 GB, 100 processes, 3600 s per phase). It writes `pilot_record.json` next to `run_report.json`, exits 0 when the paper went through the pipeline, and exits 1 on a harness error.
- `.github/workflows/pilot.yml`: started by hand only, one job per paper, `contents: read`, no secrets, no persisted credentials. It records the runner environment and uploads each paper's output (without installed dependencies) as an artifact.
- `tests/test_run_pilot.py`: commands, environment variables, and limits equal the protocol table; staging failures are recorded; the workflow stays manual and read-only. `pyyaml` added to the dev requirements for the workflow check.
- Local check without Docker: `paper_006` was cloned at its pinned commit and then refused to run (`SandboxUnavailableError`, exit 1). No paper code has run yet; the pilot run waits for the owner's approval of the Actions minutes.

### Pilot Protocol Written Before Any Run (2026-09-28 21:28 +03:00, Issue #122, P1)
- `docs/PILOT_WEEK2.md`: the pilot runs on GitHub-hosted runners (the development machine has no Docker) through a hand-started workflow built in P2 (#123); fixed limits (2 CPUs, 6 GB memory, 100 processes, 3600 s per phase, no network, CPU only); one exact command per paper, taken from each README at the pinned commit with no change to the repositories; the definitions of install success, run success, and pilot success rate; the failure categories with their evidence; and what may change after the runs start.
- Found while reading the repositories: `paper_002`'s target script has no entry point, `paper_004` and `paper_006` have no pip requirements file (conda only), and `paper_005` needs a C++ extension the sandbox does not build. Recorded in the protocol, not fixed.
- `tests/test_pilot_protocol.py`: the protocol has one command row per seed paper, with the same repository, commit, and target script as `data/seed_papers.json`.
- No paper code was run.

### Roadmap Recorded and Tracked (2026-09-28 20:33 +03:00, Issue #121)
- `docs/ROADMAP_2026-09-27.md`: complete English translation of the 2026-09-27 plan (sections 0-8, P1-P7, W1-W7), with the tracking issue next to every item. The binding order: pilot (#43) and claim extraction (#9) first and in parallel; the CLI (#136) and the report (#120) only after both; low-priority cleanup (#137, #138, #139) last.
- New issues: #122-#128 (P1-P7), #129-#133 (W1-W5), #134 (W7), #135 (section 3 closing step), #136 (GA-2), #137 (GA-15), #138 (coverage), #139 (GA-11). Updated instead of duplicated: #43 (pilot, now the current corpus), #9 (LLM extraction with quote verification), #10 (= W6), #120 (report order).
- `AGENTS.md` §6: permanent roadmap rules (English only, binding order, one topic per PR, script-generated report numbers, no simulated data as results, no committed API keys, working loop, read the roadmap first). `CLAUDE.md` points agents to `AGENTS.md`.
- `docs/gap_analysis.md`: GA-2, GA-5, GA-11, and GA-15 now link to their issues.
- No roadmap work item (pilot, extraction, CLI) was started.

### Docs: Introduction Draft Corrected and Sourced (2026-09-27, Issue #118)
- `docs/repro_radar_introduction.docx` is now marked DRAFT (title, header, banner) and scoped to a pilot study on tabular ML benchmarks.
- Unsourced claims (the 35% figure, the 1995 Claerbout date and long quote, dependency decay in 6–18 months, hardware drift) and out-of-scope claims (domain-agnostic scope, AI Decision Layer, "resolves") were removed.
- References [1]–[7] are cited in the text and checked against Crossref or the publisher page; the Claerbout quote uses the wording read in Donoho (2010).
- `docs/INTRODUCTION_SOURCES.md` maps each statement to its source and says how much of each source was read.
- Tests: the draft marking, the removed phrases, and the reference/citation match are checked in `tests/test_academic_doc.py`.

### M0 / DevOps: PR Template and Working Agreement (2026-09-27, Issues #115, #116)
- `.github/PULL_REQUEST_TEMPLATE.md`: what/why, how I tested it, what I did NOT verify, AI use, self-review checklist.
- Standing, pinned issue #115 holds the working agreement and a per-session checklist.

### M2 / Sandbox: Output Directory Writable by the Container on Any Host UID (2026-09-27, Issue #96)
- Reproduced by removing the acceptance script's `chmod` workaround: on the uid 1001 CI runner, 10 of 11 Docker checks failed with `execution_meta.json: <not written>`.
- The runner now opens the output directory only while the containers run and restores 0755 afterwards; all 11 acceptance checks pass without the workaround.
- 1 new POSIX test (runs on Linux CI).

### M2 / Sandbox: Acceptance Checks 8-11 (2026-09-27, Issue #110)
- New real-Docker checks: OOM kill under a 256 MiB limit (`OOM_KILLED` after 0.165 s), PID limit (thread creation stops after 95 extra threads), numpy 2.4.6 vs the Dockerfile floor `>=1.24.0`, and a non-existent requirement (install `FAILED`, run still completes). **11 of 11 pass** in CI run 36319286095.
- Check 8 first failed and exposed that OOM kills were reported as `TIMEOUT`; fixed separately in #113.
- Note: the numpy "bound" is only a floor; the version in the image is not pinned (GA-6).

### M2 / Sandbox: OOM Kills No Longer Reported as Timeouts (2026-09-27, Issue #112)
- Found by the new acceptance check 8: an OOM kill after 0.185 s was reported as `TIMEOUT` (exit 137 is SIGKILL for both the timeout watchdog and the OOM killer).
- The entrypoint compares the cgroup `oom_kill` counter before and after the run and writes `OOM_KILLED`; the runner reports the entrypoint's status instead of re-deriving it from the exit code.
- 2 new tests; CI checks both an OOM kill and a real timeout on Docker.

### M0 / DevOps: Gap Analysis Addendum (2026-09-27, Issue #108)
- GA-22: `pip download --prefer-binary` on the host ran an sdist's `setup.py`; reproduced with a marker-writing probe package (old command: marker written; current command: rejected, no marker). Fixed by #95 and #103.
- GA-17 updated with the claim check (2 of 16 found, #101) and the removed TabNet entry's wrong claims.

### M2 / Sandbox: Install Status at the Top of the Run Report (2026-09-27, Issue #106)
- `run_report.json` has a top-level `dependency_install_status` (`UNKNOWN` without execution metadata) for Tier 1 scoring.
- New test follows a failed install phase through the run into the report (`FAILED`); 89 tests green, 7 skipped on Windows.
- Not done: `ReproducibilityScorer` does not consume run reports yet (it is only fed by the simulated `cli.py score`, GA-2).

### M2 / Sandbox: Decision Log (2026-09-27, Issue #104)
- `docs/DECISIONS.md`: D-001 records that PR #64's removal of `noexec` from `/workspace/home` had no effect (Docker's tmpfs default), why `noexec` is kept, and the risk that `exec` would add; D-002 records the two-phase, read-only dependency mount. Each fact cites a PR or CI output.

### M2 / Sandbox: Bundle Every Requirements File; Flag Packages Without Wheels (2026-09-27, Issue #102)
- `bundle_dependencies()` downloads from every `*requirements*.txt` (previously only the first). If the download fails, each requirement is probed alone (binary-only, `--no-deps`) and the ones without a wheel are reported as `NEEDS_SDIST_BUILD`; nothing is built on the host.
- The install phase installs from the same files.
- 2 new tests; CI adds a real `pip download` check (`docopt==0.6.2`, sdist-only, is flagged) and a two-file install-phase check.

### M1 / Corpus: Claims Checked Against Papers; Seed Integrity Test (2026-09-27, Issue #100)
- Every seed claim was searched in its paper's PDF text (all printable forms, tolerant of `pypdf` spacing) and read in context: **2 of 16 claims found** (`paper_003` FT-T and ResNet, Table 2, p. 7). `paper_002`'s 0.895 is AutoGluon's value, not TabPFN's (0.894); `paper_005` cites a dataset "EP3602" and `paper_008` a HIGGS result that their papers do not contain. Details in `docs/CORPUS_VERIFICATION.md`; claim values were not changed.
- `tests/test_seed_integrity.py`: repository reachable, license allowed and matching, script at the pinned commit, one case per entry; network-only (`REPRO_RADAR_NETWORK_TESTS=1`), run in the CI corpus job. It fails for all 8 entries of the pre-fix corpus and passes for the current 6.
- No entry is called verified: each still has unverified claims and unchecked runnability.

### M2 / Sandbox: Compiled Dependencies Without Loosening Isolation (2026-09-27, Issue #92)
- Dependencies are installed by a separate install-phase container (network off, `--only-binary=:all:`, so no package code runs) into `sandbox_runs/<paper_id>/deps`, which the paper run mounts read-only at `/workspace/deps`. Compiled extensions load; `/workspace/home` and `/tmp` stay `noexec`, so paper code has no location that is both writable and executable.
- Rejected: `exec` on the home tmpfs (paper code could write and run binaries) and pre-installing packages into the image (papers pin different, large versions such as old PyTorch).
- Bundling now downloads binary wheels for the sandbox platform (manylinux, CPython 3.11) instead of the host OS.
- New acceptance check 7: `ujson` (C extension, not in the image) installs offline and loads from `/workspace/deps`; writes there fail with `Read-only file system`; the same `.so` copied to the noexec home fails to load. 7 of 7 checks pass in CI.
- The `deps` directory is world-writable only while the install container writes to it and is restored to 0755 before the run.
- Found during review and left open: the acceptance script makes the output directory world-writable, which may hide an output-permission problem on hosts not running as uid 1000 (#96).
- 7 new tests; 86 / 86 green on Linux.

### M0 / DevOps: Gap Analysis Cleanup (2026-09-27, Issue #93)
- Gap IDs renamed `G<n>` → `GA-<n>` in `docs/gap_analysis.md`, `docs/PROGRESS.md`, and `README.md`, so they no longer collide with the maintainer's TODO items `G1`-`G6`.
- Added gaps missed by the analysis: GA-17 (broken seed corpus labelled "verified", fixed in #85) and GA-18 (out-of-order work; PRs #56-#63 each merged 3-12 seconds after opening with no review), plus GA-19 to GA-21 found by the acceptance checks.
- Status references now point to the PRs that did the work.
- Checked: no "Hafta" milestones remain (removed in #76).

### M2 / Sandbox: Acceptance Evidence and Tracking Aligned (2026-09-27, Issue #86)
- `scripts/sandbox_acceptance.py` runs six checks through `DockerSandboxRunner` against a real Docker daemon in CI; **6 of 6 pass** (non-root uid 1000, network blocked, read-only root, `TIMEOUT` with duration > 0, offline install of a package not in the image, refusal without Docker). Output recorded verbatim in `docs/SANDBOX_ACCEPTANCE.md`.
- Building the evidence found and fixed two runner bugs (#88/#89, #90/#91), replaced a check that proved nothing (`six` was already in the image), and found that `/workspace/home` is `noexec` by Docker default (open: #92).
- Issue #48 rewritten in English with evidence for 4 of 5 goals and reopened (multi-seed execution is not implemented). M2 issues #13, #14, #15, #17, #18: boxes ticked only where evidence exists, with evidence notes.
- `docs/SANDBOX_GUIDE.md`: home mount, `noexec` finding, timeout defaults, and offline install status corrected.

### M2 / Sandbox: Home tmpfs Writable by the Sandbox User (2026-09-27, Issue #90)
- Found by the real-Docker acceptance run: the `/workspace/home` tmpfs was root-owned, so uid 1000 could not write to it and the offline wheel install could never succeed (`mkdir: cannot create directory '/workspace/home': Permission denied`).
- The runner and `docker/docker-compose.sandbox.yml` now mount it with `uid`/`gid` of the sandbox user.
- 1 new test; 79 / 79 tests green.

### M2 / Sandbox: Docker Runs Misreported as FAILED on Non-1000 UIDs (2026-09-26, Issue #88)
- Found by the first real-Docker acceptance run (Ubuntu CI runner, uid 1001): the runner re-wrote `stdout.log`/`stderr.log` that the container had already written as uid 1000, hit `PermissionError`, and reported every successful run as `FAILED` with its output dropped.
- The runner now keeps logs the entrypoint wrote and never lets a log write change a run's result.
- 1 new regression test; 78 / 78 tests green.

### M1 / Corpus: Seed Corpus Repaired and Verified by CI (2026-09-26, Issue #84)
- `data/seed_papers.json`: 6 entries, **6 of 6 pass `scripts/verify_corpus.py`**; every entry now pins a `repo_commit`. Removed `paper_001` (no license) and `paper_007` (community reimplementation with no runnable script).
- Fixed script paths (3 entries), renamed or mistyped repositories (3), licenses (4), titles (4), and `paper_005`'s paper link, year, and venue.
- CI corpus job is now blocking.
- `docs/CORPUS_VERIFICATION.md` records per-entry checks; runnability and all claim values are **UNVERIFIED**, and the claims of `paper_005` and `paper_008` are flagged SUSPECT.
- README no longer calls the corpus "8 verified" papers or promises short CPU-only runs.

### M1 / Corpus: Automated Corpus Verifier (2026-09-26, Issue #82)
- `scripts/verify_corpus.py` checks every seed entry: paper page title matches, GitHub repository exists (renames followed and reported), GitHub license is allowed and equals the declared license, and `target_script` exists at a pinned `repo_commit`. Any failure, including a network error, exits 1.
- First run against `data/seed_papers.json`: **0 of 8 entries pass**. Beyond the missing pinned commits, it found 4 license mismatches or unrecognized licenses, 4 title mismatches (including `paper_005` pointing to an unrelated physics paper), 2 renamed repositories, and 1 missing repository (`paper_006`).
- CI runs the verifier as a non-blocking job until the corpus is fixed in the next step.
- 16 new offline unit tests (fake HTTP client); 73 / 73 tests green.

### M2 / Sandbox: No Silent Unisolated Fallback (2026-09-26, Issue #80)
- `DockerSandboxRunner.run()` now raises `SandboxUnavailableError` and executes nothing when Docker is unavailable; previously it silently ran paper code on the host.
- Unisolated local execution requires the explicit `--allow-unsafe-local` flag (`SandboxConfig.allow_unsafe_local`); such runs print a red warning and are recorded as `"isolated": false` in `run_report.json`. Docker runs record `"isolated": true`.
- `scripts/stage_and_bundle_repo.py` exits with code 4 when execution is refused.
- Docs aligned (`README.md`, `docs/SANDBOX_GUIDE.md`, `docs/ENVIRONMENT.md`, `docs/ARCHITECTURE.md`); gap added to `docs/gap_analysis.md` as GA-16.
- 57 / 57 tests green: 5 new tests, the old fallback test rewritten for the new behavior, and the stager execution test extended to assert `isolated: false`.

### M0 / DevOps: Side-Effect Approval Gate Restored (2026-09-26, Issue #78)
- `AGENTS.md` §5.6 restored verbatim to its wording before PR #75: explicit go-ahead before git pushes, PR merges, or DB drops.
- Reason: a project review found that the relaxed gate removed the human check where the most serious problems originated (PRs merged minutes after opening without a diff review, completion claims without evidence). Green tests did not catch those problems. The maintainer and mentor decided to keep the original rule.
- The #69 entry below is kept as history; this entry supersedes it.

### M0 / DevOps: Tracking Reconciled with GitHub (2026-09-25, Issue #76)
- GitHub: closed implemented issues #5, #16, #27, #28, #47 with evidence; closed weekly umbrella issues #49, #51, #52, #53 as duplicates of the per-issue backlog; added done/missing status notes to #2, #4, #10, #11, #13, #14, #15, #17, #18, #30; removed the seven empty "Hafta" milestones.
- `docs/BLUEPRINT.md`: all 45 backlog references renumbered by title match against GitHub (they were one lower than the real issue numbers).
- This file: milestone table rebuilt from GitHub open/closed counts; no milestone is marked completed while it has open issues.
- Resolves gap analysis GA-1 and GA-4.

### M0 / DevOps: Relaxed Side-Effect Approval Gate (2026-09-25, Issue #69)
- `AGENTS.md` §5.6: after an approved proposal and a green suite, push, PR, merge, and merged-branch deletion no longer need a separate go-ahead.
- Force-pushes, direct commits to `main`, closing issues without a merged PR, settings changes, and destructive operations still require explicit approval.

### M7 / DevOps: Continuous Integration (2026-09-25, Issue #42, PR #74)
- `.github/workflows/ci.yml`: `ruff` and `pytest --cov` on Ubuntu and Windows (Python 3.11), plus a sandbox image job that builds `Dockerfile.sandbox`, checks for stray redirect files, and asserts `dependency_install_status` values. Resolves GA-3 and verifies the GA-7/GA-8 fixes from #71 on Docker.
- First CI run exposed a host-dependent test: `test_execute_staged_produces_report_and_metrics` assumed Docker was absent and failed on Ubuntu runners, where Docker is installed. The test now forces the process runner, like the other sandbox tests.

### M0 / DevOps: Setup & Verification Docs for the New Environment (2026-09-25, Issue #72)
- `README.md`: Quickstart installs `requirements-dev.txt` (runtime-only alternative noted), adds the Windows `py` launcher note, lint step, an accurate simulation note (GA-2), and a refreshed directory layout (GA-12).
- `docs/ENVIRONMENT.md`: separate runtime and development package tables, updated Windows and Linux/macOS setup, sandbox image smoke test with `dependency_install_status`, and a new verified baseline (52 tests, ruff clean).
- `docs/SANDBOX_GUIDE.md`: actual `execution_meta.json` fields and the new `meta_error` report field.
- `docs/gap_analysis.md`: status column tracking which gaps are fixed, partly fixed, or open.

### M0 / DevOps: Gap Remediation — Sandbox, Dependency, and Safety Fixes (2026-09-25, Issue #70)
- **CI (GA-3):** workflow prepared (lint, tests on Ubuntu and Windows, sandbox image build and smoke test) but not yet pushed: the GitHub token lacks the `workflow` scope. Follows in a separate PR.
- **Dependencies (GA-6):** `requirements.txt` now holds runtime packages only (`pydantic`, `sqlalchemy`, `tabulate`); tests, lint, and document tooling moved to `requirements-dev.txt`; unused `pandas`, `pyyaml`, and `requests` removed. `pyproject.toml` defines the ruff correctness gate.
- **Sandbox image (GA-7):** version constraints in `Dockerfile.sandbox` are quoted, so they are no longer parsed as shell redirections.
- **Entrypoint (GA-8):** `execution_meta.json` gains `dependency_install_status` (`SKIPPED` / `INSTALLED` / `FAILED`) instead of hiding install failures behind `|| true`.
- **Error handling (GA-9):** the metric extractor logs skipped non-JSON blocks; `execute_staged` reports an unreadable `execution_meta.json` as `meta_error`.
- **Security (GA-10):** `setup_github_backlog.py` passes argument lists without a shell and sends issue bodies on stdin.
- **Docker hygiene (GA-14):** `.dockerignore` limits the build context; obsolete Compose `version` key removed.
- 52 / 52 tests green (3 new), verified in a clean venv built from `requirements-dev.txt`.

### M0 / DevOps: Repository Gap Analysis (2026-09-24, Issue #67)
- Added `docs/gap_analysis.md`: 15 gaps (3 high, 7 medium, 5 low) across tracking, product, CI, tests, dependencies, sandbox, code quality, security, and docs, each with evidence, remedy, and related issue.
- Measured baseline: 60% line coverage (`cli.py` 0%), 281 `ruff` findings, 49 / 49 tests green.
- Highest-impact findings: living docs disagree with GitHub milestone/issue state (GA-1), `cli.py score` still runs on simulated outputs (GA-2), no CI (GA-3).
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
  - *18 → 8 (2026-09-13, commit `7a7d9ac`):* the 18 Week 1 entries were placeholders ("mock seed papers" in that commit's title); several paired paper titles with general-purpose library repositories (e.g. `optuna/optuna`, `huggingface/transformers`, `scikit-learn/scikit-learn`). They were replaced by 8 entries meant to map to real paper repositories. That commit called them "verified", which a later check disproved: see the 2026-09-26 entries for issues #82 and #84 (now 6 entries).
- **Reproducibility Scoring Engine:**
  - 4-Tier rubric (%35 Build, %35 Metrics, %15 Stability, %15 Artifacts) in `src/scoring.py`.
- **CLI & Test Suite:**
  - Built `cli.py` with `init-db`, `list-papers`, `inspect`, and `score` commands.
  - 20 unit tests in `tests/` passing.
