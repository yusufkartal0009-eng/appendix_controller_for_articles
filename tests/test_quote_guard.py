"""Verbatim quote guard (W4, #132): only claims whose value and quote occur in the paper may be scored."""

import pytest

from src.claim_schema import ClaimSet, ExtractedClaim
from src.pdf_text import PdfText
from src.quote_guard import (
    AUTO_QUOTE_MATCH,
    UNVERIFIED,
    find_on_page,
    occurs_as_words,
    scorable_claims,
    verify_claim,
    verify_claim_set,
)

SHA = "b" * 64
PDF = PdfText(
    sha256=SHA,
    pages=[
        "Datasets: California Housing (CA), Adult (AD). Models: FT-Transformer (FT-T), ResNet, XGBoost.",
        "Table 2: Results\nCA ↓ AD ↑\nResNet 0.486 0 .854\nFT-T 0.459 0 .859\nThe EP300 dataset is not used here.",
    ],
    extractor="pypdf test",
)


def _claim(**overrides):
    data = {"metric_name": "rmse", "value_as_printed": "0.459", "unit": "none", "dataset": "California Housing",
            "model_variant": "FT-T", "split": "test", "higher_is_better": False, "table_or_figure": "Table 2",
            "page": 2, "source_quote": "FT-T 0.459 0 .859", "confidence": 0.9}
    data.update(overrides)
    return ExtractedClaim(**data)


def test_matching_claim_is_verified():
    result = verify_claim(_claim(), PDF, SHA)
    assert result.status == AUTO_QUOTE_MATCH, result.reasons
    assert result.checks["quote_match"] == "exact" and result.checks["value_match"] == "exact"


def test_quote_across_a_line_break_matches_with_whitespace_normalized():
    claim = _claim(value_as_printed="0.486", source_quote="ResNet 0.486 0 .854 FT-T 0.459")  # page has a newline
    result = verify_claim(claim, PDF, SHA)
    assert result.status == AUTO_QUOTE_MATCH
    assert result.checks["quote_match"] == "whitespace_normalized"


@pytest.mark.parametrize("overrides, reason", [
    ({"source_quote": "FT-T 0.459 0.858", "value_as_printed": "0.858"}, "does not occur on page 2"),  # wrong digit
    ({"source_quote": "FT-T 0.461", "value_as_printed": "0.461"}, "does not occur on page 2"),         # invented value
    ({"page": 1}, "does not occur on page 1"),                                                          # wrong page
    ({"page": 9}, "page 9 does not exist"),
    ({"dataset": "EP3602"}, "dataset 'EP3602' does not occur in the paper"),                           # invented dataset
    ({"model_variant": "TabNet"}, "model_variant 'TabNet' does not occur in the paper"),
])
def test_non_matching_claims_stay_unverified(overrides, reason):
    result = verify_claim(_claim(**overrides), PDF, SHA)
    assert result.status == UNVERIFIED
    assert any(reason in r for r in result.reasons), result.reasons


def test_claim_from_another_pdf_is_unverified():
    result = verify_claim(_claim(), PDF, "c" * 64)
    assert result.status == UNVERIFIED
    assert "different PDF" in result.reasons[0]


def test_word_matching_rules():
    assert find_on_page("0 .859", PDF.page(2)) == "exact"
    assert find_on_page("0.859", PDF.page(2)) == "split_numbers_repaired"  # #162: retyped without the space
    assert find_on_page("FT-T 0.459 0.859", PDF.page(2)) == "split_numbers_repaired"
    assert find_on_page("0.858", PDF.page(2)) is None
    assert occurs_as_words("CA", "CA ↓ AD ↑") and not occurs_as_words("CA", "the cat")
    assert occurs_as_words("EP300", PDF.page(2)) and not occurs_as_words("EP3602", PDF.page(2))


def test_only_verified_claims_are_scorable():
    claim_set = ClaimSet(paper_id="paper_003", pdf_url="https://arxiv.org/pdf/2106.11959v5", pdf_sha256=SHA,
                         extractor_version="test",
                         claims=[_claim(), _claim(dataset="EP3602"), _claim(value_as_printed="0.461",
                                                                             source_quote="FT-T 0.461")])
    verified = verify_claim_set(claim_set, PDF)
    assert [v.result.status for v in verified] == [AUTO_QUOTE_MATCH, UNVERIFIED, UNVERIFIED]
    assert scorable_claims(verified) == [claim_set.claims[0]]


def test_retyped_value_matches_after_number_repair_and_table_claims_are_flagged():
    claim = _claim(value_as_printed="0.859", source_quote="FT-T 0.459 0.859", metric_name="accuracy",
                   dataset="Adult")
    result = verify_claim(claim, PDF, SHA)
    assert result.status == AUTO_QUOTE_MATCH, result.reasons
    assert result.checks["quote_match"] == result.checks["value_match"] == "split_numbers_repaired"
    assert result.checks["from_table"] is True
    assert verify_claim(_claim(table_or_figure=None), PDF, SHA).checks["from_table"] is False


# Bug hunt suspicion 2 (#498): the value was looked up as a plain substring of the page
def _numbers_pdf(page_text):
    return PdfText(sha256=SHA, pages=[page_text], extractor="pypdf test")


@pytest.mark.parametrize("value, page_text", [
    ("0.5", "ResNet 10.55 and more"),        # inside a longer number on both sides
    ("0.5", "ResNet 0.52 and more"),         # a longer decimal
    ("1.5", "ResNet 1.5.2 and more"),        # a version
])
def test_a_value_inside_a_longer_number_is_not_found_on_the_page(value, page_text):
    claim = _claim(value_as_printed=value, source_quote=page_text.split(" and")[0], page=1, unit="none")
    result = verify_claim(claim, _numbers_pdf(page_text + "\nDatasets: California Housing. Models: FT-T."), SHA)
    assert result.status == UNVERIFIED
    assert result.checks["value_match"] is None


@pytest.mark.parametrize("value, quote, page_text", [
    ("0.5", "ResNet 0.5", "ResNet 0.5 and more"),
    ("0.934±.0086", "AUC 0.934±.0086", "Mean AUC 0.934±.0086 0.934±.0084"),
    ("96.99 %", "Accuracy 96.99 %", "Accuracy 96.99 % on test"),
    (".859", "FT-T 0 .859", "FT-T 0 .859"),   # the extraction split the number before its decimal point (#162)
    ("0.459", "(0.459)", "RMSE (0.459), see"),
])
def test_a_value_printed_as_a_whole_number_is_still_found(value, quote, page_text):
    claim = _claim(value_as_printed=value, source_quote=quote, page=1, unit="percent" if "%" in value else "none")
    page = page_text + "\nDatasets: California Housing. Models: FT-T."
    assert verify_claim(claim, _numbers_pdf(page), SHA).checks["value_match"] is not None
