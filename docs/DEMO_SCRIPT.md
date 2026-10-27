# Demo script (4 to 5 minutes)

Issue #444. This flow uses **only examples that have evidence in the repository**. Every command below was run for real on
2026-10-24 (Windows 11, the repository's `.venv`, Python 3.11) and the output under it is what the command printed, with
local paths replaced by `<REPO>` and `<HOME>`; where an output is long it is shortened and says so. Every step says what it
shows and what it does **not** show. Nothing here is a reproduction of a paper's result.

> **Update 2026-10-27 (#509, #511, #513).** The transcripts below were recorded on 2026-10-24, before the claim map
> (`data/claim_metric_map.json`, `docs/CLAIM_METRIC_MAP.md`). Today `cli.py score` pairs claims with the run's metrics through that
> map: `paper_003` gets Tier 2 100 and `Verified` (0.459 against 0.473; one claim, one number), and `paper_006` and `paper_004` have no
> counterpart for their claims, so their Tier 2 is the neutral 70 (`docs/REAL_VERDICTS.md`, section 2, keeps both results). The
> "58.25, Needs Review" and "nothing was compared" lines of Steps 1 and 5 are therefore the state **before the map**. Since #513
> `cli.py score` also stores the run it scored, so the page of a paper shows that run ("Run of this score", with its start date), not
> another run; the remark in Step 1 that score and latest run do not belong together describes the state at the time of recording.
> The commands and their output were not recorded again.

> **Update 2026-10-28 (#542, #546, #548): the final dashboard.** Step 1 below is replaced by the new Step 1 (the old one is kept under it). The list shows a short
> reason beside every label, the paper page has "Why this label", the synthetic control is listed apart as "not a paper: known-answer
> control", and the new page `/failures` shows the failure statistics. Tier 3 of `paper_003` and `paper_006` now comes from the stored
> three-seed records (100 and 100). The commands below were run for real on 2026-10-28 in a fresh clone of the repository.

Before the talk: `python cli.py init-db` once (loads the 6 papers and the 13 claims that the owner accepted), the virtual environment
active (`.venv\Scripts\Activate.ps1`), and Docker **not** needed: every step reads stored records.

| Step | Minutes | Topic |
|---|---|---|
| 1 | 0:30 | The dashboard |
| 2 | 0:40 | A true and a false claim on a run whose answer is known (91.75 / 56.75) |
| 3 | 0:40 | The same metrics in four runs (`paper_003`, `paper_006`) |
| 4 | 0:30 | Tier 3: three seeds of `paper_006` |
| 5 | 0:30 | Scoring a stored run honestly: "nothing was compared" |
| 6 | 0:30 | `cli.py diagnose`: the failure explained from the files |
| 7 | 0:40 | Tolerance probe: where the decision changes |
| 8 | 0:20 | The candidate papers: 0 of 14 |
| 9 | 0:40 | The limits, with their intervals |

## Step 1. The dashboard with the stored runs (0:30)

Commands (a fresh clone; the dashboard binds to `127.0.0.1` only; open `http://127.0.0.1:8000/`):

```text
$ python cli.py init-db
$ python scripts/build_demo_db.py
Wrote <REPO>/data/dashboard_demo.db: 13 papers, one score each (the best stored run).
  paper_002          Failed              62.75  Pilot 2 of 3 run(s)
  paper_003          Verified            97.00  Pilot 3 of 8 run(s)
  paper_004          Needs Review        82.75  memory run of 4 run(s)
  paper_005          Failed              62.75  Pilot 2 of 4 run(s)
  paper_006          Needs Review        86.50  Pilot 2 of 5 run(s)
  paper_008          Failed              62.75  Pilot 1 of 3 run(s)
  paper_101          Needs Review        78.25  Pilot 4 of 1 run(s)
  paper_102          Needs Review        82.75  Pilot 4 of 1 run(s)
  paper_103          Failed              54.00  Pilot 4 of 1 run(s)
  paper_104          Failed              62.75  Pilot 4 of 1 run(s)
  paper_105          Failed              54.00  Pilot 4 of 1 run(s)
  paper_106          Failed              58.25  Pilot 4 of 1 run(s)
  synthetic_control  Verified            88.75  synthetic run 1 of 2 run(s)
Start the dashboard: python -m src.web --db-url sqlite:///data/dashboard_demo.db
$ python -m src.web --db-url sqlite:///data/dashboard_demo.db
```

Screenshots (headless Chrome, 2026-10-28), in `docs/evidence/demo3/`: [`list.png`](evidence/demo3/list.png),
[`paper_003.png`](evidence/demo3/paper_003.png), [`paper_006.png`](evidence/demo3/paper_006.png),
[`paper_103.png`](evidence/demo3/paper_103.png), [`synthetic_control.png`](evidence/demo3/synthetic_control.png),
[`failures.png`](evidence/demo3/failures.png).

- List: `paper_003` shows "Claim compared: yes (1 of 3) - Tier 2: 100"; `paper_006` shows "Claim compared: no - Tier 2: 70 (baseline,
  nothing compared)" and the label `Needs Review`. Failed papers say "Run failed (category); no claim compared".
- `/papers/paper_003`, "Why this label": the claim `ft_transformer_rmse` 0.459 against 0.473 in the run, a difference of 3.05 %
  (within the 5 % rule); the ResNet and XGBoost claims have no counterpart, with the reason; Tier 3 is 100 from 3 stored seed runs,
  decided by `rmse`, the metric of an accepted claim; one claim and one number, not a confirmed reproduction.
- `/failures`: counts of why selected runs failed, with the selection-bias warning first. Not a success rate.
- The footer says that the database was built from stored runs, that the scores come from `src/scoring.py`, and what Needs Review means.

- Shows: why each label was given, from stored data only.
- Does **not** show: a set of reproduced papers or a success rate.

### Step 1 as recorded on 2026-10-24 (before the final dashboard)

Command (the dashboard binds to `127.0.0.1` only; open `http://127.0.0.1:8137/`):

```text
$ python -m src.web --port 8137
```

Screenshots taken from that page, headless Chrome, on 2026-10-24: [`docs/evidence/demo/dashboard_list.png`](evidence/demo/dashboard_list.png)
and [`docs/evidence/demo/dashboard_paper_006.png`](evidence/demo/dashboard_paper_006.png).

Expected: a table of the 6 seed papers. Five show "Not scored". `paper_006` shows **58.25, Needs Review**: that score is stored in the
local database by Step 5 below (the stored Pilot 3 run, scored against the 2 accepted claims). Its "Latest run" panel still shows the
Pilot 1 record of the database (FAILED, MISSING_DEPENDENCY), because the Pilot 2 and 3 records are not loaded into the database
(`README.md`): the score and the latest run on that page **do not belong to the same run**. Say so if it is asked.

- Shows: a local page that lists papers, scores, statuses and the latest run's failure category, and a per-paper breakdown.
- Does **not** show: a set of reproduced papers. The one score on the page is the "nothing was compared" score of Step 5. The page is a
  localhost tool, not a published leaderboard.

## Step 2. A true and a false claim on a run whose answer is known (0:40)

The synthetic control (`data/synthetic_control/`, `scripts/synthetic_control.py`): a tiny repository whose classifier prints
`accuracy: 0.9`, run twice in the real sandbox. Stored scores of a true claim (0.9) and a false claim (0.5):

```text
$ python -c "import json; d = json.load(open('data/synthetic_control/result.json')); [print(k, 'claim', v['claimed'], '-> reproduced', v['reproduced'], 'Tier 1/2/3/4', v['tier1_build'], v['tier2_metrics'], v['tier3_stability'], v['tier4_artifacts'], 'total', v['total_score'], v['status_label']) for k, v in d['scores'].items()]"
true_claim claim 0.9 -> reproduced {'accuracy': 0.9} Tier 1/2/3/4 100.0 100.0 75.0 70.0 total 91.75 Verified
false_claim claim 0.5 -> reproduced {'accuracy': 0.9} Tier 1/2/3/4 100.0 0.0 75.0 70.0 total 56.75 Needs Review

[exit code 0]
```

Scoring the stored run again, without the staged repository, gives the same Tier 2 and a total that is 3 points lower, because the
README is then unknown and counts as absent in Tier 4:

```text
$ python -c "from pathlib import Path; from src.score_run import load_run, score_run; d = Path('data/synthetic_control/run1/synthetic_control'); rec, rep = load_run(d); [print('claim', c, '-> Tier 2', r['breakdown'].tier2_metrics, 'total', r['breakdown'].total_score, r['breakdown'].status_label) for c in (0.9, 0.5) for r in [score_run('synthetic_control', 'MIT', {'accuracy': c}, rec, rep, d)]]"
claim 0.9 -> Tier 2 100.0 total 88.75 Verified
claim 0.5 -> Tier 2 0.0 total 53.75 Needs Review

[exit code 0]
```

- Shows: the scoring path works end to end on a case whose answer is known by construction (the true claim reaches Tier 2 = 100,
  the false one 0), and a defect that this control found in the scorer (a repository without requirements was counted as a failed install,
  fixed; `docs/report/REPORT.md` section 6.4).
- Does **not** show: that real papers are reproduced. The control is not a paper: it has no training, data or network. The claims
  are hand-made.

## Step 3. The same metrics in four runs of one paper (0:40)

```text
$ python scripts/run_stability.py
| Paper | Run | Status (exit) | Duration (s) | Peak memory (GiB) | Memory limit (GiB) | CPUs | Metrics |
|---|---|---|---|---|---|---|---|
| `paper_003` | Pilot 3 (`data/pilot3_runs/paper_003`) | COMPLETED (0) | 1516.673 | 1.11 | 6.0 | 2.0 | loss 0.106, rmse 0.473 |
| `paper_003` | memory re-run (`data/memory_runs/paper_003`) | COMPLETED (0) | 1497.443 | 1.09 | 13.93 | 2.0 | loss 0.106, rmse 0.473 |
| `paper_003` | memory re-run, second (`data/memory_runs/paper_003_run2`) | COMPLETED (0) | 1390.574 | 1.03 | 13.93 | 2.0 | loss 0.106, rmse 0.473 |
| `paper_003` | CPU run (`data/cpu_runs/paper_003`) | COMPLETED (0) | 465.777 | 1.15 | 13.93 | 8.0 | loss 0.106, rmse 0.473 |
| `paper_006` | Pilot 2 (`data/pilot2_runs/paper_006`) | COMPLETED (0) | 3122.657 | 0.65 | 6.0 | 2.0 | accuracy 0.8886, auroc 0.892 |
| `paper_006` | Pilot 3 (`data/pilot3_runs/paper_006`) | COMPLETED (0) | 3435.356 | 0.65 | 6.0 | 2.0 | accuracy 0.8886, auroc 0.892 |
| `paper_006` | memory re-run, second (`data/memory_runs/paper_006_run2`) | COMPLETED (0) | 3268.898 | 0.65 | 13.93 | 2.0 | accuracy 0.8886, auroc 0.892 |
| `paper_006` | CPU run (`data/cpu_runs/paper_006`) | COMPLETED (0) | 1119.834 | 0.64 | 13.93 | 8.0 | accuracy 0.8886, auroc 0.892 |

`paper_003`: 4 runs, status identical, exit code identical, metrics identical (loss 0.106, rmse 0.473); 3 of 9 log files identical (line endings ignored) with the first r [...]

[exit code 0]
```

Expected: `paper_003` and `paper_006` each have four completed runs (Pilot 2 or Pilot 3, memory re-runs, and an 8-CPU run) with
identical status, exit code and metrics (`loss 0.106, rmse 0.473`; `accuracy 0.8886, auroc 0.892`), with different durations
(for example `paper_006`: 3435 s with 2 CPUs and 1120 s with 8).

- Shows: two papers run in the sandbox complete and print the same numbers every time (a deterministic seed).
- Does **not** show: that the numbers are the paper's. `paper_006` trained on a Bank dataset while its accepted claims concern Arcene;
  `docs/report/REPORT.md` section 6.3. The identical rows are one deterministic run repeated, not independent evidence.

## Step 4. Tier 3: three seeds of `paper_006` (0:30)

```text
$ python -c "import json; d = json.load(open('data/multi_seed_runs/paper_006/multi_seed_summary.json')); [print(m, 'seeds', v['seeds'], 'values', v['values'], 'mean', round(v['mean'], 4), 'cv', round(v['cv'], 4)) for m, v in d['metrics'].items()]"
accuracy seeds [1, 2, 3] values [0.8886, 0.8944, 0.8929] mean 0.892 cv 0.0028
auroc seeds [1, 2, 3] values [0.892, 0.911, 0.905] mean 0.9027 cv 0.0088

[exit code 0]
```

- Shows: Tier 3 on real runs: the paper's own seed parameter was varied (1, 2, 3), one real run per seed
  (`data/multi_seed_runs/paper_006/`, `docs/MULTI_SEED.md`), and the coefficient of variation is computed from the values (0.28 % and 0.88 %).
- Does **not** show: stability of the paper's claims (the seeds are 3, the claims are about Arcene), or anything about papers without a
  seed parameter of their own: those are not run with several seeds.

## Step 5. Scoring a stored run honestly (0:30)

```text
$ python cli.py score paper_006 --from-run data/pilot3_runs/paper_006

Evaluating reproducibility for: [paper_006] SAINT: Improved Neural Networks for Tabular Data via Row Attention and Contrastive Pre-Training
Scoring the stored run in data\pilot3_runs\paper_006 (no new run).
Accepted claims of this paper (accepted by a person): 2
Run: stage=STAGED build=BUILT install=INSTALLED run=COMPLETED exit_code=0
  [tier1] Repository cloned successfully (+25)
  [tier1] Dependencies installed successfully (+25)
  [tier1] Target script invoked (+25)
  [tier1] Clean execution with exit code 0 (+25)
  [tier2] Metric 'arcene_auroc' was not found in reproduced outputs.
  [tier2] Metric 'xgboost_arcene_auroc' was not found in reproduced outputs.
  [tier3] Single seed verified without errors; baseline stability score assigned (75.0)
  [tier4] Permissive open source license verified (Apache-2.0) (+30)
  [tier4] Environment definition present (requirements.txt / pyproject.toml / env.yml) (+30)
  [tier4] Missing README or instructions (0/20)
  [tier4] Structured output artifacts / execution logs captured (+20)

----------------- SCORING BREAKDOWN -----------------
Tier 1 (Build & Environment)  : 100.00 / 100 (Weight: 35%)
Tier 2 (Metrics Alignment)    :   0.00 / 100 (Weight: 35%)
Tier 3 (Seed Stability)       :  75.00 / 100 (Weight: 15%)
Tier 4 (Artifacts & License)  :  80.00 / 100 (Weight: 15%)
-----------------------------------------------------
TOTAL COMPOSITE SCORE         :  58.25 / 100
STATUS CLASSIFICATION         : [Needs Review]
SUMMARY / AI RATIONALE        : Needs Review (Total: 58.25/100). Code executed cleanly, but claimed metrics not found in the output (nothing was compared).
-----------------------------------------------------


[exit code 0]
```

- Shows: the build tiers are real (Tier 1 = 100 from a real run), and when no claim's name occurs in the output, the tool says
  "claimed metrics not found in the output (nothing was compared)" instead of reporting a divergence that was never measured.
- Does **not** show: a reproduced result. Tier 2 = 0 here is "nothing compared" (the claims are about Arcene, the run is on Bank). This
  command also stores the score in the local database (ignored by git), which is why Step 1 shows 58.25.

## Step 6. `cli.py diagnose` (0:30)

```text
$ python cli.py diagnose data/pilot3_runs/paper_004
# Diagnosis of `data/pilot3_runs/paper_004`

## What ran
- The run is of `paper_004` under `docs/PILOT_3.md`. *(source: pilot_record.json: paper_id; pilot_record.json: protocol)*
- The container command was `python /workspace/repo/bin/tabr.py exp/tabr/california/0-evaluation/0.toml --force`. *(source: pilot_record.json: container_command)*
- The sandbox image used Python 3.9. *(source: pilot_record.json: python_version)*
- The record runs from 2026-10-13T00:03:50+00:00 to 2026-10-13T03:18:05+00:00. *(source: pilot_record.json: started_at; pilot_record.json: finished_at)*

## How the phases ended
- Fetching the repository ended with status STAGED. *(source: pilot_record.json: stage.status)*
- The dependency install ended with status INSTALLED. *(source: run_report.json: dependency_install_status)*
- The run phase ended with status OOM_KILLED and exit code 137 after 9018.12 s. *(source: run_report.json: status; run_report.json: exit_code; run_report.json: duration_seconds)*

## Category of the outcome
- The classifier assigned the category OUT_OF_MEMORY in the run phase: the container was stopped at its memory limit. *(source: src/diagnosis/classifier.py applied to the run files)*
- The deciding line is `run_report.json`: `status: OOM_KILLED` *(source: run_report.json)*
- The category is the classifier's reading of that line; a cause behind the line was not investigated. *(source: src/diagnosis/classifier.py)*

## Limits and resources
- The container had 2 CPUs and a memory limit of 6g. *(source: pilot_record.json: limits.cpus; pilot_record.json: limits.memory_limit)*
- The time limit of the run phase was 14400 s. *(source: run_report.json: meta.timeout_limit_seconds)*
- The measured peak memory of the run was 6.00 GiB. *(source: run_report.json: meta.peak_memory_bytes)*

## Metrics and claims
- The metric extractor found these numbers in the output: lr 0.0003, weight_decay 0. The extractor reads names and numbers from the log; a number it found is not necessarily a result of the paper. *(source: run_report.json: metric [...]
- Claim `tabr_average_rank` (claimed 1.3): no metric with this name was found in the output, so nothing was compared for it. A differently named metric may measure the same thing; this report does not match names by meaning. *(sou [...]
- Claim `xgboost_average_rank` (claimed 2.5): no metric with this name was found in the output, so nothing was compared for it. A differently named metric may measure the same thing; this report does not match names by meaning. *( [...]

## Last lines of stderr
- `stderr.log:4346`: `Epoch 78:  98%|█████████▊| 51/52 [01:34<00:01,  1.82s/it]` *(source: stderr.log:4346)*
- `stderr.log:4347`: `Epoch 78: 100%|██████████| 52/52 [01:35<00:00,  1.60s/it]` *(source: stderr.log:4347)*
- `stderr.log:4348`: `Epoch 78: 100%|██████████| 52/52 [01:35<00:00,  1.83s/it]` *(source: stderr.log:4348)*

This report is rule-based: every sentence is written from the stored files of the run named above. Nothing was inferred beyond them, and a cause that no stored line states was not investigated.
[... 2 more lines of the output are not shown here]
```

- Shows: a rule-based explanation (no model, no network) in which every sentence names the file and key it was read from, quotes the
  deciding line, and says "no metric with this name was found" instead of guessing a match.
- Does **not** show: a cause. The category is the classifier's reading of one log line ("a cause behind the line was not
  investigated"); `docs/DIAGNOSIS.md` and `docs/DIAGNOSIS_VALIDATION.md` give what was and was not validated (a hand-labeled set).

## Step 7. Tolerance probe: where the decision changes (0:40)

```text
$ python scripts/tolerance_probe.py --check
tolerance probe files match the stored runs

[exit code 0]
```

The rows for `paper_006` (the four stored runs have the same values), from `data/tolerance_probe/results.json`:

```text
$ python -c "import json; d = json.load(open('data/tolerance_probe/results.json')); run = [r for r in d['runs'] if r['paper_id'] == 'paper_006'][0]; print(run['metrics']); [print(format(x['deviation_percent'], '+g'), '%', 'Tier 2', x['tier2'], 'total', x['total'], x['status']) for x in run['rows']]"
{'accuracy': 0.8886, 'auroc': 0.892}
+0 % Tier 2 100.0 total 93.25 Verified
-0.5 % Tier 2 100.0 total 93.25 Verified
+0.5 % Tier 2 100.0 total 93.25 Verified
-1 % Tier 2 100.0 total 93.25 Verified
+1 % Tier 2 100.0 total 93.25 Verified
-2 % Tier 2 100.0 total 93.25 Verified
+2 % Tier 2 100.0 total 93.25 Verified
-5 % Tier 2 100.0 total 93.25 Verified
+5 % Tier 2 100.0 total 93.25 Verified
-10 % Tier 2 50.0 total 75.75 Partially Verified
+10 % Tier 2 50.0 total 75.75 Partially Verified
-20 % Tier 2 0.0 total 58.25 Needs Review
+20 % Tier 2 0.0 total 58.25 Needs Review

[exit code 0]
```

The tolerance rule (`docs/TOLERANCE_PROBE.md` section 1): 5 % relative to the claimed value, with an absolute allowance of 0.05 for a
claim between 0 and 1; a time-named metric has no absolute allowance.

- Shows: with these values a hand-moved claim is still MATCHED up to 5 %, becomes PARTIAL at 10 % (status Partially Verified) and DIVERGED
  at 20 % (Needs Review); a small value between 0 and 1 stays MATCHED far beyond 5 % (`docs/TOLERANCE_PROBE.md` section 2).
- Does **not** show: how often the scorer is right on real papers. **These are hand-made claims, not an error of a real paper; the
  false-positive and false-negative rates in the real world have not been measured.** No accepted claim of a real paper matches a stored run.

## Step 8. The candidate papers: 0 of 14 (0:20)

```text
$ python -c "import json; r = json.load(open('data/candidates/runs/evaluation.json'))['results']; print('selected', len(r), 'run', sum(1 for x in r if x['category'] != 'command_incomplete'), 'passed', sum(1 for x in r if x['passed'])); [print(x['paper_id'], x['category'], '|', x['log_line'][:90]) for x in r]"
selected 14 run 13 passed 0
cand_001 run | ModuleNotFoundError: No module named 'igraph'
cand_002 install | ERROR: No matching distribution found for Bottleneck==1.3.5
cand_003 run | OSError: [Errno 30] Read-only file system: 'data/Tmall_train'
cand_004 run | FileNotFoundError: [Errno 2] No such file or directory: './SysID/scripts/examples/toy_sysi
cand_005 install | ERROR: No matching distribution found for absl-py==0.9.0
cand_006 run | ModuleNotFoundError: No module named 'torch'
cand_007 run | OSError: [Errno 30] Read-only file system: '../../outputs'
cand_008 install | ERROR: No matching distribution found for python>=3.9.6
cand_009 run | ModuleNotFoundError: No module named 'botorch'
cand_010 install | ERROR: No matching distribution found for tensorflow==2.4.0
cand_011 install | ERROR: ResolutionImpossible: for help visit https://pip.pypa.io/en/latest/topics/dependenc
cand_012 install | ERROR: No matching distribution found for torch==0.4.1
cand_013 command_incomplete | command_incomplete: the README line holds only placeholders (DATASET_NAME, YOUR_RUN_TIMES,
cand_025 run | FileNotFoundError: [Errno 2] No such file or directory: '/workspace/home/data/UEA_multivar

[exit code 0]
```

- Shows: of 29 candidate papers collected by the owner, the 14 that the lists call ready or fixable were run once each in the sandbox
  by a protocol that was merged before the first run (`docs/CANDIDATE_RUNS.md`): 0 passed, with their failure lines. **No candidate
  passed, so there is no candidate example in this demo.**
- Does **not** show: that these papers cannot be reproduced. No repair was allowed; the candidates were chosen by others, so this is not a
  sample and 0 of 14 is not a success rate.

## Step 9. The limits, with their intervals (0:40)

```text
$ python scripts/pilot4_report.py
<!-- Generated by scripts/pilot4_report.py from data/pilot4_runs/ and the stored measurements of Pilots 1 to 3; do not edit by hand. -->

| Measure | Pilot 1 | Pilot 2 | Pilot 3 | Pilot 4, first attempt | Pilot 4, after one correction round |
|---|---|---|---|---|---|
| Install success | 1 / 6 (0.167) | 6 / 6 (1.0) | 6 / 6 (1.0) | 2 / 6 (0.333) | 3 / 6 (0.5) |
| Run success | 0 / 6 (0.0) | 1 / 6 (0.167) | 2 / 6 (0.333) | 2 / 6 (0.333) | 2 / 6 (0.333) |
[... 23 more lines of the output are not shown here]
```

```text
$ python -c "from scripts.candidates_build import wilson_interval as w; [print(label, k, 'of', n, '-> Wilson 95 % interval', round(100 * w(k, n)[0], 1), 'to', round(100 * w(k, n)[1], 1), '%') for label, k, n in (('Pilot 4 first attempt', 1, 6), ('Pilot 3', 2, 6), ('Candidates', 0, 14))]"
Pilot 4 first attempt 1 of 6 -> Wilson 95 % interval 3.0 to 56.4 %
Pilot 3 2 of 6 -> Wilson 95 % interval 9.7 to 70.0 %
Candidates 0 of 14 -> Wilson 95 % interval 0.0 to 21.5 %

[exit code 0]
```

```text
$ python -c "import json; d = json.load(open('data/external_validation/evaluation.json')); print('ReScience C articles evaluated', d['evaluated'], 'selected', d['selected'], '(rules', d['rules'] + ')')"
ReScience C articles evaluated 65 selected 0 (rules docs/EXTERNAL_VALIDATION.md)

[exit code 0]
```

```text
$ python scripts/report_numbers.py --check
{"in_sync": true, "blocks_that_differ": []}

[exit code 0]
```

- Shows: the headline numbers are small and wide. Pilot 4 (6 new papers, first attempt, README command as written) is **1 of 6**, and 1 of 6 has a
  Wilson 95 % interval of 3.0 % to 56.4 %; Pilot 3 is 2 of 6 (9.7 % to 70.0 %), and that one used four settings chosen after Pilot 2's failures.
  An attempt to take independent reference articles from ReScience C selected **0 of 65**. Every number of the report is generated
  (`report_numbers.py --check` finds no difference).
- Does **not** show: a rate for the field. The papers were chosen, six at a time, and the intervals are wide. The claim that the
  scorer's decision is right on a known example is made only on the synthetic control and the hand-made rows of Step 7. The claim of
  how many papers run is made only on these small, selected sets.

## What to say at the end

Two claims are made separately and are not mixed: (1) how many papers run (1 of 6 in Pilot 4, 2 of 6 in Pilot 3, 0 of 14 candidates;
all selected sets, wide intervals), and (2) that the scorer decides correctly on a known example (the synthetic control, and hand-moved
claims on real runs). What is **not** done: a claim of a real paper reproduced in a real run and accepted by the owner (the "correct
example in a real paper" is still missing), and no rate of false positives or negatives on real papers.
