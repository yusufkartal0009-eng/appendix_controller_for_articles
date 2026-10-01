# Repro Radar — Claim Schema

> What one extracted claim looks like (W1, #129; roadmap section 3, #9). Claims are extracted from a paper's PDF text
> (W2, W3), checked against the page text (W4), stored with provenance (W6, #10), and confirmed by a human (W7)
> before they are used in scoring. The schema is implemented in `src/claim_schema.py`; this file and that module
> must agree (`tests/test_claim_schema.py`).

---

## 1. One claim

A claim is one number the paper reports for one metric, one dataset, one model, and one split.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `metric_name` | string | yes | The metric as a short lower-case identifier, e.g. `accuracy`, `rmse`, `auroc`, `f1`, `inference_seconds`. |
| `value_as_printed` | string | yes | The value **exactly as it appears in the PDF text**, including `%`, `±`, and spacing, e.g. `96.99 %`, `0.459`, `.842 ± .003`. W4 requires this string to occur verbatim in the page text. |
| `value_normalized` | number | yes | The value on a canonical scale, computed from `value_as_printed` and `unit` by the rule in section 2 (never typed by hand). |
| `unit` | string | yes | The unit as printed: `percent`, `fraction`, `seconds`, `milliseconds`, `count`, or `none` (unitless, e.g. RMSE or a rank). |
| `dataset` | string | yes | The dataset name as printed in the paper, e.g. `California Housing`. It must be a name that occurs in the paper; a dataset that does not occur is a "not found", not a claim (section 4). |
| `model_variant` | string | yes | The method or row the value belongs to, as printed, e.g. `FT-Transformer`, `XGBoost`. |
| `split` | string | yes | The data split the value is measured on: `test`, `validation`, `train`, `cross_validation`, or `not_stated` when the paper does not say. |
| `higher_is_better` | boolean or null | yes | `true` for metrics where larger is better (accuracy, AUROC), `false` where smaller is better (RMSE, error, time), `null` if the paper does not make it clear. |
| `table_or_figure` | string or null | yes | Where the value is printed, e.g. `Table 2`, `Figure 4`; `null` when it is in running text. |
| `page` | integer ≥ 1 | yes | The **PDF page number** (1 = first page of the PDF file), not the number printed on the page. Together with the PDF hash in the claim set (section 3) it identifies the exact page. |
| `source_quote` | string, 1-500 characters | yes | A verbatim span of the page text that contains `value_as_printed` and, where possible, the row or column label. W4 requires it to occur verbatim in the page text. |
| `confidence` | number in [0, 1] | yes | The extractor's own confidence. It is recorded but never used to accept a claim: acceptance comes only from the quote check (W4) and the human (W7). |

## 2. Normalization rule

`value_normalized` is computed from `value_as_printed` and `unit`, in this order:

1. Use the part before a `±` or `+/-` (the spread is not part of the value; it stays visible in `value_as_printed`).
2. Remove spaces (including thin and non-breaking spaces) and a trailing `%`; replace the Unicode minus `−` with `-`.
3. Remove thousands separators only in the form `1,234,567`; any other comma makes the value invalid.
4. Read the remaining text as a decimal number (`.842` is allowed). Anything else is invalid, and the claim is rejected.
5. Scale to the canonical unit:
   - `percent` → fraction: divide by 100 (`96.99 %` → `0.9699`);
   - `milliseconds` → seconds: divide by 1000;
   - `fraction`, `seconds`, `count`, `none`: unchanged.

The arithmetic is done in decimal, so `96.99 %` gives exactly `0.9699`, not `0.9698999…`. If a claim carries a
`value_normalized` that differs from the rule's result, it is rejected.

| `value_as_printed` | `unit` | `value_normalized` |
|---|---|---|
| `96.99 %` | `percent` | `0.9699` |
| `96.99` | `percent` | `0.9699` |
| `0.459` | `none` | `0.459` |
| `.842 ± .003` | `fraction` | `0.842` |
| `1,250` | `milliseconds` | `1.25` |
| `−0.12` | `none` | `-0.12` |

## 3. Claim set (one extraction of one paper)

Claims are grouped per paper and per PDF, so that page numbers and quotes always refer to one exact file:

| Field | Type | Meaning |
|---|---|---|
| `paper_id` | string | The entry in `data/seed_papers.json`, e.g. `paper_003`. |
| `pdf_url` | string | Where the PDF was downloaded from (with the version, e.g. arXiv `v5`). |
| `pdf_sha256` | string (64 hex characters) | Hash of the exact PDF file; W2 caches page text by this hash. |
| `extractor_version` | string | Version of the extractor (prompt and code) that produced the claims. |
| `claims` | list of claims | Section 1. |
| `not_found` | list of queries | Section 4. |

## 4. "Not found" is an answer

When the extractor is asked for a value that the paper does not report, it must answer "not found" instead of
guessing. A not-found answer is a query record, not a claim:

| Field | Type | Meaning |
|---|---|---|
| `query` | string | What was asked for, e.g. `auroc on EP3602`. |
| `reason` | string | Short reason, e.g. `dataset "EP3602" does not occur in the paper`. |

Required regression cases (W5, #133): `paper_005` asked for "EP3602" must give "not found" (and must not match
`EP300`), and `paper_008` asked for "HIGGS" must give "not found".

## 5. Added later, not part of the extraction output

These are attached after extraction and are not produced by the extractor itself:

- `verification_status`: `UNVERIFIED` until the verbatim quote guard (W4, `src/quote_guard.py`) passes, then
  `AUTO_QUOTE_MATCH`. A claim that fails the guard is never scored; scoring takes its claims from
  `scorable_claims()`. The guard requires:
  1. the claim set's `pdf_sha256` to equal the hash of the text's PDF, and the cited page to exist;
  2. `source_quote` and `value_as_printed` to occur on the cited page with identical characters. The only
     tolerance is that a run of whitespace counts as one space, and which mode matched (`exact` or
     `whitespace_normalized`) is recorded. A value retyped without the space the extraction put inside it
     (`0.859` for `0 .859`) does not match;
  3. `dataset` and `model_variant` to occur somewhere in the paper as whole words (ignoring case), so a claim
     about a dataset the paper never mentions (`EP3602`) cannot pass.
- `verified_by`: `auto-quote-match` or `human` (W6, #10, and W7, #134).
