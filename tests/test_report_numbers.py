"""The numbers in the final report come from the stored files, and a test keeps them in sync (#221)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import report_numbers as rn

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "report" / "REPORT.md"


def test_stored_pilot_1_and_extraction_numbers_are_rendered():
    pilot1 = rn.render("pilot1")
    assert "| Install success | 1 / 6 (0.167) |" in pilot1 and "| Pilot success | 0 / 6 (0.0) |" in pilot1
    assert "| `MISSING_DEPENDENCY` | 5 |" in pilot1 and "| `DATA_NOT_ACCESSIBLE` | 1 |" in pilot1
    extraction = rn.render("extraction")
    assert "| Passes A and B agree | 18 / 18 (disagreements: 0) |" in extraction
    assert "| Reviewed by the owner | accepted 12, rejected 0, pending 0 |" in extraction
    assert "| Precision / recall | 1.0 / 1.0 |" in extraction and "12 / 0 / 0 / 6" in extraction
    assert "`paper_008:higgs_auroc`: TN" in extraction


def test_the_pilot_2_block_needs_the_comparison_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        rn.render("pilot2", tmp_path)
    (tmp_path / "pilot2_runs").mkdir()
    (tmp_path / "pilot2_runs" / "comparison.json").write_text(json.dumps({"rates": {"x": 1}}))
    (tmp_path / "pilot2_runs" / "comparison.md").write_text("<!-- generated -->\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
    block = rn.render("pilot2", tmp_path)
    assert "| 1 | 2 |" in block and block.count("<!--") == 1  # only the generator header remains


def test_apply_replaces_a_block_and_check_detects_a_hand_edit():
    text = "before\n<!-- numbers:pilot1:start -->\nHAND TYPED 0 / 6\n<!-- numbers:pilot1:end -->\nafter\n"
    assert rn.mismatches(text) == ["pilot1"]
    fixed = rn.apply(text)
    assert rn.mismatches(fixed) == [] and fixed.startswith("before\n") and fixed.endswith("\nafter\n")
    assert "HAND TYPED" not in fixed and rn.render("pilot1") in fixed
    edited = fixed.replace("| Install success | 1 / 6 (0.167) |", "| Install success | 6 / 6 (1.0) |")
    assert rn.mismatches(edited) == ["pilot1"]


def test_an_unknown_block_is_refused():
    with pytest.raises(KeyError):
        rn.apply("<!-- numbers:nope:start -->\nx\n<!-- numbers:nope:end -->")


def test_the_report_in_the_repository_is_in_sync_with_the_stored_files():
    assert rn.mismatches(REPORT.read_text(encoding="utf-8").replace("\r\n", "\n")) == []


def test_cli_check_and_write_round_trip(tmp_path):
    report = tmp_path / "REPORT.md"
    report.write_text("x\n<!-- numbers:extraction:start -->\nold\n<!-- numbers:extraction:end -->\n", encoding="utf-8")
    assert rn.main(["--check", "--report", str(report)]) == 1
    assert rn.main(["--write", "--report", str(report)]) == 0
    assert rn.main(["--check", "--report", str(report)]) == 0
