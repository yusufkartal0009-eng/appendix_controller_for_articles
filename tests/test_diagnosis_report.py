"""The rule-based diagnosis report and `cli.py diagnose` (#33, docs/DIAGNOSIS.md)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.diagnosis_examples as examples
from src.diagnosis.classifier import classify_run
from src.diagnosis.prompts import check_neutral_language
from src.diagnosis.report import build_report, claims_from_seed_papers, diagnose_run
from src.diagnosis.schema import load_diagnosis_input

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"


def make_run(root, record=None, report=None, stderr=None, name="r"):
    d = root / name
    d.mkdir(parents=True)
    (d / "pilot_record.json").write_text(json.dumps(record if record is not None else {"paper_id": "p"}))
    if report is not None:
        (d / "run_report.json").write_text(json.dumps(report))
    if stderr is not None:
        (d / "stderr.log").write_text(stderr)
    return d


def all_run_dirs():
    return [folder for _, rel, _ in examples.GROUPS for folder in examples.run_dirs(REPO / rel)]


def test_every_statement_of_every_stored_run_names_a_field_and_a_source():
    folders = all_run_dirs()
    assert len(folders) >= 30
    for folder in folders:
        report = diagnose_run(folder)
        assert report.statements
        for s in report.statements:
            assert s.fields and s.source, (folder, s.text)
            assert s.text.strip().endswith((".", "`")) or "`" in s.text, (folder, s.text)


def test_no_report_contains_a_loaded_word():
    for folder in all_run_dirs():
        assert check_neutral_language(diagnose_run(folder).to_markdown()) == [], folder


def test_missing_values_are_written_as_unknown(tmp_path):
    folder = make_run(tmp_path, record={}, report={})
    text = diagnose_run(folder, use_seed_claims=False).to_markdown()
    assert "The paper of this run is unknown." in text
    assert "The status of the run phase is unknown." in text
    assert "The peak memory is unknown." in text
    assert "No claims were given" in text
    assert "(not present)" in text


def test_a_claim_with_a_matching_metric_states_the_difference_and_no_verdict(tmp_path):
    folder = make_run(tmp_path, report={"status": "COMPLETED", "exit_code": 0, "dependency_install_status": "INSTALLED",
                                        "metrics": {"accuracy": 0.8}})
    data = load_diagnosis_input(folder, claims={"accuracy": 0.9, "f1": 0.7})
    text = build_report(data, classify_run(folder)).to_markdown()
    assert "claimed 0.9, found in the output 0.8; the difference is 0.1 (11.1% of the claimed value)" in text
    assert "states no verdict" in text
    assert "Claim `f1` (claimed 0.7): no metric with this name was found" in text


def test_a_run_that_failed_quotes_the_deciding_line(tmp_path):
    folder = make_run(tmp_path, report={"status": "FAILED", "exit_code": 1, "dependency_install_status": "INSTALLED",
                                        "docker_used": True, "isolated": True},
                      stderr="Traceback\nModuleNotFoundError: No module named 'delu'\n",
                      record={"paper_id": "p", "stage": {"status": "STAGED", "target_script_exists": True}})
    report = diagnose_run(folder, use_seed_claims=False)
    text = report.to_markdown()
    assert report.category_label == "MISSING_DEPENDENCY"
    assert "`stderr.log:2`: `ModuleNotFoundError: No module named 'delu'`" in text
    assert "a cause behind the line was not investigated" in text


def test_an_override_is_reported_as_not_a_protocol_run():
    text = diagnose_run(DATA / "cpu_runs" / "paper_003").to_markdown()
    assert "The CPU limit was set by hand for this run" in text
    assert "The container had 8 CPUs" in text


def test_claims_come_from_the_seed_papers_only():
    assert set(claims_from_seed_papers("paper_006")) == {"arcene_auroc", "xgboost_arcene_auroc"}
    assert claims_from_seed_papers("paper_101") is None
    assert claims_from_seed_papers(None) is None


def test_cli_diagnose_prints_markdown_and_json():
    folder = (DATA / "pilot3_runs" / "paper_004").as_posix()
    md = subprocess.run([sys.executable, "cli.py", "diagnose", folder], cwd=REPO, capture_output=True, text=True, check=True)
    assert "OUT_OF_MEMORY" in md.stdout and "source:" in md.stdout
    js = subprocess.run([sys.executable, "cli.py", "diagnose", folder, "--json", "--no-claims"], cwd=REPO,
                        capture_output=True, text=True, check=True)
    parsed = json.loads(js.stdout)
    assert parsed["category"] == "OUT_OF_MEMORY" and parsed["paper_id"] == "paper_004"
    assert not any("Claim `" in s["text"] for s in parsed["statements"])


def test_cli_diagnose_on_a_missing_folder_exits_1(tmp_path):
    result = subprocess.run([sys.executable, "cli.py", "diagnose", str(tmp_path / "nope")], cwd=REPO,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 1 and "not a directory" in result.stderr


def test_the_examples_document_matches_the_stored_runs():
    assert examples.main(["--check"]) == 0


def test_the_examples_document_covers_every_group():
    text = (REPO / "docs" / "DIAGNOSIS_EXAMPLES.md").read_text(encoding="utf-8")
    for title, _, _ in examples.GROUPS:
        assert f"## {title}" in text


@pytest.mark.parametrize("label", ["OUT_OF_MEMORY", "TIMEOUT", "MISSING_DEPENDENCY", "DATA_NOT_ACCESSIBLE",
                                   "WRITE_TO_READ_ONLY_REPOSITORY", "HARDWARE_GPU_REQUIRED"])
def test_every_label_the_classifier_can_give_has_a_description(label):
    from src.diagnosis.report import CATEGORY_TEXT

    assert label in CATEGORY_TEXT
