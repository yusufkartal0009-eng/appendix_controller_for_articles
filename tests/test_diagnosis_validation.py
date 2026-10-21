"""The hand-labeled validation set of the failure classifier (#36, docs/DIAGNOSIS_VALIDATION.md)."""

import json
import re
from pathlib import Path

import scripts.evaluate_diagnosis_classifier as evaluation

REPO = Path(__file__).resolve().parent.parent
VALIDATION = REPO / "data" / "diagnosis_validation"
ANSI = re.compile(chr(27) + r"\[[0-9;?]*[A-Za-z]")


def labels():
    return json.loads((VALIDATION / "labels.json").read_text(encoding="utf-8"))


def test_every_label_quotes_text_that_exists_in_the_run_folder():
    for entry in labels()["runs"]:
        text = ANSI.sub("", (REPO / entry["run_dir"] / entry["evidence"]["file"]).read_text(encoding="utf-8", errors="replace"))
        assert entry["evidence"]["text"] in text, entry["id"]


def test_the_set_is_large_and_covers_the_main_categories():
    runs = labels()["runs"]
    assert len({e["id"] for e in runs}) == len(runs) >= 40
    categories = {e["label"]["category"] for e in runs}
    assert {"MISSING_DEPENDENCY", "DATA_NOT_ACCESSIBLE", "TIMEOUT", "OTHER", "NO_FAILURE"} <= categories
    assert {e["label"]["name"] for e in runs} >= {"OUT_OF_MEMORY", "WRITE_TO_READ_ONLY_REPOSITORY"}


def test_the_label_source_is_written_and_says_the_labels_are_not_blind():
    source = labels()["label_source"]
    assert "NOT blind" in source and "docs/PILOT_WEEK2.md section 7" in source


def test_the_labels_do_not_copy_the_stored_categories():
    # the label file has its own vocabulary and no field of the stored failure_categories.json
    assert "failure_categories" not in json.dumps(labels()["runs"])


def test_the_classifier_matches_the_real_labels_since_the_gaps_were_closed():
    # R41 was the one wrong answer until #424 closed its gap; the labels were not edited
    results = evaluation.evaluate()
    summary = results["summary"]["real"]
    assert summary["n"] == len(labels()["runs"])
    assert summary["category"]["correct"] == summary["category"]["of"]
    assert summary["wrong"] == []


def test_every_wrong_answer_has_a_written_analysis_and_a_closed_gap_is_not_wrong():
    results = evaluation.evaluate()
    analysis = json.loads((VALIDATION / "analysis.json").read_text(encoding="utf-8"))
    closed = json.loads((VALIDATION / "closed_gaps.json").read_text(encoding="utf-8"))
    wrong = results["summary"]["real"]["wrong"] + results["summary"]["synthetic"]["wrong"]
    assert set(wrong) <= set(analysis)
    assert set(analysis) <= set(wrong), "an analysis for an answer that is no longer wrong belongs in closed_gaps.json"
    assert set(closed) == {"R41", "S01", "S06", "S07", "S08", "S09"} and not set(closed) & set(wrong)


def test_the_synthetic_probes_are_kept_apart_and_were_written_to_find_gaps():
    synthetic = evaluation.evaluate()["summary"]["synthetic"]
    assert synthetic["n"] >= 10
    assert len(json.loads((VALIDATION / "closed_gaps.json").read_text(encoding="utf-8"))) >= 5


def test_the_stored_results_and_document_match_the_labels():
    assert evaluation.main(["--check"]) == 0
