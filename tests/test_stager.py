"""Unit tests for RepoStager, dependency analysis, and staging CLI automation."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import stage_and_bundle_repo
from scripts.stage_and_bundle_repo import sanitize_paper_id
from src.sandbox.runner import (
    DockerSandboxRunner,
    SandboxConfig,
    SandboxExecutionResult,
    SandboxUnavailableError,
)
from src.sandbox.stager import RepoStager


def test_sanitize_paper_id():
    assert sanitize_paper_id("https://github.com/org/ieee-paper-repo.git") == "ieee-paper-repo"
    assert sanitize_paper_id("https://github.com/org/repo-with-slashes/") == "repo-with-slashes"
    assert sanitize_paper_id("/path/to/my_research_project") == "my_research_project"
    assert sanitize_paper_id("special@chars#project!") == "special_chars_project_"


def test_analyze_dependencies(tmp_path):
    stager = RepoStager(staging_root=tmp_path / "staging")
    repo_dir = tmp_path / "sample_repo"
    repo_dir.mkdir()

    # Create dummy requirements file
    req_file = repo_dir / "requirements.txt"
    req_file.write_text(
        "# Core dependencies\n"
        "numpy>=1.24.0\n"
        "scipy==1.10.1\n"
        "torch>=2.0.0; sys_platform == 'linux'\n"
        "scikit-learn\n"
        "# Commented line\n"
        "pandas # inline comment\n",
        encoding="utf-8",
    )

    (repo_dir / "pyproject.toml").write_text("[tool.pytest]\n", encoding="utf-8")
    (repo_dir / "setup.py").write_text("# setup\n", encoding="utf-8")

    manifest = stager.analyze_dependencies(repo_dir)

    assert "requirements.txt" in manifest.requirements_files
    assert manifest.has_pyproject is True
    assert manifest.has_setup_py is True
    assert manifest.has_conda_env is False
    assert "numpy" in manifest.parsed_dependencies
    assert "scipy" in manifest.parsed_dependencies
    assert "torch" in manifest.parsed_dependencies
    assert "scikit-learn" in manifest.parsed_dependencies
    assert "pandas" in manifest.parsed_dependencies


def test_detect_candidate_scripts(tmp_path):
    stager = RepoStager(staging_root=tmp_path / "staging")
    repo_dir = tmp_path / "sample_repo"
    repo_dir.mkdir()

    # Create several candidate files
    (repo_dir / "random_file.txt").write_text("hello", encoding="utf-8")
    (repo_dir / "evaluate.py").write_text("print(1)", encoding="utf-8")
    (repo_dir / "reproduce.py").write_text("print(2)", encoding="utf-8")

    candidates = stager.detect_candidate_scripts(repo_dir)
    assert "reproduce.py" in candidates
    assert "evaluate.py" in candidates

    # When only arbitrary script exists
    repo_dir2 = tmp_path / "sample_repo2"
    repo_dir2.mkdir()
    (repo_dir2 / "custom_task.py").write_text("print('task')", encoding="utf-8")

    candidates2 = stager.detect_candidate_scripts(repo_dir2)
    assert candidates2 == ["custom_task.py"]


def test_stage_local_repository(tmp_path):
    staging_root = tmp_path / "staging"
    stager = RepoStager(staging_root=staging_root)

    source_dir = tmp_path / "source_repo"
    source_dir.mkdir()
    (source_dir / "reproduce.py").write_text("print('reproduce step')", encoding="utf-8")
    (source_dir / "requirements.txt").write_text("numpy\n", encoding="utf-8")

    staged = stager.stage_repository(
        paper_id="paper_101",
        source=str(source_dir),
    )

    assert staged.paper_id == "paper_101"
    assert staged.staged_path.exists()
    assert (staged.staged_path / "reproduce.py").exists()
    assert "reproduce.py" in staged.candidate_scripts
    assert "numpy" in staged.manifest.parsed_dependencies


def test_execute_staged_produces_report_and_metrics(tmp_path, monkeypatch):
    # Exercise the opted-in local process runner even on hosts where Docker is available (e.g. CI).
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *args, **kwargs: False))
    staging_root = tmp_path / "staging"
    stager = RepoStager(staging_root=staging_root)

    source_dir = tmp_path / "source_repo"
    source_dir.mkdir()

    # Script writes a metric file to current or output
    script_content = (
        "import json, os\n"
        "print('Executing paper reproduction...')\n"
        "out_dir = os.environ.get('SANDBOX_OUTPUT_DIR', '.')\n"
        "os.makedirs(out_dir, exist_ok=True)\n"
        "with open(os.path.join(out_dir, 'metrics.json'), 'w') as f:\n"
        "    json.dump({'accuracy': 0.942, 'f1': 0.938}, f)\n"
    )
    (source_dir / "reproduce.py").write_text(script_content, encoding="utf-8")

    staged = stager.stage_repository(
        paper_id="paper_metric_test",
        source=str(source_dir),
    )

    report = stager.execute_staged(
        staged, target_script="reproduce.py", config=SandboxConfig(allow_unsafe_local=True)
    )

    assert report["paper_id"] == "paper_metric_test"
    assert report["isolated"] is False
    assert json.loads(Path(report["run_report_path"]).read_text(encoding="utf-8"))["isolated"] is False
    assert report["status"] == "COMPLETED"
    assert report["exit_code"] == 0
    assert "reproduce.py" in report["target_script"]
    assert "metrics.json" in report["generated_files"]
    assert "metrics" in report
    assert report["metrics"]["accuracy"] == 0.942
    assert report["metrics"]["f1"] == 0.938
    assert Path(report["run_report_path"]).exists()


def test_execute_staged_reports_unreadable_execution_meta(tmp_path, caplog):
    """A corrupt execution_meta.json is surfaced in the report and logged, not swallowed."""
    stager = RepoStager(staging_root=tmp_path / "staging")
    source_dir = tmp_path / "source_repo"
    source_dir.mkdir()
    (source_dir / "reproduce.py").write_text("print('ok')", encoding="utf-8")
    staged = stager.stage_repository(paper_id="paper_meta_test", source=str(source_dir))

    output_dir = tmp_path / "run_output"
    output_dir.mkdir()
    (output_dir / "execution_meta.json").write_text("{truncated", encoding="utf-8")
    fake_result = SandboxExecutionResult(
        status="COMPLETED",
        exit_code=0,
        stdout="",
        stderr="",
        duration_seconds=0.1,
        command_executed=["python", "reproduce.py"],
        docker_used=True,
        output_dir=output_dir,
    )

    with (
        patch("src.sandbox.stager.DockerSandboxRunner.run", return_value=fake_result),
        caplog.at_level("WARNING", logger="src.sandbox.stager"),
    ):
        report = stager.execute_staged(staged, target_script="reproduce.py")

    assert report["meta"] == {}
    assert "execution_meta.json" in report["meta_error"]
    assert any("execution_meta.json" in r.getMessage() for r in caplog.records)

def test_execute_staged_refuses_without_docker_by_default(tmp_path, monkeypatch):
    """Without Docker and without opt-in, staging does not execute the paper code."""
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *args, **kwargs: False))
    stager = RepoStager(staging_root=tmp_path / "staging")
    source_dir = tmp_path / "source_repo"
    source_dir.mkdir()
    marker = tmp_path / "executed.marker"
    (source_dir / "reproduce.py").write_text(f"open(r'{marker}', 'w').write('ran')\n", encoding="utf-8")
    staged = stager.stage_repository(paper_id="paper_refuse_test", source=str(source_dir))

    with pytest.raises(SandboxUnavailableError):
        stager.execute_staged(staged, target_script="reproduce.py")

    assert not marker.exists()


def _run_cli(monkeypatch, argv):
    monkeypatch.setattr(stage_and_bundle_repo.sys, "argv", ["stage_and_bundle_repo.py", *argv])
    return stage_and_bundle_repo.main()


def test_cli_without_docker_exits_with_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *args, **kwargs: False))
    source_dir = tmp_path / "source_repo"
    source_dir.mkdir()
    (source_dir / "reproduce.py").write_text("print('ran')\n", encoding="utf-8")

    code = _run_cli(monkeypatch, [str(source_dir), "--paper-id", "cli_no_docker", "--staging-dir", str(tmp_path / "s")])

    assert code == stage_and_bundle_repo.EXIT_SANDBOX_UNAVAILABLE
    assert "--allow-unsafe-local" in capsys.readouterr().err


def test_cli_unsafe_local_flag_runs_and_warns(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *args, **kwargs: False))
    source_dir = tmp_path / "source_repo"
    source_dir.mkdir()
    (source_dir / "reproduce.py").write_text("print('ran')\n", encoding="utf-8")
    out_json = tmp_path / "report.json"

    code = _run_cli(
        monkeypatch,
        [str(source_dir), "--paper-id", "cli_unsafe", "--staging-dir", str(tmp_path / "s"),
         "--allow-unsafe-local", "--output-json", str(out_json)],
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "NOT ISOLATED" in captured.err
    assert json.loads(out_json.read_text(encoding="utf-8"))["isolated"] is False


def test_bundle_dependencies_downloads_linux_binary_wheels_only(tmp_path, monkeypatch):
    """Wheels must match the Linux sandbox (not the host OS), and sdists are refused so install runs no code."""
    stager = RepoStager(staging_root=tmp_path / "staging")
    source_dir = tmp_path / "source_repo"
    source_dir.mkdir()
    (source_dir / "reproduce.py").write_text("print(1)\n", encoding="utf-8")
    (source_dir / "requirements.txt").write_text("ujson==5.10.0\n", encoding="utf-8")
    staged = stager.stage_repository(paper_id="bundle_test", source=str(source_dir))
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("src.sandbox.stager.subprocess.run", fake_run)
    stager.bundle_dependencies(staged)

    cmd = calls[0]
    assert cmd[:4] == [sys.executable, "-m", "pip", "download"]
    assert "--only-binary=:all:" in cmd and "--prefer-binary" not in cmd
    platforms = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--platform"]
    assert "manylinux2014_x86_64" in platforms
    assert cmd[cmd.index("--python-version") + 1] == "3.11"
    assert cmd[cmd.index("--implementation") + 1] == "cp"


def _stage_with_requirements(tmp_path, files):
    stager = RepoStager(staging_root=tmp_path / "staging")
    source_dir = tmp_path / "source_repo"
    source_dir.mkdir()
    (source_dir / "reproduce.py").write_text("print(1)\n", encoding="utf-8")
    for name, content in files.items():
        (source_dir / name).write_text(content, encoding="utf-8")
    return stager, stager.stage_repository(paper_id="bundle_multi", source=str(source_dir))


def test_bundle_dependencies_uses_every_requirements_file(tmp_path, monkeypatch):
    stager, staged = _stage_with_requirements(
        tmp_path, {"requirements.txt": "toolz==0.12.1\n", "requirements-extra.txt": "ujson==5.10.0\n"}
    )
    calls = []
    monkeypatch.setattr("src.sandbox.stager.subprocess.run",
                        lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""))

    result = stager.bundle_dependencies(staged)

    requirement_args = [calls[0][i + 1] for i, a in enumerate(calls[0]) if a == "-r"]
    assert sorted(Path(r).name for r in requirement_args) == ["requirements-extra.txt", "requirements.txt"]
    assert result["status"] == "SUCCESS"
    assert result["needs_sdist_build"] == []


def test_bundle_dependencies_flags_requirements_without_wheels(tmp_path, monkeypatch):
    stager, staged = _stage_with_requirements(
        tmp_path, {"requirements.txt": "# comment\ntoolz==0.12.1\nlegacy-pkg==1.0  # sdist only\n--index-url https://x\n"}
    )
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if "-r" in cmd or "legacy-pkg==1.0" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "ERROR: No matching distribution found for legacy-pkg==1.0")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("src.sandbox.stager.subprocess.run", fake_run)
    result = stager.bundle_dependencies(staged)

    assert result["status"] == "PARTIAL"
    assert [e["requirement"] for e in result["needs_sdist_build"]] == ["legacy-pkg==1.0"]
    assert "No matching distribution" in result["needs_sdist_build"][0]["reason"]
    for cmd in calls:  # never build on the host: every download is binary-only
        assert "--only-binary=:all:" in cmd
    probes = [c for c in calls if "--no-deps" in c]
    assert sorted(c[c.index("--no-deps") + 1] for c in probes) == ["legacy-pkg==1.0", "toolz==0.12.1"]


def _fake_docker_chain(install_status):
    """Fake `docker run`: the install phase writes install_meta.json; the run phase writes execution_meta.json
    with the dependency status passed to it, like docker/entrypoint.sh does."""
    def fake_run(cmd, **kwargs):
        env = dict(a.split("=", 1) for i, a in enumerate(cmd) if i and cmd[i - 1] == "-e")
        out = next(a for a in cmd if a.endswith(":/workspace/output:rw")).rsplit(":/workspace/output:rw", 1)[0]
        if env.get("SANDBOX_PHASE") == "install":
            Path(out, "install_meta.json").write_text(json.dumps({"phase": "install", "status": install_status, "exit_code": 1}))
            return subprocess.CompletedProcess(cmd, 1, "", "")
        Path(out, "execution_meta.json").write_text(json.dumps({
            "status": "COMPLETED", "exit_code": 0,
            "dependency_install_status": env.get("SANDBOX_DEPENDENCY_STATUS", "SKIPPED"),
        }))
        return subprocess.CompletedProcess(cmd, 0, "ok\n", "")
    return fake_run


def test_failed_install_reaches_top_level_of_run_report(tmp_path, monkeypatch):
    from src.sandbox import runner as runner_module

    stager = RepoStager(staging_root=tmp_path / "staging")
    source_dir = tmp_path / "source_repo"
    source_dir.mkdir()
    (source_dir / "reproduce.py").write_text("print('ok')\n", encoding="utf-8")
    staged = stager.stage_repository(paper_id="install_status_report", source=str(source_dir))
    staged.bundle_dir = tmp_path / "pkgs"
    staged.bundle_dir.mkdir()
    (staged.bundle_dir / "broken-1.0-py3-none-any.whl").write_text("not a wheel", encoding="utf-8")
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *a, **k: True))
    monkeypatch.setattr(runner_module, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(runner_module.subprocess, "run", _fake_docker_chain("FAILED"))

    report = stager.execute_staged(staged, target_script="reproduce.py")

    assert report["dependency_install_status"] == "FAILED"
    assert json.loads(Path(report["run_report_path"]).read_text(encoding="utf-8"))["dependency_install_status"] == "FAILED"


def test_run_report_install_status_is_unknown_without_execution_meta(tmp_path):
    stager = RepoStager(staging_root=tmp_path / "staging")
    source_dir = tmp_path / "source_repo"
    source_dir.mkdir()
    (source_dir / "reproduce.py").write_text("print('ok')\n", encoding="utf-8")
    staged = stager.stage_repository(paper_id="install_status_unknown", source=str(source_dir))
    fake = SandboxExecutionResult(status="FAILED", exit_code=1, stdout="", stderr="", duration_seconds=0.0,
                                  command_executed=["docker"], docker_used=True, output_dir=tmp_path / "no_meta")
    (tmp_path / "no_meta").mkdir()
    with patch("src.sandbox.stager.DockerSandboxRunner.run", return_value=fake):
        report = stager.execute_staged(staged, target_script="reproduce.py")
    assert report["dependency_install_status"] == "UNKNOWN"
