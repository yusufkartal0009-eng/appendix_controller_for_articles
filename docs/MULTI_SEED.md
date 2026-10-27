`# Multi-seed execution (Tier 3)
`
`Issue: #48. Status: design (written before the implementation; the implementation is a separate pull request).
`
`## 1. Why
`
`Tier 3 of the rubric (`src/scoring.py`, weight 15%) asks how much a paper's result moves when only the random seed changes.
`Until now the runner executed a paper once, so `Tier3StabilityEvaluator` always took its single-run branch and assigned a
`fixed 75.0. That number is a placeholder, not a measurement. This design replaces the placeholder with real seed runs
`where the paper allows them.
`
`## 2. The paper's own seed parameter (`run_setup`)
`
`Repro Radar never edits a paper's code to inject a seed. A paper can be run with several seeds only if the paper itself
`exposes one. The seed parameter is recorded in the paper's run setup as an optional `seed` object:
`
````json
`"seed": {
`  "values": [1, 2, 3],
`  "arg": "--set_seed",
`  "source": "train.py line 36: parser.add_argument('--set_seed', default=1, type=int)"
`}
````
`
`- `values`: the list of seeds, at least two integers, all different.
`- `arg`: the command-line option that carries the seed. The runner appends `<arg> <seed>` to the script arguments.
`- `args`: optional. A replacement argument list in which every `{seed}` is replaced by the seed. It is for papers whose
`  seed is not an option but a configuration file chosen by the arguments (for example `.../default/{seed}.toml`, where
`  every file of the repository holds a different `seed = N`).
`- `source`: where in the paper's own files the seed parameter was found. A `seed` object without a `source` is rejected.
`
`A paper without a `seed` object has no seed parameter that Repro Radar knows of: it is run once, and Tier 3 keeps its
`single-run behavior (section 6).
`
`The run setups of `data/seed_papers.json` are not edited for this (that file is protected). The per-paper seed objects for
`the seed papers are stored in `data/multi_seed_settings.json`, which is applied on top of the run setup, in the same way
``data/pilot3_settings.json` is.
`
`## 3. The runner
`
``scripts/run_multi_seed.py <paper_id>` runs the paper once per seed, one after the other:
`
`1. read the seed object (overlay file or the entry's `run_setup`);
`2. for each seed, make a copy of the paper's entry with the seed applied (section 2) and call `run_pilot.run_paper` with it,
`   with the same limits (`--memory`, `--cpus`, `--pilot3`, `--run-timeout`) for every seed;
`3. store each run **as its own record** in `data/multi_seed_runs/<paper_id>/seed_<N>/` (the same files as any pilot run:
`   `pilot_record.json`, `run_report.json`, the logs). The record notes the seed (`multi_seed.seed`);
`4. after the last seed, write `data/multi_seed_runs/<paper_id>/multi_seed_summary.json`.
`
`A seed run that does not complete (status other than `COMPLETED`, or no metrics) is kept as a record and listed in the
`summary as failed; it contributes no value. The runner does not retry.
`
`## 4. The summary: mean, standard deviation, coefficient of variation
`
`For every metric name that the metric extractor found in **all** successful seed runs, the summary holds the value of each
`seed, the mean, the standard deviation, and the coefficient of variation (CV = standard deviation / |mean|, with the same
`floor of 1e-6 on the denominator as `Tier3StabilityEvaluator`).
`
`The standard deviation is the **population** standard deviation (divisor n), the one `Tier3StabilityEvaluator` already
`uses. The summary also stores the sample standard deviation (divisor n - 1) under a separate name, so that both can be
`read; the score uses the population one. With 3 to 5 seeds the two differ noticeably, which is why both are shown.
`
`Metric names are those of `run_report.json` (`metrics`), compared exactly, as Tier 2 does.
`
`**Which metric decides, and what each one alone would give (added with the first real seed runs).** The metrics are the numbers
`the metric extractor found in the output, and for a training script they include values such as the last printed training loss,
`not only the headline result. Because the metric with the largest CV decides, a noisy side number can set Tier 3 although the
`headline metric hardly moves. The summary therefore stores `tier3.decided_by` (the metric that decided) and `tier3_by_metric`
`(the CV of every metric and the score that metric alone would give), so that the reader can see both. The score itself still
`follows section 5; this only makes the choice visible. `python scripts/run_multi_seed.py <paper_id> --summarize-only` rebuilds the
`summary from the stored seed folders without Docker.
`
`## 5. Connecting `seed_results` to real seed results
`
``src/scoring.py` takes `seed_results: list[float]`. It stays as it is (one list, one metric), and a new optional input is
`added next to it:
`
`- `ReproducibilityScorer.evaluate_paper_run(..., seed_metric_results: dict[str, list[float]] | None = None)`.
`  The key is a metric name, the value the metric's value in each successful seed run.
`- `Tier3StabilityEvaluator.evaluate_by_metric(seed_metric_results, ...)` computes the CV of every metric with at least two
`  values and scores the metric with the **largest CV**. A paper is as stable as its least stable metric; this is the
`  conservative reading and it is a design choice, not a property of the rubric. The notes name the metric that decided.
`- The CV thresholds are unchanged (<= 2% -> 100, <= 5% -> 85, <= 10% -> 65, otherwise 40).
`- `src/score_run.py` accepts the summary of a multi-seed run and passes its values on. `seed_results=None` in
`  `score_run` stays the default for a single run.
`
`The rule applies to metrics, not to claims: Tier 3 does not need an accepted claim, because stability is a property of the
`paper's own repeated runs. (Tier 2 still needs claims.)

### 5a. The claimed metric decides (K-A, #542)

**Default chosen by the assistant, the owner may revise (`docs/PENDING.md`, D7).** The largest-CV rule let a side number decide
(`paper_003`: the last printed training loss, CV 7.4 %, Tier 3 = 65, while the claimed `rmse` has CV 0.70 % and alone gives 100).
Since #542:

- If an accepted claim of the paper is mapped (`data/claim_metric_map.json`, decision `map`, `docs/CLAIM_METRIC_MAP.md`) to a run
  metric that has at least two seed values, only the mapped metric(s) decide Tier 3. With more than one mapped metric, the one with
  the largest CV among them decides.
- Without an accepted claim, without a `map` decision for this paper, or when no mapped metric has seed values, the rule of section 5
  applies unchanged (the largest CV of all metrics).
- Without a stored multi-seed record the behavior is unchanged: Tier 3 is the 75.0 single-run baseline.
- `cli.py score`, `src/score_run.py` (through `seed_metric_results`), `scripts/real_verdicts.py` and `scripts/build_demo_db.py` read the
  stored record with `src.multi_seed.load_seed_metric_results` (`data/multi_seed_runs/<paper_id>/multi_seed_summary.json`, or
  `cli.py score --multi-seed-dir`). A summary that exists but cannot be used (not JSON, no `metrics`, a metric without numeric `values`)
  stops the command with a message; it is never ignored, because that would silently score the paper as a single run.
- The record belongs to the paper, not to one run: any successful stored run of the paper is scored with it. A failed run keeps Tier 3 = 0.
- `multi_seed_summary.json` is a record of the seed runs and keeps its own rule (`tier3.decided_by` is the largest-CV metric, and
  `tier3_by_metric` shows every metric alone); it is not rewritten. The score of the scorer for `paper_003` is therefore 100 while the
  summary file says 65 under the older rule; the Tier 3 notes of each say which metric decided.
- Result on the stored records: `paper_003` Tier 3 = 100 (65 under the largest-CV rule, 75 as a single-run baseline);
  `paper_006` Tier 3 = 100 (its two accepted claims have no counterpart, so the largest-CV rule applies: `auroc`, CV 0.88 %).
`
`## 6. Why the single-run baseline of 75.0 changes
`
`The 75.0 was assigned when exactly one run existed: "ran without errors once" was treated as three quarters of stability.
`Nothing was measured, and a paper can be anywhere between 40 and 100 once its seeds are varied. After this change:
`
`- **Two or more successful seed runs:** Tier 3 is computed from the measured CV (section 5). A stable paper rises above 75
`  (85 or 100), a moderately unstable one falls below it (65), a very unstable one falls to 40. The baseline no longer
`  applies.
`- **Fewer than two successful seed runs** (the paper has no seed parameter, or the seed runs failed): the 75.0 stays, so
`  that existing stored scores do not change meaning. The Tier 3 note says it is a baseline for "one clean run", and
`  the report must not call it a stability measurement.
`- A paper whose run failed keeps Tier 3 = 0 as before.
`
`## 7. What this does not do
`
`- It does not make an unseeded paper deterministic. A paper whose seed parameter does not control all of its randomness
`  (data split, GPU kernels, library defaults) can show a CV of zero or a nonzero CV for reasons other than its seed
`  setting; the summary reports what happened, not the cause.
`- It does not choose seeds by their results. The seeds are written in the settings before the runs.
`- It does not run a paper under a changed protocol: limits are the same for every seed, and they are recorded in each record.
`- A few seeds (the plan uses 3 for the real papers, 5 for the synthetic ones) give a rough CV. The tiers are thresholds on
`  a number estimated from very few runs.
`
`## 8. Evidence plan
`
`1. Two synthetic repositories (one that ignores its seed, one whose metric comes from `random.Random(seed)`) run for 5
`   seeds in real Docker; the summary is compared with the mean and standard deviation computed on the host from the same
`   seeds. Tier 3 must differ between the two.
`2. `paper_003` (seeds are the configuration files `0.toml`, `1.toml`, `2.toml`) and `paper_006` (`--set_seed`) with 3
`   seeds each, if their runs complete. The records go to `data/multi_seed_runs/`. These are not protocol runs: the memory
`   and CPU limits differ from the protocol's, and the records say so.
`
`## 9. Stored evidence

Real seed runs are stored under `data/multi_seed_runs/<paper_id>/` (one folder per seed with the pilot record, the run report, and the logs; `multi_seed_summary.json` for the paper). Local paths in the records were replaced by `<REPO>` and `<HOME>` before they were committed. The synthetic papers are in `data/synthetic_seeds/`. The numbers are in the generated block of `docs/report/REPORT.md` (section 6.4a) and in `docs/DIAGNOSIS_COMPARISONS.md` (each seed against the first).

- `paper_003`: three seeds (0, 1, 2), the configuration files `0.toml` to `2.toml`, run with `--pilot3 --memory 50% --cpus 4 --run-timeout 14400` on one machine. Seed 0 gave the same metrics as every earlier single run of the paper (it is the same configuration file). Seed 0 was run at tool commit 803d4e2 and seeds 1 and 2 at 7678f08; the two commits differ only in `cli.py` (the `diagnose` command) and `src/diagnosis/`, outside the run path, and each record keeps its own `repro_radar_commit`.

- `paper_006`: three seeds (1, 2, 3) of `--set_seed`, run with `--pilot3 --memory 50% --cpus 4 --run-timeout 14400` on the same machine, one after the other, while the seed runs of `paper_003` were also running (two containers at once, so the run times are not clean). Seed 1 is the default of the option and gave the same metrics as every earlier single run of the paper. All three seeds ran at tool commit 7678f08.
