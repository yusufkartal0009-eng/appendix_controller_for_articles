"""The PDF export of the final report keeps its text, the AI assistance statement and any DRAFT mark (#567)."""

import importlib.util
import sys
from io import BytesIO

import pytest
from pypdf import PdfReader

from src.config import PROJECT_ROOT

SCRIPT = PROJECT_ROOT / "scripts" / "export_report.py"
spec = importlib.util.spec_from_file_location("export_report", SCRIPT)
export_report = importlib.util.module_from_spec(spec)
sys.modules["export_report"] = export_report
spec.loader.exec_module(export_report)

REPORT = (PROJECT_ROOT / "docs" / "report" / "REPORT.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pdf_bytes():
    return export_report.render_bytes(REPORT)


def test_the_five_characters_outside_latin1_are_written_in_ascii_and_others_become_a_question_mark():
    assert export_report.to_latin1("a ≥ b ≤ c → d – e — f") == "a >= b <= c -> d - e  -  f"
    assert export_report.to_latin1("café ± μ") == "café ± ?"


def test_markdown_blocks_are_recognized():
    text = "# Title\n\nA para\nthat continues.\n\n- one\n  more\n- two\n\n1. first\n\n> quoted\n\n---\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n<!-- hidden -->\n"
    kinds = [kind for kind, _ in export_report.blocks(text)]
    assert kinds == ["heading", "para", "item", "item", "item", "quote", "rule", "table"]
    blocks = {k: c for k, c in export_report.blocks(text)}
    assert blocks["para"] == "A para that continues."
    assert blocks["table"] == [["a", "b"], ["1", "2"]]


def test_html_comments_and_a_missing_final_newline_do_not_matter():
    assert export_report.blocks("<!-- a\nb -->\nText") == [("para", "Text")]


def test_empty_markdown_makes_a_one_page_pdf():
    reader = PdfReader(BytesIO(export_report.render_bytes("")))
    assert len(reader.pages) == 1


def test_a_table_with_ragged_rows_and_unicode_does_not_fail():
    text = "| a | b | c |\n|---|---|---|\n| 1 |\n| é | ≥ | `x` | extra |\n"
    assert "1" in export_report.pdf_text(export_report.render_bytes(text))


def test_the_report_becomes_a_pdf_with_pages_and_the_title_on_the_first(pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) > 5
    assert (reader.pages[0].extract_text() or "").startswith("Repro Radar - Final Report")


def test_the_ai_assistance_statement_is_in_the_pdf_word_for_word(pdf_bytes):
    marker = "### AI assistance statement"
    statement = REPORT.split(marker, 1)[1].split("\n- **Sources:**", 1)[0].strip()
    assert statement.startswith("This work was compiled with AI assistance.")
    assert export_report.squash(export_report.strip_markers(statement)) in export_report.squash(export_report.pdf_text(pdf_bytes))


def test_every_draft_mark_of_the_markdown_is_in_the_pdf(pdf_bytes):
    assert export_report.pdf_text(pdf_bytes).count("DRAFT") == REPORT.count("DRAFT")


def test_every_paragraph_list_item_heading_and_table_cell_is_in_the_pdf(pdf_bytes):
    text = export_report.squash(export_report.pdf_text(pdf_bytes))
    missing = []
    for kind, content in export_report.blocks(REPORT):
        if kind == "heading":
            pieces = [content[1]]
        elif kind in ("para", "quote"):
            pieces = [content]
        elif kind == "item":
            pieces = [content[2]]
        elif kind == "table":
            pieces = [cell for row in content for cell in row]
        else:
            pieces = []
        missing += [piece for piece in pieces if export_report.squash(export_report.strip_markers(piece)) not in text]
    assert missing == []


def test_the_committed_pdf_has_the_text_of_the_current_report():
    committed = PROJECT_ROOT / "docs" / "report" / "REPORT.pdf"
    assert committed.is_file(), "run python scripts/export_report.py"
    fresh = export_report.render_bytes(REPORT)
    assert export_report.squash(export_report.pdf_text(committed.read_bytes())) == export_report.squash(export_report.pdf_text(fresh)), (
        "docs/report/REPORT.pdf is out of date: run python scripts/export_report.py")


def test_a_draft_mark_in_the_markdown_survives_in_a_heading_a_paragraph_and_a_table():
    text = "# DRAFT title\n\nThis paragraph is a DRAFT.\n\n| DRAFT | b |\n|---|---|\n| 1 | **DRAFT** |\n"
    assert export_report.pdf_text(export_report.render_bytes(text)).count("DRAFT") == text.count("DRAFT")
