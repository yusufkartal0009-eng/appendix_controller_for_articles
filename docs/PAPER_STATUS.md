# Paper status (2026-10-25, issue #503)

Which parts of `docs/report/REPORT.md` are in their final form, and which wait for the owner's decision or input. One line per
item. The owner's open decisions are listed with their long form in `docs/PENDING.md`; this page only says what the report needs.

## 1. Sections of the report

| Section | State | Waits for |
|---|---|---|
| 1 Abstract | Final in content; updated on 2026-10-25 with the two claims and the new results | nothing |
| 2 Introduction | Final (sourced in `docs/INTRODUCTION_SOURCES.md`) | nothing |
| 3 Related work | Final (nine sources verified by `scripts/verify_sources.py`; abstracts and bibliographic data only, no full texts) | nothing |
| 4 Method | Final | nothing |
| 5 Experimental setup | Final | nothing |
| 6.1, 6.1a Pilots 1 to 3 | Final | nothing |
| 6.2 Claim extraction | Final | nothing |
| 6.3 What the pilots do not show | Final; rewritten on 2026-10-25 (it had stopped at Pilot 2) | nothing |
| 6.4 Checks after the pilots | Final, except the extended gold set | **Gold set 2:** the owner's own answers to the 18 added questions (D2; form kept outside the repository); until then no precision or recall is claimed for them |
| 6.4a Seed runs, GPU check | Final | **Tier 3 rule (D7):** whether the metric with the largest CV should decide |
| 6.5 Pilot 4 | Final | nothing |
| 6.5a External reference (ReScience C) | Final as a negative result | **Reference (D5):** what outside reference to use now that none was selected; a question for the owner and the mentor |
| 6.6 Field analysis | Final (exploratory) | nothing |
| 6.7 Diagnosis layer | Final; no real language model was used | nothing |
| 6.8 Candidate papers | Final | **Candidates (D9):** whether to repair further or stop adding papers |
| 6.9 Tolerance probe | Final | **Scorer rules (D10):** the 0.05 absolute allowance for small values; whether a label may be given to a paper without an accepted claim |
| 6.10 Automatic search | Final | **Round 3 (D11):** whether to run a stage 8 or to stop |
| 6.11 Real verdicts and the pilot as an estimate | New, written from the stored files on 2026-10-25 | **Claim matching:** how the question IDs of the claims and the extracted metric names should meet (the command-line path never compares a real claim); the owner should read the section once, because it states that the expected K2 positive control was not obtained |
| 7 Limitations | Final; three bullets added on 2026-10-25 | nothing |
| 8 Lessons learned | Final; one lesson added and the "what we would change next" list replaced | nothing |
| 9 Conclusion and future work | Final; the dashboard sentence and the claims were updated | nothing |
| 10 References and reproducibility statement | Final | **Release:** no version is tagged (#45), so the version of the report is a commit |
| 10 AI assistance statement | Written; the wording is a draft of the project | **AI use note (#492, D8):** the owner confirms the wording and where the statement goes, and the mentor's answer on the attribution rule of `AGENTS.md` (D8: plan question Y2; issue #165 does not exist in this repository) |

## 2. Inputs the paper still needs from the owner

| Item | What is needed | Where |
|---|---|---|
| Gold set 2 numbers | The owner's answers to the 18 added questions | D2 in `docs/PENDING.md`; `docs/GOLD_SET_EXPANSION.md` |
| Mentor format | The format the mentor wants (length, template, venue) and which of the two claims the report should defend first (the rate of papers that run, or the correctness of the verdict on a known example); the report is a Markdown file and is not in any template | D8 in `docs/PENDING.md` |
| Video | A demo of two to three minutes; the script is `docs/DEMO_SCRIPT.md`; the owner records it | section 4 of `docs/PENDING.md` |
| AI assistance note | Wording and placement (see above) | #492, #165 |
| Decisions on the scorer | Claim matching, the small-value allowance, a label without a claim, the multi-seed link, the K1 pattern, and what the dashboard shows beside a score | `docs/BUG_HUNT.md` section 3, D10 |

## 3. Consistency scan of 2026-10-25

The whole report was read once, and then searched for the phrases that carry a claim about the state of the work ("no run", "not yet",
"reproduced", "no score", "never", "first time", the names of the four pilot papers) and for numbers that a later result changes.
Every number block was regenerated and checked (`python scripts/report_numbers.py --check`), the sources were checked
(`python scripts/verify_sources.py --check`), and the tests were run.

Found and fixed:

1. Section 6.3 was titled "What Pilot 2 does not show" and said that no run produced a metric an accepted claim names; `paper_003` prints
   `rmse` since Pilot 3. Rewritten and retitled.
2. The abstract, the introduction and sections 4.3 and 7 said "no run reproduced an accepted claim"; the new comparison (section 6.11) makes
   that precise: no run matched through the command line, and one run is close to one claim when aligned by hand. The statements now say
   "no run was shown to" and point to section 6.11.
3. The conclusion said that the database holds no score "because no run produced a metric that an accepted claim names". That reason was
   wrong (the metric exists, the claim keys do not meet it), and a demo database with scores exists now. Rewritten.
4. The lessons listed four per-paper changes as "what we would change next"; all four were applied in Pilot 3. Replaced.
5. A limitation said that the read-only data mount of `paper_003` "is proposed as a change for the next pilot"; it was applied in Pilot 3.
6. The introduction said that the pilot covers tabular machine learning only; Pilot 4, the candidate lists and the automatic search left
   that domain. Corrected.
7. Section 4.2 did not say how a claim is matched with a metric; the sentence was added, because section 6.11 depends on it.
8. The abstract had no statement of what is claimed; the two claims were added.
9. The limitations did not name that a README command mostly does not produce the paper's table, that the scorer can label a paper without
   a comparison, and that K2 has no positive control. Added.

Checked and left as they are: the pilot rates in sections 1, 6.1, 6.1a and 6.5 (generated, in sync); the Pilot 4 and candidate numbers
(generated); the statement that no paper was replaced because it failed (#166; no replacement was made); the related-work statements
(unchanged since their verification).

Not verified: that no other stale sentence remains in sections that were read but have no phrase that the search looks for; that the
walk-through numbers of the clean-clone run (section 6.4) match a run record, because the record is not in the repository.
