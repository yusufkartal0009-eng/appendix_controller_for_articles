"""Edges of src/sandbox/stager.py that need neither Docker nor a network: git failures, pip failures, build, report (#272)."""

import json
import subprocess
from types import SimpleNamespace

import pytest

import src.sandbox.stager as stager_module
from src.sandbox.runner import SandboxConfig, SandboxExecutionResult
from src.sandbox.stager import DependencyManifest, RepoStager, StagedRepo


@pytest.fixture
def stager(tmp_path):
    return RepoStager(staging_root=tmp_path / "staging")


def _staged(tmp_path, **manifest):
    path = tmp_path / "staging" / "p"
    path.mkdir(parents=True, exist_ok=True)
    return StagedRepo(paper_id="p", source="local", staged_path=path, commit_hash="unknown",
                      manifest=DependencyManifest(**manifest))


class FakeRun:
    """Stands in for subprocess.run: records the commands and answers from a script of outcomes."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.commands = []

    def __call__(self, cmd, **kwargs):
        self.commands.append(cmd)
        outcome = self.outcomes.pop(0) if self.outcomes else SimpleNamespace(returncode=0, stdout="", stderr="")
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _ok(stdout=""):
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def test_a_missing_local_source_is_reported(stager, tmp_path):
    with pytest.raises(FileNotFoundError, match="Local source directory not found"):
        stager.stage_repository("p", str(tmp_path / "nowhere"))


def test_local_directory_without_git_has_an_unknown_commit(stager, tmp_path, monkeypatch):
    source = tmp_path / "src_repo"
    (source / "sub").mkdir(parents=True)
    (source / "main.py").write_text("print(1)", encoding="utf-8")
    (source / "sub" / "a.txt").write_text("a", encoding="utf-8")
    monkeypatch.setattr(stager_module.subprocess, "run", FakeRun([SimpleNamespace(returncode=128, stdout="", stderr="")]))
    staged = stager.stage_repository("p", str(source))
    assert staged.commit_hash == "unknown" and staged.candidate_scripts == ["main.py"]
    assert (staged.staged_path / "sub" / "a.txt").read_text(encoding="utf-8") == "a"


def test_local_git_commit_is_recorded_and_a_failing_git_is_survived(stager, tmp_path, monkeypatch):
    source = tmp_path / "src_repo"
    source.mkdir()
    monkeypatch.setattr(stager_module.subprocess, "run", FakeRun([_ok("abc123\n")]))
    assert stager.stage_repository("p", str(source)).commit_hash == "abc123"
    monkeypatch.setattr(stager_module.subprocess, "run", FakeRun([OSError("no git")]))
    assert stager.stage_repository("p", str(source)).commit_hash == "unknown"


def test_clone_checkout_and_head_lookup(stager, monkeypatch):
    fake = FakeRun([_ok(), _ok(), _ok("deadbeef\n")])
    monkeypatch.setattr(stager_module.subprocess, "run", fake)
    staged = stager.stage_repository("p", "https://example.org/o/r.git", commit_or_tag="v1")
    assert staged.commit_hash == "deadbeef"
    assert fake.commands[0][:2] == ["git", "clone"] and "--depth" not in fake.commands[0]
    assert fake.commands[1] == ["git", "checkout", "v1"]


def test_a_shallow_clone_without_a_commit_and_an_unreadable_head(stager, monkeypatch):
    fake = FakeRun([_ok(), OSError("no git")])
    monkeypatch.setattr(stager_module.subprocess, "run", fake)
    staged = stager.stage_repository("p", "https://example.org/o/r.git")
    assert "--depth" in fake.commands[0] and staged.commit_hash == "unknown"


def test_clone_and_checkout_failures_are_named(stager, monkeypatch):
    monkeypatch.setattr(stager_module.subprocess, "run", FakeRun([subprocess.CalledProcessError(128, "git")]))
    with pytest.raises(RuntimeError, match="Failed to clone repository"):
        stager.stage_repository("p", "https://example.org/o/r.git")
    monkeypatch.setattr(stager_module.subprocess, "run", FakeRun([_ok(), subprocess.CalledProcessError(1, "git")]))
    with pytest.raises(RuntimeError, match="Failed to checkout commit/tag 'nope'"):
        stager.stage_repository("p", "https://example.org/o/r.git", commit_or_tag="nope")


def test_an_unreadable_requirements_file_gives_no_dependencies(stager, tmp_path):
    assert stager._parse_requirements_file(tmp_path / "missing.txt") == []


def test_bundling_without_requirements_is_skipped(stager, tmp_path):
    report = stager.bundle_dependencies(_staged(tmp_path))
    assert report["status"] == "SKIPPED" and report["wheel_count"] == 0


def test_bundling_reports_a_pip_that_cannot_run(stager, tmp_path, monkeypatch):
    staged = _staged(tmp_path, requirements_files=["requirements.txt"])
    (staged.staged_path / "requirements.txt").write_text("numpy\n", encoding="utf-8")
    monkeypatch.setattr(stager, "_run_pip", lambda cmd, timeout: (_ for _ in ()).throw(OSError("pip missing")))
    report = stager.bundle_dependencies(staged)
    assert report["status"] == "FAILED" and "pip missing" in report["message"]


def test_conda_requirements_that_cannot_be_downloaded_are_listed_as_conda_only(stager, tmp_path, monkeypatch):
    staged = _staged(tmp_path, conda_env_files=["environment.yml"], has_conda_env=True)
    (staged.staged_path / "environment.yml").write_text(
        "name: e\ndependencies:\n  - python=3.8\n  - pip:\n    - toolz==0.12.1\n", encoding="utf-8")
    monkeypatch.setattr(stager, "_run_pip", lambda cmd, timeout: (_ for _ in ()).throw(OSError("offline")))
    report = stager.bundle_dependencies(staged)
    assert report["conda_only"] and report["conda_only"][0]["reason"] == "offline"


def test_extra_requirements_failures_make_the_bundle_partial(stager, tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    staged = _staged(tmp_path)
    assert stager._with_extras({"status": "SUCCESS"}, staged, bundle, 10, "3.8", [], None) == {
        "status": "SUCCESS", "extra_requirements": []}
    monkeypatch.setattr(stager, "_run_pip", lambda cmd, timeout: SimpleNamespace(returncode=1, stdout="", stderr="x\nlast line"))
    failed = stager._with_extras({"status": "SUCCESS"}, staged, bundle, 10, "3.8", [], ["fastsk"])
    assert failed["status"] == "PARTIAL" and failed["extra_requirements_error"] == "last line"
    monkeypatch.setattr(stager, "_run_pip", lambda cmd, timeout: SimpleNamespace(returncode=2, stdout="", stderr=""))
    assert stager._with_extras({"status": "SUCCESS"}, staged, bundle, 10, "3.8", [], ["x"])["extra_requirements_error"] == "pip exited 2"
    monkeypatch.setattr(stager, "_run_pip", lambda cmd, timeout: (_ for _ in ()).throw(OSError("offline")))
    assert stager._with_extras({"status": "SUCCESS"}, staged, bundle, 10, "3.8", [], ["x"])["extra_requirements_error"] == "offline"


def test_an_sdist_probe_that_cannot_run_is_flagged_for_the_build_phase(stager, tmp_path, monkeypatch):
    req = tmp_path / "requirements.txt"
    req.write_text("fastsk==1.0\n", encoding="utf-8")
    monkeypatch.setattr(stager, "_run_pip", lambda cmd, timeout: (_ for _ in ()).throw(OSError("offline")))
    flagged = stager._find_requirements_without_wheels([req], tmp_path / "bundle", 10)
    assert flagged == [{"requirement": "fastsk==1.0", "status": "NEEDS_SDIST_BUILD", "reason": "offline"}]


def test_pip_runs_in_the_sandbox_image_when_asked(tmp_path, monkeypatch):
    stager = RepoStager(staging_root=tmp_path / "staging", bundle_in_docker=True)
    fake = FakeRun([_ok()])
    monkeypatch.setattr(stager_module.subprocess, "run", fake)
    host = stager._pip_download_command(tmp_path / "staging" / "b", "3.11") + ["toolz"]
    stager._run_pip(host, 10)
    assert fake.commands[0][:3] == ["docker", "run", "--rm"] and fake.commands[0][-1] == "toolz"


def test_build_from_source_downloads_sdists_builds_and_keeps_the_wheels(stager, tmp_path, monkeypatch):
    staged = _staged(tmp_path)
    wheel = tmp_path / "toy-1.0-py3-none-any.whl"
    wheel.write_bytes(b"w")
    sdist = tmp_path / "toy-1.0.tar.gz"
    calls = {}
    monkeypatch.setattr(stager_module, "download_sdist", lambda req, dest: calls.setdefault("sdist", req) and sdist)
    monkeypatch.setattr(stager, "_run_pip", lambda cmd, timeout: SimpleNamespace(returncode=0, stdout="", stderr=""))

    class FakeRunner:
        def __init__(self, config):
            pass

        def build_wheels(self, paper_id, repo, inputs, targets, build_requirements, from_repo):
            calls["targets"] = targets
            calls["from_repo"] = from_repo
            return {"status": "SUCCESS", "wheels": [str(wheel)]}

    monkeypatch.setattr(stager_module, "DockerSandboxRunner", FakeRunner)
    result = stager.build_from_source(staged, {"sdists": ["toy==1.0"], "build_requirements": ["setuptools"],
                                               "from_repo": True}, SandboxConfig())
    assert calls["targets"] == ["/workspace/packages/toy-1.0.tar.gz", "/workspace/repo"] and calls["from_repo"] is True
    assert result["sdists"] == ["toy-1.0.tar.gz"] and [p.name for p in staged.built_dir.iterdir()] == [wheel.name]
    # running it again replaces the earlier wheels instead of adding to them
    stager.build_from_source(staged, {"sdists": ["toy==1.0"]}, SandboxConfig())
    assert [p.name for p in staged.built_dir.iterdir()] == [wheel.name]


def test_build_requirements_that_cannot_be_downloaded_stop_the_build(stager, tmp_path, monkeypatch):
    monkeypatch.setattr(stager, "_run_pip", lambda cmd, timeout: SimpleNamespace(returncode=1, stdout="", stderr="no wheel"))
    result = stager.build_from_source(_staged(tmp_path), {"from_repo": True, "build_requirements": ["setuptools"]},
                                      SandboxConfig())
    assert result == {"status": "FAILED", "stage": "download build requirements", "error": "no wheel"}


def _fake_runner(monkeypatch, tmp_path, meta_text=None):
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    if meta_text is not None:
        (out / "execution_meta.json").write_text(meta_text, encoding="utf-8")
    result = SandboxExecutionResult(status="COMPLETED", exit_code=0, stdout="s", stderr="", duration_seconds=1.0,
                                    command_executed=[], docker_used=True, output_dir=out, isolated=True)

    class FakeRunner:
        def __init__(self, config):
            pass

        def run(self, **kwargs):
            return result

    monkeypatch.setattr(stager_module, "DockerSandboxRunner", FakeRunner)
    return out


def test_executing_needs_a_script_and_picks_the_first_candidate(stager, tmp_path, monkeypatch):
    staged = _staged(tmp_path)
    with pytest.raises(ValueError, match="No executable script"):
        stager.execute_staged(staged)
    staged.candidate_scripts = ["main.py"]
    out = _fake_runner(monkeypatch, tmp_path)
    report = stager.execute_staged(staged)
    assert report["target_script"] == "main.py" and report["status"] == "COMPLETED"
    assert json.loads((out / "run_report.json").read_text(encoding="utf-8"))["paper_id"] == "p"


def test_unreadable_run_metadata_is_recorded_not_fatal(stager, tmp_path, monkeypatch):
    staged = _staged(tmp_path)
    _fake_runner(monkeypatch, tmp_path, meta_text="{not json")
    report = stager.execute_staged(staged, target_script="a.py")
    assert "Unreadable execution_meta.json" in report["meta_error"] and report["dependency_install_status"] == "UNKNOWN"


def test_metric_extraction_and_report_write_errors_do_not_stop_the_run(stager, tmp_path, monkeypatch):
    staged = _staged(tmp_path)
    out = _fake_runner(monkeypatch, tmp_path)
    monkeypatch.setattr(stager_module.MetricExtractor, "extract_from_run_dir",
                        lambda self, path: (_ for _ in ()).throw(RuntimeError("bad log")))
    (out / "run_report.json").mkdir()  # a directory in the way: writing the report fails
    report = stager.execute_staged(staged, target_script="a.py")
    assert report["metrics_extraction_error"] == "bad log" and "run_report_path" not in report


def test_metrics_found_in_the_output_are_added_to_the_report(stager, tmp_path, monkeypatch):
    staged = _staged(tmp_path)
    _fake_runner(monkeypatch, tmp_path)
    monkeypatch.setattr(stager_module.MetricExtractor, "extract_from_run_dir", lambda self, path: {"accuracy": 0.9})
    assert stager.execute_staged(staged, target_script="a.py")["metrics"] == {"accuracy": 0.9}


def test_gpu_summary_reports_request_devices_and_memory_use():
    assert stager_module.gpu_summary("", {})["requested"] is None
    summary = stager_module.gpu_summary("all", {"gpu_devices": [{"memory_used_before_mib": 100}], "gpu_peak_memory_used_mib": 500})
    assert summary["available"] is True and summary["used"] is True
    assert stager_module.gpu_summary("all", {"gpu_devices": [{"memory_used_before_mib": 100}],
                                             "gpu_peak_memory_used_mib": 100})["used"] is False


def test_remove_tree_clears_read_only_files(tmp_path):
    target = tmp_path / "t"
    target.mkdir()
    locked = target / "locked.txt"
    locked.write_text("x", encoding="utf-8")
    locked.chmod(0o444)
    stager_module.remove_tree(target)
    assert not target.exists()


def test_extra_requirements_are_bundled_when_the_repository_has_no_requirements_file(stager, tmp_path, monkeypatch):
    """#372: the Pilot 4 correction round of a repository without requirements was silently skipped."""
    commands = []

    def fake_pip(cmd, timeout):
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(stager, "_run_pip", fake_pip)
    report = stager.bundle_dependencies(_staged(tmp_path), extra_requirements=["torch", "numpy"])
    assert report["status"] == "SUCCESS" and report["source"] == "extra_requirements"
    assert report["extra_requirements"] == ["torch", "numpy"] and commands[0][-2:] == ["torch", "numpy"]
    assert "-r" not in commands[0]


def test_failing_extra_requirements_without_a_requirements_file_make_the_bundle_partial(stager, tmp_path, monkeypatch):
    monkeypatch.setattr(stager, "_run_pip", lambda cmd, timeout: subprocess.CompletedProcess(cmd, 1, "", "ERROR: no match"))
    report = stager.bundle_dependencies(_staged(tmp_path), extra_requirements=["nonexistent-package"])
    assert report["status"] == "PARTIAL" and report["extra_requirements_error"] == "ERROR: no match"


def test_no_requirements_and_no_extras_is_still_skipped(stager, tmp_path):
    assert stager.bundle_dependencies(_staged(tmp_path), extra_requirements=[])["status"] == "SKIPPED"
