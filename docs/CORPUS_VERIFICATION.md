# Repro Radar — Corpus Verification

> What has been checked about each entry in `data/seed_papers.json`, and what has not.
> Anything not checked is marked **UNVERIFIED**. Last updated 2026-09-27.
>
> **No entry is verified as a whole:** an entry counts as verified only when every row below is complete, and every entry still has at least one `UNVERIFIED` claim and unchecked runnability.

---

## 1. Automated checks (`scripts/verify_corpus.py`)

The verifier runs in CI on every push and pull request, and the job is blocking. For every entry it checks:

| Check | Passes when |
|---|---|
| `paper` | The paper's title matches the entry title (similarity ≥ 0.90): read from the arXiv abstract page, or from Crossref for DOI links such as bioRxiv (whose pages rate-limit CI runners) |
| `repo` | The GitHub repository exists (renames are followed and reported) |
| `license` | GitHub's `license.spdx_id` is an allowed open license **and** equals the declared license |
| `script` | `target_script` exists in the repository at the pinned `repo_commit` |

A network error counts as a failure. Re-run locally with:

```bash
GH_TOKEN=$(gh auth token) python scripts/verify_corpus.py
REPRO_RADAR_NETWORK_TESTS=1 GH_TOKEN=$(gh auth token) pytest tests/test_seed_integrity.py -v
```

`tests/test_seed_integrity.py` repeats the `repo`, `license`, and `script` checks as one pytest case per entry; it also runs in the CI corpus job.

**Result on 2026-09-26: 6 of 6 entries pass.** Passing proves that the links, license, and script file are real. It does **not** prove that the script runs or that it reproduces the claims.

---

## 2. Per-entry status

| Entry | Paper | Repository @ pinned commit | License | Target script | GPU | Data download | Claims |
|---|---|---|---|---|---|---|---|
| `paper_002` | [arXiv 2207.01848](https://arxiv.org/abs/2207.01848) TabPFN | `PriorLabs/TabPFN` @ `ddf5e85` | Apache-2.0 | `tabpfn/scripts/tabular_baselines.py` | UNVERIFIED (README: "CUDA-supporting" implementation) | UNVERIFIED | 0 of 2 found (0.895 is another method's value) |
| `paper_003` | [arXiv 2106.11959](https://arxiv.org/abs/2106.11959) FT-Transformer | `yandex-research/rtdl-revisiting-models` @ `e3ed46c` | Apache-2.0 | `bin/ft_transformer.py` | Expected (README environment pins `cudatoolkit`) | UNVERIFIED | 2 of 3 found |
| `paper_004` | [arXiv 2307.14338](https://arxiv.org/abs/2307.14338) TabR | `yandex-research/tabular-dl-tabr` @ `17baa90` | MIT | `bin/tabr.py` | Recommended; README documents a CPU-only environment | Yes (README: `wget` from Hugging Face) | 0 of 3 found |
| `paper_005` | [bioRxiv 2020.04.21.053975](https://www.biorxiv.org/content/10.1101/2020.04.21.053975v1) FastSK | `QData/FastSK` @ `d275a23` | Apache-2.0 | `results/run_gridsearch.py` | Not required per README (C++ implementation) | No (README: datasets included in `data/`) | 0 of 3 found, **SUSPECT** |
| `paper_006` | [arXiv 2106.01342](https://arxiv.org/abs/2106.01342) SAINT | `somepago/saint` @ `e288e84` (archived) | Apache-2.0 | `train.py` | Used in the paper (README: one RTX 2080Ti); CPU UNVERIFIED | Yes (OpenML by `--dset_id` at runtime) | 0 of 3 found |
| `paper_008` | [arXiv 2112.02962](https://arxiv.org/abs/2112.02962) DANets | `WhatAShot/DANet` @ `b007c57` | MIT | `main.py` | Expected (README: `--g [gpu_id]`) | Yes (README: manual download links) | 0 of 2 found, **SUSPECT** |

Full commit SHAs are in `data/seed_papers.json` (`repo_commit`).

### Claims checked against the papers (2026-09-27)

Method: each paper's PDF (latest arXiv version, or the bioRxiv preprint for FastSK) was converted to text with `pypdf`, and every claim value was searched in the forms it can be printed (`0.842`, `.842`, `84.2`, `84.20`), also allowing the spaces `pypdf` inserts inside numbers. Each hit was read in context to confirm the metric, method, and table. **Found** means the value, method, metric, and table all match; everything else is `UNVERIFIED`. Page numbers are PDF pages of the version named. Claim values in `data/seed_papers.json` were not changed.

| Entry | Claim | Seed value (seed source) | In the paper | Result |
|---|---|---|---|---|
| `paper_002` (arXiv v6) | `mean_roc_auc` | 0.895 (Table 1) | Table 2, p. 18, row "Mean AUC OVO": **0.895 is AutoGluon's value**; TabPFN's is `0.894 ±.01` | UNVERIFIED (wrong method) |
| `paper_002` | `inference_seconds` | 1.25 (Section 4.2) | `1.25` not found anywhere | UNVERIFIED |
| `paper_003` (arXiv v5) | `ft_transformer_rmse` | 0.459 (Table 2, California Housing) | Table 2, p. 7, row "FT-T", column "CA ↓" (RMSE): `0.459` | **Found** |
| `paper_003` | `resnet_rmse` | 0.486 (Table 2, California Housing) | Table 2, p. 7, row "ResNet", column "CA ↓": `0.486` | **Found** |
| `paper_003` | `xgboost_rmse` | 0.453 (Table 2) | `0.453` not found; Table 2 lists DL models only | UNVERIFIED |
| `paper_004` (arXiv v2) | `tabr_average_rank` | 2.15 (Table 1) | `2.15` not found | UNVERIFIED |
| `paper_004` | `ft_transformer_average_rank` | 3.42 (Table 1) | `3.42` not found | UNVERIFIED |
| `paper_004` | `xgboost_average_rank` | 3.2 (Table 1) | only as the section number "3.2" | UNVERIFIED |
| `paper_005` (bioRxiv, 2020-06-30 PDF) | `ep3602_auroc` | 0.912 (Table 3) | not found; the dataset "EP3602" does not occur (the paper uses `EP300`, 21 mentions) | UNVERIFIED, **SUSPECT** |
| `paper_005` | `ep3602_accuracy` | 0.875 (Table 3) | not found; no "EP3602" | UNVERIFIED, **SUSPECT** |
| `paper_005` | `kernel_speedup_factor` | 15.4 (Figure 4) | `15.4` not found | UNVERIFIED, **SUSPECT** |
| `paper_006` (arXiv v1) | `arcene_auroc` | 0.887 (Table 1) | not found ("Arcene"/"arcene" occurs 13 times) | UNVERIFIED |
| `paper_006` | `bank_marketing_accuracy` | 0.914 (Table 1) | not found | UNVERIFIED |
| `paper_006` | `xgboost_arcene_auroc` | 0.865 (Table 1) | not found | UNVERIFIED |
| `paper_008` (arXiv v4) | `forest_covertype_accuracy` | 0.971 (Table 2) | not found ("Forest" occurs 17 times) | UNVERIFIED, **SUSPECT** |
| `paper_008` | `higgs_auroc` | 0.849 (Table 2) | not found; "HIGGS"/"Higgs" does not occur in the paper | UNVERIFIED, **SUSPECT** |

**Summary: 2 of 16 claims found in their papers** (both `paper_003`). One value exists but belongs to another method (`paper_002`), and two entries cite datasets their papers do not use (`paper_005` "EP3602", `paper_008` HIGGS). Before the pilot, the unverified claims must be replaced with values copied from the papers, or dropped; that is the claim-extraction work (W1-W7), not done here.

Entries flagged **SUSPECT** had wrong metadata originally, so their claims may not come from the paper at all:

- `paper_005`: the entry originally named a different title and venue ("Fast Sequence Kernel SVM for Lightweight Text and Sequence Classification", KDD 2021) and linked an unrelated physics paper.
- `paper_008`: the entry originally named the paper "DANet: Dual Adversarial Network for Tabular Data"; the linked paper and repository are *DANets: Deep Abstract Networks*.

### Runnability

Not checked for any entry. Known obstacles from the READMEs:

- Script arguments: `paper_003` and `paper_008` take a config file, `paper_006` needs `--dset_id` and `--task`, and `paper_005`'s scripts expect to be run from `results/`.
- `paper_005` needs its C++ extension built (the README clones with submodules).
- **Sandbox runs use `--network none`**, so entries that download data at runtime (`paper_004`, `paper_006`, `paper_008`, and possibly `paper_002`, `paper_003`) need their data staged before execution.

---

## 3. Removed entries

| Entry | Reason |
|---|---|
| `paper_001` (tabular-benchmark) | The repository has no license file (GitHub reports none). The project only evaluates open-licensed code. |
| `paper_007` (TabNet) | `dreamquark-ai/tabnet` is a community reimplementation, not the paper's code, and has no runnable script (`run_census.py` does not exist; only a notebook). A wrapper would measure our wrapper, not the published code. An external review also reported its claim values as wrong (not re-checked here). |

## 4. Changes made to kept entries

| Entry | Changes |
|---|---|
| `paper_002` | Repository moved `automl/TabPFN` → `PriorLabs/TabPFN`; the script path was wrong (`scripts/tabular_baselines.py` → `tabpfn/scripts/tabular_baselines.py`); pinned to the last commit before the TabPFN v2 rewrite, which deleted the script. |
| `paper_003` | Repository moved to `rtdl-revisiting-models`; `bin/evaluate.py` does not exist in it (it belongs to the TabR repository) → `bin/ft_transformer.py`; license corrected MIT → Apache-2.0. |
| `paper_004` | Title updated to the current arXiv title; license corrected Apache-2.0 → MIT. |
| `paper_005` | Paper link, title, year, and venue corrected to the real FastSK paper; license corrected BSD-3-Clause → Apache-2.0; script `fastsk/FastSK.py` (does not exist) → `results/run_gridsearch.py` (the README's experiment entry point). |
| `paper_006` | Repository typo `somepalle/saint` (404) → `somepago/saint`; title corrected to the arXiv title; license corrected MIT → Apache-2.0. |
| `paper_008` | Title corrected to the linked paper (DANets). |

All kept entries were pinned to a `repo_commit`.

## 5. Fix or replace after Pilot 1 (2026-10-04, #166)

Pilot 1 ran 0 of 6 papers (`docs/PILOT_WEEK2.md` section 11). That result stays in the record. **No paper was
replaced.** Replacing papers because they fail would raise the success rate artificially, and the claims of all six
papers were already extracted (plan stage 1). The owner decided on 2026-10-04 to fix `paper_002` to `paper_006` and
to keep `paper_008` and report it as data not accessible.

Each decision, its reason, and the sandbox options it needs are in the paper's `run_setup` entry in
`data/seed_papers.json` (read by `src/sandbox/run_setup.py`). Datasets are fetched on the host with
`scripts/fetch_data.py` and mounted read-only, because the sandbox has no network. **No paper has been run with
its run setup yet.** Whether the fixes work is a question for Pilot 2 (#171).

| Paper | Decision | What the run setup changes | Still open (not done) |
|---|---|---|---|
| `paper_002` | fix | Entry point: the notebook `tabpfn/RunFullDatasetAnalyses.ipynb`, run with `nbconvert`, from `tabpfn/`, on a writable copy (the notebook writes `results/`) | `nbconvert` and `ipykernel` are not in the repository's requirements. The notebook's OpenML-CC18 datasets are not yet listed for the data cache |
| `paper_003` | fix | The dataset archive (4.07 GiB, README "Data") is fetched on the host and mounted as `data/` | — |
| `paper_004` | fix | Runs on a writable per-run copy (it writes next to its config). `data.tar` (2.88 GiB) is mounted as `data/` | — |
| `paper_005` | fix | Starts in `results/` (README: `cd results/`) | The `fastsk` C++ extension needs a compiler and a build step that runs package code; both are owner decisions. The `python-dateutil` / `pandas` conflict is in the repository's own requirements |
| `paper_006` | fix | OpenML dataset 1461 is fetched on the host into an OpenML cache and mounted at `~/.openml/cache` | Not checked: whether openml 0.11.0 reads the cache without contacting the server |
| `paper_008` | keep, report as `DATA_NOT_ACCESSIBLE` | The pilot command unchanged | — (the split files `train_idx.csv`, `valid_idx.csv`, and `test_idx.csv` are not published; this is a finding about the paper) |

