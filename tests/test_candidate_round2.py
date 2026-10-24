"""The repair round of the candidates: the rules of docs/CANDIDATE_RUNS_ROUND2.md as code (#457)."""

import json

import pytest

from scripts import candidate_round2 as r2
from scripts import candidate_runs

REPAIR = {"repair_number": 1, "kind": "requirements", "reason": "a package is missing", "log_line": "No module named 'igraph'",
          "change": "add python-igraph"}


def _attempt(number=1, setup=None, repairs=None):
    return {"attempt": number, "setup": setup if setup is not None else {"extra_requirements": ["python-igraph"]},
            "repairs": [dict(REPAIR, repair_number=number)] if repairs is None else repairs}


def test_a_valid_first_repair_passes_validation():
    r2.validate_attempt({"attempts": []}, _attempt(), risky=False)


@pytest.mark.parametrize("bad, message", [
    ({"setup": {"writable_repo": True}}, "not allowed"),
    ({"setup": {"extra_requirements": ["x"], "env": {"A": "1"}}}, "no repair of the attempt explains"),
    ({"repairs": []}, "at least one repair"),
])
def test_a_forbidden_or_unexplained_change_is_refused(bad, message):
    with pytest.raises(ValueError, match=message):
        r2.validate_attempt({"attempts": []}, {**_attempt(), **bad}, risky=False)


def test_a_repair_needs_a_log_line_and_a_known_kind():
    with pytest.raises(ValueError, match="log line"):
        r2.validate_attempt({"attempts": []}, _attempt(repairs=[{**REPAIR, "log_line": ""}]), risky=False)
    with pytest.raises(ValueError, match="kind"):
        r2.validate_attempt({"attempts": []}, _attempt(repairs=[{**REPAIR, "kind": "edit_source"}]), risky=False)


def test_at_most_two_repairs_and_the_earlier_attempts_must_have_failed_with_a_result():
    with pytest.raises(ValueError, match="at most 2"):
        r2.validate_attempt({"attempts": []}, _attempt(number=3), risky=False)
    with pytest.raises(ValueError, match="missing"):
        r2.validate_attempt({"attempts": []}, _attempt(number=2), risky=False)
    first = {**_attempt(1), "result": {"passed": False}}
    r2.validate_attempt({"attempts": [first]}, _attempt(number=2), risky=False)
    with pytest.raises(ValueError, match="nothing to repair"):
        r2.validate_attempt({"attempts": [{**first, "result": {"passed": True}}]}, _attempt(number=2), risky=False)
    with pytest.raises(ValueError, match="no result yet"):
        r2.validate_attempt({"attempts": [_attempt(1)]}, _attempt(number=2), risky=False)


def test_attempt_zero_exists_only_for_a_risky_candidate():
    with pytest.raises(ValueError, match="attempt 0"):
        r2.validate_attempt({"attempts": []}, _attempt(number=0, repairs=[]), risky=False)
    r2.validate_attempt({"attempts": []}, {"attempt": 0, "setup": {"data": []}, "repairs": []}, risky=True)


def test_the_command_gets_the_redirect_arguments_and_a_moved_folder_rebases_the_script():
    step = {"command": "python run_sweep.py --max-runs 8", "working_dir": "research", "shell": False}
    assert r2.effective_command(step, "research/run_sweep.py", {}) == ("python run_sweep.py --max-runs 8", "research")
    assert r2.effective_command(step, "research/run_sweep.py", {"args_add": ["-o", "/workspace/output"]})[0].endswith(
        "-o /workspace/output")
    command, folder = r2.effective_command(step, "research/run_sweep.py", {"working_dir": ""})
    assert (command, folder) == ("python research/run_sweep.py --max-runs 8", "")


def test_run_attempt_records_the_attempt_and_never_runs_it_twice(tmp_path):
    plan = candidate_runs.load_plan()
    paper_id = next(p["paper_id"] for p, s in plan if s["runnable"] and not s["shell"])
    log = {"paper_id": paper_id, "round": 2, "attempts": [_attempt()]}
    r2.write_log(log, tmp_path)

    def runner(entry, correction, corpus_path, record_root, staging_dir):
        (record_root / paper_id).mkdir(parents=True)
        (record_root / paper_id / "stdout.log").write_text("accuracy: 0.912\n", encoding="utf-8")
        assert correction["extra_requirements"] == ["python-igraph"] and correction["changes"][0]["log_line"]
        return {"k1_passed": True, "category": None, "log_line": "", "metric_lines": ["accuracy: 0.912"]}

    attempt = r2.run_attempt(paper_id, 1, runner=runner, root=tmp_path, staging_dir=tmp_path / "s")
    assert attempt["result"]["passed"] is True and (tmp_path / paper_id / "attempt_1" / "stdout.log").is_file()
    assert json.loads(r2.log_path(paper_id, tmp_path).read_text())["attempts"][0]["result"]["passed"] is True
    assert not (tmp_path / paper_id / "_work_1").exists()
    with pytest.raises(ValueError, match="already has a result"):
        r2.run_attempt(paper_id, 1, runner=runner, root=tmp_path, staging_dir=tmp_path / "s")
