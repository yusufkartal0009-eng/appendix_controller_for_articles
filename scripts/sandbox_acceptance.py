#!/usr/bin/env python3
"""Sandbox acceptance checks against a real Docker daemon.

Runs small probe scripts through the project's own DockerSandboxRunner (the same code path used for
paper runs) and prints the command evidence for each check:

  1. identity  - code runs as the unprivileged sandbox user (uid 1000)
  2. network   - outbound network access fails
  3. readonly  - the root filesystem and the mounted repository are read-only
  4. timeout   - a run exceeding the time limit ends as TIMEOUT with duration_seconds > 0
  5. offline   - wheels mounted at /workspace/packages install without network access
  6. no-docker - without a Docker CLI on PATH, execution is refused and nothing runs
Informational (not pass/fail): resource limits seen inside the container, and whether the
/workspace/home tmpfs allows executing files written there.

Usage: python scripts/sandbox_acceptance.py --wheel-dir DIR   (DIR holds a wheel for `six`)
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

from src.config import SANDBOX_RUNS_DIR  # noqa: E402
from src.sandbox.runner import DockerSandboxRunner, SandboxConfig, SandboxUnavailableError  # noqa: E402

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
    "probe_import.py": "import six\nprint(f'six {six.__version__} imported from {six.__file__}')\n",
    "probe_info.py": (
        "import os, subprocess\n"
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
    out_dir.chmod(0o777)  # the container user (uid 1000) writes execution_meta.json here
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
        lines.append("stderr (last 1500 chars):
" + result.stderr.strip()[-1500:])
    return lines


def main():
    parser = argparse.ArgumentParser(description="Sandbox acceptance checks (requires Docker)")
    parser.add_argument("--wheel-dir", required=True, help="Directory containing a wheel for `six`")
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
    wheels = sorted(Path(args.wheel_dir).glob("six-*.whl"))
    offline_repo = Path(tempfile.mkdtemp(prefix="acceptance_offline_"))
    (offline_repo / "probe_import.py").write_text(PROBES["probe_import.py"])
    (offline_repo / "requirements.txt").write_text("six\n")
    offline_repo.chmod(0o755)
    r, meta = run_probe(runner, offline_repo, "probe_import.py", "acceptance_offline", packages_dir=args.wheel_dir)
    show(f"5. Offline install from /workspace/packages ({', '.join(w.name for w in wheels)})",
         r.command_executed, "\n".join([r.stdout.strip()[-600:], *summary(r, meta)]))
    results["5 offline install"] = (
        r.status == "COMPLETED" and meta.get("dependency_install_status") == "INSTALLED" and "six " in r.stdout
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
