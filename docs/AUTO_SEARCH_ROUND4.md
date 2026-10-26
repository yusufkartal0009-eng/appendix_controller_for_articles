# Automatic search, round 4: the improved match test K2 v2

Date written: 2026-10-27. Issue #515. **This addendum was written after the result of the first round was seen** (round 3,
`docs/AUTO_SEARCH_ROUND3.md`: 135 candidates run, 2 passed K1, none passed K2). It is written and merged **before any candidate of
round 4 has been searched or run**. K2 v1 is not changed and is not replaced: K2 v2 is new and additional, and both results are
stored for every run.

## 1. Why this round exists

In `docs/REAL_VERDICTS.md` section 4, K2 (v1) was tried on three papers where a match was expected (`paper_003`, `paper_006`,
`paper_102`). `paper_006` failed K2 although its run prints a number that the paper prints too: the run writes the AUROC as a
fraction (`0.933`) and the paper writes it as a percent (`93.3`). A string match in the same spelling cannot see this. So v1 may
have missed real matches in round 3. K2 v2 corrects that **known defect**, as a rule written here, and not by looking at the result
of a new search. It is applied together with v1 and the result of v1 stays on record.

This round is **not** a sample of papers and **not** a success rate (section 9). It accepts no claim: accepting a claim is the
owner's decision alone. A candidate that passes K2 v2 is a **match candidate**; it is never called verified.

## 2. What stays the same as round 3

Unchanged, exactly as in `docs/AUTO_SEARCH_ROUND3.md`:

- the static rules S1 to S6 (section 3 there), applied in the hash order, the first failed rule recorded;
- the run test K1 (section 4 there): one run per candidate, exactly as the README says, in the Docker sandbox with `--network none`
  in both phases, `--memory 50%`, `--cpus 4`, install limit 1200 s, run limit 600 s, one sandbox run at a time, no repair and no
  second run;
- K2 v1 (section 5 there): at least 2 different meaningful numbers of `stdout.log` occur in the paper's text in the same spelling and
  at least one of them on a page with a `Table <n>` line;
- the definition of a **meaningful number** (section 5 there): at least 3 significant digits; not a year, a version, a date or a
  time, an index or a line number; numbers are taken from `stdout.log` only.

## 3. K2 v2

For each meaningful number `n` of the run's `stdout.log` (canonical string `s`, as printed, without sign variants, thousands
separators and percent sign), the text of the paper is searched, page by page, for **one of these spellings**, in this order. The
first spelling that is found is stored with the match.

| Variant | Spelling searched | Applies when |
|---|---|---|
| `same` | `s` itself (this is the v1 match) | always |
| `x100` | `s` times 100 as an exact decimal shift (`0.8886` becomes `88.86`; a fraction becomes a percent) | `0 < abs(n) <= 1` |
| `div100` | `s` divided by 100 as an exact decimal shift (`88.86` becomes `0.8886`; a percent becomes a fraction) | `1 < abs(n) <= 100` |
| `<variant>+round3` | the spelling of `same`, `x100` or `div100`, rounded half up to its first 3 significant digits and searched at the same scale (`0.8886` becomes `0.889`, `88.86` becomes `88.9`) | only when the spelling has more than 3 significant digits (otherwise the rounding is the spelling itself) |

Normalisation, in both texts: the minus variants (`-`, the Unicode minus, en dash, non-breaking hyphen) are one minus sign; a
decimal comma is read as a decimal point; a thousands separator (`,`, `'`, a thin or non-breaking space) between digit groups of
three is removed; a leading zero may be dropped (`.5`). A number printed in the output with a decimal comma (`0,8886`) is read as
`0.8886`. A found spelling must not be part of a longer number (`1.5` does not match inside `21.55`, `1.52` or `1.5.2`).

**Excluded** as in v1: a number that is a year, part of a version, a date or a time, an index or a line number is not looked up,
in any variant. Percent signs and sign are removed before the comparison. The number of decimals counts: `0.50` does not match
`0.5`, and a rounded spelling is only the one defined above (no other rounding is tried).

**Guard against a chance match.** A scale conversion or a rounding makes a chance match more likely. So:

1. a match by any variant other than `same` counts only when it is on a page that has a `Table <n>` line (a `same` match counts on
   any page, as in v1);
2. `x100` and `div100` apply only in the ranges of the table (a fraction becomes a percent, a percent becomes a fraction);
3. for every number found, the variant, the page (1-based), the line of the paper and the line of the run output are stored.

**K2 v2 passes** when at least **2 different** meaningful numbers of the run are found by this procedure **and** at least one of
them is found on a page that has a `Table <n>` line. A candidate that passes K2 v2 is called a **match candidate**; it is not
called verified. The warning of section 9 applies: a scale conversion raises the chance of a coincidental match, so a person decides
from the stored page and line whether a number of the output is the number of the paper's table.

A candidate has three K2 results, all stored: `k2` (v1, as in round 3), `k2v2` and the K1 result. A candidate **passes both** K1
and K2 v2 only when it passes K1 and K2 v2; the stop condition (c) of section 6 counts a candidate once when it passed K1 and
passed K2 v1 or K2 v2.

## 4. Controls

The controls run on the stored runs of earlier work (`data/cpu_runs`, `data/pilot3_runs`, `data/memory_runs`,
`data/pilot4_runs`, the PDFs in `data/pdfs/`, not tracked by git), with the rules of section 3 and no change of them between the
runs. The rules were **not** bent until the control passed: they were written first, then run.

- **Positive control: `paper_006` must pass K2 v2.** Result of the three stored runs (Pilot 3, memory run 2, CPU run): **K2 v2
  passes in all three**, with the same two numbers: `256` (variant `same`, page 7, the batch size in the text of the training
  setup: `...a learning rate of 0.0001 with batches of size 256...`) and `0.933` (variant `x100`, spelled `93.3`, page 7, the
  `SAINT` row of the table with the AUROC of the Bank dataset; output line `[EPOCH 21] VALID ACCURACY: 90.784, VALID AUROC: 0.933`).
  K2 v1 found only `256` in these runs. So v2 sees the scale-converted match that v1 missed. **A limit of this result:** the first
  of the two numbers is a hyperparameter that occurs in the paper by coincidence, and the second is the validation AUROC of an
  epoch of the run (the test AUROC printed in the same run is `0.929`, which is not the printed `93.3`). K2 v2 therefore passes
  `paper_006` on one scale-converted match and one coincidence, and the result is recorded as it is.
- **Negative control: `paper_102` must NOT pass K2 v2** (its output is a toy example on random data from
  `sklearn.datasets.make_classification`, `docs/REAL_VERDICTS.md` section 4). Result: **K2 v2 does not pass** (10 meaningful
  numbers in the output, none found in the paper under any variant). If it had passed, the rule would be too loose and this
  document would say so and K2 v2 would not be used.
- Also run (not a control): `paper_003` passes K2 v2 as it passes v1, with the same 17 numbers; they are values the training log
  prints for other models and match the paper's tables by coincidence of dense numbers (`docs/REAL_VERDICTS.md` section 4).

The code of K2 v2 is added to `scripts/auto_search4.py` by a separate change with unit tests of these controls, and the result of
that code on the controls must equal the result written here.

## 5. The pool and its order

The pool is made as in round 3 (`docs/AUTO_SEARCH_ROUND3.md` section 2): the union of the first 100 results (default order, "best
match") of GitHub repository searches, run once per query on the day of selection and stored unchanged with the date and the exact
query strings in `data/auto_search4/pool.json`. Each query is

    arxiv.org in:readme language:Python archived:false fork:false size:<30000 topic:<topic>

The new stage topics, in this order:

- **Stage 8:** `optimal-control`, `robotics`, `computer-vision`, `remote-sensing`, `geoscience`, `climate`, `finance`,
  `healthcare`, `materials-science`, `astronomy`, `speech`, `audio`, `tabular-deep-learning`, `automl`, `interpretability`,
  `uncertainty-estimation`.
- **Stage 9** (used only when the candidates of stage 8 are used up before a stop condition of section 6 holds):
  `federated-learning`, `active-learning`, `transfer-learning`, `domain-adaptation`, `anomaly-detection`, `clustering`,
  `graph-neural-networks`, `reinforcement-learning`, `knowledge-graph`, `text-classification`, `sentiment-analysis`,
  `machine-translation`, `image-classification`, `object-detection`, `segmentation`, `forecasting`.

Duplicates are removed (case-insensitive). The repositories of **all earlier rounds are removed from the pool before ordering**:
every repository in `data/auto_search3/pool*.json` (the whole pool of round 3, checked or not), `data/demo_set/pool.json`,
`data/candidates/` (all files), `data/seed_papers.json` and `data/corpus_expansion/papers.json`. The remaining candidates are
ordered by the **SHA-256 hash of the lower-case `owner/name`**, ascending; the candidates of stage 9 come after those of stage 8. No
other ordering is used: not stars, not date, not content. Many topics of stage 8 and 9 overlap with topics searched in round 3
(for example `computer-vision`, `robotics`, `interpretability`); those repositories are in the removed set, so the topics return
only repositories that no earlier round has seen.

## 6. When the search stops

The first of these:

- **(a)** 9 hours have passed since the start of the night's work (the start, 2026-10-27 01:44 +03:00, is written to
  `sabah_bekleyenler.md`, a file outside the repository);
- **(b)** 150 new candidates have been run in the sandbox in this round;
- **(c)** 5 candidates have passed K1 and K2 (v1 or v2);
- **(d)** the free disk space is under 30 GB.

A pool that is used up is not a stop condition: the queries of the next stage are added and the search goes on. The search is
resumable: candidates with a stored result are skipped.

## 7. Records

For each run candidate, `data/auto_search4/runs/<id>/` keeps `run_report.json`, the K1, K2 v1 and K2 v2 result file, and short
logs (long outputs are truncated; local paths are replaced by `<REPO>` and `<HOME>`). `data/auto_search4/evaluation.json` holds
every checked candidate with its first failed rule or its run result. Records of earlier rounds are not touched.

## 8. Reporting

From a script and the stored files only: the number of candidates tried, the numbers that passed K1, K2 v1, K2 v2 and both, the
Wilson 95% interval for each, a table of the failure categories, and for every K2 v2 pass the command, the duration and each
matching number with its variant, page and line. No number is typed by hand.

## 9. Limits that are known before the first search

- **This is a selected and non-representative list, not a success rate.** The pool is what GitHub's search returns for these topics
  with `arxiv.org` in the README, small, and without a GPU mention; the order is a hash; the rules reject most repositories. The
  Wilson intervals describe only the candidates that were run.
- **K2 v2 can match by chance, and its scale conversion and rounding make this more likely than v1.** Hyperparameters and other
  numbers with three digits (`256`) occur in papers without being results. The result is a reason for a person to look at the stored
  page and line, not evidence. The guard of section 3 limits the chance, it does not remove it.
- K1 selects for code that runs in 10 minutes as written. A paper that fails may be reproducible with a correction; this round says
  nothing about that.
- The first `python` line of a README may be a data preparation step, a demo or a help text. A pass shows that the command ran and
  printed numbers, not that the paper's main result is reproduced.
- Simulated or synthetic data in a run's output is labelled as simulation wherever it is reported.
- No claim is accepted by this round.

## 10. Re-evaluation of the round 3 runs

K2 v2 applied to the stored `stdout.log` of the two candidates of round 3 that passed K1 (`wanyichen06/HSPR`, `fless-lab/rsi-framework`),
with the rules of section 3 and no new run. Only the K1 passers are re-evaluated: the other 133 runs of round 3 failed K1, and their
outputs (mostly install failures) are not part of this re-evaluation. The PDFs are those kept in round 3 (`data/pdfs/`, not
tracked by git).

Generated by `scripts/auto_search4.py reeval` from data/auto_search3/evaluation.json and data/auto_search3/runs/<id>/stdout.log; nothing was run again.

| Id | Repository | arXiv | Output truncated | K2 v1 | K2 v2 | Output numbers | Found (v1) | Found (v2) |
|---|---|---|---|---|---|---|---|---|
| a3_095 | `wanyichen06/HSPR` | 2610.24611 | no | no | no | 1 | 0 | 0 |
| a3_096 | `fless-lab/rsi-framework` | 2603.21610 | no | no | no | 207 | 0 | 0 |


**Result:** neither candidate passes K2 v2 (and neither passed v1): no number of the output was found in the paper under any
variant. The round 3 outcome for these two candidates does not change: K1 passed, K2 not passed, with the scale and rounding
variants as well. (The output of `a3_096` has one more meaningful number under v2 than under v1 only because v2 reads a decimal
comma as a decimal point first.) This says nothing about whether the output is related to the paper; it says only that no printed
number is also printed in the paper in a spelling that v2 can reach.

## 11. Results

Filled from the script output after the runs.
