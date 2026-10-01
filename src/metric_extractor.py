"""Empirical metric extraction and log parsing engine for scientific code outputs."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Canonical metric normalization aliases
CANONICAL_METRIC_MAP: dict[str, str] = {
    # Accuracy
    "acc": "accuracy",
    "accuracy": "accuracy",
    "test_acc": "accuracy",
    "test_accuracy": "accuracy",
    "val_acc": "accuracy",
    "val_accuracy": "accuracy",
    "valid_acc": "accuracy",
    "validation_acc": "accuracy",
    "top1_acc": "accuracy",
    "top_1_accuracy": "accuracy",

    # AUROC / AUC
    "auc": "auroc",
    "auroc": "auroc",
    "roc_auc": "auroc",
    "roc-auc": "auroc",
    "test_auc": "auroc",
    "val_auc": "auroc",
    "valid_auc": "auroc",

    # F1 Score
    "f1": "f1",
    "f1_score": "f1",
    "f1-score": "f1",
    "test_f1": "f1",
    "val_f1": "f1",
    "macro_f1": "f1",
    "weighted_f1": "f1",

    # Precision & Recall
    "prec": "precision",
    "precision": "precision",
    "test_precision": "precision",
    "val_precision": "precision",
    "macro_precision": "precision",
    "rec": "recall",
    "recall": "recall",
    "test_recall": "recall",
    "val_recall": "recall",
    "macro_recall": "recall",

    # Loss & Error
    "loss": "loss",
    "test_loss": "loss",
    "val_loss": "loss",
    "eval_loss": "loss",
    "cross_entropy": "loss",
    "mse": "mse",
    "test_mse": "mse",
    "mean_squared_error": "mse",
    "rmse": "rmse",
    "test_rmse": "rmse",
    "root_mean_squared_error": "rmse",
    "mae": "mae",
    "test_mae": "mae",
    "mean_absolute_error": "mae",
    "perplexity": "perplexity",
    "ppl": "perplexity",

    # NLP Bounded
    "bleu": "bleu",
    "bleu_score": "bleu",
    "rouge": "rouge",
    "rouge_1": "rouge",
    "rouge_2": "rouge",
    "rouge_l": "rouge",

    # Runtime & Hardware
    "latency": "latency_ms",
    "latency_ms": "latency_ms",
    "inference_time": "latency_ms",
    "inference_time_ms": "latency_ms",
    "eval_runtime": "latency_ms",
    "throughput": "throughput",
    "throughput_qps": "throughput",
    "fps": "throughput",
    "samples_per_sec": "throughput",
    "gpu_memory": "gpu_memory_mb",
    "gpu_memory_mb": "gpu_memory_mb",
    "vram_mb": "gpu_memory_mb",
}

# Metrics that are strictly percentages or rates bounded in [0.0, 1.0]
BOUNDED_RATE_METRICS = {
    "accuracy", "auroc", "f1", "precision", "recall", "rouge"
}


@dataclass
class ExtractedMetric:
    """Represents a single extracted quantitative metric."""
    canonical_name: str
    raw_name: str
    value: float
    raw_value_str: str
    confidence: float  # 0.0 to 1.0
    extraction_source: str  # 'json', 'sklearn', 'regex', 'framework'
    line_number: int | None = None


class MetricExtractor:
    """Extracts, parses, and normalizes empirical performance metrics from unstructured

    console outputs, Scikit-learn tables, JSON lines, and framework logs.
    """

    def __init__(self, canonical_map: dict[str, str] | None = None):
        self.canonical_map = dict(CANONICAL_METRIC_MAP)
        if canonical_map:
            self.canonical_map.update(canonical_map)

    def normalize_metric_name(self, raw_name: str) -> str:
        """Map a raw metric string to its canonical identifier."""
        clean = raw_name.lower().strip().replace("-", "_").replace(" ", "_")
        if clean in self.canonical_map:
            return self.canonical_map[clean]

        # Strip common prefixes like 'test_', 'eval_', 'val_', 'inference_'
        for prefix in ["test_", "eval_", "val_", "valid_", "train_", "inference_"]:
            if clean.startswith(prefix):
                candidate = clean[len(prefix):]
                if candidate in self.canonical_map:
                    return self.canonical_map[candidate]

        # Strip common suffixes like '_score', '_accuracy', '_latency'
        for suffix in ["_score", "_accuracy", "_acc", "_auc", "_f1", "_loss", "_latency", "_throughput", "_precision", "_recall"]:
            if clean.endswith(suffix):
                candidate = suffix.lstrip("_")
                if candidate in self.canonical_map:
                    return self.canonical_map[candidate]

        return self.canonical_map.get(clean, clean)

    def normalize_value(self, canonical_name: str, raw_val_str: str) -> float | None:
        """Convert a string value representation to a float, converting percentages if needed."""
        val_str = raw_val_str.strip()
        is_percentage = val_str.endswith("%")
        if is_percentage:
            val_str = val_str[:-1].strip()
        else:
            val_str = re.sub(r"(?i)\s*(ms|sec|s|mb|gb|qps)$", "", val_str).strip()

        try:
            val = float(val_str)
        except ValueError:
            return None

        if is_percentage:
            val = val / 100.0
        elif canonical_name in BOUNDED_RATE_METRICS and val > 1.0 and val <= 100.0:
            # Automatic rate conversion: e.g. Accuracy reported as 94.5 instead of 0.945
            val = val / 100.0

        return round(val, 6)

    def extract_from_json(self, text: str) -> list[ExtractedMetric]:
        """Parse JSON blocks or JSON lines emitted in the text."""
        extracted: list[ExtractedMetric] = []

        # Find curly brace json objects
        json_pattern = re.compile(r"(\{[\s\S]*?\})")
        for match in json_pattern.finditer(text):
            candidate = match.group(1)
            # Try parsing Python-style single quotes or valid JSON
            parsed = None
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                try:
                    # Convert single quotes to double quotes for python repr dicts
                    safe_json = candidate.replace("'", '"')
                    parsed = json.loads(safe_json)
                except json.JSONDecodeError:
                    logger.debug("Skipping non-JSON brace block: %.120s", candidate)

            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        canonical = self.normalize_metric_name(str(k))
                        val = self.normalize_value(canonical, str(v))
                        if val is not None:
                            extracted.append(
                                ExtractedMetric(
                                    canonical_name=canonical,
                                    raw_name=str(k),
                                    value=val,
                                    raw_value_str=str(v),
                                    confidence=0.95,
                                    extraction_source="json",
                                )
                            )

        return extracted

    def extract_from_sklearn_report(self, text: str) -> list[ExtractedMetric]:
        """Extract metrics from Scikit-learn classification_report outputs."""
        extracted: list[ExtractedMetric] = []

        # Look for the accuracy row: 'accuracy                           0.83        24'
        acc_match = re.search(r"^\s*accuracy\s+([0-9\.]+)\s+\d+", text, re.MULTILINE | re.IGNORECASE)
        if acc_match:
            val = self.normalize_value("accuracy", acc_match.group(1))
            if val is not None:
                extracted.append(
                    ExtractedMetric(
                        canonical_name="accuracy",
                        raw_name="sklearn_accuracy",
                        value=val,
                        raw_value_str=acc_match.group(1),
                        confidence=0.98,
                        extraction_source="sklearn",
                    )
                )

        # Look for macro avg / weighted avg rows
        # 'macro avg       0.79      0.83      0.81        24'
        macro_match = re.search(
            r"^\s*macro avg\s+([0-9\.]+)\s+([0-9\.]+)\s+([0-9\.]+)",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        if macro_match:
            prec_val = self.normalize_value("precision", macro_match.group(1))
            rec_val = self.normalize_value("recall", macro_match.group(2))
            f1_val = self.normalize_value("f1", macro_match.group(3))
            if prec_val is not None:
                extracted.append(ExtractedMetric("precision", "macro_precision", prec_val, macro_match.group(1), 0.95, "sklearn"))
            if rec_val is not None:
                extracted.append(ExtractedMetric("recall", "macro_recall", rec_val, macro_match.group(2), 0.95, "sklearn"))
            if f1_val is not None:
                extracted.append(ExtractedMetric("f1", "macro_f1", f1_val, macro_match.group(3), 0.95, "sklearn"))

        weighted_match = re.search(
            r"^\s*weighted avg\s+([0-9\.]+)\s+([0-9\.]+)\s+([0-9\.]+)",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        if weighted_match:
            f1_val = self.normalize_value("f1", weighted_match.group(3))
            if f1_val is not None and not any(e.canonical_name == "f1" for e in extracted):
                extracted.append(ExtractedMetric("f1", "weighted_f1", f1_val, weighted_match.group(3), 0.90, "sklearn"))

        return extracted

    def extract_from_framework_logs(self, text: str) -> list[ExtractedMetric]:
        """Extract metrics from PyTorch Lightning, XGBoost, and LightGBM logs."""
        extracted: list[ExtractedMetric] = []

        # LightGBM / XGBoost: [100] valid_0's auc: 0.89123
        gbdt_pattern = re.compile(
            r"\[\d+\]\s+(?:valid(?:_\d+)?|test|eval)(?:'s)?\s+([a-zA-Z0-9_\-]+):\s+([+-]?[0-9\.]+)",
            re.IGNORECASE,
        )
        for match in gbdt_pattern.finditer(text):
            raw_metric = match.group(1)
            raw_val = match.group(2)
            canonical = self.normalize_metric_name(raw_metric)
            val = self.normalize_value(canonical, raw_val)
            if val is not None:
                extracted.append(
                    ExtractedMetric(
                        canonical_name=canonical,
                        raw_name=raw_metric,
                        value=val,
                        raw_value_str=raw_val,
                        confidence=0.92,
                        extraction_source="framework",
                    )
                )

        return extracted

    def extract_from_regex(self, text: str) -> list[ExtractedMetric]:
        """Regex-based key-value extraction for common academic stdout lines."""
        extracted: list[ExtractedMetric] = []

        # Key-value pattern: e.g. "Test Accuracy: 0.942", "AUC = 0.912", "Loss: 0.231", "latency: 15.4ms"
        kv_pattern = re.compile(
            r"([A-Za-z0-9_\-\s]{2,25})\s*[:=]\s*([+-]?[0-9]+(?:\.[0-9]+)?\s*(?:%|ms|sec|s|mb|gb|qps)?)\b"
        )

        for line_num, line in enumerate(text.splitlines(), start=1):
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            for match in kv_pattern.finditer(line_str):
                raw_k = match.group(1).strip()
                raw_v = match.group(2).strip()

                canonical = self.normalize_metric_name(raw_k)
                # Check if it corresponds to a recognized metric or known canonical
                if canonical in CANONICAL_METRIC_MAP.values() or any(
                    term in canonical for term in ["acc", "auc", "f1", "loss", "mse", "rmse", "mae", "latency", "runtime", "throughput", "precision", "recall"]
                ):
                    val = self.normalize_value(canonical, raw_v)
                    if val is not None:
                        extracted.append(
                            ExtractedMetric(
                                canonical_name=canonical,
                                raw_name=raw_k,
                                value=val,
                                raw_value_str=raw_v,
                                confidence=0.85,
                                extraction_source="regex",
                                line_number=line_num,
                            )
                        )

        return extracted

    def extract_metrics(self, text: str) -> dict[str, float]:
        """Unified extraction method running all parsers and returning consolidated canonical metrics.

        Later occurrences in the logs take precedence (representing final test/eval metrics).
        """
        all_metrics: list[ExtractedMetric] = []

        # 1. Framework logs
        all_metrics.extend(self.extract_from_framework_logs(text))

        # 2. Scikit-learn reports
        all_metrics.extend(self.extract_from_sklearn_report(text))

        # 3. Regex key-value logs
        all_metrics.extend(self.extract_from_regex(text))

        # 4. JSON blocks (highest structured priority)
        all_metrics.extend(self.extract_from_json(text))

        # Consolidate into dictionary: higher confidence or later occurrences win
        consolidated: dict[str, tuple[float, float]] = {}  # canonical_name -> (confidence, value)

        for metric in all_metrics:
            existing = consolidated.get(metric.canonical_name)
            if existing is None:
                consolidated[metric.canonical_name] = (metric.confidence, metric.value)
            else:
                existing_conf, _ = existing
                if metric.confidence >= existing_conf:
                    consolidated[metric.canonical_name] = (metric.confidence, metric.value)

        return {k: round(v[1], 4) for k, v in consolidated.items()}

    def extract_from_run_dir(self, run_dir: str | Path) -> dict[str, float]:
        """Extract metrics from an executed sandbox run directory.

        Checks metrics.json, stdout.log, stderr.log, and persists extracted_metrics.json.
        """
        run_path = Path(run_dir).resolve()
        if not run_path.exists() or not run_path.is_dir():
            raise FileNotFoundError(f"Run directory not found: {run_path}")

        metrics: dict[str, float] = {}

        # 1. Check if explicit metrics.json or results.json exists
        for candidate_name in ["metrics.json", "results.json"]:
            m_file = run_path / candidate_name
            if m_file.exists():
                try:
                    data = json.loads(m_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if isinstance(v, (int, float)) and not isinstance(v, bool):
                                canonical = self.normalize_metric_name(str(k))
                                val = self.normalize_value(canonical, str(v))
                                if val is not None:
                                    metrics[canonical] = round(val, 4)
                except Exception as exc:  # noqa: BLE001 - files written by paper code; a bad file is logged, never fatal
                    logger.warning("Error reading %s: %s", m_file, exc)

        # 2. Parse stdout.log and stderr.log
        for log_name in ["stdout.log", "stderr.log"]:
            log_file = run_path / log_name
            if log_file.exists():
                try:
                    log_text = log_file.read_text(encoding="utf-8", errors="ignore")
                    extracted = self.extract_metrics(log_text)
                    # Merge (explicit file takes priority, log fills in remaining)
                    for k, v in extracted.items():
                        if k not in metrics:
                            metrics[k] = v
                except Exception as exc:  # noqa: BLE001 - logs written by paper code; a bad log is logged, never fatal
                    logger.warning("Error reading %s: %s", log_file, exc)

        # 3. Persist consolidated extracted_metrics.json
        try:
            out_file = run_path / "extracted_metrics.json"
            out_file.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        except OSError:
            pass

        return metrics
