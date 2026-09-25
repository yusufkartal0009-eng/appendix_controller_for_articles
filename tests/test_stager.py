"""Unit tests for RepoStager, dependency analysis, and staging CLI automation."""

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.stage_and_bundle_repo import sanitize_paper_id
from src.sandbox.runner import DockerSandboxRunner, SandboxExecutionResult
from src.sandbox.stager import DependencyManifest, RepoStager, StagedRepo


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
    # Exercise the local process runner even on hosts where Docker is available (e.g. CI).
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

    report = stager.execute_staged(staged, target_script="reproduce.py")

    assert report["paper_id"] == "paper_metric_test"
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

    with patch("src.sandbox.stager.DockerSandboxRunner.run", return_value=fake_result):
        with caplog.at_level("WARNING", logger="src.sandbox.stager"):
            report = stager.execute_staged(staged, target_script="reproduce.py")

    assert report["meta"] == {}
    assert "execution_meta.json" in report["meta_error"]
    assert any("execution_meta.json" in r.getMessage() for r in caplog.records)