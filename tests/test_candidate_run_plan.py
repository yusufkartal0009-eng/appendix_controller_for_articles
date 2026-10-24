"""The run plan of the candidate runs covers exactly the candidates the protocol names, and the protocol shows its commands (#437)."""

import json
import posixpath
import re

from src.config import DATA_DIR, PROJECT_ROOT

CANDIDATES = DATA_DIR / "candidates"
RUNNABLE_STATUSES = {"ready", "fixable", "two_step"}


def _plan():
    return json.loads((CANDIDATES / "run_plan.json").read_text(encoding="utf-8"))["runs"]


def test_the_plan_covers_exactly_the_candidates_of_the_three_statuses():
    papers = json.loads((CANDIDATES / "papers.json").read_text(encoding="utf-8"))
    expected = [p["paper_id"] for p in papers if p["status"] in RUNNABLE_STATUSES]
    assert [run["paper_id"] for run in _plan()] == expected and len(expected) == 14


def test_a_python_command_runs_the_target_script_of_the_candidate():
    papers = {p["paper_id"]: p for p in json.loads((CANDIDATES / "papers.json").read_text(encoding="utf-8"))}
    for run in _plan():
        if run["shell"]:
            continue
        script = run["command"].split()[1]
        assert posixpath.join(run["working_dir"], script) == papers[run["paper_id"]]["target_script"], run["paper_id"]


def test_a_command_that_is_not_run_says_why_and_the_others_have_no_placeholder():
    for run in _plan():
        if run["runnable"]:
            assert "..." not in run["command"] and "<" not in run["command"].replace("$(", ""), run["paper_id"]
        else:
            assert run["not_runnable_reason"].startswith("command_incomplete")


def test_the_protocol_shows_every_command_of_the_plan():
    doc = (PROJECT_ROOT / "docs" / "CANDIDATE_RUNS.md").read_text(encoding="utf-8")
    for run in _plan():
        assert f"| {run['paper_id']} | `{run['command']}` |" in doc, run["paper_id"]
    assert re.search(r"1800 s", doc)
