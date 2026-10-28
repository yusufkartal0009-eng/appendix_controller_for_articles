"""Edge cases of the memory-limit resolver and of the host/Docker memory probes (#557)."""

import subprocess

import pytest

from src.sandbox import resources
from src.sandbox.resources import (
    MIN_LIMIT_MIB,
    docker_memory_bytes,
    host_memory_bytes,
    resolve_memory_limit,
)

GIB = 1024**3


@pytest.fixture()
def machine(monkeypatch):
    """A host with 32 GiB whose Docker sees 16 GiB."""
    monkeypatch.setattr(resources, "host_memory_bytes", lambda: 32 * GIB)
    monkeypatch.setattr(resources, "docker_memory_bytes", lambda: 16 * GIB)


@pytest.mark.parametrize("size", ["8g", "512m", " 8g ", "0", "", "abc", "50", "1e3"])
def test_a_size_passes_through_unchanged_apart_from_whitespace(size):
    assert resolve_memory_limit(size) == size.strip()


def test_a_share_is_capped_at_ninety_percent_of_what_docker_sees(machine):
    assert resolve_memory_limit("100%") == f"{int(16 * GIB * 0.9 // (1024 * 1024))}m"
    assert resolve_memory_limit("50%") == "14745m"  # 16 GiB of the 32 is above 90 % of Docker's 16 GiB
    assert resolve_memory_limit("25%") == "8192m"  # 8 GiB is below the cap


def test_exactly_the_cap_share_is_not_cut(machine):
    assert resolve_memory_limit("45%") == f"{int(32 * GIB * 0.45 // (1024 * 1024))}m"


def test_the_lowest_and_highest_allowed_share(machine):
    assert resolve_memory_limit("1%") == f"{max(int(32 * GIB * 0.01 // (1024 * 1024)), MIN_LIMIT_MIB)}m"
    assert resolve_memory_limit("100%").endswith("m")


def test_a_tiny_host_gets_the_floor(monkeypatch):
    monkeypatch.setattr(resources, "host_memory_bytes", lambda: GIB // 4)
    monkeypatch.setattr(resources, "docker_memory_bytes", lambda: 0)
    assert resolve_memory_limit("50%") == f"{MIN_LIMIT_MIB}m"


def test_without_docker_the_share_of_the_host_is_used(monkeypatch):
    monkeypatch.setattr(resources, "host_memory_bytes", lambda: 8 * GIB)
    monkeypatch.setattr(resources, "docker_memory_bytes", lambda: 0)
    assert resolve_memory_limit("50%") == "4096m"


@pytest.mark.parametrize("value", ["0%", "-5%", "0.5%", "100.01%", "101%", "1000%", "nan%", "inf%", "-inf%", "%", "abc%", "5 0%"])
def test_a_share_outside_one_to_a_hundred_or_not_a_number_is_refused(machine, value):
    with pytest.raises(ValueError):
        resolve_memory_limit(value)


@pytest.mark.parametrize("value", ["1%", "100%", "50.5%", " 50% ", "5e1%"])
def test_shares_inside_the_range_resolve(machine, value):
    assert resolve_memory_limit(value).endswith("m")


def test_an_unreadable_host_memory_is_refused_with_a_clear_message(monkeypatch):
    monkeypatch.setattr(resources, "host_memory_bytes", lambda: 0)
    with pytest.raises(ValueError, match="cannot read the host's physical memory"):
        resolve_memory_limit("50%")


def test_a_non_string_size_is_turned_into_text():
    assert resolve_memory_limit(8) == "8"


def test_host_memory_is_never_negative_and_is_an_int():
    value = host_memory_bytes()
    assert isinstance(value, int) and value >= 0


def test_docker_memory_is_zero_when_docker_is_missing_fails_or_prints_nonsense(monkeypatch):
    def fake(stdout="", returncode=0, error=None):
        def run(*args, **kwargs):
            if error:
                raise error
            return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")
        return run

    monkeypatch.setattr(subprocess, "run", fake(error=FileNotFoundError()))
    assert docker_memory_bytes() == 0
    monkeypatch.setattr(subprocess, "run", fake(error=subprocess.TimeoutExpired("docker", 30)))
    assert docker_memory_bytes() == 0
    monkeypatch.setattr(subprocess, "run", fake(stdout="Cannot connect", returncode=1))
    assert docker_memory_bytes() == 0
    monkeypatch.setattr(subprocess, "run", fake(stdout="not a number\n"))
    assert docker_memory_bytes() == 0
    monkeypatch.setattr(subprocess, "run", fake(stdout="16777216000\n"))
    assert docker_memory_bytes() == 16777216000


def test_host_memory_on_macos_reads_sysctl_and_on_a_bad_answer_is_zero(monkeypatch):
    monkeypatch.setattr(resources.sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="17179869184\n", stderr=""))
    assert host_memory_bytes() == 17179869184
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="garbage", stderr=""))
    assert host_memory_bytes() == 0


def test_host_memory_on_linux_reads_meminfo_and_a_missing_line_or_file_is_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(resources.sys, "platform", "linux")
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemFree: 1 kB\nMemTotal:       16384 kB\n", encoding="utf-8")
    monkeypatch.setattr(resources, "Path", lambda _: meminfo)
    assert host_memory_bytes() == 16384 * 1024
    meminfo.write_text("MemFree: 1 kB\n", encoding="utf-8")
    assert host_memory_bytes() == 0
    monkeypatch.setattr(resources, "Path", lambda _: tmp_path / "absent")
    assert host_memory_bytes() == 0
