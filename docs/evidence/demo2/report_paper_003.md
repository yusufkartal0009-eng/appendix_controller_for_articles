# Reproducibility audit: paper_003

Revisiting Deep Learning Models for Tabular Data (NeurIPS 2021, 2021)

Generated 2026-10-25 17:11 from the project database.

## Summary

Score 58.25 / 100 - Needs Review

[demo database] Pilot 3 (data/pilot3_runs/paper_003), the best of 8 stored run(s) of this paper. Claims are matched by question ID as in cli.py score; Tier 4 is computed without the staged repository. Needs Review (Total: 58.25/100). Code executed cleanly, but claimed metrics not found in the output (nothing was compared).

## Score breakdown

| Part | Score (0-100) |
|---|---|
| Build (tier 1) | 100 |
| Metrics (tier 2) | 0 |
| Stability (tier 3) | 75 |
| Artifacts (tier 4) | 80 |
| **Total** | **58.25** |

## Latest run

| Field | Value |
|---|---|
| Run | paper_003@pilot3_runs/paper_003 |
| Status | COMPLETED |
| Exit code | 0 |
| Duration | 1516.67 s |
| Failure category | - |
| Seed | 42 |
| Started | 2026-10-12 23:18:15 |

Standard output (last 20 lines):

```
[val  ] score = -0.483 | rmse = 0.483
[test ] score = -0.479 | rmse = 0.479

>>> Epoch 77 | 0:24:15 | /workspace/output/ft_transformer_default_0
lr = 0.0001 | batch_size = 256 | chunk_size = None | epoch_size = 52 | n_parameters = 893179
[train] loss = 0.108
[val  ] score = -0.483 | rmse = 0.483
[test ] score = -0.477 | rmse = 0.477

>>> Epoch 78 | 0:24:34 | /workspace/output/ft_transformer_default_0
lr = 0.0001 | batch_size = 256 | chunk_size = None | epoch_size = 52 | n_parameters = 893179
[train] loss = 0.106
[val  ] score = -0.482 | rmse = 0.482
[test ] score = -0.485 | rmse = 0.485

Running the final evaluation...
[train] score = -0.363 | rmse = 0.363
[val  ] score = -0.473 | rmse = 0.473
[test ] score = -0.473 | rmse = 0.473
Done!
```

Standard error (last 20 lines):

```
  0%|          | 4038/52000000000 [24:44<4868947:06:28,  2.97it/s]
  0%|          | 4039/52000000000 [24:45<4769395:00:52,  3.03it/s]
  0%|          | 4040/52000000000 [24:45<4677810:59:47,  3.09it/s]
  0%|          | 4041/52000000000 [24:45<4932461:07:25,  2.93it/s]
  0%|          | 4042/52000000000 [24:46<4788176:59:16,  3.02it/s]
  0%|          | 4043/52000000000 [24:46<4681766:28:05,  3.09it/s]
  0%|          | 4044/52000000000 [24:46<4933882:43:47,  2.93it/s]
  0%|          | 4045/52000000000 [24:47<4781760:18:53,  3.02it/s]
  0%|          | 4046/52000000000 [24:47<4695455:05:10,  3.08it/s]
  0%|          | 4047/52000000000 [24:47<4618857:10:37,  3.13it/s]
  0%|          | 4048/52000000000 [24:48<4837362:21:13,  2.99it/s]
  0%|          | 4049/52000000000 [24:48<4718761:31:41,  3.06it/s]
  0%|          | 4050/52000000000 [24:48<4665201:08:23,  3.10it/s]
  0%|          | 4051/52000000000 [24:49<4586670:11:56,  3.15it/s]
  0%|          | 4052/52000000000 [24:49<4826520:29:42,  2.99it/s]
  0%|          | 4053/52000000000 [24:49<4745919:01:49,  3.04it/s]
  0%|          | 4054/52000000000 [24:50<4640576:25:25,  3.11it/s]
  0%|          | 4055/52000000000 [24:50<4582462:56:55,  3.15it/s]
  0%|          | 4056/52000000000 [24:50<4850172:45:31,  2.98it/s]
  0%|          | 4056/52000000000 [25:00<5342343:01:15,  2.70it/s]
```

## Claims

No claim comparison is stored for this paper.

## Integrity

- Outputs SHA-256: `not recorded`
- Run manifest SHA-256: `not recorded`

## Links

- Repository: https://github.com/yandex-research/rtdl-revisiting-models
- Paper: https://arxiv.org/abs/2106.11959
