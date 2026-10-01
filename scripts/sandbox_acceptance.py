#!/usr/bin/env python3
"""Sandbox acceptance checks against a real Docker daemon.

Runs small probe scripts through the project's own DockerSandboxRunner (the same code path used for
paper runs) and prints the command evidence for each check:

  1. identity  - code runs as the unprivileged sandbox user (uid 1000)
  2. network   - outbound network access fails
  3. readonly  - the root filesystem and the mounted repository are read-only
  4. timeout   - a run exceeding the time limit ends as TIMEOUT with duration_seconds > 0
  5. offline   - a pure-Python wheel not in the image installs offline (install phase) and is
                 imported from the read-only /workspace/deps mount
  6. no-docker - without a Docker CLI on PATH, execution is refused and nothing runs
  7. compiled  - a wheel with a C extension installs offline and loads from /workspace/deps, which
                 the paper code cannot write to (control: the same .so fails to load from the
                 noexec /workspace/home)
  8. oom       - under a 256 MiB limit, a memory hog is killed and reported as OOM_KILLED (not TIMEOUT)
  9. pids      - the 100-PID limit stops thread creation
  10. numpy    - `pip show numpy` in the image satisfies the Dockerfile floor numpy>=1.24.0
  11. broken   - a requirement that does not exist makes the install phase fail and the run report
                 dependency_install_status FAILED
Informational (not pass/fail): resource limits seen inside the container, and whether the
/workspace/home tmpfs allows executing files written there.

Usage: python scripts/sandbox_acceptance.py --wheel-dir DIR
  DIR holds wheels for `toolz==0.12.1` (pure Python) and `ujson==5.10.0` (manylinux, CPython 3.11),
  neither of which is in the image.
Exit code 1 if any check fails.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import SANDBOX_RUNS_DIR
from src.sandbox.runner import (
    DockerSandboxRunner,
    SandboxConfig,
    SandboxUnavailableError,
)

PROBES = {
    "probe_identity.py": "import os\nprint(f'uid={os.getuid()} gid={os.getgid()}')\n",
    "probe_network.py": (
        "import socket, urllib.request\n"
        "results = []\n"
        "for label, attempt in [\n"
        "    ('tcp 1.1.1.1:53', lambda: socket.create_connection(('1.1.1.1', 53), timeout=3)),\n"
        "    ('dns example.com', lambda: socket.getaddrinfo('example.com', 443)),\n"
        "    ('https://example.com', lambda: urllib.request.urlopen('https://example.com', timeout=3)),\n"
        "]:\n"
        "    try:\n"
        "        attempt()\n"
        "        results.append(f'{label}: REACHABLE')\n"
        "    except OSError as exc:\n"
        "        results.append(f'{label}: BLOCKED ({type(exc).__name__}: {exc})')\n"
        "print('\\n'.join(results))\n"
        "raise SystemExit(1 if any('REACHABLE' in r for r in results) else 0)\n"
    ),
    "probe_readonly.py": (
        "import errno\n"
        "root = [l for l in open('/proc/self/mounts') if l.split()[1] == '/'][0].strip()\n"
        "print(f'root mount: {root}')\n"
        "ok = 'ro' in root.split()[3].split(',')\n"
        "for path in ['/probe_root.txt', '/usr/probe.txt', '/workspace/repo/probe.txt']:\n"
        "    try:\n"
        "        open(path, 'w').write('x')\n"
        "        print(f'{path}: WRITABLE'); ok = False\n"
        "    except OSError as exc:\n"
        "        print(f'{path}: {errno.errorcode.get(exc.errno, exc.errno)} ({exc.strerror})')\n"
        "raise SystemExit(0 if ok else 1)\n"
    ),
    "probe_sleep.py": "import time\nprint('sleeping 60s', flush=True)\ntime.sleep(60)\n",
    "probe_import.py": (
        "import toolz\n"
        "print(f'toolz {toolz.__version__} imported from {toolz.__file__}')\n"
        "raise SystemExit(0 if toolz.__file__.startswith('/workspace/deps/') else 1)\n"
    ),
    "probe_oom.py": (
        "chunks = []\n"
        "for i in range(64):\n"
        "    chunks.append(b'x' * (32 * 1024 * 1024))  # touches the pages, so they count\n"
        "    print(f'allocated {(i + 1) * 32} MiB', flush=True)\n"
        "print('NOT KILLED: allocated 2 GiB')\n"
    ),
    "probe_alloc.py": (
        "import toolz\n"
        "block = b'x' * (200 * 1024 * 1024)  # touches the pages, so they count\n"
        "print(f'holding {len(block) // (1024 * 1024)} MiB; toolz {toolz.__version__} imported')\n"
    ),
    "probe_pids.py": (
        "import threading, time\n"
        "threads = []\n"
        "try:\n"
        "    for i in range(300):\n"
        "        t = threading.Thread(target=time.sleep, args=(10,), daemon=True)\n"
        "        t.start()\n"
        "        threads.append(t)\n"
        "    print(f'NOT LIMITED: started {len(threads)} threads')\n"
        "    raise SystemExit(1)\n"
        "except RuntimeError as exc:\n"
        "    print(f'limited after {len(threads)} extra threads: RuntimeError: {exc}')\n"
    ),
    "probe_numpy.py": (
        "import subprocess, sys\n"
        "import numpy\n"
        "out = subprocess.run([sys.executable, '-m', 'pip', 'show', 'numpy'], capture_output=True, text=True).stdout\n"
        "print('\\n'.join(l for l in out.splitlines() if l.split(':')[0] in ('Name', 'Version', 'Location')))\n"
        "major, minor = (int(x) for x in numpy.__version__.split('.')[:2])\n"
        "ok = (major, minor) >= (1, 24)\n"
        "print(f'numpy {numpy.__version__} satisfies >=1.24.0: {ok}')\n"
        "raise SystemExit(0 if ok else 1)\n"
    ),
    "probe_compiled.py": (
        "import importlib.util, os, shutil\n"
        "import ujson\n"
        "print(f'ujson {ujson.__version__} imported from {ujson.__file__}')\n"
        "print('ujson.dumps ->', ujson.dumps({'a': [1, 2]}))\n"
        "ok = ujson.__file__.startswith('/workspace/deps/') and ujson.__file__.endswith('.so')\n"
        "try:\n"
        "    open('/workspace/deps/planted.so', 'w').write('x')\n"
        "    print('/workspace/deps: WRITABLE by paper code'); ok = False\n"
        "except OSError as exc:\n"
        "    print(f'/workspace/deps write attempt: {exc.strerror}')\n"
        "# Control: the same compiled module copied into the noexec home cannot be loaded.\n"
        "os.makedirs('/workspace/home/nx', exist_ok=True)\n"
        "copy = shutil.copy(ujson.__file__, '/workspace/home/nx/')\n"
        "try:\n"
        "    importlib.util.module_from_spec(importlib.util.spec_from_file_location('ujson', copy))\n"
        "    print('control: same .so loaded from /workspace/home (noexec NOT enforced)')\n"
        "except ImportError as exc:\n"
        "    print(f'control: same .so from /workspace/home fails to load: {exc}')\n"
        "raise SystemExit(0 if ok else 1)\n"
    ),
    "probe_info.py": (
        "import os, subprocess\n"
        "for line in open('/proc/self/mounts'):\n"
        "    if line.split()[1] in ('/tmp', '/workspace/home'):\n"
        "        print(f'mount: {line.split()[1]} {line.split()[3]}')\n"
        "for f in ['/sys/fs/cgroup/cpu.max', '/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/pids.max']:\n"
        "    try:\n"
        "        print(f'{f}: {open(f).read().strip()}')\n"
        "    except OSError as exc:\n"
        "        print(f'{f}: unreadable ({exc.strerror})')\n"
        "path = '/workspace/home/probe.sh'\n"
        "open(path, 'w').write('#!/bin/sh\\necho executed-from-home\\n'); os.chmod(path, 0o755)\n"
        "r = subprocess.run([path], capture_output=True, text=True)\n"
        "print(f'exec from /workspace/home: rc={r.returncode} out={r.stdout.strip()!r} err={r.stderr.strip()!r}')\n"
    ),
}


def show(title, cmd, output):
    print(f"\n### {title}\n```\n$ {' '.join(cmd)}\n{output.rstrip()}\n```")


def run_probe(runner, repo, name, paper_id, packages_dir=None):
    out_dir = SANDBOX_RUNS_DIR / paper_id
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    result = runner.run(paper_id=paper_id, repo_dir=repo, target_script=name, packages_dir=packages_dir)
    meta_path = out_dir / "execution_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return result, meta


def summary(result, meta):
    lines = [f"status={result.status} exit_code={result.exit_code} docker_used={result.docker_used} isolated={result.isolated}"]
    if result.error_message:
        lines.append(f"error_message={result.error_message}")
    if meta:
        lines.append(f"execution_meta.json: {json.dumps(meta)}")
    else:
        lines.append("execution_meta.json: <not written>")
    if result.status != "COMPLETED" and result.stderr.strip():
        lines.append("stderr (last 1500 chars):\n" + result.stderr.strip()[-1500:])
    return lines


def main():
    parser = argparse.ArgumentParser(description="Sandbox acceptance checks (requires Docker)")
    parser.add_argument("--wheel-dir", required=True, help="Directory with wheels for toolz==0.12.1 and ujson==5.10.0 (neither is in the image)")
    args = parser.parse_args()

    repo = Path(tempfile.mkdtemp(prefix="acceptance_repo_"))
    for name, body in PROBES.items():
        (repo / name).write_text(body)
    repo.chmod(0o755)
    runner = DockerSandboxRunner(SandboxConfig(timeout_seconds=120))
    results = {}

    # 1. identity
    r, meta = run_probe(runner, repo, "probe_identity.py", "acceptance_identity")
    show("1. Non-root user", r.command_executed, "\n".join([r.stdout.strip(), *summary(r, meta)]))
    results["1 identity (uid 1000)"] = r.status == "COMPLETED" and "uid=1000 gid=1000" in r.stdout

    # 2. network
    r, meta = run_probe(runner, repo, "probe_network.py", "acceptance_network")
    show("2. Network disabled", r.command_executed, "\n".join([r.stdout.strip(), *summary(r, meta)]))
    results["2 network blocked"] = r.status == "COMPLETED" and "REACHABLE" not in r.stdout

    # 3. read-only
    r, meta = run_probe(runner, repo, "probe_readonly.py", "acceptance_readonly")
    show("3. Read-only root filesystem", r.command_executed, "\n".join([r.stdout.strip(), *summary(r, meta)]))
    results["3 read-only root"] = r.status == "COMPLETED"

    # 4. timeout
    short = DockerSandboxRunner(SandboxConfig(timeout_seconds=5))
    r, meta = run_probe(short, repo, "probe_sleep.py", "acceptance_timeout")
    show("4. Timeout (limit 5 s, script sleeps 60 s)", r.command_executed, "\n".join([r.stdout.strip(), *summary(r, meta)]))
    results["4 timeout"] = r.status == "TIMEOUT" and meta.get("status") == "TIMEOUT" and meta.get("duration_seconds", 0) > 0

    # 5. offline install
    wheels = sorted(Path(args.wheel_dir).glob("toolz-*.whl"))
    offline_repo = Path(tempfile.mkdtemp(prefix="acceptance_offline_"))
    (offline_repo / "probe_import.py").write_text(PROBES["probe_import.py"])
    (offline_repo / "requirements.txt").write_text("toolz==0.12.1\n")
    offline_repo.chmod(0o755)
    r, meta = run_probe(runner, offline_repo, "probe_import.py", "acceptance_offline", packages_dir=args.wheel_dir)
    show(f"5. Offline install from /workspace/packages ({', '.join(w.name for w in wheels)})",
         r.command_executed, "\n".join([r.stdout.strip()[-600:], *summary(r, meta)]))
    results["5 offline install"] = (
        r.status == "COMPLETED" and meta.get("dependency_install_status") == "INSTALLED" and "imported from /workspace/deps/" in r.stdout
    )

    # 7. compiled wheel (C extension) installed offline and loaded from the read-only deps mount
    compiled_wheels = sorted(Path(args.wheel_dir).glob("ujson-*.whl"))
    compiled_repo = Path(tempfile.mkdtemp(prefix="acceptance_compiled_"))
    (compiled_repo / "probe_compiled.py").write_text(PROBES["probe_compiled.py"])
    (compiled_repo / "requirements.txt").write_text("ujson==5.10.0\n")
    compiled_repo.chmod(0o755)
    r, meta = run_probe(runner, compiled_repo, "probe_compiled.py", "acceptance_compiled", packages_dir=args.wheel_dir)
    show(f"7. Compiled wheel installed offline ({', '.join(w.name for w in compiled_wheels)})",
         r.command_executed, "\n".join([r.stdout.strip()[-900:], *summary(r, meta)]))
    results["7 compiled wheel offline"] = (
        r.status == "COMPLETED" and meta.get("dependency_install_status") == "INSTALLED"
        and "imported from /workspace/deps/" in r.stdout and ".so" in r.stdout
    )

    # 8. OOM: 256 MiB limit, the probe tries to hold 2 GiB
    small = DockerSandboxRunner(SandboxConfig(timeout_seconds=60, memory_limit="256m", memory_swap="256m"))
    r, meta = run_probe(small, repo, "probe_oom.py", "acceptance_oom")
    show("8. Memory limit (256 MiB, probe allocates up to 2 GiB)", r.command_executed,
         "\n".join([r.stdout.strip()[-400:], *summary(r, meta)]))
    results["8 OOM killed and reported as OOM_KILLED"] = (
        "NOT KILLED" not in r.stdout and r.status == "OOM_KILLED" and meta.get("status") == "OOM_KILLED"
    )

    # 9. pids limit (100): the probe tries to start 300 threads
    r, meta = run_probe(runner, repo, "probe_pids.py", "acceptance_pids")
    show("9. PID limit (100)", r.command_executed, "\n".join([r.stdout.strip()[-400:], *summary(r, meta)]))
    results["9 pids limit holds"] = r.status == "COMPLETED" and "limited after" in r.stdout

    # 10. numpy in the image respects the Dockerfile bound (numpy>=1.24.0)
    r, meta = run_probe(runner, repo, "probe_numpy.py", "acceptance_numpy")
    show("10. `pip show numpy` vs the Dockerfile bound", r.command_executed, "\n".join([r.stdout.strip(), *summary(r, meta)]))
    results["10 numpy bound respected"] = r.status == "COMPLETED" and "satisfies >=1.24.0: True" in r.stdout

    # 11. broken requirement: the install phase fails and the run reports FAILED
    broken_repo = Path(tempfile.mkdtemp(prefix="acceptance_broken_"))
    (broken_repo / "probe_identity.py").write_text(PROBES["probe_identity.py"])
    (broken_repo / "requirements.txt").write_text("reproradar-no-such-package==9.9.9\n")
    broken_repo.chmod(0o755)
    r, meta = run_probe(runner, broken_repo, "probe_identity.py", "acceptance_broken_req", packages_dir=args.wheel_dir)
    install_log = SANDBOX_RUNS_DIR / "acceptance_broken_req" / "install.log"
    install_tail = install_log.read_text()[-300:] if install_log.exists() else "<install.log not written>"
    show("11. Broken requirement (`reproradar-no-such-package==9.9.9`)", r.command_executed,
         "\n".join([f"install.log (tail): {install_tail.strip()}", r.stdout.strip()[-300:], *summary(r, meta)]))
    results["11 broken requirement reported FAILED"] = meta.get("dependency_install_status") == "FAILED"

    # 12. resource use recorded: peak memory of the run (probe holds 200 MiB) and duration and peak of the install phase
    alloc_repo = Path(tempfile.mkdtemp(prefix="acceptance_alloc_"))
    (alloc_repo / "probe_alloc.py").write_text(PROBES["probe_alloc.py"])
    (alloc_repo / "requirements.txt").write_text("toolz==0.12.1\n")
    alloc_repo.chmod(0o755)
    r, meta = run_probe(runner, alloc_repo, "probe_alloc.py", "acceptance_resources", packages_dir=args.wheel_dir)
    install_meta_path = SANDBOX_RUNS_DIR / "acceptance_resources" / "install_meta.json"
    install_meta = json.loads(install_meta_path.read_text()) if install_meta_path.exists() else {}
    peak = meta.get("peak_memory_bytes")
    show("12. Resource use recorded (run holds 200 MiB after an offline install)", r.command_executed,
         "\n".join([r.stdout.strip()[-300:], f"install_meta.json: {json.dumps(install_meta)}",
                    f"run peak_memory_bytes: {peak}", *summary(r, meta)]))
    results["12 peak memory and install duration recorded"] = (
        r.status == "COMPLETED" and isinstance(peak, int) and peak >= 200 * 1024 * 1024
        and isinstance(install_meta.get("peak_memory_bytes"), int) and install_meta.get("duration_seconds", 0) > 0
    )

    # 6. no Docker: remove the Docker CLI from PATH for this check only
    marker = repo / "RAN.marker"
    (repo / "probe_marker.py").write_text(f"open({str(marker)!r}, 'w').write('ran')\n")
    saved_path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.path.dirname(sys.executable)
    try:
        docker_on_path = shutil.which("docker")
        DockerSandboxRunner().run(paper_id="acceptance_nodocker", repo_dir=repo, target_script="probe_marker.py")
        outcome, refused = "ran (NOT refused)", False
    except SandboxUnavailableError as exc:
        outcome, refused = f"SandboxUnavailableError: {exc}", True
    finally:
        os.environ["PATH"] = saved_path
    show("6. Docker unavailable (Docker CLI removed from PATH)", ["DockerSandboxRunner().run(...)"],
         f"shutil.which('docker') -> {docker_on_path}\n{outcome}\nscript marker file exists: {marker.exists()}")
    results["6 refused without Docker"] = refused and not marker.exists()

    # Informational
    r, meta = run_probe(runner, repo, "probe_info.py", "acceptance_info")
    show("Info: resource limits and /workspace/home exec", r.command_executed, "\n".join([r.stdout.strip(), *summary(r, meta)]))

    print("\n### Summary")
    for name, ok in results.items():
        print(f"- {'PASS' if ok else 'FAIL'}: {name}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
