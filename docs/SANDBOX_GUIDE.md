# Repro Radar: Isolated Sandbox Execution & Staging Guide 🛡️

Repro Radar reproduces and audits scientific codebases (including machine learning, empirical algorithms, and scientific computing) inside an isolated, resource-constrained sandbox environment.

This guide details the security topology, execution lifecycle, repository staging workflow, and CLI automation.

---

## 🏗️ Architecture & Security Model

When testing research code, security and isolation are primary concerns:
- Research repositories may contain unvetted dependencies or scripts.
- Memory and CPU usage must be strictly bounded to prevent runaway compute or out-of-memory crashes.
- Network exfiltration or dependencies on remote dynamic APIs must be prevented to guarantee authentic offline reproducibility.

```mermaid
graph TD
    subgraph Host Environment
        CLI[scripts/stage_and_bundle_repo.py] --> Stager[RepoStager (src/sandbox/stager.py)]
        Stager -->|1. Clone / Copy| StagingDir[.sandbox_staging/]
        Stager -->|2. Pre-download Wheels| PackageDir[offline packages/]
        Stager --> Runner[DockerSandboxRunner (src/sandbox/runner.py)]
    end

    subgraph Docker Container Boundary [Isolated Container: repro-radar-sandbox]
        Runner -->|1. install phase, --network none| Install[Install container]
        PackageDir -.->|Mount :ro| PkgMount[/workspace/packages:ro]
        Install -->|binary wheels only| DepsDir[host deps/ at /workspace/deps:rw]
        Runner -->|2. run phase, --network none| Sandbox[Run container]
        StagingDir -.->|Mount :ro| RepoMount[/workspace/repo:ro]
        DepsDir -.->|Mount :ro, exec allowed| DepsMount[/workspace/deps:ro]
        Sandbox -->|Writes to| OutMount[/workspace/output:rw]
        Sandbox -->|tmpfs noexec| TmpMount[/tmp and /workspace/home: noexec]
    end

    subgraph Output & Audit Artifacts
        OutMount --> OutFiles[stdout.log / stderr.log]
        OutMount --> Meta[execution_meta.json]
        OutMount --> Report[run_report.json / metrics.json]
    end
```

---

## 🔒 Security Hardening Specifications

| Security Vector | Implementation Flag | Rationale / Defense |
| :--- | :--- | :--- |
| **Network Isolation** | `--network none` | Completely prevents network egress/ingress; guarantees reproducibility without relying on external live APIs and eliminates data exfiltration risks. |
| **Filesystem Integrity**| `--read-only` | Locks container root filesystem; untrusted code cannot tamper with OS binaries or persist system backdoors. |
| **Repository Safety** | `-v <repo>:/workspace/repo:ro` | Mounts paper source code as strictly read-only; source code is never altered by execution. |
| **Temporary Storage** | `--tmpfs /tmp:rw,noexec,nosuid,size=64m` | In-memory temporary directory forbidding binary execution (`noexec`) and privilege escalation (`nosuid`). |
| **User Home** | `--tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000` | Writable in-memory scratch home owned by the sandbox user. **`noexec`**: paper code can write here but cannot execute or load anything it wrote (a copied `.so` fails with `failed to map segment from shared object`). |
| **Dependencies** | `-v <deps>:/workspace/deps:ro` (run) / `:rw` (install phase only) | Offline wheels are installed by a separate install-phase container, binary-only (no package code runs), into a host directory. The paper run mounts it **read-only**: compiled extensions load, but paper code cannot modify them or add executables. Together with the `noexec` home and `/tmp`, no location is both writable and executable for paper code. |
| **Working Directory** | `-w /workspace/repo` | Ensures execution runs directly in the cloned repository context so local imports (`import utils`) and relative data paths resolve seamlessly. |
| **User Space Drop** | `--user 1000:1000` | Code executes under non-root unprivileged user `sandboxuser`. |
| **Privilege Escalation**| `--security-opt no-new-privileges:true` | Prevents sub-processes from acquiring additional privileges via `setuid` or capabilities. |
| **CPU Quota** | `--cpus 2.0` | Caps container execution to 2 CPU cores, preserving host responsiveness. |
| **Memory Ceiling** | `--memory 8g --memory-swap 8g` | Hard ceiling of 8 GB RAM; disabling swap expansion prevents host swap exhaustion. |
| **Process Quota** | `--pids-limit 100` | Prevents fork-bomb vulnerabilities and uncontrolled thread spawning. |
| **Hard Timeout** | `timeout --signal=SIGKILL <N>` in `entrypoint.sh` | Enforces termination if code hangs or loops; the run is recorded as `TIMEOUT` (default 600 s in `SandboxConfig`, 300 s in `scripts/stage_and_bundle_repo.py`). |

Real-Docker evidence for the non-root user, network isolation, read-only root, timeout, offline install, and refusal without Docker, plus the CPU/memory/PID limits and the `noexec` home mount, is recorded in [SANDBOX_ACCEPTANCE.md](SANDBOX_ACCEPTANCE.md) and re-checked by CI on every change.

---

## 📦 Staging & Offline Dependency Pipeline

Because production sandbox containers run with `--network none`, dependencies cannot be fetched via `pip install` during runtime from PyPI. Repro Radar resolves this with a two-phase staging and installation workflow:

1. **Staging Phase (Online Host)**:
   - The repository is cloned via `git clone` (supporting GitHub, IEEE open repositories, or local directories).
   - If a specific commit hash or tag is provided, it is checked out to guarantee version locking.
   - Manifest files (`requirements.txt`, `pyproject.toml`, `setup.py`, `environment.yml`) are scanned.
   - When `--bundle-deps` is passed, `pip download` fetches an offline wheelhouse (`<paper_id>_packages/`) for the sandbox platform (manylinux, CPython 3.11), binary wheels only, regardless of the host OS, from every `*requirements*.txt` in the repository root. Requirements without a binary wheel are never built on the host: the bundle result lists each of them as `NEEDS_SDIST_BUILD` (the staging CLI prints them).

2. **Install Phase (separate container, network off)**:
   - The package wheelhouse is mounted at `/workspace/packages:ro`, the staged repository at `/workspace/repo:ro`, and a fresh host directory (`sandbox_runs/<paper_id>/deps`) at `/workspace/deps:rw`.
   - `entrypoint.sh` with `SANDBOX_PHASE=install` runs
     `python -m pip install --no-index --find-links=/workspace/packages --only-binary=:all: --target /workspace/deps` with `-r` for every `*requirements*.txt` in the repository root (the same files that were bundled).
     Binary wheels only: installing a wheel copies files and runs no package code (an sdist would run `setup.py`).
   - The result is written to `install_meta.json` (`INSTALLED` or `FAILED`) and `install.log`.

3. **Run Phase (Isolated Sandbox)**:
   - `/workspace/deps` is mounted **read-only** and is on `PYTHONPATH`; `/workspace/packages` is not mounted.
   - The install result is recorded as `dependency_install_status` (`SKIPPED`, `INSTALLED`, or `FAILED`) in `execution_meta.json`; a failed install does not stop the run.
   - Verified in [SANDBOX_ACCEPTANCE.md](SANDBOX_ACCEPTANCE.md) with a pure-Python wheel (`toolz`, check 5) and a wheel with a C extension (`ujson`, check 7), neither of which is in the image.
   - All standard output, standard error, Python-measured duration, and generated metrics are collected into `/workspace/output`.

---

## 🚀 CLI Usage & Automation

Repro Radar provides an automated CLI script: `scripts/stage_and_bundle_repo.py`.

### 1. Basic Remote Repository Execution
Clone a remote paper repository, auto-detect its main entrypoint, and run inside the sandbox:
```bash
python scripts/stage_and_bundle_repo.py https://github.com/example-author/paper-appendix.git
```

### 2. Specify Paper ID and Target Script
```bash
python scripts/stage_and_bundle_repo.py https://github.com/example-author/paper-appendix.git \
    --paper-id ieee_paper_042 \
    --script evaluate.py \
    --script-args --dataset test --batch-size 32
```

### 3. Pin Git Commit and Pre-Bundle Offline Dependencies
```bash
python scripts/stage_and_bundle_repo.py https://github.com/example-author/paper-appendix.git \
    --commit c7f3b89 \
    --bundle-deps \
    --timeout 600 \
    --memory 8192M
```

### 4. Stage and Execute a Local Directory
For offline datasets or manually downloaded IEEE appendix archives:
```bash
python scripts/stage_and_bundle_repo.py ./path/to/downloaded_repo \
    --paper-id local_experiment_01 \
    --output-json ./sandbox_runs/local_experiment_01/final_report.json
```

### 5. Staging-Only Mode (Inspect Manifest Without Running)
```bash
python scripts/stage_and_bundle_repo.py https://github.com/example-author/paper-appendix.git \
    --no-run
```

---

## 📊 Output Artifacts & JSON Schema

Upon completion, each execution run produces structured artifacts inside `sandbox_runs/<paper_id>/`:

- **`stdout.log`**: Complete unbuffered console output.
- **`stderr.log`**: Standard error traces or warning streams.
- **`execution_meta.json`** (written by the container entrypoint): `status` (`COMPLETED` / `FAILED` / `TIMEOUT`), `exit_code`, `duration_seconds`, `timeout_limit_seconds`, `dependency_install_status` (`SKIPPED` when no wheels are mounted, `INSTALLED`, or `FAILED`; a failed install does not stop the run), `user_id`, and `group_id`.
- **`run_report.json`**: Complete execution report. If `execution_meta.json` cannot be read, the report carries a `meta_error` field and `meta` is empty. Structured as:

```json
{
  "paper_id": "ieee_paper_042",
  "source": "https://github.com/example-author/paper-appendix.git",
  "commit_hash": "c7f3b89412dae954c25964f4340a5a676b7ef293",
  "target_script": "evaluate.py",
  "status": "COMPLETED",
  "exit_code": 0,
  "duration_seconds": 14.82,
  "docker_used": true,
  "error_message": null,
  "output_dir": "sandbox_runs/ieee_paper_042",
  "generated_files": [
    "stdout.log",
    "stderr.log",
    "execution_meta.json",
    "metrics.json"
  ],
  "metrics": {
    "accuracy": 0.942,
    "f1_score": 0.938
  }
}
```

---

## ⛔ No Docker: Execution Is Refused

If Docker is not installed or the daemon is unreachable, `DockerSandboxRunner.run()` raises `SandboxUnavailableError` and **executes nothing**. `scripts/stage_and_bundle_repo.py` prints the reason to stderr and exits with code `4`. There is no silent fallback.

## ⚠️ Unsafe Local Mode (`--allow-unsafe-local`)

**Development only, and only for code you trust.** With `--allow-unsafe-local` (or `SandboxConfig(allow_unsafe_local=True)` in code), a machine without Docker runs the target script through `ProcessSandboxRunner`, directly on the host:

- There is **no isolation**: the script has your user's file-system permissions and full network access. Only the timeout and log capture remain.
- A red warning is printed to stderr before execution, and a red `WARNING: NOT ISOLATED` banner after the run summary.
- The run report records `"docker_used": false` and `"isolated": false`, so unisolated results can never be mistaken for sandboxed ones.

```bash
python scripts/stage_and_bundle_repo.py ./my_own_trusted_repo --script run.py --allow-unsafe-local
```

Never use this flag for third-party paper repositories.
