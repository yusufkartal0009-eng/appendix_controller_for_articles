# Repro Radar — Sandbox Acceptance Evidence

> Real commands and output showing what the Docker sandbox enforces. Every section below is copied
> verbatim from a CI run; nothing is paraphrased. A check without output here is not claimed.

## Provenance

| | |
|---|---|
| Script | `scripts/sandbox_acceptance.py` (runs probe scripts through `DockerSandboxRunner`, the same code path as paper runs) |
| Where | GitHub Actions `ubuntu-latest`, job `Sandbox acceptance (real Docker)`, host user uid 1001 |
| Run | CI run `36314893982` on commit `d71fb62` (PR #87), 2026-09-27 |
| Image | `repro-radar-sandbox:latest` built from `docker/Dockerfile.sandbox` in the same job |
| Re-run | `python scripts/sandbox_acceptance.py --wheel-dir <dir with toolz-0.12.1 wheel>` on a host with Docker |

The job runs on every push and pull request and fails if any of the six checks fails.

## Results

| # | Check | Result | Evidence (below) |
|---|---|---|---|
| 1 | Container runs as a non-root user | **PASS** | `uid=1000 gid=1000` |
| 2 | Network is disabled | **PASS** | TCP, DNS, and HTTPS all fail (`Network is unreachable`, name resolution failure) |
| 3 | Root filesystem is read-only | **PASS** | root mount `ro`; writes to `/`, `/usr`, `/workspace/repo` fail with `EROFS` |
| 4 | Timeout produces `TIMEOUT` with `duration_seconds > 0` | **PASS** | limit 5 s: `TIMEOUT`, exit 137, `duration_seconds: 5.108` in `execution_meta.json` |
| 5 | Offline install from `/workspace/packages` | **PASS** | `toolz 0.12.1` (not in the image) installed with no network and imported from `/workspace/home/.local` |
| 6 | Without Docker, execution is refused | **PASS** | `SandboxUnavailableError`, the probe's marker file was not created |

Informational (not a pass/fail check): CPU, memory, and PID limits are applied inside the container
(`cpu.max 200000 100000` = 2 CPUs, `memory.max 8589934592` = 8 GiB, `pids.max 100`).
`/workspace/home` is mounted `noexec` by Docker's tmpfs defaults, so files written there cannot be executed (see *Findings*).

Check 6 was also run on a Windows 11 machine with no Docker installed (`docker: command not found`),
using the staging CLI: exit code 4, `ERROR: Docker is not available, so the code cannot be isolated;
refusing to run it on the host...`, and the target script did not run (see PR #81).

## Findings from building this evidence

The acceptance runs found real defects before any check could pass. They are listed so that the passing
results above are not mistaken for "nothing was wrong":

| Finding | Status |
|---|---|
| Runner overwrote logs the container had written as uid 1000; on hosts with another uid every Docker run was reported `FAILED` and its output was dropped | Fixed in #89 (issue #88) |
| `/workspace/home` tmpfs was root-owned, so uid 1000 could not write to it and offline installs always failed | Fixed in #91 (issue #90) |
| The first version of check 5 used `six`, which is already in the image; its "pass" proved nothing | Replaced by `toolz`, which is not in the image, and the import path is asserted |
| `/workspace/home` is `noexec` despite PR #64 removing the flag (Docker adds it by default); offline-installed wheels with compiled extensions are expected not to load | Open: issue #92 (not verified with a compiled wheel) |

## Verbatim output

### 1. Non-root user
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_bs66vpwa:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_identity:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_identity.py
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
Duration      : 0.12s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.12, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "user_id": 1000, "group_id": 1000}
```

### 2. Network disabled
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_bs66vpwa:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_network:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_network.py
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
Duration      : 0.309s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.309, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "user_id": 1000, "group_id": 1000}
```

### 3. Read-only root filesystem
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_bs66vpwa:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_readonly:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_readonly.py
==================================================
Repro Radar: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_readonly.py
==================================================
root mount: overlay / overlay ro,relatime,lowerdir=/var/lib/docker/overlay2/l/SKZBMPSCS3RWHVNN4K2FS5Z64X:/var/lib/docker/overlay2/l/4G2LJ56I43HYPYYXQCUA3JQQBD:/var/lib/docker/overlay2/l/QDHCQIEAR6VISXXXH2RZIPM6UR:/var/lib/docker/overlay2/l/N7E7I5UNLBF4VQ3ER7SN7TMXHX:/var/lib/docker/overlay2/l/TTXHFSX44I2V2DPBDKDRJA6PW6:/var/lib/docker/overlay2/l/B63SXDDERHBFCTLPYBITS6EYUT:/var/lib/docker/overlay2/l/352ZUMT7W6LLZ77UZREZWQQK3Y:/var/lib/docker/overlay2/l/7SJYDVBH5QCZYXKVJU4THX76SU:/var/lib/docker/overlay2/l/BYOHIOAYZYQZ3OR3AFGCIZ5ELH:/var/lib/docker/overlay2/l/3B2JTQFMQQECEMFZQQR32VSXAC:/var/lib/docker/overlay2/l/OHRJDQF5WPQZPERT6G6SS4ETR3:/var/lib/docker/overlay2/l/VDOMVHOPZPQ4WFVJFKL2TJAM2H,upperdir=/var/lib/docker/overlay2/826d111e8e8662edd196f04d709df61156624414c0f6a9f3001d11d2d6d257ec/diff,workdir=/var/lib/docker/overlay2/826d111e8e8662edd196f04d709df61156624414c0f6a9f3001d11d2d6d257ec/work,nouserxattr 0 0
/probe_root.txt: EROFS (Read-only file system)
/usr/probe.txt: EROFS (Read-only file system)
/workspace/repo/probe.txt: EROFS (Read-only file system)
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : SKIPPED
Duration      : 0.119s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.119, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "user_id": 1000, "group_id": 1000}
```

### 4. Timeout (limit 5 s, script sleeps 60 s)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=5 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_bs66vpwa:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_timeout:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_sleep.py
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
execution_meta.json: {"status": "TIMEOUT", "exit_code": 137, "duration_seconds": 5.108, "timeout_limit_seconds": 5, "dependency_install_status": "SKIPPED", "user_id": 1000, "group_id": 1000}
stderr (last 1500 chars):
/entrypoint.sh: line 54:    13 Killed                  timeout --signal=SIGKILL "${TIMEOUT_SECONDS}" "$@" > >(tee "${STDOUT_LOG}") 2> >(tee "${STDERR_LOG}" 1>&2)
```

### 5. Offline install from /workspace/packages (toolz-0.12.1-py3-none-any.whl)
```
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_offline_6lswyqpm:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_offline:/workspace/output:rw -v /home/runner/work/_temp/wheels:/workspace/packages:ro repro-radar-sandbox:latest python /workspace/repo/probe_import.py
: Isolated Sandbox Runtime Initiated
Working Dir   : /workspace/repo
Timeout Limit : 120s
Security Mode : Unprivileged (UID: 1000)
Network State : Isolated (--network none)
Command       : python /workspace/repo/probe_import.py
==================================================
toolz 0.12.1 imported from /workspace/home/.local/lib/python3.11/site-packages/toolz/__init__.py
==================================================
Repro Radar: Execution Concluded
Status        : COMPLETED (Exit Code: 0)
Dependencies  : INSTALLED
Duration      : 0.217s
==================================================
status=COMPLETED exit_code=0 docker_used=True isolated=True
execution_meta.json: {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 0.217, "timeout_limit_seconds": 120, "dependency_install_status": "INSTALLED", "user_id": 1000, "group_id": 1000}
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
$ docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --tmpfs /workspace/home:rw,nosuid,size=2048m,uid=1000,gid=1000 --security-opt no-new-privileges:true --user 1000:1000 --cpus=2.0 --memory=8g --memory-swap=8g --pids-limit=100 -w /workspace/repo -e SANDBOX_TIMEOUT=120 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUSERBASE=/workspace/home/.local -e PYTHONPATH=/workspace/repo:/workspace/home/.local/lib/python3.11/site-packages -v /tmp/acceptance_repo_bs66vpwa:/workspace/repo:ro -v /home/runner/work/appendix_controller_for_articles/appendix_controller_for_articles/sandbox_runs/acceptance_info:/workspace/output:rw repro-radar-sandbox:latest python /workspace/repo/probe_info.py
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
Duration      : 0.192s
==================================================
status=FAILED exit_code=1 docker_used=True isolated=True
execution_meta.json: {"status": "FAILED", "exit_code": 1, "duration_seconds": 0.192, "timeout_limit_seconds": 120, "dependency_install_status": "SKIPPED", "user_id": 1000, "group_id": 1000}
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
- PASS: 6 refused without Docker
