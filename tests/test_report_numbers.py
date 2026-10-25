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
    assert "| Reviewed by the owner | accepted 13, rejected 0, pending 0 |" in extraction
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


def test_pilot2_measurements_block_copies_the_stored_table(tmp_path):
    _pilot2_files(tmp_path)
    (tmp_path / "pilot2_runs" / "measurements.md").write_text(
        "<!-- Generated by scripts/pilot_measurements.py from data/pilot2_runs/; do not edit by hand. -->\n\n"
        "| Measure | Count | Rate |\n|---|---|---|\n| Pilot success | 1 / 6 | 0.167 |\n", encoding="utf-8")
    block = rn.render("pilot2measurements", tmp_path)
    assert "| Pilot success | 1 / 6 | 0.167 |" in block and block.count("<!--") == 1
    with pytest.raises(FileNotFoundError):
        rn.render("pilot2measurements", tmp_path / "nowhere")


def _pilot3_files(data: Path) -> None:
    runs = data / "pilot3_runs"
    runs.mkdir(parents=True)

    def rate(c):
        return {"count": c, "of": 6, "rate": round(c / 6, 3)}
    (runs / "comparison.json").write_text(json.dumps({"rates": {
        "install_success_rate": {"pilot1": rate(1), "pilot2": rate(6), "pilot3": rate(6)},
        "run_success_rate": {"pilot1": rate(0), "pilot2": rate(1), "pilot3": rate(2)},
        "pilot_success_rate": {"pilot1": rate(0), "pilot2": rate(1), "pilot3": rate(2)},
        "valid_runs": {"pilot1": rate(6), "pilot2": rate(6), "pilot3": rate(6)}}}))
    (runs / "comparison.md").write_text("<!-- generated -->\n\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 |\n")
    (runs / "measurements.md").write_text("<!-- generated -->\n\n| Measure | Count |\n|---|---|\n| Pilot success | 2 / 6 |\n")
    (runs / "failure_categories.json").write_text(json.dumps({"papers": [
        {"paper_id": "paper_004", "category": "OTHER", "other_name": "OUT_OF_MEMORY", "phase": "run", "pilot_success": False,
         "evidence": {"line": "status: OOM_KILLED"}},
        {"paper_id": "paper_003", "category": None, "other_name": None, "phase": None, "pilot_success": True, "evidence": None}]}))


def test_pilot3_blocks_come_from_the_stored_files_and_name_all_three_pilots(tmp_path):
    _pilot3_files(tmp_path)
    assert "data/pilot3_runs/comparison.json" in rn.render("pilot3", tmp_path) and "| 1 | 2 | 3 |" in rn.render("pilot3", tmp_path)
    summary = rn.render("pilot3summary", tmp_path)
    assert "Pilot success: 2 / 6 (0.333) (Pilot 1: 0 / 6 (0.0); Pilot 2: 1 / 6 (0.167))" in summary
    assert "| Pilot success | 2 / 6 |" in rn.render("pilot3measurements", tmp_path)
    failures = rn.render("pilot3failures", tmp_path)
    assert "data/pilot3_runs/failure_categories.json" in failures
    assert "| `paper_004` | OTHER (OUT_OF_MEMORY) | run | `status: OOM_KILLED` |" in failures
    assert "| `paper_003` | success | n/a | n/a |" in failures


def test_the_abstract_block_renders_the_same_sentence_as_the_pilot3_summary(tmp_path):
    _pilot3_files(tmp_path)
    assert rn.render("abstractnumbers", tmp_path) == rn.render("pilot3summary", tmp_path)


def test_a_hand_edit_of_a_pilot3_block_is_detected(tmp_path):
    _pilot3_files(tmp_path)
    text = rn.apply("<!-- numbers:pilot3summary:start -->\nx\n<!-- numbers:pilot3summary:end -->\n", tmp_path)
    assert rn.mismatches(text, tmp_path) == []
    assert rn.mismatches(text.replace("2 / 6 (0.333)", "6 / 6 (1.0)"), tmp_path) == ["pilot3summary"]


def test_the_pilot3_document_and_the_report_are_in_sync_with_the_stored_files():
    from src.config import PROJECT_ROOT
    for path in (PROJECT_ROOT / "docs" / "PILOT_3.md", PROJECT_ROOT / "docs" / "report" / "REPORT.md"):
        assert rn.mismatches(path.read_text(encoding="utf-8").replace("\r\n", "\n")) == [], path


def test_the_blocks_added_for_the_final_pass_render_their_stored_facts():
    seeds = rn.render("multiseed")
    assert "`paper_003` | 3 of 3 | 65.0" in seeds and "`paper_006` | 3 of 3 | 100.0" in seeds
    assert "`synthetic_seeded` yes" in seeds and "`loss`; `loss` 65.0, `rmse` 100.0" in seeds
    gpu = rn.render("gpucheck")
    assert "2.8.0+cu128 / 12.8" in gpu and "cuda:0; result equal to the CPU result: True" in gpu and "Checks passed | 8 of 8" in gpu
    validation = rn.render("diagnosisvalidation")
    assert "| Real runs | 46 | 46 / 46 | 10 / 10 | 36 / 36 | 46 / 46 | none |" in validation
    field = rn.render("fieldanalysis")
    assert "| all 12 papers | final | 9 / 12 | 4 / 12 | 3 / 12 | 5 / 12 | 1 / 12 |" in field
    assert "evaluated: 65; selected: 0" in rn.render("rescience")


def test_the_candidate_and_probe_blocks_render_their_stored_facts_and_the_warnings():
    runs = rn.render("candidateruns")
    assert "Selected candidates: 14; run once in the sandbox: 13; passed: 0 (none)" in runs
    assert "Wilson 95 % interval 0.0 % to 21.5 %" in runs and "not a sample; it is not a success rate" in runs
    probe = rn.render("toleranceprobe")
    assert "| paper_006 | 4 | 2 | -10 % (Verified -> Partially Verified) | +10 % (Verified -> Partially Verified) |" in probe
    assert "match a probed run by question ID: 0 of 13" in probe
    report = (rn.REPORT_PATH.read_text(encoding="utf-8")).replace("\r\n", "\n")
    assert "hand-made claims, not an error of a real paper" in report and "have not been measured" in report


def test_the_autosearch3_block_counts_runs_k1_k2_and_both_with_wilson_intervals(tmp_path):
    (tmp_path / "auto_search3").mkdir()
    passed = {"k1_passed": True, "category": None}
    failed = {"k1_passed": False, "category": "run"}
    candidates = [{"paper_id": "a3_001", "k1": passed, "k2": {"passed": True}}, {"paper_id": "a3_002", "k1": failed, "k2": None},
                  {"paper_id": "a3_003", "k1": passed, "k2": {"passed": False}}, {"full_name": "o/static", "passed": False}]
    (tmp_path / "auto_search3" / "evaluation.json").write_text(
        json.dumps({"candidates": candidates, "stopped_because": "time_limit_9h"}), encoding="utf-8")
    block = rn.render("autosearch3", tmp_path)
    assert "checked against the static rules: 4; run once in the sandbox: 3" in block
    assert "Passed K1 (the run test): 2 of 3, Wilson 95 % interval 20.8 % to 93.9 %" in block
    assert "Passed both: 1 of 3, Wilson 95 % interval 6.1 % to 79.2 % (a3_001)" in block
    assert "run 1" in block and "time_limit_9h" in block and "not a success rate" in block


def test_the_real_verdict_pilot_interval_and_clean_clone_blocks_render_their_stored_facts():
    verdicts = rn.render("realverdicts")
    assert "claimed 0.459, reproduced 0.473, relative difference 3.05 %, Tier 2 100, `Verified` in 6 of 6 runs" in verdicts
    assert "Tier 2 is 0.0 in 10 of the 10 real runs that have accepted claims" in verdicts
    assert "passed 6 of 6 runs of `paper_003`, 0 of 3 runs of `paper_006`, 0 of 1 runs of `paper_102`" in verdicts
    assert "the run's final rmse 0.473 is not printed in it" in verdicts
    assert "| all 12 papers | final | 3 / 12 | 8.9 % to 53.2 % |" in rn.render("pilotintervals")
    clean = rn.render("cleanclone")
    assert "2,490 s" in clean and "run phase 1,092.54 s" in clean and "`accuracy 0.8886, auroc 0.892`" in clean
    assert "status Needs Review." in clean


def test_the_clean_clone_block_fails_loudly_when_the_walkthrough_changes(tmp_path):
    folder = tmp_path / "docs" / "evidence" / "clean_clone"
    folder.mkdir(parents=True)
    (folder / "WALKTHROUGH.md").write_text("## Update 2\n\nnothing of the expected lines\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no longer holds"):
        rn.render("cleanclone", tmp_path / "data")
