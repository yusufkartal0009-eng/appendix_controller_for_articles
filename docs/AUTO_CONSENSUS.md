# Automatic consensus candidates (#381)

`scripts/auto_extract.py` starts three independent extraction passes per paper and reports the claims they agree on. It
**does not accept anything**: a claim that at least two passes agree on becomes a *candidate*
(`verified_by = auto-consensus`, `review_status = pending`). The database refuses to mark a claim `accepted` unless
`verified_by = human` (a CHECK constraint, kept in migration 7), `cli.py score` ignores candidates unless it is asked
`--claims auto-consensus` (and then labels the score "claims: auto-consensus candidates, not accepted by a person"), and
`import` never touches a claim a person has reviewed.

## 1. How a pass runs

For every paper and pass a packet is written outside the repository (questions, the rules and schema of
`scripts/make_blind_packet.py`, the page text of the pinned PDF, an answer template; nothing from earlier extractions).
A fresh `claude -p` process starts in that folder with `--tools Read,Write,Edit,Glob,Grep`, `--permission-mode dontAsk`
(everything not allowed is refused), no session persistence, no slash commands and no MCP servers. The processes share
nothing. Each answer is then checked as `scripts/import_pass.py` checks one: claim schema, existing page, and a quote that is
found on that page and contains the printed value. An answer that fails is not a vote. A pass whose process fails or writes
nothing is started once more in a new process.

Consensus per question: **candidate** if at least two passes gave the same normalized value, each with a valid quote;
**consensus_not_found** if at least two passes say "not found" and none found a valid claim; otherwise **no_consensus**,
which is left to a person. No threshold is set; the numbers below are only reported.

## 2. Accuracy against the first 18 gold questions

Command: `python scripts/auto_extract.py run --name gold18 --papers paper_002,paper_003,paper_004,paper_005,paper_006,paper_008`
then `... evaluate --name gold18`. The gold set is `tests/data/gold_claims/` (6 papers, 3 questions each: 12 with a value, 6
that the paper does not report). Values are compared as printed with spaces ignored, like `scripts/evaluate_gold.py`.
Files: `data/auto_extract/gold18/` (`raw/pass_<k>/`, `meta.json`, `consensus.json`, `evaluation.json`).

| Source | TP | FP | FN | TN | Precision | Recall |
|---|---|---|---|---|---|---|
| Consensus (as printed, spaces ignored) | 10 | 2 | 2 | 6 | 0.833 | 0.833 |
| Consensus (spread after ± ignored) | 12 | 0 | 0 | 6 | 1.0 | 1.0 |
| Single pass 1 (as printed) | 10 | 2 | 2 | 6 | 0.833 | 0.833 |
| Single pass 2 (as printed) | 11 | 1 | 1 | 6 | 0.917 | 0.917 |
| Single pass 3 (as printed) | 10 | 2 | 2 | 6 | 0.833 | 0.833 |

Decided by consensus: 18 of 18; left to a person: 0.
The three single passes are also scored so the consensus can be compared with one pass alone.

The consensus differs from the gold set in two questions:

| Question | Gold | Consensus candidate | Passes (1, 2, 3) |
|---|---|---|---|
| `paper_003:xgboost_rmse` | `0.433±1.6e-3` | `0.433` | `0.433`, `0.433±1.6e-3`, `0.433` |
| `paper_004:tabr_average_rank` | `1.3± 0.9` | `1.3± 0.6` | `1.3± 0.6`, `1.3± 0.6`, `1.3± 0.6` |

- `paper_003:xgboost_rmse`: the value is the same number; two passes left out the spread (`±1.6e-3`) that the gold value has.
  Under "as printed" this counts as a false positive and a false negative; ignoring the spread it is correct.
- `paper_004:tabr_average_rank`: **all three passes agree and are wrong** against the gold set. The page holds two TabR rows
  (`1.3± 0.9` and, under the default-hyperparameters block, `1.3± 0.6`); the gold set and the earlier passes A and B took the
  first, the three new passes took the second. Ignoring the spread would call this correct, which hides a real choice of
  the wrong row, so the "spread ignored" line above is not the headline. Agreement of independent passes does not protect
  against a systematic misreading of an ambiguous table; a person has to look at such claims.

## 3. What this does not show

- Eighteen questions on six papers, one run of the three passes; no repeat of the whole experiment, so the variation between
  runs is not measured. A single question moves precision and recall by several points.
- The three passes use the same model; their errors are not independent in the statistical sense (the `paper_004` case).
- The questions are fixed and were written with the gold set; open-ended extraction (any number in a results table) is not
  covered here.
- The 18 passes took 28 s each on average; the CLI reported a list-price cost of about USD 2.5 in total (`meta.json`).
- Nothing was imported into the project database; no claim was accepted.
