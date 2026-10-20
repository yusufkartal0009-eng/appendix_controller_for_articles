"""The diagnosis input: what is known about one stored run, and where each value came from (#31, docs/DIAGNOSIS.md).

`load_diagnosis_input(run_dir)` reads the files a run leaves (`pilot_record.json`, `run_report.json`, `stderr.log`,
`stdout.log`) and nothing else. A value that the files do not hold is `None` ("unknown"); it is never filled in. For every
value that was found, `sources` names the file and the key it was read from, so that every sentence of a report can point at
its field.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RECORD_NAME = "pilot_record.json"
REPORT_NAME = "run_report.json"
LOG_TAIL_LINES = 12
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# field name -> (file, dotted key path). The single place that says where a value comes from.
FIELD_SOURCES: dict[str, tuple[str, str]] = {
    "paper_id": (RECORD_NAME, "paper_id"),
    "protocol": (RECORD_NAME, "protocol"),
    "started_at": (RECORD_NAME, "started_at"),
    "finished_at": (RECORD_NAME, "finished_at"),
    "python_version": (RECORD_NAME, "python_version"),
    "repro_radar_commit": (RECORD_NAME, "repro_radar_commit"),
    "image": (REPORT_NAME, "image"),
    "installed_packages": (REPORT_NAME, "installed_packages"),
    "container_command": (RECORD_NAME, "container_command"),
    "stage_status": (RECORD_NAME, "stage.status"),
    "stage_error": (RECORD_NAME, "stage.error"),
    "build_status": (RECORD_NAME, "build.status"),
    "install_status": (REPORT_NAME, "dependency_install_status"),
    "run_status": (REPORT_NAME, "status"),
    "exit_code": (REPORT_NAME, "exit_code"),
    "duration_seconds": (REPORT_NAME, "duration_seconds"),
    "timeout_limit_seconds": (REPORT_NAME, "meta.timeout_limit_seconds"),
    "peak_memory_bytes": (REPORT_NAME, "meta.peak_memory_bytes"),
    "memory_limit": (RECORD_NAME, "limits.memory_limit"),
    "cpus": (RECORD_NAME, "limits.cpus"),
    "gpu_requested": (REPORT_NAME, "meta.gpu_requested"),
    "metrics": (REPORT_NAME, "metrics"),
    "seed": (RECORD_NAME, "multi_seed.seed"),
    "memory_override": (RECORD_NAME, "memory_override"),
    "cpus_override": (RECORD_NAME, "cpus_override"),
    "timeout_override": (RECORD_NAME, "timeout_override"),
    "pilot3_change": (RECORD_NAME, "pilot3_change"),
}


@dataclass(frozen=True)
class LogLine:
    """One quoted line of a log, with the file and the line number it came from."""

    file: str
    line_number: int
    text: str


@dataclass
class DiagnosisInput:
    """Everything a diagnosis may state about one run. `None` means unknown."""

    run_dir: str
    paper_id: str | None = None
    protocol: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    python_version: str | None = None
    repro_radar_commit: str | None = None
    image: str | None = None
    installed_packages: dict[str, str] | None = None
    container_command: str | None = None
    stage_status: str | None = None
    stage_error: str | None = None
    build_status: str | None = None
    install_status: str | None = None
    run_status: str | None = None
    exit_code: int | None = None
    duration_seconds: float | None = None
    timeout_limit_seconds: int | None = None
    peak_memory_bytes: int | None = None
    memory_limit: str | None = None
    cpus: float | None = None
    gpu_requested: bool | None = None
    metrics: dict[str, float] | None = None
    claims: dict[str, float] | None = None
    seed: int | None = None
    memory_override: dict[str, Any] | None = None
    cpus_override: dict[str, Any] | None = None
    timeout_override: dict[str, Any] | None = None
    pilot3_change: dict[str, Any] | None = None
    stderr_tail: list[LogLine] = field(default_factory=list)
    stdout_tail: list[LogLine] = field(default_factory=list)
    files_present: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)

    def source_of(self, name: str) -> str:
        """`file: key` of a field that was found, or `<file>: <key> (not present)` for an unknown one."""
        file, key = FIELD_SOURCES.get(name, ("(not a stored field)", name))
        return f"{file}: {key}" if name in self.sources else f"{file}: {key} (not present)"


def _dig(data: dict[str, Any] | None, dotted: str) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def log_tail(path: Path, count: int = LOG_TAIL_LINES) -> list[LogLine]:
    """The last `count` non-empty lines of a log, without terminal color codes, with their real line numbers."""
    if not path.is_file():
        return []
    lines = [ANSI_RE.sub("", line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    kept = [LogLine(path.name, number, text) for number, text in enumerate(lines, start=1) if text.strip()]
    return kept[-count:]


def load_diagnosis_input(run_dir: Path | str, claims: dict[str, float] | None = None) -> DiagnosisInput:
    """Read one run directory. `claims` (question ID -> value) is given by the caller; the run files do not hold claims."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"{run_dir} is not a directory")
    files = {RECORD_NAME: _read_json(run_dir / RECORD_NAME), REPORT_NAME: _read_json(run_dir / REPORT_NAME)}
    result = DiagnosisInput(run_dir=run_dir.as_posix(), claims=dict(claims) if claims else None)
    result.files_present = sorted(p.name for p in run_dir.iterdir() if p.is_file())
    for name, (file, key) in FIELD_SOURCES.items():
        value = _dig(files[file], key)
        if value is None:
            continue
        if name == "metrics":
            value = {k: float(v) for k, v in value.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        if name == "installed_packages":
            value = {p["name"]: p["version"] for p in value if isinstance(p, dict) and "name" in p and "version" in p}
        setattr(result, name, value)
        result.sources[name] = f"{file}: {key}"
    # A run that did not start the run phase has no run_report; the pilot record's own `run` block is the fallback.
    for name, key in (("run_status", "run.status"), ("exit_code", "run.exit_code"),
                      ("duration_seconds", "run.duration_seconds"), ("install_status", "run.dependency_install_status"),
                      ("peak_memory_bytes", "run.peak_memory_bytes")):
        if name not in result.sources:
            value = _dig(files[RECORD_NAME], key)
            if value is not None:
                setattr(result, name, value)
                result.sources[name] = f"{RECORD_NAME}: {key}"
    result.stderr_tail = log_tail(run_dir / "stderr.log")
    result.stdout_tail = log_tail(run_dir / "stdout.log")
    return result
