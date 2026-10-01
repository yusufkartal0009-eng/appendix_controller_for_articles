"""Query-driven claim extraction from paper text with Claude (W3, #131).

For one paper, the model answers a fixed list of queries ("RMSE of FT-Transformer on California Housing"). Each answer
is either a claim in the shape of docs/CLAIM_SCHEMA.md, with a verbatim quote and the PDF page, or an explicit "not
found" with a reason. The model never computes `value_normalized`; it is derived from `value_as_printed` by the
schema's rule. Decisions behind the setup (model, no temperature, caching) are in docs/DECISIONS.md, D-003.

The API key is read from the environment (`ANTHROPIC_API_KEY`) by the SDK; it is never passed in code or stored.
Responses are cached under a hash of everything that determines them, so a repeated run returns the stored answer.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.claim_schema import ClaimSet, ExtractedClaim, NotFound, Split, Unit
from src.config import DATA_DIR
from src.pdf_text import PdfText

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
EFFORT = "high"
MAX_TOKENS = 16000
PROMPT_VERSION = "w3-v1"
DEFAULT_CACHE_DIR = DATA_DIR / "llm_cache"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Claude Opus 5.5 list prices in USD per million tokens (input, output, cache write, cache read), for cost estimates.
PRICE_PER_MTOK = {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20}

SYSTEM_PROMPT = """You extract reported numbers from the text of one scientific paper, to answer a fixed list of queries.

The paper text was extracted from the PDF with pypdf and is given page by page between markers of the form
=== PAGE n ===, where n is the PDF page number.

Rules:
1. Answer every query exactly once, with its query_id, and nothing else.
2. Use only the given text. If the paper does not report the requested value, answer status "not_found" with a short
   reason: for example the dataset, model, or metric does not occur in the paper, or occurs only under a different
   name. Never guess, never compute a value, and never take a value from a similar dataset, model, or metric.
3. For a found value, copy value_as_printed exactly as it appears in the text, character for character, including
   spaces inside numbers (the extraction sometimes inserts them, e.g. "0 .859"), percent signs, and any ± part.
4. source_quote is one contiguous span copied exactly from the text of that page, at most 300 characters, that
   contains value_as_printed and, where possible, the row or column label. Do not correct spelling or spacing.
5. page is the number of the PAGE marker of the page the quote comes from.
6. Tables are flattened: a header line, then one line per row. Find a value's column by counting the cells. If the
   column or row of a value cannot be determined with certainty, answer "not_found" with the reason
   "column or row ambiguous" instead of guessing.
7. Fields: metric_name is a short lower-case snake_case identifier (e.g. rmse, accuracy, auroc); unit is "percent"
   if the value is printed as a percentage, otherwise fraction, seconds, milliseconds, count, or none; dataset and
   model_variant are written as in the paper; split is test, validation, train, cross_validation, or not_stated;
   higher_is_better is true, false, or null if the paper does not make it clear; table_or_figure is e.g. "Table 2"
   or null for running text; confidence is your confidence between 0 and 1.
8. For a found answer, reason is an empty string; for a not_found answer, claim is null."""

_CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "metric_name": {"type": "string"},
        "value_as_printed": {"type": "string"},
        "unit": {"type": "string", "enum": [u.value for u in Unit]},
        "dataset": {"type": "string"},
        "model_variant": {"type": "string"},
        "split": {"type": "string", "enum": [s.value for s in Split]},
        "higher_is_better": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
        "table_or_figure": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "page": {"type": "integer"},
        "source_quote": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["metric_name", "value_as_printed", "unit", "dataset", "model_variant", "split",
                 "higher_is_better", "table_or_figure", "page", "source_quote", "confidence"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "query_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["found", "not_found"]},
                    "reason": {"type": "string"},
                    "claim": {"anyOf": [_CLAIM_SCHEMA, {"type": "null"}]},
                },
                "required": ["query_id", "status", "reason", "claim"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["answers"],
    "additionalProperties": False,
}


class ExtractionError(RuntimeError):
    """The model did not produce a usable answer (refusal, truncated output, unparseable JSON)."""


@dataclass
class Query:
    query_id: str
    question: str

    def to_dict(self) -> dict[str, str]:
        return {"query_id": self.query_id, "question": self.question}


@dataclass
class ExtractionResult:
    """A claim set plus, per query, where its answer went (claim index, not found, or rejected)."""

    claim_set: ClaimSet
    answers: dict[str, dict[str, Any]]
    meta: dict[str, Any] = field(default_factory=dict)


def paper_text_block(pdf: PdfText) -> str:
    return "\n".join(f"=== PAGE {n} ===\n{text}" for n, text in enumerate(pdf.pages, start=1))


def _queries_block(queries: list[Query]) -> str:
    return "Queries (answer each one):\n" + json.dumps([q.to_dict() for q in queries], indent=2)


def cache_key(pdf: PdfText, queries: list[Query]) -> str:
    material = {
        "model": MODEL, "effort": EFFORT, "max_tokens": MAX_TOKENS, "prompt_version": PROMPT_VERSION,
        "system": SYSTEM_PROMPT, "schema": OUTPUT_SCHEMA, "pdf_sha256": pdf.sha256, "pdf_extractor": pdf.extractor,
        "queries": [q.to_dict() for q in queries],
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()


def estimate_cost_usd(usage: dict[str, Any]) -> float:
    tokens = {
        "input": usage.get("input_tokens") or 0,
        "output": usage.get("output_tokens") or 0,
        "cache_write": usage.get("cache_creation_input_tokens") or 0,
        "cache_read": usage.get("cache_read_input_tokens") or 0,
    }
    return round(sum(tokens[k] * PRICE_PER_MTOK[k] for k in tokens) / 1_000_000, 4)


def _call_model(client: Any, pdf: PdfText, queries: list[Query]) -> dict[str, Any]:
    """One Messages API call; returns the fields this module stores (not the SDK object)."""
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": paper_text_block(pdf), "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": _queries_block(queries)},
            ],
        }],
    )
    usage = getattr(response, "usage", None)
    iterations = getattr(usage, "iterations", None) or []
    return {
        "response_id": getattr(response, "id", None),
        "model": getattr(response, "model", None),
        "stop_reason": getattr(response, "stop_reason", None),
        "text": next((b.text for b in response.content if getattr(b, "type", None) == "text"), None),
        "fallback_used": any(getattr(it, "type", None) == "fallback_message" for it in iterations),
        "usage": {
            key: getattr(usage, key, None)
            for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        },
    }


def extract_claims(
    pdf: PdfText,
    paper_id: str,
    pdf_url: str,
    queries: list[Query],
    client: Any = None,
    cache_dir: str | Path | None = DEFAULT_CACHE_DIR,
) -> ExtractionResult:
    """Answer `queries` about one paper. Raises ExtractionError when the model gives no usable answer."""
    key = cache_key(pdf, queries)
    cache_file = Path(cache_dir) / f"{key}.json" if cache_dir is not None else None
    from_cache = bool(cache_file and cache_file.exists())

    if from_cache:
        call = json.loads(cache_file.read_text(encoding="utf-8"))["call"]
    else:
        if client is None:
            import anthropic  # imported here so the module and its tests do not need the SDK or a key

            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        call = _call_model(client, pdf, queries)

    if call["stop_reason"] == "refusal":
        raise ExtractionError(f"the model declined the request (response {call['response_id']})")
    if call["stop_reason"] == "max_tokens":
        raise ExtractionError(f"output truncated at max_tokens={MAX_TOKENS} (response {call['response_id']})")
    try:
        answers_raw = json.loads(call["text"] or "")["answers"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ExtractionError(f"unparseable model output: {exc}") from exc

    if cache_file is not None and not from_cache:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        record = {"cache_key": key, "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
                  "paper_id": paper_id, "pdf_sha256": pdf.sha256, "queries": [q.to_dict() for q in queries],
                  "prompt_version": PROMPT_VERSION, "call": call}
        cache_file.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    claims: list[ExtractedClaim] = []
    not_found: list[NotFound] = []
    answers: dict[str, dict[str, Any]] = {}
    known = {q.query_id: q for q in queries}
    for item in answers_raw:
        qid = item.get("query_id")
        if qid not in known or qid in answers:
            logger.warning("Ignoring answer for unknown or repeated query_id %r", qid)
            continue
        if item.get("status") == "found" and item.get("claim"):
            try:
                claims.append(ExtractedClaim(**item["claim"]))
                answers[qid] = {"status": "found", "claim_index": len(claims) - 1}
            except ValidationError as exc:
                answers[qid] = {"status": "rejected", "error": str(exc).splitlines()[0], "raw": item["claim"]}
        else:
            reason = item.get("reason") or "no reason given"
            not_found.append(NotFound(query=known[qid].question, reason=reason))
            answers[qid] = {"status": "not_found", "reason": reason}
    for qid in known:
        answers.setdefault(qid, {"status": "missing", "error": "the model gave no answer for this query"})

    claim_set = ClaimSet(paper_id=paper_id, pdf_url=pdf_url, pdf_sha256=pdf.sha256,
                         extractor_version=f"{PROMPT_VERSION}/{MODEL}", claims=claims, not_found=not_found)
    meta = {
        "model_requested": MODEL, "model_served": call["model"], "fallback_used": call["fallback_used"],
        "effort": EFFORT, "prompt_version": PROMPT_VERSION, "response_id": call["response_id"],
        "usage": call["usage"], "estimated_cost_usd": estimate_cost_usd(call["usage"]),
        "cache_key": key, "from_cache": from_cache,
    }
    return ExtractionResult(claim_set=claim_set, answers=answers, meta=meta)
