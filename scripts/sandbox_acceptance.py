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
  12-14         resource use recorded, conda-only repository, installed versions (see the code)
  15. run setup - a paper's run setup (#166): the run starts in a repository subfolder, writes to a
                 writable per-run copy of the repository (the staged repository is unchanged), and reads
                 a read-only data mount from the host cache
  16. image    - the size of the sandbox image is measured (`docker image inspect`) (#163)
  17. cpu      - under --cpus=0.5, two busy worker processes together get at most 0.6 CPUs; control: the
                 same probe with the limit set to the host's CPU count gets more than 1.5 CPUs (#163)
  18. build    - the build phase (#193) turns a pure-Python sdist and a C extension (built from a writable copy
                 of the repository) into wheels with the network off; the run phase installs them offline and
                 imports both, and the run image has no compiler
  19. data copy - a writable data mount is a per-run copy: the run writes into it, the host cache is unchanged
  20. gpu off  - the GPU is opt-in (#169): a default run has no --gpus flag and records gpu_requested false and
                 no GPU devices (a run with the GPU needs an NVIDIA host: scripts/gpu_check.py)
  21. watchdog - a paper that kills the `timeout` watchdog is reported as FAILED (killed_before_timeout), not
                 as TIMEOUT, because the time limit was not reached (#262)
Informational (not pass/fail): resource limits seen inside the container, and whether the
/workspace/home tmpfs allows executing files written there.

Usage: python scripts/sandbox_acceptance.py --wheel-dir DIR
  DIR holds wheels for `toolz==0.12.1` (pure Python) and `ujson==5.10.0` (manylinux, CPython 3.11),
  neither of which is in the image.
Exit code 1 if any check fails.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import SANDBOX_RUNS_DIR
from src.sandbox.runner import (
    DEFAULT_PYTHON_VERSION,
    DockerSandboxRunner,
    SandboxConfig,
    SandboxUnavailableError,
    build_image_for,
    image_for,
)
from src.sandbox.stager import RepoStager

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
    "probe_kill_watchdog.py": (
        "import os, signal, time\n"
        "os.kill(os.getppid(), signal.SIGKILL)\n"
        "print('killed the watchdog', flush=True)\n"
        "time.sleep(60)\n"),
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
    "probe_conda.py": (
        "import toolz, ujson\n"
        "for m in (toolz, ujson):\n"
        "    print(f'{m.__name__} imported from {m.__file__}')\n"
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
    # Two worker processes busy-loop for 3 s of wall time; the CPU time they get, divided by the wall time,
    # is the number of CPUs the container really had (#163).
    "probe_cpu.py": (
        "import multiprocessing as mp, os, time\n"
        "def burn(seconds):\n"
        "    end = time.time() + seconds\n"
        "    while time.time() < end:\n"
        "        pass\n"
        "if __name__ == '__main__':\n"
        "    try:\n"
        "        print('cpu.max: ' + open('/sys/fs/cgroup/cpu.max').read().strip())\n"
        "    except OSError as exc:\n"
        "        print(f'cpu.max: unreadable ({exc.strerror})')\n"
        "    t0, c0 = time.time(), os.times()\n"
        "    workers = [mp.Process(target=burn, args=(3,)) for _ in range(2)]\n"
        "    for w in workers:\n"
        "        w.start()\n"
        "    for w in workers:\n"
        "        w.join()\n"
        "    wall, c1 = time.time() - t0, os.times()\n"
        "    cpu = (c1.children_user - c0.children_user) + (c1.children_system - c0.children_system)\n"
        "    print(f'workers=2 wall={wall:.2f}s cpu={cpu:.2f}s effective_cpus={cpu / wall:.2f}')\n"
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
    parser.add_argument("--python-version", default=DEFAULT_PYTHON_VERSION,
                        help="Python version of the sandbox image to check (#158); the image must be built first")
    args = parser.parse_args()
    print(f"Sandbox image: {image_for(args.python_version)} (Python {args.python_version})")

    repo = Path(tempfile.mkdtemp(prefix="acceptance_repo_"))
    for name, body in PROBES.items():
        (repo / name).write_text(body)
    repo.chmod(0o755)
    runner = DockerSandboxRunner(SandboxConfig(timeout_seconds=120, python_version=args.python_version))
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
    short = DockerSandboxRunner(SandboxConfig(timeout_seconds=5, python_version=args.python_version))
    r, meta = run_probe(short, repo, "probe_sleep.py", "acceptance_timeout")
    show("4. Timeout (limit 5 s, script sleeps 60 s)", r.command_executed, "\n".join([r.stdout.strip(), *summary(r, meta)]))
    results["4 timeout"] = r.status == "TIMEOUT" and meta.get("status") == "TIMEOUT" and meta.get("duration_seconds", 0) > 0

    # 21. a paper that kills its own watchdog (#262) is not labelled TIMEOUT: the limit was not reached
    r, meta = run_probe(short, repo, "probe_kill_watchdog.py", "acceptance_kill_watchdog")
    show("21. Paper kills the `timeout` watchdog (limit 5 s)", r.command_executed,
         "\n".join([r.stdout.strip(), *summary(r, meta), f"killed_before_timeout={meta.get('killed_before_timeout')}"]))
    results["21 killed watchdog is not a timeout"] = (
        r.status == "FAILED" and meta.get("status") == "FAILED" and meta.get("killed_before_timeout") is True
        and meta.get("duration_seconds", 99) < 4
    )

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
    small = DockerSandboxRunner(SandboxConfig(timeout_seconds=60, memory_limit="256m", memory_swap="256m",
                                              python_version=args.python_version))
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

    # 13. conda-only repository (#159): environment.yml converted to pinned wheels, bundled on the host with
    # pip download --no-deps (binary only), installed offline in the install phase, imported in the run phase.
    # `requests` is pinned without its dependencies (urllib3, idna, ...): a conda environment is a lock, so it must
    # be installed as pinned, without dependency resolution (#229).
    conda_repo = Path(tempfile.mkdtemp(prefix="acceptance_conda_"))
    (conda_repo / "probe_conda.py").write_text(PROBES["probe_conda.py"])
    (conda_repo / "environment.yml").write_text(
        "name: acceptance\ndependencies:\n"
        f"  - python={args.python_version}\n  - _libgcc_mutex=0.1=conda_forge\n  - libgcc-ng=13.2.0\n"
        "  - toolz=0.12.1=pyhd8ed1ab_0\n  - requests=2.31.0=pyhd8ed1ab_0\n  - pip:\n    - ujson==5.10.0\n"
    )
    conda_repo.chmod(0o755)
    stager = RepoStager(staging_root=Path(tempfile.mkdtemp(prefix="acceptance_conda_staging_")))
    staged = stager.stage_repository(paper_id="acceptance_conda", source=str(conda_repo))
    bundle = stager.bundle_dependencies(staged, python_version=args.python_version)
    r, meta = run_probe(runner, staged.staged_path, "probe_conda.py", "acceptance_conda", packages_dir=bundle["bundle_dir"])
    show("13. Conda-only repository (environment.yml, no requirements file)", r.command_executed,
         "\n".join([(f"bundle: status={bundle['status']} converted={bundle.get('converted')} "
                    f"downloaded={bundle.get('downloaded')} conda_only={bundle.get('conda_only')} "
                    f"skipped={[x['package'] for x in bundle.get('skipped', [])]} "
                    f"env_python_versions={bundle.get('env_python_versions')}"),
                    r.stdout.strip()[-500:], *summary(r, meta)]))
    results["13 conda-only repository installed offline"] = (
        bundle.get("source") == "conda_env" and bundle["status"] == "SUCCESS"
        and r.status == "COMPLETED" and meta.get("dependency_install_status") == "INSTALLED"
        and r.stdout.count("imported from /workspace/deps/") == 2
    )

    # 14. installed versions recorded (#161): the install phase of check 5 wrote installed_packages.json
    installed_path = SANDBOX_RUNS_DIR / "acceptance_offline" / "installed_packages.json"
    installed = json.loads(installed_path.read_text()) if installed_path.exists() else None
    show("14. Installed package versions recorded by the install phase", ["(reads installed_packages.json of check 5)"],
         f"installed_packages.json: {json.dumps(installed)}")
    results["14 installed versions recorded"] = (
        isinstance(installed, list) and {"name": "toolz", "version": "0.12.1"} in
        [{"name": x.get("name"), "version": x.get("version")} for x in installed]
    )

    # 15. run setup (#166): working directory, writable per-run copy, read-only data mount
    setup_repo = Path(tempfile.mkdtemp(prefix="acceptance_setup_repo_"))
    (setup_repo / "sub").mkdir()
    (setup_repo / "sub" / "probe_runsetup.py").write_text(
        "import os\n"
        "print(f'cwd={os.getcwd()}')\n"
        "open('written_by_paper.txt', 'w').write('ok')\n"
        "print('written next to the script: ok')\n"
        "print('data: ' + open('/workspace/repo/data/X.csv').read().strip())\n"
        "try:\n"
        "    open('/workspace/repo/data/new.txt', 'w')\n"
        "    print('data writable: True')\n"
        "except OSError as exc:\n"
        "    print(f'data writable: False ({exc.strerror})')\n"
    )
    for path in [setup_repo, *setup_repo.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    data_cache = Path(tempfile.mkdtemp(prefix="acceptance_data_cache_"))
    (data_cache / "X.csv").write_text("a,b\n1,2\n")
    data_cache.chmod(0o755)
    (data_cache / "X.csv").chmod(0o644)
    setup_runner = DockerSandboxRunner(SandboxConfig(timeout_seconds=120, python_version=args.python_version,
                                                     working_dir="sub", writable_repo=True,
                                                     data_mounts={"data": str(data_cache)}))
    r, meta = run_probe(setup_runner, setup_repo, "sub/probe_runsetup.py", "acceptance_runsetup")
    copy_file = SANDBOX_RUNS_DIR / "acceptance_runsetup" / "repo_copy" / "sub" / "written_by_paper.txt"
    show("15. Run setup: working directory, writable copy, read-only data", r.command_executed,
         "\n".join([r.stdout.strip(), *summary(r, meta),
                    f"file in the per-run copy: {copy_file.exists()}",
                    f"file in the staged repository: {(setup_repo / 'sub' / 'written_by_paper.txt').exists()}"]))
    results["15 run setup (working dir, writable copy, read-only data)"] = (
        r.status == "COMPLETED" and "cwd=/workspace/repo/sub" in r.stdout and "data: a,b" in r.stdout
        and "data writable: False" in r.stdout and copy_file.exists()
        and not (setup_repo / "sub" / "written_by_paper.txt").exists()
    )

    # 16. image size (#163)
    inspect = subprocess.run(["docker", "image", "inspect", image_for(args.python_version), "--format", "{{.Size}}"],
                             capture_output=True, text=True, timeout=60, check=False)
    size = int(inspect.stdout.strip()) if inspect.returncode == 0 and inspect.stdout.strip().isdigit() else None
    show("16. Image size", ["docker", "image", "inspect", image_for(args.python_version), "--format", "{{.Size}}"],
         f"{inspect.stdout.strip() or inspect.stderr.strip()}"
         + (f"\nsize: {size} bytes ({size / 2**20:.1f} MiB)" if size else ""))
    results["16 image size measured"] = size is not None and size > 0

    # 17. CPU limit (#163): --cpus=0.5 must hold two busy workers to at most 0.6 CPUs together. The control run
    # sets the limit to the host's CPU count and must exceed 1.5 CPUs, or the probe proves nothing.
    def effective_cpus(stdout):
        for line in stdout.splitlines():
            if "effective_cpus=" in line:
                return float(line.rsplit("=", 1)[1])
        return None

    host_cpus = os.cpu_count() or 1
    limited = DockerSandboxRunner(SandboxConfig(timeout_seconds=60, cpus=0.5, python_version=args.python_version))
    r, meta = run_probe(limited, repo, "probe_cpu.py", "acceptance_cpu_limited")
    limited_cpus = effective_cpus(r.stdout)
    control = DockerSandboxRunner(SandboxConfig(timeout_seconds=60, cpus=float(host_cpus), python_version=args.python_version))
    rc, meta_c = run_probe(control, repo, "probe_cpu.py", "acceptance_cpu_control")
    control_cpus = effective_cpus(rc.stdout)
    show("17. CPU limit under load", r.command_executed,
         "\n".join([f"host CPUs: {host_cpus}", "--cpus=0.5:", r.stdout.strip(), *summary(r, meta),
                    f"control --cpus={float(host_cpus)}:", rc.stdout.strip(), *summary(rc, meta_c)]))
    results["17 cpu limit holds under load"] = (
        r.status == "COMPLETED" and limited_cpus is not None and limited_cpus <= 0.6
        and rc.status == "COMPLETED" and control_cpus is not None and control_cpus > 1.5
    )

    # 18. build phase (#193): a pure-Python sdist and a C extension built into wheels in the sandbox, then installed
    build_inputs = Path(tempfile.mkdtemp(prefix="acceptance_build_inputs_"))
    with tarfile.open(build_inputs / "rrtoy_pure-1.0.tar.gz", "w:gz") as tar:
        for name, body in {
            "rrtoy_pure-1.0/setup.py": "from setuptools import setup\nsetup(name='rrtoy_pure', version='1.0', py_modules=['rrtoy_pure'])\n",
            "rrtoy_pure-1.0/rrtoy_pure.py": "VALUE = 'pure-ok'\n",
            "rrtoy_pure-1.0/PKG-INFO": "Metadata-Version: 1.0\nName: rrtoy_pure\nVersion: 1.0\n",
        }.items():
            data = body.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    c_repo = Path(tempfile.mkdtemp(prefix="acceptance_c_repo_"))
    (c_repo / "setup.py").write_text(
        "from setuptools import Extension, setup\n"
        "setup(name='rrtoy_c', version='1.0', ext_modules=[Extension('rrtoy_c', ['rrtoy_c.c'])])\n")
    (c_repo / "rrtoy_c.c").write_text(
        "#include <Python.h>\n"
        "static PyObject* answer(PyObject* self, PyObject* args) { return PyLong_FromLong(42); }\n"
        "static PyMethodDef M[] = {{\"answer\", answer, METH_NOARGS, \"\"}, {NULL, NULL, 0, NULL}};\n"
        "static struct PyModuleDef D = {PyModuleDef_HEAD_INIT, \"rrtoy_c\", NULL, -1, M};\n"
        "PyMODINIT_FUNC PyInit_rrtoy_c(void) { return PyModule_Create(&D); }\n")
    for path in [build_inputs, c_repo, *build_inputs.iterdir(), *c_repo.iterdir()]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    built = runner.build_wheels("acceptance_build", c_repo, build_inputs,
                                ["/workspace/packages/rrtoy_pure-1.0.tar.gz", "/workspace/repo"], [], from_repo=True)
    built_names = sorted(Path(w).name for w in built["wheels"])
    run_packages = Path(tempfile.mkdtemp(prefix="acceptance_built_packages_"))
    for wheel in built["wheels"]:
        shutil.copy2(wheel, run_packages / Path(wheel).name)
    run_packages.chmod(0o755)
    use_repo = Path(tempfile.mkdtemp(prefix="acceptance_use_repo_"))
    (use_repo / "requirements.txt").write_text("rrtoy_pure==1.0\nrrtoy_c==1.0\n")
    (use_repo / "probe_built.py").write_text(
        "import shutil, rrtoy_pure, rrtoy_c\n"
        "print(f'pure: {rrtoy_pure.VALUE} from {rrtoy_pure.__file__}')\n"
        "print(f'c extension: answer()={rrtoy_c.answer()} from {rrtoy_c.__file__}')\n"
        "print(f'compiler in the run image: {shutil.which(\"gcc\")}')\n")
    for path in [use_repo, *use_repo.iterdir()]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    r, meta = run_probe(runner, use_repo, "probe_built.py", "acceptance_build_use", packages_dir=run_packages)
    show("18. Build phase: sdist and C extension built offline, then installed and imported", built["command_executed"],
         "\n".join([f"build image: {built['image']} ({build_image_for(args.python_version)})",
                    f"build status={built['status']} exit_code={built['exit_code']} wheels={built_names}",
                    "build log (last 800 chars):", built["log_tail"][-800:].strip(),
                    "--- run phase ---", r.stdout.strip(), *summary(r, meta)]))
    results["18 build phase (sdist and C extension, offline)"] = (
        built["status"] == "BUILT" and len(built_names) == 2 and any("rrtoy_c" in n for n in built_names)
        and "--network" in built["command_executed"] and r.status == "COMPLETED"
        and meta.get("dependency_install_status") == "INSTALLED"
        and "pure: pure-ok from /workspace/deps/" in r.stdout and "answer()=42 from /workspace/deps/" in r.stdout
        and "compiler in the run image: None" in r.stdout
    )

    # 19. writable data copy (#193): the run writes into its copy of the data; the host cache stays unchanged.
    # The target is nested under /workspace/home: the run must also be able to create a file NEXT TO the data
    # (openml writes its config beside its cache), which fails when Docker creates the parent as root (#231).
    cache_dir = Path(tempfile.mkdtemp(prefix="acceptance_writable_cache_"))
    (cache_dir / "description.xml").write_text("<cached/>\n")
    cache_dir.chmod(0o755)
    (cache_dir / "description.xml").chmod(0o644)
    (repo / "probe_datacopy.py").write_text(
        "import os\n"
        "base = '/workspace/home/.cache/lib'\n"
        "print('read: ' + open(base + '/description.xml').read().strip())\n"
        "open(base + '/parsed.pkl', 'w').write('parsed')\n"
        "print('wrote parsed.pkl: ' + str(os.path.exists(base + '/parsed.pkl')))\n"
        "open('/workspace/home/.cache/sibling_config', 'w').write('config')\n"
        "print('wrote a file next to the data: ' + str(os.path.exists('/workspace/home/.cache/sibling_config')))\n")
    copy_runner = DockerSandboxRunner(SandboxConfig(
        timeout_seconds=120, python_version=args.python_version,
        data_mounts={"/workspace/home/.cache/lib": str(cache_dir)}, writable_data=["/workspace/home/.cache/lib"]))
    r, meta = run_probe(copy_runner, repo, "probe_datacopy.py", "acceptance_datacopy")
    copied = SANDBOX_RUNS_DIR / "acceptance_datacopy" / "home_mounts" / ".cache" / "lib" / "parsed.pkl"
    show("19. Writable data copy", r.command_executed,
         "\n".join([r.stdout.strip(), *summary(r, meta), f"file in the per-run copy: {copied.exists()}",
                    f"host cache files: {sorted(p.name for p in cache_dir.iterdir())}"]))
    results["19 writable data copy"] = (
        r.status == "COMPLETED" and "read: <cached/>" in r.stdout and "wrote parsed.pkl: True" in r.stdout
        and "wrote a file next to the data: True" in r.stdout and copied.exists() and sorted(p.name for p in cache_dir.iterdir()) == ["description.xml"]
    )

    # 20. GPU is opt-in (#169): the default run of check 1 asked for no GPU and saw none
    identity_meta_path = SANDBOX_RUNS_DIR / "acceptance_identity" / "execution_meta.json"
    identity_meta = json.loads(identity_meta_path.read_text()) if identity_meta_path.exists() else {}
    identity_cmd = DockerSandboxRunner(SandboxConfig(python_version=args.python_version)).build_docker_command(
        repo, SANDBOX_RUNS_DIR / "acceptance_identity", ["python", "probe_identity.py"])
    show("20. GPU is opt-in", ["(reads execution_meta.json of check 1)"],
         f"--gpus in the default command: {'--gpus' in identity_cmd}\n"
         f"gpu_requested={identity_meta.get('gpu_requested')} gpu_devices={identity_meta.get('gpu_devices')} "
         f"gpu_peak_memory_used_mib={identity_meta.get('gpu_peak_memory_used_mib')}")
    results["20 gpu is opt-in"] = (
        "--gpus" not in identity_cmd and identity_meta.get("gpu_requested") is False
        and identity_meta.get("gpu_devices") == [] and identity_meta.get("gpu_peak_memory_used_mib") is None
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
