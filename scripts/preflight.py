#!/usr/bin/env python3
"""Check that this machine can do a real run, before one starts (#378).

    python scripts/preflight.py            # print the checks; exit 1 if one FAILED
    python scripts/preflight.py --json     # the same as JSON
    python scripts/preflight.py --no-start # do not try to start Docker Desktop

The checks are: Docker answers (if not, Docker Desktop is started and awaited), free disk space, available memory, the
sleep setting of the power plan (a sleeping machine stops a run that takes hours), what Docker itself can see (CPUs and
memory, which are what a WSL2 backend gets), and a real hello-world: a container of the sandbox image with the sandbox's
own isolation (no network, read-only root, no capabilities) that prints one line.

PASS means the check holds, WARN means a run may be affected (it is printed, the run goes on), FAIL stops the run.
`scripts/run_pilot.py` and `cli.py score` call `ensure_ready()` before a real run. The environment variable
`REPRO_RADAR_SKIP_PREFLIGHT=1` skips it (the tests use it); a skipped preflight is printed, not hidden.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.sandbox.runner import DEFAULT_PYTHON_VERSION, image_for

DOCKER_DESKTOP_EXE = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "DockerDesktop" / "Docker Desktop.exe"
DOCKER_START_WAIT_SECONDS = 240
GIB = 1024 ** 3
DISK_FAIL_GIB = 10
DISK_WARN_GIB = 30
MEMORY_FAIL_GIB = 2
MEMORY_WARN_GIB = 8
DOCKER_MEMORY_FAIL_GIB = 4
SLEEP_SUBGROUP = "238c9fa8-0aad-41ed-83f4-97be242c8f20"  # SUB_SLEEP
SLEEP_AFTER = "29f6c1db-86da-48c5-9fdb-f2b67b1f44da"  # STANDBYIDLE
SKIP_VARIABLE = "REPRO_RADAR_SKIP_PREFLIGHT"
HELLO_TIMEOUT_SECONDS = 120

Runner = Callable[[list[str], int], subprocess.CompletedProcess]


@dataclass
class Check:
    name: str
    status: str  # PASS, WARN, FAIL
    detail: str


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)


def _docker_info(run: Runner) -> dict | None:
    try:
        out = run(["docker", "info", "--format", "{{json .}}"], 30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        info = json.loads(out.stdout)
    except ValueError:
        return None
    return info if isinstance(info, dict) and info.get("ServerVersion") else None


def check_docker(run: Runner = _run, start: bool = True, exe: Path = DOCKER_DESKTOP_EXE, wait: int = DOCKER_START_WAIT_SECONDS,
                 sleep: Callable[[float], None] = time.sleep, popen: Callable = subprocess.Popen) -> tuple[Check, dict | None]:
    info = _docker_info(run)
    if info:
        return Check("docker", "PASS", f"Docker engine {info['ServerVersion']} answers"), info
    if not start:
        return Check("docker", "FAIL", "Docker does not answer and starting it was not asked for"), None
    if not exe.is_file():
        return Check("docker", "FAIL", f"Docker does not answer and {exe} does not exist, so it cannot be started"), None
    popen([str(exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    waited = 0
    while waited < wait:
        sleep(5)
        waited += 5
        info = _docker_info(run)
        if info:
            return Check("docker", "PASS", f"Docker Desktop was started; the engine {info['ServerVersion']} answered after about {waited} s"), info
    return Check("docker", "FAIL", f"Docker Desktop was started but the engine did not answer within {wait} s"), None


def check_disk(path: Path = project_root, usage: Callable = shutil.disk_usage) -> Check:
    free = usage(path).free / GIB
    detail = f"{free:.1f} GiB free on the drive of {path}"
    if free < DISK_FAIL_GIB:
        return Check("disk", "FAIL", f"{detail} (less than {DISK_FAIL_GIB} GiB)")
    if free < DISK_WARN_GIB:
        return Check("disk", "WARN", f"{detail} (less than {DISK_WARN_GIB} GiB; images, wheels and run files need space)")
    return Check("disk", "PASS", detail)


def available_memory_bytes() -> int:
    """Memory that is free for a new process, in bytes (0 if it cannot be read)."""
    if os.name == "nt":
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                        ("avail", ctypes.c_ulonglong), ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
                        ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                        ("avail_extended", ctypes.c_ulonglong)]

        status = Status()
        status.length = ctypes.sizeof(Status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return int(status.avail)
        return 0
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return 0


def check_memory(available: Callable[[], int] = available_memory_bytes) -> Check:
    free = available() / GIB
    if free <= 0:
        return Check("memory", "WARN", "the available memory could not be read")
    detail = f"{free:.1f} GiB available"
    if free < MEMORY_FAIL_GIB:
        return Check("memory", "FAIL", f"{detail} (less than {MEMORY_FAIL_GIB} GiB)")
    if free < MEMORY_WARN_GIB:
        return Check("memory", "WARN", f"{detail} (less than {MEMORY_WARN_GIB} GiB; close programs before a run at 50% memory)")
    return Check("memory", "PASS", detail)


def parse_sleep_seconds(powercfg_output: str) -> dict[str, int]:
    """The AC and DC 'sleep after' settings of a `powercfg /query` text, in seconds (0 means never)."""
    found: dict[str, int] = {}
    for kind, label in (("ac", "Current AC Power Setting Index"), ("dc", "Current DC Power Setting Index")):
        match = re.search(rf"{label}:\s*0x([0-9a-fA-F]+)", powercfg_output)
        if match:
            found[kind] = int(match.group(1), 16)
    return found


def check_sleep(run: Runner = _run, system: str = sys.platform) -> Check:
    if system != "win32":
        return Check("sleep", "WARN", f"the sleep setting is only read on Windows (this is {system}); not checked")
    try:
        out = run(["powercfg", "/query", "SCHEME_CURRENT", SLEEP_SUBGROUP, SLEEP_AFTER], 30)
    except (OSError, subprocess.SubprocessError) as exc:
        return Check("sleep", "WARN", f"powercfg did not run ({type(exc).__name__}); not checked")
    settings = parse_sleep_seconds(out.stdout)
    if out.returncode != 0 or "ac" not in settings:
        return Check("sleep", "WARN", "the sleep setting could not be read; not checked")
    ac = settings["ac"]
    if ac == 0:
        return Check("sleep", "PASS", "the machine does not sleep on mains power (sleep after: never)")
    return Check("sleep", "WARN", f"the machine sleeps on mains power after {ac // 60} min; a run of hours can be stopped by it "
                                  "(Settings > System > Power: set sleep to Never)")


def check_docker_resources(info: dict | None) -> Check:
    if not info:
        return Check("docker_resources", "FAIL", "Docker did not answer, so its resources are unknown")
    cpus = int(info.get("NCPU") or 0)
    memory = int(info.get("MemTotal") or 0) / GIB
    detail = f"Docker sees {cpus} CPUs and {memory:.1f} GiB of memory ({info.get('OperatingSystem', 'unknown system')})"
    if cpus < 2 or memory < DOCKER_MEMORY_FAIL_GIB:
        return Check("docker_resources", "FAIL", f"{detail} (a run needs at least 2 CPUs and {DOCKER_MEMORY_FAIL_GIB} GiB)")
    return Check("docker_resources", "PASS", detail)


def check_hello_world(run: Runner = _run, image: str | None = None) -> Check:
    image = image or image_for(DEFAULT_PYTHON_VERSION)
    cmd = ["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "--entrypoint", "python", image, "-c", "print('preflight hello-world')"]
    try:
        out = run(cmd, HELLO_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return Check("hello_world", "FAIL", f"the container of {image} did not finish within {HELLO_TIMEOUT_SECONDS} s")
    except (OSError, subprocess.SubprocessError) as exc:
        return Check("hello_world", "FAIL", f"docker run did not start ({type(exc).__name__})")
    if out.returncode == 0 and "preflight hello-world" in out.stdout:
        return Check("hello_world", "PASS", f"a container of {image} ran with no network and a read-only root and printed its line")
    return Check("hello_world", "FAIL", f"the container of {image} failed (exit code {out.returncode}): "
                                        f"{(out.stderr or out.stdout).strip()[-300:]}")


def run_checks(start_docker: bool = True) -> list[Check]:
    docker, info = check_docker(start=start_docker)
    checks = [docker, check_disk(), check_memory(), check_sleep(), check_docker_resources(info)]
    # Without a Docker engine there is nothing to run the container on.
    checks.append(check_hello_world() if info else Check("hello_world", "FAIL", "Docker did not answer, so no container was run"))
    return checks


def format_checks(checks: list[Check]) -> str:
    return "\n".join(f"  [{c.status:<4}] {c.name}: {c.detail}" for c in checks)


def ensure_ready(start_docker: bool = True, out=None) -> list[Check]:
    """Run the checks, print them, and raise RuntimeError if one FAILED. Skipped (and said so) with REPRO_RADAR_SKIP_PREFLIGHT=1."""
    out = out or sys.stderr
    if os.environ.get(SKIP_VARIABLE) == "1":
        print(f"preflight skipped ({SKIP_VARIABLE}=1)", file=out)
        return []
    checks = run_checks(start_docker)
    print("preflight:\n" + format_checks(checks), file=out)
    failed = [c for c in checks if c.status == "FAIL"]
    if failed:
        raise RuntimeError("preflight failed: " + "; ".join(f"{c.name}: {c.detail}" for c in failed))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check this machine before a real run (#378).")
    parser.add_argument("--json", action="store_true", help="print the checks as JSON")
    parser.add_argument("--no-start", action="store_true", help="do not try to start Docker Desktop")
    args = parser.parse_args(argv)
    checks = run_checks(start_docker=not args.no_start)
    print(json.dumps([asdict(c) for c in checks], indent=2) if args.json else format_checks(checks))
    return 1 if any(c.status == "FAIL" for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
