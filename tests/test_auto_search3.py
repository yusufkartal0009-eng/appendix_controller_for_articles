"""Automatic search, round 3 (#471): the pool, the numbers of an output (K2), the match, and the resumable walk.
No network and no Docker."""

import json

import pytest

from scripts import auto_search3 as a3
from tests.test_corpus_expansion import FENCE, LINK, Fetcher

PASSED = {"k1_passed": True, "category": None, "log_line": "", "install_status": "INSTALLED", "run_status": "COMPLETED",
          "exit_code": 0, "duration_seconds": 3.0, "metric_lines": ["acc: 0.9123"]}
FAILED = {"k1_passed": False, "category": "run", "log_line": "Traceback", "install_status": "INSTALLED", "run_status": "FAILED",
          "exit_code": 1, "duration_seconds": 1.0, "metric_lines": []}
K2_PASS = {"passed": True, "matches": []}
K2_FAIL = {"passed": False, "matches": []}


def numbers(text):
    return [n["number"] for n in a3.meaningful_numbers(text)]


# ---- the pool


def test_the_queries_hold_the_common_part_and_the_topic_in_the_order_of_the_document():
    stage1 = a3.queries(1)
    assert len(stage1) == 16 and len(a3.queries(2)) == 16
    assert stage1[0] == "arxiv.org in:readme language:Python archived:false fork:false size:<30000 topic:statistics"
    assert stage1[-1].endswith("topic:probabilistic-programming") and a3.queries(2)[-1].endswith("topic:nlp")


def test_the_pool_removes_earlier_rounds_orders_by_hash_and_stores_each_stage_once(tmp_path):
    fetcher = Fetcher({"o/a": {}, "o/b": {}, "O/Old": {}, "o/c": {}})
    pool = a3.command_pool(fetcher, tmp_path, 1, {"o/old"}, pause=0, sleep=lambda s: None)
    names = [c["full_name"] for c in pool["candidates_in_order"]]
    assert "O/Old" not in names and sorted(names) == ["o/a", "o/b", "o/c"]
    hashes = [c["hash"] for c in pool["candidates_in_order"]]
    assert hashes == sorted(hashes) and pool["stages"]["1"]["removed_as_earlier_round"] == ["o/old"]
    assert len(pool["stages"]["1"]["searches"]) == 16
    with pytest.raises(ValueError, match="already stored"):
        a3.command_pool(fetcher, tmp_path, 1, set(), pause=0, sleep=lambda s: None)
    second = a3.command_pool(Fetcher({"o/a": {}, "o/d": {}}), tmp_path, 2, set(), pause=0, sleep=lambda s: None)
    assert [c["full_name"] for c in second["candidates_in_order"]][-1:] == ["o/d"]
    assert [c["stage"] for c in second["candidates_in_order"]] == [1, 1, 1, 2]


def test_earlier_round_repos_reads_the_demo_pool_the_candidates_and_the_seed(tmp_path):
    (tmp_path / "data" / "demo_set").mkdir(parents=True)
    (tmp_path / "data" / "candidates" / "round2").mkdir(parents=True)
    (tmp_path / "data" / "corpus_expansion").mkdir(parents=True)
    (tmp_path / "data" / "demo_set" / "pool.json").write_text(json.dumps({"candidates_in_order": [{"full_name": "A/One"}]}), encoding="utf-8")
    (tmp_path / "data" / "candidates" / "round2" / "x.json").write_text(
        json.dumps({"repo_url": "https://github.com/B/Two.git", "full_name": "C/Three"}), encoding="utf-8")
    (tmp_path / "data" / "seed_papers.json").write_text(json.dumps([{"repo_url": "https://github.com/D/Four"}]), encoding="utf-8")
    (tmp_path / "data" / "corpus_expansion" / "papers.json").write_text("[]", encoding="utf-8")
    assert a3.earlier_round_repos(tmp_path) >= {"a/one", "b/two", "c/three", "d/four"}


# ---- K2: the numbers of an output


@pytest.mark.parametrize("text,expected", [
    ("accuracy 0.9123", ["0.9123"]),
    ("loss=0.12345 and 3.14159", ["0.12345", "3.14159"]),
    ("RMSE -0.8123", ["-0.8123"]),
    ("score 1,234,567 total", ["1234567"]),
    ("score 12,345.67", ["12345.67"]),
    ("share 95.5%", ["95.5"]),
])
def test_decimals_negatives_and_thousands_are_numbers_in_their_canonical_form(text, expected):
    assert numbers(text) == expected


@pytest.mark.parametrize("text", [
    "year 2019", "in 1999 and 2100", "numpy 1.26.4", "version 2.1", "v3.4", "Python 3.11.9", "192.168.100.200",
    "2026-10-25 and 25/10/2026", "at 12:30:05", "12:30:05.123", "line 1234", "File x.py, line 4321, in f", "[1234]", "#1234",
    "epoch 1000/5000", "step 12345", "seed 12345", "x.py:1234: error", "address 0x1f3a2b",
])
def test_years_versions_dates_times_indices_and_line_numbers_are_not_meaningful(text):
    assert numbers(text) == []


@pytest.mark.parametrize("text", ["0.5", "0.50", "12", "5%", "100", "5000", "0.0012", "7", "1.5e-05", "0.91s", "23ms"])
def test_a_number_needs_three_significant_digits_and_a_trailing_unit_is_not_a_result(text):
    assert numbers(text) == []


def test_significant_digits_ignore_sign_separators_leading_zeros_and_integer_trailing_zeros():
    assert [a3.significant_digits(c) for c in ("1234", "100", "0.5", "0.500", "-0.00123", "12345.6", "1200")] == [4, 1, 1, 3, 3, 6, 2]


def test_a_number_is_listed_once_in_the_order_of_its_first_line():
    found = a3.meaningful_numbers("a 0.9123\nb 0.8123\nc 0.9123 again\n")
    assert [n["number"] for n in found] == ["0.9123", "0.8123"] and found[0]["line"] == "a 0.9123"


def test_a_very_long_output_is_cut_at_the_limit():
    text = "\n".join(f"v {i}.123" for i in range(1, 30))
    assert len(a3.meaningful_numbers(text, limit=5)) == 5


# ---- K2: the match


def find(number, text):
    return a3.paper_pattern(number).search(text)


@pytest.mark.parametrize("number,text,ok", [
    ("0.9123", "accuracy 0.9123 on test", True),
    ("0.9123", "accuracy 0.91230 on test", False),            # not the same spelling: a longer number
    ("0.912", "accuracy 0.9123", False),
    ("1.52", "of 21.52 units", False),                         # not inside a longer number
    ("1.52", "version 1.52.3", False),
    ("1.523", "value (1.523), then", True),
    ("0.5", "x 10.5", False),
    ("0.8123", "got .8123 here", True),                        # the leading zero may be dropped
    ("0.8123", "got 0,8123 here", True),                       # a decimal comma
    ("-0.8123", "delta −0.8123", True),                   # a minus sign
    ("-0.8123", "delta -0.8123", True),
    ("-0.8123", "delta 0.8123", False),                        # the sign has to be there
    ("0.8123", "delta -0.8123", False),                        # and a positive number is not read inside a negative one
    ("1234567", "n = 1,234,567 rows", True),                   # thousands separators
    ("1234567", "n = 1234567 rows", True),
    ("1234567", "n = 1 234 567 rows", False),                  # a plain space is not a separator
    ("12345.67", "12,345.67", True),
    ("234.5", "of 1,234.5 items", False),                      # the tail of a number with a thousands group
    ("0.5123", "[0.5123,0.6123]", True),
    ("95.5", "reached 95.5% accuracy", True),
    ("1.5e-05", "lr 1.5e-05", True),
])
def test_the_match_is_the_same_spelling_and_never_inside_a_longer_number(number, text, ok):
    assert bool(find(number, text)) is ok


def test_a_split_number_of_the_pdf_text_is_repaired_before_the_match():
    hits = a3.match_numbers([{"number": "0.8501", "line": "x", "percent": False}], ["Table 1\nacc 0 .8501 here"])
    assert hits and hits[0]["pages"][0]["page"] == 1


PAGES = ["Introduction 0.9123 appears here", "Table 1. Results\nmodel A 0.9123 0.8456\nmodel B 0.7123", "References"]


def test_k2_passes_with_two_different_numbers_one_on_a_table_page():
    result = a3.evaluate_k2("acc 0.9123\nf1 0.8456\n", PAGES)
    assert result["passed"] and result["numbers_found_in_paper"] == 2 and result["numbers_found_on_table_page"] == 2
    first = result["matches"][0]
    assert first["number"] == "0.9123" and [p["page"] for p in first["pages"]] == [1, 2]
    assert first["on_table_page"] and first["pages"][1]["line"] == "model A 0.9123 0.8456"


def test_k2_needs_two_different_numbers():
    assert not a3.evaluate_k2("acc 0.9123\nagain 0.9123\n", PAGES)["passed"]
    assert not a3.evaluate_k2("acc 0.9123\n", PAGES)["passed"]


def test_k2_needs_a_number_on_a_table_page():
    pages = ["Table 1. Results\nnothing", "values 0.9123 and 0.8456", "end"]
    result = a3.evaluate_k2("acc 0.9123\nf1 0.8456\n", pages)
    assert result["numbers_found_in_paper"] == 2 and not result["passed"]


def test_k2_does_not_pass_when_the_numbers_are_not_in_the_paper():
    assert not a3.evaluate_k2("acc 0.1111\nf1 0.2222\n", PAGES)["passed"]


def test_k2_for_a_run_reads_stdout_log_and_the_stored_pdf(tmp_path, monkeypatch):
    (tmp_path / "stdout.log").write_text("acc 0.9123\nf1 0.8456\n", encoding="utf-8")
    monkeypatch.setattr(a3, "fetch_pdf", lambda arxiv_id, throttle, folder: tmp_path / "p.pdf")
    monkeypatch.setattr(a3, "extract_pdf_text", lambda path, cache_dir=None: type("P", (), {"pages": PAGES})())
    result = a3.k2_for_run({"paper_url": "https://arxiv.org/abs/2101.00001"}, tmp_path)
    assert result["passed"] and result["arxiv_id"] == "2101.00001"


def test_k2_for_a_run_whose_paper_cannot_be_read_is_not_a_pass(tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("no network")

    monkeypatch.setattr(a3, "fetch_pdf", broken)
    result = a3.k2_for_run({"paper_url": "https://arxiv.org/abs/2101.00001"}, tmp_path)
    assert not result["passed"] and "no network" in result["error"]


def test_the_throttle_waits_so_that_requests_are_three_seconds_apart():
    now, slept = [0.0], []
    throttle = a3.Throttle(3.0, clock=lambda: now[0], sleep=lambda s: slept.append(s) or now.__setitem__(0, now[0] + s))
    throttle.wait()
    now[0] += 1.0
    throttle.wait()
    throttle.wait()
    assert slept == [2.0, 3.0]


def test_long_logs_keep_the_head_and_the_tail(tmp_path):
    (tmp_path / "stdout.log").write_bytes(b"a" * 100_000 + b"z" * 20_000)
    (tmp_path / "short.log").write_bytes(b"short")
    a3.shorten_logs(tmp_path)
    kept = (tmp_path / "stdout.log").read_bytes()
    assert kept.startswith(b"a" * 100) and kept.endswith(b"z" * 100) and b"bytes cut" in kept and len(kept) < 52_000
    assert (tmp_path / "short.log").read_bytes() == b"short"


# ---- the walk


def search(tmp_path, names, results, k2=None, **limits):
    calls = []

    def runner(entry, corpus, record_root):
        calls.append(entry["paper_id"])
        assert any(e["paper_id"] == entry["paper_id"] for e in json.loads(corpus.read_text(encoding="utf-8")))
        return dict(results[len(calls) - 1])

    k2_calls = []

    def k2_runner(entry, record_dir):
        k2_calls.append(entry["paper_id"])
        return dict((k2 or [K2_FAIL] * 50)[len(k2_calls) - 1])

    fetcher = Fetcher({n: {} for n in names})
    fetcher.ids = {n: i + 1 for i, n in enumerate(names)}  # every start sees the same paper for the same repository
    walk = a3.Search(names, fetcher, set(), set(), tmp_path, runner, k2_runner,
                     now=limits.pop("now", lambda: 1000.0), free=limits.pop("free", lambda: 10**12), started_at=1000.0, **limits)
    return walk, calls, k2_calls


def stored(tmp_path):
    return json.loads((tmp_path / "evaluation.json").read_text(encoding="utf-8"))


def test_the_walk_stops_when_eight_candidates_passed_both_tests(tmp_path):
    names = [f"o/r{i}" for i in range(14)]
    results = [PASSED, FAILED, PASSED, PASSED, PASSED, PASSED, PASSED, PASSED, PASSED, PASSED, PASSED, PASSED]
    k2 = [K2_PASS] * 12  # K2 is computed for the runs that completed, so the failed run uses none
    walk, calls, _ = search(tmp_path, names, results, k2, max_both=3)
    summary = walk.run()
    assert summary["stopped_because"] == "eight_passed_both" and summary["both_passed"] == 3
    assert calls[0] == "a3_001" and summary["runs"] == 4 and summary["k1_passed"] == 3
    document = stored(tmp_path)
    assert document["stopped_because"] == "eight_passed_both" and document["candidates"][0]["k2"]["passed"]


def test_k2_is_computed_only_for_runs_that_completed_with_exit_code_zero(tmp_path):
    walk, _, k2_calls = search(tmp_path, ["o/a", "o/b", "o/c"], [FAILED, PASSED, {**FAILED, "category": "harness"}])
    walk.run()
    assert k2_calls == ["a3_002"]
    document = stored(tmp_path)
    assert document["candidates"][0]["k2"] is None and document["candidates"][1]["k2"] == K2_FAIL


@pytest.mark.parametrize("limits,reason", [
    ({"max_runs": 2}, "run_limit_150"),
    ({"max_seconds": 5.0, "now": lambda: 2000.0}, "time_limit_9h"),
    ({"free": lambda: 10 * 1024**3}, "disk_below_30gb"),
])
def test_the_walk_stops_at_the_run_limit_the_time_limit_and_the_disk_limit(tmp_path, limits, reason):
    walk, calls, _ = search(tmp_path, [f"o/r{i}" for i in range(6)], [FAILED] * 6, **limits)
    summary = walk.run()
    assert summary["stopped_because"] == reason
    assert len(calls) == (2 if reason == "run_limit_150" else 0)


def test_a_used_up_pool_is_extended_with_the_next_stage_and_then_ends(tmp_path):
    fetcher_names = {"o/a": {}, "o/b": {}}
    later = iter([["o/c"], []])
    calls = []
    walk = a3.Search(["o/a"], Fetcher(fetcher_names | {"o/c": {}}), set(), set(), tmp_path,
                     lambda e, c, r: calls.append(e["full_name"] if "full_name" in e else e["paper_id"]) or dict(FAILED),
                     lambda e, d: K2_FAIL, extend_pool=lambda: next(later), started_at=1000.0, now=lambda: 1000.0, free=lambda: 10**12)
    summary = walk.run()
    assert summary["stopped_because"] == "pool_used_up" and summary["runs"] == 2 and len(calls) == 2


def test_a_candidate_that_fails_a_static_rule_is_not_run_and_a_static_error_does_not_stop_the_walk(tmp_path):
    class Flaky(Fetcher):
        def meta(self, full_name):
            if full_name == "o/err":
                raise OSError("network down")
            return super().meta(full_name)

    repos = {"o/err": {}, "o/bad": {"readme": f"{FENCE}\nls\n{FENCE}\n{LINK}"}, "o/ok": {}}
    calls = []
    walk = a3.Search(list(repos), Flaky(repos), set(), set(), tmp_path, lambda e, c, r: calls.append(e) or dict(PASSED),
                     lambda e, d: K2_FAIL, started_at=1000.0, now=lambda: 1000.0, free=lambda: 10**12)
    summary = walk.run()
    rules = {c["full_name"]: c["failed_rule"] for c in stored(tmp_path)["candidates"]}
    assert rules == {"o/err": "static_error", "o/bad": "S2", "o/ok": None} and summary["runs"] == 1 and len(calls) == 1


def test_the_same_repository_or_paper_is_not_taken_twice(tmp_path):
    walk = a3.Search(["o/a", "O/A"], Fetcher({"o/a": {}, "O/A": {}}), set(), set(), tmp_path, lambda e, c, r: dict(PASSED),
                     lambda e, d: K2_FAIL, started_at=1000.0, now=lambda: 1000.0, free=lambda: 10**12)
    assert walk.run()["runs"] == 1


def test_a_second_start_skips_the_candidates_that_have_a_result_and_runs_a_staged_one_again(tmp_path):
    names = [f"o/r{i}" for i in range(5)]
    first, calls, _ = search(tmp_path, names, [FAILED, PASSED, FAILED], max_runs=2)
    first.run()
    assert calls == ["a3_001", "a3_002"]
    # a candidate that was staged but never ran: it passed S1 to S6 and has no result
    document = stored(tmp_path)
    assert len(document["candidates"]) >= 2 and document["started_epoch"] == 1000.0
    again, calls_again, _ = search(tmp_path, names, [FAILED, FAILED, FAILED], now=lambda: 1500.0)
    again.run()
    done = [c["paper_id"] for c in stored(tmp_path)["candidates"] if c.get("k1")]
    assert done == sorted(set(done)) and len(done) == 5 and len(calls_again) == 3
    assert calls_again[0] not in calls and stored(tmp_path)["started_epoch"] == 1000.0


def test_an_earlier_partial_record_of_a_candidate_without_a_result_is_removed_before_its_run(tmp_path):
    names = ["o/a"]
    walk, _, _ = search(tmp_path, names, [PASSED])
    partial = tmp_path / "runs" / "a3_001"
    partial.mkdir(parents=True)
    (partial / "stale.txt").write_text("x", encoding="utf-8")
    seen = []
    original = walk.runner
    walk.runner = lambda e, c, r: seen.append((r / e["paper_id"]).exists()) or original(e, c, r)
    walk.run()
    assert seen == [False]


# ---- the report


def test_the_report_has_the_counts_the_intervals_and_the_match_candidates(tmp_path):
    names = [f"o/r{i}" for i in range(3)]
    match = {"passed": True, "numbers_in_output": 4, "numbers_found_in_paper": 2, "numbers_found_on_table_page": 2,
             "matches": [{"number": "0.9123", "line": "acc 0.9123", "pages": [{"page": 2, "table_page": True, "line": "model A 0.9123"}],
                          "on_table_page": True}]}
    walk, _, _ = search(tmp_path, names, [PASSED, FAILED, PASSED], [match, K2_FAIL])
    walk.run()
    text = a3.command_report(tmp_path)
    assert "Passed K1: 2 of 3 (Wilson 95%:" in text and "Passed both K1 and K2: 1 of 3" in text
    assert "not a success rate" in text and "#### a3_001" in text and "| 0.9123 | `acc 0.9123` | 2 | yes |" in text
    assert "`pool_used_up`" in text


def test_the_report_says_when_no_candidate_passed_k2(tmp_path):
    walk, _, _ = search(tmp_path, ["o/a"], [FAILED])
    walk.run()
    assert "No candidate passed K2." in a3.command_report(tmp_path)
