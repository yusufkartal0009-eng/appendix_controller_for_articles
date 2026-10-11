# Contributing to Repro Radar

Repro Radar checks whether the numbers a research paper reports can be reproduced from the paper's public code, by running that code in an isolated Docker sandbox and scoring what comes out. This is a research prototype with a small corpus (six papers today). Contributions are welcome, within the rules below.

> **State of the project, so you know what to expect.** The maintainer decides the direction: what is accepted as a paper's claim, what the sandbox may run, and what the dashboard looks like. GitHub Actions is currently disabled, so no pull request is checked by CI; you run the checks yourself (section 3) and say so in the pull request.

## 1. Ways to contribute

- **Report a problem:** open an issue with the bug template. Include the command you ran and the real output.
- **Propose a change:** open an issue with the feature template and wait for the maintainer to agree on the approach before you write code (`AGENTS.md`, section 2).
- **Add a paper to the corpus:** follow [`docs/PAPER_ONBOARDING.md`](docs/PAPER_ONBOARDING.md). A new paper is a change to the evaluation set, so the maintainer reviews it more closely than code.
- **Improve the documentation or the tests:** the same workflow, with a small pull request.

## 2. Workflow (one item, one issue, one branch, one pull request)

1. **Issue first.** Describe the problem, what you want, and how you will know it is done. Add a short plan (an estimate and about three steps).
2. **Agree on the approach** in the issue before writing code.
3. **Branch from `main`:** `feat/issue-<n>-<topic>`, `fix/issue-<n>-<topic>`, `docs/issue-<n>-<topic>`, or `chore/issue-<n>-<topic>`. Never commit to `main` directly, and never force-push.
4. **Commit messages:** `type(area): summary (#<n>)`. Types: `feat`, `fix`, `docs`, `test`, `chore`. Areas: `corpus`, `sandbox`, `scoring`, `ai`, `web`, `devops`.
5. **Run the checks** (section 3) and keep their output for the pull request.
6. **Update [`docs/PROGRESS.md`](docs/PROGRESS.md)** with the real date and time, in the same pull request.
7. **Open the pull request** with the template (`.github/PULL_REQUEST_TEMPLATE.md`): what and why, how you tested it, **what you did not verify**, and how AI was used.
8. **Read your own diff** and post a short self-review comment before anyone merges.
9. **Close the issue** with a short comment: what is done, what is left.

Everything in the repository and on GitHub is written in **English**: code, comments, documents, issues, branch names, commit messages, pull request texts.

## 3. Local setup and checks

Python 3.11.4 or newer (`pyproject.toml`) and, for anything that runs paper code, Docker.

```
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt     # on Linux and macOS: .venv/bin/pip
.venv\Scripts\ruff.exe check .
.venv\Scripts\pytest.exe tests -q
```

The suite needs no Docker, no network, and no API key. Checks that need more are separate scripts:

| Check | Command | Needs |
|---|---|---|
| Every corpus entry points at a real paper, repository, license, and script | `python scripts/verify_corpus.py` | network (set `GITHUB_TOKEN` to avoid rate limits) |
| The sandbox holds its isolation promises | `python scripts/sandbox_acceptance.py --wheel-dir <dir>` | Docker, the sandbox image |
| Hostile probes against the container boundary | `python scripts/security_audit.py` | Docker, the sandbox image |

Build the sandbox image once with `docker build -f docker/Dockerfile.sandbox -t repro-radar-sandbox:latest .` (see [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md); images for Python 3.8 and 3.9 are built with `--build-arg PYTHON_VERSION=...`, the image tags are `repro-radar-sandbox:py3.8` and `:py3.9`, see `image_for` in `src/sandbox/runner.py`).

## 4. Rules that are not negotiable

- **No result without evidence.** Do not write "fixed", "done", "verified", or a number into a document or a pull request unless the command output that shows it is in the same place. If you could not check something, write **not verified** and say why.
- **Every number in the report comes from a script.** No hand-typed results; name the script and the data file ([`docs/report/REPORT.md`](docs/report/REPORT.md), `scripts/report_numbers.py`).
- **Simulated data is labeled** as a simulation wherever it appears, and is never stored as a result.
- **No secrets.** API keys are read from environment variables and never committed. Nothing that identifies a person is committed.
- **Claims are accepted by a person.** A claim extracted from a paper by an AI model or a script reaches scoring only after the maintainer has reviewed it one by one ([`docs/CLAIM_SCHEMA.md`](docs/CLAIM_SCHEMA.md), [`docs/AGENT_EXTRACTION.md`](docs/AGENT_EXTRACTION.md)). Never edit `expected_claims` in `data/seed_papers.json` by hand to make a number match.
- **A schema change needs a migration.** Edit `data/schema.sql` and add a migration in `src/migrations.py` that does the same to an existing database; `tests/test_migrations.py` fails when the two differ. Never edit a merged migration.
- **Do not change a paper's run settings to make it pass.** After a pilot starts, the per-paper settings are frozen; only defects in Repro Radar's own code are fixed ([`docs/PILOT_2.md`](docs/PILOT_2.md), section 9).
- **UI decisions belong to the maintainer** (layout, colors, fonts, badge design, report layout): ask with two or three options and a preview before building.

## 5. How AI assistance is handled

AI coding assistants are allowed. Say in the pull request which parts they wrote and what you checked by hand. Review the diff yourself: the pull request template asks for it, and the self-review comment is how a reader knows you did.

## 6. What a reviewer checks

A pull request is ready to merge when:

1. It is **one topic** and matches its issue; files unrelated to the issue are not touched.
2. `ruff check .` is clean and the full suite passes. The output is in the pull request, since CI is off.
3. New behavior has a test that would fail without the change.
4. Documents and `docs/PROGRESS.md` agree with the code, and each claim of success has evidence next to it.
5. The "What I did NOT verify" section is specific, not "nothing".
6. Nothing simulated is presented as real, and no secret or large generated file is committed.
7. For a **new paper**: every point of [`docs/PAPER_ONBOARDING.md`](docs/PAPER_ONBOARDING.md), section 5.

The maintainer merges after reading the diff. A change that touches what counts as a result (claims, scoring, the sandbox limits) may be held until the maintainer has decided.
