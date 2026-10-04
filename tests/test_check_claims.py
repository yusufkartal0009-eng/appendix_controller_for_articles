"""Quote guard run over the agent extractions (plan step 1.4, #182)."""

import json

import scripts.check_claims as cc
from src.pdf_text import PdfText

SHA = "e" * 64
PDF = PdfText(sha256=SHA, extractor="test", pages=["Datasets: Arcene. Models: SAINT, XGBoost.",
                                                    "Table 2\nSAINT 93.3 84.67 94.18 91.04\nXGBoost 92.96 81 .41"])


def _answer(value, quote, model="SAINT"):
    return {"status": "found", "reason": "r", "claim": {
        "metric_name": "auroc", "value_as_printed": value, "unit": "percent", "dataset": "Arcene",
        "model_variant": model, "split": "not_stated", "higher_is_better": True, "table_or_figure": "Table 2",
        "page": 2, "source_quote": quote, "confidence": 0.9}}


RECORD = {"paper_id": "paper_006", "pdf_sha256": SHA, "extractions": {
    "A": {"answers": {"q1": _answer("91.04", "SAINT 93.3 84.67 94.18 91.04"),
                      "q2": {"status": "not_found", "reason": "absent", "claim": None}}},
    "B": {"answers": {"q1": _answer("91.05", "SAINT 93.3 84.67 94.18 91.05"),       # invented digit
                      "q2": _answer("81.41", "XGBoost 92.96 81.41", model="XGBoost")}}}}  # split number in PDF


def test_rows_statuses_and_flags():
    rows = {(r["pass"], r["query_id"]): r for r in cc.check_record(RECORD, PDF)}
    assert rows[("A", "q1")]["status"] == "AUTO_QUOTE_MATCH" and rows[("A", "q1")]["from_table"] is True
    assert rows[("A", "q2")]["answer"] == "not_found"
    assert rows[("B", "q1")]["status"] == "UNVERIFIED" and rows[("B", "q1")]["reasons"]
    assert rows[("B", "q2")]["value_match"] == "split_numbers_repaired"


def test_report_counts_and_exit_code(tmp_path, monkeypatch):
    (tmp_path / "paper_006.json").write_text(json.dumps(RECORD))
    monkeypatch.setattr(cc, "extract_pdf_text", lambda path: PDF)
    assert cc.main(["--claims-dir", str(tmp_path), "--pdf-dir", str(tmp_path)]) == 1
    result = json.loads((tmp_path / "guard_report.json").read_text())
    assert (result["found_claims"], result["auto_quote_match"], result["unverified"]) == (3, 2, 1)
    assert "UNVERIFIED: 1" in (tmp_path / "guard_report.md").read_text()


def test_stored_report_covers_every_stored_answer():
    """The PDFs are not in CI, so the stored report is checked for form against the stored claim files."""
    report_path = cc.CLAIMS_DIR / "guard_report.json"
    if not report_path.exists():
        return
    report = json.loads(report_path.read_text(encoding="utf-8"))
    expected = set()
    for path in cc.CLAIMS_DIR.glob("paper_*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        for label, extraction in record["extractions"].items():
            for qid, answer in extraction["answers"].items():
                value = answer["claim"]["value_as_printed"] if answer["status"] == "found" else None
                expected.add((record["paper_id"], label, qid, value))
    stored = {(r["paper_id"], r["pass"], r["query_id"], r.get("value_as_printed")) for r in report["rows"]}
    assert stored == expected
    assert (cc.CLAIMS_DIR / "guard_report.md").read_text(encoding="utf-8") == cc.to_markdown(report)
