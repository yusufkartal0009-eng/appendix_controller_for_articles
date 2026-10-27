"""Automatic search, round 4 (#517): K2 v2 (scale conversion, rounding, separators, the chance guard), its controls, the pool
of stages 8 and 9, and the walk with both K2 results. No network and no Docker."""

import json
from pathlib import Path

import pytest

from scripts import auto_search3 as a3
from scripts import auto_search4 as a4
from tests.test_auto_search3 import FAILED, PASSED
from tests.test_corpus_expansion import Fetcher

ROOT = Path(__file__).resolve().parent.parent
TABLE = "Table 2: Results on the Bank dataset\n"


def page(*lines, table=True):
    return (TABLE if table else "") + "\n".join(lines)


def v2(output, *pages):
    return a4.evaluate_k2v2(output, list(pages))


def found(result):
    return {h["number"]: h["variant"] for h in result["matches"]}


# ---- the spellings


def test_a_fraction_is_searched_as_a_percent_and_a_percent_as_a_fraction():
    assert dict(a4.spellings("0.8886")) == {"same": "0.8886", "x100": "88.86", "x100+round3": "88.9", "same+round3": "0.889"}
    assert dict(a4.spellings("93.3"))["div100"] == "0.933"
    assert [v for v, _ in a4.spellings("1234.5")] == ["same", "same+round3"]  # outside 0..100: no conversion


def test_the_conversion_ranges_are_a_fraction_up_to_one_and_a_percent_above_one_up_to_one_hundred():
    assert "x100" in dict(a4.spellings("0.933")) and "x100" in dict(a4.spellings("-0.933"))
    assert "div100" not in dict(a4.spellings("0.933")) and "x100" not in dict(a4.spellings("93.3"))
    assert "div100" in dict(a4.spellings("100.0")) and "div100" not in dict(a4.spellings("100.5"))
    assert list(dict(a4.spellings("1.2e-05"))) == ["same"]  # a number in exponent form is only searched as printed


def test_rounding_is_half_up_to_three_significant_digits_and_only_for_longer_decimals():
    assert a4.round_significant("0.8886") == "0.889" and a4.round_significant("88.865") == "88.9"
    assert a4.round_significant("0.000123456") == "0.000123"
    assert dict(a4.spellings("0.933")) == {"same": "0.933", "x100": "93.3"}  # three digits: nothing to round
    assert "same+round3" not in dict(a4.spellings("12345"))  # an integer is not rounded


def test_a_decimal_comma_of_the_output_is_read_as_a_decimal_point_and_a_list_is_left_alone():
    assert a4.normalize_output("auroc 0,8886 and 88,86") == "auroc 0.8886 and 88.86"
    assert a4.normalize_output("size 1,234 and 12,345,678") == "size 1,234 and 12,345,678"  # thousands separators
    assert a4.normalize_output("values 10,20,30") == "values 10,20,30"


# ---- the match

PAPER_TABLE = page("SAINT 93.3 84.67 94.18 91.04", "Batch size 256 for all runs")


def test_a_fraction_of_the_output_matches_the_percent_of_the_paper_and_the_variant_is_stored():
    result = v2("VALID AUROC: 0.933\nwidth 256\n", PAPER_TABLE)
    assert found(result) == {"0.933": "x100", "256": "same"} and result["passed"]
    hit = next(h for h in result["matches"] if h["number"] == "0.933")
    assert hit["searched"] == "93.3" and hit["pages"][0]["page"] == 1 and "SAINT" in hit["pages"][0]["line"]
    assert "VALID AUROC" in hit["line"]


def test_v1_does_not_see_the_conversion_that_v2_sees():
    pages = [PAPER_TABLE]
    both = a4.k2_both("VALID AUROC: 0.933\nwidth 256\n", pages)
    assert not both["passed"] and both["v2"]["passed"]


def test_a_percent_of_the_output_matches_the_fraction_of_the_paper():
    result = v2("accuracy 88.86 and recall 91.04\n", page("Model 0.8886 0.9104"))
    assert found(result) == {"88.86": "div100", "91.04": "div100"} and result["passed"]


def test_a_rounded_value_matches_at_the_same_scale():
    result = v2("rmse 0.47312\nf1 0.8886\n", page("FT-T 0.473 0.889"))
    assert found(result) == {"0.47312": "same+round3", "0.8886": "same+round3"} and result["passed"]
    percent = v2("auroc 0.89321 and 0.91044\n", page("A 89.3 91.0"))
    assert found(percent) == {"0.89321": "x100+round3", "0.91044": "x100+round3"}


def test_a_thousands_separator_and_a_decimal_comma_of_the_paper_are_normalised():
    result = v2("total 12345.5\nscore 0.8886\n", page("Total 12,345.5 and score 88,86"))
    assert found(result) == {"12345.5": "same", "0.8886": "x100"} and result["passed"]


def test_a_year_a_version_a_date_and_an_index_are_never_looked_up():
    output = "year 2019 version 1.2.3 on 2026-10-27 at 12:30:05 epoch 1234 [1234] #5678\n"
    paper = page("2019 1.2.3 2026-10-27 12:30:05 1234 5678 [1234]")
    result = v2(output, paper)
    assert result["numbers_in_output"] == 0 and result["matches"] == [] and not result["passed"]


def test_the_chance_guard_a_converted_match_counts_only_on_a_table_page():
    prose = page("The model reaches 93.3 on Bank and 91.04 on Arcene", table=False)
    assert v2("auroc 0.933\narcene 0.9104\n", prose)["matches"] == []
    assert found(v2("auroc 0.933\narcene 0.9104\n", page("93.3 91.04"))) == {"0.933": "x100", "0.9104": "x100"}
    # a match in the same spelling counts on any page (as in v1), but a pass still needs one number on a table page
    same = v2("a 0.9331\nb 0.9104\n", prose, page("0.9331 only"))
    assert found(same) == {"0.9331": "same"} and not same["passed"]


def test_a_pass_needs_two_different_numbers_and_one_on_a_table_page():
    assert not v2("auroc 0.933\n", PAPER_TABLE)["passed"]  # one number
    assert not v2("a 0.9331\nb 0.9104\n", page("0.9331 0.9104", table=False))["passed"]  # no table page
    assert v2("a 0.9331\nb 0.9104\n", page("0.9331 0.9104"))["passed"]


def test_a_number_is_not_found_inside_a_longer_number():
    assert [h["number"] for h in v2("x 1.52\ny 21.55\n", page("21.55 and 1.5.2 and 2.152"))["matches"]] == ["21.55"]


def test_the_v2_result_is_stored_inside_the_v1_result_without_changing_it():
    pages = [page("0.9331 0.9104")]
    output = "a 0.9331\nb 0.9104\n"
    both = a4.k2_both(output, pages)
    assert {k: both[k] for k in a3.evaluate_k2(output, pages)} == a3.evaluate_k2(output, pages)
    assert both["v2"]["passed"] and both["passed"]


# ---- the controls (docs/AUTO_SEARCH_ROUND4.md section 4)


def stdout_of(relative):
    return (ROOT / "data" / relative / "stdout.log").read_text(encoding="utf-8", errors="replace")


@pytest.mark.parametrize("run", ["cpu_runs/paper_006", "pilot3_runs/paper_006", "memory_runs/paper_006_run2"])
def test_positive_control_paper_006_passes_with_the_scale_converted_auroc(run):
    """The paper prints the AUROC of SAINT on Bank as 93.3 (page 7, Table 2); the run prints 0.933."""
    pages = [page("SAINT 93.3 84.67 94.18 91.04 99.7 93.06", "a learning rate of 0.0001 with batches of size 256")]
    result = v2(stdout_of(run), *pages)
    assert result["passed"] and found(result) == {"256": "same", "0.933": "x100"}
    assert not a3.evaluate_k2(stdout_of(run), pages)["passed"]


def test_negative_control_paper_102_prints_toy_numbers_that_a_table_of_other_numbers_does_not_match():
    pages = [page("Model A 0.612 0.7 0.58", "Model B 91.2 88.1 0.431")]
    result = v2(stdout_of("pilot4_runs/paper_102"), *pages)
    assert not result["passed"] and result["matches"] == []


@pytest.mark.skipif(not (ROOT / "data" / "pdfs" / "2602.13045.pdf").is_file(), reason="PDFs are not tracked by git")
def test_negative_control_paper_102_does_not_pass_on_its_real_pdf():
    from src.pdf_text import extract_pdf_text

    pages = extract_pdf_text(ROOT / "data" / "pdfs" / "2602.13045.pdf", cache_dir=None).pages
    result = v2(stdout_of("pilot4_runs/paper_102"), *pages)
    assert not result["passed"] and result["numbers_found_in_paper"] == 0


@pytest.mark.skipif(not (ROOT / "data" / "pdfs" / "paper_006.pdf").is_file(), reason="PDFs are not tracked by git")
@pytest.mark.parametrize("run", ["cpu_runs/paper_006", "pilot3_runs/paper_006", "memory_runs/paper_006_run2"])
def test_positive_control_paper_006_passes_on_its_real_pdf(run):
    from src.pdf_text import extract_pdf_text

    pages = extract_pdf_text(ROOT / "data" / "pdfs" / "paper_006.pdf", cache_dir=None).pages
    result = v2(stdout_of(run), *pages)
    assert result["passed"] and found(result) == {"256": "same", "0.933": "x100"}
    hit = next(h for h in result["matches"] if h["number"] == "0.933")
    assert hit["pages"][0]["page"] == 7 and hit["pages"][0]["table_page"]


# ---- the pool and the walk


def test_stage_8_and_9_have_sixteen_topics_each_in_the_order_of_the_document():
    assert len(a4.queries(8)) == 16 and len(a4.queries(9)) == 16
    assert a4.queries(8)[0] == "arxiv.org in:readme language:Python archived:false fork:false size:<30000 topic:optimal-control"
    assert a4.queries(8)[-1].endswith("topic:uncertainty-estimation") and a4.queries(9)[0].endswith("topic:federated-learning")
    assert a4.queries(9)[-1].endswith("topic:forecasting")
    doc = (ROOT / "docs" / "AUTO_SEARCH_ROUND4.md").read_text(encoding="utf-8")
    for stage in (8, 9):
        assert all(f"`{t}`" in doc for t in a4.STAGE_TOPICS[stage])


def test_stages_10_to_13_have_sixteen_distinct_topics_each_and_the_document_lists_them():
    doc = (ROOT / "docs" / "AUTO_SEARCH_ROUND4.md").read_text(encoding="utf-8")
    seen = set()
    for stage in (10, 11, 12, 13):
        topics = a4.STAGE_TOPICS[stage]
        assert len(topics) == 16 and len(a4.queries(stage)) == 16
        assert all(f"`{t}`" in doc for t in topics)
        seen |= set(topics)
    assert len(seen) == 64 and not seen & set(a3.STAGE_TOPICS[7] + a4.STAGE_TOPICS[8] + a4.STAGE_TOPICS[9])


def test_the_pool_of_round_3_is_removed_whole_and_the_pool_file_names_this_round(tmp_path):
    (tmp_path / "data" / "auto_search3").mkdir(parents=True)
    (tmp_path / "data" / "corpus_expansion").mkdir()
    (tmp_path / "data" / "seed_papers.json").write_text("[]", encoding="utf-8")
    (tmp_path / "data" / "corpus_expansion" / "papers.json").write_text("[]", encoding="utf-8")
    (tmp_path / "data" / "auto_search3" / "pool.json").write_text(
        json.dumps({"candidates_in_order": [{"full_name": "Old/Checked"}]}), encoding="utf-8")
    assert "old/checked" in a4.earlier_round_repos(tmp_path)
    fetcher = Fetcher({"o/a": {}, "Old/Checked": {}})
    pool = a3.command_pool(fetcher, tmp_path / "out", 8, {"old/checked"}, pause=0, sleep=lambda s: None, queries_of=a4.queries,
                           rules=a4.RULES_DOC)
    assert [c["full_name"] for c in pool["candidates_in_order"]] == ["o/a"] and pool["rules"] == "docs/AUTO_SEARCH_ROUND4.md"
    assert len(pool["stages"]["8"]["searches"]) == 16


V2_PASS = {"passed": False, "matches": [], "v2": {"passed": True, "matches": []}}
V1_PASS = {"passed": True, "matches": [], "v2": {"passed": False, "matches": []}}
NEITHER = {"passed": False, "matches": [], "v2": {"passed": False, "matches": []}}


def walk(tmp_path, names, results, k2, **limits):
    calls = []

    def runner(entry, corpus, record_root):
        calls.append(entry["paper_id"])
        return dict(results[len(calls) - 1])

    k2_calls = []

    def k2_runner(entry, record_dir):
        k2_calls.append(entry["paper_id"])
        return json.loads(json.dumps(k2[len(k2_calls) - 1]))

    fetcher = Fetcher({n: {} for n in names})
    fetcher.ids = {n: i + 1 for i, n in enumerate(names)}
    return a4.Search(names, fetcher, set(), set(), tmp_path, runner, k2_runner, now=lambda: 1000.0, free=lambda: 10**12,
                     started_at=1000.0, **limits), calls


def test_ids_and_files_name_round_4_and_both_k2_results_are_stored(tmp_path):
    search, calls = walk(tmp_path, ["o/a", "o/b", "o/c"], [PASSED, PASSED, FAILED], [V2_PASS, V1_PASS])
    summary = search.run()
    assert calls == ["a4_001", "a4_002", "a4_003"]
    assert summary["k1_passed"] == 2 and summary["k2_passed"] == 1 and summary["k2v2_passed"] == 1 and summary["both_passed"] == 2
    assert summary["both_passed_v1"] == 1 and summary["both_passed_v2"] == 1
    document = json.loads((tmp_path / "evaluation.json").read_text(encoding="utf-8"))
    assert document["rules"] == "docs/AUTO_SEARCH_ROUND4.md" and document["candidates"][0]["k2"]["v2"]["passed"]
    assert document["candidates"][1]["k2"]["passed"] and document["candidates"][2]["k2"] is None


def test_the_walk_stops_when_five_candidates_passed_k1_and_k2_in_either_version(tmp_path):
    names = [f"o/r{i}" for i in range(12)]
    search, _ = walk(tmp_path, names, [PASSED] * 12, [V2_PASS, NEITHER, V1_PASS, V2_PASS, V1_PASS, V2_PASS] + [NEITHER] * 6,
                     max_both=a4.MAX_BOTH)
    summary = search.run()
    assert summary["stopped_because"] == "five_passed_both" and summary["both_passed"] == 5 and summary["runs"] == 6
    assert a4.MAX_BOTH == 5


# ---- the re-evaluation of round 3


def test_the_reevaluation_reads_only_stored_outputs_of_the_candidates_that_passed_k1(tmp_path):
    runs = tmp_path / "runs"
    (runs / "a3_001").mkdir(parents=True)
    (runs / "a3_001" / "stdout.log").write_text("auroc 0.933\nwidth 256\n", encoding="utf-8")
    (tmp_path / "evaluation.json").write_text(json.dumps({"candidates": [
        {"full_name": "o/a", "paper_id": "a3_001", "k1": {"k1_passed": True}, "k2": {"passed": False}},
        {"full_name": "o/b", "paper_id": "a3_002", "k1": {"k1_passed": False}}]}), encoding="utf-8")
    (tmp_path / "papers.json").write_text(json.dumps([{"paper_id": "a3_001", "paper_url": "https://arxiv.org/abs/2001.00001",
                                                       "run_command": "python run.py"}]), encoding="utf-8")
    missing = a4.command_reeval(tmp_path, tmp_path / "pdfs")
    assert [r["paper_id"] for r in missing["rows"]] == ["a3_001"] and not missing["rows"][0]["evaluated"]
    assert "not verified" in missing["rows"][0]["note"]


# ---- the report


def test_the_report_names_k1_k2_v1_and_k2_v2_and_the_converted_matches(tmp_path):
    search, _ = walk(tmp_path, ["o/a", "o/b"], [PASSED, FAILED], [{
        **V2_PASS, "numbers_in_output": 4, "v2": {"passed": True, "numbers_in_output": 4, "numbers_found_in_paper": 2,
                                                  "numbers_found_on_table_page": 2, "matches": [
            {"number": "0.933", "line": "AUROC: 0.933", "variant": "x100", "searched": "93.3", "on_table_page": True,
             "pages": [{"page": 7, "table_page": True, "line": "SAINT 93.3"}]}]}}])
    search.run()
    document = json.loads((tmp_path / "evaluation.json").read_text(encoding="utf-8"))
    papers = json.loads((tmp_path / "papers.json").read_text(encoding="utf-8"))
    text = a4.render_results(document, papers)
    assert "Passed K2 v2: 1 of 2" in text and "Passed K2 v1: 0 of 2" in text and "Passed both K1 and K2 v2: 1 of 2" in text
    assert "| 0.933 | x100 | 93.3 |" in text and "not a success rate" in text and "can match by chance" in text
