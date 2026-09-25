# Repro Radar — Project Conventions & Operating Method

This project follows the **projectflow** method paired with **superpowers** deep skills. Read this file before working, and keep the living docs current.

---

## 1. Living Docs (Read First)
- `docs/BLUEPRINT.md` — The master plan: what we're building, architecture, milestones, and how.
- `docs/ARCHITECTURE.md` — Constraints, structure, design patterns, and database/scoring contracts.
- `docs/PROGRESS.md` — What's been done. **Update it after every issue/PR.**
- `docs/STACK.md` — Tech stack, dependencies, execution environments, and security boundaries.

---

## 2. The Working Loop (projectflow)
0. **New project / greenfield?** Announce the **discovery pipeline** and start Phase 0. Skip only for well-understood or small incremental work, and **state that you are skipping and why**.
1. **Requirements → Labeled Issues** (one per area). Don't code from a vague ask. Detail implementation trade-offs under `## Options`.
2. **Show backlog + priority**; let the maintainer steer.
3. **Per issue: PROPOSE → APPROVE → IMPLEMENT** (one at a time).
   - Present the approach in plain language before touching any code.
   - Wait for explicit user approval before writing code.
4. **Verify with evidence:**
   - Run automated tests (`.venv\Scripts\pytest.exe tests/ -v`).
   - Show output directly in the message. Never claim "done" or "fixed" without evidence.
5. **PR & Code Review:**
   - Clean, focused diff.
   - Run code review before opening PR.
6. **Update `docs/PROGRESS.md`** after completing each task.
7. **Offer a bug hunt** at every milestone close.

---

## 3. Configuration
- **areas:** `corpus, sandbox, scoring, ai, web, devops`
  - `corpus` — Target research papers, metadata schemas, seed datasets, arXiv integrations
  - `sandbox` — Docker containers, cgroup resource controls, timeouts, filesystem isolation, subprocess runner
  - `scoring` — 4-Tier reproducibility engine (build, metrics, stability, artifacts), tolerances
  - `ai` — AI Decision Layer, automated diagnostic reasoning, crash analysis, discrepancy explainers
  - `web` — FastAPI REST API, paper leaderboard UI, SVG badges, PDF/Markdown report exporters
  - `devops` — CI/CD pipelines, GitHub Actions, projectflow tooling, release automation, repository standards
- **milestones:** `M0` through `M7` (Hygiene, Schema, Sandbox, Static Analysis, Metrics, AI Layer, Web, Release)
- **test commands:**
  - Full suite: `.venv\Scripts\pytest.exe tests/ -v`
  - Database: `.venv\Scripts\pytest.exe tests/test_database.py -v`
  - Models: `.venv\Scripts\pytest.exe tests/test_models.py -v`
  - Scoring: `.venv\Scripts\pytest.exe tests/test_scoring.py -v`
  - Seed dataset: `.venv\Scripts\pytest.exe tests/test_seed.py -v`
- **traceability:** Milestone tracking in `docs/PROGRESS.md` and roadmap in `docs/project_roadmap.md`.
- **working language:** English for code/docs/commits/PRs; communicate with the maintainer in their preferred language.

---

## 4. Deep Skills Integration (Superpowers)
Check this table every turn. If the matching deep skill is installed and the step needs it, invoke it:

| projectflow step | Deep skill | Inline fallback |
|---|---|---|
| discovery / scoping | `brainstorming` | Clarify goals & acceptance criteria first |
| propose the approach | `writing-plans` | Write numbered plan before coding |
| implement | `test-driven-development` | Failing test first, then implementation |
| debugging / test failure | `systematic-debugging` | Root cause analysis before fixing |
| before claiming "done" | `verification-before-completion` | Run tests, present stdout evidence |
| before opening PR | `requesting-code-review` | Audit diff with fresh perspective |
| acting on review | `receiving-code-review` | Verify feedback before applying |
| merge / branch finish | `finishing-a-development-branch` | Present merge options cleanly |

---

## 5. Always-On Guardrails
1. **Strict English Repository Rule (Mandatory):** All repository artifacts — code, docstrings, inline comments, variable/symbol names, database schemas, enum values, logs, status labels, test names, living docs, blueprints, roadmaps, issue templates, and commit/PR messages — MUST be exclusively written in English. Non-English text is strictly prohibited in repository files. The maintainer may converse in Turkish in chat, but all committed assets must be English.
2. **Propose before you do:** No edits or writes on an issue until a proposal is approved.
3. **No completion claim without evidence:** Output must be shown in the same message.
4. **Stay inside the issue:** Only touch files needed for the issue.
5. **Leave the build green:** All unit tests must pass.
6. **Side effects after approval:** Once the issue's proposal is approved and the full test suite is green, pushing the feature branch, opening the PR, merging it, and deleting the merged feature branch proceed without a further go-ahead. Explicit approval is still required for: force-pushes or history rewrites, direct commits to `main`, closing issues without a merged PR, repository or GitHub settings changes, and destructive operations (DB drops, deleting files outside the issue's scope).
7. **No AI attribution:** No "generated by AI" in commit messages or PRs.
8. **End every turn with an action plan:**
   ```
   Action plan
   - To-dos: <queued work, if any>
   - Open decisions: <what needs maintainer call, if any>
   - Next: <immediate next step>
   ```
