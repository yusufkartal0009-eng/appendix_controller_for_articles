"""Reproducibility Scoring Engine for Repro Radar.

Implements the 4-Tier Reproducibility Rubric:
- Tier 1 (Build): Repo cloning, dependency resolution, execution exit code (Weight: 35%)
- Tier 2 (Metrics): Empirical claim alignment within tolerance bounds (Weight: 35%)
- Tier 3 (Stability): Seed invariance and run-to-run variance (Weight: 15%)
- Tier 4 (Artifacts & Doc): License, environment files, README, logging (Weight: 15%)

Generates composite scores (0-100) and neutral status classifications:
- 'Verified'
- 'Partially Verified'
- 'Needs Review'
- 'Failed'
"""

import math
import os
import re
from pathlib import Path
from typing import Any

from src.config import (
    ALLOWED_LICENSES,
    DEFAULT_TOLERANCE,
    SCORE_PARTIALLY_VERIFIED_THRESHOLD,
    SCORE_VERIFIED_THRESHOLD,
    STATUS_FAILED,
    STATUS_NEEDS_REVIEW,
    STATUS_PARTIALLY_VERIFIED,
    STATUS_VERIFIED,
    TIER1_BUILD_WEIGHT,
    TIER2_METRICS_WEIGHT,
    TIER3_STABILITY_WEIGHT,
    TIER4_ARTIFACTS_WEIGHT,
)
from src.models import ScoreBreakdown

NOTHING_COMPARED_TEXT = "claimed metrics not found in the output (nothing was compared)"

# A time or latency metric is judged on its relative error only (no absolute allowance). It is recognized by the words of
# its name: the long words anywhere in the name, the short ones (`ms` would also be inside `rmse`, `params`, `items`) only
# as a whole part of the name (`latency_ms`, `inferenceMs`).
TIME_METRIC_WORDS = ("second", "time", "latency", "runtime", "duration")
TIME_METRIC_PARTS = ("sec", "secs", "ms", "msec", "msecs")
_NAME_PARTS = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")


def is_time_metric(metric_name: str) -> bool:
    """True if the name of a metric says that it is a time, latency, or duration."""
    lowered = metric_name.lower()
    if any(word in lowered for word in TIME_METRIC_WORDS):
        return True
    return any(part.lower() in TIME_METRIC_PARTS for part in _NAME_PARTS.findall(metric_name))


class Tier1BuildEvaluator:
    """Evaluates buildability, dependency installation, and clean execution."""

    @staticmethod
    def evaluate(
        clone_success: bool,
        deps_installed: bool,
        script_executed: bool,
        exit_code: int | None,
    ) -> tuple[float, list[str]]:
        """Calculate Tier 1 build score (0-100) and diagnostic notes."""
        score = 0.0
        notes = []

        if clone_success:
            score += 25.0
            notes.append("Repository cloned successfully (+25)")
        else:
            notes.append("Repository clone failed (0/25)")

        if deps_installed:
            score += 25.0
            notes.append("Dependencies installed successfully (+25)")
        else:
            notes.append("Dependency installation failed (0/25)")

        if script_executed:
            score += 25.0
            notes.append("Target script invoked (+25)")
        else:
            notes.append("Target script not invoked (0/25)")

        if exit_code == 0:
            score += 25.0
            notes.append("Clean execution with exit code 0 (+25)")
        elif exit_code is not None:
            notes.append(f"Non-zero exit code {exit_code} (0/25)")
        else:
            notes.append("Execution did not conclude (0/25)")

        return min(100.0, max(0.0, score)), notes


class Tier2MetricsEvaluator:
    """Evaluates empirical metric alignment between claimed and reproduced values."""

    @staticmethod
    def evaluate(
        claimed_metrics: dict[str, float],
        reproduced_metrics: dict[str, float],
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> tuple[float, dict[str, dict[str, Any]], list[str]]:
        """Calculate Tier 2 score (0-100) based on metric claims within tolerance."""
        if not claimed_metrics:
            return 70.0, {}, ["No numeric claims specified; neutral baseline applied (70.0)"]

        if not reproduced_metrics:
            return 0.0, {}, ["No metrics reproduced from execution run (0/100)"]

        claim_results: dict[str, dict[str, Any]] = {}
        total_claims = len(claimed_metrics)
        earned_points = 0.0
        notes = []

        for metric_name, claimed_val in claimed_metrics.items():
            if metric_name not in reproduced_metrics:
                claim_results[metric_name] = {
                    "claimed": claimed_val,
                    "reproduced": None,
                    "error": None,
                    "matches": False,
                    "points": 0.0,
                }
                notes.append(f"Metric '{metric_name}' was not found in reproduced outputs.")
                continue

            reproduced_val = reproduced_metrics[metric_name]
            # Absolute and relative differences
            abs_diff = abs(reproduced_val - claimed_val)
            denom = max(abs(claimed_val), 1e-6)
            rel_error = abs_diff / denom

            # Differentiate tolerance logic by metric category
            if is_time_metric(metric_name):
                # Time / latency metrics must strictly evaluate relative tolerance
                # to prevent the absolute tolerance trap (e.g. 0.02s taking 0.06s is 200% error)
                if rel_error <= tolerance:
                    points = 1.0
                    matches = True
                    notes.append(
                        f"Metric '{metric_name}' (runtime/latency) MATCHED (Claimed: {claimed_val}, Repro: {reproduced_val}, RelErr: {rel_error:.3%})"
                    )
                elif rel_error <= 2.0 * tolerance:
                    points = 0.5
                    matches = False
                    notes.append(
                        f"Metric '{metric_name}' (runtime/latency) PARTIAL MATCH (Claimed: {claimed_val}, Repro: {reproduced_val}, RelErr: {rel_error:.3%})"
                    )
                else:
                    points = 0.0
                    matches = False
                    notes.append(
                        f"Metric '{metric_name}' (runtime/latency) DIVERGED (Claimed: {claimed_val}, Repro: {reproduced_val}, RelErr: {rel_error:.3%})"
                    )
            else:
                # Rate, probability, and standard bounded metrics (accuracy, AUC, F1, etc.)
                # Separate relative vs absolute bounds:
                # 1. Matches if relative error is within tolerance OR
                # 2. For bounded probability/ratio metrics (claimed in [0, 1]), absolute difference is within tolerance
                is_bounded_rate = (0.0 <= claimed_val <= 1.0)
                if rel_error <= tolerance:
                    points = 1.0
                    matches = True
                    notes.append(f"Metric '{metric_name}' MATCHED (Claimed: {claimed_val}, Repro: {reproduced_val}, RelErr: {rel_error:.3%})")
                elif is_bounded_rate and abs_diff <= tolerance:
                    points = 1.0
                    matches = True
                    notes.append(f"Metric '{metric_name}' MATCHED (Absolute: Claimed {claimed_val}, Repro {reproduced_val}, AbsDiff: {abs_diff:.4f})")
                elif rel_error <= 2.0 * tolerance or (is_bounded_rate and abs_diff <= 2.0 * tolerance):
                    points = 0.5
                    matches = False
                    notes.append(f"Metric '{metric_name}' PARTIAL MATCH (Claimed: {claimed_val}, Repro: {reproduced_val}, RelErr: {rel_error:.3%})")
                else:
                    points = 0.0
                    matches = False
                    notes.append(f"Metric '{metric_name}' DIVERGED (Claimed: {claimed_val}, Repro: {reproduced_val}, RelErr: {rel_error:.3%})")

            earned_points += points
            claim_results[metric_name] = {
                "claimed": claimed_val,
                "reproduced": reproduced_val,
                "abs_diff": abs_diff,
                "rel_error": rel_error,
                "matches": matches,
                "points": points,
            }

        score = (earned_points / total_claims) * 100.0
        return min(100.0, max(0.0, score)), claim_results, notes


def coefficient_of_variation(values: list[float]) -> float:
    """Population standard deviation over |mean| (the denominator is floored at 1e-6)."""
    mean_val = sum(values) / len(values)
    variance = sum((x - mean_val) ** 2 for x in values) / len(values)
    return math.sqrt(variance) / max(abs(mean_val), 1e-6)


class Tier3StabilityEvaluator:
    """Evaluates multi-seed repeatability and variance stability."""

    @staticmethod
    def evaluate(
        seed_results: list[float] | None = None,
        single_run_clean: bool = True,
        execution_succeeded: bool = True,
    ) -> tuple[float, list[str]]:
        """Calculate Tier 3 stability score (0-100)."""
        notes = []

        # If code did not execute cleanly or build failed, stability cannot be evaluated
        if not execution_succeeded:
            notes.append("Execution failed or was not invoked; stability score zeroed (0.0/100)")
            return 0.0, notes

        if not seed_results or len(seed_results) < 2:
            if single_run_clean:
                notes.append("Single seed verified without errors; baseline stability score assigned (75.0)")
                return 75.0, notes
            else:
                notes.append("Single seed execution failed or unstable (0.0)")
                return 0.0, notes

        # Multiple seed variance calculation
        mean_val = sum(seed_results) / len(seed_results)
        variance = sum((x - mean_val) ** 2 for x in seed_results) / len(seed_results)
        std_dev = math.sqrt(variance)
        cv = coefficient_of_variation(seed_results)

        notes.append(f"Multi-seed evaluated (n={len(seed_results)}, Mean={mean_val:.4f}, StdDev={std_dev:.4f}, CV={cv:.3%})")

        if cv <= 0.02:
            score = 100.0
            notes.append("Excellent seed invariance: Coefficient of Variation <= 2% (+100)")
        elif cv <= 0.05:
            score = 85.0
            notes.append("Good stability: Coefficient of Variation <= 5% (+85)")
        elif cv <= 0.10:
            score = 65.0
            notes.append("Moderate variance across seeds: Coefficient of Variation <= 10% (+65)")
        else:
            score = 40.0
            notes.append(f"High variance across seeds: Coefficient of Variation ({cv:.2%}) exceeds 10% (+40)")

        return score, notes

    @classmethod
    def evaluate_by_metric(
        cls,
        seed_metric_results: dict[str, list[float]] | None = None,
        single_run_clean: bool = True,
        execution_succeeded: bool = True,
    ) -> tuple[float, list[str]]:
        """Tier 3 from real seed runs (docs/MULTI_SEED.md section 5): the metric with the largest CV decides.

        Without a metric that has at least two values the single-run behavior of `evaluate` applies (the 75.0 baseline).
        """
        usable = {name: values for name, values in (seed_metric_results or {}).items() if len(values) >= 2}
        if not usable:
            return cls.evaluate(None, single_run_clean=single_run_clean, execution_succeeded=execution_succeeded)
        worst = max(usable, key=lambda name: coefficient_of_variation(usable[name]))
        score, notes = cls.evaluate(usable[worst], single_run_clean=single_run_clean,
                                    execution_succeeded=execution_succeeded)
        if execution_succeeded:
            notes.insert(0, f"Metric '{worst}' has the largest CV of {len(usable)} metric(s) with seed results and decides")
        return score, notes


class Tier4ArtifactsEvaluator:
    """Evaluates documentation, license openness, environment specs, and structured artifacts."""

    @classmethod
    def detect_filesystem_artifacts(
        cls,
        repo_dir: str | Path | None = None,
        run_dir: str | Path | None = None,
    ) -> tuple[bool, bool, bool]:
        """Dynamically detect environment files, README, and saved artifacts via filesystem checks."""
        has_environment_file = False
        has_readme = False
        has_saved_artifacts = False

        if repo_dir:
            r_path = Path(repo_dir)
            if r_path.exists() and r_path.is_dir():
                env_candidates = [
                    "requirements.txt",
                    "pyproject.toml",
                    "environment.yml",
                    "environment.yaml",
                    "setup.py",
                    "Pipfile",
                ]
                has_environment_file = any(os.path.exists(r_path / f) for f in env_candidates)

                readme_candidates = [
                    "README.md",
                    "README.rst",
                    "README.txt",
                    "README",
                    "readme.md",
                ]
                has_readme = any(os.path.exists(r_path / f) for f in readme_candidates)

        if run_dir:
            run_p = Path(run_dir)
            if run_p.exists() and run_p.is_dir():
                try:
                    has_saved_artifacts = any(run_p.iterdir())
                except OSError:
                    has_saved_artifacts = False

        return has_environment_file, has_readme, has_saved_artifacts

    @staticmethod
    def evaluate(
        license_name: str,
        has_environment_file: bool = True,
        has_readme: bool = True,
        has_saved_artifacts: bool = True,
    ) -> tuple[float, list[str]]:
        """Calculate Tier 4 documentation & artifact score (0-100)."""
        score = 0.0
        notes = []

        # License Check
        is_open_license = any(
            allowed.lower() in license_name.lower()
            for allowed in ALLOWED_LICENSES
        )
        if is_open_license:
            score += 30.0
            notes.append(f"Permissive open source license verified ({license_name}) (+30)")
        else:
            notes.append(f"License '{license_name}' is non-standard or restricted (0/30)")

        # Environment specs
        if has_environment_file:
            score += 30.0
            notes.append("Environment definition present (requirements.txt / pyproject.toml / env.yml) (+30)")
        else:
            notes.append("Missing explicit environment file (0/30)")

        # Documentation / instructions
        if has_readme:
            score += 20.0
            notes.append("Reproduction documentation / README detected (+20)")
        else:
            notes.append("Missing README or instructions (0/20)")

        # Execution artifacts / structured logs
        if has_saved_artifacts:
            score += 20.0
            notes.append("Structured output artifacts / execution logs captured (+20)")
        else:
            notes.append("No saved output artifacts captured (0/20)")

        return min(100.0, max(0.0, score)), notes


class ReproducibilityScorer:
    """Composite scoring calculator and AI decision layer."""

    @classmethod
    def calculate_composite_score(
        cls,
        tier1: float,
        tier2: float,
        tier3: float,
        tier4: float,
        tier1_exit_code: int | None = 0,
        has_critical_error: bool = False,
        nothing_compared: bool = False,
        claims_compared: bool = True,
    ) -> tuple[float, str, str]:
        """Compute composite score (0-100) and assign neutral status label.

        `nothing_compared` is True when claims exist but none of them was found in the run's output; the summary then
        says so instead of reporting a divergence that was never measured (#317).
        `claims_compared` is False when no accepted claim was compared with a metric of the run (no claim at all, none with a
        counterpart, or none found in the output). Tier 2 is then the neutral baseline, which is not evidence, so a run that
        built cleanly is labeled Needs Review and never Verified or Partially Verified (#540).
        """
        total = (
            tier1 * TIER1_BUILD_WEIGHT
            + tier2 * TIER2_METRICS_WEIGHT
            + tier3 * TIER3_STABILITY_WEIGHT
            + tier4 * TIER4_ARTIFACTS_WEIGHT
        )
        total = round(min(100.0, max(0.0, total)), 2)

        # AI Decision Layer for Status Classification: Clean operator grouping with explicit parentheses
        is_build_failure = (
            tier1 < 50.0
            or has_critical_error
            or ((tier1_exit_code is not None and tier1_exit_code != 0) and tier1 < 75.0)
        )
        if is_build_failure:
            status = STATUS_FAILED
            summary = (
                f"Failed (Total: {total}/100). Build or execution runtime "
                f"failed (Tier 1: {tier1}/100)."
            )
        elif not claims_compared and tier1 >= 75.0:
            status = STATUS_NEEDS_REVIEW
            if nothing_compared:
                summary = (
                    f"Needs Review (Total: {total}/100). Code built and ran cleanly, but "
                    f"{NOTHING_COMPARED_TEXT} (Tier 2: {tier2}/100)."
                )
            else:
                summary = (
                    f"Needs Review (Total: {total}/100). Code built and ran cleanly, but no accepted claim could be "
                    f"compared with the run; Tier 2 is the neutral baseline ({tier2}/100), not a measurement."
                )
        elif total >= SCORE_VERIFIED_THRESHOLD and tier2 >= 80.0 and tier1 >= 90.0:
            status = STATUS_VERIFIED
            summary = (
                f"Verified (Total: {total}/100). Build, metrics, and stability "
                f"were successfully reproduced within specified tolerance bounds."
            )
        elif total >= SCORE_PARTIALLY_VERIFIED_THRESHOLD:
            # Check if metrics diverged or partially matched
            if tier2 < 50.0 and tier1 >= 80.0:
                status = STATUS_NEEDS_REVIEW
                if nothing_compared:
                    summary = (
                        f"Needs Review (Total: {total}/100). Code built and ran cleanly, but "
                        f"{NOTHING_COMPARED_TEXT} (Tier 2: {tier2}/100)."
                    )
                else:
                    summary = (
                        f"Needs Review (Total: {total}/100). Code built and ran cleanly, but "
                        f"significant divergence was observed between claimed and reproduced metrics "
                        f"(Tier 2: {tier2}/100)."
                    )
            else:
                status = STATUS_PARTIALLY_VERIFIED
                summary = (
                    f"Partially Verified (Total: {total}/100). Majority of metrics or components verified; "
                    f"minor tolerance exceeded or incomplete artifacts."
                )
        else:
            if tier1 >= 75.0:
                status = STATUS_NEEDS_REVIEW
                if nothing_compared:
                    summary = (
                        f"Needs Review (Total: {total}/100). Code executed cleanly, but {NOTHING_COMPARED_TEXT}."
                    )
                else:
                    summary = (
                        f"Needs Review (Total: {total}/100). Code executed cleanly, but empirical outcomes fell short of claims."
                    )
            else:
                status = STATUS_FAILED
                summary = (
                    f"Failed (Total: {total}/100). Score remained below the critical threshold ({SCORE_PARTIALLY_VERIFIED_THRESHOLD})."
                )

        return total, status, summary

    @classmethod
    def evaluate_paper_run(
        cls,
        paper_id: str,
        clone_success: bool,
        deps_installed: bool,
        script_executed: bool,
        exit_code: int | None,
        claimed_metrics: dict[str, float],
        reproduced_metrics: dict[str, float],
        license_name: str,
        seed_results: list[float] | None = None,
        seed_metric_results: dict[str, list[float]] | None = None,
        has_environment_file: bool = True,
        has_readme: bool = True,
        has_saved_artifacts: bool = True,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> dict[str, Any]:
        """Perform full end-to-end evaluation and return complete breakdown dictionary."""
        # 1. Tier 1 Build
        t1_score, t1_notes = Tier1BuildEvaluator.evaluate(
            clone_success=clone_success,
            deps_installed=deps_installed,
            script_executed=script_executed,
            exit_code=exit_code,
        )

        # Execution success gate: required for downstream empirical and stability validity
        execution_succeeded = bool(
            exit_code == 0 and script_executed and clone_success and deps_installed
        )

        # 2. Tier 2 Metrics
        t2_score, claim_details, t2_notes = Tier2MetricsEvaluator.evaluate(
            claimed_metrics=claimed_metrics,
            reproduced_metrics=reproduced_metrics if execution_succeeded else {},
            tolerance=tolerance,
        )

        # 3. Tier 3 Stability (tied to clean execution)
        if seed_metric_results:
            t3_score, t3_notes = Tier3StabilityEvaluator.evaluate_by_metric(
                seed_metric_results if execution_succeeded else None,
                single_run_clean=execution_succeeded,
                execution_succeeded=execution_succeeded,
            )
        else:
            t3_score, t3_notes = Tier3StabilityEvaluator.evaluate(
                seed_results=seed_results if execution_succeeded else None,
                single_run_clean=execution_succeeded,
                execution_succeeded=execution_succeeded,
            )

        # 4. Tier 4 Artifacts
        t4_score, t4_notes = Tier4ArtifactsEvaluator.evaluate(
            license_name=license_name,
            has_environment_file=has_environment_file,
            has_readme=has_readme,
            has_saved_artifacts=has_saved_artifacts,
        )

        # Composite Score & Neutral Status Classification
        total, status, summary = cls.calculate_composite_score(
            tier1=t1_score,
            tier2=t2_score,
            tier3=t3_score,
            tier4=t4_score,
            tier1_exit_code=exit_code,
            has_critical_error=bool(exit_code is not None and exit_code != 0),
            nothing_compared=bool(execution_succeeded and claimed_metrics
                                  and not any(d["reproduced"] is not None for d in claim_details.values())),
            claims_compared=any(d["reproduced"] is not None for d in claim_details.values()),
        )

        breakdown = ScoreBreakdown(
            tier1_build=t1_score,
            tier2_metrics=t2_score,
            tier3_stability=t3_score,
            tier4_artifacts=t4_score,
            total_score=total,
            status_label=status,
            summary=summary,
        )

        return {
            "paper_id": paper_id,
            "breakdown": breakdown,
            "claim_details": claim_details,
            "diagnostics": {
                "tier1_notes": t1_notes,
                "tier2_notes": t2_notes,
                "tier3_notes": t3_notes,
                "tier4_notes": t4_notes,
            },
        }
