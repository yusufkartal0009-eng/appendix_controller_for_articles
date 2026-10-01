"""Comprehensive model validation, statistical accuracy evaluation, and replication rubric."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class MetricCategory(str, Enum):
    """Categorization of empirical evaluation metrics."""
    BOUNDED_RATE = "bounded_rate"  # [0, 1] e.g. Accuracy, AUROC, F1, Precision, Recall, BLEU
    UNBOUNDED_LOSS = "unbounded_loss"  # [0, inf) e.g. MSE, RMSE, MAE, Perplexity, NLL (lower is better)
    RUNTIME_HARDWARE = "runtime_hardware"  # Execution latency, throughput, memory (hardware sensitive)
    CORRELATION = "correlation"  # [-1, 1] e.g. Pearson r, Spearman rho


@dataclass
class MetricToleranceSpec:
    """Tolerance specification for an individual empirical claim."""
    category: MetricCategory = MetricCategory.BOUNDED_RATE
    relative_tolerance: float = 0.05  # Default 5%
    absolute_tolerance: float = 0.02  # Epsilon for values near boundary (e.g. 0.98 vs 0.99)
    lower_is_better: bool = False
    hardware_dependent: bool = False


DEFAULT_TOLERANCE_SPECS: dict[str, MetricToleranceSpec] = {
    # Bounded rates (higher is better)
    "accuracy": MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.05, absolute_tolerance=0.02),
    "acc": MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.05, absolute_tolerance=0.02),
    "auroc": MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.04, absolute_tolerance=0.015),
    "auc": MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.04, absolute_tolerance=0.015),
    "roc_auc": MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.04, absolute_tolerance=0.015),
    "f1": MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.05, absolute_tolerance=0.02),
    "f1_score": MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.05, absolute_tolerance=0.02),
    "precision": MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.05, absolute_tolerance=0.02),
    "recall": MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.05, absolute_tolerance=0.02),
    "bleu": MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.06, absolute_tolerance=1.5),
    "rouge": MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.06, absolute_tolerance=0.02),

    # Continuous loss & error metrics (lower is better)
    "mse": MetricToleranceSpec(MetricCategory.UNBOUNDED_LOSS, relative_tolerance=0.05, lower_is_better=True),
    "rmse": MetricToleranceSpec(MetricCategory.UNBOUNDED_LOSS, relative_tolerance=0.05, lower_is_better=True),
    "mae": MetricToleranceSpec(MetricCategory.UNBOUNDED_LOSS, relative_tolerance=0.05, lower_is_better=True),
    "loss": MetricToleranceSpec(MetricCategory.UNBOUNDED_LOSS, relative_tolerance=0.05, lower_is_better=True),
    "perplexity": MetricToleranceSpec(MetricCategory.UNBOUNDED_LOSS, relative_tolerance=0.08, lower_is_better=True),

    # Hardware sensitive runtime metrics (hardware dependent)
    "latency_ms": MetricToleranceSpec(MetricCategory.RUNTIME_HARDWARE, relative_tolerance=0.30, lower_is_better=True, hardware_dependent=True),
    "latency": MetricToleranceSpec(MetricCategory.RUNTIME_HARDWARE, relative_tolerance=0.30, lower_is_better=True, hardware_dependent=True),
    "runtime": MetricToleranceSpec(MetricCategory.RUNTIME_HARDWARE, relative_tolerance=0.30, lower_is_better=True, hardware_dependent=True),
    "throughput": MetricToleranceSpec(MetricCategory.RUNTIME_HARDWARE, relative_tolerance=0.30, lower_is_better=False, hardware_dependent=True),
    "throughput_qps": MetricToleranceSpec(MetricCategory.RUNTIME_HARDWARE, relative_tolerance=0.30, lower_is_better=False, hardware_dependent=True),
    "gpu_memory_mb": MetricToleranceSpec(MetricCategory.RUNTIME_HARDWARE, relative_tolerance=0.20, lower_is_better=True, hardware_dependent=True),
}


@dataclass
class MetricEvaluationResult:
    """Evaluation breakdown for an individual metric claim."""
    metric_name: str
    category: str
    claimed_value: float
    reproduced_value: float
    relative_error: float
    absolute_error: float
    is_reproduced: bool
    score: float  # 0.0 to 100.0
    notes: list[str] = field(default_factory=list)


@dataclass
class MultiSeedStabilityResult:
    """Statistical stability outcome across multiple random seed executions."""
    metric_name: str
    seed_values: list[float]
    mean: float
    variance: float
    std_dev: float
    coefficient_of_variation_pct: float
    stability_score: float  # 0.0 to 100.0
    status: str  # 'DETERMINISTIC', 'STABLE', 'MODERATE_VARIANCE', 'UNSTABLE'
    confidence_interval_95: tuple[float, float] = (0.0, 0.0)


@dataclass
class ValidationReport:
    """Structured report returned by the ModelValidationRubric."""
    paper_id: str
    overall_validity_score: float  # 0.0 to 100.0
    validation_status: str  # 'VERIFIED', 'PARTIALLY_VERIFIED', 'NEEDS_REVIEW', 'FAILED'
    metric_results: dict[str, MetricEvaluationResult]
    stability_results: dict[str, MultiSeedStabilityResult]
    anomalies: list[str]
    summary_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert validation report into a serializable dictionary."""
        return {
            "paper_id": self.paper_id,
            "overall_validity_score": round(self.overall_validity_score, 2),
            "validation_status": self.validation_status,
            "metric_results": {k: asdict(v) for k, v in self.metric_results.items()},
            "stability_results": {k: asdict(v) for k, v in self.stability_results.items()},
            "anomalies": self.anomalies,
            "summary_notes": self.summary_notes,
        }


class ModelValidationRubric:
    """Executes quantitative, statistical, and category-aware model validation."""

    def __init__(self, custom_specs: dict[str, MetricToleranceSpec] | None = None):
        self.specs: dict[str, MetricToleranceSpec] = dict(DEFAULT_TOLERANCE_SPECS)
        if custom_specs:
            self.specs.update(custom_specs)

    def resolve_spec(self, metric_name: str) -> MetricToleranceSpec:
        """Resolve tolerance specification for a given metric identifier."""
        clean_name = metric_name.lower().strip().replace("-", "_").replace(" ", "_")
        if clean_name in self.specs:
            return self.specs[clean_name]

        # Fuzzy heuristic fallback
        if "loss" in clean_name or "error" in clean_name or "rmse" in clean_name or "mse" in clean_name:
            return MetricToleranceSpec(MetricCategory.UNBOUNDED_LOSS, relative_tolerance=0.06, lower_is_better=True)
        if "latency" in clean_name or "time" in clean_name or "memory" in clean_name or "throughput" in clean_name:
            return MetricToleranceSpec(MetricCategory.RUNTIME_HARDWARE, relative_tolerance=0.25, hardware_dependent=True)
        if "corr" in clean_name:
            return MetricToleranceSpec(MetricCategory.CORRELATION, relative_tolerance=0.08, absolute_tolerance=0.05)

        # Default bounded rate
        return MetricToleranceSpec(MetricCategory.BOUNDED_RATE, relative_tolerance=0.05, absolute_tolerance=0.02)

    def evaluate_single_metric(
        self,
        metric_name: str,
        claimed: float,
        reproduced: float,
    ) -> MetricEvaluationResult:
        """Evaluate a single empirical claim with category-aware mathematical tolerance."""
        spec = self.resolve_spec(metric_name)
        notes: list[str] = []

        abs_error = abs(reproduced - claimed)

        # Handle zero-claim edge case safely
        if math.isclose(claimed, 0.0, abs_tol=1e-9):
            rel_error = 0.0 if math.isclose(reproduced, 0.0, abs_tol=spec.absolute_tolerance) else 1.0
        else:
            rel_error = abs_error / abs(claimed)

        # Evaluation based on metric category
        if spec.category == MetricCategory.UNBOUNDED_LOSS:
            # Lower is better: if reproduced is lower than claimed, it is 100% valid!
            if reproduced <= claimed:
                is_reproduced = True
                score = 100.0
                notes.append(f"Reproduced loss ({reproduced}) improved upon baseline claim ({claimed})")
            else:
                degradation = (reproduced - claimed) / abs(claimed)
                if degradation <= spec.relative_tolerance:
                    is_reproduced = True
                    # Partial credit curve: 100 down to 80 within tolerance
                    score = 100.0 - (degradation / spec.relative_tolerance) * 20.0
                    notes.append(f"Loss degradation ({degradation*100:.2f}%) within acceptable tolerance ({spec.relative_tolerance*100:.1f}%)")
                elif degradation <= spec.relative_tolerance * 2.0:
                    is_reproduced = False
                    # Borderline credit: 80 down to 40
                    score = max(30.0, 80.0 - ((degradation - spec.relative_tolerance) / spec.relative_tolerance) * 50.0)
                    notes.append(f"Loss degradation ({degradation*100:.2f}%) exceeded tolerance, received partial credit")
                else:
                    is_reproduced = False
                    score = 0.0
                    notes.append(f"Severe loss degradation ({degradation*100:.2f}%) exceeds threshold")

        elif spec.category == MetricCategory.RUNTIME_HARDWARE:
            # Hardware-sensitive metrics use wide tolerance and note hardware variance
            if rel_error <= spec.relative_tolerance:
                is_reproduced = True
                score = 100.0
                notes.append(f"Runtime metric within hardware tolerance ({spec.relative_tolerance*100:.0f}%)")
            else:
                is_reproduced = False
                score = max(20.0, 100.0 - (rel_error / spec.relative_tolerance) * 50.0)
                notes.append(f"Runtime metric diverged by {rel_error*100:.1f}% (hardware variance note)")

        else:
            # Bounded Rate (e.g. Accuracy, AUROC, F1)
            # Both relative error and absolute epsilon guard are considered
            passed_relative = rel_error <= spec.relative_tolerance
            passed_absolute = abs_error <= spec.absolute_tolerance

            if passed_relative or passed_absolute:
                is_reproduced = True
                if rel_error <= (spec.relative_tolerance * 0.5):
                    score = 100.0
                    notes.append(f"Tight replication match ({rel_error*100:.2f}% error)")
                else:
                    score = 90.0
                    notes.append(f"Replication matched within boundary ({rel_error*100:.2f}% error)")
            elif rel_error <= (spec.relative_tolerance * 2.0):
                is_reproduced = False
                score = 50.0
                notes.append(f"Borderline divergence: relative error is {rel_error*100:.2f}%")
            else:
                is_reproduced = False
                score = 0.0
                notes.append(f"Failed to reproduce: relative error {rel_error*100:.2f}% exceeds tolerance")

        return MetricEvaluationResult(
            metric_name=metric_name,
            category=spec.category.value,
            claimed_value=claimed,
            reproduced_value=reproduced,
            relative_error=round(rel_error, 4),
            absolute_error=round(abs_error, 4),
            is_reproduced=is_reproduced,
            score=round(score, 2),
            notes=notes,
        )

    def analyze_multi_seed_stability(
        self,
        metric_name: str,
        seed_values: list[float],
    ) -> MultiSeedStabilityResult:
        """Calculate multi-seed variance, standard deviation, and Coefficient of Variation (CV)."""
        n = len(seed_values)
        if n < 1:
            raise ValueError("At least one seed value must be provided for stability analysis")

        mean = sum(seed_values) / n

        if n == 1:
            return MultiSeedStabilityResult(
                metric_name=metric_name,
                seed_values=seed_values,
                mean=round(mean, 4),
                variance=0.0,
                std_dev=0.0,
                coefficient_of_variation_pct=0.0,
                stability_score=100.0,
                status="DETERMINISTIC",
                confidence_interval_95=(round(mean, 4), round(mean, 4)),
            )

        variance = sum((x - mean) ** 2 for x in seed_values) / (n - 1)
        std_dev = math.sqrt(variance)

        if math.isclose(mean, 0.0, abs_tol=1e-9):
            cv_pct = 0.0
        else:
            cv_pct = (std_dev / abs(mean)) * 100.0

        # Normal approximation for 95% Confidence Interval
        t_crit = 1.96 if n >= 30 else 2.262  # approx for smaller n
        margin_of_error = t_crit * (std_dev / math.sqrt(n))
        ci_95 = (round(mean - margin_of_error, 4), round(mean + margin_of_error, 4))

        # Stability Scoring
        if cv_pct <= 2.0:
            stability_score = 100.0
            status = "DETERMINISTIC"
        elif cv_pct <= 5.0:
            stability_score = 90.0
            status = "STABLE"
        elif cv_pct <= 10.0:
            stability_score = 65.0
            status = "MODERATE_VARIANCE"
        else:
            stability_score = max(10.0, 100.0 - (cv_pct * 5.0))
            status = "UNSTABLE"

        return MultiSeedStabilityResult(
            metric_name=metric_name,
            seed_values=seed_values,
            mean=round(mean, 4),
            variance=round(variance, 6),
            std_dev=round(std_dev, 4),
            coefficient_of_variation_pct=round(cv_pct, 2),
            stability_score=round(stability_score, 2),
            status=status,
            confidence_interval_95=ci_95,
        )

    def detect_anomalies(
        self,
        claimed: dict[str, float],
        reproduced: dict[str, float],
    ) -> list[str]:
        """Detect potential edge cases, data leakage, and numerical anomalies."""
        anomalies: list[str] = []

        for k, v in reproduced.items():
            # Check for NaN / Infinite corruption
            if math.isnan(v) or math.isinf(v):
                anomalies.append(f"Metric '{k}' produced invalid numerical representation ({v})")
            # Check for exact 1.0000 on bounded metrics (possible data leakage or trivial split)
            clean_k = k.lower()
            if (
                any(term in clean_k for term in ["acc", "f1", "auc", "precision", "recall"])
                and math.isclose(v, 1.0, abs_tol=1e-6)
                and not math.isclose(claimed.get(k, 0.0), 1.0, abs_tol=1e-6)
            ):
                anomalies.append(f"Suspicious perfect score 1.0000 on '{k}' — verify test set contamination or target leakage")
            # Check sign flip
            if k in claimed and ((claimed[k] > 0 and v < 0) or (claimed[k] < 0 and v > 0)):
                anomalies.append(f"Sign inversion detected for metric '{k}': claimed {claimed[k]} vs reproduced {v}")

        return anomalies

    def validate_submission(
        self,
        paper_id: str,
        claimed_metrics: dict[str, float],
        reproduced_metrics: dict[str, float],
        seed_runs: dict[str, list[float]] | None = None,
    ) -> ValidationReport:
        """Run comprehensive validation analysis over paper metrics and seed replications."""
        metric_evals: dict[str, MetricEvaluationResult] = {}
        total_metric_score = 0.0
        anomalies = self.detect_anomalies(claimed_metrics, reproduced_metrics)
        notes: list[str] = []

        if not claimed_metrics:
            notes.append("No claimed numeric baseline metrics provided; neutral baseline assigned.")
            overall_metric_score = 70.0
        elif not reproduced_metrics:
            notes.append("No metrics reproduced from execution run.")
            overall_metric_score = 0.0
        else:
            for name, claimed_val in claimed_metrics.items():
                if name in reproduced_metrics:
                    eval_res = self.evaluate_single_metric(name, claimed_val, reproduced_metrics[name])
                    metric_evals[name] = eval_res
                    total_metric_score += eval_res.score
                else:
                    # Missing claim in reproduced output
                    missing_res = MetricEvaluationResult(
                        metric_name=name,
                        category="unknown",
                        claimed_value=claimed_val,
                        reproduced_value=0.0,
                        relative_error=1.0,
                        absolute_error=abs(claimed_val),
                        is_reproduced=False,
                        score=0.0,
                        notes=[f"Claimed metric '{name}' was not found in reproduced output"],
                    )
                    metric_evals[name] = missing_res

            overall_metric_score = total_metric_score / len(claimed_metrics)

        # Stability evaluation
        stability_evals: dict[str, MultiSeedStabilityResult] = {}
        stability_score_total = 0.0

        if seed_runs:
            for metric_k, seed_vals in seed_runs.items():
                stab_res = self.analyze_multi_seed_stability(metric_k, seed_vals)
                stability_evals[metric_k] = stab_res
                stability_score_total += stab_res.stability_score
            overall_stability_score = stability_score_total / len(seed_runs)
        else:
            overall_stability_score = 80.0  # Default neutral for single-run

        # Overall composite validity score (70% metric alignment, 30% seed stability)
        overall_validity = (overall_metric_score * 0.70) + (overall_stability_score * 0.30)

        # Status classification
        if overall_validity >= 85.0 and not anomalies:
            status = "VERIFIED"
        elif overall_validity >= 60.0:
            status = "PARTIALLY_VERIFIED"
        elif overall_validity >= 40.0 or anomalies:
            status = "NEEDS_REVIEW"
        else:
            status = "FAILED"

        return ValidationReport(
            paper_id=paper_id,
            overall_validity_score=round(overall_validity, 2),
            validation_status=status,
            metric_results=metric_evals,
            stability_results=stability_evals,
            anomalies=anomalies,
            summary_notes=notes,
        )
