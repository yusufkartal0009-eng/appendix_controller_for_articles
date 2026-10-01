"""The pilot driver and workflow must run exactly what docs/PILOT_WEEK2.md froze (P2, #123)."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts import run_pilot
from src.config import PROJECT_ROOT, SEED_PAPERS_PATH

PROTOCOL = (PROJECT_ROOT / "docs" / "PILOT_WEEK2.md").read_text(encoding="utf-8")
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "pilot.yml"
ENTRIES = {e["paper_id"]: e for e in json.loads(SEED_PAPERS_PATH.read_text(encoding="utf-8"))}


def _protocol_cells():
    rows = {}
    for line in PROTOCOL.splitlines():
        m = re.match(r"\| `(paper_\d{3})` ", line)
        if m and "python /workspace/repo/" in line:
            rows[m.group(1)] = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return rows


def test_specs_cover_exactly_the_seed_papers():
    assert set(run_pilot.PILOT_SPECS) == set(ENTRIES)


@pytest.mark.parametrize("paper_id", sorted(ENTRIES))
def test_command_equals_the_protocol(paper_id):
    cells = _protocol_cells()[paper_id]
    assert run_pilot.container_command(paper_id, ENTRIES[paper_id]["target_script"]) == cells[3].strip("`")


@pytest.mark.parametrize("paper_id", sorted(ENTRIES))
def test_environment_equals_the_protocol(paper_id):
    cell = _protocol_cells()[paper_id][4]
    expected = dict(re.findall(r"`([A-Z_]+)=([^`]*)`", cell))
    assert run_pilot.PILOT_SPECS[paper_id]["env"] == expected


def test_limits_equal_the_protocol():
    limits = run_pilot.PILOT_LIMITS
    assert f"`--cpus={limits['cpus']}`" in PROTOCOL
    assert f"`--memory={limits['memory_limit']}`, `--memory-swap={limits['memory_swap']}`" in PROTOCOL
    assert f"`--pids-limit={limits['pids_limit']}`" in PROTOCOL
    assert f"{limits['timeout_seconds']} s for the install phase and {limits['timeout_seconds']} s for the run phase" in PROTOCOL


class FakeStager:
    def __init__(self, tmp_path, fail_stage=False):
        self.tmp_path = tmp_path
        self.fail_stage = fail_stage
        self.executed = None

    def stage_repository(self, paper_id, source, commit_or_tag):
        if self.fail_stage:
            raise RuntimeError("Failed to clone repository")
        repo = self.tmp_path / paper_id
        script = repo / ENTRIES[paper_id]["target_script"]
        script.parent.mkdir(parents=True)
        script.write_text("print('hi')\n")
        manifest = SimpleNamespace(requirements_files=["requirements.txt"], has_conda_env=False)
        return SimpleNamespace(staged_path=repo, commit_hash=commit_or_tag, manifest=manifest)

    def bundle_dependencies(self, staged, timeout):
        assert timeout == run_pilot.BUNDLE_TIMEOUT_SECONDS
        return {"status": "SUCCESS", "wheel_count": 3}

    def execute_staged(self, staged, target_script, script_args, config):
        self.executed = (target_script, script_args, config)
        return {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 1.0, "docker_used": True,
                "isolated": True, "dependency_install_status": "INSTALLED",
                "meta": {"peak_memory_bytes": 123456789}}


def test_run_paper_uses_protocol_settings_and_writes_a_record(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    stager = FakeStager(tmp_path)
    record = run_pilot.run_paper("paper_003", tmp_path / "staging", stager=stager)

    target_script, script_args, config = stager.executed
    assert target_script == "bin/ft_transformer.py"
    assert script_args == run_pilot.PILOT_SPECS["paper_003"]["args"]
    assert (config.memory_limit, config.memory_swap, config.cpus, config.pids_limit, config.timeout_seconds) == (
        "6g", "6g", 2.0, 100, 3600)
    assert config.env_vars == {"PROJECT_DIR": "/workspace/repo", "CUDA_VISIBLE_DEVICES": ""}
    assert config.allow_unsafe_local is False

    saved = json.loads((tmp_path / "runs" / "paper_003" / "pilot_record.json").read_text())
    assert saved == record
    assert saved["stage"]["matches_pinned_commit"] is True
    assert saved["run"]["docker_used"] is True
    assert saved["run"]["peak_memory_bytes"] == 123456789


def test_staging_failure_is_recorded_not_raised(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    record = run_pilot.run_paper("paper_004", tmp_path / "staging", stager=FakeStager(tmp_path, fail_stage=True))
    assert record["stage"]["status"] == "FAILED"
    assert "run" not in record
    assert Path(tmp_path / "runs" / "paper_004" / "pilot_record.json").exists()


def test_harness_error_exits_non_zero(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("Docker is not available")

    monkeypatch.setattr(run_pilot, "run_paper", boom)
    assert run_pilot.main(["paper_002"]) == 1


def test_workflow_is_manual_read_only_and_keeps_no_credentials():
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    triggers = workflow.get("on", workflow.get(True))  # PyYAML reads the key `on` as True
    assert set(triggers) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    assert "secrets." not in text

    job = workflow["jobs"]["pilot"]
    assert job["timeout-minutes"] == 150
    assert job["strategy"]["fail-fast"] is False
    default_papers = json.loads(triggers["workflow_dispatch"]["inputs"]["papers"]["default"])
    assert sorted(default_papers) == sorted(ENTRIES)
    checkout = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout"))
    assert checkout["with"]["persist-credentials"] is False
    upload = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact"))
    assert "!sandbox_runs/${{ matrix.paper_id }}/deps" in upload["with"]["path"]
