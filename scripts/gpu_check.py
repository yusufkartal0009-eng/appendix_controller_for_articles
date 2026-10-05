#!/usr/bin/env python3
"""Show the local NVIDIA GPU inside the sandbox container, with the isolation unchanged (#169).

Run on a machine with Docker Desktop (WSL2 backend), the NVIDIA driver, and the sandbox image:

    python scripts/gpu_check.py                    # --gpus all, image repro-radar-sandbox:latest
    python scripts/gpu_check.py --python-version 3.8 --gpus device=0

The probe runs through DockerSandboxRunner, the same code path as paper runs. It prints what the container sees
(nvidia-smi, uid, network, read-only root), and the run report's GPU summary. Exit code 0 only when the GPU is
visible inside the container and the isolation checks hold. This is the evidence #169 asks for; it cannot run on
GitHub's runners, which have no GPU.

Note for the pilot report: the RTX 5070 (Blackwell) needs a PyTorch build for CUDA 12.8 or newer; the PyTorch 1.x
versions that several seed papers pin cannot use it, so those papers run on the CPU even with a GPU available.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
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
)
from src.sandbox.stager import gpu_summary

PROBE = (
    "import os, socket, subprocess\n"
    "r = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'],\n"
    "                   capture_output=True, text=True)\n"
    "print('nvidia-smi: ' + (r.stdout.strip() or r.stderr.strip() or f'exit {r.returncode}'))\n"
    "print(f'uid={os.getuid()} gid={os.getgid()}')\n"
    "try:\n"
    "    socket.create_connection(('1.1.1.1', 53), timeout=3)\n"
    "    print('network: REACHABLE')\n"
    "except OSError as exc:\n"
    "    print(f'network: blocked ({exc.strerror or exc})')\n"
    "try:\n"
    "    open('/usr/rr_probe', 'w')\n"
    "    print('root filesystem: WRITABLE')\n"
    "except OSError as exc:\n"
    "    print(f'root filesystem: read-only ({exc.strerror})')\n"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show the local GPU inside the sandbox (#169).")
    parser.add_argument("--gpus", default="all", help="Value for docker run --gpus (default: all).")
    parser.add_argument("--python-version", default=DEFAULT_PYTHON_VERSION)
    args = parser.parse_args(argv)

    repo = Path(tempfile.mkdtemp(prefix="gpu_check_repo_"))
    (repo / "probe_gpu.py").write_text(PROBE, encoding="utf-8")
    out_dir = SANDBOX_RUNS_DIR / "gpu_check"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    runner = DockerSandboxRunner(SandboxConfig(timeout_seconds=120, python_version=args.python_version, gpus=args.gpus))
    result = runner.run(paper_id="gpu_check", repo_dir=repo, target_script="probe_gpu.py")
    meta_path = out_dir / "execution_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    summary = gpu_summary(args.gpus, meta)
    print("$ " + " ".join(result.command_executed))
    print(result.stdout.strip())
    if result.stderr.strip():
        print("stderr: " + result.stderr.strip()[-1500:])
    print("run report GPU summary: " + json.dumps(summary))
    ok = (result.status == "COMPLETED" and summary["available"] and "uid=1000" in result.stdout
          and "network: blocked" in result.stdout and "root filesystem: read-only" in result.stdout)
    print("GPU visible with isolation intact: " + ("YES" if ok else "NO"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
