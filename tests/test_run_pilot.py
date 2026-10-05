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

    def bundle_dependencies(self, staged, timeout, python_version):
        assert timeout == run_pilot.BUNDLE_TIMEOUT_SECONDS
        self.bundled_for = python_version
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
    # paper_003 runs on Python 3.8 (data/seed_papers.json, #158): bundle and image follow it
    assert stager.bundled_for == "3.8" and config.python_version == "3.8"
    assert config.image_name == "repro-radar-sandbox:py3.8" and record["python_version"] == "3.8"

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


class Pilot2Stager(FakeStager):
    """FakeStager that also records the run setup options (#205)."""

    def __init__(self, tmp_path, build_status="BUILT"):
        super().__init__(tmp_path)
        self.build_status = build_status
        self.built = None
        self.bundle_kwargs = None
        self.run_kwargs = None

    def build_from_source(self, staged, build, config):
        self.built = (build, config.python_version)
        return {"status": self.build_status, "wheels": [], "command_executed": ["docker"], "image": "x-build"}

    def bundle_dependencies(self, staged, timeout, python_version, **kwargs):
        self.bundle_kwargs = kwargs
        return {"status": "SUCCESS", "wheel_count": 3}

    def execute_staged(self, staged, target_script, script_args, config, **kwargs):
        self.run_kwargs = kwargs
        return super().execute_staged(staged, target_script, script_args, config)


def _cache_for(tmp_path, paper_id):
    for item in ENTRIES[paper_id]["run_setup"].get("data", []):
        marker = tmp_path / "cache" / paper_id / item["name"] / ".complete"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("{}")
    return tmp_path / "cache"


def test_pilot2_missing_data_is_a_harness_error_naming_the_fetch_script(tmp_path):
    with pytest.raises(ValueError, match="fetch_data.py"):
        run_pilot.run_paper("paper_003", tmp_path / "staging", stager=Pilot2Stager(tmp_path), pilot2=True,
                            data_cache=tmp_path / "empty")


def test_pilot2_runs_with_the_run_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    stager = Pilot2Stager(tmp_path)
    record = run_pilot.run_paper("paper_006", tmp_path / "staging", stager=stager, pilot2=True,
                                 data_cache=_cache_for(tmp_path, "paper_006"))
    build, build_python = stager.built
    assert build["sdists"] == ["openml==0.11.0", "liac-arff==2.5.0"] and build_python == "3.8"
    assert stager.bundle_kwargs == {"extra_requirements": [], "constraints": []}
    assert stager.run_kwargs == {}  # paper_006 runs a script, so there is no command override
    _, script_args, config = stager.executed
    assert script_args == ["--dset_id", "1461", "--task", "binary", "--savemodelroot", "/workspace/output/bestmodels"]
    assert config.writable_data == ["/workspace/home/.openml/cache"] and config.gpus == ""
    assert (config.memory_limit, config.cpus, config.timeout_seconds) == ("6g", 2.0, 3600)  # Pilot 1's limits
    assert record["protocol"] == "docs/PILOT_2.md" and record["build"]["status"] == "BUILT"
    assert record["run_setup"]["decision"] == "fix" and record["run"]["status"] == "COMPLETED"


def test_pilot2_passes_the_command_extras_and_constraints(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    stager = Pilot2Stager(tmp_path)
    run_pilot.run_paper("paper_002", tmp_path / "staging", stager=stager, pilot2=True,
                        data_cache=_cache_for(tmp_path, "paper_002"))
    assert stager.bundle_kwargs["extra_requirements"] == ["nbconvert", "ipykernel"]
    assert stager.run_kwargs["command"][:4] == ["python", "-m", "nbconvert", "--to"]
    stager5 = Pilot2Stager(tmp_path / "p5")
    run_pilot.run_paper("paper_005", tmp_path / "staging5", stager=stager5, pilot2=True, data_cache=tmp_path)
    assert "pandas==1.2.4" in stager5.bundle_kwargs["constraints"]
    assert stager5.executed[2].working_dir == "results"


def test_pilot2_failed_build_ends_the_paper_before_install(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    stager = Pilot2Stager(tmp_path, build_status="FAILED")
    record = run_pilot.run_paper("paper_006", tmp_path / "staging", stager=stager, pilot2=True,
                                 data_cache=_cache_for(tmp_path, "paper_006"))
    assert record["build"]["status"] == "FAILED" and "run" not in record and "bundle" not in record
    assert stager.bundle_kwargs is None and stager.executed is None
    assert (tmp_path / "runs" / "paper_006" / "pilot_record.json").exists()


def test_pilot1_mode_does_not_use_the_run_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    stager = Pilot2Stager(tmp_path)
    record = run_pilot.run_paper("paper_006", tmp_path / "staging", stager=stager)
    assert stager.built is None and "run_setup" not in record and record["protocol"] == "docs/PILOT_WEEK2.md"
