"""Failure statistics (#546): the category rules, and that the stored files are what the stored runs give today."""

import json

import pytest

from scripts import failure_statistics as fs
from scripts import report_numbers as rn


@pytest.mark.parametrize("line, category", [
    ("ModuleNotFoundError: No module named 'torch'", "missing_python_module"),
    ("E   ModuleNotFoundError: No module named 'pyomo'", "missing_python_module"),
    ("ERROR: No matching distribution found for torch==1.6.0", "install_package_not_found"),
    ("ERROR: Could not find a version that satisfies the requirement catboost==0.24.4 (from versions: none)", "install_package_not_found"),
    ("ERROR: ResolutionImpossible: for help visit https://pip.pypa.io", "install_package_not_found"),
    ("ERROR: Cannot install -r requirements.txt (line 4) and x==1 because these package versions have conflicting dependencies.",
     "install_package_not_found"),
    ("OSError: [Errno 30] Read-only file system: 'output'", "read_only_write"),
    ("FileNotFoundError: [Errno 2] No such file or directory: './data/x.csv'", "data_or_network_missing"),
    ("urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>", "data_or_network_missing"),
    ("requests.exceptions.ConnectionError: HTTPSConnectionPool(host='huggingface.co')", "data_or_network_missing"),
    ("RuntimeError: Missing Gemini API key for models/gemini", "api_key_missing"),
    ("tutorial_train.py: error: unrecognized arguments: data path]", "wrong_argument"),
    ("error: the following arguments are required: --config", "wrong_argument"),
    ("status: TIMEOUT", "timeout"),
    ("status: OOM_KILLED", "out_of_memory"),
    ("SyntaxError: invalid syntax", "other"),
    ("", "other"),
    (None, "other"),
])
def test_a_deciding_line_gets_the_category_of_the_first_matching_rule(line, category):
    assert fs.categorize_line(line) == category


def test_the_rules_are_tried_in_order():
    # a read-only error that also names a missing file is a read-only write; an install error that names a module is an install error
    assert fs.categorize_line("Read-only file system: 'No such file or directory'") == "read_only_write"
    assert fs.categorize_line("No matching distribution found for No module named x") == "install_package_not_found"


def test_a_record_outcome_wins_over_the_line():
    assert fs.categorize("no_metric_line", "ModuleNotFoundError: No module named 'x'") == "ran_no_metric_line"
    assert fs.categorize("command_incomplete", None) == "not_run_command_incomplete"
    assert fs.categorize("staging", None) == "staging_failed"
    assert fs.categorize("run", "ModuleNotFoundError: No module named 'x'") == "missing_python_module"


def test_every_rule_category_is_a_listed_category():
    names = set(fs.CATEGORY_NAMES)
    assert {c for c, _ in fs.LINE_RULES} <= names and set(fs.RECORD_RULES.values()) <= names and fs.UNCLASSIFIED in names


def test_a_long_line_is_shortened_and_whitespace_collapsed():
    assert fs.short("a   b\n c") == "a b c"
    assert len(fs.short("x" * 500)) == fs.LINE_LIMIT and fs.short("x" * 500).endswith("...")
    assert fs.short(None) is None


def test_count_has_every_category_and_rejects_an_unknown_one():
    counts = fs.count([{"category": "timeout"}, {"category": "passed"}, {"category": "timeout"}])
    assert counts["timeout"] == 2 and counts["passed"] == 1 and counts["other"] == 0
    assert list(counts) == ["passed", *fs.CATEGORY_NAMES]
    with pytest.raises(ValueError, match="unknown categories"):
        fs.count([{"category": "invented"}])


def stored():
    return json.loads(fs.OUT_JSON.read_text(encoding="utf-8"))


def test_the_stored_files_are_what_the_stored_runs_give_today():
    assert fs.main(["--check"]) == 0


def test_the_pilot_table_has_24_attempts_of_12_papers_and_matches_the_known_pilot_successes():
    table = stored()["tables"]["pilots"]
    assert table["attempts"] == 24 and len({r["run"].split(" ", 2)[2] for r in table["rows"]}) == 12
    passed = {pilot: counts["passed"] for pilot, counts in table["by_pilot"].items()}
    assert passed == {"Pilot 1": 0, "Pilot 2": 1, "Pilot 3": 2, "Pilot 4": 1}


def test_the_counts_add_up_and_the_search_tables_match_their_evaluation_files():
    document = stored()
    for key, table in document["tables"].items():
        assert sum(table["counts"].values()) == table["attempts"] == len(table["rows"]), key
    for key, folder in (("auto_search3", "auto_search3"), ("auto_search4", "auto_search4")):
        evaluation = json.loads((fs.DATA / folder / "evaluation.json").read_text(encoding="utf-8"))
        assert document["tables"][key]["counts"]["passed"] == evaluation["k1_passed"], key


def test_the_document_carries_the_selection_warning():
    text = fs.OUT_DOC.read_text(encoding="utf-8")
    assert "selected, not sampled" in text and "GPU requirements look like zero" in text and "not a success rate" in text
    assert "Pilot 3 used settings chosen after the failures of Pilot 2" in text


def test_the_report_block_renders_the_stored_counts():
    block = rn.render("failurestatistics")
    assert "Pilots 1 to 4 (24)" in block and "Automatic search, round 3 (135)" in block
