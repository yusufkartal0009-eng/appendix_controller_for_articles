"""Explaining the difference between two stored runs of the same paper (#35, docs/DIAGNOSIS.md section 8).

Two questions are kept apart: *the same metric values taken in a different time* and *different metric values*. For
different values the report lists the recorded differences between the runs (seed, CPUs, memory, GPU, command, image, tool
commit, package versions) and the size of the shift. It does not name a cause: the records do not show which recorded
difference, if any, produced a shift, and a difference that the records do not hold is not guessed.

The rules R1 to R6 are in docs/DIAGNOSIS.md section 8; each statement names the rule it follows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import DEFAULT_TOLERANCE
from src.diagnosis.report import Statement, _num
from src.diagnosis.schema import DiagnosisInput, load_diagnosis_input

SMALL_SHIFT = 1e-3  # relative difference; at most this is called "small"
GIB = 1024**3

IDENTICAL, SMALL, MODERATE, LARGE = "identical", "small", "moderate", "large"
SAME_METRICS, SMALL_SHIFT_METRICS, DIFFERENT_METRICS, NOT_COMPARABLE = (
    "SAME_METRICS", "SMALL_METRIC_SHIFT", "DIFFERENT_METRICS", "NOT_COMPARABLE")


def shift_size(a: float, b: float) -> str:
    """identical (equal as stored), small (relative difference <= 0.1%), moderate (<= the Tier 2 tolerance), or large."""
    if a == b:
        return IDENTICAL
    rel = abs(a - b) / max(abs(a), abs(b), 1e-12)
    if rel <= SMALL_SHIFT:
        return SMALL
    return MODERATE if rel <= DEFAULT_TOLERANCE else LARGE


@dataclass
class ComparisonReport:
    run_a: str
    run_b: str
    metric_outcome: str
    differing_factors: list[str]
    review_suggested: bool
    statements: list[Statement] = field(default_factory=list)

    def sections(self) -> dict[str, list[Statement]]:
        grouped: dict[str, list[Statement]] = {}
        for statement in self.statements:
            grouped.setdefault(statement.section, []).append(statement)
        return grouped

    def to_markdown(self) -> str:
        lines = [f"# Comparison of `{self.run_a}` (A) and `{self.run_b}` (B)", ""]
        for section, items in self.sections().items():
            lines.append(f"## {section}")
            lines.extend(f"- {s.text} *(source: {s.source})*" for s in items)
            lines.append("")
        lines.append("This comparison is rule-based and uses only the stored files of the two runs. It lists recorded differences; "
                     "it does not say which of them, if any, caused a change.")
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {"run_a": self.run_a, "run_b": self.run_b, "metric_outcome": self.metric_outcome,
                "differing_factors": self.differing_factors, "review_suggested": self.review_suggested,
                "statements": [{"section": s.section, "text": s.text, "fields": list(s.fields), "source": s.source}
                               for s in self.statements]}


def _settings(change: dict[str, Any] | None) -> str:
    """The keys of a Pilot 3 change without its prose, or `none`."""
    keys = sorted(k for k in (change or {}) if k not in ("reason", "pilot2_evidence"))
    return "none" if not keys else ", ".join(f"{k}={change[k]}" for k in keys)  # type: ignore[index]


def compare_inputs(a: DiagnosisInput, b: DiagnosisInput, name_a: str | None = None, name_b: str | None = None) -> ComparisonReport:
    name_a, name_b = name_a or a.run_dir, name_b or b.run_dir
    statements: list[Statement] = []

    def add(section: str, text: str, fields: tuple[str, ...], source: str) -> None:
        statements.append(Statement(section, text, fields, source))

    def both(field_name: str) -> str:
        return f"A {a.source_of(field_name)}; B {b.source_of(field_name)}"

    # ---- the runs
    sec = "The runs"
    add(sec, f"A is `{name_a}`" + (f" ({a.paper_id})" if a.paper_id else "") + f"; B is `{name_b}`"
        + (f" ({b.paper_id})" if b.paper_id else "") + ".", ("paper_id",), both("paper_id"))
    if a.paper_id and b.paper_id and a.paper_id != b.paper_id:
        add(sec, f"The two runs are of different papers ({a.paper_id} and {b.paper_id}); a metric comparison between them "
                 "is not meaningful.", ("paper_id",), both("paper_id"))

    # ---- the recorded differences
    sec = "Recorded differences between the runs"
    differing: list[str] = []
    same: list[str] = []
    unknown: list[str] = []

    def factor(label: str, field_name: str, va: Any, vb: Any) -> None:
        if va is None or vb is None:
            unknown.append(label)
            return
        if va == vb:
            same.append(label)
            return
        differing.append(label)
        add(sec, f"{label}: {va} in A, {vb} in B.", (field_name,), both(field_name))

    factor("CPUs", "cpus", a.cpus and _num(a.cpus), b.cpus and _num(b.cpus))
    factor("Memory limit", "memory_limit", a.memory_limit, b.memory_limit)
    factor("GPU requested", "gpu_requested", a.gpu_requested, b.gpu_requested)
    if a.seed is not None or b.seed is not None:
        factor("Seed", "seed", a.seed, b.seed)
    factor("Container command", "container_command", a.container_command, b.container_command)
    factor("Python version", "python_version", a.python_version, b.python_version)
    factor("Sandbox image", "image", a.image, b.image)
    factor("Tool commit (repro_radar_commit)", "repro_radar_commit",
           a.repro_radar_commit and a.repro_radar_commit[:8], b.repro_radar_commit and b.repro_radar_commit[:8])
    if a.installed_packages is not None and b.installed_packages is not None:
        changed = sorted(n for n in set(a.installed_packages) | set(b.installed_packages)
                         if a.installed_packages.get(n) != b.installed_packages.get(n))
        if changed:
            differing.append("Installed package versions")
            shown = ", ".join(f"{n} ({a.installed_packages.get(n, 'absent')} / {b.installed_packages.get(n, 'absent')})"
                              for n in changed[:8]) + (f" and {len(changed) - 8} more" if len(changed) > 8 else "")
            add(sec, f"Installed package versions differ for {len(changed)} package(s) (A / B): {shown}.",
                ("installed_packages",), both("installed_packages"))
        else:
            same.append("Installed package versions")
    else:
        unknown.append("Installed package versions")
    if _settings(a.pilot3_change) != _settings(b.pilot3_change):
        differing.append("Paper settings of Pilot 3")
        add(sec, f"Paper settings of Pilot 3 (data/pilot3_settings.json): {_settings(a.pilot3_change)} in A, "
                 f"{_settings(b.pilot3_change)} in B.", ("pilot3_change",), both("pilot3_change"))
    for label, name in (("Memory limit set by hand", "memory_override"), ("CPU limit set by hand", "cpus_override")):
        if bool(getattr(a, name)) != bool(getattr(b, name)):
            differing.append(label)
            add(sec, f"{label}: {'yes' if getattr(a, name) else 'no'} in A, {'yes' if getattr(b, name) else 'no'} in B "
                     "(a run with a limit set by hand is not a run under the protocol's own limits).", (name,), both(name))
    if same:
        add(sec, f"The same in both runs: {', '.join(same)}.", ("cpus",), "the stored files of both runs")
    if unknown:
        add(sec, f"Not recorded in at least one of the runs: {', '.join(unknown)}.", ("cpus",), "the stored files of both runs")
    if not differing:
        add(sec, "No recorded difference was found between the two runs.", ("cpus",), "the stored files of both runs")

    # ---- the outcome
    sec = "Outcome"
    if a.run_status and b.run_status:
        if a.run_status != b.run_status or a.exit_code != b.exit_code:
            add(sec, f"The run phase ended with {a.run_status} (exit code {a.exit_code}) in A and {b.run_status} (exit code "
                     f"{b.exit_code}) in B. Rule R6: the outcomes differ, so the metrics are compared only if both runs have some.",
                ("run_status", "exit_code"), both("run_status"))
        else:
            add(sec, f"The run phase ended with {a.run_status} (exit code {a.exit_code}) in both runs.",
                ("run_status", "exit_code"), both("run_status"))
    else:
        add(sec, "The run status is unknown for at least one of the runs.", ("run_status",), both("run_status"))

    # ---- metrics
    sec = "Metrics"
    metric_outcome = NOT_COMPARABLE
    sizes: list[str] = []
    if a.metrics and b.metrics:
        shared = sorted(set(a.metrics) & set(b.metrics))
        only_a, only_b = sorted(set(a.metrics) - set(b.metrics)), sorted(set(b.metrics) - set(a.metrics))
        for name in shared:
            size = shift_size(a.metrics[name], b.metrics[name])
            sizes.append(size)
            if size == IDENTICAL:
                add(sec, f"`{name}` is {_num(a.metrics[name])} in both runs.", ("metrics",), both("metrics"))
            else:
                diff = abs(a.metrics[name] - b.metrics[name])
                rel = diff / max(abs(a.metrics[name]), abs(b.metrics[name]), 1e-12)
                add(sec, f"`{name}` is {_num(a.metrics[name])} in A and {_num(b.metrics[name])} in B: the difference is "
                         f"{_num(diff)} ({rel:.2%} relative), a {size} shift.", ("metrics",), both("metrics"))
        if only_a or only_b:
            names = [f"{n} (A)" for n in only_a] + [f"{n} (B)" for n in only_b]
            add(sec, f"Metrics found in only one run: {', '.join(names)}.", ("metrics",), both("metrics"))
        if not shared:
            metric_outcome = NOT_COMPARABLE
            add(sec, "The two runs have no metric name in common, so no metric value can be compared.", ("metrics",),
                both("metrics"))
        elif all(s == IDENTICAL for s in sizes):
            metric_outcome = SAME_METRICS
        elif all(s in (IDENTICAL, SMALL) for s in sizes):
            metric_outcome = SMALL_SHIFT_METRICS
        else:
            metric_outcome = DIFFERENT_METRICS
        add(sec, "The metrics are the numbers the extractor found in the output, stored with the digits the extractor kept; "
                 "equal stored values do not show that the unrounded values are equal.", ("metrics",), both("metrics"))
    else:
        add(sec, "At least one of the runs has no extracted metric, so no metric value can be compared.", ("metrics",),
            both("metrics"))

    # ---- time and memory
    sec = "Time and memory"
    if a.duration_seconds is not None and b.duration_seconds is not None:
        slower, faster = (("A", "B") if a.duration_seconds >= b.duration_seconds else ("B", "A"))
        ratio = max(a.duration_seconds, b.duration_seconds) / max(min(a.duration_seconds, b.duration_seconds), 1e-9)
        add(sec, f"The run phase took {_num(a.duration_seconds)} s in A and {_num(b.duration_seconds)} s in B"
                 + (f" ({faster} was {ratio:.2f} times faster than {slower})."
                   if a.duration_seconds != b.duration_seconds and a.run_status == b.run_status else "."),
            ("duration_seconds",), both("duration_seconds"))
    else:
        add(sec, "The duration of the run phase is unknown for at least one of the runs.", ("duration_seconds",),
            both("duration_seconds"))
    if a.peak_memory_bytes is not None and b.peak_memory_bytes is not None:
        add(sec, f"The peak memory was {a.peak_memory_bytes / GIB:.2f} GiB in A and {b.peak_memory_bytes / GIB:.2f} GiB in B.",
            ("peak_memory_bytes",), both("peak_memory_bytes"))
    else:
        add(sec, "The peak memory is unknown for at least one of the runs.", ("peak_memory_bytes",), both("peak_memory_bytes"))
    add(sec, "The time of a run also depends on the load of the machine, which the run files do not hold.",
        ("duration_seconds",), "rule R2, docs/DIAGNOSIS.md section 8")

    # ---- reading
    sec = "Reading"
    hardware = [f for f in differing if f in ("CPUs", "GPU requested", "Memory limit")]
    time_differs = (a.duration_seconds is not None and b.duration_seconds is not None
                    and a.duration_seconds != b.duration_seconds)
    review = False
    if metric_outcome == SAME_METRICS:
        if time_differs:
            add(sec, "Rule R2, same metrics and a different time: the stored metrics are identical and the run phase took a "
                     "different time. " + (f"Recorded differences: {', '.join(differing)}. The records do not show which of "
                                           "them changed the time." if differing else "No recorded difference was found."),
                ("metrics", "duration_seconds"), "rule R2, docs/DIAGNOSIS.md section 8")
        else:
            add(sec, "Rule R1: the stored metrics and the run time are the same.", ("metrics", "duration_seconds"),
                "rule R1, docs/DIAGNOSIS.md section 8")
    elif metric_outcome in (SMALL_SHIFT_METRICS, DIFFERENT_METRICS):
        kind = "a small shift" if metric_outcome == SMALL_SHIFT_METRICS else "different metric values"
        if "Seed" in differing:
            add(sec, f"Rule R3, {kind} with a different seed: the seeds differ. A paper that uses its seed can give different "
                     "values for different seeds; this comparison does not show whether this paper's seed controls these metrics.",
                ("metrics", "seed"), "rule R3, docs/DIAGNOSIS.md section 8")
        elif hardware or "Installed package versions" in differing:
            named = hardware + [f for f in differing if f == "Installed package versions"]
            add(sec, f"Rule R4, {kind} with different hardware settings or package versions ({', '.join(named)}). "
                     "These can change numerical results in some programs; the records do not show whether they did here.",
                ("metrics",), "rule R4, docs/DIAGNOSIS.md section 8")
        else:
            add(sec, f"Rule R5, {kind} although no recorded factor of the list differs: the difference is not explained by the "
                     "stored files.", ("metrics",), "rule R5, docs/DIAGNOSIS.md section 8")
        review = metric_outcome == DIFFERENT_METRICS and any(s == LARGE for s in sizes)
        if review:
            add(sec, "At least one shift is large (more than the Tier 2 tolerance). A person should look at this pair before "
                     "any conclusion is drawn.", ("metrics",), "rule R5, docs/DIAGNOSIS.md section 8")
    elif a.run_status != b.run_status:
        add(sec, "Rule R6: the outcomes differ, and the metrics cannot be compared.", ("run_status",),
            "rule R6, docs/DIAGNOSIS.md section 8")
    else:
        add(sec, "The metrics cannot be compared (see above).", ("metrics",), "rule R6, docs/DIAGNOSIS.md section 8")
    return ComparisonReport(run_a=name_a, run_b=name_b, metric_outcome=metric_outcome, differing_factors=differing,
                            review_suggested=review, statements=statements)


def compare_runs(run_a: Path | str, run_b: Path | str, name_a: str | None = None, name_b: str | None = None) -> ComparisonReport:
    return compare_inputs(load_diagnosis_input(run_a), load_diagnosis_input(run_b), name_a, name_b)
