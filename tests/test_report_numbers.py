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


def _pilot2_files(data: Path) -> None:
    runs = data / "pilot2_runs"
    runs.mkdir(parents=True)

    def rate(count):
        return {"count": count, "of": 6, "rate": round(count / 6, 3)}
    (runs / "comparison.json").write_text(json.dumps({"rates": {
        "install_success_rate": {"pilot1": rate(1), "pilot2": rate(6)},
        "run_success_rate": {"pilot1": rate(0), "pilot2": rate(2)},
        "pilot_success_rate": {"pilot1": rate(0), "pilot2": rate(2)},
        "valid_runs": {"pilot1": rate(6), "pilot2": rate(6)}}}))
    (runs / "failure_categories.json").write_text(json.dumps({"papers": [
        {"paper_id": "paper_002", "category": "MISSING_DEPENDENCY", "other_name": None, "phase": "run", "pilot_success": False,
         "evidence": {"file": "stderr.log", "line_number": 9, "line": "ModuleNotFoundError: No module named 'lightgbm'"}},
        {"paper_id": "paper_005", "category": "OTHER", "other_name": "OUT_OF_MEMORY", "phase": "run", "pilot_success": False,
         "evidence": {"file": "run_report.json", "line_number": None, "line": "status: OOM_KILLED | with a pipe"}},
        {"paper_id": "paper_006", "category": None, "other_name": None, "phase": None, "pilot_success": True, "evidence": None}]}))


def test_pilot2_summary_and_failure_table_come_from_the_stored_files(tmp_path):
    _pilot2_files(tmp_path)
    summary = rn.render("pilot2summary", tmp_path)
    assert ("Install success: 6 / 6 (1.0) (Pilot 1: 1 / 6 (0.167)). Run success: 2 / 6 (0.333) (Pilot 1: 0 / 6 (0.0)). "
            "Pilot success: 2 / 6 (0.333) (Pilot 1: 0 / 6 (0.0)).") in summary
    table = rn.render("pilot2failures", tmp_path)
    assert "| `paper_002` | MISSING_DEPENDENCY | run | `ModuleNotFoundError: No module named 'lightgbm'` |" in table
    assert "| `paper_005` | OTHER (OUT_OF_MEMORY) | run | `status: OOM_KILLED \\| with a pipe` |" in table
    assert "| `paper_006` | success | n/a | n/a |" in table


def test_a_hand_edit_of_the_pilot2_blocks_is_detected(tmp_path):
    _pilot2_files(tmp_path)
    text = rn.apply("<!-- numbers:pilot2summary:start -->\nx\n<!-- numbers:pilot2summary:end -->\n", tmp_path)
    assert rn.mismatches(text, tmp_path) == []
    assert rn.mismatches(text.replace("2 / 6 (0.333)", "6 / 6 (1.0)"), tmp_path) == ["pilot2summary"]
