# Automatic search, round 4: the improved match test K2 v2

Date written: 2026-10-27. Issue #515. **This addendum was written after the result of the first round was seen** (round 3,
`docs/AUTO_SEARCH_ROUND3.md`: 135 candidates run, 2 passed K1, none passed K2). It is written and merged **before any candidate of
round 4 has been searched or run**. K2 v1 is not changed and is not replaced: K2 v2 is new and additional, and both results are
stored for every run.

## 1. Why this round exists

In `docs/REAL_VERDICTS.md` section 4, K2 (v1) was tried on three papers where a match was expected (`paper_003`, `paper_006`,
`paper_102`). `paper_006` failed K2 although its run prints a number that the paper prints too: the run writes the AUROC as a
fraction (`0.933`) and the paper writes it as a percent (`93.3`). A string match in the same spelling cannot see this. So v1 may
have missed real matches in round 3. K2 v2 corrects that **known defect**, as a rule written here, and not by looking at the result
of a new search. It is applied together with v1 and the result of v1 stays on record.

This round is **not** a sample of papers and **not** a success rate (section 9). It accepts no claim: accepting a claim is the
owner's decision alone. A candidate that passes K2 v2 is a **match candidate**; it is never called verified.

## 2. What stays the same as round 3

Unchanged, exactly as in `docs/AUTO_SEARCH_ROUND3.md`:

- the static rules S1 to S6 (section 3 there), applied in the hash order, the first failed rule recorded;
- the run test K1 (section 4 there): one run per candidate, exactly as the README says, in the Docker sandbox with `--network none`
  in both phases, `--memory 50%`, `--cpus 4`, install limit 1200 s, run limit 600 s, one sandbox run at a time, no repair and no
  second run;
- K2 v1 (section 5 there): at least 2 different meaningful numbers of `stdout.log` occur in the paper's text in the same spelling and
  at least one of them on a page with a `Table <n>` line;
- the definition of a **meaningful number** (section 5 there): at least 3 significant digits; not a year, a version, a date or a
  time, an index or a line number; numbers are taken from `stdout.log` only.

## 3. K2 v2

For each meaningful number `n` of the run's `stdout.log` (canonical string `s`, as printed, without sign variants, thousands
separators and percent sign), the text of the paper is searched, page by page, for **one of these spellings**, in this order. The
first spelling that is found is stored with the match.

| Variant | Spelling searched | Applies when |
|---|---|---|
| `same` | `s` itself (this is the v1 match) | always |
| `x100` | `s` times 100 as an exact decimal shift (`0.8886` becomes `88.86`; a fraction becomes a percent) | `0 < abs(n) <= 1` |
| `div100` | `s` divided by 100 as an exact decimal shift (`88.86` becomes `0.8886`; a percent becomes a fraction) | `1 < abs(n) <= 100` |
| `<variant>+round3` | the spelling of `same`, `x100` or `div100`, rounded half up to its first 3 significant digits and searched at the same scale (`0.8886` becomes `0.889`, `88.86` becomes `88.9`) | only when the spelling has more than 3 significant digits (otherwise the rounding is the spelling itself) |

Normalisation, in both texts: the minus variants (`-`, the Unicode minus, en dash, non-breaking hyphen) are one minus sign; a
decimal comma is read as a decimal point; a thousands separator (`,`, `'`, a thin or non-breaking space) between digit groups of
three is removed; a leading zero may be dropped (`.5`). A number printed in the output with a decimal comma (`0,8886`) is read as
`0.8886`. A found spelling must not be part of a longer number (`1.5` does not match inside `21.55`, `1.52` or `1.5.2`).

**Excluded** as in v1: a number that is a year, part of a version, a date or a time, an index or a line number is not looked up,
in any variant. Percent signs and sign are removed before the comparison. The number of decimals counts: `0.50` does not match
`0.5`, and a rounded spelling is only the one defined above (no other rounding is tried).

**Guard against a chance match.** A scale conversion or a rounding makes a chance match more likely. So:

1. a match by any variant other than `same` counts only when it is on a page that has a `Table <n>` line (a `same` match counts on
   any page, as in v1);
2. `x100` and `div100` apply only in the ranges of the table (a fraction becomes a percent, a percent becomes a fraction);
3. for every number found, the variant, the page (1-based), the line of the paper and the line of the run output are stored.

**K2 v2 passes** when at least **2 different** meaningful numbers of the run are found by this procedure **and** at least one of
them is found on a page that has a `Table <n>` line. A candidate that passes K2 v2 is called a **match candidate**; it is not
called verified. The warning of section 9 applies: a scale conversion raises the chance of a coincidental match, so a person decides
from the stored page and line whether a number of the output is the number of the paper's table.

A candidate has three K2 results, all stored: `k2` (v1, as in round 3), `k2v2` and the K1 result. A candidate **passes both** K1
and K2 v2 only when it passes K1 and K2 v2; the stop condition (c) of section 6 counts a candidate once when it passed K1 and
passed K2 v1 or K2 v2.

## 4. Controls

The controls run on the stored runs of earlier work (`data/cpu_runs`, `data/pilot3_runs`, `data/memory_runs`,
`data/pilot4_runs`, the PDFs in `data/pdfs/`, not tracked by git), with the rules of section 3 and no change of them between the
runs. The rules were **not** bent until the control passed: they were written first, then run.

- **Positive control: `paper_006` must pass K2 v2.** Result of the three stored runs (Pilot 3, memory run 2, CPU run): **K2 v2
  passes in all three**, with the same two numbers: `256` (variant `same`, page 7, the batch size in the text of the training
  setup: `...a learning rate of 0.0001 with batches of size 256...`) and `0.933` (variant `x100`, spelled `93.3`, page 7, the
  `SAINT` row of the table with the AUROC of the Bank dataset; output line `[EPOCH 21] VALID ACCURACY: 90.784, VALID AUROC: 0.933`).
  K2 v1 found only `256` in these runs. So v2 sees the scale-converted match that v1 missed. **A limit of this result:** the first
  of the two numbers is a hyperparameter that occurs in the paper by coincidence, and the second is the validation AUROC of an
  epoch of the run (the test AUROC printed in the same run is `0.929`, which is not the printed `93.3`). K2 v2 therefore passes
  `paper_006` on one scale-converted match and one coincidence, and the result is recorded as it is.
- **Negative control: `paper_102` must NOT pass K2 v2** (its output is a toy example on random data from
  `sklearn.datasets.make_classification`, `docs/REAL_VERDICTS.md` section 4). Result: **K2 v2 does not pass** (10 meaningful
  numbers in the output, none found in the paper under any variant). If it had passed, the rule would be too loose and this
  document would say so and K2 v2 would not be used.
- Also run (not a control): `paper_003` passes K2 v2 as it passes v1, with the same 17 numbers; they are values the training log
  prints for other models and match the paper's tables by coincidence of dense numbers (`docs/REAL_VERDICTS.md` section 4).

The code of K2 v2 is added to `scripts/auto_search4.py` by a separate change with unit tests of these controls, and the result of
that code on the controls must equal the result written here.

## 5. The pool and its order

The pool is made as in round 3 (`docs/AUTO_SEARCH_ROUND3.md` section 2): the union of the first 100 results (default order, "best
match") of GitHub repository searches, run once per query on the day of selection and stored unchanged with the date and the exact
query strings in `data/auto_search4/pool.json`. Each query is

    arxiv.org in:readme language:Python archived:false fork:false size:<30000 topic:<topic>

The new stage topics, in this order:

- **Stage 8:** `optimal-control`, `robotics`, `computer-vision`, `remote-sensing`, `geoscience`, `climate`, `finance`,
  `healthcare`, `materials-science`, `astronomy`, `speech`, `audio`, `tabular-deep-learning`, `automl`, `interpretability`,
  `uncertainty-estimation`.
- **Stage 9** (used only when the candidates of stage 8 are used up before a stop condition of section 6 holds):
  `federated-learning`, `active-learning`, `transfer-learning`, `domain-adaptation`, `anomaly-detection`, `clustering`,
  `graph-neural-networks`, `reinforcement-learning`, `knowledge-graph`, `text-classification`, `sentiment-analysis`,
  `machine-translation`, `image-classification`, `object-detection`, `segmentation`, `forecasting`.

- **Stages 10 to 13** (added on 2026-10-27 at 03:30, after stages 8 and 9 were used up with 573 candidates checked, 18 run and none
  passing K1; subfield and domain topics chosen from general machine learning and application areas without looking at any
  candidate; the same rules apply; each stage is used only when the stage before it is used up before a stop condition of
  section 6 holds):
  - **Stage 10:** `medical-image-analysis`, `time-series-classification`, `representation-learning`, `contrastive-learning`,
    `self-supervised-learning`, `meta-learning`, `few-shot-learning`, `continual-learning`, `multi-task-learning`,
    `neural-architecture-search`, `model-compression`, `adversarial-attacks`, `adversarial-robustness`, `graph-embedding`,
    `link-prediction`, `community-detection`.
  - **Stage 11:** `causal-discovery`, `counterfactual`, `fairness`, `privacy`, `differential-privacy`, `recommendation`,
    `collaborative-filtering`, `matrix-factorization`, `tensor-decomposition`, `compressed-sensing`, `dictionary-learning`,
    `manifold-learning`, `kernel-density-estimation`, `bandits`, `multi-armed-bandit`, `sparse-regression`.
  - **Stage 12:** `variational-inference`, `mcmc`, `normalizing-flows`, `diffusion-models`, `gan`, `vae`, `autoencoder`, `attention`,
    `lstm`, `cnn`, `rnn`, `transformer`, `bert`, `word-embeddings`, `question-answering`, `named-entity-recognition`.
  - **Stage 13:** `traffic`, `energy`, `power-systems`, `drug-discovery`, `protein`, `molecular-dynamics`, `cheminformatics`,
    `agriculture`, `earth-observation`, `weather`, `hydrology`, `seismology`, `fluid-dynamics`, `wireless-communication`,
    `scheduling`, `combinatorial-optimization`.

- **Stages 14 to 17** (added on 2026-10-27, merged at 06:37, after stage 13 was used up with 1,607 candidates checked and 67 run; topics chosen from
  general machine learning, optimization and application areas without looking at any candidate, none used in any earlier stage; the same
  rules apply; each stage is used only when the stage before it is used up before a stop condition of section 6 holds):
  - **Stage 14:** `data-augmentation`, `knowledge-distillation`, `graph-learning`, `hypergraph`, `point-cloud`, `3d-reconstruction`, `pose-estimation`, `video-understanding`, `visual-question-answering`, `image-generation`, `super-resolution`, `denoising`, `ocr`, `speaker-recognition`, `music`, `eeg`.
  - **Stage 15:** `bayesian-neural-networks`, `conformal-prediction`, `calibration`, `out-of-distribution-detection`, `outlier-detection`, `imbalanced-learning`, `semi-supervised-learning`, `weak-supervision`, `crowdsourcing`, `ranking`, `learning-to-rank`, `metric-learning`, `similarity-search`, `hashing`, `sketching`, `streaming-algorithms`.
  - **Stage 16:** `numerical-optimization`, `convex-optimization`, `stochastic-optimization`, `gradient-descent`, `sgd`, `adam`, `learning-rate`, `regularization`, `dropout`, `batch-normalization`, `activation-functions`, `loss-functions`, `neural-ode`, `physics-informed`, `pinn`, `surrogate-model`.
  - **Stage 17:** `survival`, `epidemic`, `covid-19`, `genetics`, `single-cell`, `proteomics`, `neuroimaging`, `fmri`, `ecg`, `clinical`, `electronic-health-records`, `drug-repurposing`, `ecology-modeling`, `crop`, `remote-sensing-imagery`, `satellite`.

- **Stages 18 to 21** (added on 2026-10-27, after stage 17 was used up with 2,170 candidates checked and 91 run; classical method, statistics,
  control and language topics chosen without looking at any candidate, none used in any earlier stage; the same rules apply; each stage is
  used only when the stage before it is used up before a stop condition of section 6 holds):
  - **Stage 18:** `decision-tree`, `gradient-boosting`, `logistic-regression`, `linear-regression`, `naive-bayes`, `k-means`, `pca`, `nearest-neighbors`, `knn`, `hidden-markov-model`, `kalman-filter`, `particle-filter`, `state-space-model`, `gaussian-mixture-model`, `expectation-maximization`, `markov-chain`.
  - **Stage 19:** `lasso`, `ridge-regression`, `elastic-net`, `bootstrap`, `hypothesis-testing`, `bayesian-statistics`, `mixed-effects`, `time-series-decomposition`, `spectral-analysis`, `wavelet`, `fourier-transform`, `filtering`, `change-point-detection`, `sequence-alignment`, `phylogenetics`, `protein-structure`.
  - **Stage 20:** `policy-gradient`, `q-learning`, `multi-agent`, `imitation-learning`, `offline-reinforcement-learning`, `model-based-rl`, `planning`, `reward-learning`, `inverse-reinforcement-learning`, `control`, `trajectory-optimization`, `model-predictive-control`, `path-planning`, `slam`, `autonomous-driving`, `drone`.
  - **Stage 21:** `text-generation`, `language-model`, `summarization`, `information-extraction`, `text-mining`, `retrieval`, `information-retrieval`, `search-engine`, `embeddings`, `dialogue`, `chatbot`, `prompt`, `in-context-learning`, `fine-tuning`, `lora`, `tokenization`.

Duplicates are removed (case-insensitive). The repositories of **all earlier rounds are removed from the pool before ordering**:
every repository in `data/auto_search3/pool*.json` (the whole pool of round 3, checked or not), `data/demo_set/pool.json`,
`data/candidates/` (all files), `data/seed_papers.json` and `data/corpus_expansion/papers.json`. The remaining candidates are
ordered by the **SHA-256 hash of the lower-case `owner/name`**, ascending; the candidates of stage 9 come after those of stage 8. No
other ordering is used: not stars, not date, not content. Many topics of stage 8 and 9 overlap with topics searched in round 3
(for example `computer-vision`, `robotics`, `interpretability`); those repositories are in the removed set, so the topics return
only repositories that no earlier round has seen.

## 6. When the search stops

The first of these:

- **(a)** 9 hours have passed since the start of the night's work (the start, 2026-10-27 01:44 +03:00, is written to
  `sabah_bekleyenler.md`, a file outside the repository);
- **(b)** 150 new candidates have been run in the sandbox in this round;
- **(c)** 5 candidates have passed K1 and K2 (v1 or v2);
- **(d)** the free disk space is under 30 GB.

A pool that is used up is not a stop condition: the queries of the next stage are added and the search goes on. The search is
resumable: candidates with a stored result are skipped.

## 7. Records

For each run candidate, `data/auto_search4/runs/<id>/` keeps `run_report.json`, the K1, K2 v1 and K2 v2 result file, and short
logs (long outputs are truncated; local paths are replaced by `<REPO>` and `<HOME>`). `data/auto_search4/evaluation.json` holds
every checked candidate with its first failed rule or its run result. Records of earlier rounds are not touched.

## 8. Reporting

From a script and the stored files only: the number of candidates tried, the numbers that passed K1, K2 v1, K2 v2 and both, the
Wilson 95% interval for each, a table of the failure categories, and for every K2 v2 pass the command, the duration and each
matching number with its variant, page and line. No number is typed by hand.

## 9. Limits that are known before the first search

- **This is a selected and non-representative list, not a success rate.** The pool is what GitHub's search returns for these topics
  with `arxiv.org` in the README, small, and without a GPU mention; the order is a hash; the rules reject most repositories. The
  Wilson intervals describe only the candidates that were run.
- **K2 v2 can match by chance, and its scale conversion and rounding make this more likely than v1.** Hyperparameters and other
  numbers with three digits (`256`) occur in papers without being results. The result is a reason for a person to look at the stored
  page and line, not evidence. The guard of section 3 limits the chance, it does not remove it.
- K1 selects for code that runs in 10 minutes as written. A paper that fails may be reproducible with a correction; this round says
  nothing about that.
- The first `python` line of a README may be a data preparation step, a demo or a help text. A pass shows that the command ran and
  printed numbers, not that the paper's main result is reproduced.
- Simulated or synthetic data in a run's output is labelled as simulation wherever it is reported.
- No claim is accepted by this round.

## 10. Re-evaluation of the round 3 runs

K2 v2 applied to the stored `stdout.log` of the two candidates of round 3 that passed K1 (`wanyichen06/HSPR`, `fless-lab/rsi-framework`),
with the rules of section 3 and no new run. Only the K1 passers are re-evaluated: the other 133 runs of round 3 failed K1, and their
outputs (mostly install failures) are not part of this re-evaluation. The PDFs are those kept in round 3 (`data/pdfs/`, not
tracked by git).

Generated by `scripts/auto_search4.py reeval` from data/auto_search3/evaluation.json and data/auto_search3/runs/<id>/stdout.log; nothing was run again.

| Id | Repository | arXiv | Output truncated | K2 v1 | K2 v2 | Output numbers | Found (v1) | Found (v2) |
|---|---|---|---|---|---|---|---|---|
| a3_095 | `wanyichen06/HSPR` | 2610.24611 | no | no | no | 1 | 0 | 0 |
| a3_096 | `fless-lab/rsi-framework` | 2603.21610 | no | no | no | 207 | 0 | 0 |


**Result:** neither candidate passes K2 v2 (and neither passed v1): no number of the output was found in the paper under any
variant. The round 3 outcome for these two candidates does not change: K1 passed, K2 not passed, with the scale and rounding
variants as well. (The output of `a3_096` has one more meaningful number under v2 than under v1 only because v2 reads a decimal
comma as a decimal point first.) This says nothing about whether the output is related to the paper; it says only that no printed
number is also printed in the paper in a spelling that v2 can reach.

## 11. Results

Run of 2026-10-27 (issues #521, #523, #529, #535). The search started at 2026-10-27 01:44 +03:00 and applied this protocol to the
pools of stages 8 to 21. The tables below are generated (`python scripts/auto_search4.py report`) from
`data/auto_search4/evaluation.json` and the run folders; the notes after them are written by hand from them.

<!-- results:start -->
Generated by `scripts/auto_search4.py report` from `data/auto_search4/evaluation.json` (written 2026-10-27T08:03:30+00:00, search started 2026-10-26T22:44:00+00:00) and `data/auto_search4/runs/`; do not edit by hand. The search stopped because: `time_limit_9h`.

**This is a selected, non-representative list. The shares below describe only the candidates that were run, under these rules and this pool. They are not a success rate and not the reproducibility of any field. A K2 pass is a match candidate (a string match), not a verified result. K2 v2 converts scales and rounds, so it can match by chance.**

### Results 1: What was tried

- Candidates checked against S1 to S6: 2648.
- Candidates that passed S1 to S6 and were run once in the sandbox (tried): 107.
- Passed K1: 3 of 107 (Wilson 95%: 1.0 % - 7.9 %).
- Passed K2 v1: 1 of 107 (Wilson 95%: 0.2 % - 5.1 %); K2 was computed for 7 runs that completed with exit code 0.
- Passed K2 v2: 1 of 107 (Wilson 95%: 0.2 % - 5.1 %).
- Passed both K1 and K2 v1: 0 of 107 (Wilson 95%: 0.0 % - 3.5 %).
- Passed both K1 and K2 v2: 0 of 107 (Wilson 95%: 0.0 % - 3.5 %).

First failed static rule of the checked candidates:

| Rule | Candidates |
|---|---|
| S1 | 1140 |
| S2 | 999 |
| S3 | 344 |
| S4 | 8 |
| S5 | 40 |
| S6 | 7 |

Outcome of the run test K1 (failure reasons):

| Outcome | Candidates |
|---|---|
| harness | 2 |
| install | 31 |
| no_metric_line | 4 |
| passed K1 | 3 |
| run | 66 |
| staging | 1 |

### Results 2: Every run

| Id | Repository | Command | Install | Run | Exit | Seconds | K1 | K2 v1 | K2 v2 | Deciding log line |
|---|---|---|---|---|---|---|---|---|---|---|
| a4_001 | `yamahigashi/Wav2Vec2FBX` | `python main.py input_audio.wav` | FAILED | FAILED | 1 | 0.654 | install | - | - | `ERROR: No matching distribution found for audioread==2.1.9` |
| a4_002 | `ML4Sustain/Awesome-RS-Reasoning-Models` | `python scripts/fetch_arxiv_meta.py` | INSTALLED | COMPLETED | 0 | 3.708 | no_metric_line | no | no | `No metadata updates needed.` |
| a4_003 | `prs-eth/xbd-s12` | `python src/data/create_aligned_vrt.py --original_xbd_path="data/original_xbd" --num_workers=8` | SKIPPED | FAILED | 1 | 0.719 | run | - | - | `ModuleNotFoundError: No module named 'rasterio'` |
| a4_004 | `wazeerzulfikar/deep-split-ensembles` | `python main.py train --datasets_dir datasets --dataset boston --model_dir boston_models --verbose 1` | FAILED | FAILED | 1 | 0.769 | install | - | - | `ERROR: No matching distribution found for absl-py==0.9.0` |
| a4_005 | `sevakon/efficientdet` | `python main.py -mode 'trainval' -model 'efficientdet-d{}'` | FAILED | FAILED | 1 | 0.515 | install | - | - | `ERROR: No matching distribution found for matplotlib==3.1.3` |
| a4_006 | `just-eoghan/Lightning-UDA-detect` | `python preprocess/foggy_data_beta_0.02.py` | FAILED | FAILED | 1 | 0.5 | install | - | - | `ERROR: No matching distribution found for pudb==2022.1.3` |
| a4_007 | `joyboseroy/falkor-irac` | `python ingestion/pdf_extractor.py --input data/raw/sc_judgment.pdf --output data/processed/` | INSTALLED | FAILED | 1 | 3.184 | run | - | - | `OSError: [Errno 30] Read-only file system: 'data'` |
| a4_008 | `varunghat/GrammarMT` | `python scripts/utils/download_models.py` | FAILED | FAILED | 1 | 0.488 | install | - | - | `ERROR: No matching distribution found for langdetect` |
| a4_009 | `sensein/search_hybrid` | `python build_index.py` | INSTALLED | FAILED | 1 | 1.429 | run | - | - | `sqlite3.OperationalError: unable to open database file` |
| a4_010 | `hhy-huang/GraphJudge` | `python ./chat/run_chatgpt_entity.py` | SKIPPED | FAILED | 1 | 0.663 | run | - | - | `ModuleNotFoundError: No module named 'openai'` |
| a4_011 | `joyboseroy/ideaforge` | `python ideaforge.py --idea "A voice-first legal assistant in Hindi for rural India"` | INSTALLED | FAILED | 1 | 57.011 | run | - | - | `redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.` |
| a4_012 | `rozumden/FMODetect` | `python run.py --video example/falling_pen.avi` | SKIPPED | FAILED | 1 | 0.648 | run | - | - | `ModuleNotFoundError: No module named 'tensorflow'` |
| a4_013 | `Aqasch/replay_buffer_eng_for_quantum_optimization` | `python compiling/main_1q_small_rot.py --replay CHOOSE_BUFFER` | INSTALLED | FAILED | 1 | 21.033 | run | - | - | `OSError: [Errno 30] Read-only file system: 'checkpoints'` |
| a4_014 | `ambekarsameer96/GLSS` | `python vae_u-efficientnet_latent_search.py` | SKIPPED | FAILED | 1 | 0.687 | run | - | - | `ModuleNotFoundError: No module named 'matplotlib'` |
| a4_015 | `DataSciencePolimi/MDER-DR_RAG` | `python build_knowledge_base.py` | FAILED | FAILED | 1 | 1.003 | install | - | - | `ERROR: No matching distribution found for pdfminer==20191125` |
| a4_016 | `JerryX1110/awesome-rvos` | `python down_YTVOS_w_refer.py` | SKIPPED | FAILED | 1 | 0.474 | run | - | - | `ModuleNotFoundError: No module named 'gdown'` |
| a4_017 | `onur-cubukcu/cop28-hate-speech` | `python merge_datasets.py file1.json file2.json file3.json` | FAILED | FAILED | 1 | 0.608 | install | - | - | `ERROR: No matching distribution found for proxy_tools` |
| a4_018 | `CXY0112/PAGE-RAG` | `python scripts/build.py path/to/book.epub --work-id my_book --work-status COMPLETED` | SKIPPED | FAILED | 1 | 0.671 | run | - | - | `ModuleNotFoundError: No module named 'algorithm'` |
| a4_019 | `Emmimal/catastrophic-forgetting` | `python demo.py` | INSTALLED | COMPLETED | 0 | 31.869 | passed | no | no | `` |
| a4_020 | `hebo1221/RandWireNN` | `python run_RandWireNN.py` | INSTALLED | FAILED | 1 | 0.487 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_021 | `ml4ai/mliis` | `python run_metasegnet.py <args>` | FAILED | FAILED | 1 | 0.758 | install | - | - | `ERROR: No matching distribution found for tensorflow==1.15.4` |
| a4_022 | `imrahulr/adversarial_robustness_pytorch` | `python train-wa.py --data-dir <data_dir> --log-dir <log_dir> --desc <name_of_the_experiment> --data cifar10s --batch-size 1024 --model wrn-28-10-swish --num-adv-epochs 400 --lr 0.4 --beta 6.0 --unsup-fraction 0.7 --aux-data-filename <path_to_additional_data>` | FAILED | FAILED | 1 | 1.214 | install | - | - | `ERROR: No matching distribution found for autoattack==0.1` |
| a4_023 | `as791/ZOO_Attack_PyTorch` | `python setup_mnist_model.py` | SKIPPED | FAILED | 1 | 0.664 | run | - | - | `ModuleNotFoundError: No module named 'matplotlib'` |
| a4_024 | `nik-dim/pamal` | `python multimnist.py method=pamal data.root=/path/to/data` | FAILED | FAILED | 1 | 0.553 | install | - | - | `ERROR: No matching distribution found for meshzoo==0.11.6` |
| a4_025 | `AYMANE-SNOUSSI/adversarial-attacks-rag` | `python src/fetch_corpus.py` | FAILED | FAILED | 1 | 0.581 | install | - | - | `ERROR: No matching distribution found for numpy==2.5.3` |
| a4_026 | `pfriedri/medfuncta` | `python train.py --config ./configs/experiments/DATASET_RESOLUTION.yaml` | None | None | None | None | harness | - | - | `ModuleNotFoundError: No module named 'yaml'` |
| a4_027 | `anmold-07/GRNN-FaultChain-Predictor` | `python faultChainSolver.py --case 39 --load 0.55` | None | None | None | None | harness | - | - | `ModuleNotFoundError: No module named 'yaml'` |
| a4_028 | `Emmimal/continual-learning` | `python benchmarks/benchmark.py` | INSTALLED | FAILED | 1 | 31.899 | run | - | - | `OSError: [Errno 30] Read-only file system: './data'` |
| a4_029 | `SES-Lab-OTH/deberta-conpara` | `python src/conpara.py --text "paste a document here"` | INSTALLED | FAILED | 1 | 90.076 | run | - | - | `huggingface_hub.errors.LocalEntryNotFoundError: An error happened while trying to locate the file on the Hub and we cannot find the requested files in the local cache. Please check your connection and try again or make sure your Internet connection is on.` |
| a4_030 | `qroa/QROA` | `python main.py data/instructions.csv [API_AUTH_TOKEN]` | FAILED | FAILED | 1 | 0.528 | install | - | - | `ERROR: No matching distribution found for fastchat==0.2.20` |
| a4_031 | `VITA-Group/SparseADV_Homotopy` | `python demo_attack.py --img_dir path/to/imgs` | SKIPPED | FAILED | 1 | 0.559 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_032 | `sarthak268/DisCont` | `python train.py` | SKIPPED | FAILED | 1 | 0.694 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_033 | `RjDuan/AdvDrop` | `python infod_sample.py` | SKIPPED | FAILED | 1 | 0.687 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_034 | `DLR-RM/RECALL` | `python recall/data_import/data_generation_script.py --path_to_datasets $PATH_TO_DATASET --dataset_name "core50"` | SKIPPED | FAILED | 1 | 0.59 | run | - | - | `ModuleNotFoundError: No module named 'yaml'` |
| a4_035 | `houchengbin/GloDyNE` | `python src/main.py --method DynWalks --task gr --graph data/AS733/AS733_new.pkl --label data/AS733/AS733_label.pkl --emb-file output/AS733_DynWalks.pkl --num-walks 10 --walk-length 80 --window 10 --limit 0.1 --scheme 4 --seed 2019 --emb-dim 128 --workers 32` | SKIPPED | FAILED | 1 | 0.647 | run | - | - | `ModuleNotFoundError: No module named 'networkx'` |
| a4_036 | `AliLotfi92/InfoMaxVAE` | `python main.py --method infomax --model mlp --dim 128 --num_iter 500 --batch_size 64 --gamma 20 --alpha 1 --dataset cifar10 --trial 1` | SKIPPED | FAILED | 1 | 0.455 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_037 | `microsoft/figure` | `python download_datasets.py` | FAILED | FAILED | 1 | 0.466 | install | - | - | `ERROR: No matching distribution found for torchvision==0.17.1+cu121` |
| a4_038 | `aymen-000/predict-reconstruct-language-models` | `python src/train.py --config config/config.yaml --mode hybrid` | INSTALLED | FAILED | 1 | 75.676 | run | - | - | `Check your internet connection or see how to run the library in offline mode at 'https://huggingface.co/docs/transformers/installation#offline-mode'.` |
| a4_039 | `fabio-rovai/worldkernel` | `python experiments/counterfactual_witness.py` | SKIPPED | FAILED | 1 | 0.617 | run | - | - | `ModuleNotFoundError: No module named 'worldkernel'` |
| a4_040 | `YTomar79/fairmix-audit` | `python scripts/build_workshop_artifacts.py --run-dir results/<run-dir> --output-dir results/paper_artifacts` | INSTALLED | FAILED | 1 | 9.277 | run | - | - | `OSError: [Errno 30] Read-only file system: '/workspace/repo/results/paper_artifacts/tables/csv'` |
| a4_041 | `ayanmaj92/fairall` | `python main.py --dataset_file {DATASET_PARAMS_FILE} --model_file {MODEL_PARAMS_FILE} --trainer_file {TRAINER_PARAMS_FILE}` | SKIPPED | FAILED | 1 | 0.526 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_042 | `martinlukk/fairfund-bench` | `python benchmark/parse.py logs/ -o gpt-4o_outcomes.csv` | SKIPPED | FAILED | 1 | 1.055 | run | - | - | `ModuleNotFoundError: No module named 'inspect_ai'` |
| a4_043 | `jericho-cain/cwt-manifold-grav-wav` | `python scripts/run_end_to_end_test.py --config config/run_3_5000_samples.yaml` | INSTALLED | FAILED | 1 | 26.055 | run | - | - | `OSError: [Errno 30] Read-only file system: '/workspace/repo/end_to_end_test_20261027_022409.log'` |
| a4_044 | `tmadmao/noveldedup` | `python novel_dedup.py --selftest` | INSTALLED | COMPLETED | 0 | 1.512 | no_metric_line | no | no | `自检结果：14/14 通过，用时 0.7s` |
| a4_045 | `sulgik/orts` | `python examples/basic_usage.py` | SKIPPED | COMPLETED | 0 | 1.476 | passed | no | no | `` |
| a4_046 | `LazarusNLP/NusaBERT` | `python scripts/run_mlm.py --model_name_or_path indobenchmark/indobert-base-p1 --tokenizer_name LazarusNLP/nusabert-base --max_seq_length 128 --per_device_train_batch_size 256 --per_device_eval_batch_size 256 --do_train --do_eval --max_steps 500000 --warmup_steps 24000 --learning_rate 3e-4 --weight_decay 0.01 --optim adamw_torch_fused --bf16 --preprocessing_num_workers 24 --dataloader_num_workers 24 --save_steps 10000 --save_total_limit 3 --output_dir outputs/nusabert-base --overwrite_output_dir --report_to tensorboard --push_to_hub --hub_private_repo --hub_model_id LazarusNLP/nusabert-base` | INSTALLED | FAILED | 1 | 55.125 | run | - | - | `ImportError: cannot import name 'is_torch_tpu_available' from 'transformers' (/workspace/deps/transformers/__init__.py)` |
| a4_047 | `wenxueru/GraphNER` | `python main.py --dataset_name=genia --evaluate=test --concat --pretrain_select=dmis-lab/biobert-base-cased-v1.2 --word2vec_select=bio --batch_size=4 --epochs=5 --max_length=128 --pos_dim=50 --char_dim=50` | FAILED | FAILED | 1 | 0.646 | install | - | - | `ERROR: No matching distribution found for torch==1.12.1` |
| a4_048 | `Iman998/bactrainus` | `python examples/build_reader_view.py` | SKIPPED | FAILED | 1 | 0.548 | run | - | - | `ModuleNotFoundError: No module named 'bactrainus'` |
| a4_049 | `rishikksh20/Avocodo-pytorch` | `python train.py --config config_v1.json` | FAILED | FAILED | 1 | 0.539 | install | - | - | `ERROR: No matching distribution found for numpy==1.17.4` |
| a4_050 | `wenge-research/TableEval` | `python run_prediction.py --model_name gpt-4o-mini` | INSTALLED | FAILED | 1 | 5.829 | run | - | - | `OSError: [Errno 30] Read-only file system: './outputs'` |
| a4_051 | `OpenMOSS/HalluQA` | `python calculate_metrics.py --response_file_name gpt-4-0613_responses.json("replace with your own responses") --api_key "your openai api key" --organization "organization of your openai account"` | SKIPPED | FAILED | 1 | 0.515 | run | - | - | `ModuleNotFoundError: No module named 'openai'` |
| a4_052 | `uclaml/Rephrase-and-Respond` | `python main.py [options]` | SKIPPED | FAILED | 1 | 0.537 | run | - | - | `ModuleNotFoundError: No module named 'openai'` |
| a4_053 | `Lornatang/FAN-PyTorch` | `python predict.py --image_path ./figures/Available.png --weights_path ./results/pretrained_models/FAN-MJSynth-e9341ede.pth.tar` | INSTALLED | FAILED | 1 | 1.275 | run | - | - | `ImportError: libxcb.so.1: cannot open shared object file: No such file or directory` |
| a4_054 | `dukesun99/Corpus2Skill` | `python scripts/prepare_wixqa.py --output ./wixqa_corpus` | SKIPPED | FAILED | 1 | 0.559 | run | - | - | `ModuleNotFoundError: No module named 'datasets'` |
| a4_055 | `kingofspace0wzz/wae-rnf-lm` | `python main.py --dist normal --kla --mmd --kernel im --flow --n_flows 3 --center --reg im --t` | SKIPPED | FAILED | 1 | 0.513 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_056 | `1Konny/FactorVAE` | `python main.py --name run_celeba --dataset celeba --gamma 6.4 --lr_VAE 1e-4 --lr_D 5e-5 --z_dim 10 ...` | SKIPPED | FAILED | 1 | 0.658 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_057 | `nbip/IWAE` | `python main.py --n_samples          <# of importance samples, 5 by default>` | SKIPPED | FAILED | 1 | 0.437 | run | - | - | `ModuleNotFoundError: No module named 'tensorflow'` |
| a4_058 | `ZhangXinWhut/SimWhisper-Codec` | `python inference.py --input_dir /path/to/LibriSpeech/test-clean` | FAILED | FAILED | 1 | 0.51 | install | - | - | `ERROR: No matching distribution found for pesq==0.0.4` |
| a4_059 | `bot66/MNISTDiffusion` | `python train_mnist.py` | INSTALLED | FAILED | 1 | 31.697 | run | - | - | `OSError: [Errno 30] Read-only file system: './mnist_data'` |
| a4_060 | `alibaba/SRDiffusion` | `python ./wan/srd_generate.py --task t2v-14B --size 832*480 --ckpt_dir ./Wan2.1-T2V-14B --rendering_ckpt_dir ./Wan2.1-T2V-1.3B --offload_model True --t5_cpu --self_diff_threshold 0.01 --prompt "Two anthropomorphic cats in comfy boxing gear and bright gloves fight intensely on a spotlighted stage."` | SKIPPED | FAILED | 1 | 0.584 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_061 | `lyutyuh/structured-span-selector` | `python minimize.py ./data_dir/ ./data_dir/ false` | SKIPPED | FAILED | 1 | 0.586 | run | - | - | `ModuleNotFoundError: No module named 'nltk'` |
| a4_062 | `NewLandTV/Attention` | `python Train.py  --n=6 --d_model=512 --d_ff=8 --h=8 --d_k=64 --d_v=64 --p_drop=0.1 --e_ls=0.1 --epoch=1 --batch_size=128 --warmup_steps=4000 --root_data_path=".Data" --model_path="./Model.pb" --use_small_data` | INSTALLED | FAILED | 2 | 26.042 | run | - | - | `Train.py: error: unrecognized arguments: --d_model=512 --d_ff=8 --d_k=64 --d_v=64 --p_drop=0.1 --e_ls=0.1 --batch_size=128 --warmup_steps=4000 --root_data_path=.Data --model_path=./Model.pb --use_small_data` |
| a4_063 | `AlbMLpy/laplace-tnkm` | `python setup_project.py` | INSTALLED | FAILED | 1 | 1.456 | run | - | - | `pytz: No module named 'pytz'` |
| a4_064 | `fl0wbar/advDNIC.estimator` | `python main.py --verbose --model-dir="experiments/base_model/generator" train --train-data-dir="data/train" --eval-data-dir="data/benchmark/kodak" --num-parallel-calls=4 --batchsize=4 --epochs=1000 --save-summary-steps=10 --random-seed=230 --allow-growth=True --xla=False --save-profiling-steps=0 --log-verbosity="INFO"` | SKIPPED | FAILED | 1 | 0.518 | run | - | - | `ModuleNotFoundError: No module named 'absl'` |
| a4_065 | `DiogoRibeiro7/rcpsp_cf_ivfth` | `python run_tests.py --no-solver` | SKIPPED | FAILED | 4 | 1.15 | run | - | - | `E   ModuleNotFoundError: No module named 'pyomo'` |
| a4_066 | `RelationRx/tiny_moves` | `python  tiny_moves/entry_points/chat.py --config_name tiny_moves_no_corpus.yaml` | FAILED | FAILED | 1 | 0.501 | install | - | - | `ERROR: No matching distribution found for anyio<5.0.0,>=4.0.0` |
| a4_067 | `HyunwooLee0429/GMSPP` | `python fuzz_alns.py 200` | SKIPPED | COMPLETED | 0 | 225.212 | no_metric_line | passed | passed | `200/200 passed` |
| a4_068 | `guyyariv/DyPE` | `python run_dype.py --prompt "Your text prompt here"` | INSTALLED | FAILED | 1 | 55.403 | run | - | - | `ModuleNotFoundError: No module named 'sqlalchemy'` |
| a4_069 | `BennyDaBall930/pid-tiled-decode` | `python pid_tiled_decode.py --from-latent "latents/my_shot_00001_.latent" --label my_shot_8k --out runs/my_shot_8k --vae-image path/to/your_vae_decode.png` | SKIPPED | FAILED | 1 | 0.897 | run | - | - | `ModuleNotFoundError: No module named 'PIL'` |
| a4_070 | `zhongshsh/4D-Animal` | `python main_optimize_scene.py 'exp.sequence_index="1030_23106_17099"' 'exp.experiment_folder="experiments"'` | SKIPPED | FAILED | 1 | 0.5 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_071 | `ysl609/stereovision-mars` | `python scripts/stereo.py` | INSTALLED | FAILED | 1 | 1.994 | run | - | - | `ImportError: libGL.so.1: cannot open shared object file: No such file or directory` |
| a4_072 | `ildoonet/unsupervised-data-augmentation` | `python train.py -c confs/wresnet28x2.yaml --unsupervised` | FAILED | FAILED | 1 | 0.554 | install | - | - | `ERROR: Cannot find command 'git' - do you have 'git' installed and in your PATH?` |
| a4_073 | `LeapLabTHU/RvR` | `python app.py` | INSTALLED | FAILED | 1 | 25.968 | run | - | - | `ImportError: libGL.so.1: cannot open shared object file: No such file or directory` |
| a4_074 | `HINTLab/pulmonary-tree-labeling` | `python train_network.py -d $dataset_specs_json_file` | SKIPPED | FAILED | 1 | 0.52 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_075 | `Lornatang/CRNN-PyTorch` | `python predict.py --image_path ./figures/Available.png --weights_path ./results/pretrained_models/CRNN-MJSynth-e9341ede.pth.tar` | INSTALLED | FAILED | 1 | 1.308 | run | - | - | `ImportError: libxcb.so.1: cannot open shared object file: No such file or directory` |
| a4_076 | `IDEA-Research/DINO-X-API` | `python demo.py` | FAILED | FAILED | 1 | 0.582 | install | - | - | `ERROR: No matching distribution found for dds-cloudapi-sdk==0.5.3` |
| a4_077 | `wjq-learning/SleepDG` | `python main_5.py` | SKIPPED | FAILED | 1 | 0.555 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_078 | `Shidu-Ren/ICM-Bench` | `python evaluation/judging/scripts/rejudge_openqa_m3agent_style.py --input "$ICM_BENCH_OUTPUT_ROOT/SYSTEM/answers.jsonl" --output "$ICM_BENCH_OUTPUT_ROOT/SYSTEM/answers.judged.jsonl" --summary "$ICM_BENCH_OUTPUT_ROOT/SYSTEM/answers.judged.summary.json"` | SKIPPED | FAILED | 1 | 0.707 | run | - | - | `RuntimeError: Missing Gemini API key for models/gemini-3-flash-preview` |
| a4_079 | `iMoonLab/LLM4Hypergraph` | `python ./eval_LLM.py` | FAILED | FAILED | 1 | 0.477 | install | - | - | `Installing collected packages: nvidia-cusparselt-cu13, namex, mpmath, libclang, flatbuffers, cuda-toolkit, wrapt, urllib3, tzdata, typing_extensions, triton, tqdm, threadpoolctl, termcolor, sympy, six, setuptools, PyYAML, pyparsing, pygments, protobuf, pillow, packaging, opt_einsum, nvidia-nvtx, nvi` |
| a4_080 | `TreeLLi/AROID` | `python src/train.py -a wresnet --depth 34 --width 10 --max_iter 0 --epochs 40 --annealing 20 30 -ei 0` | FAILED | FAILED | 1 | 0.51 | install | - | - | `ERROR: Cannot find command 'git' - do you have 'git' installed and in your PATH?` |
| a4_081 | `InstituteOfSleepAndDreamTechnologies/Traumschreiber_Python_Offline-Data-Analysis` | `python plot_sleep_scoring.py /media/$USER/TS2607-XXX/ADC/AD0021_20261020_2351.BDF --channel 0` | INSTALLED | FAILED | 1 | 23.578 | run | - | - | `FileNotFoundError: [Errno 2] No such file or directory: '/media/$USER/TS2607-XXX/ADC/AD0021_20261020_2351.BDF'` |
| a4_082 | `erwinmsmith/DAMCHA` | `python main.py --dataset cifar10 --use_M --use_mlp --share_mlp` | FAILED | FAILED | 1 | 0.561 | install | - | - | `ERROR: No matching distribution found for rouge-score>=0.1.2` |
| a4_083 | `najmulhasan-code/crc-screen` | `python recompute_signal2.py` | INSTALLED | FAILED | 1 | 4.183 | run | - | - | `OSError: [Errno 30] Read-only file system: '/workspace/repo/data'` |
| a4_084 | `SALT-NLP/Sketch2Code` | `python experiments/gpt4_direct.py --model gpt-4o --input_dir /path/to/your/sketch2code/dataset --out_dir /path/to/your/output/directory` | FAILED | FAILED | 1 | 0.52 | install | - | - | `Hint: = is not a valid operator. Did you mean == ?` |
| a4_085 | `Rushab1/gr-jev` | `python scripts/data/download_data.py metatool` | SKIPPED | FAILED | 1 | 0.544 | run | - | - | `ModuleNotFoundError: No module named 'grjev'` |
| a4_086 | `fatemafaria142/LabourCrew` | `python scripts/ingest_pdf.py data/raw/Bangladesh-Labour-Act-2006-Amended-Chapter2.pdf` | FAILED | FAILED | 1 | 0.626 | install | - | - | `Installing collected packages: pymupdf4llm, pymupdf-layout, nvidia-cusparselt-cu13, mpmath, flatbuffers, cuda-toolkit, appdirs, zstandard, xxhash, websockets, uuid-utils, urllib3, tzdata, typing-extensions, truststore, triton, tqdm, threadpoolctl, tenacity, tabulate, sympy, sniffio, six, shellingham` |
| a4_087 | `amaxiom/OverNaN` | `python tests/OverNaN_test.py` | INSTALLED | FAILED | 1 | 9.234 | run | - | - | `ModuleNotFoundError: No module named 'xgboost'` |
| a4_088 | `mlahozy21/Graph-Convolutional-Networks-GCN` | `python scripts/main.py` | INSTALLED | FAILED | 1 | 3.319 | run | - | - | `ModuleNotFoundError: No module named 'gcn'` |
| a4_089 | `ivannz/cplxmodule` | `python tests/test_relevance.py` | SKIPPED | FAILED | 1 | 0.489 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_090 | `yubocai-poly/ALMTON` | `python tools/check_mosek.py` | INSTALLED | FAILED | 1 | 7.435 | run | - | - | `}` |
| a4_091 | `mbeps/custom-neural-network-classifier` | `python pacman.py --pacman ClassifierAgent` | SKIPPED | FAILED | 1 | 0.86 | run | - | - | `ImportError: libtk8.6.so: cannot open shared object file: No such file or directory` |
| a4_092 | `shaheennabi/Proximal-Policy-Optimization-PPO` | `python main.py` | INSTALLED | COMPLETED | 0 | 55.468 | no_metric_line | no | no | `Iter   40 \| Return  -1179.0 \| KL 0.0059 \| Clip 0.05 \| VLoss 86.704 \| Entropy 1.205` |
| a4_093 | `YilunKuang/lpworldmodel` | `python train.py --config-name train_rdmreg.yaml env=pusht frameskip=5 num_hist=3 encoder=vit_scratch link=reprelu target_p=1 regularizer=rdmreg mu=0 agg=b predictor=ar_adaln encoder.proj_dim=384 action_emb_dim=384 mup=true training.mup_lr=1e-4 reg_weight=0.5 training.epochs=2 training.batch_size=64 env.num_workers=20 ckpt_base_path=./runs hydra.run.dir=./runs/outputs/lpwm_adaln_pusht_d384` | FAILED | FAILED | 1 | 0.484 | install | - | - | `Installing collected packages: wcwidth, triton, thop, tensorboardx, stack-data, python-xlib, pynput, pure-eval, ptyprocess, proglog, pexpect, nvidia-ml-py, mpmath, libclang, hydra-submitit-launcher, hydra-core, gym-notices, google-pasta, flatbuffers, fastjsonschema, einops, docker-pycreds, distlib, ` |
| a4_094 | `OK-computer008/TradingAgents-CryptoA` | `python run_a_share.py` | INSTALLED | FAILED | 1 | 39.912 | run | - | - | `ImportError: akshare is required for A-share data. Install with: pip install akshare` |
| a4_095 | `sadia-sigma-lab/BLINDSPOT` | `python scripts/generate_trajectories.py` | SKIPPED | FAILED | 1 | 0.563 | run | - | - | `or set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars` |
| a4_096 | `d1024choi/pathgan_pytorch` | `python train.py --exp_id 100` | SKIPPED | FAILED | 1 | 0.499 | run | - | - | `ModuleNotFoundError: No module named 'torch'` |
| a4_097 | `enjeeneer/zero-shot-rl` | `python exorl_reformatter.py walker_rnd` | FAILED | FAILED | 1 | 0.877 | install | - | - | `ERROR: No matching distribution found for POT==0.9.0` |
| a4_098 | `SALT-NLP/agent-collusion` | `python analysis/agreement_judge.py --runs 'results/main/*/run.json' --out analysis/results/agreement.csv --base-url http://localhost:8042/v1 --model qwen3.8-27b --verdict-policy raw-only` | INSTALLED | FAILED | 2 | 0.637 | run | - | - | `no run.json matched` |
| a4_099 | `SII-MemQ/MemQ` | `python run/run_llb.py --config configs/my_experiment.local.yaml` | INSTALLED | FAILED | 1 | 11.702 | run | - | - | `ModuleNotFoundError: No module named 'colorama'` |
| a4_100 | `tanminsen/creativity-eval` | `python export_data.py llama results_quickstart.json llmjudge deberta false 1.0 1 nohs 0` | FAILED | FAILED | 1 | 0.742 | install | - | - | `ERROR: No matching distribution found for llama_cpp_python==0.2.77` |
| a4_101 | `SPL-BGU/PolyPlan` | `python demo.py` | FAILED | FAILED | 1 | 0.502 | install | - | - | `ERROR: No matching distribution found for gym==0.21.0` |
| a4_102 | `shubham-61291/pre_generation_rag_retrieval_benchmark` | `python pre_generation_rag_retrieval_benchmark.py` | SKIPPED | FAILED | 1 | 0.436 | run | - | - | `SyntaxError: invalid syntax` |
| a4_103 | `nguyenvo09/LearningFromFactCheckers` | `python Masters/master_fcrg.py` | FAILED | FAILED | 1 | 1.609 | install | - | - | `ERROR: No matching distribution found for pandas==0.23.1` |
| a4_104 | `snap-stanford/stark` | `python emb_download.py --dataset amazon --emb_dir emb/` | FAILED | FAILED | 1 | 0.744 | install | - | - | `ERROR: No matching distribution found for langdetect` |
| a4_105 | `rrahimi-uci/agentic-context-engineering` | `python examples/01_quickstart.py` | SKIPPED | COMPLETED | 0 | 0.817 | passed | no | no | `` |
| a4_106 | `emory-irlab/conqret-rag` | `python retriever.py` | None | None | None | None | staging | - | - | `Failed to clone repository from 'https://github.com/emory-irlab/conqret-rag': Command '['git', 'clone', 'https://github.com/emory-irlab/conqret-rag', '<HOME>\\rr_pr\\.sandbox_staging\\a4_106']' returned non-zero exit status 128.` |
| a4_107 | `Venta02/visual-search-engine` | `python scripts/download_sample_dataset.py` | FAILED | FAILED | 1 | 0.527 | install | - | - | `Installing collected packages: triton, sentencepiece, pytz, pure-eval, ptyprocess, passlib, nvidia-cusparselt-cu12, mpmath, brotli, zope.interface, zope.event, websockets, wcwidth, watchdog, vine, uvloop, urllib3, tzdata, typing-extensions, traitlets, tqdm, tornado, toml, threadpoolctl, tenacity, sy` |

### Results 3: Match candidates (K2 v1 or K2 v2 passed)

#### a4_067: Exact and Matheuristic Methods for the Generalized Multiple Strip Packing Problem

- Paper: https://arxiv.org/abs/2604.04740
- Repository: https://github.com/HyunwooLee0429/GMSPP at commit `07cae93a82b31660a24e2a2788679f5fb91bb0b5` (MIT)
- Command: `python fuzz_alns.py 200`
- Run phase: 225.212 s; install: SKIPPED; K1: no_metric_line; K2 v1: passed; K2 v2: passed
- K2 v2: numbers of the output found in the paper: 12 of 408 (7 on a page with a `Table <n>` line). A string match with scale conversion; not verified.

| Number | Variant | Searched | Output line | PDF pages | On a table page |
|---|---|---|---|---|---|
| 472 | same | 472 | `[1/200] ok  obj=472  generate_type2(n=36, m=2, seed=271493) obj=makespan alns_se` | 26 | no |
| 178 | same | 178 | `[9/200] ok  obj=178  generate_type1(n=41, m=3, seed=255759) obj=makespan alns_se` | 27 | yes |
| 258 | same | 258 | `[64/200] ok  obj=258  generate_type2(n=40, m=3, seed=881693) obj=makespan alns_s` | 21 | yes |
| 102 | same | 102 | `[102/200] ok  obj=109  generate_type1(n=24, m=2, seed=814054) obj=makespan alns_` | 26 | no |
| 127 | same | 127 | `[127/200] ok  obj=23660  generate_type2(n=15, m=3, seed=791711) obj=total_cost a` | 26 | no |
| 145 | same | 145 | `[145/200] ok  obj=72  generate_type1(n=15, m=4, seed=995422) obj=makespan alns_s` | 16, 19, 21 | yes |
| 284 | same | 284 | `[156/200] ok  obj=284  generate_type2(n=36, m=3, seed=56560) obj=makespan alns_s` | 26 | no |
| 159 | same | 159 | `[159/200] ok  obj=26006  generate_type2(n=10, m=3, seed=686426) obj=total_cost a` | 19 | yes |
| 239 | same | 239 | `[172/200] ok  obj=239  generate_type2(n=24, m=2, seed=881285) obj=makespan alns_` | 27 | yes |
| 183 | same | 183 | `[183/200] ok  obj=20643  generate_type1(n=18, m=3, seed=162784) obj=total_cost a` | 27 | yes |
| 197 | same | 197 | `[197/200] ok  obj=33401  generate_type1(n=32, m=4, seed=443183) obj=total_cost a` | 16, 27 | yes |
| 198 | same | 198 | `[198/200] ok  obj=132  generate_type1(n=38, m=3, seed=148955) obj=makespan alns_` | 26 | no |
<!-- results:end -->

### Notes (by hand, from the generated tables)

- **Stop condition.** The search stopped at the 9-hour limit (condition (a), `time_limit_9h`); the run limit of 150 (b), the 5 passes of
  condition (c) and the disk limit (d) were not reached (107 candidates run; none passed K1 and K2; the free disk space was above 200 GB at every check, made about every 10 minutes).
  3 candidates (a4_108, a4_109, a4_110) had passed S1 to S6 and were staged when the time limit was reached; they were not run and are
  not counted as tried.
- **Stages.** Stages 8 and 9 were in the protocol before the first search. They were used up after 573 candidates; stages 10 to 13, 14 to 17
  and 18 to 21 were added to the protocol, each by a merged change before its search (#523, #529, #535), without looking at a candidate.
  Stages 8 to 20 were used up completely; stage 21 was used in part (the walk reached the time limit inside it).
  The sandbox was idle while a used-up pool waited for the next stage (three times, for roughly 10 to 30 minutes each; the periods were not timed exactly; the
  cause was that a stage addition needed a merged change before the search could be restarted).
- **Restarts.** The walk was restarted four times after its first start (three times after a stage addition, and once after the harness failure below). A candidate that was running at
  a restart was run again from the start and its partial record was deleted, as the resumable rule of round 3 says. The start time of
  the 9 hours (01:44) was passed to every restart.
- **Harness failures.** a4_026 and a4_027 are recorded as `harness`: the Python that started the walk had no PyYAML, which the
  conda environment reader needs. The walk was restarted with the project's virtual environment, and the two candidates were **not**
  run again (a candidate is not repaired or run a second time). a4_106 is recorded as `staging` (`git clone` failed).
- **Order of work.** The code of K2 v2 (#517) was merged before the re-evaluation of the round 3 records (#519, section 10), because the
  re-evaluation needs the code.
- **K1 passers (3).** a4_019 (`python demo.py`), a4_045 (`python examples/basic_usage.py`) and a4_105 (`python examples/01_quickstart.py`)
  are, by their file names, demo or example scripts; their outputs hold 11, 16 and 4 meaningful numbers. K2 v1 found no number of any of them in
  its paper; K2 v2 found one number for a4_019 (below the 2 that a pass needs) and none for a4_045 and a4_105. No candidate passed both K1 and
  K2 (v1 or v2), so **no claim form was made** (the task step B5 was skipped for this reason).
- **K2 passer (1, not a K1 passer).** a4_067 (`python fuzz_alns.py 200`, a fuzzing script) passed K2 v1 and K2 v2 with 12 numbers in the
  same spelling, but failed K1 (`no_metric_line`). The matched numbers are integers: objective values and counters of progress lines
  such as `[102/200]` (the index mask of K2 does not cover the `[n/m]` form) that occur in the tables and the text of the paper by
  coincidence. It is a chance match of a dense output, the kind that section 9 warns about, and not a reproduction of a table; this is
  my reading of the stored lines, and a person has not checked it. The pass is kept as the script recorded it.
- **K2 v2 against K2 v1 in this round.** K2 v2 passed the same single candidate as K2 v1 (a4_067); it found no new match candidate.
  The scale conversion that the positive control `paper_006` needed did not change a result of this round.
- **Not a success rate.** The Wilson intervals above describe only the 107 candidates that were run, under these rules and this pool.

