"""Memory limits written as a share of the host's RAM (#311)."""

import pytest

from src.sandbox import resources
from src.sandbox.runner import DockerSandboxRunner, SandboxConfig

GIB = 1024**3


def _host(monkeypatch, host_gib, docker_gib):
    monkeypatch.setattr(resources, "host_memory_bytes", lambda: int(host_gib * GIB))
    monkeypatch.setattr(resources, "docker_memory_bytes", lambda: int(docker_gib * GIB))


def test_a_size_passes_through_unchanged(monkeypatch):
    _host(monkeypatch, 32, 15.5)
    assert resources.resolve_memory_limit("8g") == "8g"
    assert resources.resolve_memory_limit("6144M") == "6144M"


def test_half_of_the_host_when_docker_can_see_enough(monkeypatch):
    _host(monkeypatch, 32, 24)
    assert resources.resolve_memory_limit("50%") == f"{16 * 1024}m"


def test_the_limit_is_capped_below_what_docker_can_see(monkeypatch):
    _host(monkeypatch, 32, 15.5)  # Docker Desktop on WSL2 by default
    assert resources.resolve_memory_limit("50%") == f"{int(15.5 * 1024 * 0.9)}m"


def test_a_percentage_works_when_docker_does_not_answer(monkeypatch):
    _host(monkeypatch, 32, 0)
    assert resources.resolve_memory_limit("25%") == f"{8 * 1024}m"


def test_the_limit_has_a_minimum(monkeypatch):
    _host(monkeypatch, 0.25, 0)
    assert resources.resolve_memory_limit("10%") == f"{resources.MIN_LIMIT_MIB}m"


@pytest.mark.parametrize("bad", ["0%", "101%", "abc%", "-5%"])
def test_a_bad_percentage_is_refused(monkeypatch, bad):
    _host(monkeypatch, 32, 15.5)
    with pytest.raises(ValueError):
        resources.resolve_memory_limit(bad)


def test_an_unreadable_host_memory_is_refused(monkeypatch):
    _host(monkeypatch, 0, 0)
    with pytest.raises(ValueError, match="host's physical memory"):
        resources.resolve_memory_limit("50%")


def test_the_docker_command_carries_the_resolved_size(monkeypatch, tmp_path):
    _host(monkeypatch, 32, 24)
    runner = DockerSandboxRunner(SandboxConfig(memory_limit="50%", memory_swap="50%"))
    cmd = runner.build_docker_command(tmp_path, tmp_path, ["python", "x.py"])
    assert f"--memory={16 * 1024}m" in cmd and f"--memory-swap={16 * 1024}m" in cmd


def test_the_library_default_is_still_a_fixed_size():
    assert SandboxConfig().memory_limit == "8g"


def test_the_host_memory_of_this_machine_is_readable():
    assert resources.host_memory_bytes() > 0
