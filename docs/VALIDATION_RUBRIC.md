# Model Validation & Project Accuracy Evaluation Rubric 📐

This specification establishes the formal mathematical rubric, statistical tolerances, variance benchmarks, and edge-case anomaly matrices used by **Repro Radar** to audit empirical scientific replication accuracy.

---

## 1. Metric Taxonomy & Category-Aware Tolerances

Evaluating all empirical metrics with a blanket $5\%$ relative tolerance leads to critical failure modes:
- **Loss / Error Metrics:** Lower is better; a replicated run that achieves a *lower* loss than claimed should receive full marks, not a penalty.
- **Hardware-Sensitive Metrics:** Execution latencies, throughput (QPS), and peak VRAM consumption depend directly on host microarchitecture, memory bus bandwidth, and thermal throttling. Applying a narrow $5\%$ window penalizes mathematically valid code.
- **Bounded Rate Metrics near 1.0 or 0.0:** A claim of $0.990$ vs a reproduction of $0.975$ represents a $1.51\%$ relative error, but a significant absolute deviation; conversely, near $0.0$, relative error can explode.

### Metric Classification Matrix

| Category | Typical Metrics | Directionality | Relative Tolerance | Absolute Guard ($\epsilon_{abs}$) | Scoring Behavior |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Bounded Rate** | Accuracy, AUROC, F1, Precision, Recall, BLEU, ROUGE | Higher is better | $\le 5\%$ ($\le 4\%$ for AUC) | $0.02$ ($0.015$ for AUC) | Dual relative & absolute boundary check. Full credit if either satisfied. |
| **Unbounded Loss** | MSE, RMSE, MAE, Cross-Entropy, Perplexity, NLL | Lower is better | $\le 5\%$ degradation | N/A | Full credit ($100\%$) if $v_{repro} \le v_{claimed}$. Partial credit on minor degradation. |
| **Runtime & Hardware** | Latency (ms), Throughput (QPS), GPU VRAM (MB) | Metric-specific | $\le 25\% - 30\%$ | N/A | Broad hardware variance allowance; flags note host hardware differences. |
| **Correlation** | Pearson $r$, Spearman $\rho$ | Higher is better | $\le 8\%$ | $0.05$ | Sign preservation enforced. |

---

## 2. Mathematical Formulations

### 2.1 Bounded Rate Metric Alignment
For a bounded metric $m \in [0, 1]$ (or $[0, 100]$):

$$\text{RelError}(v_{repro}, v_{claimed}) = \frac{|v_{repro} - v_{claimed}|}{\max(|v_{claimed}|, \epsilon_{floor})}$$

$$\text{AbsError}(v_{repro}, v_{claimed}) = |v_{repro} - v_{claimed}|$$

$$\text{Score}_{rate} = \begin{cases} 
100.0 & \text{if } \text{RelError} \le 0.5 \times \tau_{rel} \lor \text{AbsError} \le 0.5 \times \tau_{abs} \\
90.0 & \text{if } \text{RelError} \le \tau_{rel} \lor \text{AbsError} \le \tau_{abs} \\
50.0 & \text{if } \tau_{rel} < \text{RelError} \le 2.0 \times \tau_{rel} \\
0.0 & \text{otherwise}
\end{cases}$$

### 2.2 Unbounded Loss Evaluation (Lower is Better)
For an optimization loss or regression error metric $L$:

$$\Delta_{deg} = \frac{v_{repro} - v_{claimed}}{|v_{claimed}|}$$

$$\text{Score}_{loss} = \begin{cases} 
100.0 & \text{if } v_{repro} \le v_{claimed} \\
100.0 - \left(\frac{\Delta_{deg}}{\tau_{loss}}\right) \times 20.0 & \text{if } 0 < \Delta_{deg} \le \tau_{loss} \\
\max\left(30.0, \; 80.0 - \left(\frac{\Delta_{deg} - \tau_{loss}}{\tau_{loss}}\right) \times 50.0\right) & \text{if } \tau_{loss} < \Delta_{deg} \le 2.0 \times \tau_{loss} \\
0.0 & \text{if } \Delta_{deg} > 2.0 \times \tau_{loss}
\end{cases}$$

---

## 3. Multi-Seed Stability & Variance Benchmarking

Scientific claims that only replicate under a single lucky seed fail empirical integrity. Repro Radar executes replication across repeated pseudorandom seeds ($S = \{s_1, s_2, \dots, s_n\}$ for $n \ge 3$) and computes the sample mean $\bar{x}$, unbiased sample variance $s^2$, standard deviation $s$, and the **Coefficient of Variation (CV)**:

$$\bar{x} = \frac{1}{n} \sum_{i=1}^{n} x_i, \qquad s = \sqrt{\frac{1}{n-1} \sum_{i=1}^{n} (x_i - \bar{x})^2}$$

$$\text{CV} = \left(\frac{s}{|\bar{x}|}\right) \times 100\%$$

### Stability Grading Scale

| Coefficient of Variation (CV) | Classification | Stability Score | Diagnostic Implication |
| :--- | :--- | :---: | :--- |
| $\text{CV} \le 2.0\%$ | **Deterministic** | **100** | Strict numerical determinism and robust random seed conditioning. |
| $2.0\% < \text{CV} \le 5.0\%$ | **Stable** | **90** | Standard acceptable stochastic noise for deep learning / empirical algorithms. |
| $5.0\% < \text{CV} \le 10.0\%$ | **Moderate Variance** | **65** | Borderline stochastic sensitivity; authors should provide seed averages. |
| $\text{CV} > 10.0\%$ | **Unstable** | $\le \mathbf{40}$ | Severe seed dependence; high probability of cherry-picked experimental reporting. |

### 95% Confidence Interval
A two-tailed Student's t-distribution confidence interval is estimated:

$$\text{CI}_{95\%} = \left[ \bar{x} - t_{\alpha/2, n-1} \frac{s}{\sqrt{n}}, \;\; \bar{x} + t_{\alpha/2, n-1} \frac{s}{\sqrt{n}} \right]$$

If claimed baseline $\mu_{claimed} \in \text{CI}_{95\%}$, the replication is statistically indistinguishable from the claim at $p = 0.05$.

---

## 4. Edge-Case & Anomaly Detection Matrix

| Anomaly Code | Condition Trigger | Diagnostic Action |
| :--- | :--- | :--- |
| `PERFECT_SCORE_WARNING` | Bounded metric $v_{repro} = 1.0000$ while $v_{claimed} < 1.0000$ | Triggers audit for test dataset contamination, label leakage, or dummy mock returns. |
| `ZERO_CLAIM_FALLBACK` | $v_{claimed} = 0.0$ | Disables division by zero; switches to absolute epsilon comparison ($\epsilon \le 0.02$). |
| `SIGN_FLIP_ANOMALY` | $\text{sign}(v_{repro}) \ne \text{sign}(v_{claimed})$ | Flags fundamental algorithmic divergence or inverted objective function. |
| `NAN_INF_CORRUPTION` | $\text{isnan}(v) \lor \text{isinf}(v)$ | Flags numerical overflow, vanishing gradient, or zero division in tensor operations. |

---

## 5. Software Integration

This rubric is programmatically implemented in:
- [`src/validation_rubric.py`](file:///C:/Users/yusuf/.gemini/antigravity/scratch/repro-radar/src/validation_rubric.py): `ModelValidationRubric`, `MetricToleranceSpec`, `MultiSeedStabilityAnalyzer`.
- [`src/scoring.py`](file:///C:/Users/yusuf/.gemini/antigravity/scratch/repro-radar/src/scoring.py): Integrated with `ReproducibilityScorer`.
- [`tests/test_validation_rubric.py`](file:///C:/Users/yusuf/.gemini/antigravity/scratch/repro-radar/tests/test_validation_rubric.py): Full test coverage across all metric classes and edge cases.
