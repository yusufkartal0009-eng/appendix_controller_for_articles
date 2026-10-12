# Repro Radar — Agent-Assisted Claim Extraction Protocol

> How claims are extracted without an API key (D-004) for plan step 1.1 (#131), in two passes compared by step
> 1.2 (D-005). Both extractions follow exactly these rules. Written before either extraction was made; section 3
> was corrected on 2026-10-04 to say that the two passes are made by the same agent.

## 1. Inputs

- **Questions:** `data/claim_queries/<paper_id>.json`, one question per claim in `data/seed_papers.json`, written from
  the claim's name and cited source **without the seed value**, so the expected answer cannot leak into the question.
  6 papers, 16 seed claims; 18 questions after the owner's splits of 2026-10-04 (#184).
- **Paper text:** the pypdf page text of the exact PDF named in the question file (`src/pdf_text.py`, W2), page by
  page. The PDF's SHA-256 is recorded with every extraction.
- Nothing else: not `data/seed_papers.json`'s values, not `docs/CORPUS_VERIFICATION.md`, not the other extraction,
  not the gold set.

## 2. Answer rules (the same rules as the API prompt in `src/claim_extraction.py`)

1. Answer every question exactly once.
2. Use only the given text. If the paper does not report the requested value, answer `not_found` with a short reason
   (for example: the dataset, model, or metric does not occur in the paper, or occurs only under another name). Never
   guess, never compute a value, never take a value from a similar dataset, model, or metric.
3. `value_as_printed` is copied character for character from the extracted text, including spaces the extraction put
   inside numbers (`0 .859`), percent signs, and any `±` part.
4. `source_quote` is one contiguous span copied exactly from that page's text (at most 300 characters) that contains
   `value_as_printed` and, where possible, the row or column label.
5. `page` is the PDF page number of the quote.
6. Tables are flattened (a header line, then one line per row). Find a value's column by counting cells. If the
   column or row cannot be determined with certainty, answer `not_found` with the reason "column or row ambiguous".
7. **Several matching values:** if the paper prints the requested value in more than one place (for example single
   model and ensemble, or default and tuned hyperparameters), report the one from the paper's main results table for
   a single model with the paper's own recommended setting, and say in `reason` which other values exist.
8. Fields follow `docs/CLAIM_SCHEMA.md`; `value_normalized` is never written by hand, it is computed by
   `src/claim_schema.py`.
9. **Owner decisions of 2026-10-04 (#184, `data/claims/owner_decisions.json`):**
   - values measured on different hardware are separate claims (one question each, e.g. GPU and CPU time);
   - model variants with different results are separate claims, distinguished by `model_variant` (e.g. DANet-20
     and DANet-32);
   - ranks that are compared must come from the same table; if no table holds both, the answer says they are not
     comparable.
   A question split by these rules keeps the seed claim it comes from in `seed_claim` (`<seed claim>__<variant>`).

## 3. Two extractions (A and B), and how independent they are

- **Extraction A** and **extraction B** each answer all 16 questions from the inputs above. They are stored side by
  side in `data/claims/<paper_id>.json`, each with its method, date, and the PDF hash.
- **They are not fully independent.** On the owner's instruction (2026-10-04), no separate agent was used: both
  extractions are made by the same agent (Claude Code) in one session. Extraction B is a second pass made after A was
  written down: B searches each paper again from the start by a different route (first the row or sentence that names
  the model, then the column or value), but its author has seen A. In the 2026-10-04 extraction every re-search
  confirmed A's answer, so B's values, units, and pages were taken over from A, and only B's quotes and reasons
  were copied again from the page text.
  So the A/B comparison (step 1.2) catches copying, transcription, and normalization errors, but **not** a
  misunderstanding that both passes share. Shared misunderstandings are caught only by the quote guard (W4), the
  owner's gold set (W5, Y3), and the owner's approval (W7).
- **Follow-up questions (#258):** a question added after the 18 gold-set questions is listed under
  `followup_queries` in its question file and answered in pass A only, in `data/claims/followup/<paper_id>.json`
  (with the quote guard's result). It is not part of the passes A and B comparison, the gold set, the database import,
  or `data/seed_papers.json`. It becomes a claim only after a blind pass B (#186) and the owner's review (W7).
  Today there is one: `paper_005`, the average kernel speedup on EP300 (Table 1).
- Step 1.2 compares them by normalized value (D-005). Every disagreement goes to the owner in W7 (#134); neither
  extraction is "right" by default.
- Neither extraction is approved by being extracted. Approval comes only from the quote guard (W4) and the owner (W7).
- **Making pass B independent (#186):** `python scripts/make_blind_packet.py <folder outside the repository>` writes a
  blind packet; the owner runs a new Claude Code session in that folder with the prompt in its README; then
  `python scripts/import_pass.py <folder>` checks the answers and replaces pass B. After that, step 1.2's comparison
  is meaningful.
