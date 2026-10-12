#!/usr/bin/env python3
"""Record the Pilot 2 environment from command output only (docs/PILOT_2.md section 2).

    python scripts/record_pilot2_environment.py            # Pilot 2
    python scripts/record_pilot2_environment.py --pilot3   # Pilot 3 (docs/PILOT_3.md section 7): data/pilot3_runs/

Writes data/pilot2_runs/environment.txt: the Repro Radar commit and `git status`, `docker version` and `docker info`,
`nvidia-smi` on the host, the output of scripts/gpu_check.py (the GPU inside the sandbox, #169), and the free disk
space. Each block names the command it came from; a command that fails is recorded with its error, not skipped.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
OUT = project_root / "data" / "pilot2_runs" / "environment.txt"
OUT_PILOT3 = project_root / "data" / "pilot3_runs" / "environment.txt"

COMMANDS: list[tuple[str, list[str]]] = [
    ("python --version", [sys.executable, "--version"]),
    ("git rev-parse HEAD", ["git", "rev-parse", "HEAD"]),
    ("git status --short", ["git", "status", "--short"]),
    ("docker version", ["docker", "version"]),
    ("docker info", ["docker", "info"]),
    ("nvidia-smi", ["nvidia-smi"]),
    ("python scripts/gpu_check.py", [sys.executable, "scripts/gpu_check.py"]),
    ("docker image ls repro-radar-sandbox", ["docker", "image", "ls", "repro-radar-sandbox"]),
]


def run(command: list[str]) -> str:
    try:
        res = subprocess.run(command, cwd=project_root, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=900, check=False,
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    except (OSError, subprocess.SubprocessError) as exc:
        return f"FAILED to run: {exc}"
    text = (res.stdout or "") + (("\n[stderr]\n" + res.stderr) if res.stderr.strip() else "")
    return f"{text.rstrip()}\n[exit code {res.returncode}]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record the pilot environment from command output.")
    parser.add_argument("--pilot3", action="store_true", help="Write the Pilot 3 record instead of Pilot 2's.")
    args = parser.parse_args([] if argv is None else argv)
    out = OUT_PILOT3 if args.pilot3 else OUT
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    blocks = [f"Pilot {3 if args.pilot3 else 2} environment, recorded {stamp} by scripts/record_pilot2_environment.py"]
    for title, command in COMMANDS:
        blocks.append(f"=== {title}\n{run(command)}")
    usage = shutil.disk_usage(project_root)
    blocks.append(f"=== disk usage of the drive holding the repository (shutil.disk_usage)\n"
                  f"total={usage.total} used={usage.used} free={usage.free}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
