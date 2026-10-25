"""Verbatim quote guard against invented claims (W4, #132).

A claim is verified automatically (`AUTO_QUOTE_MATCH`) only if what it says can be found in the paper text it was
extracted from. Everything else stays `UNVERIFIED` and must not be used in scoring: scoring takes its claims from
`scorable_claims()`. Rules (docs/CLAIM_SCHEMA.md section 5):

1. The claim set's `pdf_sha256` equals the hash of the text's PDF, and the cited page exists.
2. `source_quote` and `value_as_printed` occur on the cited page (the value as a whole number: `0.5` is not found inside
   `10.55`, #498). Characters must be identical; the only tolerances
   are that any run of whitespace counts as one space (the extracted text breaks lines where a quote may use a
   space), and that numbers the extraction split before their decimal point are joined on both sides first
   (`0 .859` = `0.859`, #162). The mode that matched is recorded.
3. `dataset` and `model_variant` occur somewhere in the paper text as whole words (ignoring case and whitespace
   runs, so "CA" does not match inside "cat"), so a claim
   about a dataset or model the paper never mentions (the seed's invented "EP3602") cannot pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.claim_schema import ClaimSet, ExtractedClaim
from src.pdf_text import PdfText, repair_split_numbers

AUTO_QUOTE_MATCH = "AUTO_QUOTE_MATCH"
UNVERIFIED = "UNVERIFIED"

_WHITESPACE = re.compile(r"\s+")


def _squash(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def find_on_page(needle: str, page_text: str) -> str | None:
    """'exact', 'whitespace_normalized', 'split_numbers_repaired', or None when `needle` does not occur."""
    if needle and needle in page_text:
        return "exact"
    squashed = _squash(needle)
    if squashed and squashed in _squash(page_text):
        return "whitespace_normalized"
    repaired = repair_split_numbers(squashed)
    if repaired and repaired in repair_split_numbers(_squash(page_text)):
        return "split_numbers_repaired"
    return None


def _whole_number(needle: str) -> re.Pattern[str]:
    """`needle` where it is not part of a longer number: not preceded by a digit or a decimal point, and not followed by a digit
    or by a decimal point and a digit (`0.5` is not in `10.55`, `0.52` or `1.5.2`). A needle that starts with a decimal point
    (`.859`) may follow a single `0`."""
    head = r"(?:(?<![\d.])0?|(?<!\d))" if needle.startswith(".") else r"(?<![\d.])"
    return re.compile(head + re.escape(needle) + r"(?!\d|\.\d)")


def find_value_on_page(value: str, page_text: str) -> str | None:
    """Like `find_on_page`, but the value must be printed as a whole number: a value that only occurs inside a longer number
    (`0.5` inside `10.55`) is not found (bug hunt suspicion 2, #498). Same three modes."""
    if not value:
        return None
    candidates = [("exact", value, page_text), ("whitespace_normalized", _squash(value), _squash(page_text)),
                  ("split_numbers_repaired", repair_split_numbers(_squash(value)), repair_split_numbers(_squash(page_text)))]
    for mode, needle, text in candidates:
        if needle and _whole_number(needle).search(text):
            return mode
    return None


def occurs_as_words(name: str, text: str) -> bool:
    """True if `name` occurs in `text` as whole words, ignoring case and whitespace runs ("CA" does not match "cat")."""
    squashed = _squash(name).lower()
    if not squashed:
        return False
    return re.search(r"(?<!\w)" + re.escape(squashed) + r"(?!\w)", _squash(text).lower()) is not None


@dataclass
class GuardResult:
    status: str
    checks: dict[str, object] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


@dataclass
class VerifiedClaim:
    claim: ExtractedClaim
    result: GuardResult


def verify_claim(claim: ExtractedClaim, pdf: PdfText, pdf_sha256: str) -> GuardResult:
    reasons: list[str] = []
    checks: dict[str, object] = {}

    checks["same_pdf"] = pdf_sha256 == pdf.sha256
    if not checks["same_pdf"]:
        reasons.append("the claim was extracted from a different PDF")
    checks["page_exists"] = 1 <= claim.page <= len(pdf.pages)
    if not checks["page_exists"]:
        reasons.append(f"page {claim.page} does not exist (the PDF has {len(pdf.pages)} pages)")

    if checks["same_pdf"] and checks["page_exists"]:
        page_text = pdf.page(claim.page)
        # Table rows lose their column structure in the extracted text (docs/PDF_TEXT_EXTRACTION.md), so table
        # claims are flagged; the owner reviews them in W7 (#134) even when the quote matches.
        checks["from_table"] = bool(claim.table_or_figure) and claim.table_or_figure.lower().startswith("table")
        checks["quote_match"] = find_on_page(claim.source_quote, page_text)
        checks["value_match"] = find_value_on_page(claim.value_as_printed, page_text)
        if checks["quote_match"] is None:
            reasons.append(f"source_quote does not occur on page {claim.page}")
        if checks["value_match"] is None:
            reasons.append(f"value_as_printed {claim.value_as_printed!r} does not occur on page {claim.page}")

        paper = "\n".join(pdf.pages)
        for name in ("dataset", "model_variant"):
            value = getattr(claim, name)
            checks[f"{name}_in_paper"] = occurs_as_words(value, paper)
            if not checks[f"{name}_in_paper"]:
                reasons.append(f"{name} {value!r} does not occur in the paper")

    return GuardResult(status=UNVERIFIED if reasons else AUTO_QUOTE_MATCH, checks=checks, reasons=reasons)


def verify_claim_set(claim_set: ClaimSet, pdf: PdfText) -> list[VerifiedClaim]:
    return [VerifiedClaim(claim, verify_claim(claim, pdf, claim_set.pdf_sha256)) for claim in claim_set.claims]


def scorable_claims(verified: list[VerifiedClaim]) -> list[ExtractedClaim]:
    """The only claims scoring may use: those that passed the guard. (W7 adds the human acceptance on top.)"""
    return [v.claim for v in verified if v.result.status == AUTO_QUOTE_MATCH]
