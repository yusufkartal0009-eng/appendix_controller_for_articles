"""Unit tests for the Docker and Process sandbox execution runner."""

import os
from pathlib import Path
import subprocess
import tempfile
import pytest

from src.sandbox import runner as runner_module
from src.sandbox.runner import (
    DockerSandboxRunner,
    ProcessSandboxRunner,
    SandboxConfig,
    SandboxUnavailableError,
)


def test_sandbox_config_defaults():
    """Verify security default configuration parameters."""
    cfg = SandboxConfig()
    assert cfg.cpus == 2.0
    assert cfg.memory_limit == "8g"
    assert cfg.memory_swap == "8g"
    assert cfg.pids_limit == 100
    assert cfg.timeout_seconds == 600
    assert cfg.network_isolated is True
    assert cfg.read_only_root is True
    assert cfg.user_id == 1000
    assert cfg.group_id == 1000
    assert cfg.allow_unsafe_local is False


def test_build_docker_command_security_flags():
    """Verify all security and isolation flags in constructed docker command."""
    cfg = SandboxConfig(
        cpus=1.5,
        memory_limit="4g",
        memory_swap="4g",
        pids_limit=50,
        timeout_seconds=300,
    )
    runner = DockerSandboxRunner(config=cfg)

    cmd = runner.build_docker_command(
        repo_dir="/tmp/sample_repo",
        output_dir="/tmp/sample_output",
        command=["python", "train.py"],
    )

    # 1. Network isolation
    assert "--network" in cmd
    net_idx = cmd.index("--network")
    assert cmd[net_idx + 1] == "none"

    # 2. Filesystem security
    assert "--read-only" in cmd
    assert "--tmpfs" in cmd
    assert any("/tmp:rw,noexec,nosuid,size=64m" in arg for arg in cmd)

    # 3. Privilege escalation prevention & non-root user
    assert "--security-opt" in cmd
    assert "no-new-privileges:true" in cmd
    assert "--user" in cmd
    user_idx = cmd.index("--user")
    assert cmd[user_idx + 1] == "1000:1000"

    # 4. Quotas
    assert "--cpus=1.5" in cmd
    assert "--memory=4g" in cmd
    assert "--memory-swap=4g" in cmd
    assert "--pids-limit=50" in cmd

    # 5. Working Directory & Python Environment Isolation
    assert "-w" in cmd
    w_idx = cmd.index("-w")
    assert cmd[w_idx + 1] == "/workspace/repo"
    assert any("PYTHONUSERBASE=/workspace/home/.local" in arg for arg in cmd)
    assert any("PYTHONPATH=/workspace/repo" in arg for arg in cmd)

    # 6. Volume read-only constraints & home tmpfs execution permissions
    assert any(":ro" in arg and "sample_repo" in arg for arg in cmd)
    assert any(":rw" in arg and "sample_output" in arg for arg in cmd)
    assert any("/workspace/home:rw,nosuid,size=2048m" in arg for arg in cmd)


def test_process_sandbox_runner_clean_execution(tmp_path):
    """Verify ProcessSandboxRunner executes a script cleanly and captures logs."""
    script_file = tmp_path / "sample_benchmark.py"
    script_file.write_text(
        "import sys\nprint('Benchmark metric=0.942')\nsys.exit(0)\n",
        encoding="utf-8",
    )

    runner = ProcessSandboxRunner(timeout_seconds=10)
    result = runner.run(
        paper_id="test_paper_proc",
        repo_dir=tmp_path,
        target_script="sample_benchmark.py",
    )

    assert result.status == "COMPLETED"
    assert result.exit_code == 0
    assert "Benchmark metric=0.942" in result.stdout
    assert (result.output_dir / "stdout.log").exists()
    assert (result.output_dir / "stderr.log").exists()


def test_process_sandbox_runner_timeout(tmp_path):
    """Verify ProcessSandboxRunner terminates script when timeout expires."""
    script_file = tmp_path / "sleep_script.py"
    script_file.write_text(
        "import time\ntime.sleep(10)\n",
        encoding="utf-8",
    )

    runner = ProcessSandboxRunner(timeout_seconds=1)
    result = runner.run(
        paper_id="test_paper_timeout",
        repo_dir=tmp_path,
        target_script="sleep_script.py",
    )

    assert result.status == "TIMEOUT"
    assert result.exit_code == 124


def _docker_available(monkeypatch, available):
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *args, **kwargs: available))


def test_docker_runner_refuses_to_run_without_docker(tmp_path, monkeypatch):
    """Without Docker and without opt-in, nothing is executed on the host."""
    marker = tmp_path / "executed.marker"
    (tmp_path / "eval.py").write_text(
        f"open(r'{marker}', 'w').write('ran')\n", encoding="utf-8"
    )
    _docker_available(monkeypatch, False)

    with pytest.raises(SandboxUnavailableError, match="--allow-unsafe-local"):
        DockerSandboxRunner().run(paper_id="test_no_docker", repo_dir=tmp_path, target_script="eval.py")

    assert not marker.exists()


def test_docker_runner_unsafe_local_opt_in_marks_run_unisolated(tmp_path, monkeypatch):
    """With the explicit opt-in, the script runs locally and the result says it was not isolated."""
    (tmp_path / "eval.py").write_text("print('Local run executed')\n", encoding="utf-8")
    _docker_available(monkeypatch, False)

    runner = DockerSandboxRunner(config=SandboxConfig(allow_unsafe_local=True))
    result = runner.run(paper_id="test_unsafe_local", repo_dir=tmp_path, target_script="eval.py")

    assert result.status == "COMPLETED"
    assert "Local run executed" in result.stdout
    assert result.docker_used is False
    assert result.isolated is False
    assert result.to_dict()["isolated"] is False


def test_docker_runner_with_docker_reports_docker_used_and_isolated(tmp_path, monkeypatch):
    """With Docker available, execution goes through `docker run` and is marked isolated."""
    (tmp_path / "eval.py").write_text("print('ok')\n", encoding="utf-8")
    _docker_available(monkeypatch, True)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    result = DockerSandboxRunner().run(paper_id="test_with_docker", repo_dir=tmp_path, target_script="eval.py")

    assert calls and calls[0][:2] == ["docker", "run"]
    assert result.docker_used is True
    assert result.isolated is True
    assert result.to_dict()["docker_used"] is True
