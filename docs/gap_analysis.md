# Repro Radar — Gap Analysis

> Snapshot of known weaknesses in code quality, tests, documentation, dependencies, devops, and
> security. Report only: each gap is meant to become its own issue and flow through the normal loop.
>
> **Baseline:** `main` at `0290e86`, 2026-09-24, Windows 11, Python 3.11.9, fresh `.venv`.

---

## 1. Summary

| ID | Severity | Category | Gap | Related issue | Status |
|---|---|---|---|---|---|
| GA-1 | High | Tracking | `PROGRESS.md` / `BLUEPRINT.md` disagree with GitHub milestone and issue state | #5 | Fixed in #77 (issue #76) |
| GA-2 | High | Product | `cli.py score` scores simulated outputs only; sandbox and extractor are not reachable from the CLI | #43 | Open (README note corrected in #73) |
| GA-3 | High | DevOps | No CI: tests and lint never run on PRs | #42 | Fixed in #74 |
| GA-4 | Medium | Tracking | Duplicate non-English "Hafta 1–7" milestones run a second, parallel plan | — | Fixed: milestones removed and issues consolidated (issue #76, PR #77) |
| GA-5 | Medium | Tests | 60% line coverage; `cli.py` and Docker execution path untested | #18 | Open: tests added in #71, #81, #83, #85, #89, #91; coverage not re-measured since the baseline |
| GA-6 | Medium | Dependencies | Unused, unpinned, and mixed runtime/dev dependencies | — | Partly fixed in #71: split and unused removed; no lock file yet |
| GA-7 | Medium | Sandbox | `Dockerfile.sandbox` version constraints are parsed as shell redirections | #13 | Fixed in #71; verified by CI image build in #74 |
| GA-8 | Medium | Sandbox | `entrypoint.sh` silently ignores dependency install failures | #32 | Fixed in #71; verified by CI smoke tests in #74 |
| GA-9 | Medium | Code quality | Blind `except Exception`, two silently swallowed | — | Partly fixed in #71: both silent cases fixed; 7 broad catches remain |
| GA-10 | Medium | Security | `setup_github_backlog.py` builds `shell=True` commands from issue text | #46 | Fixed in #71 |
| GA-11 | Low | Code quality | 281 lint findings, no lint or type-check configuration | — | Open (lint gate config added in #71) |
| GA-12 | Low | Docs | README directory layout is out of date | — | Fixed in #73 |
| GA-13 | Low | Repo structure | Missing `pyproject.toml`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `CLAUDE.md` | #44, #45 | Partly fixed: `pyproject.toml` added in #71 |
| GA-14 | Low | Sandbox | No `.dockerignore`; obsolete Compose `version` key | — | Fixed in #71 |
| GA-15 | Low | Repo hygiene | Generated `.docx` committed next to its generator | — | Open |
| GA-16 | High | Security | Without Docker, paper code silently ran on the host with no isolation | #80 | Fixed in #81: execution refused without Docker; opt-in `--allow-unsafe-local` marks runs `isolated: false` |
| GA-17 | High | Corpus | Seed corpus broken (6 of 8 entries not runnable; wrong links, licenses, titles, script paths) while the README called it "8 verified" | #84 | Fixed in #85: verifier enforced in CI (#83); 6 of 6 entries pass; claim values still UNVERIFIED |
| GA-18 | Medium | Process | Work merged out of plan order and without review | #78 | Mitigated: approval gate kept (#79); self-review comment on every PR since #81 |
| GA-19 | High | Sandbox | `/workspace/home` is `noexec` (Docker default), so offline-installed compiled wheels cannot load | #92 | Fixed in #95: dependencies installed in a separate phase and mounted read-only; compiled wheel verified by acceptance check 7 |
| GA-20 | High | Sandbox | Host log write turned every Docker run into `FAILED` on hosts not running as uid 1000 | #88 | Fixed in #89 |
| GA-21 | High | Sandbox | `/workspace/home` tmpfs root-owned, so offline installs always failed | #90 | Fixed in #91 |

Status last updated 2026-09-27. Detailed findings below describe the state at the baseline commit. GA-16, GA-17, and GA-18 were missed by this analysis and added after an external review on 2026-09-26; GA-19 to GA-21 were found by the real-Docker acceptance checks (`docs/SANDBOX_ACCEPTANCE.md`). IDs carry the `GA-` prefix so they are not confused with the `G1`-`G6` items of the maintainer's TODO list.

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

### GA-1 — Living docs disagree with GitHub (High)
- `docs/PROGRESS.md:20–24` marks M0, M1, M2, and M4 **COMPLETED**, but on GitHub M1 and M2 each have 6 open and 0 closed issues, M0 still has #2–#6 open, and M4 has 4 open.
- Issue numbers are off by one: `PROGRESS.md` maps M1 to #6–#11 and M2 to #12–#17, while GitHub has M1 = #7–#12 and M2 = #13–#18. `BLUEPRINT.md:104` lists the security audit as #45; on GitHub it is #46.
- Work that exists in code is still tracked as open, e.g. #13 (`docker/Dockerfile.sandbox` exists) and #16 (`ProcessSandboxRunner` exists).

**Remedy:** reconcile once: close implemented issues with a reference to the PR that delivered them, fix the issue ranges in `PROGRESS.md` and `BLUEPRINT.md`, and treat GitHub as the source of truth from then on.

### GA-2 — CLI scoring is still simulated (High)
- `cli.py:100–111` fabricates the reproduced metrics as `expected × 1.012` (or `× 0.65` / `× 1.08` with flags); nothing from `src/sandbox/` or `src/metric_extractor.py` is called from the CLI. Only `scripts/stage_and_bundle_repo.py` runs real executions.
- When a paper has not been staged, Tier 4 inspects **Repro Radar's own repository** instead of the paper's (`cli.py:133–136`), so every unstaged paper gets credit for this repo's `requirements.txt` and `README.md`.
- `README.md:113` still says real sandbox execution "will be integrated in Week 2".

**Remedy:** add a `run` / `score --live` path that stages, executes, extracts, and scores; make the simulated mode explicit (`--simulate`) and score Tier 4 as unknown when the repository is not staged; update the README note.

### GA-3 — No continuous integration (High)
`.github/workflows/` does not exist. Tests, lint, and the conventional-commit rules in `AGENTS.md` are enforced only by hand, and branch protection is unavailable on the current plan for a private repository.

**Remedy:** covered by #42: a workflow running `pytest` and `ruff` on push and PR, plus a PR-title check.

### GA-4 — Parallel non-English milestones (Medium)
GitHub has seven "Hafta 1–7" milestones (with issues #47–#53) alongside M0–M7. They duplicate the roadmap and their titles break the English-only rule in `AGENTS.md` §5.1.

**Remedy:** move #47–#53 into the matching M-milestones (or close them as duplicates), then close or delete the "Hafta" milestones.

### GA-5 — Test gaps (Medium)
- `cli.py` has 0% coverage: no test imports it, so argument parsing and every command path are unverified.
- The Docker path of `DockerSandboxRunner` (`runner.py:189–241`) never runs in tests; only command construction and the process fallback are exercised.
- `RepoStager` clone/checkout and dependency download (`stager.py:99–134`, `239–273`) are untested.
- `src/database.py` is at 65%.

**Remedy:** CLI tests via `subprocess` or by calling `main()` with a temporary database; an opt-in Docker integration test (`@pytest.mark.docker`, skipped when Docker is absent) as scoped in #18; local-bare-repo fixtures for the stager.

### GA-6 — Dependency hygiene (Medium)
- `pandas`, `pyyaml`, and `requests` are declared in `requirements.txt` but imported nowhere.
- Runtime, test (`pytest`), and script-only (`python-docx`, `pillow`) dependencies share one file.
- Every entry is a floor (`>=`) with no lock file, so two installs a month apart can differ. For a reproducibility tool, that weakens its own reproducibility claims.

**Remedy:** split into `requirements.txt` (runtime) and `requirements-dev.txt` (test, lint, docs tooling); drop or defer unused packages until the issue that needs them; add a lock (`pip-tools` `requirements.lock` or `uv.lock`).

### GA-7 — Dockerfile version constraints are shell redirections (Medium)
`docker/Dockerfile.sandbox:36–42` runs `pip install ... numpy>=1.24.0 scipy>=1.10.0 ...` unquoted in a shell-form `RUN`. `/bin/sh` parses each `>=x.y.z` as an output redirection, so:
- every version floor is silently dropped (packages install unconstrained);
- pip's output is written to stray files such as `/=1.24.0` inside the image instead of the build log.

**Remedy:** quote each requirement (`"numpy>=1.24.0"`) or install from a pinned requirements file copied into the image.

### GA-8 — Dependency install failures are swallowed (Medium)
`docker/entrypoint.sh:27` and `:29` end the offline `pip install` with `|| true`. A missing wheel lets the run proceed and fail later with an `ImportError`, which is then classified as a generic `FAILED` rather than a dependency failure.

**Remedy:** record the install exit code in `execution_meta.json` (e.g. `dependency_install_status`) so the scorer and the failure classifier (#32) can tell "could not install" from "ran and failed".

### GA-9 — Broad and silent exception handling (Medium)
Nine `except Exception` blocks (`ruff` BLE001): `src/metric_extractor.py:189, 385, 399`, `src/sandbox/runner.py:239, 338`, `src/sandbox/stager.py:315, 342`, `scripts/stage_and_bundle_repo.py:143, 192`. Two of them swallow errors with `pass`:
- `metric_extractor.py:189` drops malformed JSON metric lines with no trace.
- `stager.py:315` ignores an unreadable `execution_meta.json`, losing status and exit code.

Nine `subprocess.run` calls rely on manual return-code checks (`PLW1510`).

**Remedy:** catch specific exceptions (`json.JSONDecodeError`, `OSError`) and log at `debug`/`warning`; keep broad catches only at process boundaries, with logging.

### GA-10 — Shell injection surface in backlog script (Medium)
`scripts/setup_github_backlog.py:862` runs `subprocess.run(cmd, shell=True)`, and lines 869–907 build `cmd` by interpolating label names, milestone titles, and full issue bodies into f-strings. Only `"` is escaped (line 905). Backticks, `$(...)`, or `%VAR%` in a body would be expanded by the shell. `setup_7week_board.py` already shows the safe pattern (argument list, body on stdin).

**Remedy:** pass argument lists without `shell=True` and send bodies via `--body-file` or stdin, as the projectflow security note prescribes.

### GA-11 — Lint debt without configuration (Low)
`ruff check .` reports 281 findings: 164 legacy typing annotations (`UP006`/`UP045`/`UP007`/`UP035`), 60 unused imports (`F401`), 18 unsorted imports, 10 unused unpacked variables in `tests/test_scoring.py`, and one invalid escape sequence (`scripts/setup_github_backlog.py:509`). There is no `ruff`/`mypy` configuration, so nothing defines the target.

**Remedy:** add `[tool.ruff]` (and optionally `mypy`) to a `pyproject.toml`, run `ruff check --fix` once in a dedicated PR, then gate new findings in CI (GA-3).

### GA-12 — README directory layout out of date (Low)
`README.md` "Directory Layout" omits `src/metric_extractor.py`, `src/validation_rubric.py`, `scripts/generate_academic_introduction_doc.py`, `scripts/setup_7week_board.py`, `scripts/setup_github_backlog.py`, `scripts/setup_github_board.sh`, `tests/test_metric_extractor.py`, `tests/test_validation_rubric.py`, `tests/test_academic_doc.py`, and `docs/VALIDATION_RUBRIC.md`.

**Remedy:** refresh the tree, or replace it with a short per-directory description that does not go stale per file.

### GA-13 — Missing repository scaffolding (Low)
| File | Why it matters |
|---|---|
| `pyproject.toml` | Project metadata and a home for tool configuration (GA-11) |
| `CONTRIBUTING.md` | Onboarding for contributors and new papers (#44) |
| `SECURITY.md` | Reporting channel for a project that executes third-party code |
| `CHANGELOG.md` | Release notes for semantic versioning (#45) |
| `CLAUDE.md` | Claude Code's project memory file; a one-line `@AGENTS.md` import loads the project rules at the start of every session |
| commitlint / PR-title check | Conventions in `AGENTS.md` are not enforced (#3) |

### GA-14 — Docker build context and Compose hygiene (Low)
- No `.dockerignore`: the Compose build context is the repo root (`docker-compose.sandbox.yml` `context: ..`), so `.venv/`, `temp_clones/`, and `sandbox_runs/` are sent to the Docker daemon on every build.
- `docker/docker-compose.sandbox.yml:6` declares `version: '3.8'`, which Compose v2 ignores and warns about.

### GA-15 — Generated binary in version control (Low)
`docs/repro_radar_introduction.docx` is committed next to `scripts/generate_academic_introduction_doc.py`, which produces it. Edits to one can drift from the other, and binary diffs are not reviewable.

**Remedy:** either treat the script as the source and publish the `.docx` as a release asset, or add a test that regenerates it and fails on drift.

### GA-16 — Silent unisolated fallback without Docker (High, added 2026-09-26)
Not found by the original analysis; reported by an external review. When `docker` was unavailable, `DockerSandboxRunner.run()` (`src/sandbox/runner.py`, "graceful fallback") silently switched to `ProcessSandboxRunner`, so third-party paper code ran directly on the host with the user's files and network, with no warning. This contradicted the README's claim that external code never runs unsandboxed, and several docs presented the fallback as a feature (the "good shape" list below did too).

**Remedy (done in #80):** raise `SandboxUnavailableError` and execute nothing without Docker; allow unisolated runs only through the explicit `--allow-unsafe-local` / `SandboxConfig.allow_unsafe_local` opt-in, print a red warning, and record `"isolated": false` in the run report.

### GA-17 — Broken seed corpus labelled "verified" (High, added 2026-09-26)
Not found by the original analysis; reported by an external review. Of the 8 entries in `data/seed_papers.json`, only 2 had a target script that existed; others had renamed or missing repositories (one mistyped), licenses that did not match GitHub, titles that did not match the linked paper, and `paper_005` linked an unrelated physics paper. The README still described the set as "8 verified" papers.

**Remedy (done):** `scripts/verify_corpus.py` checks paper title, repository, license, and a script at a pinned commit, and runs as a blocking CI job (#83, #85). Two entries were removed, six repaired; `docs/CORPUS_VERIFICATION.md` records what is still unverified (runnability and every claim value).

### GA-18 — Work merged out of order and without review (Medium, added 2026-09-26)
Not found by the original analysis; reported by an external review. Work outside the plan (cover image and docx: #54 / PR #61; validation rubric: #55 / PR #60) and ahead of the corpus and sandbox gates (metric extraction: PR #62) was merged, and PRs #56-#63 were each merged 3 to 12 seconds after being opened, with zero reviews (GitHub `createdAt`/`mergedAt`), so nobody read the diffs. Green tests did not catch GA-16 or GA-17.

**Remedy:** the side-effect approval gate in `AGENTS.md` stays (the relaxation in #75 was reverted in #79); every PR since #81 carries a self-review comment written after reading the full diff. The out-of-order work is kept, but no new work is built on it until the pilot gates are passed.

### GA-19, GA-20, GA-21 — Found by the real-Docker acceptance checks (2026-09-27)
See `docs/SANDBOX_ACCEPTANCE.md` (Findings). GA-20 (#88/#89) and GA-21 (#90/#91) are fixed; GA-19 (#92) is fixed in #95: dependencies are installed by a separate install-phase container into a directory the paper run mounts read-only, so compiled extensions load (acceptance check 7) while `/workspace/home` stays `noexec`.

---

## 4. What is in good shape

- The full suite is green on a clean machine, and core modules (`models`, `metric_extractor`, `scoring`, `validation_rubric`) sit at 82–96% coverage.
- The container sandbox is defensive: non-root user, read-only root filesystem, `--network none`, and CPU/memory/PID limits. (The silent process fallback previously listed here was a security gap; see GA-16.)
- Tracked text files contain no non-English content, consistent with `AGENTS.md` §5.1.
- Environment and dependencies are inventoried in [`ENVIRONMENT.md`](ENVIRONMENT.md).

---

## 5. Suggested order

1. **GA-1 + GA-4**: reconcile tracking first, so later work lands on an accurate board.
2. **GA-3**: CI, so every following fix is checked automatically.
3. **GA-7, GA-8, GA-10**: small, high-value correctness and safety fixes.
4. **GA-2**: connect the real pipeline to the CLI (depends on GA-5 tests to do safely).
5. **GA-5, GA-6, GA-9, GA-11–GA-15**: incremental hygiene, one issue each.
