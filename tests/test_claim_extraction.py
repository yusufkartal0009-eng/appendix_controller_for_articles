"""Query-driven claim extraction (W3, #131). A fake client stands in for the API: no network, no key, no cost."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.claim_extraction as ce
from src.claim_extraction import ExtractionError, Query, extract_claims
from src.pdf_text import PdfText

PDF = PdfText(sha256="a" * 64, pages=["Intro", "Table 2\nCA RMSE\nFT-T 0.459 0 .859\nResNet 0.486"], extractor="pypdf test")
QUERIES = [
    Query("ft_transformer_rmse", "Test RMSE of FT-Transformer on California Housing."),
    Query("xgboost_rmse", "Test RMSE of XGBoost on California Housing."),
]


def _claim(**overrides):
    claim = {"metric_name": "rmse", "value_as_printed": "0.459", "unit": "none", "dataset": "California Housing",
             "model_variant": "FT-T", "split": "test", "higher_is_better": False, "table_or_figure": "Table 2",
             "page": 2, "source_quote": "FT-T 0.459", "confidence": 0.9}
    claim.update(overrides)
    return claim


def _answers(*items):
    return {"answers": list(items)}


FOUND = {"query_id": "ft_transformer_rmse", "status": "found", "reason": "", "claim": _claim()}
NOT_FOUND = {"query_id": "xgboost_rmse", "status": "not_found", "reason": "XGBoost is not in Table 2", "claim": None}


class FakeClient:
    """Mimics client.beta.messages.create and records the request."""

    def __init__(self, payload, stop_reason="end_turn", fallback=False):
        self.payload = payload
        self.stop_reason = stop_reason
        self.fallback = fallback
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        iterations = [SimpleNamespace(type="fallback_message")] if self.fallback else []
        usage = SimpleNamespace(input_tokens=1000, output_tokens=500, cache_creation_input_tokens=20000,
                                cache_read_input_tokens=0, iterations=iterations)
        return SimpleNamespace(id="msg_test", model=ce.MODEL, stop_reason=self.stop_reason, usage=usage,
                               content=[SimpleNamespace(type="text", text=text)])


def _run(client, tmp_path, queries=QUERIES):
    return extract_claims(PDF, "paper_003", "https://arxiv.org/pdf/2106.11959v5", queries, client=client,
                          cache_dir=tmp_path / "cache")


def test_request_uses_the_decided_model_settings(tmp_path):
    client = FakeClient(_answers(FOUND, NOT_FOUND))
    _run(client, tmp_path)
    request = client.requests[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["output_config"]["effort"] == "high"
    assert request["output_config"]["format"]["schema"] == ce.OUTPUT_SCHEMA
    assert "temperature" not in request and "thinking" not in request  # rejected by / always on for Opus 5.5
    assert request["fallbacks"] == "default" and request["betas"] == [ce.FALLBACK_BETA]
    paper_block, query_block = request["messages"][0]["content"]
    assert "=== PAGE 2 ===\nTable 2" in paper_block["text"] and paper_block["cache_control"] == {"type": "ephemeral"}
    assert "xgboost_rmse" in query_block["text"]


def test_answers_become_claims_and_not_found_records(tmp_path):
    result = _run(FakeClient(_answers(FOUND, NOT_FOUND)), tmp_path)
    assert result.answers["ft_transformer_rmse"] == {"status": "found", "claim_index": 0}
    claim = result.claim_set.claims[0]
    assert claim.value_normalized == 0.459  # computed by the schema rule, not by the model
    assert result.answers["xgboost_rmse"] == {"status": "not_found", "reason": "XGBoost is not in Table 2"}
    assert result.claim_set.not_found[0].query == QUERIES[1].question
    assert result.meta["estimated_cost_usd"] == round((1000 * 4 + 500 * 20 + 20000 * 5) / 1e6, 4)


def test_invalid_claims_are_rejected_not_kept(tmp_path):
    bad = dict(FOUND, claim=_claim(source_quote="FT-T 0.46"))  # quote does not contain the printed value
    result = _run(FakeClient(_answers(bad, NOT_FOUND)), tmp_path)
    assert result.answers["ft_transformer_rmse"]["status"] == "rejected"
    assert result.claim_set.claims == []


def test_unknown_repeated_and_missing_answers(tmp_path):
    stray = dict(NOT_FOUND, query_id="not_asked")
    result = _run(FakeClient(_answers(FOUND, FOUND, stray)), tmp_path)
    assert len(result.claim_set.claims) == 1
    assert "not_asked" not in result.answers
    assert result.answers["xgboost_rmse"]["status"] == "missing"


def test_second_run_is_answered_from_the_cache(tmp_path):
    first = _run(FakeClient(_answers(FOUND, NOT_FOUND)), tmp_path)
    assert first.meta["from_cache"] is False
    assert len(list((tmp_path / "cache").glob("*.json"))) == 1

    class NoCalls:
        beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: pytest.fail("the API was called")))

    second = _run(NoCalls(), tmp_path)
    assert second.meta["from_cache"] is True
    assert second.claim_set == first.claim_set
    # different queries -> different cache entry
    assert ce.cache_key(PDF, QUERIES[:1]) != ce.cache_key(PDF, QUERIES)


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_unusable_responses_raise_and_are_not_cached(tmp_path, stop_reason):
    with pytest.raises(ExtractionError):
        _run(FakeClient(_answers(FOUND), stop_reason=stop_reason), tmp_path)
    assert not (tmp_path / "cache").exists()


def test_unparseable_output_raises(tmp_path):
    with pytest.raises(ExtractionError, match="unparseable"):
        _run(FakeClient("not json"), tmp_path)


def test_fallback_is_recorded(tmp_path):
    result = _run(FakeClient(_answers(FOUND, NOT_FOUND), fallback=True), tmp_path)
    assert result.meta["fallback_used"] is True


def test_no_key_or_secret_in_the_source():
    source = Path(ce.__file__).read_text(encoding="utf-8")
    assert "sk-ant" not in source and "api_key=" not in source
