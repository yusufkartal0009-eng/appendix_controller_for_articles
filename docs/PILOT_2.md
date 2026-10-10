# Repro Radar — Pilot 2: Protocol

> **Status: run and reported.** The protocol (sections 1-11) was written on 2026-10-05 for plan step 2.9 (#171),
> before any Pilot 2 run (#201), and frozen when it was merged. Pilot 2 ran on 2026-10-10 on the owner's machine in
> real Docker (Docker Desktop, WSL2); the owner confirmed Docker and asked for the run to be made per this protocol.
> The results (section 12 onward) were added afterwards.
> *This status note was updated on 2026-10-10; it is the only change above section 12.*
>
> Pilot 1: `docs/PILOT_WEEK2.md` (run on 2026-09-30, pilot success 0 / 6). Its result stays in the record and is shown
> next to Pilot 2's.

---

## 1. What the pilot measures

Like Pilot 1, Pilot 2 measures **Tier 1 only**: whether each of the 6 papers in `data/seed_papers.json` installs and
runs in the real Docker sandbox. It does not compare numbers with the paper; claim scoring needs claims accepted by a
person (#134), and that is not part of this pilot.

What changed since Pilot 1 is the sandbox and the per-paper run setups, not the papers and not the definitions:

| Change | Issue |
|---|---|
| Sandbox images for Python 3.8 and 3.9 next to 3.11; each paper uses the version its repository names | #158 |
| Conda-only repositories installed through their pinned Python packages | #159 |
| Dependency conflicts and installed versions recorded in the run report | #160, #161 |
| Per-paper run setup (`run_setup` in `data/seed_papers.json`): entry command, working directory, writable repository copy, data cache | #166 |
| Isolated build phase for packages that exist only as source; extra requirements; version constraints; writable data copies | #193 |
| Docker detection that tolerates a slow daemon | #164 |
| Opt-in local GPU, recorded in the run report | #169 |

Each paper is run **once**. With n = 6 and one run per paper, the results are anecdotal, not statistical.

---

## 2. Where the runs happen: the owner's machine

Pilot 2 runs on the owner's Windows machine with Docker Desktop (WSL2 backend), not on GitHub Actions (plan decision
D-006, everything runs locally). No GitHub Actions minutes are used.

Before the first run, the environment is recorded in `data/pilot2_runs/environment.txt`, from command output only:
- the Repro Radar commit (`git rev-parse HEAD`) and a clean `git status`;
- `docker version` and `docker info` (CPUs, memory, storage driver, WSL kernel);
- `nvidia-smi` on the host, and `python scripts/gpu_check.py` (#169) inside the sandbox;
- free disk space of the Docker data disk and of the data cache (`.data_cache/`).

---

## 3. Fixed settings (same for every paper)

The limits are Pilot 1's, so that the two pilots differ only in what section 1 lists.

| Setting | Value | Same as Pilot 1? |
|---|---|---|
| Images | `repro-radar-sandbox:latest` (3.11), `:py3.9`, `:py3.8`, and for the build phase `:build`, `:py3.9-build`, `:py3.8-build`, built from `docker/Dockerfile.sandbox` at the recorded commit | Python version per paper (new) |
| Network | `--network none` in the build, install, and run phases | Yes |
| CPUs | `--cpus=2.0` | Yes |
| Memory | `--memory=6g`, `--memory-swap=6g` | Yes |
| Processes | `--pids-limit=100` | Yes |
| Scratch space | `/tmp` 64 MB, `/workspace/home` 2048 MB, both `noexec` | Yes |
| Timeout | 3600 s per phase (build, install, run) | Yes (the build phase is new) |
| GPU | **None** for the counted run, as in Pilot 1 | Yes |
| Repetitions | 1 run per paper, no seed loop | Yes |

**GPU.** The counted run is CPU-only, so that a change in the rates cannot come from the hardware. A second,
separately reported run with `--gpus all` is allowed only for papers whose installed PyTorch supports the RTX 5070
(PyTorch built for CUDA 12.8 or newer). The PyTorch 1.x versions that several papers pin cannot use it. A GPU run is
never counted in the rates of section 5.

---

## 4. Per-paper settings

Each paper runs with its `run_setup` in `data/seed_papers.json` at the recorded commit: command or script arguments,
environment, working directory, writable copy, data items, build, extra requirements, and constraints. The run
report stores the setup it used (`run_report.json`: `command`, `working_dir`, `writable_repo`, `data_mounts`).

| Paper | Python | Build phase | Data (fetched with `scripts/fetch_data.py` before the run) | Note fixed before the run |
|---|---|---|---|---|
| `paper_002` | 3.8 | `openml==0.12.2`, `liac-arff==2.5.0` | 30 OpenML-CC18 datasets (writable OpenML cache) | **Open owner decision (#193):** the notebook lists its datasets through the OpenML API, which needs network. Unless the owner decides otherwise before the run, it runs with the network off, as every paper does |
| `paper_003` | 3.8 | — | `revisiting_models_data` (4.07 GiB) as `data/` | — |
| `paper_004` | 3.9 | — | `tabular_benchmarks` (2.88 GiB) as `data/`; writable repository copy | — |
| `paper_005` | 3.8 | `fastsk` from the repository (`pybind11==2.6.2`) | — (the datasets are in the repository) | Version constraints from the pinned commit's date (`constraints_source`) |
| `paper_006` | 3.8 | `openml==0.11.0`, `liac-arff==2.5.0` | OpenML dataset 1461 (writable OpenML cache) | — |
| `paper_008` | 3.11 | — | — | Expected `DATA_NOT_ACCESSIBLE`: the split files are not published (#166). It is still run and counted |

---

## 5. Definitions

These are Pilot 1's definitions (`docs/PILOT_WEEK2.md`, section 5), unchanged. They are fixed before any result is
seen and are not changed afterwards.

| Term | Definition |
|---|---|
| **Valid run** | A run whose `run_report.json` shows `docker_used: true` and `isolated: true`. Only valid runs are counted; a run without Docker is not a pilot run. |
| **Install success** | `dependency_install_status: INSTALLED` in `run_report.json`. `FAILED`, `SKIPPED` (nothing to install, e.g. no requirements file), and `UNKNOWN` are **not** install success. |
| **Run success** | Exit code 0 of the run phase in a valid run. `TIMEOUT`, `OOM_KILLED`, and any non-zero exit code are **not** run success. |
| **Pilot success** (per paper) | Install success **and** run success. |
| **Install success rate** | Papers with install success / 6 |
| **Run success rate** | Papers with run success / 6 |
| **Pilot success rate** | Papers with pilot success / 6 |

The denominator is always 6, including papers whose staging, build, or data fetch fails and `paper_008`. A failed
build phase counts as a failed install (the paper's dependencies could not be installed).

---

## 6. Measurements

Computed by a script from the stored files, never typed by hand (`scripts/pilot_measurements.py`, as for Pilot 1):
- the three rates of section 5, next to Pilot 1's;
- time per paper: run phase, install phase, and build phase durations, where recorded;
- peak memory per paper, where the sandbox records it; otherwise "not measured";
- per paper, from the run report: `dependency_conflicts` (#160) and `requested_vs_installed` (#161);
- for a separate GPU run (section 3), the run report's `gpu` summary. It is informational and not part of the rates.

---

## 7. Failure categories

Pilot 1's categories and rules (`docs/PILOT_WEEK2.md`, section 7), unchanged: every paper without pilot success gets
exactly one category, decided by the **first** failure. The order is now build → install → run, and the log line
that decided it is quoted in the report.

| Category | Evidence |
|---|---|
| `MISSING_DEPENDENCY` | Build phase or install phase `FAILED`, a requirement reported as `NEEDS_SDIST_BUILD`, or `ModuleNotFoundError` / `ImportError` in the run |
| `DATA_NOT_ACCESSIBLE` | A data file is missing, a data fetch fails, or a data download is attempted (the network is off) |
| `HARDWARE_GPU_REQUIRED` | The code requires CUDA or a GPU (for example "no CUDA GPUs are available", "Torch not compiled with CUDA") |
| `TIMEOUT` | Status `TIMEOUT` (still running at the 3600 s limit) |
| `SCRIPT_NOT_FOUND` | The target script does not exist in the staged repository |
| `LICENSE_BLOCKED` | The repository's license is not allowed |
| `OTHER` | Anything else, read by hand and named or explained in the report |

---

## 8. Steps

1. **STOP:** the owner confirms Docker Desktop with WSL2 is installed and approves this protocol.
2. Record the environment (section 2).
3. Build the six images (section 3).
4. Fetch the data of `paper_002`, `paper_003`, `paper_004`, and `paper_006` with `scripts/fetch_data.py`. A fetch that
   fails is a result (`DATA_NOT_ACCESSIBLE`), not a reason to change the setup.
5. Run each paper once: stage at the pinned commit → build phase (if any) → bundle → install phase → run phase.
   `scripts/run_pilot.py` still runs Pilot 1's frozen commands. Reading `run_setup` is added in its own issue and PR
   **before** the first Pilot 2 run, without changing this protocol.
6. Store each paper's output directory in `data/pilot2_runs/<paper_id>/`: `run_report.json`, `execution_meta.json`,
   `install.log`, `install_meta.json`, `build.log`, `stdout.log`, `stderr.log`, `pilot_record.json`.
7. Write the report (section 10) from those files.

---

## 9. What may change after the runs start

Pilot 1's rules, unchanged:
- **Frozen:** the definitions (section 5), the settings (section 3), the per-paper settings (section 4, as stored in
  `data/seed_papers.json` at the recorded commit), and the category rules (section 7). If one turns out to be wrong,
  the result stays as it is, and the change is proposed for the next pilot in the report.
- **Allowed:** fixing a defect in Repro Radar's own code that stops a run from happening as specified here. Each fix is
  its own issue and PR. The paper is re-run, and the report lists the fix and keeps the first attempt's result.
- **Never:** editing a paper's code or data, adding a wrapper, or editing a result by hand.

---

## 10. Report (after the runs)

The results go below this protocol, in the same shape as Pilot 1's report (`docs/PILOT_WEEK2.md`, section 11):
- the rates of Pilot 1 and Pilot 2 side by side;
- a per-paper table;
- failure categories with the deciding log line;
- what was surprising;
- what we would change;
- limits.

Every number names the script and file it came from.

---

## 11. Known limits of this pilot

- n = 6, one run per paper: anecdotal, not statistical.
- CPU only for the counted run, 2 CPUs and 6 GB of memory: papers written for GPUs may time out or fail where they
  would work on the authors' hardware.
- The run setups were written by Repro Radar (#166, #193): an entry command, a working directory, data fetched ahead
  of time, built packages, and version constraints. A paper that runs with them shows that it *can* be run this way,
  not that its README alone is enough.
- `paper_005`'s version constraints are a choice (newest release before the pinned commit's date), recorded with
  their source; other choices could behave differently.
- Pilot 1 ran on GitHub's runners, Pilot 2 on the owner's machine: the limits are the same, but the hardware is not.

---

# Results (written after the runs)

The sections below were added after Pilot 2 ran on the owner's machine (Docker Desktop with WSL2, 2026-10-10). The raw
files are in `data/pilot2_runs/`, the earlier attempts in `data/pilot2_runs/first_attempts/`; the protocol above was not
changed. Every number below is a generated block (`scripts/report_numbers.py --report docs/PILOT_2.md`; `--check` and a
test fail if one is edited by hand), copied from `data/pilot2_runs/` and from Pilot 1's stored files, which are unchanged.

## 12. Pilot report

**In one line:**

<!-- numbers:pilot2summary:start -->
<!-- Generated by scripts/report_numbers.py from data/pilot2_runs/comparison.json; do not edit by hand. -->

Install success: 6 / 6 (1.0) (Pilot 1: 1 / 6 (0.167)). Run success: 1 / 6 (0.167) (Pilot 1: 0 / 6 (0.0)). Pilot success: 1 / 6 (0.167) (Pilot 1: 0 / 6 (0.0)).
<!-- numbers:pilot2summary:end -->

Every one of the six runs is valid (Docker used, isolated, each repository at its pinned commit). The counted result of
each paper is its last attempt; the Repro Radar commit of every attempt is in its `pilot_record.json`. The last change to
the run path is commit `5772631` (#233), where `paper_006` ran. The other five counted runs are at `c10340b`: four
(`paper_002`, `paper_003`, `paper_005`, `paper_008`) were re-run there after the last fix so that their counted results
come from the final code, and `paper_004` ran there. `git diff --stat 5772631 c10340b -- src scripts docker` lists
`scripts/categorize_pilot_failures.py` and `scripts/pilot_measurements.py` only, so no run-path code differs.

### Rates and per-paper results

<!-- numbers:pilot2measurements:start -->
<!-- Generated by scripts/report_numbers.py from data/pilot2_runs/measurements.md (scripts/pilot_measurements.py); do not edit by hand. -->

| Measure | Count | Rate |
|---|---|---|
| Install success | 6 / 6 | 1.0 |
| Run success | 1 / 6 | 0.167 |
| Pilot success | 1 / 6 | 0.167 |
| Valid runs | 6 / 6 | 1.0 |

| Paper | Dependencies | Run status | Exit code | Install (s) | Run (s) | Install peak (MiB) | Run peak (MiB) | Pilot success |
|---|---|---|---|---|---|---|---|---|
| `paper_002` | INSTALLED | FAILED | 1 | 687.762 | 38.147 | 87.6 | 475.5 | no |
| `paper_003` | INSTALLED | FAILED | 1 | 1011.087 | 14.995 | 169.1 | 355.8 | no |
| `paper_004` | INSTALLED | TIMEOUT | 137 | 1663.447 | 3600.761 | 190.1 | 3953.0 | no |
| `paper_005` | INSTALLED | OOM_KILLED | 137 | 176.881 | 469.451 | 70.7 | 6144.0 | no |
| `paper_006` | INSTALLED | COMPLETED | 0 | 563.184 | 3122.657 | 79.1 | 664.2 | yes |
| `paper_008` | INSTALLED | FAILED | 1 | 734.835 | 26.077 | 136.5 | 755.4 | no |
<!-- numbers:pilot2measurements:end -->

"Install" is the install phase only; the time to fetch the wheels on the host and to build packages from source is in
each paper's `pilot_record.json`.

### Pilot 1 and Pilot 2 side by side

<!-- numbers:pilot2:start -->
<!-- Generated by scripts/report_numbers.py from data/pilot2_runs/comparison.json (scripts/pilot_compare.py); do not edit by hand. -->

| Measure | Pilot 1 (`data/pilot_runs/`) | Pilot 2 (`data/pilot2_runs/`) |
|---|---|---|
| Install success | 1 / 6 (0.167) | 6 / 6 (1.0) |
| Run success | 0 / 6 (0.0) | 1 / 6 (0.167) |
| Pilot success | 0 / 6 (0.0) | 1 / 6 (0.167) |
| Valid runs | 6 / 6 (1.0) | 6 / 6 (1.0) |

| Paper | Pilot 1 | Pilot 2 |
|---|---|---|
| `paper_002` | MISSING_DEPENDENCY (install) | MISSING_DEPENDENCY (run) |
| `paper_003` | MISSING_DEPENDENCY (install) | OTHER (run) |
| `paper_004` | MISSING_DEPENDENCY (run) | TIMEOUT (run) |
| `paper_005` | MISSING_DEPENDENCY (install) | OTHER (run) |
| `paper_006` | MISSING_DEPENDENCY (run) | success |
| `paper_008` | DATA_NOT_ACCESSIBLE (run) | DATA_NOT_ACCESSIBLE (run) |

| Failure category | Pilot 1 | Pilot 2 |
|---|---|---|
| `MISSING_DEPENDENCY` | 5 | 1 |
| `DATA_NOT_ACCESSIBLE` | 1 | 1 |
| `HARDWARE_GPU_REQUIRED` | 0 | 0 |
| `TIMEOUT` | 0 | 1 |
| `SCRIPT_NOT_FOUND` | 0 | 0 |
| `LICENSE_BLOCKED` | 0 | 0 |
| `OTHER` | 0 | 2 |
<!-- numbers:pilot2:end -->

### Failure categories

The first failure decides (build, then install, then run), and the deciding line is quoted
(`data/pilot2_runs/failure_categories.json`):

<!-- numbers:pilot2failures:start -->
<!-- Generated by scripts/report_numbers.py from data/pilot2_runs/failure_categories.json; do not edit by hand. -->

| Paper | Category | Phase | Deciding line |
|---|---|---|---|
| `paper_002` | MISSING_DEPENDENCY | run | `ModuleNotFoundError: No module named 'lightgbm'` |
| `paper_003` | OTHER (WRITE_TO_READ_ONLY_REPOSITORY) | run | `OSError: [Errno 30] Read-only file system: '/workspace/repo/data/california_housing/build_X__quantile__mean__new__indices__0.pickle'` |
| `paper_004` | TIMEOUT | run | `status: TIMEOUT` |
| `paper_005` | OTHER (OUT_OF_MEMORY) | run | `status: OOM_KILLED` |
| `paper_006` | success | n/a | n/a |
| `paper_008` | DATA_NOT_ACCESSIBLE | run | `FileNotFoundError: [Errno 2] No such file or directory: './data/forest_cover_type/forest-cover-type.csv'` |
<!-- numbers:pilot2failures:end -->

### What each paper did

- **`paper_006` (SAINT), the one pilot success.** It built `openml` and `liac-arff` from source in the isolated build
  phase, installed its conda environment as pinned, read OpenML dataset 1461 (bank-marketing) from the mounted cache
  with the network off, trained with the default settings, and exited with code 0 after printing `AUROC on best model:
  0.929` (`data/pilot2_runs/paper_006/stdout.log`). That dataset and metric are not among the paper's accepted claims
  (`arcene_auroc`, `xgboost_arcene_auroc`), so the output is not scored against a claim.
- **`paper_004` (TabR).** It installed its large conda environment as pinned, trained on California Housing from
  the mounted data, and was still training when the 3600-second limit of the run phase ended (`TIMEOUT`); its log shows
  the validation and test scores of the epochs it completed.
- **`paper_005` (FastSK).** Its C++ extension was built from the repository in the sandbox's build phase; the grid search
  started (`grid search: 14% | 76/540` in the last log lines) and the container was killed at the 6 GiB memory limit
  (`OOM_KILLED`).
- **`paper_002` (TabPFN).** The repository's notebook ran inside the sandbox through `nbconvert` and stopped at a cell
  that imports `lightgbm`, which the repository's `requirements.txt` does not list.
- **`paper_003` (FT-Transformer).** The dataset archive was mounted and the model started; the run then stopped when the
  paper's code wrote a cache file into `data/california_housing/`, which the run setup mounts read-only. The run setup is
  a frozen per-paper setting (section 9), so the result stays as it is.
- **`paper_008` (DANets).** It installed and then stopped at the missing `forest-cover-type.csv`: the paper's train,
  validation, and test split files are not published (#166). This is the result decided in advance.

### Defects in Repro Radar that the first attempts found

The tool's own defects, not the papers', stopped most of the first attempts (`data/pilot2_runs/first_attempts/README.md`
lists every attempt with its commit, how it ended, and why it was superseded). Each was fixed in its own issue and PR
(section 9), and the paper was re-run:

- the container entrypoint was converted to CRLF by `core.autocrlf` on Windows, and every container failed to start (#211);
- dependency bundling evaluated environment markers for the host, not for the sandbox's Linux and Python (#215);
- re-staging could not delete git's read-only files on Windows, and a failed record listed the files of an older run (#217);
- the extra requirements of a run setup were bundled but never installed (#223);
- the conda conversion skipped `setuptools` and `certifi` (#225), then installed the environment by resolving it instead
  of as pinned, which a conda lock does not need (#227, #228, corrected by #229), mapped `python-graphviz` wrongly (#227),
  and did not map the CUDA build of `faiss` to `faiss-cpu` (#233);
- a writable data mount under the sandbox home left its parent directory owned by root (#231);
- the failure categorizer did not see through terminal colors in a notebook's traceback (#243).

### What was surprising

- **Most stops were defects of the tool.** Once they were fixed, the papers' own obstacles became visible, and they are
  different from Pilot 1's: an undeclared dependency, a cache written into a read-only directory, memory, time, and
  unpublished data. In Pilot 1 the dependency failures hid all of them.
- **The second platform found what Linux CI could not.** The CRLF entrypoint and the host-evaluated markers only fail on
  a Windows host; the real-Docker acceptance checks in CI had passed throughout.
- **One wrong diagnosis.** The first answer to the conda failures (a resolver pass over the pins, #227/#228) failed in
  turn on a source-only dependency and on conda's `mkl` packages; a conda environment file is a lock that already pins
  every dependency, so it is installed as pinned (#229).

### What we would change (proposals for the next pilot; none is implemented)

- **Run setups:** let `paper_003` write to its data directory (a writable copy), give `paper_005` more than 6 GiB or a
  smaller grid, give `paper_004` more than 3600 seconds, and list `lightgbm` among `paper_002`'s extra requirements.
  These are per-paper settings, frozen in this pilot.
- **Claims:** choose each paper's command so that it produces the metrics the accepted claims name. None of the runs
  does, so Pilot 2 says nothing about numerical reproducibility (Tier 2).
- **Cost:** installing a large environment takes minutes to half an hour per run (see the install column); a shared wheel
  cache across papers would cut it.

### Limits

- n = 6, one counted run per paper, no seed loop: the results are anecdotal, not statistical.
- The run setups (entry command, working directory, data, build, extra requirements, constraints) were written by Repro
  Radar. A paper that runs shows that it *can* be run this way, not that its README alone is enough.
- Substitutions: `faiss-cpu` for conda's CUDA `faiss` (`paper_004`), and packages that a requirement file leaves unpinned
  were installed at the newest version that fits (for example the PyTorch version in `paper_008`'s `install.log`), not at
  the version the authors used.
- CPU only, 2 CPUs, 6 GiB of memory, 3600 seconds per phase, network off: papers written for GPUs or for more memory can
  fail here where they would work on the authors' hardware (`paper_005` was killed at the memory limit; `paper_004`
  at the time limit).
- The runs are on one machine (Windows, Docker Desktop, WSL2); Pilot 1 ran on GitHub's Linux runners.
- Defects were fixed during the pilot, so the attempts ran at several Repro Radar commits; the counted attempts are at
  the commits shown in their records.
