# Repro Radar — PDF Text Extraction

> How paper text is read for claim extraction (W2, #130; roadmap section 3, #9), and what that text can and cannot
> be trusted for. Implemented in `src/pdf_text.py`.

## What it does

- `extract_pdf_text(pdf_path)` returns the text of every page with `pypdf`. Pages are numbered as PDF pages
  (1 = first page of the file), the numbering used by `docs/CLAIM_SCHEMA.md`.
- `PdfText.find(text)` lists the pages that contain a string verbatim; this is the primitive for the quote check (W4).
- The text is cached as `data/pdf_text_cache/<sha256>.json`, keyed by the SHA-256 of the PDF bytes. The same file is
  extracted once; a different version of the paper (another arXiv `vN`) is another file and gets its own entry. A
  cache entry written by a different `pypdf` version, or one that cannot be read, is replaced by a fresh extraction.
- The cache holds full paper text, so it is **not committed** (`.gitignore`).

## Known limitations (seen on a real paper)

Example: `paper_003` (arXiv 2106.11959v5, SHA-256 `f2faa32f…478d`, 25 pages), PDF page 7, Table 2, as extracted
by `pypdf 6.19.0`:

```
CA ↓ AD ↑ HE ↑ JA ↑ HI ↑ AL ↑ EP ↑ YE ↓ CO ↑ Y A↓ MI ↓ rank (std)
TabNet 0.510 0 .850 0 .378 0 .723 0 .719 0 .954 0 .8896 8 .909 0 .957 0 .823 0 .751 7.5 (2.0)
GrowNet 0.487 0.857 – – 0.722 – 0.8970 8 .827 – 0.765 0 .751 5.7 (2.2)
FT-T 0.459 0 .859 0.391 0.732 0 .729 0.960 0.8982 8.855 0.970 0.756 0 .746 1.8 (1.2)
```

1. **A table row becomes one line, and the column structure is lost.** The header (`CA ↓ AD ↑ …`) is a separate
   line, so a value's column can only be found by counting positions. Empty cells (`–`) shift those positions,
   and labels can be split (`Y A↓` for `YA ↓`). The text alone does not reliably say which column a number belongs to.
2. **Spaces can appear inside numbers.** `0 .850` and `8 .909` above are `0.850` and `8.909` in the PDF. The same value
   can be extracted with or without the space in one table (`0.859` and `0 .859` both occur on this page).
   **Repaired (#162):** `repair_split_numbers()` in `src/pdf_text.py` removes a single space between a digit and a
   following decimal point (`0 .850` → `0.850`), and the quote guard compares quotes and values after this repair
   on both sides (match mode `split_numbers_repaired`). In the six seed PDFs the pattern occurs 1,213 times
   (`paper_003`: 226, `paper_004`: 986, `paper_006`: 1, the others: 0); every match that was checked is a split
   number, including the one in running text (`β1 = 0 .9`). A space after a period (`2019. 22`, reference lists)
   is not changed. The stored page text is not modified; the repair is applied only when comparing.
3. **Formatting is gone.** Bold or underlined "best" results, colors, and footnote markers are not in the text.
4. **Scanned PDFs have no text.** A page that is an image gives an empty string; there is no OCR.
5. Figures are not read: values that appear only in a plot are not in the text.

Because of 1, the column of a value (and so its `dataset` and `metric_name`) cannot be decided from the extracted
text alone. **Approach for table claims (#162):** table structure is not reconstructed. Instead, the quote guard
flags every claim whose `table_or_figure` names a table (`from_table` in its checks), and flagged claims always go
to the owner in the human confirmation step (W7, #134), even when their quote matches. The extraction rules
(`docs/AGENT_EXTRACTION.md`) also require "not found" when a value's column cannot be determined with certainty.
