# Week 2 pilot: stored run files

Raw output of the pilot described in `docs/PILOT_WEEK2.md`. The files are copied unchanged from the GitHub Actions
artifacts; nothing in `<paper_id>/` was edited by hand.

| | |
|---|---|
| Workflow run | [`36759195752`](https://github.com/yusufkartal0009-eng/appendix_controller_for_articles/actions/runs/36759195752), `Pilot (Week 2)`, attempt 1, started by hand on 2026-09-30 18:31 UTC |
| Repro Radar commit | `dbcbe5afcdc7f6b388459887f26e2f15a4ccd077` (the protocol was merged in `bcdff49`, before this run) |
| Runner | GitHub-hosted `ubuntu24 20260927.320.1`, kernel `6.17.0-1022-azure`, 2 CPUs, 7938 MB RAM (see each `runner_environment.txt`) |
| Fetched with | `gh run download 36759195752`, then each `pilot-<paper_id>/` artifact copied to `<paper_id>/` |

Files per paper:

| File | Written by |
|---|---|
| `pilot_record.json` | `scripts/run_pilot.py` (staging, bundling, phase results, timings) |
| `run_report.json` | `RepoStager.execute_staged` |
| `execution_meta.json`, `stdout.log`, `stderr.log` | the container entrypoint, run phase |
| `install_meta.json`, `install.log` | the container entrypoint, install phase (absent when there was nothing to install) |
| `extracted_metrics.json` | `MetricExtractor` on the run output |
| `runner_environment.txt` | the workflow (hardware, image, disk before and after) |

`measurements.json` and `measurements.md` are generated from these files by `scripts/pilot_measurements.py`;
`tests/test_pilot_measurements.py` fails if they no longer match the stored runs.
