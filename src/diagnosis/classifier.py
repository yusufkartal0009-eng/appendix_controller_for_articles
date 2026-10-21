"""Rule-based classification of a failed (or successful) sandbox run into the failure categories (#32).

The rules are those of `docs/PILOT_WEEK2.md` section 7, moved here from `scripts/categorize_pilot_failures.py` (which imports
them, so the pilot scripts and this classifier cannot disagree). The first failure in the order stage -> build -> install ->
run decides the category, and the deciding log line is quoted verbatim with its file and line number. Nothing here calls a
model or the network.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CATEGORIES = (
    "MISSING_DEPENDENCY",
    "DATA_NOT_ACCESSIBLE",
    "HARDWARE_GPU_REQUIRED",
    "TIMEOUT",
    "SCRIPT_NOT_FOUND",
    "LICENSE_BLOCKED",
    "OTHER",
)

GPU_PATTERNS = ("no cuda gpus are available", "torch not compiled with cuda", "cuda driver", "nvidia driver",
                "found no nvidia driver", "cuda error", "cudaerror")
NETWORK_PATTERNS = ("network is unreachable", "temporary failure in name resolution", "name or service not known",
                    "urlerror", "connectionerror", "max retries exceeded", "failed to establish a new connection",
                    "httperror", "connectionrefusederror", "connection refused")
DATA_EXTENSIONS = (".csv", ".tsv", ".npy", ".npz", ".pkl", ".pickle", ".parquet", ".arff", ".fasta", ".tar", ".gz",
                   ".zip", ".h5", ".hdf5", ".json", ".txt", ".svm", ".libsvm", ".pt")


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")  # terminal colors, for example from a Jupyter traceback (#243)


def _lines(path: Path) -> list[str]:
    """The lines of a log file, without terminal color codes, so that they can be classified and quoted."""
    if not path.exists():
        return []
    return [ANSI_RE.sub("", line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]


def _evidence(path: Path, line_no: int, line: str) -> dict[str, Any]:
    return {"file": path.name, "line_number": line_no, "line": line}


def _first_matching(path: Path, predicate) -> tuple[int, str] | None:
    for i, line in enumerate(_lines(path), start=1):
        if predicate(line):
            return i, line
    return None


def _last_nonempty(path: Path) -> tuple[int, str] | None:
    lines = _lines(path)
    for i in range(len(lines), 0, -1):
        if lines[i - 1].strip():
            return i, lines[i - 1]
    return None


def classify_exception(line: str) -> tuple[str, str | None]:
    """Category (and a name for OTHER) from the final exception line of a failed run."""
    lower = line.lower()
    if line.startswith(("ModuleNotFoundError", "ImportError")):
        return "MISSING_DEPENDENCY", None
    if "cuda out of memory" in lower:
        return "OTHER", "GPU_OUT_OF_MEMORY"
    if any(p in lower for p in GPU_PATTERNS):
        return "HARDWARE_GPU_REQUIRED", None
    if any(p in lower for p in NETWORK_PATTERNS):
        return "DATA_NOT_ACCESSIBLE", None
    if "read-only file system" in lower:
        return "OTHER", "WRITE_TO_READ_ONLY_REPOSITORY"
    if "no space left on device" in lower:
        return "OTHER", "NO_SPACE_LEFT"
    if "permissionerror" in lower or "permission denied" in lower:
        return "OTHER", "PERMISSION_DENIED"
    missing = re.search(r"(FileNotFoundError|No such file or directory).*?'([^']+)'", line)
    if missing:
        path = missing.group(2).lower()
        if "data" in path or path.endswith(DATA_EXTENSIONS):
            return "DATA_NOT_ACCESSIBLE", None
        return "OTHER", "MISSING_FILE"
    return "OTHER", None


def categorize_paper(paper_id: str, runs_dir: Path) -> dict[str, Any]:
    paper_dir = runs_dir / paper_id
    result: dict[str, Any] = {"paper_id": paper_id, "category": None, "other_name": None, "phase": None,
                              "evidence": None, "pilot_success": False}
    if not (paper_dir / "pilot_record.json").is_file():
        result.update(category="OTHER", other_name="NOT_RUN", phase="stage",
                      evidence={"file": "pilot_record.json", "line_number": None, "line": "no pilot record exists for this paper"})
        return result
    record = json.loads((paper_dir / "pilot_record.json").read_text(encoding="utf-8"))
    report_path = paper_dir / "run_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None

    stage = record.get("stage") or {}
    if stage.get("status") != "STAGED":
        result.update(category="OTHER", other_name="STAGING_FAILED", phase="stage",
                      evidence={"file": "pilot_record.json", "line_number": None, "line": stage.get("error", "")})
        return result
    build = record.get("build")
    if build and build.get("status") != "BUILT":
        # Pilot 2 (docs/PILOT_2.md section 7): the first failure decides, in the order build, install, run. A failed
        # build means the paper's dependencies could not be installed.
        build_log = paper_dir / "build.log"
        hit = _first_matching(build_log, lambda s: s.startswith("ERROR") or "error:" in s.lower()) or _last_nonempty(build_log)
        if hit is None and build.get("error"):
            evidence = {"file": "pilot_record.json", "line_number": None, "line": str(build["error"])[:300]}
        else:
            evidence = _evidence(build_log, *hit) if hit else None
        result.update(category="MISSING_DEPENDENCY", phase="build", evidence=evidence)
        return result
    if report is None:
        result.update(category="OTHER", other_name="NO_RUN_REPORT", phase="run",
                      evidence={"file": "pilot_record.json", "line_number": None, "line": "no run_report.json was written"})
        return result
    if not stage.get("target_script_exists", True):
        result.update(category="SCRIPT_NOT_FOUND", phase="stage",
                      evidence={"file": "pilot_record.json", "line_number": None, "line": "target_script_exists: false"})
        return result

    install_ok = report.get("dependency_install_status") == "INSTALLED"
    run_ok = report.get("docker_used") is True and report.get("isolated") is True and report.get("exit_code") == 0
    if install_ok and run_ok:
        result["pilot_success"] = True
        return result

    if report.get("dependency_install_status") == "FAILED":
        install_log = paper_dir / "install.log"
        hit = _first_matching(install_log, lambda s: s.startswith("ERROR:"))
        result.update(category="MISSING_DEPENDENCY", phase="install",
                      evidence=_evidence(install_log, *hit) if hit else None)
        return result

    status = report.get("status")
    stderr = paper_dir / "stderr.log"
    if status == "TIMEOUT":
        result.update(category="TIMEOUT", phase="run",
                      evidence={"file": "run_report.json", "line_number": None, "line": "status: TIMEOUT"})
        return result
    if status == "OOM_KILLED":
        result.update(category="OTHER", other_name="OUT_OF_MEMORY", phase="run",
                      evidence={"file": "run_report.json", "line_number": None, "line": "status: OOM_KILLED"})
        return result
    if status == "OUTPUT_LIMIT_EXCEEDED":
        result.update(category="OTHER", other_name="OUTPUT_LIMIT_EXCEEDED", phase="run",
                      evidence={"file": "run_report.json", "line_number": None, "line": "status: OUTPUT_LIMIT_EXCEEDED"})
        return result
    if run_ok:
        # Ran with exit code 0 but nothing was installed (SKIPPED): no failure, no pilot success (section 7).
        result.update(category=None, other_name="RAN_WITHOUT_INSTALLED_DEPENDENCIES", phase="install")
        return result

    hit = _last_nonempty(stderr)
    category, other_name = classify_exception(hit[1]) if hit else ("OTHER", None)
    result.update(category=category, other_name=other_name, phase="run",
                  evidence=_evidence(stderr, *hit) if hit else None)
    return result


@dataclass(frozen=True)
class Classification:
    """The classifier's answer for one run. `category` is None for a run without a failure."""

    paper_id: str
    category: str | None
    other_name: str | None
    phase: str | None
    evidence: dict[str, Any] | None
    pilot_success: bool

    @property
    def label(self) -> str | None:
        """The name used in reports: the `OTHER` name when there is one (for example OUT_OF_MEMORY), else the category."""
        return self.other_name or self.category


def classify_run(run_dir: Path | str) -> Classification:
    """Classify one stored run folder (`pilot_record.json`, `run_report.json`, and the logs)."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"{run_dir} is not a directory")
    found = categorize_paper(run_dir.name, run_dir.parent)
    return Classification(paper_id=found["paper_id"], category=found["category"], other_name=found["other_name"],
                          phase=found["phase"], evidence=found["evidence"], pilot_success=found["pilot_success"])


def classify_log_text(text: str) -> tuple[str, str | None, int, str] | None:
    """Classify the final exception line of a stderr text: (category, other name, line number, line), or None if empty."""
    lines = [ANSI_RE.sub("", line) for line in text.splitlines()]
    for number in range(len(lines), 0, -1):
        if lines[number - 1].strip():
            category, other_name = classify_exception(lines[number - 1])
            return category, other_name, number, lines[number - 1]
    return None
