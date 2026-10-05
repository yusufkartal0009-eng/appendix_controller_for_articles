"""Opt-in local GPU for the sandbox, recorded in the run report (#169)."""

import pytest

from src.sandbox.runner import (
    DockerSandboxRunner,
    SandboxConfig,
    SandboxUnavailableError,
)
from src.sandbox.stager import gpu_summary


def _cmd(tmp_path, **config):
    return DockerSandboxRunner(SandboxConfig(**config)).build_docker_command(tmp_path / "repo", tmp_path / "out", ["x"])


def test_gpu_is_off_by_default(tmp_path):
    assert "--gpus" not in _cmd(tmp_path)


def test_gpu_opt_in_keeps_every_isolation_flag(tmp_path):
    default, gpu = _cmd(tmp_path), _cmd(tmp_path, gpus="all")
    assert gpu[gpu.index("--gpus") + 1] == "all" and "SANDBOX_GPUS_REQUESTED=1" in gpu
    for flag in ("--read-only", "--network", "none", "no-new-privileges:true", "1000:1000", "--cpus=2.0", "--pids-limit=100"):
        assert flag in default and flag in gpu


@pytest.mark.parametrize("value", ["all", "1", "2", "device=0", "device=0,1"])
def test_valid_gpu_values(value):
    assert SandboxConfig(gpus=value).gpus == value


@pytest.mark.parametrize("value", ["yes", "0", "device=", "all --privileged", "device=0;rm"])
def test_invalid_gpu_values_are_refused(value):
    with pytest.raises(ValueError):
        SandboxConfig(gpus=value)


def test_local_fallback_refuses_a_gpu_run(tmp_path, monkeypatch):
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *a, **k: False))
    with pytest.raises(SandboxUnavailableError):
        DockerSandboxRunner(SandboxConfig(gpus="all", allow_unsafe_local=True)).run(
            paper_id="p", repo_dir=tmp_path, target_script="x.py")


def test_gpu_summary():
    assert gpu_summary("", {}) == {"requested": None, "available": False, "devices": [],
                                   "peak_memory_used_mib": None, "used": None}
    device = {"index": 0, "name": "NVIDIA GeForce RTX 5070", "driver": "580.1", "memory_total_mib": 12227,
              "memory_used_before_mib": 600}
    used = gpu_summary("all", {"gpu_devices": [device], "gpu_peak_memory_used_mib": 3100})
    assert used["available"] and used["used"] is True and used["requested"] == "all"
    idle = gpu_summary("all", {"gpu_devices": [device], "gpu_peak_memory_used_mib": 600})
    assert idle["used"] is False
    requested_not_visible = gpu_summary("all", {"gpu_devices": [], "gpu_peak_memory_used_mib": None})
    assert requested_not_visible["available"] is False and requested_not_visible["used"] is None
