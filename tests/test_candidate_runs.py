"""The candidate runs: the corpus entry of the plan, the folder and shell command of the Pilot 4 flow, one attempt each (#437)."""

import json
from types import SimpleNamespace

import pytest

from scripts import candidate_runs, run_pilot
from src.config import DATA_DIR

PAPERS = {p["paper_id"]: p for p in json.loads((DATA_DIR / "candidates" / "papers.json").read_text(encoding="utf-8"))}


def _plan_entries():
    return [(paper, step) for paper, step in candidate_runs.load_plan() if step["runnable"]]


def test_every_runnable_step_of_the_plan_is_a_valid_pilot_4_entry(tmp_path):
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps([candidate_runs.corpus_entry(p, s) for p, s in _plan_entries()]), encoding="utf-8")
    assert len(_plan_entries()) == 13
    for paper, step in _plan_entries():
        entry = run_pilot.pilot4_entry(paper["paper_id"], corpus)
        setup = entry["run_setup"]
        assert setup["working_dir"] == step["working_dir"] and setup["writable_repo"] is False and not setup["data"]
        assert (setup.get("command") is not None) == step["shell"]


def test_a_folder_and_a_shell_command_reach_the_entry_and_the_script_must_match_the_target(tmp_path):
    base = dict(PAPERS["cand_008"])
    path = tmp_path / "c.json"
    path.write_text(json.dumps([candidate_runs.corpus_entry(base, {"command": "python run_sweep.py --max-runs 8", "working_dir": "research", "shell": False})]))
    setup = run_pilot.pilot4_entry("cand_008", path)["run_setup"]
    assert setup["working_dir"] == "research" and setup["args"] == ["--max-runs", "8"] and "command" not in setup
    path.write_text(json.dumps([candidate_runs.corpus_entry(base, {"command": "python run_sweep.py", "working_dir": "", "shell": False})]))
    with pytest.raises(ValueError, match="not the target script"):
        run_pilot.pilot4_entry("cand_008", path)
    shell = candidate_runs.corpus_entry(PAPERS["cand_025"], {"command": "python a.py && python b.py", "working_dir": "", "shell": True})
    path.write_text(json.dumps([shell]))
    setup = run_pilot.pilot4_entry("cand_025", path)["run_setup"]
    assert setup["command"] == ["sh", "-c", "python a.py && python b.py"] and setup["args"] == []


class Stager:
    def __init__(self, tmp_path):
        self.tmp_path, self.run_kwargs, self.executed = tmp_path, None, None

    def stage_repository(self, paper_id, source, commit_or_tag):
        repo = self.tmp_path / paper_id
        repo.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(staged_path=repo, commit_hash=commit_or_tag,
                               manifest=SimpleNamespace(requirements_files=[], has_conda_env=False))

    def bundle_dependencies(self, staged, timeout, python_version, **kwargs):
        return {"status": "SUCCESS", "wheel_count": 0}

    def execute_staged(self, staged, target_script, script_args, config, **kwargs):
        self.executed, self.run_kwargs = (target_script, script_args, config), kwargs
        return {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 1.0, "docker_used": True, "isolated": True,
                "dependency_install_status": "SKIPPED", "meta": {"peak_memory_bytes": 1}}


def test_the_run_gets_the_folder_and_the_shell_command_and_the_limits_of_the_protocol(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pilot, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(run_pilot, "resolve_memory_limit", lambda value: "7777m" if value == "50%" else value)
    paper, step = next((p, s) for p, s in _plan_entries() if s["paper_id"] == "cand_007")
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps([candidate_runs.corpus_entry(paper, step)]), encoding="utf-8")
    stager = Stager(tmp_path)
    record = run_pilot.run_paper("cand_007", tmp_path / "staging", stager=stager, pilot4=True, corpus_path=corpus,
                                 memory_limit=candidate_runs.MEMORY, cpus=candidate_runs.CPUS,
                                 run_timeout=candidate_runs.RUN_TIMEOUT_SECONDS, record_root=tmp_path / "records")
    config = stager.executed[2]
    assert stager.run_kwargs["command"][:2] == ["sh", "-c"] and "PYTHONPATH" in stager.run_kwargs["command"][2]
    assert (config.cpus, config.memory_limit, config.run_timeout_seconds) == (4.0, "7777m", 1800)
    assert record["timeout_override"]["requested"] == 1800


def test_each_candidate_is_run_once_a_command_that_is_not_runnable_is_not_run_and_the_results_are_kept(tmp_path):
    calls = []

    def runner(entry, corpus_path, record_root, staging_dir):
        calls.append(entry["paper_id"])
        folder = record_root / entry["paper_id"]
        folder.mkdir(parents=True)
        (folder / "stdout.log").write_text("x" * 100_000, encoding="utf-8")
        return {"k1_passed": entry["paper_id"] == "cand_001", "category": None, "log_line": "", "install_status": "INSTALLED",
                "run_status": "COMPLETED", "exit_code": 0, "duration_seconds": 1.0, "metric_lines": ["a: 0.5"]}

    results = candidate_runs.run_all(tmp_path / "runs", tmp_path / "staging", runner=runner)
    assert len(results) == 14 and len(calls) == 13 and "cand_013" not in calls
    by_id = {r["paper_id"]: r for r in results}
    assert by_id["cand_001"]["passed"] is True and by_id["cand_002"]["passed"] is False
    assert by_id["cand_013"]["category"] == "command_incomplete" and by_id["cand_013"]["passed"] is False
    log = (tmp_path / "runs" / "cand_001" / "stdout.log").read_text(encoding="utf-8")
    assert len(log) < 61_000 and "bytes cut" in log
    # a second call runs nothing: the results are kept
    assert len(candidate_runs.run_all(tmp_path / "runs", tmp_path / "staging", runner=runner)) == 14 and len(calls) == 13
    document = json.loads((tmp_path / "runs" / "evaluation.json").read_text(encoding="utf-8"))
    assert document["limits"]["run_timeout_seconds"] == 1800 and "not a success rate" in document["note"]


def test_a_candidate_with_a_record_but_no_result_is_not_run_again(tmp_path):
    (tmp_path / "runs" / "cand_001").mkdir(parents=True)
    (tmp_path / "runs" / "cand_001" / "pilot_record.json").write_text("{}", encoding="utf-8")
    calls = []

    def runner(entry, corpus_path, record_root, staging_dir):
        calls.append(entry["paper_id"])
        return candidate_runs.harness_result("x")

    results = candidate_runs.run_all(tmp_path / "runs", tmp_path / "staging", runner=runner, only={"cand_001"})
    assert calls == [] and results[0]["category"] == "harness" and "no second attempt" in results[0]["log_line"]
