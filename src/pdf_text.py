"""Page-by-page text of paper PDFs, cached by the PDF's SHA-256 (W2, #130).

Page numbers are PDF pages (1 = first page of the file), as in docs/CLAIM_SCHEMA.md. The cache key is the hash of the
PDF bytes, so the same file is extracted once and any other version of the paper gets its own entry. The text is
what `pypdf` extracts; see docs/PDF_TEXT_EXTRACTION.md for its known limitations (tables can collapse into one line).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pypdf

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = DATA_DIR / "pdf_text_cache"

# pypdf sometimes puts a space between a digit and the decimal point that follows it ("0 .850" for "0.850").
_SPLIT_NUMBER = re.compile(r"(?<=\d) (?=\.\d)")


def repair_split_numbers(text: str) -> str:
    """Join numbers that the PDF text extraction split before their decimal point: "0 .850" -> "0.850" (#162).

    Only the pattern digit, one space, ".", digit is changed. Spacing after a period ("2019. 22", common in
    reference lists) is left alone. See docs/PDF_TEXT_EXTRACTION.md.
    """
    return _SPLIT_NUMBER.sub("", text)


@dataclass(frozen=True)
class PdfText:
    """Text of one exact PDF file, one string per page."""

    sha256: str
    pages: list[str]
    extractor: str  # e.g. "pypdf 6.19.0"

    def page(self, number: int) -> str:
        """Text of PDF page `number` (1-based)."""
        if not 1 <= number <= len(self.pages):
            raise IndexError(f"page {number} out of range 1..{len(self.pages)}")
        return self.pages[number - 1]

    def find(self, needle: str) -> list[int]:
        """PDF page numbers (1-based) whose text contains `needle` verbatim."""
        return [i for i, text in enumerate(self.pages, start=1) if needle in text]


def sha256_of(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract(path: Path) -> list[str]:
    reader = pypdf.PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages]


def extract_pdf_text(pdf_path: str | Path, cache_dir: str | Path | None = DEFAULT_CACHE_DIR) -> PdfText:
    """Return the page texts of `pdf_path`, from the cache when this exact file was extracted before.

    `cache_dir=None` disables the cache. A cache entry that cannot be read, or that was written by another
    extractor version, is replaced by a fresh extraction.
    """
    path = Path(pdf_path)
    sha = sha256_of(path)
    extractor = f"pypdf {pypdf.__version__}"
    cache_file = Path(cache_dir) / f"{sha}.json" if cache_dir is not None else None

    if cache_file is not None and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("sha256") == sha and cached.get("extractor") == extractor:
                return PdfText(sha256=sha, pages=list(cached["pages"]), extractor=extractor)
            logger.info("Cache entry %s is from %s; extracting again", cache_file.name, cached.get("extractor"))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Unreadable cache entry %s (%s); extracting again", cache_file, exc)

    result = PdfText(sha256=sha, pages=_extract(path), extractor=extractor)
    if cache_file is not None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"sha256": sha, "extractor": extractor, "source_name": path.name, "pages": result.pages}
        cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return result
