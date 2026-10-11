"""scripts/stage_and_bundle_repo.py: the exit code of every stage of the command line (#272)."""

import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

from scripts import stage_and_bundle_repo as cli
from src.sandbox.runner import SandboxUnavailableError
from src.sandbox.stager import DependencyManifest, StagedRepo


def _staged(tmp_path, candidates=("main.py",)):
    return StagedRepo(paper_id="p", source="s", staged_path=tmp_path, commit_hash="abc", manifest=DependencyManifest(),
                      candidate_scripts=list(candidates))


class FakeStager:
    """Replaces RepoStager: each stage answers from the class attributes a test sets."""

    staged = None
    stage_error = None
    bundle: ClassVar[dict[str, Any]] = {"status": "SUCCESS", "wheel_count": 2, "bundle_dir": "b", "needs_sdist_build": []}
    execute: ClassVar[dict[str, Any]] = {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 1.0, "docker_used": True, "isolated": True,
               "output_dir": "o", "generated_files": []}
    execute_error = None
    executed_with = None

    def __init__(self, staging_root=None):
        pass

    def stage_repository(self, paper_id, source, commit_or_tag=None):
        if FakeStager.stage_error:
            raise FakeStager.stage_error
        return FakeStager.staged

    def bundle_dependencies(self, staged):
        return FakeStager.bundle

    def execute_staged(self, staged, target_script, script_args, config):
        FakeStager.executed_with = (target_script, script_args, config)
        if FakeStager.execute_error:
            raise FakeStager.execute_error
        return FakeStager.execute


@pytest.fixture
def run_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RepoStager", FakeStager)
    monkeypatch.setattr(FakeStager, "staged", _staged(tmp_path))
    monkeypatch.setattr(FakeStager, "stage_error", None)
    monkeypatch.setattr(FakeStager, "execute_error", None)

    def run(*args):
        monkeypatch.setattr("sys.argv", ["stage_and_bundle_repo.py", "https://example.org/o/r.git", *args])
        return cli.main()
    return run


def test_a_staging_failure_exits_with_1(run_cli, monkeypatch):
    monkeypatch.setattr(FakeStager, "stage_error", RuntimeError("clone failed"))
    assert run_cli() == 1


def test_no_run_stops_after_staging_and_lists_sdist_builds(run_cli, monkeypatch, capsys):
    monkeypatch.setattr(FakeStager, "bundle", {"status": "PARTIAL", "wheel_count": 1, "bundle_dir": "b",
                                               "needs_sdist_build": [{"requirement": "fastsk", "reason": "no wheel"}]})
    assert run_cli("--bundle-deps", "--no-run") == 0
    out = capsys.readouterr().out
    assert "NEEDS_SDIST_BUILD: fastsk (no wheel)" in out and "Execution skipped" in out


def test_without_a_script_and_no_candidate_it_exits_with_2(run_cli, monkeypatch, tmp_path):
    monkeypatch.setattr(FakeStager, "staged", _staged(tmp_path, candidates=()))
    assert run_cli() == 2


def test_the_first_candidate_runs_with_the_given_limits(run_cli, capsys):
    assert run_cli("--timeout", "45", "--memory", "4g", "--cpus", "1.5", "--script-args", "--seed", "7") == 0
    script, args, config = FakeStager.executed_with
    assert script == "main.py" and args == ["--seed", "7"]
    assert (config.timeout_seconds, config.memory_limit, config.cpus) == (45, "4g", "1.5")
    assert "Auto-selected entrypoint script: main.py" in capsys.readouterr().out


def test_unavailable_sandbox_and_other_failures_have_their_own_exit_codes(run_cli, monkeypatch, capsys):
    monkeypatch.setattr(FakeStager, "execute_error", SandboxUnavailableError("no docker"))
    assert run_cli() == cli.EXIT_SANDBOX_UNAVAILABLE
    assert "ERROR: no docker" in capsys.readouterr().err
    monkeypatch.setattr(FakeStager, "execute_error", ValueError("boom"))
    assert run_cli() == 3


def test_summary_shows_fallback_metrics_and_warns_about_an_unisolated_run(run_cli, monkeypatch, capsys, tmp_path):
    report = {**FakeStager.execute, "status": "FAILED", "isolated": False, "fallback_reason": "Docker unavailable",
              "metrics": {"accuracy": 0.9}}
    monkeypatch.setattr(FakeStager, "execute", report)
    target = tmp_path / "reports" / "r.json"
    assert run_cli("--allow-unsafe-local", "--output-json", str(target)) == 1  # FAILED is not a success
    captured = capsys.readouterr()
    assert "Fallback Reason: Docker unavailable" in captured.out and '"accuracy": 0.9' in captured.out
    assert cli.UNSAFE_LOCAL_PRERUN_WARNING in captured.err and cli.UNSAFE_LOCAL_WARNING in captured.err
    assert json.loads(Path(target).read_text(encoding="utf-8"))["status"] == "FAILED"
