"""Page-by-page PDF text with a hash-keyed cache (W2, #130). The PDFs here are generated, not real papers."""

import json

import pytest

from src import pdf_text
from src.pdf_text import extract_pdf_text, sha256_of


def make_pdf(path, page_texts):
    """Write a minimal valid PDF with one line of Helvetica text per page."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>"]
    n = len(page_texts)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>")
    font_obj = 3 + 2 * n
    for i, text in enumerate(page_texts):
        content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {4 + 2 * i} 0 R >>")
        objects.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


@pytest.fixture
def pdf(tmp_path):
    return make_pdf(tmp_path / "paper.pdf", ["Introduction page one", "Table 2 FT-T 0.459", "References"])


def test_pages_keep_their_order_and_numbers(pdf, tmp_path):
    text = extract_pdf_text(pdf, cache_dir=None)
    assert len(text.pages) == 3
    assert "FT-T 0.459" in text.page(2)
    assert text.find("0.459") == [2]
    assert text.find("not in the paper") == []
    with pytest.raises(IndexError):
        text.page(0)
    with pytest.raises(IndexError):
        text.page(4)


def test_cache_is_keyed_by_the_pdf_hash_and_reused(pdf, tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    first = extract_pdf_text(pdf, cache_dir=cache)
    entry = cache / f"{sha256_of(pdf)}.json"
    assert entry.exists() and first.sha256 == sha256_of(pdf)
    assert json.loads(entry.read_text(encoding="utf-8"))["extractor"] == first.extractor

    def no_extraction(path):
        raise AssertionError("the cached text should have been used")

    monkeypatch.setattr(pdf_text, "_extract", no_extraction)
    assert extract_pdf_text(pdf, cache_dir=cache).pages == first.pages


def test_another_pdf_version_gets_its_own_entry(pdf, tmp_path):
    cache = tmp_path / "cache"
    other = make_pdf(tmp_path / "paper_v2.pdf", ["Introduction page one", "Table 2 FT-T 0.460", "References"])
    a = extract_pdf_text(pdf, cache_dir=cache)
    b = extract_pdf_text(other, cache_dir=cache)
    assert a.sha256 != b.sha256
    assert len(list(cache.glob("*.json"))) == 2
    assert b.find("0.459") == [] and b.find("0.460") == [2]


@pytest.mark.parametrize("bad_entry", ["{not json", json.dumps({"sha256": "x", "extractor": "pypdf 0.0", "pages": []})])
def test_unreadable_or_stale_cache_entries_are_replaced(pdf, tmp_path, bad_entry):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / f"{sha256_of(pdf)}.json").write_text(bad_entry, encoding="utf-8")
    text = extract_pdf_text(pdf, cache_dir=cache)
    assert text.find("0.459") == [2]
    assert json.loads((cache / f"{text.sha256}.json").read_text(encoding="utf-8"))["pages"] == text.pages
