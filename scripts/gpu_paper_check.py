#!/usr/bin/env python3
"""A small synthetic paper that needs a modern PyTorch and the local GPU, run through the real pipeline (#169).

    python scripts/gpu_paper_check.py            # needs Docker, the NVIDIA driver, and about 3 GB of wheels; writes data/gpu_check/

A tiny git repository is made in a temporary directory: `requirements.txt` pins `torch==2.8.0` (the default PyPI Linux wheel
of that release is built for CUDA 12.8, which the RTX 5070's Blackwell architecture needs), and `train.py` checks that CUDA is
visible to torch, does a matrix product on the GPU, compares it with the CPU result, and keeps the GPU busy for a few seconds.
The paper goes through the same code as a pilot paper (`scripts/run_pilot.py run_paper`: staging, wheel bundling in the
image, offline install, the sandbox with `--gpus all`, `--network none`, and a read-only root). The result is the container's own
output and the `gpu` block of `run_report.json`.

What it shows: the sandbox can give a modern PyTorch the GPU with the isolation unchanged. What it does not show: that any
real paper benefits from the GPU. The papers of the seed corpus pin PyTorch 1.x, which the RTX 5070 cannot use.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts import run_pilot
from scripts.synthetic_control import scrub_paths

PAPER_ID = "gpu_check_paper"
TORCH_REQUIREMENT = "torch==2.8.0"
OUT_DIR = project_root / "data" / "gpu_check"

TRAIN_PY = '''"""Synthetic paper: a tensor operation on the GPU, checked against the CPU."""
import time

import torch

print("torch_version:", torch.__version__)
print("torch_cuda_version:", torch.version.cuda)
print("cuda_available:", torch.cuda.is_available())
print("arch_list:", " ".join(torch.cuda.get_arch_list()))
if not torch.cuda.is_available():
    raise SystemExit("no CUDA device is visible to torch")
print("device_name:", torch.cuda.get_device_name(0))
print("device_capability:", torch.cuda.get_device_capability(0))
a = torch.arange(16, dtype=torch.float32).reshape(4, 4)
expected = a @ a
result = a.to("cuda") @ a.to("cuda")
torch.cuda.synchronize()
print("tensor_device:", result.device)
print("matmul_matches_cpu:", bool(torch.equal(result.cpu(), expected)))
# keep the GPU and its memory in use for a few seconds, so that the one-second memory sampler of the sandbox sees it
x = torch.randn(8192, 8192, device="cuda")
start = time.time()
while time.time() - start < 4:
    x = (x @ x).clamp_(-1, 1)
torch.cuda.synchronize()
print("gpu_memory_allocated_mib:", torch.cuda.memory_allocated() // 2**20)
'''
README = "# GPU check paper\n\nOne script that needs a modern PyTorch and a GPU. It tests the sandbox, not a paper.\n"


def make_repository(root: Path) -> tuple[Path, str]:
    repo = root / "gpu_check_repo"
    repo.mkdir(parents=True)
    (repo / "train.py").write_text(TRAIN_PY, encoding="utf-8", newline="\n")
    (repo / "requirements.txt").write_text(TORCH_REQUIREMENT + "\n", encoding="utf-8", newline="\n")
    (repo / "README.md").write_text(README, encoding="utf-8", newline="\n")
    env = ["-c", "user.name=synthetic", "-c", "user.email=synthetic@example.invalid"]
    for args in (["init", "-q", "-b", "main"], ["add", "."], [*env, "commit", "-q", "-m", "gpu check paper"]):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True,
                            text=True).stdout.strip()
    return repo, commit


def entry_for(repo: Path, commit: str) -> dict[str, Any]:
    return {
        "paper_id": PAPER_ID, "title": "GPU check paper", "repo_url": repo.as_posix(), "repo_commit": commit,
        "license": "MIT", "target_script": "train.py", "expected_claims": {}, "python_version": "3.11",
        "run_setup": {"decision": "fix", "reason": "Synthetic paper: a script that needs a modern PyTorch and the GPU."},
    }


def directory_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else 0


def parse_output(stdout: str) -> dict[str, str]:
    """The `key: value` lines that train.py prints."""
    values = {}
    for line in stdout.splitlines():
        key, sep, value = line.partition(": ")
        if sep and key.replace("_", "").isalnum():
            values[key] = value.strip()
    return values


def judge(report: dict[str, Any], printed: dict[str, str]) -> dict[str, bool]:
    """Each fact the check claims, from the container's own output and the run report."""
    gpu = report.get("gpu") or {}
    return {
        "run_completed_exit_0": report.get("status") == "COMPLETED" and report.get("exit_code") == 0,
        "gpu_requested": gpu.get("requested") == "all",
        "gpu_visible_in_container": bool(gpu.get("available")),
        "torch_sees_cuda": printed.get("cuda_available") == "True",
        "tensor_op_on_gpu": printed.get("tensor_device", "").startswith("cuda"),
        "gpu_result_matches_cpu": printed.get("matmul_matches_cpu") == "True",
        "report_gpu_used": gpu.get("used") is True,
        "isolated": report.get("isolated") is True and report.get("docker_used") is True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(OUT_DIR))
    parser.add_argument("--memory", default="50%")
    parser.add_argument("--cpus", type=float, default=4)
    args = parser.parse_args(argv)
    from scripts import preflight

    preflight.ensure_ready()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="gpu_check_") as tmp:
        tmp_path = Path(tmp)
        repo, commit = make_repository(tmp_path)
        entry = entry_for(repo, commit)
        staging = tmp_path / "staging"
        record = run_pilot.run_paper(PAPER_ID, staging, pilot2=True, record_root=out, entry_override=entry, gpus="all",
                                     memory_limit=args.memory, cpus=args.cpus, run_timeout=1800)
        packages_bytes = directory_size(staging / f"{PAPER_ID}_packages")
        run_dir = out / PAPER_ID
        report = json.loads((run_dir / "run_report.json").read_text(encoding="utf-8")) if (run_dir / "run_report.json").is_file() else {}
        stdout = (run_dir / "stdout.log").read_text(encoding="utf-8", errors="replace") if (run_dir / "stdout.log").is_file() else ""
        scrub_paths(out, {tmp_path.resolve(): "<TMP>", tmp_path: "<TMP>", project_root: "<REPO>", Path.home(): "<HOME>"})
    printed = parse_output(stdout)
    checks = judge(report, printed)
    result = {
        "paper_id": PAPER_ID, "requirement": TORCH_REQUIREMENT, "checks": checks, "all_checks_pass": all(checks.values()),
        "container_output": printed, "gpu_block_of_run_report": report.get("gpu"),
        "run": record.get("run"), "bundle_seconds": (record.get("bundle") or {}).get("duration_seconds"),
        "bundle_status": (record.get("bundle") or {}).get("status"), "bundled_packages_bytes": packages_bytes,
        "bundled_packages_gib": round(packages_bytes / 1024**3, 2), "sandbox_duration_seconds": record.get("sandbox_duration_seconds"),
        "limits": record.get("limits"), "gpus_override": record.get("gpus_override"),
        "note": "synthetic paper; shows that the sandbox can give a modern PyTorch the GPU, not that a real paper benefits",
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["all_checks_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
