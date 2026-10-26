# Claim-to-Run-Metric Map

> Written for #507 (finding of docs/REAL_VERDICTS.md, PENDING D12). The data is `data/claim_metric_map.json`. This is a
> proposal: the owner may revise any row. Nothing here changes an accepted claim.

## 1. Why a separate file

An accepted claim is stored under a question ID (`ft_transformer_rmse`); a run's metrics are stored under the name the metric
extractor found in the output (`rmse`). The two never agreed, so `cli.py score` compared no real claim (Tier 2 was 0 and the
label `Needs Review` for every real run). The two key spaces cannot be unified by renaming either side:

- `data/seed_papers.json` must not change, and
- `data/claims/review_decisions.json` holds decisions a person made; changing a key there would alter accepted records.

So the pairing lives in its own file, next to the claims, and says for each accepted claim what the run counterpart is.

## 2. The rule

A claim is mapped to a run metric only by **identity**, never by closeness of the values:

- same **model** (the claim's `model_variant`),
- same **dataset**,
- same **measure** (RMSE, AUROC, an average rank, a time ...), and
- same **split** (test or validation), shown by the log and by the extractor code.

If any of these differs, or the run produced no number at all, the decision is `no_counterpart`. When unsure the entry is
`no_counterpart` and the reason says so (not verified). Every entry carries evidence: a string that occurs in a stored run file
(`tests/test_claim_metric_map.py` checks that each string is still there).

## 3. Decisions

13 accepted claims: **1 `map`, 12 `no_counterpart`**.

| Paper | Claim (question ID) | Decision | Run metric | Reason | Evidence |
|---|---|---|---|---|---|
| paper_002 | `inference_seconds__cpu` | no_counterpart | - | the notebook run failed before any metric was printed (no network for OpenML) | `data/pilot3_runs/paper_002/stderr.log`: `Failed to resolve 'www.openml.org'` |
| paper_002 | `inference_seconds__gpu` | no_counterpart | - | same; also a GPU timing | same |
| paper_002 | `mean_roc_auc` | no_counterpart | - | same | same |
| paper_003 | `ft_transformer_rmse` | **map** | `rmse` | FT-Transformer on California Housing; the last `rmse` line is the final test RMSE | `data/pilot3_runs/paper_003/stdout.log`: `Config: .../california_housing/ft_transformer/default/0.toml`, `[test ] score = -0.473 \| rmse = 0.473` |
| paper_003 | `resnet_rmse` | no_counterpart | - | the run trains FT-Transformer only | same log: `Output: /workspace/output/ft_transformer_default_0` |
| paper_003 | `xgboost_rmse` | no_counterpart | - | the run trains FT-Transformer only | same |
| paper_004 | `tabr_average_rank` | no_counterpart | - | claim is an average rank over a benchmark; the run is one TabR training on one dataset | `data/memory_runs/paper_004/stdout.log`: `'path': ':data/california'` |
| paper_004 | `xgboost_average_rank` | no_counterpart | - | average rank of XGBoost; the run is TabR on one dataset | same |
| paper_005 | `ep300_avg_kernel_speedup` | no_counterpart | - | run killed for memory (exit 137), no speed-up factor printed | `data/pilot3_runs/paper_005/pilot_record.json`: `"status": "OOM_KILLED"` |
| paper_006 | `arcene_auroc` | no_counterpart | - | claim is on Arcene; the run reads OpenML dataset 1461 (bank-marketing) | `data/pilot3_runs/paper_006/stdout.log`: `dset_id=1461` |
| paper_006 | `xgboost_arcene_auroc` | no_counterpart | - | XGBoost on Arcene; the run trains SAINT on dataset 1461 | same |
| paper_008 | `forest_covertype_accuracy__danet_20` | no_counterpart | - | run failed while loading data (CSV missing), no metric printed | `data/pilot3_runs/paper_008/stderr.log`: `No such file or directory: './data/forest_cover_type/forest-cover-type.csv'` |
| paper_008 | `forest_covertype_accuracy__danet_32` | no_counterpart | - | same | same |

## 4. The one mapped claim: `paper_003` / `ft_transformer_rmse`

- The claim: FT-T RMSE 0.459 on California Housing, Table 2, page 7.
- The run: `src/metric_extractor.py` (`extract_metrics`) keeps the *last* occurrence of a metric name. The last `rmse` line of the
  log (line 502 in each of the six stored runs) is `[test ] score = -0.473 | rmse = 0.473`, the final test evaluation. The line
  before it is the validation evaluation and prints the same 0.473, so the split cannot change the number here.
- The six stored runs (`pilot3_runs`, `memory_runs` x2, `cpu_runs`, `env_cache_runs` x2) all report `rmse = 0.473`.
- This is one claim and one number. A 3.05% gap inside the 5% tolerance is not an exact reproduction, and the mapping says
  nothing about whether the tolerance is the right one.

## 5. Limits

- The decisions are per paper, not per run: if a future run of a paper reads another dataset, the entry must be revised.
- `paper_004`: the run's own California result (a test RMSE in its log) is not a claim anyone accepted; it is not mapped.
- `paper_006`: the stored `auroc` is the last logged test line, not the run's "AUROC on best model" (see docs/REAL_VERDICTS.md).
  Irrelevant to the map today (no counterpart), relevant once an accepted claim for Bank exists.
- New accepted claims need a new entry; the test fails until one is added.
