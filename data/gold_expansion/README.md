# Gold set expansion: questions, candidates, and passes

See `docs/GOLD_SET_EXPANSION.md` (selection rule, written before the answers were looked at, and the status).

- `questions.json`: 18 new questions (3 per paper: two values from the main tables, one negative control).
- `candidates.json`: candidate values for the owner's form, listed by an agent; they are not the passes' answers.
- `claims/<paper_id>.json`: pass A (main session) and pass B (blind, fresh process); `claims/consistency.*`: the A/B comparison.
- No `gold/` folder yet: it is written from the owner's filled form (`scripts/evaluate_gold.py from-form`).
