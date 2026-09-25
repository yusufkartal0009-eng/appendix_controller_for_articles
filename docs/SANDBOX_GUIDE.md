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
        Runner -->|docker run --network none| Sandbox[Container Runtime]
        StagingDir -.->|Mount :ro| RepoMount[/workspace/repo:ro]
        PackageDir -.->|Mount :ro| PkgMount[/workspace/packages:ro]
        Sandbox -->|Writes to| OutMount[/workspace/output:rw]
        Sandbox -->|tmpfs noexec| TmpMount[/tmp:rw,noexec]
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
| **User Home & Packages**| `--tmpfs /workspace/home:rw,nosuid,size=2048m` | High-capacity in-memory home workspace allowing execution of compiled C-extensions (`.so`) for scientific packages (PyTorch, SciPy). |
| **Working Directory** | `-w /workspace/repo` | Ensures execution runs directly in the cloned repository context so local imports (`import utils`) and relative data paths resolve seamlessly. |
| **User Space Drop** | `--user 1000:1000` | Code executes under non-root unprivileged user `sandboxuser`. |
| **Privilege Escalation**| `--security-opt no-new-privileges:true` | Prevents sub-processes from acquiring additional privileges via `setuid` or capabilities. |
| **CPU Quota** | `--cpus 2.0` | Caps container execution to 2 CPU cores, preserving host responsiveness. |
| **Memory Ceiling** | `--memory 8g --memory-swap 8g` | Hard ceiling of 8 GB RAM; disabling swap expansion prevents host swap exhaustion. |
| **Process Quota** | `--pids-limit 100` | Prevents fork-bomb vulnerabilities and uncontrolled thread spawning. |
| **Hard Timeout** | `timeout <N>s` in `entrypoint.sh` | Enforces deterministic termination if code hangs, deadlocks, or loops indefinitely (default: 300s). |

---

## 📦 Staging & Offline Dependency Pipeline

Because production sandbox containers run with `--network none`, dependencies cannot be fetched via `pip install` during runtime from PyPI. Repro Radar resolves this with a two-phase staging and installation workflow:

1. **Staging Phase (Online Host)**:
   - The repository is cloned via `git clone` (supporting GitHub, IEEE open repositories, or local directories).
   - If a specific commit hash or tag is provided, it is checked out to guarantee version locking.
   - Manifest files (`requirements.txt`, `pyproject.toml`, `setup.py`, `environment.yml`) are scanned.
   - When `--bundle-deps` is passed, `pip download` compiles an offline wheelhouse directory (`<paper_id>_packages/`).

2. **Installation & Execution Phase (Isolated Sandbox)**:
   - The staged repository is mounted into `/workspace/repo:ro`.
   - The package wheelhouse is mounted into `/workspace/packages:ro`.
   - Container bootstrap (`entrypoint.sh`) executes an offline user installation:
     `pip install --no-index --find-links=/workspace/packages --no-cache-dir --user -r /workspace/repo/requirements.txt`
   - Installed packages are stored in writable in-memory `/workspace/home/.local` with `PYTHONUSERBASE` and `PYTHONPATH` preconfigured.
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

## 🔄 Graceful Host Fallback Mode

If Docker is not installed or the Docker daemon is temporarily unreachable on the development machine, `DockerSandboxRunner` automatically activates `ProcessSandboxRunner`.

In fallback mode:
- The script executes in a managed local subprocess jail.
- Timeout protection and environment variable isolation (`SANDBOX_OUTPUT_DIR`, `PYTHONUNBUFFERED`) remain active.
- Output logs and run reports are recorded identically.
- The `docker_used` flag is set to `false`, and `error_message` records the fallback reason so review systems can track whether execution was containerized or local.
