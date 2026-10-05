# Repro Radar — Pilot 2: Protocol

> **Status: protocol only. Nothing has been run.** Written on 2026-10-05 for plan step 2.9 (#171), before any Pilot 2
> run, so that the definitions are fixed before any result is seen (checkable in git history). **STOP before the
> first run:** the owner confirms that Docker Desktop with WSL2 is installed (plan item Y1, #172) and approves this
> protocol.
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
