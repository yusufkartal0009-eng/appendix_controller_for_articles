# Related work (report section 3): claims and sources

> Draft for the owner's review (#270). Every external statement in section 3 of `REPORT.md` is listed with its source
> and with the words of the source that support it. The lookups are in `related_work_verification.json`, written by
> `python scripts/verify_sources.py` from `related_work_sources.json`. **What was read: bibliographic data from Crossref
> or the arXiv API, and the abstract where the service returned one. No full text was read.** A statement that goes
> beyond what the abstract says is not in the draft.

## 1. References: how each was verified

| # | Reference | Looked up in | Agreed on | Not verified |
|---|---|---|---|---|
| [6] | Pineau et al., *Improving Reproducibility in Machine Learning Research (A Report from the NeurIPS 2019 Reproducibility Program)*, JMLR 22(164), 2021 | arXiv 2003.12206 (title, first author; the preprint is from 2020) | title, first author | the JMLR volume, issue, and year here (checked earlier at jmlr.org, `docs/INTRODUCTION_SOURCES.md`) |
| [7] | Henderson, Islam, Bachman, Pineau, Precup, Meger, *Deep Reinforcement Learning That Matters*, AAAI 32(1), 2018 | Crossref `10.1609/aaai.v32i1.11694`; arXiv 1709.06560 | title, first author, year | pages |
| [8] | Gundersen and Kjensmo, *State of the Art: Reproducibility in Artificial Intelligence*, AAAI 32(1), 2018 | Crossref `10.1609/aaai.v32i1.11503` | title, first author, year, authors, volume and issue | pages |
| [9] | Raff, *A Step Toward Quantifying Independently Reproducible Machine Learning Research*, arXiv 1909.06674, 2019 | arXiv 1909.06674 | title, first author, year | the conference version (NeurIPS 2019) was not looked up; cite the preprint |
| [10] | Collberg and Proebsting, *Repeatability in computer systems research*, Communications of the ACM 59(3), 62-69, 2016 | Crossref `10.1145/2812803` | title, first author, year, authors, volume, issue, pages | |
| [11] | Pimentel, Murta, Braganholo, Freire, *A Large-Scale Study About Quality and Reproducibility of Jupyter Notebooks*, MSR 2019, 507-517 | Crossref `10.1109/MSR.2019.00077` | title, first author, year, authors, pages | the abstract (Crossref returned none) |
| [12] | Trisovic, Lau, Pasquier, Crosas, *A large-scale study on research code quality and execution*, Scientific Data 9(1), 60, 2022 | Crossref `10.1038/s41597-022-01143-6` | title, first author, year, authors, volume, issue, article number | |
| [13] | Boettiger, *An introduction to Docker for reproducible research*, ACM SIGOPS Operating Systems Review 49(1), 71-79, 2015 | Crossref `10.1145/2723872.2723882`; arXiv 1410.0846 (its title adds ", with examples from the R environment") | title, first author, year, authors, volume, issue, pages | |
| [14] | Bouthillier et al., *Accounting for Variance in Machine Learning Benchmarks*, arXiv 2103.03098, 2021 | arXiv 2103.03098 | title, first author, year | the conference version (MLSys 2021) was not looked up; cite the preprint |

Section 10 of the report (the reference list) is not written here; this table is what it should draw on for [8]-[14].

## 2. Claims in section 3 and their sources

| Claim in the draft | Source | Words of the source that support it | Read |
|---|---|---|---|
| 400 papers from IJCAI and AAAI were surveyed with six reproducibility metrics | [8] | "A total of 400 research papers from the conference series IJCAI and AAAI have been surveyed using the metrics"; "six reproducibility metrics" | abstract |
| None documented all the variables; between 20% and 30% of the variables for each factor were documented | [8] | "None of the papers document all of the variables. The metrics show that between 20% and 30% of the variables for each factor are documented." | abstract |
| 255 papers from 1984 to 2017 were implemented without looking at the authors' code, and analyzed statistically | [9] | "manually attempting to implement 255 papers published from 1984 until 2017, recording features of each paper, and performing statistical analysis"; "we did not look at the authors code" | abstract |
| Releasing code is important but not sufficient for determining reproducibility | [9] | "Our field focuses on releasing code, which is important, but is not sufficient for determining reproducibility." | abstract |
| The NeurIPS 2019 program had a code submission policy, a reproducibility challenge, and a checklist in the submission process | [6] | "a code submission policy, a community-wide reproducibility challenge, and the inclusion of the Machine Learning Reproducibility checklist as part of the paper submission process" | abstract |
| For computer systems research: fund repeatability engineering and reward sharing of research artifacts | [10] | Crossref abstract: "To encourage repeatable research, fund repeatability engineering and reward commitments to sharing research artifacts." | abstract (one sentence) |
| R code from more than 2,000 replication datasets was executed in a clean runtime environment | [12] | "we retrieve and analyze more than 2000 replication datasets with over 9000 unique R files"; "we execute the code in a clean runtime environment" | abstract |
| 74% of the R files failed in the first execution; 56% still failed after automatic code cleaning | [12] | "74% of R files failed to complete without error in the initial execution, while 56% failed when code cleaning was applied" | abstract |
| A large-scale study of the quality and reproducibility of Jupyter notebooks exists | [11] | the title only | title and bibliographic data |
| Code written for one project often cannot be run or extended by later researchers; Docker is presented as one way to address this | [13] | "common reasons that code developed for one research project cannot be successfully executed or extended by subsequent researchers"; "examine how the popular emerging technology Docker ... address[es] these challenges" | abstract |
| Non-determinism in benchmark environments with variance intrinsic to the methods can make reported results hard to interpret (deep RL) | [7] | "non-determinism in standard benchmark environments, combined with variance intrinsic to the methods, can make reported results tough to interpret" | abstract |
| Data sampling, parameter initialization, and hyperparameter choice each affect results markedly | [14] | "variance due to data sampling, parameter initialization and hyperparameter choice impact markedly the results" | abstract |

## 3. Statements about Repro Radar in the draft (project evidence, not literature)

| Statement | Evidence |
|---|---|
| Six tabular ML papers, each at a pinned commit, chosen by the project | `data/seed_papers.json` (`repo_commit`), `tests/test_seed.py` |
| Run in an isolated sandbox, with a setup written by the project | `docs/SANDBOX_ACCEPTANCE.md`, `docs/SECURITY_AUDIT.md`, `run_setup` in `data/seed_papers.json` |
| Judged against numbers that a person accepted after a verbatim-quote check | `docs/AGENT_EXTRACTION.md`, `src/quote_guard.py`, `data/claims/review_decisions.json` |
| The pilots used one counted run per paper, so Tier 3 has not been exercised on real results | `docs/PILOT_2.md` (counted records in `data/pilot2_runs/`) |
| The counts are not comparable with [12] (other language, other selection, far smaller n) | a comparison made by the author of the draft, from [12]'s abstract and the corpus size |

## 4. Not done

- No full text of any source was read. A reader who needs more than the abstract's statements should open the papers.
- Candidate sources that were not looked up are not cited (no unverified source is in the draft).
- Whether the list is the right one for the report is the owner's call; it covers measurement of reproducibility, execution of released code, containers, and variance, and it is not a systematic search.
