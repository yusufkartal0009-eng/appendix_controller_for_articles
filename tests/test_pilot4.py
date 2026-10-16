"""Pilot 4 (#346): the README command as written, the fixed settings, and the one recorded correction round."""

import json
import re
from types import SimpleNamespace

import pytest

from scripts import categorize_pilot_failures, pilot_measurements, run_pilot
from src.config import PROJECT_ROOT

PROTOCOL = (PROJECT_ROOT / "docs" / "PILOT_4.md").read_text(encoding="utf-8")
CORPUS = {e["paper_id"]: e for e in json.loads((PROJECT_ROOT / "data" / "corpus_expansion" / "papers.json").read_text(encoding="utf-8"))}


class Stager:
    """A stager that records what the driver asks of it, for any corpus paper."""

    def __init__(self, tmp_path, status="COMPLETED", exit_code=0):
        self.tmp_path = tmp_path
        self.status, self.exit_code = status, exit_code
        self.bundled_for = self.bundle_kwargs = self.executed = self.run_kwargs = None

    def stage_repository(self, paper_id, source, commit_or_tag):
        repo = self.tmp_path / paper_id
        (repo / "x").mkdir(parents=True, exist_ok=True)
        target = CORPUS[paper_id]["target_script"]
        (repo / target).parent.mkdir(parents=True, exist_ok=True)
        (repo / target).write_text("print('hi')\n")
        manifest = SimpleNamespace(requirements_files=[], has_conda_env=False)
        return SimpleNamespace(staged_path=repo, commit_hash=commit_or_tag, manifest=manifest)

    def bundle_dependencies(self, staged, timeout, python_version, **kwargs):
        self.bundled_for, self.bundle_kwargs = python_version, kwargs
        return {"status": "SUCCESS", "wheel_count": 0}

    def execute_staged(self, staged, target_script, script_args, config, **kwargs):
        self.executed, self.run_kwargs = (target_script, script_args, config), kwargs
        return {"status": self.status, "exit_code": self.exit_code, "duration_seconds": 1.0, "docker_used": True,
                "isolated": True, "dependency_install_status": "SKIPPED", "meta": {"peak_memory_bytes": 1}}


@pytest.fixture(autouse=True)
def _dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(run_pilot, "PILOT4_RUNS_DIR", tmp_path / "pilot4")
    monkeypatch.setattr(run_pilot, "resolve_memory_limit", lambda value: "7777m" if value == "50%" else value)


def _run(tmp_path, paper_id="paper_105", **kwargs):
    stager = Stager(tmp_path)
    record = run_pilot.run_paper(paper_id, tmp_path / "staging", stager=stager, pilot4=True, data_cache=tmp_path / "cache",
                                 **kwargs)
    return record, stager


def test_the_first_attempt_runs_the_readme_command_as_written_under_the_fixed_settings(tmp_path):
    record, stager = _run(tmp_path)
    target, args, config = stager.executed
    assert target == "train.py" and args == ["--dataset", "Cora"]  # `python train.py --dataset Cora`
    assert (config.cpus, config.memory_limit, config.memory_swap, config.pids_limit) == (2.0, "7777m", "7777m", 100)
    assert (config.timeout_seconds, config.run_timeout_seconds) == (3600, 14400)
    assert config.python_version == "3.11" and stager.bundled_for == "3.11" and config.working_dir == ""
    assert config.writable_repo is False and not config.data_mounts and config.env_vars == {}
    assert stager.bundle_kwargs == {"extra_requirements": [], "constraints": []} and stager.run_kwargs == {}
    assert record["protocol"] == "docs/PILOT_4.md" and record["pilot4"]["attempt"] == "first"
    assert record["pilot4"]["run_command"] == "python train.py --dataset Cora" and record["pilot4"]["correction"] is None
    assert record["memory_override"]["resolved"] == "7777m"
    assert (tmp_path / "pilot4" / "paper_105" / "pilot_record.json").exists()  # data/pilot4_runs, not pilot2/3


def test_a_paper_of_the_seed_corpus_is_not_a_pilot_4_paper(tmp_path):
    with pytest.raises(KeyError):
        run_pilot.run_paper("paper_003", tmp_path / "staging", stager=Stager(tmp_path), pilot4=True)


def test_the_correction_round_changes_only_what_it_names_and_is_recorded(tmp_path):
    correction = {"extra_requirements": ["scikit-learn"], "python_version": "3.9",
                  "changes": [{"change": "add scikit-learn", "log_line": "ModuleNotFoundError: No module named 'sklearn'"}]}
    record, stager = _run(tmp_path, correction=correction)
    config = stager.executed[2]
    assert stager.bundled_for == "3.9" and config.python_version == "3.9" and config.image_name.endswith("py3.9")
    assert stager.bundle_kwargs["extra_requirements"] == ["scikit-learn"]
    # the limits of the protocol stay: a correction cannot give more memory, time, or CPUs
    assert (config.cpus, config.memory_limit, config.run_timeout_seconds) == (2.0, "7777m", 14400)
    assert record["pilot4"]["attempt"] == "correction" and record["pilot4"]["correction"] == correction


@pytest.mark.parametrize("correction,message", [
    ({"memory_limit": "20g", "changes": [{"change": "x", "log_line": "y"}]}, "not allowed"),
    ({"cpus": 8, "changes": [{"change": "x", "log_line": "y"}]}, "not allowed"),
    ({"run_timeout_seconds": 99999, "changes": [{"change": "x", "log_line": "y"}]}, "not allowed"),
    ({"command": "python other.py"}, "not allowed"),
    ({"extra_requirements": ["a"]}, "changes"),
    ({"extra_requirements": ["a"], "changes": [{"change": "a"}]}, "log_line"),
    ({"python_version": "2.7", "changes": [{"change": "x", "log_line": "y"}]}, "python_version"),
    ({"constraints": ["a<2"], "changes": [{"change": "x", "log_line": "y"}]}, "constraints_source"),
])
def test_a_correction_outside_the_protocol_is_refused(tmp_path, correction, message):
    with pytest.raises(ValueError, match=message):
        _run(tmp_path, correction=correction)


def test_every_corpus_command_is_python_script_args_and_matches_its_target():
    for paper_id in CORPUS:
        entry = run_pilot.pilot4_entry(paper_id)
        assert entry["run_setup"]["decision"] == "report_as_is" and entry["python_version"] == "3.11"
        assert entry["run_command"].split()[1].removeprefix("./") == entry["target_script"]


def test_an_interpreter_option_before_the_script_is_a_harness_error(tmp_path):
    path = tmp_path / "papers.json"
    entry = dict(CORPUS["paper_105"], run_command="python -u train.py")
    path.write_text(json.dumps([entry]), encoding="utf-8")
    with pytest.raises(ValueError, match="python <script>"):
        run_pilot.pilot4_entry("paper_105", path)


def test_the_command_line_needs_the_pilot_4_flag_for_corpus_papers_and_refuses_mixing(capsys):
    for argv in (["paper_105"], ["paper_105", "--correction", "x.json"], ["paper_003", "--pilot4", "--pilot3"]):
        with pytest.raises(SystemExit):
            run_pilot.main(argv)


def test_the_command_line_passes_pilot_4_options_on(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(run_pilot, "run_paper", lambda paper_id, staging_dir, **kw: seen.update(kw) or {"paper_id": paper_id})
    file = tmp_path / "c.json"
    file.write_text(json.dumps({"changes": []}), encoding="utf-8")
    assert run_pilot.main(["paper_105", "--pilot4", "--correction", str(file)]) == 0
    assert seen["pilot4"] is True and seen["correction"] == {"changes": []} and seen["memory_limit"] is None


def test_the_code_and_the_protocol_agree():
    assert run_pilot.PILOT4_RUN_TIMEOUT_SECONDS == 14400 and "**14400 s for the run phase**" in PROTOCOL
    assert run_pilot.PILOT4_MEMORY == "50%" and "**50% of the host's RAM**" in PROTOCOL
    assert run_pilot.PILOT_LIMITS["cpus"] == 2.0 and "`--cpus=2.0`" in PROTOCOL
    assert run_pilot.PILOT_LIMITS["pids_limit"] == 100 and "`--pids-limit=100`" in PROTOCOL
    assert run_pilot.PILOT_LIMITS["timeout_seconds"] == 3600 and "3600 s for the install phase" in PROTOCOL
    for key in run_pilot.CORRECTION_KEYS:
        if key not in ("changes", "constraints_source"):
            assert re.search(rf"\b{key.split('_')[0]}", PROTOCOL.replace("working directory", "working_dir"), re.IGNORECASE) or key == "env"


def test_the_measurement_and_category_tools_read_the_paper_list_of_the_corpus(tmp_path):
    corpus = PROJECT_ROOT / "data" / "corpus_expansion" / "papers.json"
    result = pilot_measurements.measure(tmp_path / "pilot4_runs", corpus)
    assert result["protocol"] == "docs/PILOT_4.md" and result["pilot_success_rate"]["of"] == 6
    assert [p["paper_id"] for p in result["papers"]] == sorted(CORPUS)
    categories = categorize_pilot_failures.categorize(tmp_path / "pilot4_runs", corpus)
    assert [p["paper_id"] for p in categories["papers"]] == sorted(CORPUS)
