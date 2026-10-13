# Pilot 3: earlier attempts

Kept as evidence (docs/PILOT_3.md section 8). Not counted.

| Attempt | Paper | Repro Radar commit | How it ended | Why it was superseded |
|---|---|---|---|---|
| `paper_002_attempt1` | `paper_002` | `cb9fe9b` | `OUTPUT_LIMIT_EXCEEDED` after 0.87 s; the run never started the paper (`run_report.json`: "The output directory reached 3202 MiB; the limit is 1024 MiB") | A defect of Repro Radar, not a result about the paper: the output limit of #261 counted the runner's own `deps/`, repository copy and data copies. Fixed in #290 / #291 (the limit counts growth during the run); `paper_002` was run again at the fixed commit. |

`paper_003` had been started at the same commit and was stopped by the operator at the start of its run phase when this defect was found (it would have hit the same limit with its 4 GiB data copy); it left no record and was run again.
