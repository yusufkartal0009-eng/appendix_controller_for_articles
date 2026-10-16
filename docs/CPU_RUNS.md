# CPU runs: do more CPUs shorten a long run?

Date: 2026-10-16. Issues #331, #348, #353, #350. Records: `data/cpu_runs/`. Table: `scripts/run_stability.py`.

## 1. What was run, and what these runs are not

`paper_006` and `paper_003`, the two papers whose runs complete, were run with Pilot 3's per-paper settings, a memory limit of
50% of the host's RAM, and **8 CPUs instead of the protocol's 2**:

```
python scripts/run_pilot.py <paper_id> --pilot3 --memory 50% --cpus 8 --record-root data/cpu_runs
```

The records say so (`cpus_override`, `memory_override`). They are **not protocol runs**: `data/pilot2_runs/` and
`data/pilot3_runs/` were not touched, and no rate of the report was recomputed. The runs were made one after the other on one
Windows machine with Docker Desktop (12 CPUs seen by Docker). Each was made once.

## 2. Side by side with the runs that have 2 CPUs

"Run phase" is the sandbox's own measurement of the run phase (`duration_seconds` of the record's `run`); "install and run" is the
whole sandbox part of the pilot record (`sandbox_duration_seconds`: the install phase and the run phase, without staging and
the host-side bundling of wheels). A speed-up is the 2-CPU time divided by the 8-CPU time.

<!-- cpu-runs:start -->
| Paper | CPU run: CPUs | Compared with (2 CPUs) | Its run phase (s) | CPU run's run phase (s) | Seconds saved | Run-phase speed-up | Install and run (s): reference / CPU run | Same status and exit code | Same metrics |
|---|---|---|---|---|---|---|---|---|---|
| `paper_003` | 8 | Pilot 3 | 1516.673 | 465.777 | 1050.9 | 3.26x | 2635.4 / 1513.969 | yes | yes |
| `paper_003` | 8 | memory re-run | 1497.443 | 465.777 | 1031.7 | 3.21x | 2563.229 / 1513.969 | yes | yes |
| `paper_003` | 8 | memory re-run, second | 1390.574 | 465.777 | 924.8 | 2.99x | 2399.558 / 1513.969 | yes | yes |
| `paper_006` | 8 | Pilot 2 | 3122.657 | 1119.834 | 2002.8 | 2.79x | 3688.728 / 1711.129 | yes | yes |
| `paper_006` | 8 | Pilot 3 | 3435.356 | 1119.834 | 2315.5 | 3.07x | 4065.419 / 1711.129 | yes | yes |
| `paper_006` | 8 | memory re-run, second | 3268.898 | 1119.834 | 2149.1 | 2.92x | 3853.736 / 1711.129 | yes | yes |

With 8 CPUs instead of 2, the run phase was 2.79 to 3.26 times faster in the 6 comparisons (install and run together: 1.58 to 2.38 times); status, exit code, and metrics were the same in all of them.
<!-- cpu-runs:end -->

## 3. How to read it

- The run phase is shorter in every comparison, by the seconds and the factor in the table. The factor of "install and run" is
  lower than that of the run phase because the rest of the sandbox time (the install phase and the container start-up; the split was not measured here) did not get much shorter:
  the "install and run" column minus the run phase column is about the same for the 2-CPU and the 8-CPU run of each paper.
- Four times the CPUs gave less than four times the speed-up. The records do not say why (limits of the code's own parallelism,
  data loading, or the host); this was not investigated.
- The status, the exit code, and the final metrics stored in `run_report.json` are the same as in the 2-CPU runs. More CPUs did
  not change what these two papers computed; this is the same metrics from one run each, not a claim about every setting.
- The host-side bundling of wheels (`bundle.duration_seconds` in the records) is not part of "install and run" and does not
  use the container's CPUs.

## 4. Limits of this evidence

- One CPU run per paper and two papers: the factor is a measurement of these runs, not an estimate for other papers or
  for 2 versus 8 CPUs in general.
- The runs differ in more than the CPUs. The memory limit is 14265m in the CPU runs and 6g in Pilots 2 and 3 (the two papers use
  about 1 GiB at most, so the limit does not bind), the tool commit differs (`repro_radar_commit` in the records), and short
  test and CI jobs ran on the same machine during the CPU runs. None of these was isolated, so the table does not prove that the
  CPUs alone caused the difference.
- The timing of a run depends on the host's load and on Docker Desktop's virtual machine.
