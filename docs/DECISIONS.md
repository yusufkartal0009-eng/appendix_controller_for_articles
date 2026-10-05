# Repro Radar — Decision Log

> Decisions that change what the sandbox allows (D-001, D-002), or that decide how evidence is produced and where
> the work runs (D-003 to D-007), with their context, risks, and evidence. Other architecture decisions go to
> `docs/ARCHITECTURE.md`.

---

## D-001 — `/workspace/home` stays `noexec` (2026-09-27)

**Status:** accepted (supersedes the intent of PR #64). **Related:** PR #64, #87, #91, #92, #95.

### Context

- `/workspace/home` is an in-memory tmpfs that the paper code can write to (it is the sandbox user's home).
- **PR #64** (merged 2026-09-18, commit `cd6ff82`) changed its mount flags from `rw,noexec,nosuid,size=128m` to `rw,nosuid,size=2048m` in `src/sandbox/runner.py` and `docker/docker-compose.sandbox.yml`. The PR description gives the intent (compiled `.so` extensions of offline-installed packages such as PyTorch or SciPy could not load from `~/.local`, and 128 MB was too small) but no assessment of the security risk.
- **What actually happened:** Docker adds `noexec` (and `nodev`) to `--tmpfs` mounts by default, so removing the flag had no effect. The real-Docker acceptance run (CI run `36314893982`, PR #87) printed, with the PR #64 flags in place:
  ```
  mount: /workspace/home rw,nosuid,nodev,noexec,relatime,size=2097152k,mode=700,uid=1000,gid=1000,inode64
  PermissionError: [Errno 13] Permission denied: '/workspace/home/probe.sh'
  ```
  So the risk PR #64 would have introduced never materialized, and neither did its benefit: compiled dependencies could not load (issue #92). The same runs found the mount was also root-owned, so nothing could be installed there at all (fixed in #91).

### Decision

1. Keep `/workspace/home` (and `/tmp`) `noexec`, and state it explicitly in the mount flags (`rw,noexec,nosuid,size=2048m,uid=1000,gid=1000`) instead of relying on Docker's default.
2. Load compiled dependencies from a different place: see D-002.

### Risk that `exec` would have added (why it was not chosen)

With `exec` on a location the paper code can write, the code could write a binary or shared object and run it. That gives untrusted code native execution outside the Python interpreter (e.g. a downloaded-then-compiled payload, or `ctypes` loading a planted `.so`), which makes any kernel or container escape attempt easier. The other isolation layers (no network, read-only root, uid 1000, `no-new-privileges`, resource limits) would still apply, but one layer of defense would be removed for no reason once D-002 exists.

### Remaining risk of this decision, and why it is acceptable

- **Paper code that legitimately compiles or runs its own binaries at runtime** (e.g. JIT caches written to the home directory, or a build step inside the script) will fail with `Permission denied` / `failed to map segment from shared object`. Accepted: such failures are visible in the run's stderr and are the paper's reproducibility problem to report, not a reason to weaken isolation. If a pilot paper needs it, it will be decided per paper and recorded here.
- **Size 2048 MB (RAM-backed)**, raised by PR #64 from 128 MB, is kept: tmpfs pages are expected to be charged to the container's memory cgroup (8 GB limit), which would stop it from exhausting host memory; this was not tested here. Dependencies no longer live there (D-002), so it could be lowered later if memory is tight.

### Evidence

`docs/SANDBOX_ACCEPTANCE.md` (CI run `36316295634`): the mount shows `noexec`; a compiled module copied into `/workspace/home` fails with `failed to map segment from shared object`, while the same module loads from `/workspace/deps` (check 7).

---

## D-002 — Dependencies are installed in a separate phase and mounted read-only (2026-09-27)

**Status:** accepted. **Related:** #92, PR #95, #102, PR #103.

### Context

Papers need compiled dependencies (e.g. PyTorch). They must be installed without network access, must be able to load, and must not give the paper code a location that is both writable and executable (D-001).

### Decision

- An **install-phase** container (same isolation flags as the run, network off) installs wheels from `/workspace/packages` with `--only-binary=:all:` into a host directory mounted at `/workspace/deps:rw`. Installing a wheel only copies files; no package code runs.
- The **run-phase** container mounts that directory **read-only** at `/workspace/deps` (on `PYTHONPATH`). Compiled extensions load from it; the paper code cannot modify it or add files. The host directory is world-writable only while the install container writes to it, then restored to `0755`.
- Bundling on the host (`pip download`) is binary-only for the sandbox platform, so no repository code runs on the host either; requirements without a wheel are reported as `NEEDS_SDIST_BUILD` (PR #103).

### Alternatives rejected

- **`exec` on `/workspace/home`:** see D-001.
- **Pre-installing dependencies into the image:** the seed papers pin different and large versions (e.g. old PyTorch for TabPFN); one image cannot hold all of them, and new papers would still fail.

### Remaining risk

The install phase reads the paper's requirements files (untrusted input), but only to select wheels from the local wheelhouse; no package code executes before the fully isolated run. Requirements published only as sdists cannot be installed (`NEEDS_SDIST_BUILD`); building them would need its own isolated build step, not decided yet.

### Evidence

`docs/SANDBOX_ACCEPTANCE.md` check 7: `ujson` loads from `/workspace/deps/ujson.cpython-311-x86_64-linux-gnu.so`; writing to `/workspace/deps` fails with `Read-only file system`.

---

## D-003 — Claim extraction uses Claude Opus 5.5, without a temperature setting (2026-10-01)

**Status:** accepted by the owner on 2026-10-01; **partly superseded on the same day by D-004 and D-005**: extraction is agent-assisted for now, and the consistency rule of D-005 replaces the temperature question. The API path described here stays in the code for later use. **Related:** #131 (W3), #132 (W4), #9, roadmap section 3.

### Context

Roadmap W3 asks for temperature 0, JSON-schema output, a mandatory source quote, "not found" instead of guessing,
one model provider with a written reason, the API key only from an environment variable, and cached responses.

### Decision

1. **Provider and model:** Anthropic, Claude Opus 5.5 (`claude-opus-5-5`), chosen by the owner. It supports JSON-schema
   output, and its context window (1M tokens) holds a whole paper in one request (`paper_003`: 25 pages,
   about 26,000 tokens), so every quote can name its PDF page. List price: $4 per million input tokens and $20 per
   million output tokens, about $0.30 per paper estimated before the first run.
2. **No temperature.** Claude Opus 5.5 rejects sampling parameters (`temperature`, `top_p`, `top_k` return HTTP 400),
   and its thinking cannot be switched off. Repeatability is not taken from the model; it comes from three things
   around it:
   - **Response cache:** a response is stored under a hash of the model, effort, prompt version, output schema, PDF
     hash, and queries (`src/claim_extraction.py`). A repeated run returns the stored answer unchanged.
   - **Verbatim quote guard (W4):** a claim is used only if its printed value and its quote occur in the text of
     the page it cites. A non-deterministic model can change which claims it finds, but not what an accepted
     number says.
   - **Human confirmation (W7):** only accepted claims enter scoring.
3. **Structured output:** `output_config.format` with a JSON schema. `value_normalized` is computed by code from
   `value_as_printed` (`src/claim_schema.py`), never by the model.
4. **Refusal fallback:** requests opt into the server-side fallback (`fallbacks: "default"`). If a safety classifier
   declines a request, the API runs it on Anthropic's recommended fallback model. The model that actually answered,
   and whether a fallback ran, are recorded with every result.
5. **Credentials:** the SDK reads `ANTHROPIC_API_KEY` from the environment; no key is passed in code, stored, or
   committed (`AGENTS.md` §6.7). Tests use a fake client, so CI makes no API calls.

### Alternatives rejected

- **Claude Haiku 4.5 with temperature 0:** it still accepts sampling parameters, but it is a weaker model, and
  temperature 0 does not guarantee identical output across model or API versions either.
- **Relying on the model alone:** without the quote guard, a fluent but wrong number (like the seed's invented
  `EP3602` claims) would be indistinguishable from a real one.

### Remaining risk

- A run with a cleared cache, or with a new prompt version, can return different answers. The stored extraction
  results (`data/claim_extractions/`) record the model, prompt version, and response ID of each result.
- If the fallback runs, a different model answered; this is recorded, and the cost estimate (computed with Opus 5.5
  prices) is then approximate.

### Evidence

`tests/test_claim_extraction.py` checks the request settings (model, effort, no temperature, schema, fallback), the
cache, and the handling of refusals and truncated output. The first real runs are recorded in #131 and #133.

---

## D-004 — Claim extraction is agent-assisted; no API key for now (2026-10-01)

**Status:** decided by the owner on 2026-10-01 (`docs/PLAN_2026-10-01.md`, section 0, decision 1; recorded in #168).
**Related:** #131, #132, #133, #134, D-003.

### Context

PR #156 (W3) added extraction through the Claude API (`src/claim_extraction.py`), which needs `ANTHROPIC_API_KEY`.
No real API call was made: the key was not available to the working session.

### Decision

- **No API key will be used for now.** Claim extraction is done by the Claude Code agent ("agent-assisted
  extraction"): it reads the paper's page text (W2, `src/pdf_text.py`) and records every claim as JSON according to
  the W1 schema (`docs/CLAIM_SCHEMA.md`), with its verbatim quote and page number, in `data/claims/<paper_id>.json`.
- **The API code of PR #156 is not deleted.** If a key becomes available later, it is used with the same schema.

### Reason

The owner's decision: no API key is used for now. The plan gives no further reason.

### Consequences

- Extraction is not a script that anyone can re-run; the checks around it carry the weight: the consistency rule
  (D-005), the verbatim quote guard (W4, `src/quote_guard.py`), and the owner's approval (W7, #134).
- The extracting agent's own answers cannot serve as the gold set for measuring it. The owner chooses and confirms
  the gold values (plan item Y3, #133); the agent only prepares the form.
- D-003 still describes the API path; it applies only when that path is used. Because both paths use the same
  schema, they produce the same kind of record and pass through the same checks.

---

## D-005 — "Temperature 0" is dropped; two independent extractions must agree on the numbers (2026-10-01)

**Status:** decided by the owner on 2026-10-01 (`docs/PLAN_2026-10-01.md`, section 0, decision 2; recorded in #168).
**Related:** #131, #134, D-003, D-004.

### Context

The 2026-09-27 roadmap (W3) required "temperature 0" for extraction, so that repeated extractions would give the
same answers. D-003 already recorded that Claude Opus 5.5 rejects a temperature setting; with agent-assisted
extraction (D-004) there is no such setting either.

### Decision

The temperature requirement is dropped. A simpler consistency rule replaces it:

> When the same claim is found in two separate extractions, **the numeric value after W1 normalization must be the
> same** (e.g. `96.99 %` → `0.9699`). The quote text, the description, or the field names may differ; all that
> matters is that the numbers agree. Every value that does not agree goes to the owner for approval in W7.

### Reason

As the plan states, the quote text, description, or field names may differ; what matters is only that the numbers
agree. Comparing normalized values checks exactly that.

### Consequences

- Every paper is extracted **twice, independently of each other** (plan step 1.1), and a script compares the two
  extractions by normalized value (step 1.2, #131).
- Every disagreement is listed and goes to the owner in W7 (#134); it is never resolved silently.

---

## D-006 — Everything runs locally; no server or website (2026-10-01)

**Status:** decided by the owner on 2026-10-01 (`docs/PLAN_2026-10-01.md`, section 0, decision 3; recorded in #168).
**Related:** #170, #171, #172, #37-#41, `docs/PILOT_WEEK2.md`.

### Context

Pilot 1 ran on GitHub-hosted runners (`.github/workflows/pilot.yml`) because the owner's machine had no Docker. The
dashboard backlog (#37-#41) did not say where the dashboard would run.

### Decision

- There is no server or website. Everything runs locally on the owner's computer; the dashboard too, on `localhost`.
- Paper runs happen locally, once Docker is installed on the owner's computer (plan item Y1, #172).
- GitHub Actions stays only for CI.

### Reason

The owner's decision; the plan gives no further reason.

### Consequences

- The dashboard skeleton (D0, #170) and D1-D5 (#37-#41) are built and tested for `localhost` only; nothing is deployed.
- Pilot 2 (#171) runs on the owner's machine in real Docker, not on GitHub Actions. Pilot 1's workflow and stored
  results stay in the repository as the record of Pilot 1.
- Local runs depend on Docker Desktop with WSL2 and enough disk space (#172); using the local GPU is #169.

---

## D-007 — Papers that cannot be made to run may be replaced, with a record (2026-10-01)

**Status:** decided by the owner on 2026-10-01 (`docs/PLAN_2026-10-01.md`, section 0, decision 4; recorded in #168).
**Related:** #166, #171, `docs/PILOT_WEEK2.md`, `docs/CORPUS_VERIFICATION.md`.

### Context

In Pilot 1 none of the six papers reached its experiment code (pilot success 0 / 6).

### Decision

Papers that cannot be fixed may be replaced with new ones (#166). Every replacement is recorded with its reason, and
the first pilot result (0 / 6) stays on record.

### Reason

As the plan states: choosing only papers that "work" would raise the success rate artificially. Recording every
replacement and keeping Pilot 1's result makes such a selection visible instead of hiding it.

### Consequences

- A replacement is decided per paper (fix or replace, plan step 2.5, #166) and written down with its reason, for
  example in `docs/CORPUS_VERIFICATION.md`.
- The Pilot 2 report (#171) shows Pilot 1's result next to its own and names every replaced paper.

## D-008 — Package build code runs in a separate, isolated build phase (2026-10-05)

**Status:** decided by the agent on 2026-10-05 while resolving #193, under the owner's instruction to resolve the
open run-setup items without waiting; open to the owner's review.
**Related:** #193, #166, D-001, `docker/Dockerfile.sandbox` (target `build`), `docker/entrypoint.sh` (build phase).

### Context

The install phase installs binary wheels only, so that no package code runs while installing. Three seed papers
need packages that exist only as source: `openml` and `liac-arff` (`paper_002`, `paper_006`) and the `fastsk` C++
extension (`paper_005`). Building them runs their `setup.py`. Building on the host would run third-party code
outside the sandbox, and `pip download` of an sdist already runs its metadata hooks on the host.

### Decision

- Sdists are downloaded on the host from the PyPI JSON API and checked against PyPI's SHA-256 digest; nothing in
  them runs on the host.
- A separate **build phase** builds them into wheels inside the sandbox, from the build image (the sandbox image
  plus `build-essential`, `setuptools`, and `wheel`). It runs under the same isolation as paper code: network off,
  uid 1000, read-only root. Only the build output directory is writable, plus a per-run copy of the repository
  when building from it.
- The install phase stays binary-only and installs the built wheels like any other wheel. Paper runs use the
  default image, which has no compiler.

### Reason

Build code is third-party code, like paper code, so it gets the paper code's isolation. Keeping the compiler out of
the run image and keeping the install phase binary-only keeps the earlier guarantees (D-001) unchanged.

### Consequences

- CI builds a second image per Python version (`repro-radar-sandbox:build`, `:py3.9-build`, `:py3.8-build`), and
  real-Docker acceptance check 18 covers the phase.
- Wheels built this way carry the plain `linux_x86_64` tag. Bundling accepts that platform only when built wheels
  are present.

