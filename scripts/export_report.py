#!/usr/bin/env python3
"""Export the final report (docs/report/REPORT.md) to a PDF with fpdf2, which the project already depends on (#567).

    python scripts/export_report.py                  # write docs/report/REPORT.pdf
    python scripts/export_report.py --check          # exit 1 if the committed PDF has other text than a fresh rendering
    python scripts/export_report.py --output PATH    # write somewhere else

The renderer reads the Markdown subset the report uses: headings, paragraphs, bullet and numbered lists, block quotes, tables,
horizontal rules, `**bold**`, `*italic*`, and `code`. HTML comments (the markers of the generated number blocks) are not shown.
The PDF uses core fonts, so the five characters of the report outside Latin-1 are written in ASCII (see `REPLACEMENTS`);
every other character is kept. Nothing is added to the text and nothing is left out: the AI assistance statement and any `DRAFT`
mark are copied as they stand (a test compares them with the Markdown).
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_MD = PROJECT_ROOT / "docs" / "report" / "REPORT.md"
REPORT_PDF = PROJECT_ROOT / "docs" / "report" / "REPORT.pdf"
CREATION_DATE = datetime(2026, 10, 28, 12, 0, 0, tzinfo=UTC)  # fixed, so that a rendering does not depend on the day it is made

# Characters outside Latin-1 that the report uses, and what the PDF shows instead. Any other such character becomes "?".
REPLACEMENTS = {"—": " - ", "–": "-", "≥": ">=", "≤": "<=", "→": "->"}

HEADING_SIZES = {1: 18, 2: 14, 3: 12, 4: 11}
BODY_SIZE = 10
TABLE_SIZE = 7.5
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BULLET = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
RULE = re.compile(r"^\s*(-{3,}|\*{3,})\s*$")


def to_latin1(text: str) -> str:
    """The text with the replacements applied and anything else outside Latin-1 written as '?'."""
    for char, ascii_text in REPLACEMENTS.items():
        text = text.replace(char, ascii_text)
    return text.encode("latin-1", "replace").decode("latin-1")


def clean(text: str) -> str:
    return to_latin1(LINK.sub(r"\1 (\2)", text))


def strip_markers(text: str) -> str:
    """Plain text of an inline-marked string (used in table cells, which have one style)."""
    return clean(INLINE.sub(lambda m: m.group(0).strip("*`"), text))


def blocks(markdown: str) -> list[tuple[str, object]]:
    """Split the Markdown into (kind, content) blocks: heading, para, item, quote, table, rule."""
    lines = COMMENT.sub("", markdown).splitlines()
    out: list[tuple[str, object]] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
        elif RULE.match(line):
            out.append(("rule", ""))
            i += 1
        elif line.lstrip().startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            out.append(("heading", (min(level, 4), line.lstrip("#").strip())))
            i += 1
        elif line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append(("table", rows))
        elif line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip(">").strip())
                i += 1
            out.append(("quote", " ".join(q for q in quote if q)))
        elif BULLET.match(line):
            match = BULLET.match(line)
            indent, marker, text = len(match.group(1)), match.group(2), match.group(3)
            i += 1
            while i < len(lines) and lines[i].strip() and not BULLET.match(lines[i]) and lines[i].startswith(" "):
                text += " " + lines[i].strip()
                i += 1
            out.append(("item", (indent, marker, text)))
        else:
            text = line.strip()
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^\s*(#|\||>|[-*]\s|\d+\.\s)", lines[i]) and not RULE.match(lines[i]):
                text += " " + lines[i].strip()
                i += 1
            out.append(("para", text))
    return out


class ReportPdf(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.cell(0, 6, f"Repro Radar - final report - page {self.page_no()}", align="C")


def write_inline(pdf: FPDF, text: str, size: float, line_height: float, base_style: str = "") -> None:
    """Write one paragraph with bold, italic and code spans; the text wraps inside the current margins."""
    for part in INLINE.split(clean(text)):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            pdf.set_font("Helvetica", "B" + base_style.replace("B", ""), size)
            pdf.write(line_height, part[2:-2])
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            pdf.set_font("Courier", "", size - 1)
            pdf.write(line_height, part[1:-1])
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            pdf.set_font("Helvetica", "I" + base_style.replace("I", ""), size)
            pdf.write(line_height, part[1:-1])
        else:
            pdf.set_font("Helvetica", base_style, size)
            pdf.write(line_height, part)
    pdf.set_font("Helvetica", "", size)


def column_widths(rows: list[list[str]], total: float) -> list[float]:
    count = max(len(r) for r in rows)
    longest = [max((len(strip_markers(r[c])) if c < len(r) else 0) for r in rows) for c in range(count)]
    weights = [min(max(n, 6), 60) for n in longest]
    return [total * w / sum(weights) for w in weights]


def render(markdown: str) -> FPDF:
    pdf = ReportPdf(format="A4")
    pdf.set_margins(16, 16, 16)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_title("Repro Radar - Final Report")
    pdf.set_creator("scripts/export_report.py")
    pdf.set_creation_date(CREATION_DATE)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin
    for kind, content in blocks(markdown):
        pdf.set_x(pdf.l_margin)
        if kind == "heading":
            level, text = content  # type: ignore[misc]
            pdf.ln(3 if level > 1 else 5)
            pdf.set_font("Helvetica", "B", HEADING_SIZES[level])
            pdf.multi_cell(width, HEADING_SIZES[level] * 0.55, strip_markers(text), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif kind == "para":
            write_inline(pdf, str(content), BODY_SIZE, 4.6)
            pdf.ln(6.5)
        elif kind == "quote":
            pdf.set_left_margin(pdf.l_margin + 5)
            pdf.set_x(pdf.l_margin)
            write_inline(pdf, str(content), BODY_SIZE - 1, 4.4, "I")
            pdf.ln(6)
            pdf.set_left_margin(16)
        elif kind == "item":
            indent, marker, text = content  # type: ignore[misc]
            shift = 5 + min(indent, 8) * 1.2
            pdf.set_font("Helvetica", "", BODY_SIZE)
            pdf.set_x(pdf.l_margin + shift - 4.5)
            pdf.write(4.6, "-" if marker in "-*" else marker)
            pdf.set_left_margin(16 + shift + (1.5 if marker not in "-*" else 0))
            pdf.set_x(pdf.l_margin)
            write_inline(pdf, text, BODY_SIZE, 4.6)
            pdf.ln(5.6)
            pdf.set_left_margin(16)
        elif kind == "rule":
            pdf.ln(1)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + width, pdf.get_y())
            pdf.ln(3)
        elif kind == "table":
            rows: list[list[str]] = content  # type: ignore[assignment]
            columns = max(len(r) for r in rows)
            pdf.set_font("Helvetica", "", TABLE_SIZE)
            with pdf.table(col_widths=column_widths(rows, width), text_align="LEFT", line_height=3.6, first_row_as_headings=True,
                           width=width) as table:
                for cells in rows:
                    row = table.row()
                    for c in range(columns):
                        row.cell(strip_markers(cells[c]) if c < len(cells) else "")
            pdf.ln(3)
    return pdf


def render_bytes(markdown: str) -> bytes:
    return bytes(render(markdown).output())


FOOTER = re.compile(r"Repro Radar - final report - page \d+")


def pdf_text(data: bytes) -> str:
    """The text of the PDF without the page footers (a footer can fall in the middle of a paragraph)."""
    return FOOTER.sub("", "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages))


def squash(text: str) -> str:
    """Text without whitespace, so that the line breaks of a PDF do not matter in a comparison."""
    return re.sub(r"\s+", "", text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export docs/report/REPORT.md to a PDF.")
    parser.add_argument("--input", type=Path, default=REPORT_MD)
    parser.add_argument("--output", type=Path, default=REPORT_PDF)
    parser.add_argument("--check", action="store_true", help="fail if the committed PDF has other text than a fresh rendering")
    args = parser.parse_args()
    data = render_bytes(args.input.read_text(encoding="utf-8"))
    if args.check:
        if not args.output.is_file():
            print(f"{args.output} does not exist")
            return 1
        if squash(pdf_text(args.output.read_bytes())) != squash(pdf_text(data)):
            print(f"{args.output} has other text than a rendering of {args.input}; run scripts/export_report.py")
            return 1
        print(f"{args.output} matches {args.input}")
        return 0
    args.output.write_bytes(data)
    reader = PdfReader(BytesIO(data))
    first = (reader.pages[0].extract_text() or "").strip().splitlines()
    print(f"wrote {args.output}: {len(reader.pages)} pages, {len(data)} bytes; first line: {first[0] if first else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
