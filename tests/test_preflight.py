import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import preflight


def done(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


INFO = '{"ServerVersion": "29.8.2", "NCPU": 12, "MemTotal": 16620765184, "OperatingSystem": "Docker Desktop"}'


def test_a_running_docker_passes_and_is_not_started():
    started = []
    check, info = preflight.check_docker(run=lambda cmd, t: done(INFO), popen=lambda *a, **k: started.append(a))
    assert check.status == "PASS" and info["NCPU"] == 12 and not started


def test_docker_that_does_not_answer_is_started_and_awaited(tmp_path):
    exe = tmp_path / "Docker Desktop.exe"
    exe.write_text("x")
    answers = iter([done("", 1), done("", 1), done(INFO)])
    started = []
    check, info = preflight.check_docker(run=lambda cmd, t: next(answers), exe=exe, sleep=lambda s: None,
                                         popen=lambda *a, **k: started.append(a))
    assert check.status == "PASS" and "was started" in check.detail and len(started) == 1 and info


def test_docker_that_never_answers_fails_after_the_wait(tmp_path):
    exe = tmp_path / "Docker Desktop.exe"
    exe.write_text("x")
    check, info = preflight.check_docker(run=lambda cmd, t: done("", 1), exe=exe, wait=10, sleep=lambda s: None,
                                         popen=lambda *a, **k: None)
    assert check.status == "FAIL" and info is None and "within 10 s" in check.detail


def test_docker_is_not_started_when_not_asked_or_when_the_program_is_missing(tmp_path):
    assert preflight.check_docker(run=lambda c, t: done("", 1), start=False)[0].status == "FAIL"
    missing = preflight.check_docker(run=lambda c, t: done("", 1), exe=tmp_path / "none.exe")[0]
    assert missing.status == "FAIL" and "cannot be started" in missing.detail


@pytest.mark.parametrize(("free_gib", "status"), [(5, "FAIL"), (20, "WARN"), (100, "PASS")])
def test_disk_thresholds(free_gib, status):
    usage = lambda path: SimpleNamespace(free=free_gib * preflight.GIB)
    assert preflight.check_disk(Path("."), usage=usage).status == status


@pytest.mark.parametrize(("free_gib", "status"), [(1, "FAIL"), (4, "WARN"), (12, "PASS"), (0, "WARN")])
def test_memory_thresholds(free_gib, status):
    assert preflight.check_memory(available=lambda: int(free_gib * preflight.GIB)).status == status


def test_sleep_setting_is_read_from_the_power_plan():
    text = "Current AC Power Setting Index: 0x00000000\n    Current DC Power Setting Index: 0x00000258\n"
    assert preflight.parse_sleep_seconds(text) == {"ac": 0, "dc": 600}
    assert preflight.check_sleep(run=lambda c, t: done(text), system="win32").status == "PASS"
    sleeping = "Current AC Power Setting Index: 0x00000708"
    warn = preflight.check_sleep(run=lambda c, t: done(sleeping), system="win32")
    assert warn.status == "WARN" and "30 min" in warn.detail
    assert preflight.check_sleep(run=lambda c, t: done("garbage"), system="win32").status == "WARN"
    assert preflight.check_sleep(system="linux").status == "WARN"


def test_docker_resources_need_two_cpus_and_enough_memory():
    ok = {"NCPU": 8, "MemTotal": 8 * preflight.GIB}
    assert preflight.check_docker_resources(ok).status == "PASS"
    assert preflight.check_docker_resources({"NCPU": 1, "MemTotal": 8 * preflight.GIB}).status == "FAIL"
    assert preflight.check_docker_resources({"NCPU": 8, "MemTotal": 2 * preflight.GIB}).status == "FAIL"
    assert preflight.check_docker_resources(None).status == "FAIL"


def test_hello_world_runs_the_sandbox_image_with_the_sandbox_isolation():
    seen = []

    def run(cmd, timeout):
        seen.append(cmd)
        return done("preflight hello-world\n")

    assert preflight.check_hello_world(run=run, image="img:1").status == "PASS"
    cmd = seen[0]
    assert "--network" in cmd and cmd[cmd.index("--network") + 1] == "none" and "--read-only" in cmd and "img:1" in cmd
    assert preflight.check_hello_world(run=lambda c, t: done("", 125, "no such image")).status == "FAIL"

    def hang(cmd, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    assert preflight.check_hello_world(run=hang).status == "FAIL"


def test_ensure_ready_raises_on_a_failed_check_and_can_be_skipped(monkeypatch, capsys):
    monkeypatch.delenv(preflight.SKIP_VARIABLE, raising=False)
    monkeypatch.setattr(preflight, "run_checks", lambda start: [preflight.Check("docker", "FAIL", "down"),
                                                                 preflight.Check("disk", "PASS", "ok")])
    with pytest.raises(RuntimeError, match="docker: down"):
        preflight.ensure_ready()
    monkeypatch.setattr(preflight, "run_checks", lambda start: [preflight.Check("sleep", "WARN", "sleeps")])
    assert preflight.ensure_ready()[0].status == "WARN"  # a warning is printed, the run goes on
    assert "[WARN]" in capsys.readouterr().err
    monkeypatch.setenv(preflight.SKIP_VARIABLE, "1")
    assert preflight.ensure_ready() == []
    assert "skipped" in capsys.readouterr().err


def test_main_exit_code_follows_the_checks(monkeypatch, capsys):
    monkeypatch.setattr(preflight, "run_checks", lambda start_docker: [preflight.Check("docker", "FAIL", "down")])
    assert preflight.main(["--json", "--no-start"]) == 1
    assert '"status": "FAIL"' in capsys.readouterr().out
    monkeypatch.setattr(preflight, "run_checks", lambda start_docker: [preflight.Check("docker", "PASS", "up")])
    assert preflight.main([]) == 0


def test_a_missing_sandbox_image_fails_with_the_build_command():
    asked = []

    def run(cmd, timeout):
        asked.append(cmd)
        return done("", 1, "Error: No such image: repro-radar-sandbox:latest")

    check = preflight.check_image(run=run, image="repro-radar-sandbox:latest")
    assert check.status == "FAIL"
    assert "docker build -f docker/Dockerfile.sandbox -t repro-radar-sandbox:latest ." in check.detail
    assert asked == [["docker", "image", "inspect", "repro-radar-sandbox:latest"]]


def test_an_existing_sandbox_image_passes():
    assert preflight.check_image(run=lambda c, t: done("[{}]"), image="img:1").status == "PASS"


def test_run_checks_skips_the_container_when_the_image_is_missing(monkeypatch):
    monkeypatch.setattr(preflight, "check_docker", lambda start=True: (preflight.Check("docker", "PASS", "ok"), {"NCPU": 4, "MemTotal": 16 * 2**30}))
    monkeypatch.setattr(preflight, "check_image", lambda: preflight.Check("image", "FAIL", "not built"))
    monkeypatch.setattr(preflight, "check_hello_world", lambda: pytest.fail("no container may be started without the image"))
    names = [c.name for c in preflight.run_checks()]
    assert "image" in names and "hello_world" not in names

