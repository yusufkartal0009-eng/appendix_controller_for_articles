# Paper status (updated 2026-10-28, issue #550; first written 2026-10-25, issue #503)

Which parts of `docs/report/REPORT.md` are in their final form, and which wait for the owner's decision or input. One line per
item. The owner's open decisions are listed with their long form in `docs/PENDING.md`; this page only says what the report needs.

## 1. Sections of the report

| Section | State | Waits for |
|---|---|---|
| 1 Abstract | Final in content; updated on 2026-10-25 with the two claims and the new results | nothing |
| 2 Introduction | Final (sourced in `docs/INTRODUCTION_SOURCES.md`) | nothing |
| 3 Related work | Final (nine sources verified by `scripts/verify_sources.py`; abstracts and bibliographic data only, no full texts) | nothing |
| 4 Method | Final; the label rule (#540) and the Tier 3 rule (#542) were added on 2026-10-28 | **Tier 3 rule (D7):** the claimed-metric rule is a default chosen by the assistant; the owner may revise it |
| 5 Experimental setup | Final | nothing |
| 6.1, 6.1a Pilots 1 to 3 | Final | nothing |
| 6.2 Claim extraction | Final | nothing |
| 6.3 What the pilots do not show | Final; rewritten on 2026-10-25 (it had stopped at Pilot 2) | nothing |
| 6.4 Checks after the pilots | Final, except the extended gold set | **Gold set 2:** the owner's own answers to the 18 added questions (D2; form kept outside the repository); until then no precision or recall is claimed for them |
| 6.4a Seed runs, GPU check | Final; the two Tier 3 rules are shown side by side (generated block `tier3binding`) | **Tier 3 rule (D7):** the owner may revise the default (the claimed metric decides) |
| 6.5 Pilot 4 | Final | nothing |
| 6.5a External reference (ReScience C) | Final as a negative result | **Reference (D5):** what outside reference to use now that none was selected; a question for the owner and the mentor |
| 6.6 Field analysis | Final (exploratory) | nothing |
| 6.7 Diagnosis layer | Final; no real language model was used | nothing |
| 6.8 Candidate papers | Final | **Candidates (D9):** whether to repair further or stop adding papers |
| 6.9 Tolerance probe | Final; the 0.05 allowance is stated as a known limit | **Scorer rules (D10, K-B):** the owner may revise the default (the allowance stays) |
| 6.10 Automatic search | Final | **Round 3 (D11):** whether to run a stage 8 or to stop |
| 6.11 Real verdicts and the pilot as an estimate | New, written from the stored files on 2026-10-25 | **Claim matching:** the claim map (`data/claim_metric_map.json`, #507, #509) is a proposal the owner may revise; before it the command-line path never compared a real claim; the owner should read the section once, because it states that the expected K2 positive control was not obtained |
| 6.12 Why the runs failed | New (2026-10-28), generated from `data/failure_statistics.json` | nothing |
| 6.13 The dashboard in its final form | New (2026-10-28) | **Dashboard choices:** layout choices are defaults that follow the earlier design; the owner may revise them (`AGENTS.md` section 6, rule 9) |
| 7 Limitations | Final; extended on 2026-10-28 (total with a baseline, no K2 positive control, 0.05 allowance, selection bias, 0 of 65 from ReScience C, no second gold set, no real language model) | nothing |
| 8 Lessons learned | Final; one lesson added and the "what we would change next" list replaced | nothing |
| 9 Conclusion and future work | Final; the dashboard sentence and the claims were updated | nothing |
| 10 References and reproducibility statement | Final | **Release:** no version is tagged (#45), so the version of the report is a commit |
| 10 DRAFT marks | `docs/report/REPORT.md` carries no `DRAFT` mark today (searched on 2026-10-28); the AI assistance statement was not changed | **Approval:** the owner reads the report and confirms that it may be called final |
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

## 4. Consistency scan of 2026-10-28 (issue #550)

The report was read from the abstract to the references. The phrases that carry a claim about the state of the work ("pending", "will",
"not yet", "Partially Verified", the section numbers, the numbers of the two claims) were searched, every `--check` was run, and the sources
were checked (`python scripts/verify_sources.py --check`: nothing missing).

Found and fixed:

1. Section 6.11 and the limitations said that `paper_004`, `paper_006` and `paper_102` get `Partially Verified` from the build tiers alone. Since
   #540 such a run is `Needs Review`; the text now says so and states that the total still contains the neutral baseline.
2. Section 4.2 did not state the label rule of #540 or the Tier 3 rule of #542 (it still said that the largest CV decides). Rewritten.
3. Section 6.4a said that "whether the rule is the right one is a question for the owner" without the change that followed (#542); it now
   shows both rules in a generated block (`tier3binding`).
4. Section 5.2 said "in both pilots" for the resource limits although Pilots 3 and 4 changed some. Corrected.
5. The conclusion pointed to `docs/evidence/demo2/` and a dashboard without reasons; it now points to the final dashboard (section 6.13,
   `docs/evidence/demo3/`).
6. The limitations did not name, as items of their own, the 0.05 allowance, the selection bias, the missing K2 positive control, the 0 of 65
   from ReScience C, the missing second gold set and that no language-model path ran with a real model. Added.
7. Section 6.12 had a doubled parenthesis. Corrected.

Checked and left: all `section N` references point to existing sections; the pilot rates, the candidate and search counts and the verdict
table are generated blocks in sync. The automatic search of round 4 has 107 runs in `evaluation.json` and 105 stored run folders (the failure
statistics count folders); the report blocks that come from `evaluation.json` say 107.

Not verified: that no stale sentence remains in text that the search phrases do not reach; the clean-clone walk-through numbers (the run
record is not in the repository).

## 5. Export

On 2026-10-28 (night 8) no converter was found and no PDF was made. On the same night (night 9, issue #567) the project's own dependency `fpdf2` turned out to be enough: `python scripts/export_report.py` writes `docs/report/REPORT.pdf` (22 pages) and `python scripts/export_report.py --check` fails if the committed PDF has other text than a fresh rendering of `docs/report/REPORT.md` (a test does the same). The PDF is made with core fonts, so the five characters of the report outside Latin-1 are written in ASCII (`REPLACEMENTS` in the script); the HTML comments that mark the generated number blocks are not shown. A test compares the AI assistance statement, every `DRAFT` mark, and every paragraph, list item, heading and table cell of the Markdown with the text of the PDF. The report carries no `DRAFT` mark today, and the statement is copied unchanged. **Not verified:** the layout in a PDF viewer other than the page images that were looked at (pages 1, 7, 13 and 22 were rendered and read); the PDF is not a typeset paper and does not use a conference template.

## 6. Number audit of 2026-10-28 (issue #554)

Every hand-typed number of the report, the README and the status documents was checked against its source; the table and the seven corrections are in `docs/NUMBER_AUDIT.md`.
