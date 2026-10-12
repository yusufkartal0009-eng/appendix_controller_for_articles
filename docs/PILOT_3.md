# Repro Radar — Pilot 3: Protocol

> **Status: protocol written, not yet run.** This protocol was written on 2026-10-13 for issue #285, **before any
> Pilot 3 run**, and is frozen when it is merged. The results are added below it afterwards (section 11 onward), the
> same way as for Pilot 1 (`docs/PILOT_WEEK2.md`) and Pilot 2 (`docs/PILOT_2.md`).
>
> Pilot 1 (run on 2026-09-30): pilot success 0 / 6. Pilot 2 (run on 2026-10-10): pilot success 1 / 6. Their results,
> files, and reports stay exactly as they are; Pilot 3 never edits them. The three pilots are shown side by side.

---

## 1. What Pilot 3 is, and what it is not

Pilot 3 repeats Pilot 2 for the same six papers with **four per-paper settings changed**. The changes are the proposals
that Pilot 2's report made under "What we would change" (`docs/PILOT_2.md`, section 12), because Pilot 2 showed that
four papers stopped at a limit or a missing piece that Repro Radar set, not at something in the paper itself.

**This is configuring the experiment, not a better result about the papers.** The four changes were chosen *after* the
failures were seen, with the failure log in hand. A higher success rate in Pilot 3 therefore measures how far the
settings were moved, not how reproducible the papers are in general, and it must not be reported as an improvement of
the papers. What Pilot 3 can show is the next obstacle of each paper, once the obstacle that Repro Radar itself had
set is out of the way.

Like Pilots 1 and 2, Pilot 3 measures **Tier 1 only**: whether each of the 6 papers in `data/seed_papers.json` installs
and runs in the real Docker sandbox. It does not compare any number with the paper; no accepted claim is scored here.

---

## 2. The four changes

Everything not listed here is Pilot 2's setting. The changes live in `data/pilot3_settings.json` (an overlay read by
`scripts/run_pilot.py --pilot3`, added in its own issue and PR **before** the first run, without changing this
protocol). `data/seed_papers.json` is not edited, so Pilot 2's frozen setup stays readable.

| Paper | Pilot 2 stop (deciding line, `data/pilot2_runs/failure_categories.json`) | Change in Pilot 3 | Why |
|---|---|---|---|
| `paper_003` | `OSError: [Errno 30] Read-only file system: '/workspace/repo/data/california_housing/build_X__quantile__mean__new__indices__0.pickle'` | The data item `revisiting_models_data` (mounted as `data/`) is mounted as a **writable per-run copy** instead of read-only | The paper's own code caches a preprocessed file inside its data directory. A per-run copy lets it write there without touching the host cache (the same mechanism `paper_002` and `paper_006` already use for their OpenML cache). The 4.07 GiB archive is copied for each run. |
| `paper_005` | `status: OOM_KILLED` (peak 6144 MiB, grid search at 76 of 540, after 469 s) | Memory limit **12 GiB** (`--memory=12g --memory-swap=12g`), up from 6 GiB | The run was killed by the memory limit at 14% of its grid search, so the limit hid whatever comes next. 12 GiB is what fits in the machine's Docker allocation (15.5 GiB for all of Docker) with room for Docker itself. It is a choice, not a measured need: if the paper needs more, it is `OOM_KILLED` again and that is the result. |
| `paper_004` | `status: TIMEOUT` (run phase, 3600 s; about 107 s per epoch, still improving) | Run-phase timeout **14400 s** (4 hours), up from 3600 s | The config trains until the validation score has not improved for 16 epochs (`patience = 16`, `n_epochs = inf`), and at the limit it was still finding new best epochs. Four hours is a choice, not an estimate of the needed time; if the paper needs more, it times out again and that is the result. Build and install phases keep 3600 s. |
| `paper_002` | `ModuleNotFoundError: No module named 'lightgbm'` | `lightgbm` is **added to the extra requirements** (unpinned; the newest release with a wheel for Python 3.8 that pip chooses; the installed version is recorded in the run report) | The notebook imports `lightgbm`, which the repository's `requirements.txt` does not list. |

### Known open item that is *not* changed

`paper_002`'s notebook lists its datasets through the OpenML API (`openml.datasets.list_datasets`), which needs the
network (`run_setup.open_items` in `data/seed_papers.json`). The network stays **off** for every paper in every pilot,
and the owner has not decided otherwise. After the `lightgbm` change, `paper_002` is expected to run further and may
stop at that cell, or run into the time limit. Either is a result; neither is a reason to change a setting during the
pilot.

---

## 3. What else is different from Pilot 2

The papers, their pinned commits, the data, the Python versions, and the other limits are the same. What differs, and
is not a setting, is **Repro Radar's own code**: Pilot 2's counted runs are at commits `5772631` and `c10340b`, and
Pilot 3 runs at the then-current main. Since then, sandbox changes were made that apply to every paper:

| Change | Issue |
|---|---|
| `--cap-drop ALL` on the run, install, and bundling containers | #260 |
| The output directory is limited (default 1024 MiB); a run above it is killed and recorded as `OUTPUT_LIMIT_EXCEEDED` | #261 |
| A paper that kills its own watchdog is recorded as `FAILED` with `killed_before_timeout`, not `TIMEOUT` | #262 |
| The container's output is decoded as UTF-8 (in Pilot 2 the preview fields were empty for papers that print non-ASCII bytes) | #248 |

The other changes since then (database migrations, run hashing, scoring, report tools) are not on the run path.
None of the changes above is meant to change a paper's outcome. **All six papers are run again**, the two whose settings do not
change (`paper_006`, `paper_008`) included, so that the denominator stays 6 and so that they show whether the sandbox
changes alone moved anything. If `paper_006` or `paper_008` differ from Pilot 2, that is reported.

---

## 4. Fixed settings (same for every paper unless section 2 says otherwise)

| Setting | Value |
|---|---|
| Images | `repro-radar-sandbox:latest` (3.11), `:py3.9`, `:py3.8`, and `:build`, `:py3.9-build`, `:py3.8-build`, built from `docker/Dockerfile.sandbox` at the recorded commit |
| Network | `--network none` in the build, install, and run phases |
| CPUs | `--cpus=2.0` |
| Memory | `--memory=6g`, `--memory-swap=6g` (`paper_005`: 12g, section 2) |
| Processes | `--pids-limit=100` |
| Scratch space | `/tmp` 64 MB, `/workspace/home` 2048 MB, both `noexec` |
| Output directory | 1024 MiB limit (new since Pilot 2, section 3) |
| Timeout | 3600 s per phase (build, install, run); `paper_004` run phase: 14400 s (section 2) |
| GPU | **None** for the counted run |
| Repetitions | 1 run per paper, no seed loop |
| Order | One paper at a time, never in parallel, so that one run cannot take CPU or memory from another |

---

## 5. Definitions and failure categories

Unchanged from Pilot 1 and Pilot 2 (`docs/PILOT_2.md`, sections 5 and 7), and fixed before any result is seen:
valid run, install success, run success, pilot success, and the three rates with the denominator 6; every paper
without pilot success gets exactly one category, decided by the first failure in the order build, install, run, with
the deciding log line quoted. A status `OUTPUT_LIMIT_EXCEEDED` is categorized `OTHER` and named.

---

## 6. Measurements

Computed by scripts from the stored files, never typed by hand: the three rates, time per phase, peak memory per
paper, dependency conflicts and requested-vs-installed versions (`scripts/pilot_measurements.py`), the failure
categories (`scripts/categorize_pilot_failures.py`), and the three-way comparison (`scripts/pilot_compare.py`,
extended for Pilot 3 in its own issue). Every number in the report names the script and the file it came from.

---

## 7. Steps

1. Record the environment in `data/pilot3_runs/environment.txt` (commit, `docker version`, `docker info`, `nvidia-smi`,
   `python --version`, free disk), from command output only.
2. Build the six images (section 4) from the recorded commit.
3. Check that the data cache holds `paper_002`, `paper_003`, `paper_004`, and `paper_006` data (`.data_cache/`, from
   `scripts/fetch_data.py`); a fetch that fails is a result, not a reason to change a setting.
4. Run each paper once with `python scripts/run_pilot.py <paper_id> --pilot3`: stage at the pinned commit, build phase
   (if any), bundle, install phase, run phase. Files go to `data/pilot3_runs/<paper_id>/` (the same file set as
   Pilot 2, section 8).
5. Categorize the failures and compute the measurements and the comparison with the scripts of section 6.
6. Write the report (section 9) from those files.

The time is dominated by `paper_004` (install about half an hour, run up to four hours) and `paper_006` (about one
hour); all six runs are expected to take most of a working day. If the usage limit of the assistant that drives the run is
reached, the run continues after the reset; a run that was cut in the middle is not counted and is started again.

---

## 8. What may change after the runs start

Pilot 1's and Pilot 2's rules, unchanged:
- **Frozen:** the definitions, the settings of sections 2 and 4, the per-paper settings of Pilot 2, and the category
  rules. If one turns out to be wrong, the result stays as it is, and the change is proposed for a next pilot.
- **Allowed:** fixing a defect in Repro Radar's own code that stops a run from happening as specified here. Each fix is
  its own issue and PR; the paper is re-run, and the report lists the fix and keeps the first attempt's result
  (`data/pilot3_runs/first_attempts/`).
- **Never:** editing a paper's code or data, adding a wrapper, changing a result by hand, or changing a setting
  because of what a run showed (for example, raising a limit a second time).

---

## 9. Report (after the runs)

Below this protocol, in the shape of `docs/PILOT_2.md` section 12: the rates of Pilots 1, 2, and 3 side by side;
a per-paper table with the failure category of each pilot; the deciding log line of each Pilot 3 failure; what was
surprising; limits. The same three-pilot tables are added to the Results section of `docs/report/REPORT.md`, as
generated blocks. The text must say, next to the numbers, that the four settings were chosen after the failures.

---

## 10. Known limits of this pilot

- n = 6, one run per paper: anecdotal, not statistical.
- The four changes were made after seeing Pilot 2's failures (section 1). Pilot 3's rates are not comparable with
  Pilot 2's as a measure of the papers, only as a measure of the effect of these settings.
- The memory (12 GiB) and time (4 hours) values are choices; a paper that needs more fails again, and the choice is
  not tuned further (section 8).
- Repro Radar's own code differs from Pilot 2's (section 3), on one machine (Windows, Docker Desktop, WSL2).
- CPU only, network off, unpinned packages at the newest version that fits (`lightgbm` included).
- No accepted claim is scored, so Pilot 3 says nothing about numerical reproducibility (Tier 2).
