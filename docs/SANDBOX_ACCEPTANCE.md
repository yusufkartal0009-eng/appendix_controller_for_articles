# Repro Radar — Sandbox Acceptance Evidence

> Real commands and output showing what the Docker sandbox enforces. Every section below is copied
> verbatim from a CI run; nothing is paraphrased. A check without output here is not claimed.

## Provenance

| | |
|---|---|
| Script | `scripts/sandbox_acceptance.py` (runs probe scripts through `DockerSandboxRunner`, the same code path as paper runs) |
| Where | GitHub Actions `ubuntu-latest`, job `Sandbox acceptance (real Docker)`, host user uid 1001 |
| Run | CI run `36316295634` on commit `96c70c7` (PR #95), 2026-09-27 |
| Image | `repro-radar-sandbox:latest` built from `docker/Dockerfile.sandbox` in the same job |
| Re-run | `python scripts/sandbox_acceptance.py --wheel-dir <dir>` on a host with Docker; `<dir>` holds `toolz==0.12.1` and `ujson==5.10.0` wheels (manylinux, CPython 3.11) |

The job runs on every push and pull request and fails if any check fails.

## Results

| # | Check | Result | Evidence (below) |
|---|---|---|---|
| 1 | Container runs as a non-root user | **PASS** | `uid=1000 gid=1000` |
| 2 | Network is disabled | **PASS** | TCP, DNS, and HTTPS all fail (`Network is unreachable`, name resolution failure) |
| 3 | Root filesystem is read-only | **PASS** | root mount `ro`; writes to `/`, `/usr`, `/workspace/repo` fail with `EROFS` |
| 4 | Timeout produces `TIMEOUT` with `duration_seconds > 0` | **PASS** | limit 5 s: `TIMEOUT`, exit 137, `duration_seconds: 5.109` |
| 5 | Offline install of a pure-Python wheel | **PASS** | `toolz` (not in the image) installed by the install phase, imported from `/workspace/deps/toolz/__init__.py` |
| 6 | Without Docker, execution is refused | **PASS** | `SandboxUnavailableError`; the probe's marker file was not created |
| 7 | Offline install of a compiled wheel | **PASS** | `ujson` C extension (not in the image) loaded from `/workspace/deps/ujson.cpython-311-x86_64-linux-gnu.so`; paper code writing to `/workspace/deps`: `Read-only file system` |

Informational (not a pass/fail check): CPU, memory, and PID limits are applied inside the container
(`cpu.max 200000 100000` = 2 CPUs, `memory.max 8589934592` = 8 GiB, `pids.max 100`).
`/workspace/home` and `/tmp` are `noexec` on purpose: files written there cannot be executed or loaded.
Check 7's control shows this for a compiled module: `same .so from /workspace/home fails to load: /workspace/home/nx/ujson.cpython-311-x86_64-linux-gnu.so: failed to map segment from shared object`.

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

## Verbatim output

### 1. Non-root user
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_0xk3flep:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_identity:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_identity.py
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
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.124, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "user_id": 1000, "group_id": 1000}
```

### 2. Network disabled
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_0xk3flep:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_network:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_network.py
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
Duration      : 0.332s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.332, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "user_id": 1000, "group_id": 1000}
```

### 3. Read-only root filesystem
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_0xk3flep:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_readonly:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_readonly.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_readonly.py
==================================================
root mount: overlay / overlay ro,relatime,lowerdir=/var/lib/docker/overlay2/l/OZPYNBWBSJHAEEQH75SDEPMYKB:/var/lib/docker/overlay2/l/GAAF4GSJTLRRAZK3HUNEH2MHJK:/var/lib/docker/overlay2/l/SUCLJU6FFZYMP57F65QQL44EVN:/var/lib/docker/overlay2/l/W6XFNE57VTBLVNOFPWNIB2V55C:/var/lib/docker/overlay2/l/CHYUNRILGEHZL6W6JA7IXXL2MB:/var/lib/docker/overlay2/l/4GPVFTNDOJODADQRRMCJX7O6WL:/var/lib/docker/overlay2/l/KE4QAUEZU2LYYJAB6OWK3CPUD3:/var/lib/docker/overlay2/l/4WJZSFXQC7IBX2MGIX2GT5HODE:/var/lib/docker/overlay2/l/W4GBIGKFM5LDI3DIV6S7MUJCDF:/var/lib/docker/overlay2/l/JULLQDIW3X42VU5LBD5H7FJWOM:/var/lib/docker/overlay2/l/XUAC7KTVDT37I2NQMNKE266SM6:/var/lib/docker/overlay2/l/ZHYRI53UHNIUNJSJKG3JKOMOR4,upperdir=/var/lib/docker/overlay2/aca211442bed45baf4bac34eab608c77bb6abcfbe559a32110027bc1f0e95fc8/diff,workdir=/var/lib/docker/overlay2/aca211442bed45baf4bac34eab608c77bb6abcfbe559a32110027bc1f0e95fc8/work,nouserxattr 0 0
/probe_root.txt: EROFS (Read-only file system)
/usr/probe.txt: EROFS (Read-only file system)
/workspace/repo/probe.txt: EROFS (Read-only file system)
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 0.123s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.123, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "user_id": 1000, "group_id": 1000}
```

### 4. Timeout (limit 5 s, script sleeps 60 s)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=5 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_0xk3flep:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_timeout:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_sleep.py
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
Duration      : 5.109s
==================================================
status=TIMEOUT exit_code=137 docker_used=True isolated=True
execution_meta.json: {"status": "TIMEOUT", "exit_code": 137, "duration_seconds": 5.109, "timeout_limit_seconds": 5, "dependency_install_status": "SKIPPED", "user_id": 1000, "group_id": 1000}
stderr (last 1500 chars):
/entrypoint.sh: line 72:    11 Killed                  timeout --signal=SIGKILL "${TIMEOUT_SECONDS}" "$@" > >(tee "${STDOUT_LOG}") 2> >(tee "${STDERR_LOG}" 1>&2)
```

### 5. Offline install from /workspace/packages (toolz-0.12.1-py3-none-any.whl)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=INSTALLED -v /tmp/acceptance_offline_a57jpax1:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_offline:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_offline/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_import.py
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
Duration      : 0.222s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.222, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "user_id": 1000, "group_id": 1000}
```

### 7. Compiled wheel installed offline (ujson-5.10.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -e SANDBOX_DEPENDENCY_STATUS=INSTALLED -v /tmp/acceptance_compiled_n2wbhvyw:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_compiled:/workspace/output:rw -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_compiled/deps:/workspace/deps:ro repro-radar-sandbox:latest python /workspace/repo/probe_compiled.py
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
Duration      : 0.195s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.195, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "user_id": 1000, "group_id": 1000}
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
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/deps:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_0xk3flep:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_info:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_info.py
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
execution_meta.json: {"status": "FAILED", "exit_code": 1, "duration_seconds": 0.199, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "user_id": 1000, "group_id": 1000}
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
- PASS: 6 refused without Docker
