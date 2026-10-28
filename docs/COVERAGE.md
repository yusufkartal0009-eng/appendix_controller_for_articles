# Test coverage and boundary-case tests (2026-10-28, issue #557)

Measured with `pytest-cov` (already in `requirements-dev.txt`):

```
.venv\Scripts\pytest.exe tests -q --cov=src --cov=cli --cov-report=term-missing
```

"Before" is `main` at `864d03c` (1304 tests passed, 9 skipped). "After" is `main` with the changes of this issue (1711 tests passed, 10 skipped; the
extra skip is a symlink test that needs a privilege Windows does not give by default). The numbers are line coverage of `src/` and `cli.py` as
`pytest-cov` reports them (statements, missed statements). Coverage says which lines ran, not that they were checked well.

## Before and after

| Module | Statements | Missed before | Cover before | Statements after | Missed after | Cover after |
|---|---|---|---|---|---|---|


All modules of `src/web/` were at 100 % before and stay there. Modules not listed were at 97 % or more and did not change.

## Which modules were chosen

The five lowest before: `cli.py`, `src/sandbox/resources.py`, `src/sandbox/run_setup.py`, `src/sandbox/runner.py`, `src/sandbox/env_cache.py`. The
task also named `src/scoring.py`, `src/score_run.py`, `src/claim_store.py`, `cli.py` and `src/web`, so those got edge-case tests as well, and the
metric extractor, because a defect found while reviewing issue #30 sits there.

- Not improved: `src/sandbox/runner.py` stays at 90.2 %. Its uncovered lines (error branches of the Docker calls) need a Docker daemon or a
  large mock of one; the real-Docker checks of `docs/SANDBOX_ACCEPTANCE.md` cover that path, and no test was added for it here.
- `cli.py` stays at 89.3 %: the rest is the branch of `score` that starts a real Docker run, which these tests do not start.

## New test files

| File | What it covers |
|---|---|
| `tests/test_scoring_edges.py` | exact 5 % and 0.05 bounds, twice the tolerance, a claim of 0, NaN and infinity, negative and huge values, Unicode names, empty inputs, CV on the 2 %, 5 % and 10 % edges |
| `tests/test_metric_extractor_noisy.py` | ANSI color codes, progress bars, CRLF, NUL bytes, NaN and infinity, percent, Unicode, broken JSON, a run folder with a bad results file |
| `tests/test_score_run_edges.py` | empty record and report, non-numeric metrics, failed build, skipped install, NaN metric, no claims, a huge and a non-UTF-8 log |
| `tests/test_claim_store_edges.py` | malformed decisions files, entries without ids, a bad date, unknown ids, a NaN value, an unknown paper, a long Unicode quote |
| `tests/test_cli_score_errors.py`, `tests/test_cli_edges.py` | a missing or corrupt run folder, empty database, unknown paper and command, Unicode titles, diagnose of a stored run and of a bad backend, a labeled simulation |
| `tests/test_resources_edges.py` | memory shares at the edges (1 %, 100 %, 0 %, 101 %, NaN, infinity), the 90 % Docker cap, the floor, an unreadable host, the macOS and Linux readers |
| `tests/test_run_setup_edges.py` | every refusal of the run-setup validation and the accepted shapes |
| `tests/test_env_cache_edges.py` | tree digests (empty, renamed, symlink), a corrupt or mismatching entry, replacement, Docker errors |

## Real defects found and fixed (one pull request each)

| Pull request | Defect |
|---|---|
| #559 | Float noise at an exact threshold: a difference of exactly 0.05 lost half the points for 105 of 198 tested claims, and a CV of exactly 2 %, 5 % or 10 % fell into the next worse band. The tolerance and the bands are unchanged. |
| #560 | An ANSI color code in a log line became part of the metric name (`32maccuracy`), so a claim could not match it. |
| #561 | A malformed `review_decisions.json` ended in a raw `JSONDecodeError`, `AttributeError`, `TypeError` or `KeyError`; it is now a `ValueError` that names the file. |
| #562 | `cli.py score --from-run` with a missing or corrupt run folder ended in a traceback; it is now a message and exit code 1. |

## Behaviors found and not changed (owner decision, listed in `docs/PENDING.md`)

- A claimed value of infinity against an equal infinity earns no points; a NaN or infinite seed value gives Tier 3 = 40 with a note that says
  the variation "exceeds 10 %". Both are conservative, and changing them would be a scoring decision.
- A boolean in `run_report.json` metrics would be read as the number 1.0 or 0.0.
- The metric extractor reads `0,85` as `0.0`, does not read `.85` or `1e-5`, and keeps a JSON `NaN` while it drops a log line `nan`.

Not verified: that the new tests catch every future change of these modules; mutation testing was not run.
