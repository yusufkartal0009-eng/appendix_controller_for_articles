# Gold set expansion (18 to 36 questions, #315)

The gold set of the first round has 18 questions (6 papers, 3 each). Precision and recall of 1.0 on 18 questions is weak
evidence, so 18 more are added. This document is written **before** the new answers are looked at, and it is the rule
by which the questions were chosen.

## 1. Selection rule

For each of the 6 papers, 3 new questions:

1. **A model-by-dataset value from the paper's main results table** that is not one of the first round's questions:
   a different row (model) or a different column (dataset) of the same table, chosen by position, not by whether an
   extraction found it.
2. **A second value of a different kind** from the same table or its neighbor: a rank, a mean, or a maximum.
3. **One negative control**: a model, dataset, or metric that sounds plausible and is **not reported** in the paper
   (checked by a text search of the paper before the question was kept). The right answer is "not in the paper".

A question names a table, a row, and a column; it never contains a value. The wording is taken from the table's own
headers and captions. Questions that two readers could reasonably answer differently are avoided by naming the table.

## 2. What is compared

- **Pass A:** the main session answers with the same rules as the first round (`docs/AGENT_EXTRACTION.md` section 2).
  It is not blind: the same agent that wrote the questions knows where the answers are.
- **Pass B:** a **fresh process** (`claude -p`, no history, only Read/Write/Edit/Glob/Grep) in a blind packet
  (`scripts/gold_expansion.py packet`); it sees the page text, the questions, and the rules, and nothing else.
- **Gold:** the **owner** chooses the correct answers in a form (`scripts/gold_expansion.py form`), from candidate values
  listed by the agent (`data/gold_expansion/candidates.json`); the form does not show which candidate the passes
  chose. The owner can also choose "not in the paper" or write another value. Nothing is scored against an agent's
  answer.
- Precision and recall are computed with `scripts/evaluate_gold.py score --gold data/gold_expansion/gold --claims-dir
  data/gold_expansion/claims --pass A|B`, as in the first round.

## 3. Limits (stated before the result)

- The candidates are listed by an agent, so a correct value that the agent did not list can enter the gold set only
  through the owner's "other" answer.
- The negative controls test whether a pass invents a value; a pass that answers them correctly is not shown to be
  correct on all papers.
- Both passes are the same model; the blind pass removes the shared conversation, not the shared model.
- 36 questions over 6 papers is still small.

## 4. Status (2026-10-15)

- **Questions, candidates, pass A, and pass B are in `data/gold_expansion/`.** Pass B was made in a fresh process
  (`claude -p`, no history, Read/Write/Edit/Glob/Grep only) on a blind packet; the packet was started by the main
  session, which knew pass A (not by the owner in a separate terminal).
- **A and B agree on all 18 questions** by normalized value (12 values, 6 "not found", including all 6 negative
  controls); every quote of both passes occurs on the page it cites (`scripts/gold_expansion.py import-pass` refuses
  an answer whose quote is not on the page). Agreement of two passes of the same model is not correctness.
- **The owner's gold set for these 18 questions does not exist yet.** The form is
  `scripts/gold_expansion.py form <path>`; when the owner has filled it, run
  `scripts/evaluate_gold.py from-form <form> --out data/gold_expansion/gold`, then `evaluate_gold.py score --gold
  data/gold_expansion/gold --claims-dir data/gold_expansion/claims --pass A` (and `--pass B`) and record the result
  here. Until then **no precision or recall is claimed for these 18 questions.**
