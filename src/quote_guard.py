"""Verbatim quote guard against invented claims (W4, #132).

A claim is verified automatically (`AUTO_QUOTE_MATCH`) only if what it says can be found in the paper text it was
extracted from. Everything else stays `UNVERIFIED` and must not be used in scoring: scoring takes its claims from
`scorable_claims()`. Rules (docs/CLAIM_SCHEMA.md section 5):

1. The claim set's `pdf_sha256` equals the hash of the text's PDF, and the cited page exists.
2. `source_quote` and `value_as_printed` occur on the cited page. Characters must be identical; the only tolerance is
   that any run of whitespace counts as one space (the extracted text breaks lines where a quote may use a space).
   A value retyped without the space the extraction put inside it (`0.859` for `0 .859`) does not match.
3. `dataset` and `model_variant` occur somewhere in the paper text as whole words (ignoring case and whitespace
   runs, so "CA" does not match inside "cat"), so a claim
   about a dataset or model the paper never mentions (the seed's invented "EP3602") cannot pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.claim_schema import ClaimSet, ExtractedClaim
from src.pdf_text import PdfText

AUTO_QUOTE_MATCH = "AUTO_QUOTE_MATCH"
UNVERIFIED = "UNVERIFIED"

_WHITESPACE = re.compile(r"\s+")


def _squash(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def find_on_page(needle: str, page_text: str) -> str | None:
    """'exact', 'whitespace_normalized', or None when `needle` does not occur in `page_text`."""
    if needle and needle in page_text:
        return "exact"
    squashed = _squash(needle)
    if squashed and squashed in _squash(page_text):
        return "whitespace_normalized"
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
        checks["quote_match"] = find_on_page(claim.source_quote, page_text)
        checks["value_match"] = find_on_page(claim.value_as_printed, page_text)
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
