# Candidate runs: protocol

Date written: 2026-10-24. Issue #437. This document and `data/candidates/run_plan.json` are written and merged **before any
candidate has been run**. Nothing in them is changed after the first run. If something is wrong with the protocol, the fix is a
new, dated section, not an edit of the rules below, and the runs made before it keep the rules they were made under.

## 1. What this is, and what it is not

`data/candidates/` holds 29 papers with a public repository that the owner collected (`docs/CANDIDATES.md`). None has been run.
This protocol runs **the 14 whose lists call them `ready` (9), `fixable` (4) or `two_step` (1)**, once each, in the sandbox.
The 11 of status `risky` and the 4 of status `excluded` are **not run**: the lists themselves say they need a download by hand,
a server, a cluster, or write into the repository.

- The 14 are a **selected list**, chosen by other people for being easy. They are **not a sample** of papers and the share that
  passes is **not a success rate** of anything. It is quoted only as "K of the 14 selected candidates".
- A pass does not show that the paper is reproduced. It shows that a command ran and printed a number (section 5).
- No claim of a paper is accepted by these runs. Accepting a claim is the owner's decision alone.

## 2. The commands

The command of a run is **the command of the lists** (`data/candidates/input.json`), together with the folder it is run in.
Where the listed command holds a placeholder (`...` or `<...>`), the placeholder is completed **only from the README of the
repository at the pinned commit**, verbatim, by one rule: the first README line that starts with the listed text. If the README
gives no concrete value (only placeholders again), the command is **not run** and the candidate is recorded as
`command_incomplete`. The protocol does not invent values. The completed commands were read from the READMEs before any run
and are fixed in `data/candidates/run_plan.json` (the source of every completion is written there). The one change that is
not a README completion: `<output directory>` of cand_002 is `/workspace/output`, the sandbox's writable output folder.

| Id | Command | Folder | Run by | Run? |
|---|---|---|---|---|
| cand_001 | `python notears/linear.py` | repository root | python | yes |
| cand_002 | `python run_BnpC.py example_data/data.csv -o /workspace/output` | repository root | python | yes |
| cand_003 | `python main.py` | repository root | python | yes |
| cand_004 | `python scripts/examples/linear_dynamics.py` | repository root | python | yes |
| cand_005 | `python main.py --scm_class sanity-3-lin --classifier_class lr --lambda_lcb 2. --optimization_approach grad_descent --grad_descent_epochs 1000 --batch_number 0 --sample_count 100` | repository root | python | yes |
| cand_006 | `python main_train.py --cfg utils/config.yaml` | repository root | python | yes |
| cand_007 | `export PYTHONPATH="$(pwd)/src:$PYTHONPATH"; python src/sim/simulator.py` | repository root | sh -c | yes |
| cand_008 | `python run_sweep.py --max-runs 8 --end-time 1.0` | `research` | python | yes |
| cand_009 | `python test-mocahesp.py --solver bo -f ackley20c -n 400 --seed 1` | repository root | python | yes |
| cand_010 | `python AE.py --method MLAE --latent_dim 16 --n_samples 800 --n_epochs 1000 --ood 1 --noise 1` | `code/brittle-fracture` | python | yes |
| cand_011 | `python main_synthetic_data.py` | `experiments/Synthetic_Data_Experiments` | python | yes |
| cand_012 | `python single_experiment.py --dataset CUB --num_shots 0 --generalized True` | `model` | python | yes |
| cand_013 | `python run.py --dataset=DATASET_NAME --run_times=YOUR_RUN_TIMES --subg_scale=PARAMETER_LAMBDA` | `code` | python | no: `command_incomplete` |
| cand_025 | `python generate_test_set.py && python experiment.py` | repository root | sh -c | yes |

- **No correction after the result.** A command is never changed because of what its run printed. A run that fails is recorded as
  it failed.
- **One attempt.** There is no second run, no retry, and no replacement of a failed candidate by another one.
- The repository is mounted **read-only**; a paper that writes into its own folder fails with `Read-only file system` and is
  recorded as that. The writable folder is `/workspace/output` (and the tmpfs of the sandbox user's home).
- Python 3.11, the repository's own requirement files, no extra requirement, no constraint, no data mount: the flow of
  `scripts/run_pilot.py --pilot4` (`docs/PILOT_4.md` sections 2 and 3). The install phase bundles wheels on the host and installs
  them offline; the run phase has `--network none`.
- Third-party code is executed **only inside the sandbox container**, never on the host.
- A `sh -c` command is the README's own text run by the shell in the repository folder; `cand_025`'s second command runs only if
  the first exits with 0.

## 3. Limits

| Setting | Value |
|---|---|
| Memory | `--memory 50%` of the host's RAM |
| CPUs | `--cpus 4` |
| Run phase time limit | **1800 s** (a run with a changed limit is not a protocol run of Pilot 2; its record says so) |
| Install phase | the limits of the pilots |
| Network | none, in both phases |
| Attempts | one per candidate |

## 4. How a run is made

`scripts/candidate_runs.py` (a thin script over `scripts/run_pilot.py`, the same mechanism as `scripts/demo_set.py`) builds the
corpus entry of each candidate from `data/candidates/papers.json` and `data/candidates/run_plan.json`, runs it once in the order of
the table, and writes the record to `data/candidates/runs/<paper_id>/` with local paths replaced by `<REPO>` and `<HOME>` and
large outputs shortened. The classification of a run is the function `classify_run` of `scripts/demo_set.py`.

## 5. What counts as a pass

A candidate **passes** only when all three hold:

1. the dependency installation status is `INSTALLED` or `SKIPPED`;
2. the run phase has status `COMPLETED` and exit code 0 (a valid run: `docker_used` and `isolated` are true);
3. the output (`stdout.log` or `stderr.log`) has at least one **numeric metric line**: a name, a `:` or `=`, and a number with a
   decimal point (the pattern of `scripts/demo_set.py`).

A candidate that does not pass is recorded with one category: `command_incomplete`, `staging`, `install`, `run`, `timeout`,
`memory`, `no_metric_line` or `harness`, with the deciding log line. It is not repaired and not run again.

Two limits of this definition are known now:

- **A metric line is a text pattern.** It can match a setup value (the demo set's `demo_020` passed on `True post-break alpha: 1.5`).
  Therefore the results list the lines themselves, and a second, stricter fact is recorded for every pass: whether a printed number
  with at least three decimals occurs in the text of the paper (exact string match on the PDF, as in `docs/DEMO_SET.md`). That match
  does not show that the number means the same thing in the paper. Whether the output is comparable with **a table** of the paper is
  decided by a person, not by this protocol, and is "not verified" until then.
- **A pass is not reproduction.** No claim is compared with a result in this step.

## 6. What is reported

- N = 14 (the selected candidates; a candidate that was not run because its command is incomplete counts as not passed, because the
  question is whether the listed command works), K = the number that passed, and the **Wilson 95 % interval** of K / N, computed by a
  script from the stored records (`python scripts/candidates_build.py --doc`). The number actually run (N minus those not runnable)
  is stated next to it.
- A table of failure categories and, for every pass, the command, the duration, and the metric lines.
- The sentence: "This is a selected list of candidates, not a representative sample; K / N is not a success rate."

## 7. Known before the first run (not results)

- cand_025 needs processed data in `~/data` before `generate_test_set.py` (its README); no data is mounted, so it is expected to
  fail. It is run anyway, as listed.
- cand_010 may need a conda environment (`environment.yml`); the flow installs the repository's pip requirement files only.
- cand_013 is not run (section 2).
- Python 3.11 is used for all; a paper that needs another Python version fails on that basis and is not repaired.
- The mechanism of `scripts/run_pilot.py` ignores `working_dir` of a corpus entry and takes only a `python <script>` command; the
  change that lets it read both (and a shell command for cand_007 and cand_025) is a separate small pull request, merged after this
  document and before the first run. It changes no behavior for the existing corpora (none of them has a `working_dir`).
