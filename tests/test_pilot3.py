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


def test_memory_and_record_root_options_change_only_the_memory_limit_and_the_directory(tmp_path, monkeypatch):
    """#319: Pilot 3's settings stay as they are; the memory limit is replaced; the record goes elsewhere."""
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(run_pilot, "PILOT3_RUNS_DIR", tmp_path / "pilot3")
    monkeypatch.setattr(run_pilot, "PILOT2_RUNS_DIR", tmp_path / "pilot2")
    monkeypatch.setattr(run_pilot, "resolve_memory_limit", lambda value: "7777m" if value == "50%" else value)
    stager = Pilot2Stager(tmp_path)
    record = run_pilot.run_paper("paper_004", tmp_path / "staging", stager=stager, pilot3=True,
                                 data_cache=_cache(tmp_path, "paper_004"), memory_limit="50%",
                                 record_root=tmp_path / "memory_runs")
    config = stager.executed[2]
    # memory and swap replaced; Pilot 3's longer run phase (paper_004) and the other limits are kept
    assert (config.memory_limit, config.memory_swap, config.run_timeout_seconds, config.timeout_seconds) == (
        "7777m", "7777m", 14400, 3600)
    assert record["memory_override"] == {"requested": "50%", "resolved": "7777m", "protocol_memory_limit": "6g"}
    assert record["protocol"] == "docs/PILOT_3.md" and record["pilot3_change"]["run_timeout_seconds"] == 14400
    assert (tmp_path / "memory_runs" / "paper_004" / "pilot_record.json").exists()
    assert not (tmp_path / "pilot3").exists() and not (tmp_path / "pilot2").exists()  # protocol directories untouched


def test_the_memory_option_replaces_pilot_3s_own_memory_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(run_pilot, "resolve_memory_limit", lambda value: value)
    stager = Pilot2Stager(tmp_path)
    record = run_pilot.run_paper("paper_005", tmp_path / "staging", stager=stager, pilot3=True,
                                 data_cache=_cache(tmp_path, "paper_005"), memory_limit="8g",
                                 record_root=tmp_path / "memory_runs")
    assert stager.executed[2].memory_limit == "8g"
    assert record["memory_override"]["protocol_memory_limit"] == "12g"  # Pilot 3's own value is recorded


def test_the_command_line_passes_both_options_on(monkeypatch, tmp_path):
    seen = {}

    def fake(paper_id, staging_dir, **kwargs):
        seen.update(kwargs)
        return {"paper_id": paper_id}

    monkeypatch.setattr(run_pilot, "run_paper", fake)
    assert run_pilot.main(["paper_005", "--pilot3", "--memory", "50%", "--record-root", str(tmp_path / "m")]) == 0
    assert seen["pilot3"] is True and seen["memory_limit"] == "50%" and seen["record_root"] == tmp_path / "m"
    seen.clear()
    assert run_pilot.main(["paper_005", "--pilot3"]) == 0  # without the options: nothing changes
    assert seen["memory_limit"] is None and seen["record_root"] is None


def test_record_root_without_a_pilot_flag_is_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(run_pilot, "run_paper", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(SystemExit):
        run_pilot.main(["paper_005", "--record-root", str(tmp_path)])


def test_the_cpus_option_changes_only_the_cpu_limit_and_is_recorded(tmp_path, monkeypatch):
    """#331: not a protocol run; every other Pilot 3 setting stays."""
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    stager = Pilot2Stager(tmp_path)
    record = run_pilot.run_paper("paper_005", tmp_path / "staging", stager=stager, pilot3=True,
                                 data_cache=_cache(tmp_path, "paper_005"), cpus=8, record_root=tmp_path / "cpu_runs")
    config = stager.executed[2]
    assert (config.cpus, config.memory_limit, config.pids_limit, config.timeout_seconds) == (8.0, "12g", 100, 3600)
    assert record["cpus_override"]["requested"] == 8 and record["cpus_override"]["protocol_cpus"] == 2.0
    assert "not a protocol run" in record["cpus_override"]["note"] and "memory_override" not in record
    assert record["limits"]["cpus"] == 8.0
    assert (tmp_path / "cpu_runs" / "paper_005" / "pilot_record.json").exists()


def test_without_the_cpus_option_nothing_changes(tmp_path, monkeypatch):
    record, stager = _run(tmp_path, monkeypatch, "paper_005")
    assert stager.executed[2].cpus == 2.0 and "cpus_override" not in record


@pytest.mark.parametrize("value", [0, -1])
def test_a_non_positive_cpu_limit_is_a_harness_error(tmp_path, monkeypatch, value):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    with pytest.raises(ValueError, match="CPU limit"):
        run_pilot.run_paper("paper_005", tmp_path / "staging", stager=Pilot2Stager(tmp_path), pilot3=True,
                            data_cache=_cache(tmp_path, "paper_005"), cpus=value)


def test_the_command_line_passes_cpus_on(monkeypatch):
    seen = {}
    monkeypatch.setattr(run_pilot, "run_paper", lambda paper_id, staging_dir, **kw: seen.update(kw) or {"paper_id": paper_id})
    assert run_pilot.main(["paper_003", "--pilot3", "--cpus", "8"]) == 0 and seen["cpus"] == 8.0


def test_the_timeout_option_changes_only_the_run_phase_limit_and_is_recorded(tmp_path, monkeypatch):
    """#396: not a protocol run; the install phase keeps its limit."""
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    stager = Pilot2Stager(tmp_path)
    record = run_pilot.run_paper("paper_005", tmp_path / "staging", stager=stager, pilot3=True,
                                 data_cache=_cache(tmp_path, "paper_005"), run_timeout=7200, record_root=tmp_path / "t_runs")
    config = stager.executed[2]
    assert (config.run_timeout_seconds, config.timeout_seconds, config.cpus) == (7200, 3600, 2.0)
    assert record["timeout_override"]["requested"] == 7200 and "not a protocol run" in record["timeout_override"]["note"]
    assert record["limits"]["run_timeout_seconds"] == 7200


def test_without_the_timeout_option_nothing_changes(tmp_path, monkeypatch):
    record, _stager = _run(tmp_path, monkeypatch, "paper_005")
    assert "timeout_override" not in record


@pytest.mark.parametrize("value", [0, -5])
def test_a_non_positive_run_time_limit_is_a_harness_error(tmp_path, monkeypatch, value):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    with pytest.raises(ValueError, match="run time limit"):
        run_pilot.run_paper("paper_005", tmp_path / "staging", stager=Pilot2Stager(tmp_path), pilot3=True,
                            data_cache=_cache(tmp_path, "paper_005"), run_timeout=value)

