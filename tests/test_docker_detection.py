"""Docker detection tolerates a slow daemon but still reports a missing Docker (#164)."""

import subprocess
from types import SimpleNamespace

import pytest

from src.sandbox import runner as runner_module
from src.sandbox.runner import DockerSandboxRunner


@pytest.fixture
def calls(monkeypatch):
    """Record `docker info` calls and the waits between them; the CLI is on PATH unless a test removes it."""
    record = {"run": 0, "sleep": []}
    monkeypatch.setattr(runner_module.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(runner_module.time, "sleep", lambda seconds: record["sleep"].append(seconds))
    return record


def _run_sequence(monkeypatch, calls, outcomes):
    def fake_run(cmd, **kwargs):
        calls["run"] += 1
        outcome = outcomes[calls["run"] - 1]
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        return SimpleNamespace(returncode=outcome)

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)


def test_slow_daemon_is_detected_on_a_later_attempt(monkeypatch, calls):
    _run_sequence(monkeypatch, calls, ["timeout", 1, 0])
    assert DockerSandboxRunner.is_docker_available() is True
    assert calls["run"] == 3 and calls["sleep"] == [2.0, 2.0]


def test_daemon_that_never_answers_is_reported_unavailable(monkeypatch, calls):
    _run_sequence(monkeypatch, calls, ["timeout", "timeout", "timeout"])
    assert DockerSandboxRunner.is_docker_available() is False
    assert calls["run"] == 3 and calls["sleep"] == [2.0, 2.0]  # no wait after the last attempt


def test_missing_docker_cli_fails_at_once(monkeypatch, calls):
    monkeypatch.setattr(runner_module.shutil, "which", lambda name: None)
    _run_sequence(monkeypatch, calls, [])
    assert DockerSandboxRunner.is_docker_available() is False
    assert calls["run"] == 0 and calls["sleep"] == []


def test_each_attempt_uses_the_longer_timeout(monkeypatch, calls):
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(kwargs["timeout"])
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)
    assert DockerSandboxRunner.is_docker_available() is True
    assert seen == [15]
