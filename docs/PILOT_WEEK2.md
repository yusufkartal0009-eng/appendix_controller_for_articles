# Repro Radar — Week 2 Pilot: Protocol

> **Status: protocol only. No pilot run has been started.** Written on 2026-09-28 for P1 (#122), before any paper code
> was executed. After this file is merged, the definitions, commands, and limits below are frozen (section 8).
> The one-page pilot report (P6, #127) will be added to this file below the protocol after the runs.
>
> Roadmap: `docs/ROADMAP_2026-09-27.md`, section 2. Umbrella issue: #43.

---

## 1. What the pilot measures

The pilot measures **Tier 1 only**: whether each of the 6 papers in `data/seed_papers.json` installs and runs in the
real Docker sandbox. It does **not** check whether the numbers match the paper; the claim values are not verified yet
(`docs/CORPUS_VERIFICATION.md`), and fixing them is section 3 of the roadmap (#9).

Each paper is run **once**, on CPU, with the commands in section 4. With n = 6 and a single run per paper, the results
are anecdotal, not statistical.

---

## 2. Where the runs happen: GitHub Actions

The development machine has no Docker, and the sandbox refuses to run paper code without Docker (by design, #80).
All pilot runs therefore happen on **GitHub-hosted runners** (`ubuntu-latest`), where Docker is available; the CI job
`Sandbox acceptance (real Docker)` already runs the sandbox there.

The workflow is built in P2 (#123), not here. It must follow this design:

| Property | Rule |
|---|---|
| File | `.github/workflows/pilot.yml`, separate from `ci.yml` |
| Trigger | `workflow_dispatch` only (started by hand); never on push or pull request |
| Jobs | One job per paper (matrix over the 6 `paper_id`s), each on its own fresh runner, `fail-fast: false` |
| Permissions | `permissions: contents: read`; no repository secrets are referenced by the job |
| Isolation | Paper code runs only inside the sandbox container (`--network none`, read-only root, non-root user); `GITHUB_TOKEN` and other runner variables are not passed into the container |
| Job time limit | `timeout-minutes: 150` per job |
| Evidence kept | The job records the runner environment (step 1 below), and uploads the paper's sandbox output directory (`run_report.json`, `execution_meta.json`, `install.log`, `install_meta.json`, `stdout.log`, `stderr.log`) as an artifact |

Steps of each job:
1. Record the environment: `GITHUB_SHA`, `uname -r`, `nproc`, `free -m`, `df -h`, `docker version`, and the runner image version.
2. Build the sandbox image from `docker/Dockerfile.sandbox` at `GITHUB_SHA`.
3. Stage the repository with `src/sandbox/stager.py`: clone, then check out the pinned `repo_commit`.
4. Bundle dependencies on the runner with `pip download --only-binary=:all:` (this never runs package code on the host, #102).
5. Run the install phase and the run phase with `src/sandbox/runner.py` (`DockerSandboxRunner`) using the settings of sections 3 and 4.
6. Upload the output directory as an artifact.

After the runs, the artifacts are downloaded and committed to the repository in the P3 PR (#124), together with the
Actions run ID, so that every number in the report can be traced to a stored file (artifacts expire).

**Minutes budget.** The repository is private, so runner minutes count against the account's monthly allowance. Worst
case: 6 jobs × 150 minutes = 900 minutes.

---

## 3. Fixed settings (same for every paper)

| Setting | Value | Why |
|---|---|---|
| Runner | GitHub-hosted `ubuntu-latest` | Has Docker; hardware is recorded per job (section 2, step 1) |
| Image | `repro-radar-sandbox:latest`, built from `docker/Dockerfile.sandbox` at the recorded `GITHUB_SHA` | Same image as the acceptance checks |
| Python | 3.11 (image `python:3.11-slim`) | Image default |
| Network | `--network none` in both phases | Sandbox default |
| CPUs | `--cpus=2.0` | Sandbox default |
| Memory | `--memory=6g`, `--memory-swap=6g` | Lower than the sandbox default (8g) so the limit stays below the runner's RAM (GitHub documents 7 GB for private-repository Linux runners; confirmed by `free -m` in each job). With 8g, an out-of-memory kill would come from the host, not from the container limit |
| Processes | `--pids-limit=100` | Sandbox default |
| Scratch space | `/tmp` 64 MB, `/workspace/home` 2048 MB, both `noexec` | Sandbox defaults |
| Timeout | 3600 s for the install phase and 3600 s for the run phase | One hour per phase; a run still going at the limit is recorded as `TIMEOUT` |
| GPU | None (GitHub-hosted runners have no GPU); every command selects CPU where the script allows it | |
| Repetitions | 1 run per paper, no seed loop | Multi-seed execution is not implemented (#48) |

---

## 4. Per-paper commands

The command column is exactly what runs inside the container; the working directory is always `/workspace/repo`
(the repository, mounted read-only), and the output directory is `/workspace/output`.

**Rules for choosing the commands:**
- Start from the invocation the paper's README documents for its target script.
- Allowed adaptations: (a) options the script itself provides to write output into `/workspace/output`; (b) selecting
  the CPU where the script or README offers it; (c) environment variables the README tells the user to set.
- Nothing in the repository is edited, created, or copied, and no code of ours is added around the paper's code (no `WRAPPER`).
- No data is pre-downloaded or mounted. The roadmap offers two options for papers that download data at run time
  (pre-download and mount read-only, or mark "data not accessible"); the pilot chooses to **run them without data**,
  so the install phase is still measured and the failure is recorded in the category `DATA_NOT_ACCESSIBLE`. Whether a
  read-only data cache (`/workspace/data`) is needed is decided after P5 (#126), not now.
- Dependencies come only from `*requirements*.txt` files in the repository root (the sandbox's install phase). Conda
  environment files are not used, and nothing is built from source.

| Paper | Repository @ pinned commit | Target script | Exact command in the container | Environment | Installed from |
|---|---|---|---|---|---|
| `paper_002` TabPFN | `PriorLabs/TabPFN` @ `ddf5e85` | `tabpfn/scripts/tabular_baselines.py` | `python /workspace/repo/tabpfn/scripts/tabular_baselines.py` | — | `requirements.txt` |
| `paper_003` FT-Transformer | `yandex-research/rtdl-revisiting-models` @ `e3ed46c` | `bin/ft_transformer.py` | `python /workspace/repo/bin/ft_transformer.py output/california_housing/ft_transformer/default/0.toml -o /workspace/output/ft_transformer_default_0` | `PROJECT_DIR=/workspace/repo`, `CUDA_VISIBLE_DEVICES=` (empty) | `requirements.txt` |
| `paper_004` TabR | `yandex-research/tabular-dl-tabr` @ `17baa90` | `bin/tabr.py` | `python /workspace/repo/bin/tabr.py exp/tabr/california/0-evaluation/0.toml --force` | `CUDA_VISIBLE_DEVICES=` (empty) | nothing: the repository has no requirements file (conda `environment.yaml` only) |
| `paper_005` FastSK | `QData/FastSK` @ `d275a23` | `results/run_gridsearch.py` | `python /workspace/repo/results/run_gridsearch.py` | — | `requirements.txt` |
| `paper_006` SAINT | `somepago/saint` @ `e288e84` | `train.py` | `python /workspace/repo/train.py --dset_id 1461 --task binary --savemodelroot /workspace/output/bestmodels` | — | nothing: the repository has no requirements file (conda `saint_environment.yml` only) |
| `paper_008` DANets | `WhatAShot/DANet` @ `b007c57` | `main.py` | `python /workspace/repo/main.py -c config/forest_cover_type.yaml -g ""` | — | `requirements.txt` |

Full commit SHAs are in `data/seed_papers.json` (`repo_commit`).

**Where each command comes from, and known obstacles** (read from the repositories at the pinned commits on
2026-09-28; none of this has been run):

- **`paper_002`**: the target script has no entry point. It defines functions and parameter grids; its `argparse`
  parser is inside a function, and there is no `if __name__ == "__main__"` block. The paper's experiments are run from
  notebooks (`tabpfn/RunFullDatasetAnalyses.ipynb`). The command is therefore run without arguments, and **an exit
  code 0 for this paper only shows that the module imports**. This is a corpus problem (the target script is not an
  experiment entry point); it is recorded here and not fixed during the pilot.
- **`paper_003`**: the README runs `python bin/<model>.py <config>.toml` after setting `PROJECT_DIR`. The config is the
  published default FT-Transformer config for California Housing (the dataset of the seed claims). The script's own
  `-o/--output` option sends its output to `/workspace/output`. PyTorch is installed through conda in the README and
  is not in `requirements.txt`. The data is a manual download (`data.tar.gz` from Dropbox) and is not in the repository.
- **`paper_004`**: the README runs `python bin/<script>.py <config>.toml --force` with `CUDA_VISIBLE_DEVICES` set
  explicitly; the script sets `PROJECT_DIR` itself. The config is the published TabR evaluation config for California
  Housing. The script writes its output next to the config and creates `cache/` in the repository root, both inside
  the read-only repository, and has no option to redirect them. The data is a download from Hugging Face. The
  repository is large (its file tree has over 55,000 entries at this commit), and the stager's clone timeout is 120 s.
- **`paper_005`**: the README runs `cd results/ && python run_gridsearch.py`. The sandbox always starts in the
  repository root, and the script opens `spreadsheets/datasets_to_use.csv` relative to the working directory (the file
  is at `results/spreadsheets/datasets_to_use.csv`). The script imports the `fastsk` package, a C++ extension that the
  README installs with `pip install .`; the sandbox builds nothing from source, so the extension is not installed. The
  datasets are included in the repository (`data/`). Building the extension inside a container is a candidate sandbox
  change for the P6 report, not part of this pilot.
- **`paper_006`**: the README runs `python train.py --dset_id <openml_dataset_id> --task <task_name> ...`. OpenML
  dataset 1461 is `bank-marketing` (checked through the OpenML API on 2026-09-28), the dataset of the seed claim
  `bank_marketing_accuracy`. The script's own `--savemodelroot` option sends saved models to `/workspace/output`;
  all other options keep their defaults (100 epochs). The dataset is downloaded from OpenML at run time.
- **`paper_008`**: the README runs `python main.py --c [config_path] --g [gpu_id]`. The config is the repository's
  Forest Cover Type config (the dataset of the seed claim `forest_covertype_accuracy`; 5000 maximum epochs). The script
  sets `CUDA_VISIBLE_DEVICES` from `-g`; an empty value selects no GPU. The data is a manual download (README links)
  and is not in the repository.

---

## 5. Definitions

These are fixed before any result is seen and are not changed afterwards.

| Term | Definition |
|---|---|
| **Valid run** | A run whose `run_report.json` shows `docker_used: true` and `isolated: true`. Only valid runs are counted; a run without Docker is not a pilot run. |
| **Install success** | `dependency_install_status: INSTALLED` in `run_report.json`. `FAILED`, `SKIPPED` (nothing to install, e.g. no requirements file), and `UNKNOWN` are **not** install success. |
| **Run success** | Exit code 0 of the run phase in a valid run. `TIMEOUT`, `OOM_KILLED`, and any non-zero exit code are **not** run success. |
| **Pilot success** (per paper) | Install success **and** run success. |
| **Install success rate** | Papers with install success / 6 |
| **Run success rate** | Papers with run success / 6 |
| **Pilot success rate** | Papers with pilot success / 6 |

The denominator is always 6, including papers whose staging fails or whose run cannot start. The caveat for
`paper_002` (section 4) is reported next to its result; it does not change the definitions.

---

## 6. Measurements (P3, #124)

Computed by a script from the stored `run_report.json` files, never typed by hand:
- the three rates of section 5;
- time per paper: `duration_seconds` of the run phase, and the install-phase duration if the report contains it;
- peak memory per paper, **only if** the sandbox records it (for example from the container's cgroup `memory.peak`);
  otherwise it is reported as "not measured".

---

## 7. Failure categories (P4, #125)

Every paper without pilot success gets exactly one category. The category is decided by the **first** failure in
the order install → run, using the evidence below; the log line that decided it is quoted in the report.

| Category | Evidence |
|---|---|
| `MISSING_DEPENDENCY` | Install phase `FAILED`, a requirement reported as `NEEDS_SDIST_BUILD`, or `ModuleNotFoundError` / `ImportError` in the run |
| `DATA_NOT_ACCESSIBLE` | A data file is missing or a data download fails (the network is off) |
| `HARDWARE_GPU_REQUIRED` | The code requires CUDA or a GPU (for example "no CUDA GPUs are available", "Torch not compiled with CUDA") |
| `TIMEOUT` | Status `TIMEOUT` (still running at the 3600 s limit) |
| `SCRIPT_NOT_FOUND` | The target script does not exist in the staged repository |
| `LICENSE_BLOCKED` | The repository's license is not allowed (all 6 currently pass `scripts/verify_corpus.py`) |
| `OTHER` | Anything else. Every `OTHER` is read by hand and either given a name in the report (for example an out-of-memory kill, a write to the read-only repository, or a failed clone) or explained |

A paper that installs as `SKIPPED` and then runs with exit code 0 has no failure but no pilot success; it is reported
as "ran without installed dependencies".

---

## 8. What may change after the runs start

- **Frozen:** the definitions (section 5), the commands, environment variables, and dataset choices (section 4), the
  limits and timeouts (section 3), and the category rules (section 7). If one of them turns out to be wrong, the
  pilot result stays as it is, and the change is proposed for the next pilot, in the report.
- **Allowed:** fixing a defect in Repro Radar's own code (workflow, stager, runner) that stops a run from happening
  as specified here. Each fix is its own issue and PR, the paper is re-run, and the report lists the fix and keeps
  the result of the first attempt.
- **Never:** editing a paper's code or data, adding a wrapper, or editing a result by hand.

---

## 9. Known limits of this pilot

- n = 6, one run per paper: anecdotal, not statistical.
- CPU only, 2 CPUs and 6 GB of memory: papers written for GPUs may time out or fail where they would work on the
  authors' hardware.
- Only pip `requirements.txt` files are installed: repositories that document a conda environment (`paper_004`,
  `paper_006`, and PyTorch for `paper_003`) cannot get their full environment in this sandbox.
- No data is staged: papers that download data at run time are expected to stop at the data step, so the run phase
  of those papers measures little beyond start-up.
- The target script of `paper_002` is not an experiment entry point (section 4).
