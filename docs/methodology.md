# Repro Radar: Methodology & Scoring Rubric

## 1. Introduction & Problem Definition

In contemporary artificial intelligence and machine learning literature, hundreds of empirical papers are published weekly. Despite this extraordinary research output, automated infrastructure to verify the independent reproducibility of empirical results remains severely limited. Missing hyperparameters, unseeded pseudo-random number generators, unpinned package versions, and non-public data pipelines contribute to an ongoing reproducibility crisis.

**Repro Radar** systematically addresses this gap by evaluating research paper codebases in isolated execution sandboxes, calculating an empirical **Reproducibility Score** (0–100) across four tiers, and providing actionable diagnostic feedback powered by an **AI Decision Layer**.

---

## 2. Four-Tier (4-Tier) Reproducibility Rubric

Repro Radar does not treat reproducibility as a binary "pass / fail" outcome. It employs a multi-dimensional rubric that measures buildability, empirical accuracy, variance stability, and software engineering hygiene:

| Tier | Focus Area | Weight | Evaluated Dimensions |
| :--- | :--- | :---: | :--- |
| **Tier 1: Build & Execution** | Codebase Integrity | **35%** | Git clone, dependency resolution, script entrypoint invocation, clean exit code (0) |
| **Tier 2: Metric Alignment** | Empirical Claim Verification | **35%** | Replication of reported metrics (accuracy, ROC-AUC, F1, loss) within tolerance bounds |
| **Tier 3: Seed Stability** | Multi-Seed Invariance | **15%** | Coefficient of Variation (CV) across repeated seeds and stochastic stability |
| **Tier 4: Documentation & License**| Open Science & Artifacts | **15%** | Permissive OSI license (MIT, Apache, BSD), pinned environment specs, structured logs |

---

### Tier 1: Build & Execution (35%)

Measures the ability to configure and run the software from scratch in an isolated environment:
- **Repository Clone (+25 pts):** The repository is publicly accessible, cloneable without authentication, and structurally intact.
- **Dependency Installation (+25 pts):** The package manager (pip, uv, conda) resolves and installs all required dependencies without unresolvable conflicts.
- **Entrypoint Invocation (+25 pts):** The declared benchmark script (e.g. `run.py`, `eval.py`) launches without missing module exceptions.
- **Clean Termination (+25 pts):** The benchmark process terminates cleanly with an exit code of `0`.

$$\text{Tier 1 Score} \in [0, 100]$$

---

### Tier 2: Metric Alignment (35%)

Evaluates the concordance between numerical claims reported in the paper and values computed in the isolated sandbox run:

1. **Relative Error Formulation:**
   $$\text{RelError} = \frac{|\text{Reproduced} - \text{Claimed}|}{\max(|\text{Claimed}|, 10^{-6})}$$

2. **Scoring Logic:**
   - $\text{RelError} \le \text{Tolerance}$ (Default: 5%) $\rightarrow$ **Full Credit (1.0)**
   - $\text{Tolerance} < \text{RelError} \le 2 \times \text{Tolerance}$ $\rightarrow$ **Partial Credit (0.5)**
   - $\text{RelError} > 2 \times \text{Tolerance}$ or Missing Metric $\rightarrow$ **Zero Credit (0.0)**

$$\text{Tier 2 Score} = \left( \frac{\sum \text{Earned Points}}{\text{Total Claims}} \right) \times 100$$

---

### Tier 3: Seed Stability & Variance (15%)

Verifies whether reported performance relies on a single cherry-picked seed or remains robust across stochastic initializations:
- For multi-seed evaluations ($n \ge 3$), the **Coefficient of Variation (CV)** is computed:
  $$\text{CV} = \frac{\sigma}{\mu}$$
- $\text{CV} \le 2\%$: **100 Points** (Outstanding stability)
- $2\% < \text{CV} \le 5\%$: **85 Points** (High stability)
- $5\% < \text{CV} \le 10\%$: **65 Points** (Acceptable variance)
- $\text{CV} > 10\%$: **40 Points** (High stochastic instability)
- Single-seed clean run: **75 Points** (Baseline clean execution score)

---

### Tier 4: Artifacts, License, & Documentation (15%)

Audits software engineering hygiene and open-science compliance:
- **Permissive Open Source License (+30 pts):** Verified OSI-approved license (MIT, Apache-2.0, BSD-2/3, CC-BY-4.0).
- **Explicit Environment Definition (+30 pts):** Presence of `requirements.txt`, `pyproject.toml`, or `environment.yml`.
- **Documentation & Instructions (+20 pts):** Clear reproduction instructions in `README.md`.
- **Structured Logs & Artifacts (+20 pts):** Programmatic capture of JSON/CSV benchmark summaries or model checkpoints.

---

## 3. Composite Score & Status Classification

The final composite reproducibility score is calculated as a weighted linear combination:

$$\text{Total Score} = 0.35 \times \text{Tier 1} + 0.35 \times \text{Tier 2} + 0.15 \times \text{Tier 3} + 0.15 \times \text{Tier 4}$$

### Neutral & Objective Status Labels

Repro Radar strictly avoids accusatory or subjective characterizations ("Fake", "Fraudulent", "Invalid"). It applies constructive, scientifically neutral labels:

1. **`Verified` [Score $\ge 85$, Tier 1 $\ge 90$, Tier 2 $\ge 80$]:**
   The codebase built cleanly and reproduced empirical claims within tight tolerance bounds.
2. **`Partially Verified` [Score $\ge 60$]:**
   The codebase executed cleanly and the majority of claims replicated; minor discrepancies or incomplete environment specifications exist.
3. **`Needs Review` [Score $< 60$, Tier 1 $\ge 75$]:**
   The codebase built and ran successfully, but reproduced metrics diverged significantly from reported claims. This indicates potential hardware disparities, dataset version shifts, or unseeded operations requiring human inspection.
4. **`Failed` [Tier 1 $< 50$ or Fatal Crash]:**
   The codebase could not be executed due to broken dependencies, missing files, or runtime exceptions.

---

## 4. Security, Isolation, & Ethical Standards

- **Containerized Sandboxing:** External repositories run in ephemeral, isolated Docker containers with host-system boundaries.
- **Resource Constraints:** Strict limits on execution time (timeout = 600s), memory (max 8GB), and CPU allocation prevent infinite loops and denial-of-service vulnerabilities.
- **Permissive Repositories Only:** Only publicly licensed repositories (MIT, Apache, BSD) are ingested and evaluated.
- **Transparent Diagnostics:** Detailed build logs (`stdout`, `stderr`) and dependency resolutions are stored transparently alongside every score.
