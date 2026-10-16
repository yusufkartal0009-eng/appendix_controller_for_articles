"""Installed-environment cache (#380): key, digest check, and the skipped install phase."""

import json
import subprocess
from pathlib import Path

import pytest

from src.sandbox import env_cache
from src.sandbox import runner as runner_module
from src.sandbox.runner import DockerSandboxRunner, SandboxConfig


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(env_cache, "image_id", lambda image: "sha256:image-one")
    packages = tmp_path / "packages"
    packages.mkdir()
    (packages / "demo-1.0-py3-none-any.whl").write_bytes(b"wheel one")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("demo==1.0\n", encoding="utf-8")
    return packages, repo


def test_the_key_follows_every_input_that_decides_the_environment(inputs, monkeypatch):
    packages, repo = inputs
    base, details = env_cache.environment_key("img", packages, repo, [])
    assert base == env_cache.environment_key("img", packages, repo, [])[0]  # stable
    assert details["mode"] == "requirement_files" and "demo-1.0-py3-none-any.whl" in details["bundle"]
    assert env_cache.environment_key("img", packages, repo, ["extra"])[0] != base
    (repo / "requirements.txt").write_text("demo==1.1\n", encoding="utf-8")
    assert env_cache.environment_key("img", packages, repo, [])[0] != base
    (repo / "requirements.txt").write_text("demo==1.0\n", encoding="utf-8")
    (packages / "demo-1.0-py3-none-any.whl").write_bytes(b"wheel two")  # same name, other bytes
    assert env_cache.environment_key("img", packages, repo, [])[0] != base
    (packages / "demo-1.0-py3-none-any.whl").write_bytes(b"wheel one")
    monkeypatch.setattr(env_cache, "image_id", lambda image: "sha256:image-two")  # a rebuilt image
    assert env_cache.environment_key("img", packages, repo, [])[0] != base


def test_the_mode_is_all_wheels_without_requirement_files(inputs):
    packages, repo = inputs
    (repo / "requirements.txt").unlink()
    assert env_cache.environment_key("img", packages, repo, [])[1]["mode"] == "all_bundled_wheels"


def test_an_unknown_image_gives_no_key(inputs, monkeypatch):
    packages, repo = inputs
    monkeypatch.setattr(env_cache, "image_id", lambda image: None)
    with pytest.raises(LookupError):
        env_cache.environment_key("img", packages, repo, [])


def _stored(tmp_path, inputs):
    packages, repo = inputs
    key, details = env_cache.environment_key("img", packages, repo, [])
    deps = tmp_path / "deps"
    (deps / "demo").mkdir(parents=True)
    (deps / "demo" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    (out / "install_meta.json").write_text(json.dumps({"status": "INSTALLED", "duration_seconds": 12.5}), encoding="utf-8")
    cache = env_cache.EnvironmentCache(tmp_path / "cache")
    cache.store(key, details, deps, out)
    return cache, key


def test_a_stored_entry_is_found_again(tmp_path, inputs):
    cache, key = _stored(tmp_path, inputs)
    entry, info = cache.lookup(key)
    assert entry is not None and info["reason"] == "hit" and info["files"] == 1
    assert (entry / "deps" / "demo" / "__init__.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert cache.lookup("0" * 64)[0] is None


def test_a_changed_file_makes_the_entry_unusable_and_deletes_it(tmp_path, inputs):
    cache, key = _stored(tmp_path, inputs)
    (cache.entry_dir(key) / "deps" / "demo" / "__init__.py").write_text("VALUE = 2\n", encoding="utf-8")
    entry, info = cache.lookup(key)
    assert entry is None and "does not match" in info["reason"] and not cache.entry_dir(key).exists()


def test_an_added_file_also_makes_the_entry_unusable(tmp_path, inputs):
    cache, key = _stored(tmp_path, inputs)
    (cache.entry_dir(key) / "deps" / "planted.so").write_bytes(b"x")
    assert cache.lookup(key)[0] is None


def _flag(cmd, flag, wanted):
    return [cmd[i + 1] for i, a in enumerate(cmd[:-1]) if a == flag and wanted(cmd[i + 1])]


def _fake_docker(calls, install_status="INSTALLED"):
    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(cmd, 0, "sha256:image-one\n", "")
        calls.append(cmd)
        if any(v == "SANDBOX_PHASE=install" for v in _flag(cmd, "-e", lambda v: True)):
            out = Path(_flag(cmd, "-v", lambda v: v.endswith(":/workspace/output:rw"))[0].rsplit(":/workspace/output:rw", 1)[0])
            deps = Path(_flag(cmd, "-v", lambda v: v.endswith(":/workspace/deps:rw"))[0].rsplit(":/workspace/deps:rw", 1)[0])
            (deps / "demo.py").write_text("x = 1\n", encoding="utf-8")
            (out / "installed_packages.json").write_text('[{"name": "demo", "version": "1.0"}]', encoding="utf-8")
            (out / "install_meta.json").write_text(
                json.dumps({"phase": "install", "status": install_status, "duration_seconds": 30.0, "peak_memory_bytes": 5}),
                encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0 if install_status == "INSTALLED" else 1, "", "")
        return subprocess.CompletedProcess(cmd, 0, "ran\n", "")
    return fake_run


def _run_twice(tmp_path, monkeypatch, status="INSTALLED", times=2):
    (tmp_path / "eval.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("demo==1.0\n", encoding="utf-8")
    packages = tmp_path / "packages"
    packages.mkdir()
    (packages / "demo-1.0-py3-none-any.whl").write_bytes(b"wheel")
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *a, **k: True))
    monkeypatch.setattr(runner_module, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    calls = []
    monkeypatch.setattr(runner_module.subprocess, "run", _fake_docker(calls, status))
    config = SandboxConfig(env_cache_dir=str(tmp_path / "cache"))
    results = []
    for _ in range(times):
        result = DockerSandboxRunner(config).run(paper_id="cached", repo_dir=tmp_path, target_script="eval.py", packages_dir=packages)
        # both runs use the same output directory, so each run's cache record is read before the next run
        result.env_cache = json.loads((result.output_dir / "env_cache.json").read_text(encoding="utf-8"))
        results.append(result)
    return calls, results


def test_the_second_run_skips_the_install_container_and_mounts_the_stored_copy_read_only(tmp_path, monkeypatch):
    calls, results = _run_twice(tmp_path, monkeypatch)
    phases = ["install" if any(v == "SANDBOX_PHASE=install" for v in _flag(c, "-e", lambda v: True)) else "run" for c in calls]
    assert phases == ["install", "run", "run"]  # the second run has no install container
    second = _flag(calls[2], "-v", lambda v: v.endswith(":/workspace/deps:ro"))[0]
    assert "cache" in second  # the stored copy, not a fresh deps directory of this run
    assert "SANDBOX_DEPENDENCY_STATUS=INSTALLED" in calls[2]
    out = results[1].output_dir
    info = json.loads((out / "env_cache.json").read_text(encoding="utf-8"))
    assert info["hit"] is True and info["restore_seconds"] >= 0
    meta = json.loads((out / "install_meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "INSTALLED" and meta["env_cache"] == "hit" and meta["original_duration_seconds"] == 30.0
    assert meta["peak_memory_bytes"] is None  # the original peak is not claimed for a run that did not install
    assert (out / "installed_packages.json").is_file()
    first = results[0].env_cache
    assert first["hit"] is False and first["stored"]["files"] == 1


def test_a_failed_install_is_not_stored(tmp_path, monkeypatch):
    calls, results = _run_twice(tmp_path, monkeypatch, status="FAILED")
    assert sum(1 for c in calls if "SANDBOX_PHASE=install" in _flag(c, "-e", lambda v: True)) == 2
    assert not any((tmp_path / "cache").glob("*/entry.json"))
    assert results[1].env_cache["hit"] is False


def test_without_a_cache_directory_nothing_changes(tmp_path, monkeypatch):
    (tmp_path / "eval.py").write_text("print('ok')\n", encoding="utf-8")
    packages = tmp_path / "packages"
    packages.mkdir()
    (packages / "demo-1.0-py3-none-any.whl").write_bytes(b"wheel")
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *a, **k: True))
    monkeypatch.setattr(runner_module, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    calls = []
    monkeypatch.setattr(runner_module.subprocess, "run", _fake_docker(calls))
    result = DockerSandboxRunner().run(paper_id="plain", repo_dir=tmp_path, target_script="eval.py", packages_dir=packages)
    assert len(calls) == 2 and not (result.output_dir / "env_cache.json").exists()
