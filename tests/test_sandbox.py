"""Unit tests for the Docker and Process sandbox execution runner."""

import json
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
    assert any("/workspace/home:rw,noexec,nosuid,size=2048m,uid=1000,gid=1000" in arg for arg in cmd)


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


def test_docker_run_status_survives_unwritable_logs_written_by_container(tmp_path, monkeypatch):
    """Logs created by the container user (another uid) must not turn a successful run into FAILED."""
    (tmp_path / "eval.py").write_text("print('ok')\n", encoding="utf-8")
    _docker_available(monkeypatch, True)
    monkeypatch.setattr(runner_module, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    out_dir = tmp_path / "runs" / "test_log_perms"
    out_dir.mkdir(parents=True)
    for name in ("stdout.log", "stderr.log"):
        log = out_dir / name
        log.write_text("written by the container entrypoint\n", encoding="utf-8")
        log.chmod(0o444)  # simulates a file owned by uid 1000 that the host user cannot overwrite

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="accuracy: 0.9\n", stderr="")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)
    try:
        result = DockerSandboxRunner().run(paper_id="test_log_perms", repo_dir=tmp_path, target_script="eval.py")
    finally:
        for name in ("stdout.log", "stderr.log"):
            (out_dir / name).chmod(0o644)

    assert result.status == "COMPLETED"
    assert result.exit_code == 0
    assert "accuracy: 0.9" in result.stdout
    assert (out_dir / "stdout.log").read_text(encoding="utf-8") == "written by the container entrypoint\n"


def test_home_tmpfs_is_owned_by_the_sandbox_user():
    """The writable home tmpfs must be owned by the container user, or pip --user cannot write to it."""
    cfg = SandboxConfig(user_id=1234, group_id=5678)
    cmd = DockerSandboxRunner(config=cfg).build_docker_command(
        repo_dir="/tmp/sample_repo", output_dir="/tmp/sample_output", command=["python", "train.py"]
    )
    home_mounts = [arg for arg in cmd if arg.startswith("/workspace/home:")]
    assert len(home_mounts) == 1
    options = home_mounts[0].split(":", 1)[1].split(",")
    assert "uid=1234" in options and "gid=5678" in options
    assert "--user" in cmd and cmd[cmd.index("--user") + 1] == "1234:5678"


def _flag_value(cmd, flag, predicate):
    return [cmd[i + 1] for i, arg in enumerate(cmd[:-1]) if arg == flag and predicate(cmd[i + 1])]


def test_install_phase_command_mounts_packages_ro_and_deps_rw():
    cmd = DockerSandboxRunner().build_docker_command(
        repo_dir="/tmp/repo", output_dir="/tmp/out", command=["true"],
        packages_dir=".", deps_dir="/tmp/deps", deps_writable=True, extra_env={"SANDBOX_PHASE": "install"},
    )
    assert _flag_value(cmd, "-v", lambda v: v.endswith(":/workspace/packages:ro"))
    assert _flag_value(cmd, "-v", lambda v: v.endswith(":/workspace/deps:rw"))
    assert "SANDBOX_PHASE=install" in _flag_value(cmd, "-e", lambda v: v.startswith("SANDBOX_PHASE="))
    assert cmd[cmd.index("--network") + 1] == "none"


def test_run_phase_command_mounts_deps_read_only_without_packages():
    cmd = DockerSandboxRunner().build_docker_command(
        repo_dir="/tmp/repo", output_dir="/tmp/out", command=["python", "train.py"], deps_dir="/tmp/deps",
    )
    assert _flag_value(cmd, "-v", lambda v: v.endswith(":/workspace/deps:ro"))
    assert not _flag_value(cmd, "-v", lambda v: "/workspace/packages" in v)
    pythonpath = _flag_value(cmd, "-e", lambda v: v.startswith("PYTHONPATH="))[0]
    assert "/workspace/deps" in pythonpath.split("=", 1)[1].split(":")


def test_home_tmpfs_stays_noexec():
    cmd = DockerSandboxRunner().build_docker_command(repo_dir="/tmp/repo", output_dir="/tmp/out", command=["true"])
    home = _flag_value(cmd, "--tmpfs", lambda v: v.startswith("/workspace/home:"))[0]
    assert "noexec" in home.split(":", 1)[1].split(",")


def _fake_docker(calls, install_status):
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        env = _flag_value(cmd, "-e", lambda v: True)
        if "SANDBOX_PHASE=install" in env:
            out = next(v for v in _flag_value(cmd, "-v", lambda v: v.endswith(":/workspace/output:rw")))
            host_out = out.rsplit(":/workspace/output:rw", 1)[0]
            Path(host_out, "install_meta.json").write_text(
                json.dumps({"phase": "install", "status": install_status, "exit_code": 0 if install_status == "INSTALLED" else 1})
            )
            return subprocess.CompletedProcess(cmd, 0 if install_status == "INSTALLED" else 1, "", "")
        return subprocess.CompletedProcess(cmd, 0, "ran\n", "")
    return fake_run


@pytest.mark.parametrize("install_status", ["INSTALLED", "FAILED"])
def test_run_with_packages_installs_first_then_runs_with_read_only_deps(tmp_path, monkeypatch, install_status):
    (tmp_path / "eval.py").write_text("print('ok')\n", encoding="utf-8")
    packages = tmp_path / "packages"
    packages.mkdir()
    (packages / "demo-1.0-py3-none-any.whl").write_text("x", encoding="utf-8")
    _docker_available(monkeypatch, True)
    monkeypatch.setattr(runner_module, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    calls = []
    monkeypatch.setattr(runner_module.subprocess, "run", _fake_docker(calls, install_status))

    result = DockerSandboxRunner().run(
        paper_id="two_phase", repo_dir=tmp_path, target_script="eval.py", packages_dir=packages
    )

    assert len(calls) == 2
    install, run = calls
    assert "SANDBOX_PHASE=install" in install
    assert _flag_value(install, "-v", lambda v: v.endswith(":/workspace/deps:rw"))
    assert _flag_value(run, "-v", lambda v: v.endswith(":/workspace/deps:ro"))
    assert not _flag_value(run, "-v", lambda v: "/workspace/packages" in v)
    assert f"SANDBOX_DEPENDENCY_STATUS={install_status}" in run
    assert result.status == "COMPLETED"
