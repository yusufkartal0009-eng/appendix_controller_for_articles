# Repro Radar — Sandbox Acceptance Evidence

> Real commands and output showing what the Docker sandbox enforces. Every section below is copied
> verbatim from a CI run; nothing is paraphrased. A check without output here is not claimed.

## Provenance

| | |
|---|---|
| Script | `scripts/sandbox_acceptance.py` (runs probe scripts through `DockerSandboxRunner`, the same code path as paper runs) |
| Where | GitHub Actions `ubuntu-latest`, job `Sandbox acceptance (real Docker)`, host user uid 1001 |
| Run | CI run `37327002007` on commit `50838e5` (PR for #193), 2026-10-05; verbatim output below is the Python 3.11 image (`repro-radar-sandbox:latest`) |
| Other images | The same 19 checks passed in the same run for `repro-radar-sandbox:py3.9` and `repro-radar-sandbox:py3.8` (job logs `Sandbox acceptance (real Docker, Python 3.9)` / `(…, Python 3.8)`; #158, #159, #161, #163, #193) |
| Image | `repro-radar-sandbox:latest` built from `docker/Dockerfile.sandbox` in the same job |
| Re-run | `python scripts/sandbox_acceptance.py --wheel-dir <dir>` on a host with Docker; `<dir>` holds `toolz==0.12.1` and `ujson==5.10.0` wheels (manylinux, CPython 3.11) |

The job ran on every push and pull request and failed if any check failed. The CI workflow was removed in #388 (`docs/DECISIONS.md` D-010), so the evidence below is from the CI run named above; re-run the checks locally with the command in the table.


## Results

| # | Check | Result | Evidence (below) |
|---|---|---|---|
| 1 | Container runs as a non-root user | **PASS** | `uid=1000 gid=1000` |
| 2 | Network is disabled | **PASS** | TCP, DNS, and HTTPS all fail (`Network is unreachable`, name resolution failure) |
| 3 | Root filesystem is read-only | **PASS** | root mount `ro`; writes to `/`, `/usr`, `/workspace/repo` fail with `EROFS` |
| 4 | Timeout produces `TIMEOUT` with `duration_seconds > 0` | **PASS** | limit 5 s: `TIMEOUT`, exit 137, `duration_seconds: 5.11` |
| 5 | Offline install of a pure-Python wheel | **PASS** | `toolz` (not in the image) imported from `/workspace/deps/toolz/__init__.py` |
| 6 | Without Docker, execution is refused | **PASS** | `SandboxUnavailableError`; the probe's marker file was not created |
| 7 | Offline install of a compiled wheel | **PASS** | `ujson` C extension loaded from `/workspace/deps/ujson.cpython-311-x86_64-linux-gnu.so`; writing to `/workspace/deps`: `Read-only file system` |
| 8 | Memory limit: OOM kill reported as `OOM_KILLED` | **PASS** | 256 MiB limit: `OOM_KILLED`, exit 137, after `0.163` s (timeout limit 60 s); recorded peak `268435456` bytes = the limit |
| 9 | PID limit holds | **PASS** | `limited after 95 extra threads: RuntimeError: can't start new thread` (`pids.max 100`) |
| 10 | `pip show numpy` vs the Dockerfile bound `numpy>=1.24.0` | **PASS** | numpy `2.4.6`. The Dockerfile sets only a floor, so the exact version is not pinned (GA-6) |
| 11 | Broken requirement → `dependency_install_status: FAILED` | **PASS** | install log: `ERROR: Could not find a version that satisfies the requirement reproradar-no-such-package==9.9.9 (from versions: none)`; run status `COMPLETED`, `dependency_install_status: FAILED` |
| 12 | Peak memory and install duration are recorded | **PASS** | probe holding 200 MiB: `peak_memory_bytes: 221790208` (≥ 200 MiB) in `execution_meta.json`; install phase: `duration_seconds: 0.782`, `peak_memory_bytes: 39800832` in `install_meta.json` |
| 13 | Conda-only repository installed offline (#159) | **PASS** | `environment.yml` without a requirements file: bundle `status=SUCCESS converted=2 downloaded=['toolz==0.12.1', 'ujson==5.10.0'] conda_only=[]`, skipped `_libgcc_mutex`, `libgcc-ng`; run `COMPLETED`, `dependency_install_status: INSTALLED`, both imported from `/workspace/deps/` |
| 14 | Installed package versions recorded (#161) | **PASS** | the install phase of check 5 wrote `installed_packages.json`: `[{"name": "toolz", "version": "0.12.1"}]` |
| 15 | Run setup: working directory, writable copy, read-only data (#166) | **PASS** | run starts in `/workspace/repo/sub`; the file it writes lands in the per-run copy, not in the staged repository; `/workspace/repo/data` is readable and `data writable: False (Read-only file system)` |
| 16 | Image size measured (#163) | **PASS** | `docker image inspect`: `500403624` bytes (477.2 MiB) for `repro-radar-sandbox:latest` (Python 3.11); `473139462` (451.2 MiB) for `:py3.9`; `437381943` (417.1 MiB) for `:py3.8` (same run, the other two job logs) |
| 17 | CPU limit holds under load (#163) | **PASS** | two busy workers for 3 s: under `--cpus=0.5` (`cpu.max 50000 100000`) `effective_cpus=0.49`; control at the runner's 2 CPUs (`--cpus=2.0`, `cpu.max 200000 100000`) `effective_cpus=1.97`. Same on 3.9 (0.49 / 1.98) and 3.8 (0.49 / 1.98) |
| 18 | Build phase: sdist and C extension built offline (#193) | **PASS** | build image `repro-radar-sandbox:build`, `--network none`: `rrtoy_c-1.0-cp311-cp311-linux_x86_64.whl` (from a writable repository copy) and `rrtoy_pure-1.0-py3-none-any.whl` (from an sdist); the run phase installed both and imported them from `/workspace/deps/` (`answer()=42`); `compiler in the run image: None`. Same on `:py3.9-build` and `:py3.8-build` |
| 19 | Writable data copy (#193) | **PASS** | the run read the cached file and wrote `parsed.pkl` into its per-run copy; host cache files afterwards: `['description.xml']` |
| 20 | GPU is opt-in (#169) | **PASS** | default command without `--gpus`; `execution_meta.json` of check 1: `gpu_requested=False gpu_devices=[] gpu_peak_memory_used_mib=None`. From CI run `37330741288` (PR for #169), where all 20 checks passed on all three images; the verbatim output below is from run `37327002007` (checks 1-19). A run with a real GPU is not shown: GitHub's runners have none (`scripts/gpu_check.py` on the owner's machine) |
| 21 | A paper that kills its `timeout` watchdog is not reported as TIMEOUT (#262) | **PASS** (local run, not from the CI run above) | limit 5 s, the probe sends SIGKILL to its parent `timeout` process after 0.5 s: `status=FAILED exit_code=137`, `execution_meta.json` has `killed_before_timeout: true` and `duration_seconds` under 4. Control: check 4 (a real timeout) is still `TIMEOUT`. Run on the owner's machine (Docker 29.8.2) on the 3.11 image rebuilt with the new entrypoint; the CI result of this change is in the pull request |

Informational (not a pass/fail check): CPU, memory, and PID limits are applied inside the container
(`cpu.max 200000 100000` = 2 CPUs, `memory.max 8589934592` = 8 GiB, `pids.max 100`).
`/workspace/home` and `/tmp` are `noexec` on purpose (`docs/DECISIONS.md`, D-001): files written there
cannot be executed or loaded. Check 7's control shows this for a compiled module: `same .so from /workspace/home fails to load: /workspace/home/nx/ujson.cpython-311-x86_64-linux-gnu.so: failed to map segment from shared object`.

Check 6 was also run on a Windows 11 machine with no Docker installed (`docker: command not found`),
using the staging CLI: exit code 4, `ERROR: Docker is not available, so the code cannot be isolated;
refusing to run it on the host...`, and the target script did not run (see PR #81).

## How dependencies are isolated

Dependencies are installed by a separate **install-phase** container (network off, binary wheels only,
so no package code runs) into a host directory mounted at `/workspace/deps:rw`. The **run-phase**
container, which executes the paper code, mounts that directory **read-only**. Compiled extensions can
load from it, but the paper code cannot change them or add executables, and every location it can
write to (`/tmp`, `/workspace/home`, `/workspace/output`) is not executable.

## Findings from building this evidence

The acceptance runs found real defects before the checks could pass. They are listed so the passing
results are not mistaken for "nothing was wrong":

| Finding | Status |
|---|---|
| Runner overwrote logs the container had written as uid 1000; on hosts with another uid every Docker run was reported `FAILED` and its output was dropped | Fixed in #89 (issue #88) |
| `/workspace/home` tmpfs was root-owned, so uid 1000 could not write to it and offline installs always failed | Fixed in #91 (issue #90) |
| The first version of check 5 used `six`, which is already in the image; its "pass" proved nothing | Replaced by `toolz`, which is not in the image, and the import path is asserted |
| `/workspace/home` was `noexec` despite PR #64 removing the flag (Docker adds it by default), so offline-installed compiled wheels could not load | Fixed in #95 (issue #92): separate install phase, read-only `/workspace/deps`; verified by check 7 |
| An OOM kill (exit 137) was reported as `TIMEOUT` (found by check 8) | Fixed in #113 (issue #112): the entrypoint reads the cgroup `oom_kill` counter |
| The runner left the output directory unwritable for the container on hosts not running as uid 1000, so every Docker run there failed and wrote no `execution_meta.json`; the acceptance script hid it by pre-opening the directory | Fixed in #114 (issue #96): the runner opens the directory only during the container phases; the acceptance script no longer pre-opens it |

## Verbatim output

### 1. Non-root user
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_c2ez2p84:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_identity:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_identity.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_identity.py
==================================================
uid=1000 gid=1000
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 0.124s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.124, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 6991872, "user_id": 1000, "group_id": 1000}
```

### 2. Network disabled
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_c2ez2p84:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_network:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_network.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_network.py
==================================================
tcp 1.1.1.1:53: BLOCKED (OSError: [Errno 101] Network is unreachable)
dns example.com: BLOCKED (gaierror: [Errno -3] Temporary failure in name resolution)
https://example.com: BLOCKED (URLError: <urlopen error [Errno -3] Temporary failure in name resolution>)
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 0.321s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.321, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 16015360, "user_id": 1000, "group_id": 1000}
```

### 3. Read-only root filesystem
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_c2ez2p84:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_readonly:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_readonly.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_readonly.py
==================================================
root mount: overlay / overlay ro,relatime,lowerdir=/var/lib/docker/overlay2/l/NO4ZGPBCFC6XLI7OKTWOXQ5JPD:/var/lib/docker/overlay2/l/YLOYOZQPTQS3YCZU3XYC4AARUE:/var/lib/docker/overlay2/l/SANBIHPD6B7QZRXBVHVYNU6CJN:/var/lib/docker/overlay2/l/LLPZEWA4U7TXPHQAQ5JNGNZGCY:/var/lib/docker/overlay2/l/PGAUOA3XADIIKSANOX3IZOQ3DW:/var/lib/docker/overlay2/l/2NYZESJF3COJ7QOGGBOGDJE5DF:/var/lib/docker/overlay2/l/HMY4ZO4WH3Y32OEG2AE6HOGEME:/var/lib/docker/overlay2/l/UCQ5A43ZTCVIQR6RYBIA5F22EY:/var/lib/docker/overlay2/l/7ETSSZHZXDLU5XFPLVJJCIW42C:/var/lib/docker/overlay2/l/XB45K5K7PCV6AO3CW2XZKI7THR:/var/lib/docker/overlay2/l/BDZOVYJT5YB736FB2YUZS3L4RW:/var/lib/docker/overlay2/l/WC5V5JA5AF3KI66RSYOVTOX2BS,upperdir=/var/lib/docker/overlay2/5a0b82b6927e1b0bdb66204e3ff2fbad5b24b3ee5b08e7b4070f207468bfd6d0/diff,workdir=/var/lib/docker/overlay2/5a0b82b6927e1b0bdb66204e3ff2fbad5b24b3ee5b08e7b4070f207468bfd6d0/work,nouserxattr 0 0
/probe_root.txt: EROFS (Read-only file system)
/usr/probe.txt: EROFS (Read-only file system)
/workspace/repo/probe.txt: EROFS (Read-only file system)
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 0.124s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.124, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 8933376, "user_id": 1000, "group_id": 1000}
```

### 4. Timeout (limit 5 s, script sleeps 60 s)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=5 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_c2ez2p84:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_timeout:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_sleep.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 5s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_sleep.py
==================================================
sleeping 60s
==================================================
Repro Radar: Execution Concluded
Status        : TIMEOUT (Exit Code: 137)
Dependencies  : SKIPPED
Duration      : 5.11s
==================================================
status=TIMEOUT exit_code=137 docker_used=True isolated=True
execution_meta.json: {"status": "TIMEOUT", "exit_code": 137, "duration_seconds": 5.11, "timeout_limit_seconds": 5, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 6713344, "user_id": 1000, "group_id": 1000}
stderr (last 1500 chars):
/entrypoint.sh: line 171:    13 Killed                  timeout --signal=SIGKILL "${TIMEOUT_SECONDS}" "$@" > >(tee "${STDOUT_LOG}") 2> >(tee "${STDERR_LOG}" 1>&2)
```

### 5. Offline install from /workspace/packages (toolz-0.12.1-py3-none-any.whl)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=INSTALLED -v /tmp/acceptance_offline_6ulh3kva:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_offline:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_offline/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_import.py
========================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_import.py
==================================================
toolz 0.12.1 imported from /workspace/deps/toolz/__init__.py
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : INSTALLED
Duration      : 0.225s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.225, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "peak_memory_bytes": 12988416, "user_id": 1000, "group_id": 1000}
```

### 7. Compiled wheel installed offline (ujson-5.10.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=INSTALLED -v /tmp/acceptance_compiled_089udvxl:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_compiled:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_compiled/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_compiled.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_compiled.py
==================================================
ujson 5.10.0 imported from /workspace/deps/ujson.cpython-311-x86_64-linux-gnu.so
ujson.dumps -> {"a":[1,2]}
/workspace/deps write attempt: Read-only file system
control: same .so from /workspace/home fails to load: /workspace/home/nx/ujson.cpython-311-x86_64-linux-gnu.so: failed to map segment from shared object
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : INSTALLED
Duration      : 0.197s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.197, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "peak_memory_bytes": 10985472, "user_id": 1000, "group_id": 1000}
```

### 8. Memory limit (256 MiB, probe allocates up to 2 GiB)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=256m --memory-swap=256m --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=60 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_c2ez2p84:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_oom:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_oom.py

==================================================
allocated 32 MiB
allocated 64 MiB
allocated 96 MiB
allocated 128 MiB
allocated 160 MiB
allocated 192 MiB
allocated 224 MiB
==================================================
Repro Radar: Execution Concluded
Status        : OOM_KILLED (Exit Code: 137)
Dependencies  : SKIPPED
Duration      : 0.163s
==================================================
status=OOM_KILLED exit_code=137 docker_used=True isolated=True
execution_meta.json: {"status": "OOM_KILLED", "exit_code": 137, "duration_seconds": 0.163, "timeout_limit_seconds": 60, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 268435456, "user_id": 1000, "group_id": 1000}
stderr (last 1500 chars):
/entrypoint.sh: line 171:    13 Killed                  timeout --signal=SIGKILL "${TIMEOUT_SECONDS}" "$@" > >(tee "${STDOUT_LOG}") 2> >(tee "${STDERR_LOG}" 1>&2)
```

### 9. PID limit (100)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_c2ez2p84:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_pids:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_pids.py
one)
Command       : python /workspace/repo/probe_pids.py
==================================================
limited after 95 extra threads: RuntimeError: can't start new thread
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 0.163s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.163, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 12546048, "user_id": 1000, "group_id": 1000}
```

### 10. `pip show numpy` vs the Dockerfile bound
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_c2ez2p84:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_numpy:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_numpy.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_numpy.py
==================================================
Name: numpy
Version: 2.4.6
Location: /usr/local/lib/python3.11/site-packages
numpy 2.4.6 satisfies >=1.24.0: True
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 0.863s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.863, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 44179456, "user_id": 1000, "group_id": 1000}
```

### 11. Broken requirement (`reproradar-no-such-package==9.9.9`)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=FAILED -v /tmp/acceptance_broken_s62d4v9_:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_broken_req:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_broken_req/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_identity.py
install.log (tail): Looking in links: /workspace/packages
ERROR: Could not find a version that satisfies the requirement reproradar-no-such-package==9.9.9 (from versions: none)
ERROR: No matching distribution found for reproradar-no-such-package==9.9.9
entity.py
==================================================
uid=1000 gid=1000
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : FAILED
Duration      : 0.127s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.127, "timeout_limit_seconds": 120, "dependency_install_status": "FAILED", "peak_memory_bytes": 6975488, "user_id": 1000, "group_id": 1000}
```

### 12. Resource use recorded (run holds 200 MiB after an offline install)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=INSTALLED -v /tmp/acceptance_alloc_spx4lfxv:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_resources:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_resources/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_alloc.py
====================================
holding 200 MiB; toolz 0.12.1 imported
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : INSTALLED
Duration      : 0.252s
==================================================
install_meta.json: {"phase": "install", "status": "INSTALLED", "exit_code": 0, "duration_seconds": 0.782, "peak_memory_bytes": 39800832}
run peak_memory_bytes: 221790208
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.252, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "peak_memory_bytes": 221790208, "user_id": 1000, "group_id": 1000}
```

### 13. Conda-only repository (environment.yml, no requirements file)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=INSTALLED -v /tmp/acceptance_conda_staging_1o1fa7z6/acceptance_conda:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_conda:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_conda/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_conda.py
bundle: status=SUCCESS converted=2 downloaded=['toolz==0.12.1', 'ujson==5.10.0'] conda_only=[] skipped=['_libgcc_mutex=0.1=conda_forge', 'libgcc-ng=13.2.0'] env_python_versions=['3.11']

Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_conda.py
==================================================
toolz imported from /workspace/deps/toolz/__init__.py
ujson imported from /workspace/deps/ujson.cpython-311-x86_64-linux-gnu.so
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : INSTALLED
Duration      : 0.227s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.227, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "peak_memory_bytes": 12935168, "user_id": 1000, "group_id": 1000}
```

### 14. Installed package versions recorded by the install phase
```
$ (reads installed_packages.json of check 5)
installed_packages.json: [{"name": "toolz", "version": "0.12.1"}]
```

### 15. Run setup: working directory, writable copy, read-only data
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo/sub -e SANDBOX_WORKDIR=/workspace/repo/sub -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_runsetup/repo_copy:/workspace/repo:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_runsetup:/workspace/output:rw -v /tmp/acceptance_data_cache_he2e2b7j:/workspace/repo/data:ro repro-radar-sandbox:latest python /workspace/repo/sub/probe_runsetup.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo/sub
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/sub/probe_runsetup.py
==================================================
cwd=/workspace/repo/sub
written next to the script: ok
data: a,b
1,2
data writable: False (Read-only file system)
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 0.124s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.124, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 6705152, "user_id": 1000, "group_id": 1000}
file in the per-run copy: True
file in the staged repository: False
```

### 16. Image size
```
$ docker image inspect repro-radar-sandbox:latest --format {{.Size}}
500403624
size: 500403624 bytes (477.2 MiB)
```

### 17. CPU limit under load
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=0.5 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=60 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_c2ez2p84:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_cpu_limited:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_cpu.py
host CPUs: 2
--cpus=0.5:
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 60s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_cpu.py
==================================================
cpu.max: 50000 100000
workers=2 wall=3.09s cpu=1.50s effective_cpus=0.49
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 3.379s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 3.379, "timeout_limit_seconds": 60, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 14868480, "user_id": 1000, "group_id": 1000}
control --cpus=2.0:
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 60s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_cpu.py
==================================================
cpu.max: 200000 100000
workers=2 wall=3.03s cpu=5.97s effective_cpus=1.97
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 3.24s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 3.24, "timeout_limit_seconds": 60, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 14811136, "user_id": 1000, "group_id": 1000}
```

### 18. Build phase: sdist and C extension built offline, then installed and imported
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_PHASE=build -e SANDBOX_BUILD_TARGETS=/workspace/packages/rrtoy_pure-1.0.tar.gz /workspace/repo -e SANDBOX_BUILD_REQUIREMENTS= -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_build.build/repo_copy:/workspace/repo:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_build.build:/workspace/output:rw -v /tmp/acceptance_build_inputs_6f1pc724:/workspace/packages:ro repro-radar-sandbox:build build-wheels
build image: repro-radar-sandbox:build (repro-radar-sandbox:build)
build status=BUILT exit_code=0 wheels=['rrtoy_c-1.0-cp311-cp311-linux_x86_64.whl', 'rrtoy_pure-1.0-py3-none-any.whl']
build log (last 800 chars):
h status 'done'
  Created wheel for rrtoy_pure: filename=rrtoy_pure-1.0-py3-none-any.whl size=1110 sha256=7a80d4ced9e35c6d2ee7bf67ec63eeaa68fd7cc139625728f5701a9bbb76540d
  Stored in directory: /workspace/output/.build-tmp/pip-ephem-wheel-cache-7ae026ix/wheels/04/71/84/baaa01d165e242c548ec45d1a4243d4b7f5186448bf614d452
  Building wheel for rrtoy_c (pyproject.toml): started
  Building wheel for rrtoy_c (pyproject.toml): finished with status 'done'
  Created wheel for rrtoy_c: filename=rrtoy_c-1.0-cp311-cp311-linux_x86_64.whl size=7168 sha256=536fa10be85a7722189fe477c31af525ec2baa761b48dbde23d326fdd8d0ee86
  Stored in directory: /workspace/output/.build-tmp/pip-ephem-wheel-cache-7ae026ix/wheels/c2/81/f8/80362a24bb9d696a6903cb9e14b079a7f9b71630cac4b95f94
Successfully built rrtoy_pure rrtoy_c
--- run phase ---
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_built.py
==================================================
pure: pure-ok from /workspace/deps/rrtoy_pure.py
c extension: answer()=42 from /workspace/deps/rrtoy_c.cpython-311-x86_64-linux-gnu.so
compiler in the run image: None
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : INSTALLED
Duration      : 0.178s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.178, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "peak_memory_bytes": 9740288, "user_id": 1000, "group_id": 1000}
```

### 19. Writable data copy
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_c2ez2p84:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_datacopy:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_datacopy/data_copies/0:/workspace/home/.cache/lib:rw repro-radar-sandbox:latest python /workspace/repo/probe_datacopy.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_datacopy.py
==================================================
read: <cached/>
wrote parsed.pkl: True
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 0.123s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.123, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 8957952, "user_id": 1000, "group_id": 1000}
file in the per-run copy: True
host cache files: ['description.xml']
```

### 6. Docker unavailable (Docker CLI removed from PATH)
```
$ DockerSandboxRunner().run(...)
shutil.which('docker') -> None
SandboxUnavailableError: Docker is not available, so the code cannot be isolated; refusing to run it on the host. Install and start Docker, or pass --allow-unsafe-local (SandboxConfig.allow_unsafe_local) to run unisolated, only for code you trust.
script marker file exists: False
```

### Info: resource limits and /workspace/home exec
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_WORKDIR=/workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_c2ez2p84:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_info:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_info.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_info.py
==================================================
mount: /tmp rw,nosuid,nodev,noexec,relatime,size=65536k,inode64
mount: /workspace/home rw,nosuid,nodev,noexec,relatime,size=2097152k,mode=700,uid=1000,gid=1000,inode64
/sys/fs/cgroup/cpu.max: 200000 100000
/sys/fs/cgroup/memory.max: 8589934592
/sys/fs/cgroup/pids.max: 100
==================================================
Repro Radar: Execution Concluded
Status        : FAILED (Exit Code: 1)
Dependencies  : SKIPPED
Duration      : 0.199s
==================================================
status=FAILED exit_code=1 docker_used=True isolated=True
execution_meta.json: {"status": "FAILED", "exit_code": 1, "duration_seconds": 0.199, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 10907648, "user_id": 1000, "group_id": 1000}
stderr (last 1500 chars):
Traceback (most recent call last):
  File "/workspace/repo/probe_info.py", line 12, in <module>
    r = subprocess.run([path], capture_output=True, text=True)
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/subprocess.py", line 548, in run
    with Popen(*popenargs, **kwargs) as process:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/subprocess.py", line 1026, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "/usr/local/lib/python3.11/subprocess.py", line 1955, in _execute_child
    raise child_exception_type(errno_num, err_msg, err_filename)
PermissionError: [Errno 13] Permission denied: '/workspace/home/probe.sh'
```

### Summary (as printed by the script)
- PASS: 1 identity (uid 1000)
- PASS: 2 network blocked
- PASS: 3 read-only root
- PASS: 4 timeout
- PASS: 5 offline install
- PASS: 7 compiled wheel offline
- PASS: 8 OOM killed and reported as OOM_KILLED
- PASS: 9 pids limit holds
- PASS: 10 numpy bound respected
- PASS: 11 broken requirement reported FAILED
- PASS: 12 peak memory and install duration recorded
- PASS: 13 conda-only repository installed offline
- PASS: 14 installed versions recorded
- PASS: 15 run setup (working dir, writable copy, read-only data)
- PASS: 16 image size measured
- PASS: 17 cpu limit holds under load
- PASS: 18 build phase (sdist and C extension, offline)
- PASS: 19 writable data copy
- PASS: 6 refused without Docker
