# Field analysis (week 6): definitions

Issue: #413. This part of the document is the **definitions**. It was written before `scripts/field_analysis.py` existed and before any rate, autonomy figure, or factor value was computed in the form defined here. The author already knew the outcomes of Pilots 1 to 4 (they are in the repository), so the definitions are not blind to them; what is fixed in advance is how each number is computed. A later section (results) is added only from the script's output.

## 1. Pool

12 papers: the 6 seed papers of `data/seed_papers.json` (`paper_002`, `paper_003`, `paper_004`, `paper_005`, `paper_006`, `paper_008`) and the 6 papers of `data/corpus_expansion/papers.json` (`paper_101` to `paper_106`, Pilot 4). The ReScience selection (65 articles evaluated, none selected) and the external-validation articles are **not** in the pool, because no run was made for them.

The analysis is **exploratory, n = 12**. No test of significance is made and no relationship is claimed. The two sub-pools differ in how they were chosen and how they were run (section 3), so they are always shown separately as well as together.

## 2. Reference runs

Each paper has two reference runs, taken from the stored measurements and not recomputed:

| | Seed papers (6) | Expansion papers (6) |
|---|---|---|
| **First protocol run** | Pilot 1, `data/pilot_runs/measurements.json` (`docs/PILOT_WEEK2.md`) | Pilot 4 first attempt, `strict` in `data/pilot4_runs/summary.json` (`docs/PILOT_4.md`) |
| **Final protocol run** | Pilot 3, `data/pilot3_runs/measurements.json` (`docs/PILOT_3.md`) | Pilot 4 after the one correction round, `corrected` in `data/pilot4_runs/summary.json` |

The final run of a seed paper comes after settings that were chosen from Pilot 2's failures (`data/pilot3_settings.json`); it measures the settings as much as the paper (`docs/PILOT_3.md` section 1).

## 3. Success rates

For each reference run and each sub-pool, the script counts the stored booleans: **setup success** (`install_success`), **run success** (`run_success`), and **pilot success** (`pilot_success`), as defined in `docs/PILOT_WEEK2.md` section 5 (install success is `dependency_install_status: INSTALLED`, run success is exit code 0 of a valid run, pilot success is both). It reports `k / n` and the proportion; the denominator is the number of papers of the pool (6 or 12), also for a paper whose run could not start. It does not redefine any of them. A rate is the share of the papers of the pool, not an estimate of a rate in the field.

## 4. Human intervention

A person's action counts as **human intervention** in a paper's outcome when it is one of the following. Each is read from a stored file, so the script can decide it mechanically.

| Code | Intervention | How the script decides it |
|---|---|---|
| I1 | **A command or run setup chosen by a person.** The entry point and its arguments, data mounts, environment variables, Python version, build steps, or pip constraints were written by a person for this paper. | A seed paper: always (its `target_script`, and for Pilots 2 and 3 its `run_setup` with `decision: fix`, were chosen by the owner or the agent). An expansion paper: only if `run_command` differs from the command the paper's README states, which no paper does (the command is taken from the README by rule E4 of `docs/EXTERNAL_VALIDATION.md` and `docs/PILOT_4.md`); this is recorded as `false` for them unless `data/pilot4_runs/summary.json` shows otherwise. |
| I2 | **A correction round or a per-paper change made after a failure was seen.** | A paper listed in `data/pilot3_settings.json`; a Pilot 4 paper with `correction_round: true`. |
| I3 | **A change to Repro Radar made to get this paper through** (a defect of the tool fixed, then the paper run again). | Pilot 2: a paper with an attempt in `data/pilot2_runs/first_attempts/index.json` whose `superseded_because` does not contain "No defect". Pilot 4: a paper with a folder in `data/pilot4_runs/first_attempts/` whose name contains `tool_defect`. |
| I4 | **A claim accepted by a person.** | A paper with at least one claim of `data/claims/review_decisions.json` whose `review_status` is `accepted` and whose `verified_by` is `human`. |

I1 to I3 are interventions in **getting an outcome** (a run result or a classified failure). I4 is an intervention in **scoring**: by the rule of this project only a person accepts a claim (`src/claim_review.py` stores every decision with `verified_by: human`), so scoring is never autonomous by design. The script therefore reports I4 as a count of papers with at least one accepted claim, **not** as part of a rate; an "autonomy rate" that includes I4 would be 0 by construction.

## 5. The AI autonomy rate

> **AI autonomy rate** = the percentage of the papers of a pool whose outcome was reached with none of I1, I2, and I3.

"Outcome" means that the paper has a stored result of the reference run: either a pilot success or a classified failure (`docs/PILOT_WEEK2.md` section 7). It is calculated twice:

- **Concluded autonomously:** papers with an outcome and none of I1 to I3, over the papers of the pool.
- **Succeeded autonomously:** papers with a pilot success and none of I1 to I3, over the papers of the pool.

For the seed papers I1 holds by definition, so their rate is 0 / 6 by construction; the figure is still printed, with that remark, so that the pool total is not mistaken for something else. The meaningful comparison is among the expansion papers.

The word "AI" in the name is the project's: the pipeline and the agent that ran it are the "AI"; the rate does not measure a model. It counts the human actions listed in section 4 and no others, so actions that the stored files do not show are not counted (for example reading a log).

## 6. Factors

Three descriptive factors per paper, computed from the repository at the **pinned commit** by `scripts/field_analysis.py --extract-features` (this step needs the cloned repositories in `.sandbox_staging/`) and stored in `data/field_analysis/features.json` with the README's SHA-256, so that the table can be recomputed without the clones.

- **F1, documentation quality (0 to 4).** One point each for: (a) a README file exists; (b) it contains an installation instruction (`pip install`, `conda`, `requirements`, `environment.yml`, or `setup.py`); (c) it contains a run command in a code block (a line starting with `python`, `python3`, `bash`, `sh`, `make`, or `jupyter`); (d) it describes data (the word `data` or `dataset` with `download` or `prepare` in the same README). The checklist is crude and counts words, not correctness; it is the measure, not a judgement of the README.
- **F2, code age (years).** The time between the commit date of the pinned commit and the start of the paper's first protocol run (`started_at` in its `pilot_record.json`), in years of 365.25 days.
- **F3, number of declared dependencies.** The number of requirement lines (not comments, not options such as `-r`) in the requirement files recorded at staging (`stage.requirements_files` of the pilot record), plus the entries of a conda environment file (its `dependencies`, including a nested `pip` list). 0 when the repository declares none.

The table lists each paper's factors next to its first and final outcomes and, per factor, the median among papers with and without a pilot success. **It is a table, not a test.** With 12 papers and three factors, any pattern could be chance, and the factors are related to each other and to how the papers were chosen (the seed papers were chosen for tabular deep learning; the expansion papers by rule from a pool of arXiv articles).

## 7. What the analysis will not say

- That a factor causes or predicts reproducibility.
- That the rates describe the field: the pool is 12 papers, not a sample.
- That the autonomy rate measures a model's ability: it counts recorded human actions.
- Anything about papers outside the pool.

<!-- field-analysis:start -->
## 8. Results (generated)

Generated by `scripts/field_analysis.py` from the stored records; do not edit by hand. Exploratory, n = 12 (6 + 6): no test of significance is made and no relationship is claimed.

### 8.1 Clarification written with the script (before the first computation)

Section 5 does not say which reference run the autonomy rate is computed for. It is computed for **both**: for the first protocol run only I1 counts (I2 and I3 are, by their definition, made after a first run); for the final protocol run I1, I2, and I3 count. Concluded and succeeded autonomously are counted over all papers of the pool.

### 8.2 Success rates

**First protocol run (Pilot 1 for seed papers, Pilot 4 first attempt for expansion papers)**

| Pool | Setup success | Run success | Pilot success |
|---|---|---|---|
| seed papers | 1 / 6 (17%) | 0 / 6 (0%) | 0 / 6 (0%) |
| expansion papers | 2 / 6 (33%) | 2 / 6 (33%) | 1 / 6 (17%) |
| all 12 papers | 3 / 12 (25%) | 2 / 12 (17%) | 1 / 12 (8%) |

**Final protocol run (Pilot 3 for seed papers, Pilot 4 after the correction round for expansion papers)**

| Pool | Setup success | Run success | Pilot success |
|---|---|---|---|
| seed papers | 6 / 6 (100%) | 2 / 6 (33%) | 2 / 6 (33%) |
| expansion papers | 3 / 6 (50%) | 2 / 6 (33%) | 1 / 6 (17%) |
| all 12 papers | 9 / 12 (75%) | 4 / 12 (33%) | 3 / 12 (25%) |

### 8.3 Human intervention per paper

| Paper | Pool | I1 command or setup by a person | I2 correction or setting after a failure | I3 tool change for the paper | I4 claim accepted by a person |
|---|---|---|---|---|---|
| `paper_002` | seed | yes | yes | no | yes |
| `paper_003` | seed | yes | yes | no | yes |
| `paper_004` | seed | yes | yes | yes | yes |
| `paper_005` | seed | yes | yes | yes | yes |
| `paper_006` | seed | yes | no | yes | yes |
| `paper_008` | seed | yes | no | yes | yes |
| `paper_101` | expansion | no | no | no | no |
| `paper_102` | expansion | no | no | no | no |
| `paper_103` | expansion | no | no | no | no |
| `paper_104` | expansion | no | no | no | no |
| `paper_105` | expansion | no | no | no | no |
| `paper_106` | expansion | no | yes | yes | no |

### 8.4 AI autonomy rate

For the seed papers I1 holds by definition, so their rate is 0 by construction (section 5).

| Pool | Run | Concluded autonomously | Succeeded autonomously |
|---|---|---|---|
| seed papers | first | 0 / 6 (0%) | 0 / 6 (0%) |
| seed papers | final | 0 / 6 (0%) | 0 / 6 (0%) |
| expansion papers | first | 6 / 6 (100%) | 1 / 6 (17%) |
| expansion papers | final | 5 / 6 (83%) | 1 / 6 (17%) |
| all 12 papers | first | 6 / 12 (50%) | 1 / 12 (8%) |
| all 12 papers | final | 5 / 12 (42%) | 1 / 12 (8%) |

Papers with at least one claim accepted by a person (I4, not part of the rate): seed papers 6 / 6 (100%), expansion papers 0 / 6 (0%), all 12 papers 6 / 12 (50%).

### 8.5 Factors (descriptive table, not a test)

| Paper | Pool | F1 documentation (0-4) | F2 code age (years) | F3 declared dependencies | Pilot success, first run | Pilot success, final run |
|---|---|---|---|---|---|---|
| `paper_002` | seed | 2 | 1.93 | 12 | no | no |
| `paper_003` | seed | 4 | 1.88 | 28 | no | yes |
| `paper_004` | seed | 3 | 0.87 | 439 | no | no |
| `paper_005` | seed | 3 | 5.39 | 10 | no | no |
| `paper_006` | seed | 3 | 4.82 | 194 | no | yes |
| `paper_008` | seed | 3 | 4.62 | 5 | no | no |
| `paper_101` | expansion | 3 | 0.02 | 0 | no | no |
| `paper_102` | expansion | 4 | 0.41 | 3 | yes | yes |
| `paper_103` | expansion | 4 | 4.07 | 12 | no | no |
| `paper_104` | expansion | 4 | 0.16 | 8 | no | no |
| `paper_105` | expansion | 3 | 2.48 | 9 | no | no |
| `paper_106` | expansion | 3 | 4.29 | 0 | no | no |

F3 sums all requirement files and conda environment files of a repository (`data/field_analysis/features.json` lists them). A conda environment file lists every package of an environment, system libraries included, so it counts far more than a requirements file; the two kinds of file are not comparable.

Median of each factor among the papers with and without a pilot success of the **final** run (the numbers of papers are in parentheses; with so few papers a median says little):

| Factor | With pilot success | Without pilot success |
|---|---|---|
| F1 documentation | 4 (n=3) | 3 (n=9) |
| F2 code age | 1.88 (n=3) | 2.48 (n=9) |
| F3 dependencies | 28 (n=3) | 9 (n=9) |

<!-- field-analysis:end -->
