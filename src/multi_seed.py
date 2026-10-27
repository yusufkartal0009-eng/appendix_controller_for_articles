"""Multi-seed execution: the seed spec, applying a seed to a paper's run setup, and the per-metric summary (#48).

The design is `docs/MULTI_SEED.md`. A paper is run once per seed only if the paper itself has a seed parameter; nothing
here edits a paper's code. The seed spec names the seeds and how the paper takes them, and where in the paper's files
that was found.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

from src.scoring import coefficient_of_variation

MULTI_SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "multi_seed_runs"
SUMMARY_NAME = "multi_seed_summary.json"
SEED_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "multi_seed_settings.json"
PLACEHOLDER = "{seed}"


def validate_seed_spec(paper_id: str, spec: dict[str, Any]) -> None:
    """Raises ValueError unless the spec follows docs/MULTI_SEED.md section 2."""
    values = spec.get("values")
    if (not isinstance(values, list) or len(values) < 2
            or not all(isinstance(v, int) and not isinstance(v, bool) for v in values)):
        raise ValueError(f"{paper_id}: seed values must be a list of at least two integers: {values}")
    if len(set(values)) != len(values):
        raise ValueError(f"{paper_id}: seed values must be different from each other: {values}")
    if not spec.get("source"):
        raise ValueError(f"{paper_id}: a seed spec needs a source (where in the paper's files the seed parameter is)")
    has_arg, has_args = "arg" in spec, "args" in spec
    if has_arg == has_args:
        raise ValueError(f"{paper_id}: a seed spec needs exactly one of `arg` and `args`")
    if has_arg and not (isinstance(spec["arg"], str) and spec["arg"].startswith("-")):
        raise ValueError(f"{paper_id}: `arg` must be a command-line option such as --seed: {spec['arg']!r}")
    if has_args and not any(PLACEHOLDER in str(a) for a in spec["args"]):
        raise ValueError(f"{paper_id}: `args` must contain {PLACEHOLDER}")


def load_seed_settings(path: Path | None = None) -> dict[str, Any]:
    """The per-paper seed specs of the settings file ({} when the file does not exist)."""
    path = path or SEED_SETTINGS_PATH
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("papers", {})


def seed_spec_of(entry: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any] | None:
    """The validated seed spec of a paper: the settings file first, then the entry's own `run_setup.seed`; None if neither."""
    paper_id = entry["paper_id"]
    spec = (settings.get(paper_id) or {}).get("seed") or (entry.get("run_setup") or {}).get("seed")
    if spec is None:
        return None
    validate_seed_spec(paper_id, spec)
    return spec


def apply_seed(entry: dict[str, Any], spec: dict[str, Any], seed: int) -> dict[str, Any]:
    """A copy of the entry whose run setup passes `seed` to the paper; the entry itself is not modified."""
    result = copy.deepcopy(entry)
    setup = result["run_setup"]
    args = [str(a).replace(PLACEHOLDER, str(seed)) for a in (spec["args"] if "args" in spec else setup.get("args", []))]
    if "arg" in spec:
        args += [spec["arg"], str(seed)]
    setup["args"] = args
    setup["env"] = {k: str(v).replace(PLACEHOLDER, str(seed)) for k, v in setup.get("env", {}).items()}
    return result


def summarize_seed_runs(metrics_by_seed: dict[int, dict[str, float]]) -> dict[str, dict[str, Any]]:
    """Per metric found in every seed run: the values (in seed order), mean, standard deviations, and CV.

    `std_population` (divisor n) is the one `Tier3StabilityEvaluator` uses; `std_sample` (divisor n - 1) is stored beside it.
    """
    if not metrics_by_seed:
        return {}
    seeds = sorted(metrics_by_seed)
    names = set.intersection(*(set(metrics_by_seed[s]) for s in seeds))
    summary: dict[str, dict[str, Any]] = {}
    for name in sorted(names):
        values = [float(metrics_by_seed[s][name]) for s in seeds]
        n = len(values)
        mean = sum(values) / n
        squares = sum((v - mean) ** 2 for v in values)
        summary[name] = {
            "seeds": seeds, "values": values, "n": n, "mean": mean,
            "std_population": math.sqrt(squares / n),
            "std_sample": math.sqrt(squares / (n - 1)) if n > 1 else None,
            "cv": coefficient_of_variation(values),
        }
    return summary


class MultiSeedRecordError(ValueError):
    """A stored multi-seed summary exists but cannot be used."""


def load_seed_metric_results(paper_id: str, root: Path | None = None) -> dict[str, list[float]] | None:
    """The per-metric seed values of a paper's stored multi-seed summary, or None when the paper has no such record.

    Tier 3 then uses them (`seed_metric_results` of the scorer). A record that exists but is malformed raises
    `MultiSeedRecordError`; it is never silently ignored, because that would score the paper as a single run.
    """
    path = Path(root or MULTI_SEED_DIR) / paper_id / SUMMARY_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise MultiSeedRecordError(f"multi-seed summary {path} cannot be read as JSON: {exc}") from exc
    metrics = data.get("metrics") if isinstance(data, dict) else None
    if not isinstance(metrics, dict):
        raise MultiSeedRecordError(f"multi-seed summary {path} has no 'metrics' object")
    results: dict[str, list[float]] = {}
    for name, item in metrics.items():
        values = item.get("values") if isinstance(item, dict) else None
        if (not isinstance(values, list) or not values
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values)):
            raise MultiSeedRecordError(f"multi-seed summary {path}: metric '{name}' needs a non-empty list of numeric 'values'")
        results[name] = [float(v) for v in values]
    return results
