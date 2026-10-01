"""The claim schema module follows docs/CLAIM_SCHEMA.md (W1, #129)."""

import re

import pytest
from pydantic import ValidationError

from src.claim_schema import (
    ClaimSet,
    ExtractedClaim,
    NotFound,
    Split,
    Unit,
    normalize_value,
)
from src.config import PROJECT_ROOT

DOC = (PROJECT_ROOT / "docs" / "CLAIM_SCHEMA.md").read_text(encoding="utf-8")


def _doc_table(section_title):
    lines = DOC.split(section_title, 1)[1].split("\n## ", 1)[0].splitlines()
    header_rows = {i for i, line in enumerate(lines[1:]) if line.startswith("|---")}  # row before a separator
    return [[c.strip() for c in line.strip().strip("|").split("|")]
            for i, line in enumerate(lines) if line.startswith("| `") and i not in header_rows]


def test_documented_normalization_examples():
    rows = _doc_table("## 2. Normalization rule")
    assert len(rows) == 6
    for printed, unit, expected in rows:
        assert normalize_value(printed.strip("`"), unit.strip("`")) == float(expected.strip("`")), printed


def test_documented_claim_fields_equal_the_model():
    documented = [row[0].strip("`") for row in _doc_table("## 1. One claim")]
    assert documented == list(ExtractedClaim.model_fields)


def test_documented_units_and_splits_equal_the_enums():
    units = re.findall(r"`(\w+)`", DOC.split("| `unit` |", 1)[1].split("\n", 1)[0])
    splits = re.findall(r"`(\w+)`", DOC.split("| `split` |", 1)[1].split("\n", 1)[0])
    assert set(units) == {u.value for u in Unit}
    assert set(splits) == {s.value for s in Split}


@pytest.mark.parametrize("printed", ["96,99", "1,23", "abc", "", "12.3.4", "N/A", "~0.5"])
def test_invalid_values_are_rejected(printed):
    with pytest.raises(ValueError):
        normalize_value(printed, "none")


def _claim(**overrides):
    data = {
        "metric_name": "rmse", "value_as_printed": "0.459", "unit": "none", "dataset": "California Housing",
        "model_variant": "FT-Transformer", "split": "test", "higher_is_better": False,
        "table_or_figure": "Table 2", "page": 7, "source_quote": "FT-T 0.459", "confidence": 0.9,
    }
    data.update(overrides)
    return ExtractedClaim(**data)


def test_value_normalized_is_computed_and_checked():
    assert _claim().value_normalized == 0.459
    assert _claim(value_as_printed="96.99 %", unit="percent", source_quote="FT-T 96.99 %").value_normalized == 0.9699
    with pytest.raises(ValidationError, match="does not follow the rule"):
        _claim(value_normalized=0.46)


@pytest.mark.parametrize("overrides", [
    {"page": 0},
    {"confidence": 1.5},
    {"split": "holdout"},
    {"unit": "percentage"},
    {"metric_name": "RMSE score"},
    {"source_quote": "FT-T 0.46"},  # does not contain value_as_printed
    {"source_quote": "x" * 501},
    {"extra_field": 1},
])
def test_invalid_claims_are_rejected(overrides):
    with pytest.raises(ValidationError):
        _claim(**overrides)


def test_claim_set_holds_claims_and_not_found_answers():
    claim_set = ClaimSet(
        paper_id="paper_005", pdf_url="https://www.biorxiv.org/content/10.1101/2020.04.21.053975v1.full.pdf",
        pdf_sha256="a" * 64, extractor_version="w3-0.1", claims=[],
        not_found=[NotFound(query="auroc on EP3602", reason='dataset "EP3602" does not occur in the paper')],
    )
    assert claim_set.not_found[0].query == "auroc on EP3602"
    with pytest.raises(ValidationError):
        ClaimSet(paper_id="paper_5", pdf_url="x", pdf_sha256="a" * 64, extractor_version="v")
    with pytest.raises(ValidationError):
        ClaimSet(paper_id="paper_005", pdf_url="x", pdf_sha256="xyz", extractor_version="v")
