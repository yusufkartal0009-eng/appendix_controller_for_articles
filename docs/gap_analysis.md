# Repro Radar — Gap Analysis

> Snapshot of known weaknesses in code quality, tests, documentation, dependencies, devops, and
> security. Report only: each gap is meant to become its own issue and flow through the normal loop.
>
> **Baseline:** `main` at `0290e86`, 2026-09-24, Windows 11, Python 3.11.9, fresh `.venv`.

---

## 1. Summary

| ID | Severity | Category | Gap | Related issue | Status |
|---|---|---|---|---|---|
| G1 | High | Tracking | `PROGRESS.md` / `BLUEPRINT.md` disagree with GitHub milestone and issue state | #5 | Fixed in #76 |
| G2 | High | Product | `cli.py score` scores simulated outputs only; sandbox and extractor are not reachable from the CLI | #43 | Open (README note corrected in #72) |
| G3 | High | DevOps | No CI: tests and lint never run on PRs | #42 | Fixed in #74 |
| G4 | Medium | Tracking | Duplicate non-English "Hafta 1–7" milestones run a second, parallel plan | — | Fixed: milestones removed, issues consolidated (#76) |
| G5 | Medium | Tests | 60% line coverage; `cli.py` and Docker execution path untested | #18 | Open (3 tests added in #71) |
| G6 | Medium | Dependencies | Unused, unpinned, and mixed runtime/dev dependencies | — | Partly fixed in #71: split and unused removed; no lock file yet |
| G7 | Medium | Sandbox | `Dockerfile.sandbox` version constraints are parsed as shell redirections | #13 | Fixed in #71; verified by CI image build in #74 |
| G8 | Medium | Sandbox | `entrypoint.sh` silently ignores dependency install failures | #32 | Fixed in #71; verified by CI smoke tests in #74 |
| G9 | Medium | Code quality | Blind `except Exception`, two silently swallowed | — | Partly fixed in #71: both silent cases fixed; 7 broad catches remain |
| G10 | Medium | Security | `setup_github_backlog.py` builds `shell=True` commands from issue text | #46 | Fixed in #71 |
| G11 | Low | Code quality | 281 lint findings, no lint or type-check configuration | — | Open (lint gate config added in #71) |
| G12 | Low | Docs | README directory layout is out of date | — | Fixed in #72 |
| G13 | Low | Repo structure | Missing `pyproject.toml`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `CLAUDE.md` | #44, #45 | Partly fixed: `pyproject.toml` added in #71 |
| G14 | Low | Sandbox | No `.dockerignore`; obsolete Compose `version` key | — | Fixed in #71 |
| G15 | Low | Repo hygiene | Generated `.docx` committed next to its generator | — | Open |

Status last updated 2026-09-25. Detailed findings below describe the state at the baseline commit.

---

## 2. Measurements

| Check | Command | Result |
|---|---|---|
| Test suite | `pytest tests/ -q` | 49 passed |
| Coverage | `pytest tests/ --cov=src --cov=cli --cov=scripts` | **60%** (1604 statements, 644 missed) |
| Lint | `ruff check .` (ruff 0.16.9, default rules) | **281** findings, 229 auto-fixable |
| Non-English text | scan of tracked text files for Turkish characters | none found |

Coverage per module:

| Module | Coverage | Largest uncovered region |
|---|---:|---|
| `src/config.py`, `src/__init__.py`, `src/sandbox/__init__.py` | 100% | — |
| `src/models.py` | 96% | 56–64 |
| `src/metric_extractor.py` | 92% | 385–407 |
| `src/validation_rubric.py` | 84% | 340–351, 374–379 |
| `src/scoring.py` | 82% | 383–396 |
| `src/sandbox/runner.py` | 73% | Docker execution path, 189–241 |
| `src/sandbox/stager.py` | 69% | `git clone` / checkout, 99–134; dependency download, 239–273 |
| `src/database.py` | 65% | 96–106, 181–185 |
| `scripts/stage_and_bundle_repo.py` | 22% | CLI body, 44–215 |
| `scripts/*` (other three) | 0% | whole files |
| `cli.py` | 0% | not imported by any test |

---

## 3. Findings

### G1 — Living docs disagree with GitHub (High)
- `docs/PROGRESS.md:20–24` marks M0, M1, M2, and M4 **COMPLETED**, but on GitHub M1 and M2 each have 6 open and 0 closed issues, M0 still has #2–#6 open, and M4 has 4 open.
- Issue numbers are off by one: `PROGRESS.md` maps M1 to #6–#11 and M2 to #12–#17, while GitHub has M1 = #7–#12 and M2 = #13–#18. `BLUEPRINT.md:104` lists the security audit as #45; on GitHub it is #46.
- Work that exists in code is still tracked as open, e.g. #13 (`docker/Dockerfile.sandbox` exists) and #16 (`ProcessSandboxRunner` exists).

**Remedy:** reconcile once: close implemented issues with a reference to the PR that delivered them, fix the issue ranges in `PROGRESS.md` and `BLUEPRINT.md`, and treat GitHub as the source of truth from then on.

### G2 — CLI scoring is still simulated (High)
- `cli.py:100–111` fabricates the reproduced metrics as `expected × 1.012` (or `× 0.65` / `× 1.08` with flags); nothing from `src/sandbox/` or `src/metric_extractor.py` is called from the CLI. Only `scripts/stage_and_bundle_repo.py` runs real executions.
- When a paper has not been staged, Tier 4 inspects **Repro Radar's own repository** instead of the paper's (`cli.py:133–136`), so every unstaged paper gets credit for this repo's `requirements.txt` and `README.md`.
- `README.md:113` still says real sandbox execution "will be integrated in Week 2".

**Remedy:** add a `run` / `score --live` path that stages, executes, extracts, and scores; make the simulated mode explicit (`--simulate`) and score Tier 4 as unknown when the repository is not staged; update the README note.

### G3 — No continuous integration (High)
`.github/workflows/` does not exist. Tests, lint, and the conventional-commit rules in `AGENTS.md` are enforced only by hand, and branch protection is unavailable on the current plan for a private repository.

**Remedy:** covered by #42: a workflow running `pytest` and `ruff` on push and PR, plus a PR-title check.

### G4 — Parallel non-English milestones (Medium)
GitHub has seven "Hafta 1–7" milestones (with issues #47–#53) alongside M0–M7. They duplicate the roadmap and their titles break the English-only rule in `AGENTS.md` §5.1.

**Remedy:** move #47–#53 into the matching M-milestones (or close them as duplicates), then close or delete the "Hafta" milestones.

### G5 — Test gaps (Medium)
- `cli.py` has 0% coverage: no test imports it, so argument parsing and every command path are unverified.
- The Docker path of `DockerSandboxRunner` (`runner.py:189–241`) never runs in tests; only command construction and the process fallback are exercised.
- `RepoStager` clone/checkout and dependency download (`stager.py:99–134`, `239–273`) are untested.
- `src/database.py` is at 65%.

**Remedy:** CLI tests via `subprocess` or by calling `main()` with a temporary database; an opt-in Docker integration test (`@pytest.mark.docker`, skipped when Docker is absent) as scoped in #18; local-bare-repo fixtures for the stager.

### G6 — Dependency hygiene (Medium)
- `pandas`, `pyyaml`, and `requests` are declared in `requirements.txt` but imported nowhere.
- Runtime, test (`pytest`), and script-only (`python-docx`, `pillow`) dependencies share one file.
- Every entry is a floor (`>=`) with no lock file, so two installs a month apart can differ. For a reproducibility tool, that weakens its own reproducibility claims.

**Remedy:** split into `requirements.txt` (runtime) and `requirements-dev.txt` (test, lint, docs tooling); drop or defer unused packages until the issue that needs them; add a lock (`pip-tools` `requirements.lock` or `uv.lock`).

### G7 — Dockerfile version constraints are shell redirections (Medium)
`docker/Dockerfile.sandbox:36–42` runs `pip install ... numpy>=1.24.0 scipy>=1.10.0 ...` unquoted in a shell-form `RUN`. `/bin/sh` parses each `>=x.y.z` as an output redirection, so:
- every version floor is silently dropped (packages install unconstrained);
- pip's output is written to stray files such as `/=1.24.0` inside the image instead of the build log.

**Remedy:** quote each requirement (`"numpy>=1.24.0"`) or install from a pinned requirements file copied into the image.

### G8 — Dependency install failures are swallowed (Medium)
`docker/entrypoint.sh:27` and `:29` end the offline `pip install` with `|| true`. A missing wheel lets the run proceed and fail later with an `ImportError`, which is then classified as a generic `FAILED` rather than a dependency failure.

**Remedy:** record the install exit code in `execution_meta.json` (e.g. `dependency_install_status`) so the scorer and the failure classifier (#32) can tell "could not install" from "ran and failed".

### G9 — Broad and silent exception handling (Medium)
Nine `except Exception` blocks (`ruff` BLE001): `src/metric_extractor.py:189, 385, 399`, `src/sandbox/runner.py:239, 338`, `src/sandbox/stager.py:315, 342`, `scripts/stage_and_bundle_repo.py:143, 192`. Two of them swallow errors with `pass`:
- `metric_extractor.py:189` drops malformed JSON metric lines with no trace.
- `stager.py:315` ignores an unreadable `execution_meta.json`, losing status and exit code.

Nine `subprocess.run` calls rely on manual return-code checks (`PLW1510`).

**Remedy:** catch specific exceptions (`json.JSONDecodeError`, `OSError`) and log at `debug`/`warning`; keep broad catches only at process boundaries, with logging.

### G10 — Shell injection surface in backlog script (Medium)
`scripts/setup_github_backlog.py:862` runs `subprocess.run(cmd, shell=True)`, and lines 869–907 build `cmd` by interpolating label names, milestone titles, and full issue bodies into f-strings. Only `"` is escaped (line 905). Backticks, `$(...)`, or `%VAR%` in a body would be expanded by the shell. `setup_7week_board.py` already shows the safe pattern (argument list, body on stdin).

**Remedy:** pass argument lists without `shell=True` and send bodies via `--body-file` or stdin, as the projectflow security note prescribes.

### G11 — Lint debt without configuration (Low)
`ruff check .` reports 281 findings: 164 legacy typing annotations (`UP006`/`UP045`/`UP007`/`UP035`), 60 unused imports (`F401`), 18 unsorted imports, 10 unused unpacked variables in `tests/test_scoring.py`, and one invalid escape sequence (`scripts/setup_github_backlog.py:509`). There is no `ruff`/`mypy` configuration, so nothing defines the target.

**Remedy:** add `[tool.ruff]` (and optionally `mypy`) to a `pyproject.toml`, run `ruff check --fix` once in a dedicated PR, then gate new findings in CI (G3).

### G12 — README directory layout out of date (Low)
`README.md` "Directory Layout" omits `src/metric_extractor.py`, `src/validation_rubric.py`, `scripts/generate_academic_introduction_doc.py`, `scripts/setup_7week_board.py`, `scripts/setup_github_backlog.py`, `scripts/setup_github_board.sh`, `tests/test_metric_extractor.py`, `tests/test_validation_rubric.py`, `tests/test_academic_doc.py`, and `docs/VALIDATION_RUBRIC.md`.

**Remedy:** refresh the tree, or replace it with a short per-directory description that does not go stale per file.

### G13 — Missing repository scaffolding (Low)
| File | Why it matters |
|---|---|
| `pyproject.toml` | Project metadata and a home for tool configuration (G11) |
| `CONTRIBUTING.md` | Onboarding for contributors and new papers (#44) |
| `SECURITY.md` | Reporting channel for a project that executes third-party code |
| `CHANGELOG.md` | Release notes for semantic versioning (#45) |
| `CLAUDE.md` | Claude Code's project memory file; a one-line `@AGENTS.md` import loads the project rules at the start of every session |
| commitlint / PR-title check | Conventions in `AGENTS.md` are not enforced (#3) |

### G14 — Docker build context and Compose hygiene (Low)
- No `.dockerignore`: the Compose build context is the repo root (`docker-compose.sandbox.yml` `context: ..`), so `.venv/`, `temp_clones/`, and `sandbox_runs/` are sent to the Docker daemon on every build.
- `docker/docker-compose.sandbox.yml:6` declares `version: '3.8'`, which Compose v2 ignores and warns about.

### G15 — Generated binary in version control (Low)
`docs/repro_radar_introduction.docx` is committed next to `scripts/generate_academic_introduction_doc.py`, which produces it. Edits to one can drift from the other, and binary diffs are not reviewable.

**Remedy:** either treat the script as the source and publish the `.docx` as a release asset, or add a test that regenerates it and fails on drift.

---

## 4. What is in good shape

- The full suite is green on a clean machine, and core modules (`models`, `metric_extractor`, `scoring`, `validation_rubric`) sit at 82–96% coverage.
- The sandbox design is defensive: non-root user, read-only root filesystem, `--network none`, CPU/memory/PID limits, and a process fallback when Docker is absent.
- Tracked text files contain no non-English content, consistent with `AGENTS.md` §5.1.
- Environment and dependencies are inventoried in [`ENVIRONMENT.md`](ENVIRONMENT.md).

---

## 5. Suggested order

1. **G1 + G4**: reconcile tracking first, so later work lands on an accurate board.
2. **G3**: CI, so every following fix is checked automatically.
3. **G7, G8, G10**: small, high-value correctness and safety fixes.
4. **G2**: connect the real pipeline to the CLI (depends on G5 tests to do safely).
5. **G5, G6, G9, G11–G15**: incremental hygiene, one issue each.
