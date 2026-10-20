"""The rule-based diagnosis report of one stored run (#33, docs/DIAGNOSIS.md).

`build_report` turns a `DiagnosisInput` and the classifier's answer into statements. Every statement carries the fields it
rests on and the file and key they were read from; a value that the run files do not hold is written as unknown, never
guessed. No model and no network are used. The wording is neutral and describes the run, not the paper or its authors.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import DEFAULT_TOLERANCE, SEED_PAPERS_PATH
from src.diagnosis.classifier import Classification, classify_run
from src.diagnosis.schema import DiagnosisInput, load_diagnosis_input

GIB = 1024**3

# What each category means, as a description of the category and not of the cause behind it.
CATEGORY_TEXT = {
    "MISSING_DEPENDENCY": "a package that the code or its requirements name was not available in the sandbox when the run needed it",
    "DATA_NOT_ACCESSIBLE": "a data file or network address that the program asked for was not available in the sandbox (the sandbox has no network)",
    "HARDWARE_GPU_REQUIRED": "the program asked for a GPU or a CUDA driver that the container did not provide",
    "TIMEOUT": "the run phase reached its time limit before the program ended; it is not known whether it would have finished later",
    "SCRIPT_NOT_FOUND": "the script named as the entry point was not in the repository at the pinned commit",
    "LICENSE_BLOCKED": "the repository's license did not allow the run",
    "OUT_OF_MEMORY": "the container was stopped at its memory limit",
    "OUTPUT_LIMIT_EXCEEDED": "the program wrote more output than the sandbox keeps and was stopped",
    "WRITE_TO_READ_ONLY_REPOSITORY": "the program tried to write into the repository, which the sandbox mounts read-only",
    "MISSING_FILE": "a file that is not a data file and that the program asked for was not found",
    "STAGING_FAILED": "the repository could not be fetched at the pinned commit",
    "NOT_RUN": "no record of a run exists in the folder",
    "NO_RUN_REPORT": "the run phase wrote no report",
    "RAN_WITHOUT_INSTALLED_DEPENDENCIES": "the program ended with exit code 0 but nothing was installed, so the run is not counted as a success",
    "OTHER": "the final error line matches none of the named categories",
}


@dataclass(frozen=True)
class Statement:
    """One sentence of the report, the fields it rests on, and where each was read from."""

    section: str
    text: str
    fields: tuple[str, ...]
    source: str


@dataclass
class DiagnosisReport:
    run_dir: str
    paper_id: str | None
    category_label: str | None
    statements: list[Statement] = field(default_factory=list)

    def sections(self) -> dict[str, list[Statement]]:
        grouped: dict[str, list[Statement]] = {}
        for statement in self.statements:
            grouped.setdefault(statement.section, []).append(statement)
        return grouped

    def to_markdown(self) -> str:
        lines = [f"# Diagnosis of `{self.run_dir}`", ""]
        for section, items in self.sections().items():
            lines.append(f"## {section}")
            lines.extend(f"- {s.text} *(source: {s.source})*" for s in items)
            lines.append("")
        lines.append("This report is rule-based: every sentence is written from the stored files of the run named above. "
                     "Nothing was inferred beyond them, and a cause that no stored line states was not investigated.")
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {"run_dir": self.run_dir, "paper_id": self.paper_id, "category": self.category_label,
                "statements": [{"section": s.section, "text": s.text, "fields": list(s.fields), "source": s.source}
                               for s in self.statements]}


def claims_from_seed_papers(paper_id: str | None, path: Path | None = None) -> dict[str, float] | None:
    """The `expected_claims` of a seed paper (data/seed_papers.json), or None for a paper that is not in the file."""
    if not paper_id:
        return None
    entries = json.loads((path or SEED_PAPERS_PATH).read_text(encoding="utf-8"))
    for entry in entries:
        if entry["paper_id"] == paper_id:
            return {k: float(v) for k, v in entry.get("expected_claims", {}).items()} or None
    return None


def _num(value: float) -> str:
    return f"{value:g}"


def _unknown(data: DiagnosisInput, name: str, what: str) -> tuple[str, tuple[str, ...], str]:
    return f"{what} is unknown.", (name,), data.source_of(name)


def build_report(data: DiagnosisInput, classification: Classification | None = None) -> DiagnosisReport:
    """The statements of one run. `classification` is the classifier's answer (None: not classified)."""
    report = DiagnosisReport(run_dir=data.run_dir, paper_id=data.paper_id,
                             category_label=classification.label if classification else None)

    def add(section: str, text: str, fields: tuple[str, ...], source: str | None = None) -> None:
        report.statements.append(Statement(section, text, fields, source or "; ".join(data.source_of(f) for f in fields)))

    # ---- what ran
    sec = "What ran"
    if data.paper_id:
        add(sec, f"The run is of `{data.paper_id}`" + (f" under `{data.protocol}`." if data.protocol else "."),
            ("paper_id", "protocol") if data.protocol else ("paper_id",))
    else:
        add(sec, *_unknown(data, "paper_id", "The paper of this run"))
    if data.container_command:
        add(sec, f"The container command was `{data.container_command}`.", ("container_command",))
    else:
        add(sec, *_unknown(data, "container_command", "The container command"))
    if data.python_version:
        add(sec, f"The sandbox image used Python {data.python_version}.", ("python_version",))
    if data.started_at and data.finished_at:
        add(sec, f"The record runs from {data.started_at} to {data.finished_at}.", ("started_at", "finished_at"))
    if data.seed is not None:
        add(sec, f"This is the run with seed {data.seed} of a multi-seed run (docs/MULTI_SEED.md).", ("seed",))

    # ---- phases
    sec = "How the phases ended"
    if data.stage_status:
        text = f"Fetching the repository ended with status {data.stage_status}."
        if data.stage_error:
            text += f" The recorded error was: {data.stage_error}"
        add(sec, text, ("stage_status", "stage_error") if data.stage_error else ("stage_status",))
    else:
        add(sec, *_unknown(data, "stage_status", "The status of fetching the repository"))
    if data.build_status:
        add(sec, f"The build phase ended with status {data.build_status}.", ("build_status",))
    if data.install_status:
        add(sec, f"The dependency install ended with status {data.install_status}.", ("install_status",))
    else:
        add(sec, *_unknown(data, "install_status", "The status of the dependency install"))
    if data.run_status:
        text = f"The run phase ended with status {data.run_status}"
        fields = ["run_status"]
        if data.exit_code is not None:
            text += f" and exit code {data.exit_code}"
            fields.append("exit_code")
        if data.duration_seconds is not None:
            text += f" after {_num(data.duration_seconds)} s"
            fields.append("duration_seconds")
        add(sec, text + ".", tuple(fields))
    else:
        add(sec, *_unknown(data, "run_status", "The status of the run phase"))

    # ---- classification
    if classification is not None:
        sec = "Category of the outcome"
        if classification.pilot_success:
            add(sec, "The classifier found no failure: the install and the run phase both ended cleanly.",
                ("install_status", "run_status", "exit_code"))
        elif classification.label is None:
            add(sec, "The classifier assigned no failure category.", ("run_status",))
        else:
            meaning = CATEGORY_TEXT.get(classification.label, CATEGORY_TEXT.get(classification.category or "", ""))
            phase = f" in the {classification.phase} phase" if classification.phase else ""
            add(sec, f"The classifier assigned the category {classification.label}{phase}: {meaning}.",
                ("run_status", "install_status", "stage_status"), "src/diagnosis/classifier.py applied to the run files")
            ev = classification.evidence
            if ev and ev.get("line"):
                where = f"{ev['file']}:{ev['line_number']}" if ev.get("line_number") else ev["file"]
                add(sec, f"The deciding line is `{where}`: `{ev['line']}`", ("run_status",), where)
            add(sec, "The category is the classifier's reading of that line; a cause behind the line was not investigated.",
                ("run_status",), "src/diagnosis/classifier.py")

    # ---- limits
    sec = "Limits and resources"
    if data.cpus is not None or data.memory_limit:
        parts = []
        fields = []
        if data.cpus is not None:
            parts.append(f"{_num(data.cpus)} CPUs")
            fields.append("cpus")
        if data.memory_limit:
            parts.append(f"a memory limit of {data.memory_limit}")
            fields.append("memory_limit")
        add(sec, f"The container had {' and '.join(parts)}.", tuple(fields))
    else:
        add(sec, *_unknown(data, "memory_limit", "The CPU and memory limits"))
    if data.timeout_limit_seconds is not None:
        add(sec, f"The time limit of the run phase was {data.timeout_limit_seconds} s.", ("timeout_limit_seconds",))
    if data.peak_memory_bytes is not None:
        add(sec, f"The measured peak memory of the run was {data.peak_memory_bytes / GIB:.2f} GiB.", ("peak_memory_bytes",))
    else:
        add(sec, *_unknown(data, "peak_memory_bytes", "The peak memory"))
    for name, label in (("memory_override", "memory limit"), ("cpus_override", "CPU limit"), ("timeout_override", "time limit")):
        if getattr(data, name):
            add(sec, f"The {label} was set by hand for this run, so it is not a run under the protocol's own limits.", (name,))

    # ---- metrics and claims
    sec = "Metrics and claims"
    if data.metrics:
        shown = ", ".join(f"{k} {_num(v)}" for k, v in sorted(data.metrics.items()))
        add(sec, f"The metric extractor found these numbers in the output: {shown}. The extractor reads names and numbers from "
                 "the log; a number it found is not necessarily a result of the paper.", ("metrics",))
    else:
        add(sec, "No metric was extracted from the output (or the run report is missing), so no number of this run can be compared.",
            ("metrics",))
    if data.claims:
        for name, claimed in sorted(data.claims.items()):
            if data.metrics and name in data.metrics:
                got = data.metrics[name]
                diff = abs(got - claimed)
                rel = f"{diff / abs(claimed):.1%}" if claimed else "undefined (claimed value is 0)"
                add(sec, f"Claim `{name}`: claimed {_num(claimed)}, found in the output {_num(got)}; the difference is {_num(diff)} "
                         f"({rel} of the claimed value). The Tier 2 tolerance is {_num(DEFAULT_TOLERANCE)}; this report states "
                         "no verdict.", ("claims", "metrics"), f"claims given; {data.source_of('metrics')}")
            else:
                add(sec, f"Claim `{name}` (claimed {_num(claimed)}): no metric with this name was found in the output, so nothing "
                         "was compared for it. A differently named metric may measure the same thing; this report does not "
                         "match names by meaning.", ("claims", "metrics"), f"claims given; {data.source_of('metrics')}")
    else:
        add(sec, "No claims were given for this diagnosis, so no comparison with a claim was made.", ("claims",),
            "no claims were passed")

    # ---- the end of the stderr, when the run failed
    if classification is not None and not classification.pilot_success and data.stderr_tail:
        sec = "Last lines of stderr"
        for line in data.stderr_tail[-3:]:
            add(sec, f"`stderr.log:{line.line_number}`: `{line.text}`", ("run_status",), f"stderr.log:{line.line_number}")
    return report


def diagnose_run(run_dir: Path | str, claims: dict[str, float] | None = None, use_seed_claims: bool = True) -> DiagnosisReport:
    """Load, classify, and report one run folder. Claims default to the seed paper's `expected_claims` when it has any."""
    data = load_diagnosis_input(run_dir)
    if claims is None and use_seed_claims:
        claims = claims_from_seed_papers(data.paper_id)
    data.claims = claims
    return build_report(data, classify_run(run_dir))
