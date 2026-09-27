# Repro Radar — Decision Log

> Decisions that change what the sandbox allows, with their context, risks, and evidence.
> Architecture decisions that do not affect security go to `docs/ARCHITECTURE.md`.

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
