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


class FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def find(self, needle):
        return [i for i, t in enumerate(self.pages, start=1) if needle in t]

    def page(self, number):
        return self.pages[number - 1]


def test_number_forms_cover_the_leading_zero_and_the_percentage():
    assert [f for f, _ in ds.number_forms("0.9123")] == ["0.9123", ".9123", "91.23"]
    assert [f for f, _ in ds.number_forms("3.14")] == ["3.14"]


def test_a_printed_number_is_located_on_the_pages_of_the_paper_with_the_table_captions():
    pdf = FakePdf(["intro 0.5", "Table 2. Results\nours 91.23 base 80.1", "Table 3. Ablation"])
    hits = ds.locate_numbers(["accuracy: 0.9123", "loss=7.77"], pdf)
    assert hits[0]["pages"] == [2] and hits[0]["captions"] == ["Table 2"] and "percentage" in hits[0]["form"]
    assert hits[1]["pages"] == [] and hits[1]["form"] is None


def test_the_results_section_lists_every_run_and_only_the_passed_papers_in_detail():
    document = {"written_at": "T", "stopped_because": "five_passed", "evaluated": 3, "pool_size": 9, "candidates": [
        {"full_name": "o/a", "failed_rule": "S2", "passed": False},
        {"full_name": "o/b", "failed_rule": None, "passed": True, "paper_id": "demo_001",
         "k1": {"k1_passed": True, "category": None, "log_line": "", "install_status": "INSTALLED", "run_status": "COMPLETED",
                "exit_code": 0, "duration_seconds": 4.2, "metric_lines": ["acc: 0.5"]}},
        {"full_name": "o/c", "failed_rule": None, "passed": True, "paper_id": "demo_002",
         "k1": {"k1_passed": False, "category": "run", "log_line": "a|b", "install_status": "INSTALLED", "run_status": "FAILED",
                "exit_code": 1, "duration_seconds": 1.0, "metric_lines": []}}]}
    papers = [{"paper_id": i, "title": f"T{i}", "paper_url": "u", "repo_url": "r", "repo_commit": "c", "license": "MIT",
               "run_command": "python x.py"} for i in ("demo_001", "demo_002")]
    text = ds.render_results(document, papers, {"demo_001": ds.locate_numbers(["acc: 0.5"], FakePdf(["Table 1\n0.5"]))})
    assert "Candidates that passed K1: 1" in text and "no number below is a success rate" in text
    assert "#### demo_001: Tdemo_001" in text and "#### demo_002" not in text
    assert "| demo_002 | `o/c` |" in text and r"a\|b" in text and "| S2 | 1 |" in text


def test_output_numbers_are_the_distinct_decimals_with_three_decimals_or_more():
    text = "RMSE 0.6620 and 0.6620 again\n3.5 1.123456 2024.05 -0.250 v1.2.3.4567"
    assert ds.output_numbers(text) == ["0.6620", "1.123456", "-0.250"]


def test_the_results_section_counts_the_output_numbers_found_in_the_paper():
    document = {"written_at": "T", "stopped_because": "time_limit", "evaluated": 1, "candidates": [
        {"full_name": "o/b", "failed_rule": None, "paper_id": "demo_001",
         "k1": {"k1_passed": True, "category": None, "log_line": "", "install_status": "SKIPPED", "run_status": "COMPLETED",
                "exit_code": 0, "duration_seconds": 1.0, "metric_lines": ["a: 0.5"]}}]}
    papers = [{"paper_id": "demo_001", "title": "T", "paper_url": "u", "repo_url": "r", "repo_commit": "c", "license": "MIT",
               "run_command": "python x.py"}]
    pdf = FakePdf(["Table 1\n0.6620"])
    hits = ds.locate_numbers([f"= {n}" for n in ds.output_numbers("rmse 0.6620 0.7173")], pdf)
    text = ds.render_results(document, papers, {"demo_001": []}, {"demo_001": hits})
    assert "printed anywhere in `stdout.log`: 2; found in the paper's text by the same string match: 1." in text
    assert "| 0.6620 | 0.6620 (as printed) | 1 | Table 1 |" in text
