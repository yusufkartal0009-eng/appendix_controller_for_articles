# Repro Radar — Corpus Verification

> What has been checked about each entry in `data/seed_papers.json`, and what has not.
> Anything not checked is marked **UNVERIFIED**. Last updated 2026-09-26.

---

## 1. Automated checks (`scripts/verify_corpus.py`)

The verifier runs in CI on every push and pull request, and the job is blocking. For every entry it checks:

| Check | Passes when |
|---|---|
| `paper` | The paper page opens and its title matches the entry title (similarity ≥ 0.90) |
| `repo` | The GitHub repository exists (renames are followed and reported) |
| `license` | GitHub's `license.spdx_id` is an allowed open license **and** equals the declared license |
| `script` | `target_script` exists in the repository at the pinned `repo_commit` |

A network error counts as a failure. Re-run locally with:

```bash
GH_TOKEN=$(gh auth token) python scripts/verify_corpus.py
```

**Result on 2026-09-26: 6 of 6 entries pass.** Passing proves that the links, license, and script file are real. It does **not** prove that the script runs or that it reproduces the claims.

---

## 2. Per-entry status

| Entry | Paper | Repository @ pinned commit | License | Target script | GPU | Data download | Claims |
|---|---|---|---|---|---|---|---|
| `paper_002` | [arXiv 2207.01848](https://arxiv.org/abs/2207.01848) TabPFN | `PriorLabs/TabPFN` @ `ddf5e85` | Apache-2.0 | `tabpfn/scripts/tabular_baselines.py` | UNVERIFIED (README: "CUDA-supporting" implementation) | UNVERIFIED | UNVERIFIED |
| `paper_003` | [arXiv 2106.11959](https://arxiv.org/abs/2106.11959) FT-Transformer | `yandex-research/rtdl-revisiting-models` @ `e3ed46c` | Apache-2.0 | `bin/ft_transformer.py` | Expected (README environment pins `cudatoolkit`) | UNVERIFIED | UNVERIFIED |
| `paper_004` | [arXiv 2307.14338](https://arxiv.org/abs/2307.14338) TabR | `yandex-research/tabular-dl-tabr` @ `17baa90` | MIT | `bin/tabr.py` | Recommended; README documents a CPU-only environment | Yes (README: `wget` from Hugging Face) | UNVERIFIED |
| `paper_005` | [bioRxiv 2020.04.21.053975](https://www.biorxiv.org/content/10.1101/2020.04.21.053975v1) FastSK | `QData/FastSK` @ `d275a23` | Apache-2.0 | `results/run_gridsearch.py` | Not required per README (C++ implementation) | No (README: datasets included in `data/`) | **SUSPECT** (see below) |
| `paper_006` | [arXiv 2106.01342](https://arxiv.org/abs/2106.01342) SAINT | `somepago/saint` @ `e288e84` (archived) | Apache-2.0 | `train.py` | Used in the paper (README: one RTX 2080Ti); CPU UNVERIFIED | Yes (OpenML by `--dset_id` at runtime) | UNVERIFIED |
| `paper_008` | [arXiv 2112.02962](https://arxiv.org/abs/2112.02962) DANets | `WhatAShot/DANet` @ `b007c57` | MIT | `main.py` | Expected (README: `--g [gpu_id]`) | Yes (README: manual download links) | **SUSPECT** (see below) |

Full commit SHAs are in `data/seed_papers.json` (`repo_commit`).

### Claims

No claim value in the corpus has been checked against the paper's tables yet; that is the claim-extraction work item. Two entries are flagged **SUSPECT** because their original metadata was wrong, so their claims may not come from the paper at all:

- `paper_005`: the entry originally named a different title and venue ("Fast Sequence Kernel SVM for Lightweight Text and Sequence Classification", KDD 2021) and linked an unrelated physics paper. Its claims cite an "EP3602" dataset; the FastSK repository README uses datasets such as `EP300`.
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
