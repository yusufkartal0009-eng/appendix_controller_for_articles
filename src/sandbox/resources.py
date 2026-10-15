"""Resolve a container memory limit written as a share of the host's memory (for example ``50%``).

A fixed size such as ``8g`` passes through unchanged. A percentage is resolved at run time from the host's physical
memory, and capped at 90 percent of the memory that Docker itself can see: Docker Desktop on WSL2 gives its virtual
machine about half of the host's RAM by default, so a container limit above that cannot be met and would starve the
Docker daemon.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

DOCKER_SHARE_CAP = 0.9
MIN_LIMIT_MIB = 512


def host_memory_bytes() -> int:
    """Total physical memory of the host, in bytes (0 if it cannot be read)."""
    try:
        if sys.platform == "win32":
            class _MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MemoryStatus()
            status.dwLength = ctypes.sizeof(status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))  # type: ignore[attr-defined]
            return int(status.ullTotalPhys)
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=10, check=False)
            return int(out.stdout.strip())
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, subprocess.SubprocessError, AttributeError):
        pass
    return 0


def docker_memory_bytes() -> int:
    """Memory that the Docker engine can use, in bytes (0 if Docker does not answer)."""
    try:
        out = subprocess.run(["docker", "info", "--format", "{{.MemTotal}}"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30, check=False)
        return int(out.stdout.strip()) if out.returncode == 0 else 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def resolve_memory_limit(value: str) -> str:
    """Return a Docker memory size for `value`: a size passes through, ``NN%`` is resolved (see the module text).

    Raises ValueError for a percentage outside 1 to 100 or when the host's memory cannot be read.
    """
    text = str(value).strip()
    if not text.endswith("%"):
        return text
    try:
        percent = float(text[:-1])
    except ValueError as exc:
        raise ValueError(f"not a memory limit: {value!r}") from exc
    if not 1 <= percent <= 100:
        raise ValueError(f"a memory percentage must be between 1 and 100, not {value!r}")
    host = host_memory_bytes()
    if host <= 0:
        raise ValueError("cannot read the host's physical memory, so a percentage cannot be resolved; give a size such as 8g")
    limit = host * percent / 100
    docker = docker_memory_bytes()
    if docker > 0:
        limit = min(limit, docker * DOCKER_SHARE_CAP)
    return f"{max(int(limit // (1024 * 1024)), MIN_LIMIT_MIB)}m"
