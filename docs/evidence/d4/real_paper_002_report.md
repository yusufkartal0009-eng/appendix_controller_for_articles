# Reproducibility audit: paper_002

TabPFN: A Transformer That Solves Small Tabular Classification Problems in a Second (ICLR 2023, 2022)

Generated 2026-10-15 11:20 from the project database.

## Summary

Not scored

## Score breakdown

No score is stored for this paper.

## Latest run

| Field | Value |
|---|---|
| Run | pilot-36759195752-paper_002 |
| Status | FAILED |
| Exit code | 1 |
| Duration | 0.975 s |
| Failure category | MISSING_DEPENDENCY |
| Seed | 42 |
| Started | 2026-09-30 18:32:15 |

Standard error (last 20 lines):

```
Traceback (most recent call last):
  File "/workspace/repo/tabpfn/scripts/tabular_baselines.py", line 6, in <module>
    from catboost import CatBoostClassifier, Pool
ModuleNotFoundError: No module named 'catboost'
```

## Claims

No claim comparison is stored for this paper.

## Integrity

- Outputs SHA-256: `not recorded`
- Run manifest SHA-256: `not recorded`

## Links

- Repository: https://github.com/PriorLabs/TabPFN
- Paper: https://arxiv.org/abs/2207.01848
