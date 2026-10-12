"""The output directory quota of the run container (#261)."""

import os
import sqlite3
import subprocess
import threading

import pytest

from src.migrations import upgrade
from src.sandbox import runner as runner_module
from src.sandbox.runner import DockerSandboxRunner, SandboxConfig, directory_size
from tests.test_migrations import _baseline_db, _engine


def test_directory_size_adds_up_nested_files_and_ignores_symlinks(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "x.bin").write_bytes(b"1" * 100)
    (tmp_path / "a" / "y.bin").write_bytes(b"2" * 50)
    (tmp_path / "a" / "b" / "z.bin").write_bytes(b"3" * 25)
    try:
        os.symlink(tmp_path / "x.bin", tmp_path / "link.bin")
        os.symlink(tmp_path / "a", tmp_path / "linkdir", target_is_directory=True)
    except (OSError, NotImplementedError):
        pass  # this account may not create symlinks (Windows)
    assert directory_size(tmp_path) == 175


def test_directory_size_of_a_missing_folder_is_zero(tmp_path):
    assert directory_size(tmp_path / "nope") == 0


def test_default_limit_and_validation():
    assert SandboxConfig().output_limit_mb == 1024
    assert SandboxConfig(output_limit_mb=0).output_limit_mb == 0
    with pytest.raises(ValueError, match="output_limit_mb"):
        SandboxConfig(output_limit_mb=-1)


def test_the_container_name_is_only_in_the_command_when_given():
    runner = DockerSandboxRunner(SandboxConfig())
    assert "--name" not in runner.build_docker_command("/r", "/o", ["python", "x.py"])
    cmd = runner.build_docker_command("/r", "/o", ["python", "x.py"], container_name="repro-radar-run-abc")
    assert cmd[cmd.index("--name") + 1] == "repro-radar-run-abc"


@pytest.fixture
def run_with(tmp_path, monkeypatch):
    """Runs the Docker runner with a fake `docker`: `behaviour(cmd, out_dir, killed)` plays the container."""
    (tmp_path / "eval.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *a, **k: True))
    monkeypatch.setattr(runner_module, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(runner_module, "OUTPUT_POLL_SECONDS", 0.02)

    def run(behaviour, limit_mb):
        killed = threading.Event()
        kills = []

        def fake_run(cmd, **kwargs):
            if cmd[:2] == ["docker", "kill"]:
                kills.append(cmd[2])
                killed.set()
                return subprocess.CompletedProcess(cmd, 0, "", "")
            out = tmp_path / "runs" / "quota"
            return behaviour(cmd, out, killed)

        monkeypatch.setattr(runner_module.subprocess, "run", fake_run)
        runner = DockerSandboxRunner(SandboxConfig(output_limit_mb=limit_mb))
        return runner.run(paper_id="quota", repo_dir=tmp_path, target_script="eval.py"), kills
    return run


def test_a_run_that_fills_the_output_directory_is_killed_and_labelled(run_with):
    def container(cmd, out, killed):
        with open(out / "big.bin", "wb") as f:
            f.truncate(3 * 1024 * 1024)  # 3 MiB against a 1 MiB limit
        assert killed.wait(10), "the watcher never killed the container"
        return subprocess.CompletedProcess(cmd, 137, "", "")

    result, kills = run_with(container, limit_mb=1)
    assert result.status == "OUTPUT_LIMIT_EXCEEDED" and result.exit_code == 137
    assert "limit is 1 MiB" in result.error_message and "grew by 3 MiB" in result.error_message
    assert len(kills) == 1 and kills[0].startswith("repro-radar-run-")
    assert result.command_executed[result.command_executed.index("--name") + 1] == kills[0]


def test_files_the_runner_put_there_before_the_run_do_not_count(run_with, tmp_path):
    out = tmp_path / "runs" / "quota"
    out.mkdir(parents=True)
    with open(out / "deps_and_copies.bin", "wb") as f:  # 3 MiB already there when the container starts, limit 1 MiB
        f.truncate(3 * 1024 * 1024)

    def container(cmd, out_dir, killed):
        assert not killed.wait(0.3), "the runner's own files were counted"
        with open(out_dir / "small.bin", "wb") as f:
            f.truncate(100 * 1024)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    result, kills = run_with(container, limit_mb=1)
    assert result.status == "COMPLETED" and kills == []


def test_a_run_under_the_limit_is_left_alone(run_with):
    def container(cmd, out, killed):
        (out / "small.txt").write_text("fine")
        return subprocess.CompletedProcess(cmd, 0, "ok\n", "")

    result, kills = run_with(container, limit_mb=1)
    assert result.status == "COMPLETED" and result.error_message is None and kills == []


def test_limit_zero_switches_the_watcher_off(run_with):
    def container(cmd, out, killed):
        with open(out / "big.bin", "wb") as f:
            f.truncate(3 * 1024 * 1024)
        assert not killed.wait(0.3)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    result, kills = run_with(container, limit_mb=0)
    assert result.status == "COMPLETED" and kills == []


def test_old_runs_table_rejects_the_new_status_until_migration_6(tmp_path):
    path = tmp_path / "old.db"
    _baseline_db(path)
    conn = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO runs (run_id, paper_id, status) VALUES ('r9', 'paper_001', 'OUTPUT_LIMIT_EXCEEDED')")
    conn.close()
    upgrade(_engine(path))
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO runs (run_id, paper_id, status) VALUES ('r9', 'paper_001', 'OUTPUT_LIMIT_EXCEEDED')")
    assert conn.execute("SELECT status FROM runs WHERE run_id = 'r9'").fetchone() == ("OUTPUT_LIMIT_EXCEEDED",)
    conn.close()
