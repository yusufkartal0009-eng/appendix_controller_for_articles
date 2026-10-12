"""Pilot 3 (#287): the four changes of docs/PILOT_3.md as an overlay on the Pilot 2 run setups."""

import json
import re
import sys

import pytest

from scripts import (
    categorize_pilot_failures,
    pilot_measurements,
    record_pilot2_environment,
    run_pilot,
)
from src.config import PROJECT_ROOT, SEED_PAPERS_PATH
from src.sandbox.runner import DockerSandboxRunner, SandboxConfig
from tests.test_run_pilot import Pilot2Stager

ENTRIES = {e["paper_id"]: e for e in json.loads(SEED_PAPERS_PATH.read_text(encoding="utf-8"))}
PROTOCOL = (PROJECT_ROOT / "docs" / "PILOT_3.md").read_text(encoding="utf-8")


def _cache(tmp_path, paper_id):
    for item in ENTRIES[paper_id]["run_setup"].get("data", []):
        marker = tmp_path / "cache" / paper_id / item["name"] / ".complete"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("{}")
    return tmp_path / "cache"


def _run(tmp_path, monkeypatch, paper_id):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(run_pilot, "PILOT3_RUNS_DIR", tmp_path / "pilot3")
    stager = Pilot2Stager(tmp_path)
    record = run_pilot.run_paper(paper_id, tmp_path / "staging", stager=stager, pilot3=True,
                                 data_cache=_cache(tmp_path, paper_id))
    return record, stager


def test_the_overlay_lists_exactly_the_four_papers_of_the_protocol():
    settings = json.loads(run_pilot.PILOT3_SETTINGS_PATH.read_text(encoding="utf-8"))
    assert settings["protocol"] == "docs/PILOT_3.md"
    assert sorted(settings["papers"]) == ["paper_002", "paper_003", "paper_004", "paper_005"]
    for paper_id in settings["papers"]:
        change = run_pilot.load_pilot3_change(paper_id)  # validates the keys, the reason and the evidence
        assert paper_id in PROTOCOL
        run_pilot.apply_pilot3_change(ENTRIES[paper_id], change)  # every name it points at exists
    assert run_pilot.load_pilot3_change("paper_006") == {} and run_pilot.load_pilot3_change("paper_008") == {}


def test_the_values_in_the_overlay_are_the_values_in_the_protocol():
    papers = json.loads(run_pilot.PILOT3_SETTINGS_PATH.read_text(encoding="utf-8"))["papers"]
    assert papers["paper_005"]["memory_limit"] == papers["paper_005"]["memory_swap"] == "12g"
    assert "`--memory=12g --memory-swap=12g`" in PROTOCOL
    assert papers["paper_004"]["run_timeout_seconds"] == 14400 and "**14400 s**" in PROTOCOL
    assert papers["paper_002"]["extra_requirements_add"] == ["lightgbm"] and "`lightgbm`" in PROTOCOL
    assert papers["paper_003"]["data_writable"] == ["revisiting_models_data"]
    assert re.search(r"`revisiting_models_data`.*writable per-run copy", PROTOCOL)


def test_the_overlay_does_not_change_the_seed_entry():
    before = json.dumps(ENTRIES["paper_003"], sort_keys=True)
    changed = run_pilot.apply_pilot3_change(ENTRIES["paper_003"], run_pilot.load_pilot3_change("paper_003"))
    assert json.dumps(ENTRIES["paper_003"], sort_keys=True) == before
    assert changed["run_setup"]["data"][0]["writable"] is True
    assert "writable" not in ENTRIES["paper_003"]["run_setup"]["data"][0]


def test_an_unknown_key_or_name_or_a_missing_reason_is_an_error(tmp_path):
    path = tmp_path / "settings.json"

    def write(change):
        path.write_text(json.dumps({"papers": {"paper_003": change}}), encoding="utf-8")

    write({"memory": "12g", "reason": "r", "pilot2_evidence": "e"})
    with pytest.raises(ValueError, match="unknown keys"):
        run_pilot.load_pilot3_change("paper_003", path)
    write({"memory_limit": "12g"})
    with pytest.raises(ValueError, match="reason"):
        run_pilot.load_pilot3_change("paper_003", path)
    with pytest.raises(ValueError, match="not a data item"):
        run_pilot.apply_pilot3_change(ENTRIES["paper_003"], {"data_writable": ["nothing"]})


def test_paper_005_gets_12g_and_keeps_every_other_limit(tmp_path, monkeypatch):
    record, stager = _run(tmp_path, monkeypatch, "paper_005")
    config = stager.executed[2]
    assert (config.memory_limit, config.memory_swap, config.cpus, config.pids_limit, config.timeout_seconds,
            config.run_timeout_seconds) == ("12g", "12g", 2.0, 100, 3600, 0)
    assert record["protocol"] == "docs/PILOT_3.md" and record["limits"]["memory_limit"] == "12g"
    assert record["pilot3_change"]["memory_limit"] == "12g"
    assert (tmp_path / "pilot3" / "paper_005" / "pilot_record.json").exists()  # data/pilot3_runs, not pilot2_runs


def test_paper_004_gets_a_longer_run_phase_only(tmp_path, monkeypatch):
    _, stager = _run(tmp_path, monkeypatch, "paper_004")
    config = stager.executed[2]
    assert (config.timeout_seconds, config.run_timeout_seconds, config.memory_limit) == (3600, 14400, "6g")


def test_paper_003_mounts_its_data_as_a_writable_copy(tmp_path, monkeypatch):
    _, stager = _run(tmp_path, monkeypatch, "paper_003")
    config = stager.executed[2]
    assert config.writable_data == ["/workspace/repo/data"] and "/workspace/repo/data" in config.data_mounts


def test_paper_002_installs_lightgbm_too(tmp_path, monkeypatch):
    _, stager = _run(tmp_path, monkeypatch, "paper_002")
    assert stager.bundle_kwargs["extra_requirements"] == ["nbconvert", "ipykernel", "lightgbm"]
    assert stager.executed[2].extra_requirements == ["nbconvert", "ipykernel", "lightgbm"]


@pytest.mark.parametrize("paper_id", ["paper_006", "paper_008"])
def test_the_papers_without_a_change_run_as_in_pilot_2(tmp_path, monkeypatch, paper_id):
    record, stager = _run(tmp_path, monkeypatch, paper_id)
    assert record["pilot3_change"] == {} and record["limits"] == run_pilot.PILOT_LIMITS
    assert stager.executed[2].run_timeout_seconds == 0


def test_the_run_timeout_applies_to_the_run_phase_and_not_to_the_install_phase():
    runner = DockerSandboxRunner(SandboxConfig(timeout_seconds=3600, run_timeout_seconds=14400))
    install = runner.build_docker_command("/r", "/o", ["x"])
    run = runner.build_docker_command("/r", "/o", ["x"], extra_env={"SANDBOX_TIMEOUT": "14400"})
    assert install.count("SANDBOX_TIMEOUT=3600") == 1 and "SANDBOX_TIMEOUT=14400" not in install
    assert run.count("SANDBOX_TIMEOUT=14400") == 1 and "SANDBOX_TIMEOUT=3600" not in run
    with pytest.raises(ValueError, match="run_timeout_seconds"):
        SandboxConfig(run_timeout_seconds=-1)


def test_the_tools_name_the_pilot_3_directory(tmp_path, monkeypatch, capsys):
    runs = tmp_path / "pilot3_runs"
    runs.mkdir()
    assert pilot_measurements.measure(runs)["protocol"] == "docs/PILOT_3.md"
    assert "data/pilot3_runs/" in pilot_measurements.to_markdown(pilot_measurements.measure(runs))
    assert categorize_pilot_failures.categorize(runs)["protocol"].startswith("docs/PILOT_3.md")
    out = tmp_path / "pilot3_runs" / "environment.txt"
    monkeypatch.setattr(record_pilot2_environment, "OUT_PILOT3", out)
    monkeypatch.setattr(record_pilot2_environment, "COMMANDS", [("python --version", [sys.executable, "--version"])])
    assert record_pilot2_environment.main(["--pilot3"]) == 0
    assert out.read_text(encoding="utf-8").startswith("Pilot 3 environment, recorded ")
