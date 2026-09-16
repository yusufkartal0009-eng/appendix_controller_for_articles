"""Unit tests for the Docker and Process sandbox execution runner."""

import os
from pathlib import Path
import tempfile
import pytest

from src.sandbox.runner import (
    DockerSandboxRunner,
    ProcessSandboxRunner,
    SandboxConfig,
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

    # 5. Volume read-only constraints
    assert any(":ro" in arg and "sample_repo" in arg for arg in cmd)
    assert any(":rw" in arg and "sample_output" in arg for arg in cmd)


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


def test_docker_sandbox_runner_fallback(tmp_path, monkeypatch):
    """Verify DockerSandboxRunner gracefully falls back to local runner when docker is absent."""
    script_file = tmp_path / "eval.py"
    script_file.write_text("print('Fallback executed')\n", encoding="utf-8")

    # Force is_docker_available to return False
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *args, **kwargs: False))

    runner = DockerSandboxRunner()
    result = runner.run(
        paper_id="test_paper_fallback",
        repo_dir=tmp_path,
        target_script="eval.py",
    )

    assert result.docker_used is False
    assert result.status == "COMPLETED"
    assert "Fallback executed" in result.stdout
