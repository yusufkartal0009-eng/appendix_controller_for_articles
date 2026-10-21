"""Demo set (#421): the rules of docs/DEMO_SET.md, the K1 verdict, and the selection loop. No network and no Docker."""

import json

import pytest

from scripts import demo_set as ds
from tests.test_corpus_expansion import FENCE, LINK, Fetcher, _readme

PASSED = {"k1_passed": True, "category": None, "log_line": "", "metric_lines": ["acc: 0.9"]}
FAILED = {"k1_passed": False, "category": "run", "log_line": "Traceback", "metric_lines": []}


def test_the_pool_queries_are_the_eight_topics_of_the_document():
    assert len(ds.queries()) == 8
    assert ds.queries()[0] == "topic:scikit-learn arxiv.org in:readme language:Python archived:false fork:false size:<20000"
    assert [q.split()[0] for q in ds.queries()][-1] == "topic:reproducibility"


@pytest.mark.parametrize("line,expected", [
    ("accuracy: 0.9123", True), ("Test RMSE = 3.14", True), ("epoch 3 loss=0.5", True), ("AUC (macro): -0.25", True),
    ("accuracy: 91", False), ("done in 3 seconds", False), ("0.91", False), ("", False),
])
def test_a_numeric_metric_line_has_a_name_a_separator_and_a_decimal_number(line, expected):
    assert bool(ds.metric_lines(line)) is expected


def _record(**run):
    base = {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 3.0, "docker_used": True, "isolated": True,
            "dependency_install_status": "INSTALLED"}
    return {"stage": {"status": "STAGED"}, "run": {**base, **run}}


def _logs(folder, stdout="acc: 0.91\n", stderr="", install=""):
    (folder / "stdout.log").write_text(stdout, encoding="utf-8")
    (folder / "stderr.log").write_text(stderr, encoding="utf-8")
    (folder / "install.log").write_text(install, encoding="utf-8")


@pytest.mark.parametrize("run,stdout,stderr,install,category", [
    ({}, "acc: 0.91\n", "", "", None),
    ({"dependency_install_status": "SKIPPED"}, "acc: 0.91\n", "", "", None),
    ({"dependency_install_status": "FAILED"}, "acc: 0.91\n", "", "ERROR: no matching distribution\n", "install"),
    ({"dependency_install_status": "UNKNOWN"}, "acc: 0.91\n", "", "", "install"),
    ({"status": "TIMEOUT", "exit_code": 137}, "", "", "", "timeout"),
    ({"status": "OOM_KILLED", "exit_code": 137}, "", "", "", "memory"),
    ({"status": "FAILED", "exit_code": 1}, "", "Traceback\nValueError: bad\n", "", "run"),
    ({}, "all done\n", "", "", "no_metric_line"),
    ({"isolated": False}, "acc: 0.91\n", "", "", "harness"),
])
def test_k1_verdict_and_category(tmp_path, run, stdout, stderr, install, category):
    _logs(tmp_path, stdout, stderr, install)
    result = ds.classify_run(_record(**run), tmp_path)
    assert result["category"] == category and result["k1_passed"] is (category is None)


def test_the_deciding_log_line_is_the_last_line_of_the_log(tmp_path):
    _logs(tmp_path, stderr="Traceback\nValueError: bad\n")
    assert ds.classify_run(_record(status="FAILED", exit_code=1), tmp_path)["log_line"] == "ValueError: bad"


def test_a_staging_failure_and_a_missing_run_phase_are_not_passes(tmp_path):
    staging = ds.classify_run({"stage": {"status": "FAILED", "error": "clone failed"}}, tmp_path)
    assert staging["category"] == "staging" and staging["log_line"] == "clone failed"
    assert ds.classify_run({"stage": {"status": "STAGED"}}, tmp_path)["category"] == "harness"


def test_a_stated_size_in_the_readme_does_not_reject_a_candidate_and_rules_get_the_new_names():
    big = {"readme": _readme("python train.py", "The data is 2 GB.")}
    assert ds.static_check("o/r", Fetcher({"o/r": big}), set(), set(), set(), set())["passed"]
    result = ds.static_check("o/r", Fetcher({"o/r": {"readme": _readme("python train.py", "Needs a GPU.")}}), set(), set(), set(), set())
    assert result["failed_rule"] == "S3"
    result = ds.static_check("o/r", Fetcher({"o/r": {"readme": f"{FENCE}\nls\n{FENCE}\n{LINK}"}}), set(), set(), set(), set())
    assert result["failed_rule"] == "S2"


def test_sanitize_replaces_the_repository_and_the_home_paths():
    text = rf"{ds.project_root}\data and {ds.project_root.as_posix()}/x and {ds.Path.home().as_posix()}/y"
    cleaned = ds.sanitize(text)
    assert "<REPO>" in cleaned and "<HOME>" in cleaned and str(ds.Path.home()) not in cleaned


def _select(tmp_path, names, results, **limits):
    calls = []

    def runner(entry, corpus, record_root):
        calls.append(entry["paper_id"])
        assert any(e["paper_id"] == entry["paper_id"] for e in json.loads(corpus.read_text(encoding="utf-8")))
        return dict(results[len(calls) - 1])

    summary = ds.select_and_run(names, Fetcher({n: {} for n in names}), set(), set(), tmp_path, runner, **limits)
    return summary, calls, json.loads((tmp_path / "evaluation.json").read_text(encoding="utf-8"))


def test_the_loop_stops_at_five_passes_and_records_every_candidate(tmp_path):
    names = [f"o/r{i}" for i in range(9)]
    results = [PASSED, FAILED, PASSED, PASSED, FAILED, PASSED, PASSED, PASSED, PASSED]
    summary, calls, document = _select(tmp_path, names, results)
    assert summary == {"evaluated": 7, "runs": 7, "k1_passed": 5, "stopped_because": "five_passed"}
    assert calls[0] == "demo_001" and len(document["candidates"]) == 7
    assert document["candidates"][1]["k1"]["category"] == "run"
    assert len(json.loads((tmp_path / "papers.json").read_text(encoding="utf-8"))) == 7


def test_the_loop_stops_at_the_run_limit_and_at_the_time_limit(tmp_path):
    names = [f"o/r{i}" for i in range(6)]
    summary, calls, _ = _select(tmp_path, names, [FAILED] * 6, max_runs=3)
    assert summary["stopped_because"] == "thirty_runs" and len(calls) == 3
    ticks = iter(range(0, 1000, 10))
    summary, calls, _ = _select(tmp_path / "t" if (tmp_path / "t").mkdir() is None else tmp_path, names, [FAILED] * 6,
                                clock=lambda: next(ticks), max_seconds=25)
    assert summary["stopped_because"] == "time_limit" and len(calls) == 2


def test_a_candidate_that_fails_a_static_rule_is_not_run(tmp_path):
    fetcher = Fetcher({"o/a": {"readme": f"{FENCE}\nls\n{FENCE}\n{LINK}"}, "o/b": {}})
    calls = []
    summary = ds.select_and_run(["o/a", "o/b"], fetcher, set(), set(), tmp_path, lambda e, c, r: calls.append(e) or PASSED)
    document = json.loads((tmp_path / "evaluation.json").read_text(encoding="utf-8"))
    assert summary["runs"] == 1 and document["candidates"][0]["failed_rule"] == "S2" and "k1" not in document["candidates"][0]


def test_the_same_repository_or_paper_is_not_taken_twice(tmp_path):
    fetcher = Fetcher({"o/a": {}, "O/A": {}})
    summary = ds.select_and_run(["o/a", "O/A"], fetcher, set(), set(), tmp_path, lambda e, c, r: PASSED)
    assert summary["runs"] == 1
