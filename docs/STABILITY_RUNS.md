# Repeated runs of paper_003 and paper_006

Date: 2026-10-16. Issues #321, #356, #358. Records: `data/pilot2_runs/`, `data/pilot3_runs/`, `data/memory_runs/`, `data/cpu_runs/`.
Table: `scripts/run_stability.py`. Byte comparisons: `scripts/hash_run.py` (output in `data/memory_runs/hash_compare_*.txt`).

## 1. What was run

The two papers whose runs complete were run again with the same paper settings (`data/pilot3_settings.json`, `--pilot3`):

```
python scripts/run_pilot.py <paper_id> --pilot3 --memory 50% --record-root <folder>     # 2 CPUs, the protocol's
python scripts/run_pilot.py <paper_id> --pilot3 --memory 50% --cpus 8 --record-root data/cpu_runs
```

The second runs are stored as `data/memory_runs/paper_003_run2/` and `data/memory_runs/paper_006_run2/`. The first memory run of
`paper_006` (a `cli.py score` run of 2026-10-15) was never stored in the repository, so `paper_006` has its Pilot 2 and Pilot 3
runs, this second-run folder, and the CPU run. `paper_003` has its Pilot 3 run, the first memory run, the second run, and the CPU
run. **These are not repetitions under one protocol**: the memory limit is 6g in the pilots and 14265m in the memory runs, the CPU
runs have 8 CPUs, and the tool commit differs between runs (`repro_radar_commit` in each record). Each run was made once. No run was
made with a different seed.

## 2. The runs side by side

Status, exit code, and metrics are those of the stored records (`pilot_record.json`, `run_report.json`).

<!-- stability-runs:start -->
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

`paper_003`: 4 runs, status identical, exit code identical, metrics identical (loss 0.106, rmse 0.473); 3 of 9 log files identical (line endings ignored) with the first run's; `paper_006`: 4 runs, status identical, exit code identical, metrics identical (accuracy 0.8886, auroc 0.892); 9 of 15 log files identical (line endings ignored) with the first run's.
<!-- stability-runs:end -->

## 3. Byte comparison (`scripts/hash_run.py --compare`)

`data/memory_runs/hash_compare_paper_003_run2.txt` and `hash_compare_paper_006_run2.txt` hold the output of the comparison of each
second run with the earlier runs of the same paper. In every comparison **no paper output file exists** (the two papers write no file
that the protocol collects; the one file counted in the first comparison of `paper_003` is the `hash_compare.txt` that was
added to the folder of its first memory run). **No metadata file is byte-identical** (clock times, durations, and paths differ), and few log files
are identical. The table above compares the logs after normalizing line endings, because the
repository is checked out with `core.autocrlf` and a stored log can carry CRLF where a fresh one has LF; that difference alone makes
some byte comparisons report "differing". `stdout.log` of `paper_003` also holds the epoch clock times, which differ between runs
(after ignoring them and the line endings, the second run's `stdout.log` equals Pilot 3's line by line, which was checked with a
`diff` and is not part of a script).

## 4. What this shows, and what it does not

- Every run listed completed with the same exit code and stored the same metrics. For these two papers, the sandbox and the run
  setup gave the same computation each time, with 6g or 14265m of memory and with 2 or 8 CPUs.
- The metrics are those the metric extractor found in the output (`run_report.json`), compared exactly. They are not compared with
  any claim of the paper, and the runs are not scored.
- The run times vary: the table shows the run phase of each run; the runs with the same limits differ by up to about a hundred
  seconds (`paper_003`) and a few hundred seconds (`paper_006`), which is a property of the host's load as far as the records show.
- **This is not the stability tier of the score** (#48). That tier needs runs with different seeds, and the code's use of seeds was not
  examined. Runs that repeat the same metrics may repeat them because the code fixes its seeds; the records do not say.
- Two papers, three or four runs each, on one Windows host: no statement about other papers or machines.
