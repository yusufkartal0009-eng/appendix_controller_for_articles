"""Memory re-runs next to Pilot 3 (#327): the table comes from the records, and the documents show it."""

import json
import re

import pytest

from scripts import memory_runs, report_numbers
from src.config import PROJECT_ROOT


def _record(directory, status, exit_code, peak, limit, seconds=10.0, stderr=""):
    directory.mkdir(parents=True)
    record = {"limits": {"memory_limit": limit},
              "run": {"status": status, "exit_code": exit_code, "duration_seconds": seconds, "peak_memory_bytes": peak}}
    (directory / "pilot_record.json").write_text(json.dumps(record), encoding="utf-8")
    (directory / "stderr.log").write_text(stderr, encoding="utf-8")


@pytest.fixture
def data(tmp_path):
    gib = 1024 ** 3
    _record(tmp_path / "pilot3_runs" / "paper_901", "OOM_KILLED", 137, 6 * gib, "6g",
            stderr="1.1 grid search:  14%|#| 76/540 [00:01<00:02, 3.0s/it]")
    _record(tmp_path / "memory_runs" / "paper_901", "COMPLETED", 0, 10 * gib, "14265m")
    return tmp_path


@pytest.mark.parametrize("text,expected", [("6g", 6 * 1024 ** 3), ("14265m", 14265 * 1024 ** 2), ("512K", 512 * 1024)])
def test_memory_sizes_are_read(text, expected):
    assert memory_runs.limit_bytes(text) == expected


def test_a_bad_memory_size_is_an_error():
    with pytest.raises(ValueError):
        memory_runs.limit_bytes("lots")


def test_rows_pair_each_memory_run_with_the_same_papers_pilot_3_record(data):
    rows = memory_runs.measure(data)
    assert [r["paper_id"] for r in rows] == ["paper_901"]
    pilot3, rerun = rows[0]["pilot3"], rows[0]["memory_run"]
    assert (pilot3["status"], pilot3["exit_code"], pilot3["peak_memory_gib"], pilot3["memory_limit_gib"]) == (
        "OOM_KILLED", 137, 6.0, 6.0)
    assert pilot3["peak_share_of_limit"] == 1.0 and pilot3["last_grid_step"] == "76/540"
    assert (rerun["status"], rerun["peak_memory_gib"], rerun["memory_limit_gib"], rerun["last_grid_step"]) == (
        "COMPLETED", 10.0, 13.93, "n/a")


def test_a_pilot_3_run_without_a_memory_run_is_not_listed(data):
    _record(data / "pilot3_runs" / "paper_902", "COMPLETED", 0, 1, "6g")
    assert [r["paper_id"] for r in memory_runs.measure(data)] == ["paper_901"]


def test_the_table_and_the_sentence_show_both_outcomes(data):
    rows = memory_runs.measure(data)
    table = memory_runs.to_markdown(rows)
    assert "| `paper_901` | OOM_KILLED (exit 137) | 10.0 | 6.0 | 6.0 | 76/540 | COMPLETED (exit 0) |" in table
    sentence = memory_runs.to_sentence(rows)
    assert "OOM_KILLED at 6.0 GiB (peak 6.0 GiB) in Pilot 3, COMPLETED at 13.93 GiB (peak 10.0 GiB)" in sentence


def test_apply_replaces_only_the_block_and_needs_exactly_one(data):
    text = "before\n" + memory_runs.START + "\nold\n" + memory_runs.END + "\nafter\n"
    new = memory_runs.apply(text, data)
    assert new.startswith("before\n") and new.endswith("after\n") and "old" not in new and "paper_901" in new
    assert memory_runs.in_sync(new, data) and not memory_runs.in_sync(text, data)
    with pytest.raises(ValueError):
        memory_runs.apply("no block here", data)


def test_the_stored_document_and_the_stored_records_agree():
    text = (PROJECT_ROOT / "docs" / "MEMORY_RUNS.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert memory_runs.in_sync(text)
    papers = {row["paper_id"] for row in memory_runs.measure()}
    assert papers == {"paper_003", "paper_004", "paper_005"}


def test_the_report_has_the_memory_block_and_no_empty_numbers_block():
    """A block whose markers touch is never rendered (the pattern needs a line between them); #327 found four."""
    text = (PROJECT_ROOT / "docs" / "report" / "REPORT.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert report_numbers.mismatches(text) == []
    names = re.findall(r"<!-- numbers:([a-z0-9]+):start -->", text)
    assert "memoryruns" in names
    assert not re.search(r"<!-- numbers:([a-z0-9]+):start -->\n<!-- numbers:\1:end -->", text)
    for name in names:
        match = re.search(rf"<!-- numbers:{name}:start -->\n(.*?)\n<!-- numbers:{name}:end -->", text, re.DOTALL)
        assert match and match.group(1).strip(), f"block {name} is empty"


def test_a_second_run_folder_is_not_a_first_memory_run(data):
    _record(data / "memory_runs" / "paper_901_run2", "COMPLETED", 0, 1024 ** 3, "14265m")
    assert [r["paper_id"] for r in memory_runs.measure(data)] == ["paper_901"]
