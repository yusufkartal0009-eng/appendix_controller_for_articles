"""Reproducibility Scoring Engine for Repro Radar.

Implements the 4-Tier Reproducibility Rubric:
- Tier 1 (Build): Repo cloning, dependency resolution, execution exit code (Weight: 35%)
- Tier 2 (Metrics): Empirical claim alignment within tolerance bounds (Weight: 35%)
- Tier 3 (Stability): Seed invariance and run-to-run variance (Weight: 15%)
- Tier 4 (Artifacts & Doc): License, environment files, README, logging (Weight: 15%)

Generates composite scores (0-100) and neutral status classifications:
- 'Doğrulandı' (Verified)
- 'Kısmen Doğrulandı' (Partially Verified)
- 'İncelenmeli' (Needs Review / Inconclusive)
- 'Tekrarlanamadı' (Failed)
"""

import math
from typing import Any, Dict, List, Optional, Tuple
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


class Tier1BuildEvaluator:
    """Evaluates buildability, dependency installation, and clean execution."""

    @staticmethod
    def evaluate(
        clone_success: bool,
        deps_installed: bool,
        script_executed: bool,
        exit_code: Optional[int],
    ) -> Tuple[float, List[str]]:
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
        claimed_metrics: Dict[str, float],
        reproduced_metrics: Dict[str, float],
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> Tuple[float, Dict[str, Dict[str, Any]], List[str]]:
        """Calculate Tier 2 score (0-100) based on metric claims within tolerance."""
        if not claimed_metrics:
            return 70.0, {}, ["No numeric claims specified; neutral baseline applied (70.0)"]

        if not reproduced_metrics:
            return 0.0, {}, ["No metrics reproduced from execution run (0/100)"]

        claim_results: Dict[str, Dict[str, Any]] = {}
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

            # Check if within tolerance
            if rel_error <= tolerance or abs_diff <= tolerance:
                points = 1.0
                matches = True
                notes.append(f"Metric '{metric_name}' MATCHED (Claimed: {claimed_val}, Repro: {reproduced_val}, RelErr: {rel_error:.3%})")
            elif rel_error <= 2.0 * tolerance:
                # Partial credit for being close
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


class Tier3StabilityEvaluator:
    """Evaluates multi-seed repeatability and variance stability."""

    @staticmethod
    def evaluate(
        seed_results: Optional[List[float]] = None,
        single_run_clean: bool = True,
    ) -> Tuple[float, List[str]]:
        """Calculate Tier 3 stability score (0-100)."""
        notes = []
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
        cv = std_dev / max(abs(mean_val), 1e-6)

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


class Tier4ArtifactsEvaluator:
    """Evaluates documentation, license openness, environment specs, and structured artifacts."""

    @staticmethod
    def evaluate(
        license_name: str,
        has_environment_file: bool = True,
        has_readme: bool = True,
        has_saved_artifacts: bool = True,
    ) -> Tuple[float, List[str]]:
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
        tier1_exit_code: Optional[int] = 0,
        has_critical_error: bool = False,
    ) -> Tuple[float, str, str]:
        """Compute composite score (0-100) and assign neutral status label."""
        total = (
            tier1 * TIER1_BUILD_WEIGHT
            + tier2 * TIER2_METRICS_WEIGHT
            + tier3 * TIER3_STABILITY_WEIGHT
            + tier4 * TIER4_ARTIFACTS_WEIGHT
        )
        total = round(min(100.0, max(0.0, total)), 2)

        # AI Decision Layer for Status Classification
        if tier1 < 50.0 or has_critical_error or tier1_exit_code != 0 and tier1 < 75.0:
            status = STATUS_FAILED
            summary = (
                f"Tekrarlanamadı (Total: {total}/100). Build veya çalıştırma katmanı "
                f"başarısız oldu (Tier 1: {tier1}/100)."
            )
        elif total >= SCORE_VERIFIED_THRESHOLD and tier2 >= 80.0 and tier1 >= 90.0:
            status = STATUS_VERIFIED
            summary = (
                f"Doğrulandı (Total: {total}/100). Build, metrikler ve kararlılık "
                f"tüm tolerans sınırları içinde başarıyla tekrarlandı."
            )
        elif total >= SCORE_PARTIALLY_VERIFIED_THRESHOLD:
            # Check if metrics diverged or partially matched
            if tier2 < 50.0 and tier1 >= 80.0:
                status = STATUS_NEEDS_REVIEW
                summary = (
                    f"İncelenmeli (Total: {total}/100). Kod sorunsuz derlenip çalıştı ancak "
                    f"iddia edilen metrikler ile üretilen sonuçlar arasında belirgin fark tespit edildi "
                    f"(Tier 2: {tier2}/100)."
                )
            else:
                status = STATUS_PARTIALLY_VERIFIED
                summary = (
                    f"Kısmen Doğrulandı (Total: {total}/100). Çoğu metrik veya bileşen doğrulandı, "
                    f"küçük tolerans aşımı veya eksik artefakt mevcut."
                )
        else:
            if tier1 >= 75.0:
                status = STATUS_NEEDS_REVIEW
                summary = (
                    f"İncelenmeli (Total: {total}/100). Kod çalıştırıldı ancak sonuçlar bekleneni karşılamadı."
                )
            else:
                status = STATUS_FAILED
                summary = (
                    f"Tekrarlanamadı (Total: {total}/100). Skor kritik eşiğin ({SCORE_PARTIALLY_VERIFIED_THRESHOLD}) altında kaldı."
                )

        return total, status, summary

    @classmethod
    def evaluate_paper_run(
        cls,
        paper_id: str,
        clone_success: bool,
        deps_installed: bool,
        script_executed: bool,
        exit_code: Optional[int],
        claimed_metrics: Dict[str, float],
        reproduced_metrics: Dict[str, float],
        license_name: str,
        seed_results: Optional[List[float]] = None,
        has_environment_file: bool = True,
        has_readme: bool = True,
        has_saved_artifacts: bool = True,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> Dict[str, Any]:
        """Perform full end-to-end evaluation and return complete breakdown dictionary."""
        # 1. Tier 1 Build
        t1_score, t1_notes = Tier1BuildEvaluator.evaluate(
            clone_success=clone_success,
            deps_installed=deps_installed,
            script_executed=script_executed,
            exit_code=exit_code,
        )

        # 2. Tier 2 Metrics
        t2_score, claim_details, t2_notes = Tier2MetricsEvaluator.evaluate(
            claimed_metrics=claimed_metrics,
            reproduced_metrics=reproduced_metrics,
            tolerance=tolerance,
        )

        # 3. Tier 3 Stability
        t3_score, t3_notes = Tier3StabilityEvaluator.evaluate(
            seed_results=seed_results,
            single_run_clean=(exit_code == 0 and script_executed),
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
            has_critical_error=(exit_code is not None and exit_code != 0),
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
