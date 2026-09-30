"""The pilot report (docs/PILOT_WEEK2.md section 11) only shows numbers from the generated files (P6, #127)."""

import json
import re

import pytest

from src.config import PROJECT_ROOT

DOC = (PROJECT_ROOT / "docs" / "PILOT_WEEK2.md").read_text(encoding="utf-8")
RUNS = PROJECT_ROOT / "data" / "pilot_runs"

pytestmark = pytest.mark.skipif("## 11. Pilot report" not in DOC, reason="pilot report not written yet")


def test_pasted_measurements_equal_the_generated_file():
    block = re.search(r"<!-- measurements:start -->\n(.*?)<!-- measurements:end -->", DOC, re.S)
    assert block, "measurements markers missing"
    assert block.group(1) == (RUNS / "measurements.md").read_text(encoding="utf-8")


def test_category_rows_equal_the_generated_categories():
    categories = json.loads((RUNS / "failure_categories.json").read_text(encoding="utf-8"))
    report = DOC.split("## 11. Pilot report", 1)[1]
    for paper in categories["papers"]:
        line = paper["evidence"]["line"] if paper["evidence"] else ""
        row = f"| `{paper['paper_id']}` | {paper['category']} | {paper['phase']} | `{line}` |"
        assert row in report, row


def test_headline_counts_equal_the_generated_measurements():
    m = json.loads((RUNS / "measurements.json").read_text(encoding="utf-8"))
    report = DOC.split("## 11. Pilot report", 1)[1]
    assert f"**{m['pilot_success_rate']['count']} of {m['pilot_success_rate']['of']}**" in report
    assert f"(pilot success {m['pilot_success_rate']['count']} / 6)" in report
    counts = json.loads((RUNS / "failure_categories.json").read_text(encoding="utf-8"))["counts"]
    assert f"`MISSING_DEPENDENCY`, {counts['MISSING_DEPENDENCY']} of 6" in report
    assert f"`DATA_NOT_ACCESSIBLE`: {counts['DATA_NOT_ACCESSIBLE']} of 6" in report
