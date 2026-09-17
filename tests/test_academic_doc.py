"""Unit tests verifying the generation, integrity, and layout of the academic docx document and banner asset."""

from pathlib import Path
from docx import Document
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
ASSETS_DIR = DOCS_DIR / "assets"
BANNER_PATH = ASSETS_DIR / "repro_radar_banner.png"
DOCX_PATH = DOCS_DIR / "repro_radar_introduction.docx"


def test_cover_banner_image_properties():
    assert BANNER_PATH.exists(), "Cover banner PNG must exist in docs/assets/"
    with Image.open(BANNER_PATH) as img:
        assert img.format == "PNG"
        assert img.width == 1200
        assert img.height == 420


def test_academic_introduction_docx_integrity():
    assert DOCX_PATH.exists(), "Academic introduction Word document (.docx) must exist in docs/"
    doc = Document(DOCX_PATH)

    # Verify paragraphs and text content
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Repro Radar" in full_text
    assert "Empirical Reproducibility" in full_text
    assert "Isolated Sandboxing" in full_text
    assert "Four-Tier" in full_text or "4-Tier" in full_text
    assert "Claerbout" in full_text

    # Verify tables (Metadata, Sandbox Specs, Rubric)
    assert len(doc.tables) >= 3, "Document should contain structured comparison and metadata tables"

    # Verify headings
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert any("Crisis of Empirical Reproducibility" in h for h in headings)
    assert any("Container-Isolated Sandboxing" in h for h in headings)
    assert any("Four-Tier" in h for h in headings)
    assert any("References" in h for h in headings)
