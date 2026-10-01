"""Schema of claims extracted from paper PDFs (W1, #129). Documented in docs/CLAIM_SCHEMA.md."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Unit(str, Enum):
    PERCENT = "percent"
    FRACTION = "fraction"
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    COUNT = "count"
    NONE = "none"


class Split(str, Enum):
    TEST = "test"
    VALIDATION = "validation"
    TRAIN = "train"
    CROSS_VALIDATION = "cross_validation"
    NOT_STATED = "not_stated"


_SCALE = {Unit.PERCENT: Decimal(100), Unit.MILLISECONDS: Decimal(1000)}
_SPACES = re.compile(r"[\s   ]+")
_THOUSANDS = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")
_NUMBER = re.compile(r"^-?(\d+\.?\d*|\.\d+)$")


def normalize_value(value_as_printed: str, unit: Unit | str) -> float:
    """Canonical value of a printed number (docs/CLAIM_SCHEMA.md section 2). Raises ValueError if invalid."""
    unit = Unit(unit)
    text = re.split(r"±|\+/-", value_as_printed, maxsplit=1)[0]
    text = _SPACES.sub("", text).replace("−", "-")
    text = text.removesuffix("%")
    if "," in text:
        if not _THOUSANDS.match(text):
            raise ValueError(f"ambiguous comma in {value_as_printed!r}")
        text = text.replace(",", "")
    if not _NUMBER.match(text):
        raise ValueError(f"not a number: {value_as_printed!r}")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {value_as_printed!r}") from exc
    return float(value / _SCALE.get(unit, Decimal(1)))


class ExtractedClaim(BaseModel):
    """One number the paper reports for one metric, dataset, model, and split."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    metric_name: str = Field(..., min_length=1, pattern=r"^[a-z0-9_]+$")
    value_as_printed: str = Field(..., min_length=1)
    value_normalized: float | None = None
    unit: Unit
    dataset: str = Field(..., min_length=1)
    model_variant: str = Field(..., min_length=1)
    split: Split
    higher_is_better: bool | None
    table_or_figure: str | None
    page: int = Field(..., ge=1)
    source_quote: str = Field(..., min_length=1, max_length=500)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _normalized_value_follows_the_rule(self) -> ExtractedClaim:
        expected = normalize_value(self.value_as_printed, self.unit)
        if self.value_normalized is None:
            self.value_normalized = expected
        elif self.value_normalized != expected:
            raise ValueError(
                f"value_normalized {self.value_normalized} does not follow the rule "
                f"({self.value_as_printed!r} in {self.unit} -> {expected})"
            )
        if self.value_as_printed not in self.source_quote:
            raise ValueError("source_quote must contain value_as_printed")
        return self


class NotFound(BaseModel):
    """An explicit "not found" answer to a query (docs/CLAIM_SCHEMA.md section 4)."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class ClaimSet(BaseModel):
    """All claims extracted from one exact PDF of one paper."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str = Field(..., pattern=r"^paper_\d{3}$")
    pdf_url: str = Field(..., min_length=1)
    pdf_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    extractor_version: str = Field(..., min_length=1)
    claims: list[ExtractedClaim] = Field(default_factory=list)
    not_found: list[NotFound] = Field(default_factory=list)
