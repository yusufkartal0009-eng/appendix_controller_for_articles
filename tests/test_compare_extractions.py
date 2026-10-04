"""Comparison of the two extraction passes by normalized value (plan step 1.2, #179; D-005)."""

import json

import pytest

import scripts.compare_extractions as ce


def _found(value, unit="none", quote_extra=""):
    return {"status": "found", "reason": "r", "claim": {
        "metric_name": "rmse", "value_as_printed": value, "unit": unit, "dataset": "D", "model_variant": "M",
        "split": "test", "higher_is_better": False, "table_or_figure": "Table 1", "page": 1,
        "source_quote": f"M {value}{quote_extra}", "confidence": 0.5}}


NOT_FOUND = {"status": "not_found", "reason": "absent", "claim": None}


@pytest.mark.parametrize("a, b, verdict", [
    (_found("0.459"), _found("0.459", quote_extra=" 0 .859"), "agree_value"),      # different quotes, same number
    (_found("96.99 %", "percent"), _found("0.9699", "fraction"), "agree_value"),    # same after normalization
    (_found("0.459"), _found("0.486"), "value_mismatch"),
    (_found("0.459"), NOT_FOUND, "found_vs_not_found"),
    (NOT_FOUND, NOT_FOUND, "agree_not_found"),
])
def test_rules(a, b, verdict):
    assert ce.compare_answers(a, b)["verdict"] == verdict


def test_report_and_exit_code(tmp_path):
    record = {"paper_id": "paper_001", "extractions": {
        "A": {"answers": {"q1": _found("0.459"), "q2": NOT_FOUND}},
        "B": {"answers": {"q1": _found("0.459"), "q2": _found("0.1")}}}}
    (tmp_path / "paper_001.json").write_text(json.dumps(record))
    assert ce.main(["--claims-dir", str(tmp_path)]) == 1
    result = json.loads((tmp_path / "consistency.json").read_text())
    assert (result["agreements"], result["disagreements"]) == (1, 1)
    assert "found_vs_not_found" in (tmp_path / "consistency.md").read_text()


def test_passes_must_answer_the_same_questions(tmp_path):
    record = {"paper_id": "paper_001", "extractions": {"A": {"answers": {"q1": NOT_FOUND}}, "B": {"answers": {}}}}
    (tmp_path / "paper_001.json").write_text(json.dumps(record))
    with pytest.raises(ValueError, match="different questions"):
        ce.compare(tmp_path)


def test_stored_report_matches_the_stored_extractions():
    stored = ce.CLAIMS_DIR / "consistency.json"
    if not stored.exists():
        pytest.skip("no consistency report stored yet")
    result = ce.compare()
    assert json.loads(stored.read_text(encoding="utf-8")) == result
    assert (ce.CLAIMS_DIR / "consistency.md").read_text(encoding="utf-8") == ce.to_markdown(result)
