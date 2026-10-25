# Automatic search, round 3: runs checked against the paper text

Date written: 2026-10-25. Issue #469. This document is written and merged **before any pool of this round has been searched,
before any candidate has been listed, and before any candidate has been run**. The rules are mechanical on purpose: a script
applies them and a reader can re-check them. They were written without looking at any candidate list.

## 1. Why this round exists, and what it is not

In earlier rounds, no run of a real paper's code produced output that matched the paper's text (demo set: 1 of 22 runs passed
the run test and none of its printed numbers occurred in the paper; the repair round of the 29-candidate list: 1 of 14 passed
after repair, and its output did not match the paper's table). This round runs many more candidates, each exactly as its README
says, and measures automatically whether numbers printed by the run occur in the text of the paper (test K2, section 5).

It is **not** a sample of papers and **not** a success rate (section 9). Nothing here accepts a claim: accepting a claim is the
owner's decision alone. A candidate that passes K2 is a **match candidate**; it is never called verified, because a number can occur
in a paper by chance and because that a printed number means the same thing as the number in the paper is not checked.

The files of earlier rounds (`data/seed_papers.json`, `data/corpus_expansion/`, `data/demo_set/`, `data/candidates/`) are not
changed. This round writes only to `data/auto_search3/`.

## 2. The pool and its order

The pool is the union of the first 100 results (default order, "best match") of GitHub repository searches (`gh api
search/repositories` or the same call through `scripts/corpus_expansion.py`), run once per query on the day of selection and
stored unchanged, with the date and the exact query strings, in `data/auto_search3/pool.json`. Each query is

    arxiv.org in:readme language:Python archived:false fork:false size:<30000 topic:<topic>

(`size:<30000` is the GitHub search qualifier, in KB). The topics, in this order:

- **Stage 1:** `statistics`, `bayesian`, `optimization`, `causal-inference`, `survival-analysis`, `regression`, `simulation`,
  `signal-processing`, `computational-biology`, `physics`, `graph-algorithms`, `recommender-system`, `symbolic-regression`,
  `feature-selection`, `dimensionality-reduction`, `probabilistic-programming`.
- **Stage 2** (used only when the candidates of stage 1 are used up before a stop condition of section 6 holds):
  `numerical-methods`, `monte-carlo`, `differential-equations`, `econometrics`, `bioinformatics`, `chemistry`, `neuroscience`,
  `ecology`, `epidemiology`, `game-theory`, `information-theory`, `kernel-methods`, `ensemble-learning`, `time-series-forecasting`,
  `topic-modeling`, `nlp`.

- **Stage 3** (added on 2026-10-25 at 01:10, after stages 1 and 2 were used up with 780 candidates checked, 22 run and none passing K1; the topics were chosen from the list of common topics of the demo set and general topics, without looking at any candidate, and the same rules apply; used only when stage 2 is used up before a stop condition of section 6 holds): `machine-learning`, `deep-learning`, `data-science`, `scientific-computing`, `reinforcement-learning`, `computer-vision`, `graph-neural-networks`, `forecasting`, `clustering`, `classification`, `anomaly-detection`, `scikit-learn`, `tabular-data`, `time-series`, `benchmark`, `reproducibility`.

- **Stage 4** (added on 2026-10-25 at 02:35, after stages 1 to 3 were used up with 1,381 candidates checked, 54 run and none passing K1; general and paper-related topics, chosen without looking at any candidate; the same rules apply; used only when stage 3 is used up before a stop condition of section 6 holds): `arxiv`, `paper`, `research`, `research-paper`, `paper-implementation`, `official-implementation`, `reproducible-research`, `python`, `numpy`, `pandas`, `jax`, `matplotlib`, `algorithm`, `mathematics`, `data-analysis`, `evaluation`.

- **Stage 5** (added on 2026-10-25 at 04:00, before stage 4 is used up, with 76 candidates run and none passing K1; method and library topics chosen without looking at any candidate; the same rules apply; used only when stage 4 is used up before a stop condition of section 6 holds): `pytorch`, `neural-network`, `bayesian-inference`, `gaussian-processes`, `stochastic-processes`, `sampling`, `linear-algebra`, `scipy`, `xgboost`, `lightgbm`, `random-forest`, `svm`, `deep-reinforcement-learning`, `generative-model`, `explainable-ai`, `interpretability`.

- **Stage 6** (added on 2026-10-25 at 06:45, after stages 1 to 5 were used up with 2,508 candidates checked, 106 run, 2 passing K1 and none K2; algorithm and method topics chosen without looking at any candidate; the same rules apply; used only when stage 5 is used up before a stop condition of section 6 holds): `tensorflow`, `keras`, `transformers`, `natural-language-processing`, `data-mining`, `optimization-algorithms`, `evolutionary-algorithms`, `genetic-algorithm`, `federated-learning`, `graph-theory`, `time-series-analysis`, `bayesian-optimization`, `hyperparameter-optimization`, `uncertainty-quantification`, `machine-learning-algorithms`, `deep-neural-networks`.

- **Stage 7** (added on 2026-10-25 at 07:30, after stages 1 to 6 were used up with 2,992 candidates checked, 118 run, 2 passing K1 and none K2; domain topics chosen without looking at any candidate; the same rules apply; used only when stage 6 is used up before a stop condition of section 6 holds): `astronomy`, `geoscience`, `climate`, `finance`, `economics`, `genomics`, `medical-imaging`, `healthcare`, `materials-science`, `quantum`, `robotics`, `control-theory`, `social-network-analysis`, `computational-physics`, `image-processing`, `speech`.

Duplicates are removed (case-insensitive). The repositories of earlier rounds are **removed from the pool before ordering**: every
repository in `data/demo_set/pool.json` (the whole pool of the demo set, evaluated or not), in `data/candidates/` (all files),
in `data/seed_papers.json` and in `data/corpus_expansion/papers.json`. The remaining candidates are ordered by the **SHA-256 hash of the
lower-case `owner/name`**, ascending. Stages 2 to 7 are searched and stored as further blocks of the same file only when it is needed; its
candidates are ordered the same way and come after all candidates of stage 1. No other ordering is used: not stars, not date, not
content.

## 3. The static rules S1 to S6

The rules are those of `docs/DEMO_SET.md` section 3, unchanged, applied in this order; the **first rule a candidate fails** is
recorded as its reason. Only repository metadata, the README, a few named files and the paper's text are used.

| Rule | A candidate passes when |
|---|---|
| S1 Repository | Public, Python is the main language, not archived, not a fork, and GitHub's `license.spdx_id` is in `ALLOWED_LICENSES` of `src/config.py`. |
| S2 Run command | The README holds a fenced code block with a line that starts with `python ` followed by a path to a `.py` file that exists in the repository at the pinned commit. The **first** such line, verbatim with its arguments (backslash continuations joined, a trailing shell comment removed, `setup.py` lines skipped), is the run command. |
| S3 No GPU | Neither the README nor the requirement files (`requirements*.txt`, `setup.py`, `environment.yml`, `pyproject.toml`) contain `gpu` or `cuda` (case-insensitive), and the run command has no GPU option. |
| S4 Size | The GitHub API `size` is at most 100,000 KB and `.gitattributes` has no `filter=lfs` line. |
| S5 Paper | The README links an arXiv paper (`arxiv.org/abs/<id>` or `arxiv.org/pdf/<id>`) and the paper's text (pypdf) has at least two lines that start with `Table <n>` and at least 20 numbers with a decimal point. |
| S6 New | The repository is not in the seed, not in an earlier round (section 2), and the paper's arXiv id is not in the seed or in `data/corpus_expansion/papers.json`; no earlier candidate of this round uses the same repository or the same paper. |

The pinned commit is the head of the default branch on the day the candidate is checked. The static rules are applied in the hash
order, one candidate at a time; a candidate that passes S1 to S6 enters the run test at once (section 4). This lets the sandbox work
on one candidate while the next candidates can be checked statically.

## 4. The run test K1

Every candidate that passes S1 to S6 is run **once**, **exactly as the README says**: no correction, no extra requirement, no wrapper,
no edit of the paper's code or data. The run is made as `scripts/run_pilot.py --pilot4` makes it (`docs/PILOT_4.md` sections 2 and 3:
the Docker sandbox, `--network none` in both phases, the repository's own requirement files, the README command), with these
settings:

| Setting | Value |
|---|---|
| Memory | `--memory 50%` |
| CPUs | `--cpus 4` |
| Install time limit | **1200 s** |
| Run time limit | **600 s** |
| Network | None, in both phases |
| Attempts | One per candidate |
| Parallelism | At most one sandbox run at a time |

A candidate **passes K1** only when all three hold:

1. the dependency installation status is `INSTALLED` or `SKIPPED`;
2. the run phase has status `COMPLETED` and exit code 0 (a valid run: `docker_used` and `isolated` are true);
3. `stdout.log` or `stderr.log` has at least one numeric metric line (the pattern of `scripts/demo_set.py`: a name, a `:` or `=`,
   and a number with a decimal point).

A candidate that does not pass K1 is **not replaced, not repaired and not run a second time**. The reason is recorded with a category
(`install`, `run`, `timeout`, `memory`, `no_metric_line`, `harness`, `staging`) and the deciding log line. A run whose mechanism
crashed or hung is recorded as `harness` and the search continues; fixing the mechanism is a separate change and does not re-run the
candidate.

Downloaded code is untrusted data. It is only ever executed inside the sandbox container, never on the host. Downloaded PDFs are kept
under `data/pdfs` (not tracked by git); staging folders are under `.sandbox_staging`. After each candidate, the staging, wheel and
output folders that the run created are deleted.

## 5. The match test K2

K2 is computed for every candidate whose run phase is `COMPLETED` with exit code 0 (so that K2 can be reported next to K1); a candidate
**passes both tests** only when it passes K1 and K2.

**Numbers of the run.** Numbers are taken from `stdout.log` only (not from `stderr.log`, which holds warnings and progress bars). A
number is a **meaningful number** when all of these hold:

- it has at least **3 significant digits**: after removing the sign, thousands separators, the decimal point and leading zeros, at
  least 3 digits remain; for an integer the trailing zeros are also removed first (so `100` and `5000` do not count, `1234` does);
- it is not a **year** (an integer from 1900 to 2100 with no decimal part);
- it is not part of a **version** (two or more dots between digit groups, or a number preceded by `v` or `version`);
- it is not part of a **date or a time** (`2026-10-25`, `25/10/2026`, `12:30:05`, `12:30:05.123`);
- it is not an **index or a line number** (a number in square brackets, after `#`, after the word `line`, `epoch`, `step`, `iter`,
  `iteration`, `batch`, `fold`, `seed`, `row`, `col`, or in the `:<n>:` position of a traceback or file reference);
- it is not a single-digit number (a lone digit `0` to `9`), unless it is followed by `%`.

The distinct meaningful numbers are kept in the order in which they occur, each with its line.

**Text of the paper.** The PDF of the paper (downloaded from the arXiv link of the README) is read with pypdf, page by page. The text
is normalised for the comparison: the minus variants (`−`, `–`, `‑`) are read as `-`; a decimal comma is read as a decimal point; a
thousands separator (`,`, a thin space, or `'`) between digit groups of three is removed. A number of the run occurs in the paper when
its normalised string occurs in the normalised text of a page **in the same spelling** (the same digits, the same number of
decimals; `0.50` does not match `0.5`; a leading zero may be dropped, as in `.5`), and it is **not part of a longer number** (`1.5`
does not match inside `21.55`, `1.52` or `1.5.2`) and, for a negative number, the minus sign is present.

**K2 passes** when at least **2 different** meaningful numbers of the run occur in the paper's text **and** at least one of them
occurs on a page that has a line starting with `Table <n>` (the table pages are those that count for S5). For each number found, the
page numbers (1-based) and the line of the paper around the match are stored together with the line of the run output.

A candidate that passes K2 is called a **match candidate**. A chance match is possible, mostly for numbers with few digits; K2 does
not exclude it, and a match candidate is **not** called verified. Whether a number of the output is the number of the paper's table
is decided by a person, from the stored page and line.

## 6. When the search stops

The search stops at the first of these:

- **(a)** 9 hours have passed since the start of the run (the start is written to `sabah_bekleyenler.md`);
- **(b)** 150 candidates have been run in the sandbox;
- **(c)** 8 candidates have passed both K1 and K2;
- **(d)** the free disk space is under 30 GB.

A pool that is used up is not a stop condition: the queries of the next stage (section 2) are added and the search goes on. The search
is **resumable**: the candidates that were already run are read from the stored records and skipped, so that a restarted session or
background run continues where it stopped. The reason for the stop is stored in the evaluation file.

## 7. Records

For each run candidate, `data/auto_search3/runs/<id>/` keeps `run_report.json`, the K1 and K2 result file, and short logs (long
outputs are truncated; local paths are replaced by `<REPO>` and `<HOME>`). `data/auto_search3/evaluation.json` holds every checked
candidate with its first failed rule or its run result. Records of earlier rounds are not touched.

## 8. Reporting

The report names, from a script and from the stored files only: the number of candidates tried (run in the sandbox), the number that
passed K1, the number that passed K2 and the number that passed both; the Wilson 95% interval for each proportion, computed by the
script; a table of the failure categories; and, for every match candidate, the command, the duration and the matching numbers with
their pages. No number is typed by hand.

## 9. Limits that are known before the first search

- **This is a selected and non-representative list, not a success rate.** The pool is what GitHub's search returns for these topics
  with `arxiv.org` in the README, small, and without a GPU mention; the order is a hash; the rules reject most repositories. The
  shares of candidates that pass K1 or K2 are properties of these rules and this pool, never the reproducibility of a field. The
  Wilson intervals describe only the candidates that were run.
- K1 selects for code that runs in 10 minutes as written. A paper that fails may be reproducible with a correction; this round says
  nothing about that.
- The first `python` line of a README may be a data preparation step, a demo or a help text. A pass shows that the command ran and
  printed numbers, not that the paper's main result is reproduced.
- K2 is a string match. It can match by chance, it can miss a value printed in another spelling (a different number of decimals, a
  percentage, a rounded value), and it does not know what a number means. A K2 pass is therefore a reason for a human to look, not
  evidence.
- Simulated or synthetic data in a run's output (for example a setup parameter) is labelled as simulation wherever it is reported.
- No claim is accepted by this round.

## 10. Results

Run of 2026-10-25 (issues #469, #471, #473). The search started at 2026-10-24 23:59 +03:00 and applied this protocol to the pools of
stages 1 to 7. The tables below are generated (`python scripts/auto_search3.py report`) from `data/auto_search3/evaluation.json` and the
run folders; the notes after them are written by hand from them.

<!-- results:start -->
Generated by `scripts/auto_search3.py report` from `data/auto_search3/evaluation.json` (written 2026-10-25T05:40:13+00:00, search started 2026-10-24T20:59:14+00:00) and `data/auto_search3/runs/`; do not edit by hand. The search stopped because: `pool_used_up`.

**This is a selected, non-representative list. The shares below describe only the candidates that were run, under these rules and this pool. They are not a success rate and not the reproducibility of any field. A K2 pass is a match candidate (a string match), not a verified result.**

### Results 1: What was tried

- Candidates checked against S1 to S6: 3399.
- Candidates that passed S1 to S6 and were run once in the sandbox (tried): 135.
- Passed K1: 2 of 135 (Wilson 95%: 0.4 % - 5.2 %).
- Passed K2: 0 of 135 (Wilson 95%: 0.0 % - 2.8 %); K2 was computed for 7 runs that completed with exit code 0.
- Passed both K1 and K2: 0 of 135 (Wilson 95%: 0.0 % - 2.8 %).

First failed static rule of the checked candidates:

| Rule | Candidates |
|---|---|
| S1 | 1313 |
| S2 | 1536 |
| S3 | 306 |
| S4 | 5 |
| S5 | 99 |
| S6 | 5 |

Outcome of the run test K1 (failure reasons):

| Outcome | Candidates |
|---|---|
| install | 27 |
| no_metric_line | 5 |
| passed K1 | 2 |
| run | 101 |

### Results 2: Every run

| Id | Repository | Command | Install | Run | Exit | Seconds | K1 | K2 | Deciding log line |
|---|---|---|---|---|---|---|---|---|---|
| a3_001 | `joisino/pretender` | `python plot.py` | SKIPPED | FAILED | 1 | 0.507 | run | - | `ModuleNotFoundError: No module named 'matplotlib'` |
| a3_002 | `joisino/private-recsys` | `python evaluate.py --data 100k --prov cosine --sensitive popularity` | INSTALLED | FAILED | 1 | 2.303 | run | - | `ImportError: libgomp.so.1: cannot open shared object file: No such file or directory` |
| a3_003 | `microsoft/delegate52` | `python run_relay.py --model_names gpt-5.4 --domains subtitles --num_round_trips 10` | FAILED | FAILED | 1 | 0.619 | install | - | `ERROR: No matching distribution found for srt` |
| a3_004 | `AragornBFRer/mdcp` | `python notebook/eval_linear.py --num-trials 1 --base-seed 34567` | FAILED | FAILED | 1 | 0.849 | install | - | `ERROR: No matching distribution found for torch-scatter` |
| a3_005 | `BrendanJamesLynskey/Torch_Sim_Frontend` | `python examples/results.py` | SKIPPED | FAILED | 1 | 0.63 | run | - | `ModuleNotFoundError: No module named 'onnx'` |
| a3_006 | `joisino/twinpaper` | `python assumptions.py` | INSTALLED | FAILED | 1 | 3.061 | run | - | `FileNotFoundError: [Errno 2] No such file or directory: 'twin_ids.pickle'` |
| a3_007 | `ahmedanees-m/bio-firewall` | `python examples/demo.py` | SKIPPED | FAILED | 1 | 0.819 | run | - | `ModuleNotFoundError: No module named 'yaml'` |
| a3_008 | `rezaakb/pinns-tf2` | `python examples/navier_stokes/train.py` | FAILED | FAILED | 1 | 0.54 | install | - | `ERROR: No matching distribution found for nvidia-cublas-cu11` |
| a3_009 | `TomLee0122/Mean_ConTest` | `python examples/demo.py` | SKIPPED | FAILED | 1 | 0.697 | run | - | `ModuleNotFoundError: No module named 'mean_contest'` |
| a3_010 | `farukalpay/PSD` | `python experiments.py` | INSTALLED | FAILED | 1 | 1.194 | run | - | `OSError: [Errno 30] Read-only file system: '/workspace/repo/results/dimension_scaling.csv'` |
| a3_011 | `semitable/robotic-warehouse` | `python human_play.py --env <env_name>` | SKIPPED | FAILED | 1 | 0.696 | run | - | `ModuleNotFoundError: No module named 'gymnasium'` |
| a3_012 | `pkluber/Chat-bot-Evaluation-Project` | `python roll.py sample_questions` | SKIPPED | FAILED | 1 | 0.716 | run | - | `FileNotFoundError: [Errno 2] No such file or directory: 'class.txt'` |
| a3_013 | `joisino/consul` | `python LOE_adult.py` | FAILED | FAILED | 1 | 0.499 | install | - | `ERROR: No matching distribution found for implicit==0.4.8` |
| a3_014 | `DouniaLakhmiri/SR2` | `python main.py --reg=l0 --precond=andrei --beta=0.95 --lam=0.001` | SKIPPED | FAILED | 1 | 0.708 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_015 | `ahmedbesbes/character-based-cnn` | `python train.py --data_path=/data/tweets.csv --max_rows=200000` | SKIPPED | FAILED | 1 | 0.607 | run | - | `ModuleNotFoundError: No module named 'tqdm'` |
| a3_016 | `XiaoyangCao1113/LiRA` | `python scripts/train_citylearn.py --config configs/citylearn.yaml --output-dir runs/citylearn` | SKIPPED | FAILED | 1 | 0.551 | run | - | `ModuleNotFoundError: No module named 'yaml'` |
| a3_017 | `ziyuey/ReasonCast` | `python scripts/text_fusion/grpo/train_stage1_grpo.py --help` | SKIPPED | FAILED | 1 | 0.739 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_018 | `ssydasheng/Neural-Kernel-Network` | `python exp/time-series.py --name airline --kern nkn` | SKIPPED | FAILED | 1 | 0.764 | run | - | `ModuleNotFoundError: No module named 'matplotlib'` |
| a3_019 | `apple-aiml-research/ml-mkqa` | `python mkqa_eval.py --annotation_file ./dataset/mkqa.jsonl.gz --predictions_file ./sample_predictions/en.jsonl --language en (--out_dir <optional output directory for saving metrics and pr curves>, --verbose)` | INSTALLED | FAILED | 2 | 2.936 | run | - | `Official evaluation script for single language MKQA.: error: unrecognized arguments: (--out_dir <optional output directory for saving metrics and pr curves>, --verbose)` |
| a3_020 | `programasweights/claudish` | `python translate.py to-claudish "The release can go out after Alice approves the final report."` | FAILED | FAILED | 1 | 0.464 | install | - | `ERROR: No matching distribution found for httpx<1.0,>=0.27.0` |
| a3_021 | `cranesun1226/ttm-btcusdt-research` | `python trader/bt_trader.py --model saved_models/highest_accuracy/model.pth --duration 10` | FAILED | FAILED | 1 | 1.188 | install | - | `ERROR: No matching distribution found for tsfm-public>=0.1.0` |
| a3_022 | `HarimxChoi/ensemble-bid-prediction` | `python train_cluster_models.py` | INSTALLED | FAILED | 1 | 3.922 | run | - | `ModuleNotFoundError: No module named 'xgboost'` |
| a3_023 | `YerevaNN/DIIN-in-Keras` | `python preprocess.py --p 32 --h 32 --chars_per_word 16 --save_dir data/ --dataset snli --word_vec_save_path data/word-vectors.npy` | INSTALLED | FAILED | 1 | 1.757 | run | - | `ModuleNotFoundError: No module named 'tensorflow'` |
| a3_024 | `jadore801120/attention-is-all-you-need-pytorch` | `python preprocess.py -lang_src de -lang_trg en -share_vocab -save_data m30k_deen_shr.pkl` | FAILED | FAILED | 1 | 0.545 | install | - | `ERROR: No matching distribution found for msgpack-python==1.0.2` |
| a3_025 | `jacobjinkelly/easy-neural-ode` | `python mnist.py --reg r3 --lam 6e-5` | SKIPPED | FAILED | 1 | 0.528 | run | - | `ModuleNotFoundError: No module named 'haiku'` |
| a3_026 | `EverMind-AI/SkillCorpus` | `python examples/skillhub_demo.py "extract tables from a scanned PDF invoice"` | INSTALLED | FAILED | 1 | 0.707 | run | - | `Override with:  export SKILLHUB_URL=https://your-host` |
| a3_027 | `KAVentures/clinical-evidence-sufficiency-llm` | `python analysis/power_simulation.py --n-items 200 --n-models 4 --n-perturbations 4 --n-sims 200` | INSTALLED | FAILED | 1 | 3.747 | run | - | `OverflowError: int too large to convert to float` |
| a3_028 | `Howuhh/prioritized_experience_replay` | `python train.py --seeds 10 CartPole-v0` | INSTALLED | FAILED | 1 | 36.139 | run | - | `RuntimeError: [enforce fail at inline_container.cc:747] . open file failed with strerror: Read-only file system` |
| a3_029 | `IC3Net/IC3Net` | `python main.py --env_name predator_prey --nagents 3 --nprocesses 16 --num_epochs 2000 --hid_size 128 --detach_gap 10 --lrate 0.001 --dim 5 --max_steps 20 --ic3net --vision 0 --recurrent` | SKIPPED | FAILED | 1 | 0.747 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_030 | `WXinlong/ASIS` | `python collect_indoor3d_data.py` | SKIPPED | FAILED | 1 | 0.673 | run | - | `OSError: [Errno 30] Read-only file system: '/workspace/repo/data/stanford_indoor3d_ins.sem'` |
| a3_031 | `imlrz/DeepResearch-Bench-II` | `python run_evaluation.py` | SKIPPED | FAILED | 1 | 0.617 | run | - | `ModuleNotFoundError: No module named 'requests'` |
| a3_032 | `htmoges/Lite-STGNN` | `python src/lite_stgnn_modular.py --dataset electricity --data-root ./data --seq-len 96 --pred-len 720 --epochs 50 --learning-rate 5e-4 --adj-rank 16 --adj-topk 10 --adj-tau 1.2 --use-input-residual --use-temporal-head --temporal-head-ratio 0.5 --residual-dropout 0.1 --gate-mode band --prop-orders 2` | INSTALLED | FAILED | 1 | 40.904 | run | - | `FileNotFoundError: [Errno 2] No such file or directory: './data/electricity.csv'` |
| a3_033 | `rzhub/GateMem` | `python bench/scripts/run_eval.py --data_dir bench/data/medical --agent long_context` | INSTALLED | FAILED | 1 | 7.244 | run | - | `OSError: [Errno 30] Read-only file system: 'outputs'` |
| a3_034 | `yuyangw/iMolCLR` | `python imolclr.py` | SKIPPED | FAILED | 1 | 0.489 | run | - | `ModuleNotFoundError: No module named 'yaml'` |
| a3_035 | `lucidrains/rectified-flow-pytorch` | `python train_oxford.py` | SKIPPED | FAILED | 1 | 0.464 | run | - | `ModuleNotFoundError: No module named 'fire'` |
| a3_036 | `canturan10/satellighte` | `python training/eurosat_training.py` | FAILED | FAILED | 1 | 0.542 | install | - | `ERROR: No matching distribution found for fire~=0.5.0` |
| a3_037 | `lucidrains/En-transformer` | `python denoise.py` | SKIPPED | FAILED | 1 | 0.468 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_038 | `lucidrains/x-transformers-rl` | `python train_lander.py` | SKIPPED | FAILED | 1 | 0.476 | run | - | `ModuleNotFoundError: No module named 'gymnasium'` |
| a3_039 | `lucidrains/x-ppo` | `python train.py` | FAILED | FAILED | 1 | 0.518 | install | - | `ERROR: No matching distribution found for box2d-py` |
| a3_040 | `Karim-53/pdll` | `python run_benchmark.py --model DecisionTreeClassifier --data 0` | FAILED | FAILED | 1 | 0.879 | install | - | `ERROR: No matching distribution found for openml~=0.14.2` |
| a3_041 | `QwQ2000/WSDM26-Graph-Unlearning-Inversion` | `python main.py --dataset_name cora --target_model=GCN --exp Inversion --method GIF --unlearn_ratio 0.05 --attack_method=trend_steal --num_runs=5 --is_gen_unlearn_request=True --is_gen_unlearned_probs=True` | SKIPPED | FAILED | 1 | 0.516 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_042 | `Karl1109/SCSegamba` | `python main.py` | SKIPPED | FAILED | 1 | 0.725 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_043 | `cmavro/ReaRev_KGQA` | `python main.py ReaRev --entity_dim 50 --num_epoch 200 --batch_size 8 --eval_every 2 --data_folder data/webqsp/ --lm sbert --num_iter 3 --num_ins 2 --num_gnn 2 --relation_word_emb True --experiment_name Webqsp322 --name webqsp` | FAILED | FAILED | 1 | 0.55 | install | - | `ERROR: No matching distribution found for Base==1.0.4` |
| a3_044 | `tianyi-lab/HallusionBench` | `python evaluation.py` | SKIPPED | FAILED | 1 | 0.5 | run | - | `ModuleNotFoundError: No module named 'tqdm'` |
| a3_045 | `PolyAI-LDN/conversational-datasets` | `python tools/tfrutil.py size data/reddit-test` | FAILED | FAILED | 1 | 0.487 | install | - | `ERROR: No matching distribution found for absl-py==0.7.0` |
| a3_046 | `rspence821505/Data-Consistent-Filtering` | `python scripts/reproduce_figures.py --compare` | INSTALLED | FAILED | 1 | 1.111 | run | - | `ModuleNotFoundError: No module named 'pyparsing'` |
| a3_047 | `una-dinosauria/human-motion-prediction` | `python src/translate.py --action walking --seq_length_out 25 --iterations 10000` | SKIPPED | FAILED | 1 | 0.466 | run | - | `ModuleNotFoundError: No module named 'h5py'` |
| a3_048 | `etaoxing/multigame-dt` | `python scripts/download_weights.py` | FAILED | FAILED | 1 | 0.527 | install | - | `ERROR: No matching distribution found for gym==0.25.2` |
| a3_049 | `takuseno/ppo` | `python train.py [--env env-id] [--render] [--logdir log-name]` | SKIPPED | FAILED | 1 | 0.514 | run | - | `ModuleNotFoundError: No module named 'cv2'` |
| a3_050 | `Commonwealth-Bank-of-Australia/PSAO-IJCAI-release` | `python app.py --config gpt4o/psaollm_5sent.yaml --verbose` | INSTALLED | FAILED | 1 | 15.996 | run | - | `OSError: [Errno 30] Read-only file system: 'output'` |
| a3_051 | `tomekkorbak/pretraining-with-human-feedback` | `python train.py --task configs/toxicity/pretrain.yml --method configs/toxicity/mle.yml` | FAILED | FAILED | 1 | 0.537 | install | - | `ERROR: No matching distribution found for aiohttp==3.8.1` |
| a3_052 | `saurabhsharma1993/generative_pose` | `python main.py --exp [name of your experiment]` | SKIPPED | FAILED | 1 | 0.463 | run | - | `SyntaxError: invalid syntax` |
| a3_053 | `turingmotors/ACT-Bench` | `python run_benchmark.py --input_dir generated_videos/<your_model_name> --output_dir results/<your_model_name>` | SKIPPED | FAILED | 1 | 0.454 | run | - | `ModuleNotFoundError: No module named 'transformers'` |
| a3_054 | `gepavlou/fitPALSpectra` | `python scripts/run_fit.py` | INSTALLED | FAILED | 1 | 70.334 | run | - | `OSError: [Errno 30] Read-only file system: '/workspace/repo/outputs/simulated_spectrum_W_20261024_233917'` |
| a3_055 | `KuaishouGameMind/TRACE-Bench` | `python main.py --config config.yaml validate-config` | INSTALLED | FAILED | 1 | 24.083 | run | - | `FileNotFoundError: [Errno 2] No such file or directory: '/workspace/repo/config.yaml'` |
| a3_056 | `yuyangw/MolCLR` | `python molclr.py` | SKIPPED | FAILED | 1 | 0.515 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_057 | `ByteDance-BandAI/ReportBench` | `python openai_processor.py --input=captured_data_dir --output=parsed_output_dir --markdown` | INSTALLED | FAILED | 1 | 0.734 | run | - | `OSError: [Errno 30] Read-only file system: 'logs'` |
| a3_058 | `wanng-ide/open-paper-analysis` | `python scripts/check_markdown_links.py` | SKIPPED | COMPLETED | 0 | 1.793 | no_metric_line | no | `All local Markdown links resolve` |
| a3_059 | `liyuqin606-del/RhetoricShield` | `python rhetoric-shield/scripts/preservation_check.py ORIGINAL REVISED` | SKIPPED | FAILED | 2 | 0.606 | run | - | `error: path does not exist: ORIGINAL` |
| a3_060 | `amazon-science/Self-Evolving-Agents-Double-Ratchet` | `python scripts/screen_mbpp.py baseline && python scripts/screen_mbpp.py subset` | SKIPPED | FAILED | 2 | 0.74 | run | - | `screen_mbpp.py: error: unrecognized arguments: && python scripts/screen_mbpp.py subset` |
| a3_061 | `alloevil/AI-Paper-Daily` | `python scripts/main.py` | INSTALLED | COMPLETED | 0 | 0.94 | no_metric_line | no | `No papers found, exiting` |
| a3_062 | `amughalbscs16/http-api-quality-analyzer` | `python analyze.py --anonymize` | SKIPPED | FAILED | 1 | 1.109 | run | - | `ModuleNotFoundError: No module named 'matplotlib'` |
| a3_063 | `ContextualAI/LMUnit` | `python eval/eval.py --task <task> --model-path <lmunit-model> --tensor-parallel-size <tp-size>` | SKIPPED | FAILED | 1 | 0.943 | run | - | `ModuleNotFoundError: No module named 'datasets'` |
| a3_064 | `RUC-NLPIR/WebThinker` | `python scripts/run_web_thinker.py --single_question "What is OpenAI Deep Research?" --search_engine "serper" --serper_api_key "YOUR_GOOGLE_SERPER_API" --api_base_url "YOUR_API_BASE_URL" --model_name "QwQ-32B" --aux_api_base_url "YOUR_AUX_API_BASE_URL" --aux_model_name "Qwen2.5-32B-Instruct" --tokenizer_path "PATH_TO_YOUR_TOKENIZER" --aux_tokenizer_path "PATH_TO_YOUR_AUX_TOKENIZER"` | FAILED | FAILED | 1 | 0.541 | install | - | `ERROR: No matching distribution found for pyext==0.7` |
| a3_065 | `ryuryukke/MINT` | `python run.py --task mia --domain arxiv --methods all --model_name pythia-160m` | INSTALLED | FAILED | 1 | 3.933 | run | - | `ImportError: pyarrow requires NumPy 2.0 or newer, found 1.25.2` |
| a3_066 | `sail-sg/rosmo` | `python experiment/bsuite/main.py -exp_id test -env cartpole` | SKIPPED | FAILED | 1 | 0.538 | run | - | `ModuleNotFoundError: No module named 'jax'` |
| a3_067 | `AndyChiangSH/BADGE` | `python code/data/CSV+QA.py` | INSTALLED | FAILED | 1 | 6.546 | run | - | `OSError: [Errno 30] Read-only file system: 'CSV/Viktor_Axelsen_Ng_Ka_Long_Angus_YONEX_Thailand_Open_2021_Finals/set1.csv'` |
| a3_068 | `Ganesh-403/image-colorization-project` | `python download_models.py` | INSTALLED | FAILED | 1 | 1.322 | run | - | `ImportError: libxcb.so.1: cannot open shared object file: No such file or directory` |
| a3_069 | `fangz-cs/ClarifyCodeBench` | `python scripts/run_eval.py --data data/ClarifyCodeBench.jsonl --model gpt-4o --out results/gpt-4o.jsonl` | INSTALLED | FAILED | 1 | 5.693 | run | - | `RuntimeError: No API key. Set CLARIFY_API_KEY (and CLARIFY_BASE_URL) or pass api_key=.` |
| a3_070 | `yonatantussa/chainofexperience` | `python agent/run_agent.py` | SKIPPED | FAILED | 1 | 0.724 | run | - | `ModuleNotFoundError: No module named 'playwright'` |
| a3_071 | `ibaiGorordo/PyTorch-High-Res-Stereo-Depth-Estimation` | `python imageDepthEstimation.py` | FAILED | FAILED | 1 | 0.478 | install | - | `ERROR: No matching distribution found for imread-from-url` |
| a3_072 | `Lornatang/CARN-PyTorch` | `python ./inference.py --inputs_path ./figure/comic_lr.png --output_path ./figure/comic_sr.png --weights_path ./results/pretrained_models/CARN_x2-DIV2K-4797e51b.pth.tar` | INSTALLED | FAILED | 1 | 1.267 | run | - | `ImportError: libxcb.so.1: cannot open shared object file: No such file or directory` |
| a3_073 | `weich97/TreLLM-public` | `python scripts/calibrate_execution_model.py --data-dir data/real/yahoo_intraday_1h_50` | SKIPPED | FAILED | 1 | 0.528 | run | - | `ModuleNotFoundError: No module named 'tradearena'` |
| a3_074 | `xmpuspus/agent-memory-testbench` | `python scripts/aggregate_bootstrap.py` | SKIPPED | FAILED | 1 | 1.112 | run | - | `OSError: [Errno 30] Read-only file system: '/workspace/repo/results/longmemeval-s_amem_summary.json'` |
| a3_075 | `najmulhasan-code/dpbench` | `python experiments/scripts/run.py` | FAILED | FAILED | 1 | 0.594 | install | - | `ERROR: No matching distribution found for langgraph-checkpoint<4.0.0,>=2.1.0` |
| a3_076 | `SalesforceAIResearch/Beagle` | `python scripts/generate_eval_configs.py` | SKIPPED | FAILED | 1 | 0.601 | run | - | `ModuleNotFoundError: No module named 'yaml'` |
| a3_077 | `shayme92/Titans-NNX` | `python training/train_mac.py --config configs/mac.yaml --train_path /path/to/train/data --val_path /path/to/val/data` | INSTALLED | FAILED | 2 | 7.434 | run | - | `train_mac.py: error: unrecognized arguments: --train_path /path/to/train/data --val_path /path/to/val/data` |
| a3_078 | `schmittsfn/swissfin-bench` | `python app.py input tasks/swissfin_public_sample_v0_1.yaml` | SKIPPED | FAILED | 1 | 1.162 | run | - | `ModuleNotFoundError: No module named 'yaml'` |
| a3_079 | `xirui-li/ClawEnvKit` | `python scripts/generate_dataset.py --multiplier 10` | SKIPPED | FAILED | 1 | 0.498 | run | - | `ModuleNotFoundError: No module named 'yaml'` |
| a3_080 | `AutoResearch-Factory/SciPIvot` | `python scripts/make_prompt.py --id case_000 --condition project --order ab` | SKIPPED | COMPLETED | 0 | 0.575 | no_metric_line | no | `- Only read the contents of `/project`. Do not go to parent directories. Do not access the network.` |
| a3_081 | `gagazzotti/Bilateral-GIG` | `python main.py` | INSTALLED | FAILED | 1 | 7.482 | run | - | `RuntimeError: Failed to process string with tex because latex could not be found` |
| a3_082 | `isaacus-dev/legal-rag-bench` | `python db.py` | INSTALLED | FAILED | 1 | 21.608 | run | - | `ValueError: ISAACUS_API_KEY not set in .env` |
| a3_083 | `Ractorrr/arxiv-mcp` | `python arxiv_tool.py search "LLM jailbreaking" --max 10` | INSTALLED | FAILED | 1 | 1.98 | run | - | `requests.exceptions.ConnectionError: HTTPSConnectionPool(host='export.arxiv.org', port=443): Max retries exceeded with url: /api/query?search_query=LLM+jailbreaking&id_list=&sortBy=relevance&sortOrder=descending&start=0&max_results=100 (Caused by NameResolutionError("HTTPSConnection(host='export.arx` |
| a3_084 | `zjunlp/AutoSciRub` | `python scripts/install.py codex` | INSTALLED | COMPLETED | 0 | 1.654 | no_metric_line | no | `Note: codex is not on PATH; install or open that agent before using the skills.` |
| a3_085 | `The-Swarm-Corporation/AgentRearrange-Paper` | `python examples/01_minimal_sequential.py` | SKIPPED | FAILED | 1 | 0.455 | run | - | `ModuleNotFoundError: No module named 'swarms'` |
| a3_086 | `kuff/vibescholar` | `python server.py --transport streamable-http --host 127.0.0.1 --port 8765` | SKIPPED | FAILED | 1 | 0.522 | run | - | `ModuleNotFoundError: No module named 'mcp'` |
| a3_087 | `dissensus-ai/asri` | `python scripts/event_study_hac.py` | SKIPPED | FAILED | 1 | 1.003 | run | - | `ModuleNotFoundError: No module named 'statsmodels'` |
| a3_088 | `sanbuphy/SmartPaper` | `python cli_get_prompt_mode_paper.py https://arxiv.org/pdf/2312.12456.pdf` | INSTALLED | FAILED | 1 | 0.839 | run | - | `ModuleNotFoundError: No module named 'core'` |
| a3_089 | `AlphaPav/mem-kk-logic` | `python data_prep/data_gen_kk.py` | INSTALLED | FAILED | 1 | 21.153 | run | - | `OSError: [Errno 30] Read-only file system: 'data'` |
| a3_090 | `qinyao-he/bit-rnn` | `python train.py --config=config.gru --data_path=YOUR_DATA_PATH` | SKIPPED | FAILED | 1 | 0.703 | run | - | `ModuleNotFoundError: No module named 'tensorflow'` |
| a3_091 | `minitap-ai/mobile-use` | `python ./minitap/mobile_use/main.py "Go to settings and tell me my current battery level"` | SKIPPED | FAILED | 1 | 0.698 | run | - | `ModuleNotFoundError: No module named 'typer'` |
| a3_092 | `narumiruna/efficientnet-pytorch` | `python train.py -c /path/to/config` | SKIPPED | FAILED | 1 | 0.489 | run | - | `ModuleNotFoundError: No module named 'mlconfig'` |
| a3_093 | `alvinwan/neural-backed-decision-trees` | `python main.py --lr=0.01 --dataset=CIFAR10 --arch=wrn28_10_cifar10 --hierarchy=induced-wrn28_10_cifar10 --pretrained --loss=SoftTreeSupLoss` | FAILED | FAILED | 1 | 0.757 | install | - | `ERROR: No matching distribution found for torch==1.6.0` |
| a3_094 | `atalbanese/NEON_Hyperspectral` | `python site_pca.py SITENAME DATA_DIRECTORY` | SKIPPED | FAILED | 1 | 2.031 | run | - | `ModuleNotFoundError: No module named 'einops'` |
| a3_095 | `wanyichen06/HSPR` | `python example.py` | INSTALLED | COMPLETED | 0 | 4.212 | passed | no | `` |
| a3_096 | `fless-lab/rsi-framework` | `python experiments/togo-fiscal/run.py` | INSTALLED | COMPLETED | 0 | 28.231 | passed | no | `` |
| a3_097 | `TheDeadcoder/paired-rollouts` | `python scripts/verify_run.py outputs/runs/<run_id>` | SKIPPED | FAILED | 1 | 0.505 | run | - | `ModuleNotFoundError: No module named 'pairedrl'` |
| a3_098 | `jwmao1/MedSegFactory` | `python tutorial_train.py --data_root_path [your data path] --output_dir [your output path]` | INSTALLED | FAILED | 2 | 43.359 | run | - | `tutorial_train.py: error: unrecognized arguments: data path] output path]` |
| a3_099 | `gentlyzhao/Hijacking` | `python main.py --target-model claude-4-sonnet` | FAILED | FAILED | 1 | 0.537 | install | - | `ERROR: No matching distribution found for anyio<5,>=3.5.0` |
| a3_100 | `yunjey/stargan` | `python main.py --mode train --dataset CelebA --image_size 128 --c_dim 5 --sample_dir stargan_celeba/samples --log_dir stargan_celeba/logs --model_save_dir stargan_celeba/models --result_dir stargan_celeba/results --selected_attrs Black_Hair Blond_Hair Brown_Hair Male Young` | SKIPPED | FAILED | 1 | 0.557 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_101 | `bramgrooten/automatic-noise-filtering` | `python main.py --policy ANF-SAC --env HalfCheetah-v3 --fake_features 0.9 --input_layer_sparsity 0.8 --wandb_mode disabled` | SKIPPED | FAILED | 1 | 0.655 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_102 | `deep-spin/sparse-marginalization-lvm` | `python  experiments/semi_supervised-vae/train.py --n_epochs 100 --lr 1e-3 --labeled_only --normalizer sparsemax --batch_size 64` | FAILED | FAILED | 1 | 0.534 | install | - | `ERROR: No matching distribution found for torch==1.6.0` |
| a3_103 | `skhanzad/snakeAi` | `python main.py` | INSTALLED | COMPLETED | 0 | 27.91 | no_metric_line | no | `Game 1 Score 0 Record: 0` |
| a3_104 | `xlnwel/grl` | `python run/train.py algo -e env` | SKIPPED | FAILED | 1 | 0.741 | run | - | `ModuleNotFoundError: No module named 'yaml'` |
| a3_105 | `LvCheng09/Reasoning-AI-demo-v0.1` | `python demo.py --preset dso` | SKIPPED | FAILED | 1 | 1.548 | run | - | `RuntimeError: missing required environment variables: LLM_BASE_URL, LLM_API_KEY` |
| a3_106 | `lazaratan/meta-flow-matching` | `python train.py experiment=experiment_name.yaml` | FAILED | FAILED | 1 | 0.449 | install | - | `ERROR: No matching distribution found for torch-cluster==1.6.3` |
| a3_107 | `skirdey/voicerestore` | `python inference_short.py --checkpoint ./checkpoints/voicerestore-1.1.pth --input test_input.wav --output test_output.wav --steps 32 --cfg_strength 0.5` | INSTALLED | FAILED | 1 | 13.015 | run | - | `ImportError: cannot import name 'bigvgan' from 'BigVGAN' (unknown location)` |
| a3_108 | `philipperemy/tensorflow-maxout` | `python mnist_maxout_example.py MAXOUT` | SKIPPED | FAILED | 1 | 0.44 | run | - | `ModuleNotFoundError: No module named 'tensorflow'` |
| a3_109 | `ibaiGorordo/HITNET-Stereo-Depth-estimation` | `python imageDepthEstimation.py` | FAILED | FAILED | 1 | 0.452 | install | - | `ERROR: No matching distribution found for imread-from-url` |
| a3_110 | `Wilmido/HEA4ORR` | `python K_fold.py` | FAILED | FAILED | 1 | 0.488 | install | - | `^ (from line 1 of /workspace/repo/requirements.txt)` |
| a3_111 | `nicklashansen/adaptive-learning-rate-schedule` | `python train.py --dataset cifar10 --architecture resnet` | SKIPPED | FAILED | 1 | 0.735 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_112 | `jjoeysu/cocp` | `python scripts/run_experiment.py --config configs/synth1d.yaml` | INSTALLED | FAILED | 1 | 24.344 | run | - | `OSError: [Errno 30] Read-only file system: 'results'` |
| a3_113 | `betterCallSherlock/CPR` | `python run.py --config configs/webqsp.yaml --puct_calib --alpha 0.5 --out_json results/webqsp_a05.json` | INSTALLED | FAILED | 2 | 67.971 | run | - | `run.py: error: unrecognized arguments: --config configs/webqsp.yaml` |
| a3_114 | `joisino/wordtour` | `python generate_order_file.py` | INSTALLED | FAILED | 1 | 6.039 | run | - | `FileNotFoundError: [Errno 2] No such file or directory: 'LKH-3.0.6/wordtour.out'` |
| a3_115 | `cfinlay/confident-nn` | `python eval_model.py /path/to/data/dir/ --model resnet152 --dataset imagenet` | SKIPPED | FAILED | 1 | 0.943 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_116 | `darkrockmountain/spacy-ewc` | `python examples/ewc_ner_training_example.py` | SKIPPED | FAILED | 1 | 0.468 | run | - | `ModuleNotFoundError: No module named 'spacy'` |
| a3_117 | `kaiyinzhou/BERT-NER` | `python BERT_NER.py --task_name="NER" --do_lower_case=False --crf=False --do_train=True --do_eval=True --do_predict=True --data_dir=data --vocab_file=cased_L-12_H-768_A-12/vocab.txt --bert_config_file=cased_L-12_H-768_A-12/bert_config.json --init_checkpoint=cased_L-12_H-768_A-12/bert_model.ckpt --max_seq_length=128 --train_batch_size=32 --learning_rate=2e-5 --num_train_epochs=3.0 --output_dir=./output/result_dir` | SKIPPED | FAILED | 1 | 0.484 | run | - | `ModuleNotFoundError: No module named 'absl'` |
| a3_118 | `danielegrattarola/ccm-aae` | `python src/mnist.py` | SKIPPED | FAILED | 1 | 0.666 | run | - | `ModuleNotFoundError: No module named 'keras'` |
| a3_119 | `New-Ground-AI/CARE` | `python python/build_mimic_db.py` | INSTALLED | FAILED | 1 | 1.215 | run | - | `OSError: [Errno 30] Read-only file system: '/workspace/repo/data'` |
| a3_120 | `Garfield-kh/FastVLA` | `python scripts/serve.py --model checkpoints/fastvla-robotwin --port 8765` | INSTALLED | FAILED | 1 | 1.185 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_121 | `ToFec/AtlasRegistration` | `python ./code/TrainAtlas.py -c ./Path/to/your/config/file.json` | INSTALLED | FAILED | 1 | 24.523 | run | - | `ModuleNotFoundError: No module named 'matplotlib'` |
| a3_122 | `RolnickLab/constrained-downscaling` | `python main.py --dataset era5_sr_data --model cnn --model_id twc_cnn_noconstraints --constraints none` | SKIPPED | FAILED | 1 | 0.48 | run | - | `ModuleNotFoundError: No module named 'torch'` |
| a3_123 | `RVScoder/VQA` | `python train.py` | INSTALLED | FAILED | 1 | 15.338 | run | - | `ModuleNotFoundError: No module named 'answer_transforms'` |
| a3_124 | `etetteh/OoD_Gen-Chest_Xray` | `python chest_quantize.py --dataset_dir <data dir> --train_datas cx pc --val_data mc --seed 0` | FAILED | FAILED | 1 | 0.449 | install | - | `ERROR: No matching distribution found for markupsafe==2.1.1` |
| a3_125 | `Guowei-Zou/d2ppo-release` | `python script/run.py --config-name=ft_ppo_diffusion_mlp_img --config-dir=cfg/robomimic/finetune/can/ wandb=null` | SKIPPED | FAILED | 1 | 0.445 | run | - | `ModuleNotFoundError: No module named 'pretty_errors'` |
| a3_126 | `stmharry/dental-pano-ai` | `python main.py` | SKIPPED | FAILED | 1 | 1.085 | run | - | `ModuleNotFoundError: No module named 'absl'` |
| a3_127 | `AnqiLi24/OpenTumorBoard` | `python src/search.py` | INSTALLED | FAILED | 1 | 1.883 | run | - | `OSError: [Errno 30] Read-only file system: 'searched_videos.csv'` |
| a3_128 | `rishikksh20/iSTFT-Avocodo-pytorch` | `python train.py --config config_v1.json` | FAILED | FAILED | 1 | 0.528 | install | - | `ERROR: No matching distribution found for numpy==1.17.4` |
| a3_129 | `dakebone/identifier-deference-probe` | `python probe/build_tasks.py` | SKIPPED | FAILED | 1 | 0.629 | run | - | `urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>` |
| a3_130 | `lucidrains/blackbox-gradient-sensing` | `python train.py` | FAILED | FAILED | 1 | 0.45 | install | - | `ERROR: No matching distribution found for box2d-py` |
| a3_131 | `StefanDenn3r/Spatio-temporal-MS-Lesion-Segmentation` | `python train.py --resume path/to/checkpoint` | FAILED | FAILED | 1 | 0.656 | install | - | `ERROR: No matching distribution found for future==0.18.2` |
| a3_132 | `yophis/partial-yarn` | `python inference_qwen2_audio_mcqa.py --test-dataset-path <path_to_your_data.json> [OPTIONS]` | INSTALLED | FAILED | 2 | 59.335 | run | - | `inference_qwen2_audio_mcqa.py: error: unrecognized arguments: [OPTIONS]` |
| a3_133 | `radiuma-com/PySERA` | `python radiomics_standalone.py --image-input image.nii.gz --mask-input mask.nii.gz --output ./results` | INSTALLED | FAILED | 1 | 2.817 | run | - | `AttributeError: module 'typing' has no attribute '_ClassVar'. Did you mean: 'ClassVar'?` |
| a3_134 | `J0Jng/own_trading_agants` | `python main.py` | SKIPPED | FAILED | 1 | 0.624 | run | - | `ModuleNotFoundError: No module named 'langchain_core'` |
| a3_135 | `BricksRL/bricksrl` | `python experiments/walker/train.py` | SKIPPED | FAILED | 1 | 0.452 | run | - | `ModuleNotFoundError: No module named 'hydra'` |

### Results 3: Match candidates (K2 passed)

No candidate passed K2.
<!-- results:end -->

Notes (by hand, from the generated part):

- **Why the search ended.** Stage 7 was the last stage used up (`pool_used_up`) at about 08:41, with all 3,399 candidates of the seven
  stages checked and 135 run. This was before the 9-hour limit (08:59) and before the other limits (150 runs, 8 passing both, 30 GB of
  disk). No stage 8 was added because less than 20 minutes were left, so the search ended on a used-up pool and not on a stop condition
  of section 6.
- **The pool needed seven stages.** Stages 1 and 2 are those of section 2; stages 3 to 7 were added to the protocol one at a time, each in
  its own merged pull request before its search and without looking at any candidate (section 2). The stage 6 paragraph names the time
  06:45 but the pull request was made at about 06:30 (corrected in the PROGRESS entry of stage 7). The static rules rejected most
  repositories: the table above shows that the run command rule (S2) and the repository rule (S1) stopped most of them.
- **Two K1 passes, no K2 pass.** `a3_095` (`wanyichen06/HSPR`, `python example.py`) printed one metric line, `Estimated full score: 41.7%`;
  with one meaningful number in the output, K2 could not pass (it needs two different numbers). `a3_096`
  (`fless-lab/rsi-framework`, `python experiments/togo-fiscal/run.py`, 28.2 s) printed 207 distinct meaningful numbers, none of which occurs in
  the text of its paper (0 of 207). Whether the numbers of `a3_096` come from a simulation is **not verified**; the output has lines such as
  `R1_TVA: 0.426 (prior E[c]=0.70)`. K2 was computed for 7 runs (the runs that completed with exit code 0: these two and five that printed no
  metric line). The other runs failed before K2 (section 4).
- **Most failures need help that K1 does not allow.** The causes of the failures are in the table above: the run phase failed most often
  (the README command imports a module that no requirement file names, needs a data file, or writes into the read-only repository), then
  the installation (a package without a wheel for the image). By the protocol, none was repaired or replaced.
- **A crash of the mechanism, fixed (#482).** The search process ended after 76 runs, about 40 minutes before it was noticed, because deleting
  the installed packages of candidate `a3_077` raised an error (a path longer than Windows allows). The cleanup and the handling of a runner
  exception were changed in a separate pull request and the search was started again; `a3_077` had no stored result and was run again from the
  start. The search was also started again after each stage was added (the records of the candidates that had a result were kept).
- **What this does not show.** The shares describe the candidates that were run under these rules and this pool. They are not a success rate
  and not the reproducibility of a field. No candidate is a match candidate, so no claim was extracted for this round and nothing was accepted.
  That the K2 rule would find a real reproduction was not tested on a known positive case in the repository (unit tests only).
