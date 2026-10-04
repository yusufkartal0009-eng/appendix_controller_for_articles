"""Blind packet for an independent pass B, and its import (#186)."""

import json

import pytest

import scripts.import_pass as ip
import scripts.make_blind_packet as mbp
from src.config import DATA_DIR
from src.pdf_text import PdfText

SHA = "f" * 64
PDF = PdfText(sha256=SHA, extractor="test", pages=["Datasets: Arcene. Models: SAINT.", "Table 2\nSAINT 93.3 91.04"])


def _stored_answer_values():
    values = set()
    for path in (DATA_DIR / "claims").glob("paper_*.json"):
        for extraction in json.loads(path.read_text(encoding="utf-8"))["extractions"].values():
            for answer in extraction["answers"].values():
                if answer["status"] == "found":
                    values.add(answer["claim"]["value_as_printed"])
    return values


def test_fixed_packet_texts_contain_no_extracted_value():
    values = _stored_answer_values()
    assert values, "expected stored extractions"
    for text in (mbp.RULES, mbp.SCHEMA, mbp.README):
        assert not [v for v in values if v in text]


@pytest.fixture
def fake_corpus(tmp_path, monkeypatch):
    queries = tmp_path / "queries"
    queries.mkdir()
    (queries / "paper_006.json").write_text(json.dumps({
        "paper_id": "paper_006", "pdf_url": "https://example.org/p.pdf",
        "queries": [{"query_id": "arcene_auroc", "question": "AUROC of SAINT on Arcene.", "seed_claim": "x"}]}))
    for module in (mbp, ip):
        monkeypatch.setattr(module, "QUERIES_DIR", queries)
        monkeypatch.setattr(module, "extract_pdf_text", lambda path: PDF)
    return tmp_path


def test_packet_has_questions_pages_and_template_but_no_answers(fake_corpus):
    out = fake_corpus / "packet"
    assert mbp.make_packet(out) == {"papers": 1, "questions": 1}
    assert json.loads((out / "questions" / "paper_006.json").read_text())["queries"] == [
        {"query_id": "arcene_auroc", "question": "AUROC of SAINT on Arcene."}]  # internal fields dropped
    assert "=== PAGE 2 ===\nTable 2" in (out / "papers" / "paper_006.txt").read_text(encoding="utf-8")
    assert json.loads((out / "answers.json").read_text())["paper_006"]["arcene_auroc"]["status"] is None
    assert json.loads((out / "manifest.json").read_text())["paper_006"]["pdf_sha256"] == SHA
    assert str(out) in (out / "README.md").read_text(encoding="utf-8")


def test_packet_refuses_the_repository(fake_corpus):
    with pytest.raises(ValueError, match="outside the repository"):
        mbp.make_packet(mbp.PROJECT_ROOT / "tmp_packet")


def test_existing_answers_are_not_overwritten(fake_corpus):
    out = fake_corpus / "packet"
    mbp.make_packet(out)
    (out / "answers.json").write_text('{"filled": true}')
    mbp.make_packet(out)
    assert json.loads((out / "answers.json").read_text()) == {"filled": True}


def _found(quote="SAINT 93.3 91.04", page=2, value="91.04"):
    return {"status": "found", "reason": "r", "claim": {
        "metric_name": "auroc", "value_as_printed": value, "unit": "percent", "dataset": "Arcene",
        "model_variant": "SAINT", "split": "not_stated", "higher_is_better": True, "table_or_figure": "Table 2",
        "page": page, "source_quote": quote, "confidence": 0.9}}


@pytest.mark.parametrize("answer, problem", [
    (_found(), None),
    ({"status": "not_found", "reason": "absent", "claim": None}, None),
    (_found(quote="SAINT 93.3 91.05", value="91.05"), "not on page 2"),
    (_found(page=7), "does not exist"),
    ({"status": None, "reason": "", "claim": None}, "status must be"),
    ({"status": "not_found", "reason": "", "claim": None}, "needs a reason"),
    (_found(value="91.04 "), "invalid claim"),
])
def test_import_checks(fake_corpus, answer, problem):
    problems = ip.check_answers({"paper_006": {"arcene_auroc": answer}}, pdf_dir=fake_corpus)
    if problem is None:
        assert problems == []
    else:
        assert problems and problem in problems[0]


def test_import_needs_every_question(fake_corpus):
    assert "questions" in ip.check_answers({"paper_006": {}}, pdf_dir=fake_corpus)[0]
