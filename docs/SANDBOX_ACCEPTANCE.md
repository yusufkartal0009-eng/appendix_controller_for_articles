# Repro Radar — Sandbox Acceptance Evidence

> Real commands and output showing what the Docker sandbox enforces. Every section below is copied
> verbatim from a CI run; nothing is paraphrased. A check without output here is not claimed.

## Provenance

| | |
|---|---|
| Script | `scripts/sandbox_acceptance.py` (runs probe scripts through `DockerSandboxRunner`, the same code path as paper runs) |
| Where | GitHub Actions `ubuntu-latest`, job `Sandbox acceptance (real Docker)`, host user uid 1001 |
| Run | CI run `37215662071` on commit `6571c2f` (PR for #161), 2026-10-04; verbatim output below is the Python 3.11 image (`repro-radar-sandbox:latest`) |
| Other images | The same 14 checks passed in the same run for `repro-radar-sandbox:py3.9` and `repro-radar-sandbox:py3.8` (job logs `Sandbox acceptance (real Docker, Python 3.9)` / `(…, Python 3.8)`; #158, #159, #161) |
| Image | `repro-radar-sandbox:latest` built from `docker/Dockerfile.sandbox` in the same job |
| Re-run | `python scripts/sandbox_acceptance.py --wheel-dir <dir>` on a host with Docker; `<dir>` holds `toolz==0.12.1` and `ujson==5.10.0` wheels (manylinux, CPython 3.11) |

The job runs on every push and pull request and fails if any check fails.


## Results

| # | Check | Result | Evidence (below) |
|---|---|---|---|
| 1 | Container runs as a non-root user | **PASS** | `uid=1000 gid=1000` |
| 2 | Network is disabled | **PASS** | TCP, DNS, and HTTPS all fail (`Network is unreachable`, name resolution failure) |
| 3 | Root filesystem is read-only | **PASS** | root mount `ro`; writes to `/`, `/usr`, `/workspace/repo` fail with `EROFS` |
| 4 | Timeout produces `TIMEOUT` with `duration_seconds > 0` | **PASS** | limit 5 s: `TIMEOUT`, exit 137, `duration_seconds: 5.108` |
| 5 | Offline install of a pure-Python wheel | **PASS** | `toolz` (not in the image) imported from `/workspace/deps/toolz/__init__.py` |
| 6 | Without Docker, execution is refused | **PASS** | `SandboxUnavailableError`; the probe's marker file was not created |
| 7 | Offline install of a compiled wheel | **PASS** | `ujson` C extension loaded from `/workspace/deps/ujson.cpython-311-x86_64-linux-gnu.so`; writing to `/workspace/deps`: `Read-only file system` |
| 8 | Memory limit: OOM kill reported as `OOM_KILLED` | **PASS** | 256 MiB limit: `OOM_KILLED`, exit 137, after `0.17` s (timeout limit 60 s); recorded peak `268435456` bytes = the limit |
| 9 | PID limit holds | **PASS** | `limited after 95 extra threads: RuntimeError: can't start new thread` (`pids.max 100`) |
| 10 | `pip show numpy` vs the Dockerfile bound `numpy>=1.24.0` | **PASS** | numpy `2.4.6`. The Dockerfile sets only a floor, so the exact version is not pinned (GA-6) |
| 11 | Broken requirement → `dependency_install_status: FAILED` | **PASS** | install log: `ERROR: Could not find a version that satisfies the requirement reproradar-no-such-package==9.9.9 (from versions: none)`; run status `COMPLETED`, `dependency_install_status: FAILED` |
| 12 | Peak memory and install duration are recorded | **PASS** | probe holding 200 MiB: `peak_memory_bytes: 221732864` (≥ 200 MiB) in `execution_meta.json`; install phase: `duration_seconds: 0.537`, `peak_memory_bytes: 40382464` in `install_meta.json` |
| 13 | Conda-only repository installed offline (#159) | **PASS** | `environment.yml` without a requirements file: bundle `status=SUCCESS converted=2 downloaded=['toolz==0.12.1', 'ujson==5.10.0'] conda_only=[]`, skipped `_libgcc_mutex`, `libgcc-ng`; run `COMPLETED`, `dependency_install_status: INSTALLED`, both imported from `/workspace/deps/` |
| 14 | Installed package versions recorded (#161) | **PASS** | the install phase of check 5 wrote `installed_packages.json`: `[{"name": "toolz", "version": "0.12.1"}]` |

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
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_xfobv32h:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_identity:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_identity.py
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
Duration      : 0.121s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.121, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 6836224, "user_id": 1000, "group_id": 1000}
```

### 2. Network disabled
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_xfobv32h:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_network:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_network.py
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
Duration      : 0.25s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.25, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 16220160, "user_id": 1000, "group_id": 1000}
```

### 3. Read-only root filesystem
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_xfobv32h:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_readonly:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_readonly.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_readonly.py
==================================================
root mount: overlay / overlay ro,relatime,lowerdir=/var/lib/docker/overlay2/l/WZMAEMZPPCSUXCZ6QPF7GEBHZH:/var/lib/docker/overlay2/l/ONMDEXPYF4D4RVOLKJQP5MFA5S:/var/lib/docker/overlay2/l/BIVNZSM2L62F34TZ2EXUG5M7F7:/var/lib/docker/overlay2/l/KRNI523DL6VKS4EWJILL5IXFWN:/var/lib/docker/overlay2/l/OTAAG7K4HAJ4FH5IPT4YQED3DX:/var/lib/docker/overlay2/l/LUUOQINKWQPENJWOBR4XFS5E4Z:/var/lib/docker/overlay2/l/I5QIK25KKDI5X27IBHBD2BAECK:/var/lib/docker/overlay2/l/VMMDC22HX5HDQKR33LPMTDPTZW:/var/lib/docker/overlay2/l/MEILAKVX5SFXXNYWHSVAZDXA6D:/var/lib/docker/overlay2/l/BZID4JS4OJU3T4AOEZG4DRWTSS:/var/lib/docker/overlay2/l/II3S3YVZXSFUYKQ3SF576IHB4J:/var/lib/docker/overlay2/l/LLTEJICROT7X64LYDJYRNLY464,upperdir=/var/lib/docker/overlay2/8155e7d5610f68044523118672da235cd554c670dbc2ad592655a27582a8cc4c/diff,workdir=/var/lib/docker/overlay2/8155e7d5610f68044523118672da235cd554c670dbc2ad592655a27582a8cc4c/work,nouserxattr 0 0
/probe_root.txt: EROFS (Read-only file system)
/usr/probe.txt: EROFS (Read-only file system)
/workspace/repo/probe.txt: EROFS (Read-only file system)
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 0.118s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.118, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 6975488, "user_id": 1000, "group_id": 1000}
```

### 4. Timeout (limit 5 s, script sleeps 60 s)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=5 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_xfobv32h:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_timeout:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_sleep.py
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
Duration      : 5.108s
==================================================
status=TIMEOUT exit_code=137 docker_used=True isolated=True
execution_meta.json: {"status": "TIMEOUT", "exit_code": 137, "duration_seconds": 5.108, "timeout_limit_seconds": 5, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 6701056, "user_id": 1000, "group_id": 1000}
stderr (last 1500 chars):
/entrypoint.sh: line 114:    13 Killed                  timeout --signal=SIGKILL "${TIMEOUT_SECONDS}" "$@" > >(tee "${STDOUT_LOG}") 2> >(tee "${STDERR_LOG}" 1>&2)
```

### 5. Offline install from /workspace/packages (toolz-0.12.1-py3-none-any.whl)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=INSTALLED -v /tmp/acceptance_offline_c2oycvka:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_offline:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_offline/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_import.py
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
Duration      : 0.181s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.181, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "peak_memory_bytes": 13012992, "user_id": 1000, "group_id": 1000}
```

### 7. Compiled wheel installed offline (ujson-5.10.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=INSTALLED -v /tmp/acceptance_compiled_9c11hogv:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_compiled:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_compiled/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_compiled.py
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
Duration      : 0.168s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.168, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "peak_memory_bytes": 10760192, "user_id": 1000, "group_id": 1000}
```

### 8. Memory limit (256 MiB, probe allocates up to 2 GiB)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=256m --memory-swap=256m --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=60 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_xfobv32h:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_oom:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_oom.py
y
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
Duration      : 0.17s
==================================================
status=OOM_KILLED exit_code=137 docker_used=True isolated=True
execution_meta.json: {"status": "OOM_KILLED", "exit_code": 137, "duration_seconds": 0.17, "timeout_limit_seconds": 60, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 268435456, "user_id": 1000, "group_id": 1000}
stderr (last 1500 chars):
/entrypoint.sh: line 114:    13 Killed                  timeout --signal=SIGKILL "${TIMEOUT_SECONDS}" "$@" > >(tee "${STDOUT_LOG}") 2> >(tee "${STDERR_LOG}" 1>&2)
```

### 9. PID limit (100)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_xfobv32h:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_pids:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_pids.py
one)
Command       : python /workspace/repo/probe_pids.py
==================================================
limited after 95 extra threads: RuntimeError: can't start new thread
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 0.139s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.139, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 12816384, "user_id": 1000, "group_id": 1000}
```

### 10. `pip show numpy` vs the Dockerfile bound
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_xfobv32h:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_numpy:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_numpy.py
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
Duration      : 0.579s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.579, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 44273664, "user_id": 1000, "group_id": 1000}
```

### 11. Broken requirement (`reproradar-no-such-package==9.9.9`)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=FAILED -v /tmp/acceptance_broken_d09_k03b:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_broken_req:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_broken_req/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_identity.py
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
Duration      : 0.121s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.121, "timeout_limit_seconds": 120, "dependency_install_status": "FAILED", "peak_memory_bytes": 9129984, "user_id": 1000, "group_id": 1000}
```

### 12. Resource use recorded (run holds 200 MiB after an offline install)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=INSTALLED -v /tmp/acceptance_alloc_aztwag2f:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_resources:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_resources/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_alloc.py
====================================
holding 200 MiB; toolz 0.12.1 imported
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : INSTALLED
Duration      : 0.211s
==================================================
install_meta.json: {"phase": "install", "status": "INSTALLED", "exit_code": 0, "duration_seconds": 0.537, "peak_memory_bytes": 40382464}
run peak_memory_bytes: 221732864
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.211, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "peak_memory_bytes": 221732864, "user_id": 1000, "group_id": 1000}
```

### 13. Conda-only repository (environment.yml, no requirements file)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=INSTALLED -v /tmp/acceptance_conda_staging_up65y429/acceptance_conda:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_conda:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_conda/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_conda.py
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
Duration      : 0.182s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.182, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "peak_memory_bytes": 12988416, "user_id": 1000, "group_id": 1000}
```

### 14. Installed package versions recorded by the install phase
```
$ (reads installed_packages.json of check 5)
installed_packages.json: [{"name": "toolz", "version": "0.12.1"}]
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
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_xfobv32h:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_info:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_info.py
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
Duration      : 0.169s
==================================================
status=FAILED exit_code=1 docker_used=True isolated=True
execution_meta.json: {"status": "FAILED", "exit_code": 1, "duration_seconds": 0.169, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "peak_memory_bytes": 10424320, "user_id": 1000, "group_id": 1000}
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
- PASS: 6 refused without Docker
