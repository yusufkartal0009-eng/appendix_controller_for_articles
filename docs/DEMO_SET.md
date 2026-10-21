# Demo set: how light, easy-to-analyse papers are chosen

Date written: 2026-10-21. Issue #421. This document is written and merged **before any candidate repository of the pool below
has been listed or opened**. At the time of writing no search of this document has been run. The rules are mechanical on
purpose: a script applies them and a reader can re-check them.

## 1. What this set is, and what it is not

The owner wants papers for the dashboard that **run fast, bring their own data, and are easy to analyse**. This is a
**demo set**. It is chosen on purpose, and it is **not a random sample** of papers. Therefore:

- **Nothing in this set is a success rate.** The share of candidates that pass is a property of these rules and of this pool,
  not of machine learning papers, and it is never to be quoted as the reproducibility of the field.
- Only the papers that pass the run test (K1, section 4) are shown. They are not representative of the pool they came from.
- The candidates are not replaced or repaired after a failed run (section 4).
- Whatever this set shows on the dashboard has to carry this label: "demo set, hand-picked rules, not a success rate".

The set is separate from `data/seed_papers.json` and from `data/corpus_expansion/papers.json`. Neither file is changed.

## 2. The pool and its order

The pool is the union of the first 100 results (default order, "best match") of these eight GitHub repository searches, run
once on the day of selection and stored unchanged, with the date and the exact query strings, in `data/demo_set/pool.json`.
Each query is the topic plus the common part:

    topic:<topic> arxiv.org in:readme language:Python archived:false fork:false size:<20000

with `<topic>` in this order: `scikit-learn`, `tabular-data`, `time-series`, `classification`, `clustering`,
`anomaly-detection`, `gradient-boosting`, `reproducibility`. (`size:<20000` is the GitHub search qualifier, in KB.)

Duplicates are removed (case-insensitive). The candidates are then **ordered by the SHA-256 hash of the lower-case
`owner/name`**, ascending. No other ordering is used: not stars, not date, not content.

## 3. The static rules S1 to S6

Candidates are checked in the hash order. Each candidate is checked against S1 to S6 in this order; the **first rule it fails**
is recorded as its reason in `data/demo_set/evaluation.json`. Only repository metadata, the README, a few named files, and the
paper's text are used.

| Rule | A candidate passes when |
|---|---|
| S1 Repository | It is public, Python is its main language, it is not archived, it is not a fork, and GitHub's `license.spdx_id` is in `ALLOWED_LICENSES` of `src/config.py`. |
| S2 Run command | The README holds a fenced code block with a line that starts with `python ` followed by a path to a `.py` file that exists in the repository at the pinned commit. The **first** such line is the run command, taken verbatim with its arguments (backslash continuations joined, a trailing shell comment removed, `setup.py` lines skipped as install commands: the same function as R3 of `docs/CORPUS_EXPANSION.md`). |
| S3 No GPU | Neither the README nor the repository's requirement files (`requirements*.txt`, `setup.py`, `environment.yml`, `pyproject.toml`) contain `gpu` or `cuda` (case-insensitive), and the run command has no GPU option. |
| S4 Size | The GitHub API `size` is at most 100,000 KB and `.gitattributes` has no `filter=lfs` line. |
| S5 Paper | The README links an arXiv paper (`arxiv.org/abs/<id>` or `arxiv.org/pdf/<id>`) and the paper's text (pypdf) has at least two table captions of the form `Table <n>` at the start of a line and at least 20 numbers with a decimal point (the counting of R6 in `scripts/corpus_expansion.py`). |
| S6 New | The repository is not in `data/seed_papers.json` and not in `data/corpus_expansion/papers.json`, and the paper's arXiv id is not in either file, and no earlier selected candidate uses the same repository or paper. |

The pinned commit is the head of the default branch on the day of selection. A candidate that passes S1 to S6 enters the
run test in the same order.

## 4. The run test K1

Every candidate that passes S1 to S6 is run **once**, in the hash order, **exactly as the README says**: no correction, no
extra requirement, no wrapper, no edit of the paper's code or data. The run is made as `scripts/run_pilot.py --pilot4` makes
it (`docs/PILOT_4.md` sections 2 and 3: the Docker sandbox, `--network none` in both phases, the repository's own requirement
files, the README command), with these settings:

| Setting | Value |
|---|---|
| Corpus file | `data/demo_set/papers.json` (all candidates that passed S1 to S6 are written there, in the order they are run) |
| Memory | `--memory 50%` of the host's RAM |
| CPUs | `--cpus 4` |
| Run time limit | **600 s** for the run phase (instead of the 14400 s of Pilot 4). The install phase keeps its limit. |
| Network | None, in both phases |
| Attempts | One per candidate |

A candidate **passes K1** only when all three hold:

1. the dependency installation status is `INSTALLED` or `SKIPPED`;
2. the run phase has status `COMPLETED` and exit code 0 (a valid run: `docker_used` and `isolated` are true);
3. the run's `stdout.log` or `stderr.log` has at least one **numeric metric line**: a line with a name, a `:` or `=`, and a
   number with a decimal point (the regular expression is in `scripts/demo_set.py`).

A candidate that does not pass K1 is **not replaced, not repaired and not run a second time**. It is skipped, and the reason
is recorded with a category (`install`, `run`, `timeout`, `memory`, `no_metric_line`, `harness`, `staging`) and the deciding
log line.

Downloaded code is untrusted data. It is only ever executed inside the sandbox container, never on the host.

## 5. When the search stops

The run test goes through the passing candidates in the hash order and stops at the first of:

- **5 candidates have passed K1**, or
- **30 runs** have been made, or
- **2.5 hours** have passed since the start of the run test, or
- the candidates that passed S1 to S6 are used up.

If fewer than 5 candidates passed, the document says how many, and the set is smaller. There is no second pool and no
loosening of a rule.

## 6. Limits that are known before the first search

- The pool is biased: repositories that GitHub's search returns for these topics, with `arxiv.org` in the README, small
  (under 20 MB), and without a GPU mention. It misses papers without a topic tag or without a README link.
- K1 selects for papers that run in 10 minutes without help. A paper that fails K1 may be reproducible with a correction;
  this set says nothing about that.
- The first `python` line of a README may be a data preparation step, an example, or a documentation checker; K1 runs it as
  written. A pass shows that this command ran and printed a number, not that the paper's main result is reproduced.
- A "numeric metric line" is a text pattern. It can match a log line that is not a result (a progress bar, a timing). The
  results section therefore names the table and the number of the paper that each shown metric is meant to correspond to,
  and says where that match was **not verified**.
- No claim of any paper is accepted by this set. Accepting a claim is the owner's decision alone.

## 7. Result (run of 2026-10-21, issue #421)

Applied with `scripts/demo_set.py` (`pool`, `run`, then `report`) to the pool stored in `data/demo_set/pool.json`. Every candidate with
its first failed rule or its run result is in `data/demo_set/evaluation.json`; the runs are in `data/demo_set/runs/<paper_id>/`
(local paths replaced by `<REPO>` and `<HOME>`). `data/demo_set/papers.json` holds every candidate that passed S1 to S6 and was run,
because the run reads it; **which of them passed K1 is in `evaluation.json`**. Only the papers that passed K1 are shown in section
7.3, and **they are not representative of the pool**. The tables below are generated (`python scripts/demo_set.py report`); the notes
after them are written by hand from them.

<!-- results:start -->
Generated by `scripts/demo_set.py report` from `data/demo_set/evaluation.json` (written 2026-10-21T19:33:27+00:00) and `data/demo_set/runs/`; do not edit by hand. The run stopped because: `time_limit`.

**Only the papers that passed K1 are shown in section 7.3. This is a hand-picked demo set: it is not representative of the pool it came from, and no number below is a success rate.**

### 7.1 What was tried

- Candidates checked against S1 to S6: 416 (the pool holds 464).
- Candidates that passed S1 to S6 and were run once: 22.
- Candidates that passed K1: 1.

First failed static rule of the checked candidates:

| Rule | Candidates |
|---|---|
| S1 | 159 |
| S2 | 179 |
| S3 | 41 |
| S4 | 1 |
| S5 | 9 |
| S6 | 5 |

Outcome of the run test K1:

| Outcome | Candidates |
|---|---|
| install | 5 |
| no_metric_line | 2 |
| passed | 1 |
| run | 14 |

### 7.2 Every run

| Id | Repository | Command | Install | Run | Exit | Seconds | Outcome | Deciding log line |
|---|---|---|---|---|---|---|---|---|
| demo_001 | `Mrawdian/llm-debate-judge-bias` | `python fetch_rfcs.py` | INSTALLED | FAILED | 1 | 0.651 | run | `urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>` |
| demo_002 | `Sajib-006/PerturbGraph` | `python stable_shift_bench.py --help` | INSTALLED | COMPLETED | 0 | 43.028 | no_metric_line | `--loss_gamma_cosine LOSS_GAMMA_COSINE` |
| demo_003 | `Phuriches/GenRepASD` | `python run_genrep_dcase2023.py --dataset_name dcase2023 --model_name beats_ft1 --pretrained_model_dir <path_to_pretrained_model> --temporal_pooling --n_mix_support 990 --alpha 0.9 --save_official` | INSTALLED | FAILED | 1 | 24.469 | run | `OSError: [Errno 30] Read-only file system: 'out'` |
| demo_004 | `Atlamtiz/Sonar-TS` | `python scripts/download_dataset.py` | INSTALLED | FAILED | 1 | 2.001 | run | `OSError: [Errno 30] Read-only file system: '/workspace/repo/nlqtsbench/ts_data'` |
| demo_005 | `yzhao062/auditable` | `python benchmarks/catchbench_parity/run_parity.py checks` | SKIPPED | FAILED | 1 | 0.642 | run | `catchbench_parity._env.ParityEnvironmentError: run the harness with PYTHONHASHSEED=0 (the CatchBench board is scored that way)` |
| demo_006 | `huan-yin/UniDG` | `python inference.py` | INSTALLED | FAILED | 1 | 0.506 | run | `ModuleNotFoundError: No module named 'cv2'` |
| demo_007 | `USC-FORTIS/AD-AGENT` | `python main.py` | INSTALLED | FAILED | 1 | 0.932 | run | `ValueError: OPENAI_API_KEY is missing. Set environment variable OPENAI_API_KEY or set Config.OPENAI_API_KEY in src/config/config.py.` |
| demo_008 | `ibm-client-engineering/output-drift-financial-llms` | `python data/generate_toy_finance.py` | INSTALLED | FAILED | 1 | 7.757 | run | `sqlite3.OperationalError: unable to open database file` |
| demo_009 | `ClimSocAna/tecb-de` | `python scripts/run_cteb_de.py --reddit-flag` | FAILED | FAILED | 1 | 0.616 | install | `ERROR: No matching distribution found for hdbscan==0.8.29` |
| demo_010 | `mainlp/semantic_components` | `python example.py` | FAILED | FAILED | 1 | 2.244 | install | `ERROR: No matching distribution found for jieba==0.42.1` |
| demo_011 | `smrfeld/tsmixer-pytorch` | `python download_etdataset.py` | INSTALLED | FAILED | 1 | 1.324 | run | `OSError: [Errno 30] Read-only file system: 'data'` |
| demo_012 | `GT-RIPL/L2C` | `python demo.py` | FAILED | FAILED | 1 | 0.517 | install | `ERROR: No matching distribution found for sklearn` |
| demo_013 | `SAP/synthesis-through-simulation` | `python scripts/compute_fidelity.py --env airline --all-runs` | SKIPPED | FAILED | 1 | 0.622 | run | `ModuleNotFoundError: No module named 'pydantic'` |
| demo_014 | `xcyao00/FOD` | `python create_distance_maps.py` | FAILED | FAILED | 1 | 0.794 | install | `ERROR: No matching distribution found for torchvision==0.14.1` |
| demo_015 | `moyi-dong/ExeCRE` | `python main.py --config configs/e1_execre_deepseek_chat.json` | INSTALLED | FAILED | 1 | 2.553 | run | `OSError: [Errno 30] Read-only file system: '/workspace/repo/results/e1'` |
| demo_016 | `HarmanDotpy/Normalizations-in-Deep-Learning` | `python train_cifar.py --normalization <norm_type> --data_dir ./dataset/cifar-10-batches-py --output_file ./saving_results/1.1.pth --n 2 --num_epochs 2` | SKIPPED | FAILED | 1 | 0.475 | run | `ModuleNotFoundError: No module named 'torch'` |
| demo_017 | `OthmaneAnalytics/sb-drift-experiments` | `python scripts/00_preflight.py --config configs/gg_1d.yaml` | INSTALLED | FAILED | 1 | 7.85 | run | `OSError: [Errno 30] Read-only file system: '/workspace/repo/results/processed/preflight/gg_1d.json'` |
| demo_018 | `xiahaifeng1995/FAVAE-anomaly-detection-localization-master` | `python train.py --obj bottle --do_aug` | SKIPPED | FAILED | 1 | 0.523 | run | `ModuleNotFoundError: No module named 'torch'` |
| demo_019 | `qiqi-xingyi/QSAD` | `python instance_sampling.py` | INSTALLED | FAILED | 1 | 11.617 | run | `OSError: [Errno 30] Read-only file system: '/workspace/repo/quantum_data'` |
| demo_020 | `skimeur/pioneer-detection-method` | `python pdm_demo.py` | INSTALLED | COMPLETED | 0 | 12.578 | passed | `` |
| demo_021 | `AgvanTsydypov/sample-efficiency-mujoco` | `python aggregate_results.py --env Hopper-v5 --algos ppo sac sac_ls1000` | FAILED | FAILED | 1 | 0.71 | install | `ERROR: No matching distribution found for contourpy==1.4.0` |
| demo_022 | `Byte-Authority/Byte-Authority` | `python src/injecagent_runner.py --help` | INSTALLED | COMPLETED | 0 | 49.474 | no_metric_line | `--payload-variant PAYLOAD_VARIANT` |

### 7.3 Papers that passed K1

#### demo_020: Insurance Supervision under Climate Change: A Pioneer Detection Method

- Paper: https://arxiv.org/abs/2511.16760
- Repository: https://github.com/skimeur/pioneer-detection-method at commit `0b2e72039012d63a62703d353e5c4396ab593a09` (MIT)
- Command: `python pdm_demo.py`
- Duration of the run phase: 12.578 s; install: INSTALLED
- Metric lines of the output (first 10):

  - `True post-break alpha: 1.5`

Where the printed numbers occur in the paper's text (exact string match on the PDF pages, `pypdf`; that the number means the same thing is **not verified**):

| Printed line | Number | Found as | PDF pages | Table captions on those pages |
|---|---|---|---|---|
| `True post-break alpha: 1.5` | 1.5 | 1.5 (as printed) | 23, 39, 40, 41 | Table 5 |

Decimal numbers with at least 3 decimals printed anywhere in `stdout.log`: 48; found in the paper's text by the same string match: 0.
<!-- results:end -->

Notes (by hand, from the generated part):

- **The set is smaller than the five that were asked for.** The run stopped on the 2.5-hour limit (`time_limit`) after the runs
  listed in 7.2, with candidates of the pool left unchecked (7.1). Nothing was loosened and no candidate was repeated.
- **K1 passed `demo_020` on a line that is a setup value, not a result.** The only numeric metric line that K1's pattern found is
  `True post-break alpha: 1.5` (the true value of the simulated parameter). The output also holds a table of RMSE values per method
  (`stdout.log` in `data/demo_set/runs/demo_020/`); K1 does not match those lines because they have no `:` or `=`. K1 was not changed
  after the run: this is a limit of the rule.
- **No number of the output was found in the paper.** None of the decimal numbers with three or more decimals printed by the run
  occurs as a string in the paper's text. The paper's tables (for example Tables 2 and 3) give RMSE **ratios** to the Pioneer method
  for several pooling methods, which resembles the output's "Relative" column, but nothing was found that equals a printed value.
  That the program reproduces a table of the paper is therefore **not verified**, and not claimed.
- Most failed runs stopped because the sandbox mounts the repository read-only and K1 allows no correction (`Read-only file
  system`), because a requirement could not be installed, or because the command needs a network, a key, or data (7.2). These are
  the obstacles that K1 treats as a failure; they say nothing about whether the papers are reproducible with help.
- The page text of the paper was read by `pypdf`; the table captions are the `Table <n>` lines at the start of a line, so a
  prose line that starts with "Table 5 reports" counts as a caption for rule S5 (the paper's own captions are in capitals).

