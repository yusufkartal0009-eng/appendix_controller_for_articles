# Repro Radar — Final Report (skeleton)

> **Status: skeleton only** (#120, created 2026-10-05). Each section holds its one-line purpose, what it needs before it
> can be written, and where that evidence is (or that it does not exist yet). **No section is written before its
> evidence exists in the repository** (a merged PR, a stored run report, or a script output). Every number will come
> from a script, and every factual statement will be listed in a claim → source table.

---

## 1. Abstract

**Purpose:** summarize the problem, the method, and what the evidence supports, in at most 200 words; written last.

- **Needs:** sections 2–10.
- **Status:** not started.

## 2. Introduction

**Purpose:** state the problem (published ML results that cannot be checked) and why an automated, isolated
re-run helps.

- **Needs:** the sourced, corrected introduction draft (#118, PR #119; sources in `docs/INTRODUCTION_SOURCES.md`).
- **Status:** evidence exists; not yet written here.

## 3. Related work

**Purpose:** place Repro Radar among existing reproducibility efforts and tools, and say how it differs.

- **Needs:** 5–10 sources, each checked against the original.
- **Status:** not started (no verified source list yet).

## 4. Method

**Purpose:** describe the sandbox and its threat model, the four-tier score, claim extraction with the quote guard,
and the tolerance rules.

- **Needs:**
  - the sandbox evidence (`docs/SANDBOX_ACCEPTANCE.md`);
  - the extraction protocol (`docs/AGENT_EXTRACTION.md`);
  - the claim store and review step (#10, #134).
- **Status:** partly evidenced. The scoring tiers are not yet connected to real runs (#136).

## 5. Experimental setup

**Purpose:** describe the corpus, its verification, the pinned commits, the sandbox limits, and the definitions of
install and run success.

- **Needs:**
  - `docs/CORPUS_VERIFICATION.md`;
  - `data/seed_papers.json` with the run setups;
  - the pilot protocols (`docs/PILOT_WEEK2.md`, `docs/PILOT_2.md`).
- **Status:** partly evidenced.

## 6. Results

**Purpose:** report the pilot rates and failure categories, and the precision and recall of claim extraction.

- **Needs:**
  - Pilot 1 (exists, `docs/PILOT_WEEK2.md` section 11);
  - Pilot 2 runs (#171, not run);
  - the gold set and its precision/recall (#133, not filled).
- **Status:** blocked.

## 7. Limitations and threats to validity

**Purpose:** state honestly what the results cannot show: small n, run setups written by us, hardware and seeds,
extraction errors, and what was not done.

- **Needs:** Pilot 2 done; written before the Abstract and the Conclusion.
- **Status:** blocked.

## 8. Lessons learned

**Purpose:** record what surprised us and what we would change.

- **Needs:** Pilot 2 done.
- **Status:** blocked.

## 9. Conclusion and future work

**Purpose:** say what the evidence supports and what should come next, no more than section 7 allows.

- **Needs:** sections 6 and 7.
- **Status:** blocked.

## 10. References and reproducibility statement

**Purpose:** list every reference, each checked against its source, and explain how to re-run everything (commit,
commands, data).

- **Needs:** a tagged commit and the verified source list.
- **Status:** not started.
