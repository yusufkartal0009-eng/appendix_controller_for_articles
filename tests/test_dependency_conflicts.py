"""Dependency conflicts named in the bundle and run reports (#160)."""

import json
import subprocess
import sys
import zipfile

from src.config import PROJECT_ROOT
from src.sandbox.dependency_conflicts import (
    name_requirement_lines,
    parse_dependency_conflicts,
)
from src.sandbox.stager import RepoStager


def test_real_pilot_install_log_of_paper_005():
    log = (PROJECT_ROOT / "data" / "pilot_runs" / "paper_005" / "install.log").read_text(encoding="utf-8")
    assert parse_dependency_conflicts(log) == [{
        "cannot_install": ["-r /workspace/repo/requirements.txt (line 4)", "python-dateutil==2.8.1"],
        "caused_by": ["The user requested python-dateutil==2.8.1", "pandas 3.0.6 depends on python-dateutil>=2.8.2"],
    }]


def test_requirement_lines_are_named_from_the_staged_file(tmp_path):
    (tmp_path / "requirements.txt").write_text("certifi\njoblib\nnumpy\npandas\npython-dateutil==2.8.1\n")
    conflicts = [{"cannot_install": ["-r /workspace/repo/requirements.txt (line 4)", "python-dateutil==2.8.1"],
                  "caused_by": []}]
    assert name_requirement_lines(conflicts, tmp_path)[0]["cannot_install"] == [
        "pandas (requirements.txt line 4)", "python-dateutil==2.8.1"]


def test_no_conflict_gives_an_empty_list():
    assert parse_dependency_conflicts("Successfully installed toolz-0.12.1\n") == []
    assert parse_dependency_conflicts("") == []


def _wheel(directory, name, version, requires=()):
    """A minimal pure-Python wheel with dependency metadata only (built by hand, no network)."""
    dist = f"{name}-{version}.dist-info"
    path = directory / f"{name}-{version}-py3-none-any.whl"
    meta = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n" + "".join(f"Requires-Dist: {r}\n" for r in requires)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{name}/__init__.py", "")
        zf.writestr(f"{dist}/METADATA", meta)
        zf.writestr(f"{dist}/WHEEL", "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        zf.writestr(f"{dist}/RECORD", "")
    return path


def test_minimal_conflicting_requirements_file_with_real_pip(tmp_path):
    """Real pip, offline: rrtoolb 1.0 needs rrtoola>=2, but the file pins rrtoola==1.0."""
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    _wheel(wheels, "rrtoola", "1.0")
    _wheel(wheels, "rrtoolb", "1.0", requires=["rrtoola>=2"])
    req = tmp_path / "requirements.txt"
    req.write_text("rrtoola==1.0\nrrtoolb==1.0\n")
    res = subprocess.run([sys.executable, "-m", "pip", "install", "--dry-run", "--no-index", "--find-links", str(wheels),
                          "-r", str(req)], capture_output=True, text=True, check=False)
    assert res.returncode != 0
    # pip prints the ERROR line to stderr and the cause lines to stdout
    conflicts = name_requirement_lines(parse_dependency_conflicts(res.stderr + "\n" + res.stdout), tmp_path)
    assert len(conflicts) == 1
    assert any("rrtoola==1.0" in item for item in conflicts[0]["cannot_install"])
    assert any("rrtoolb 1.0 depends on rrtoola>=2" in cause for cause in conflicts[0]["caused_by"])


def test_bundle_report_names_conflicts_from_the_full_stderr(tmp_path, monkeypatch):
    source = tmp_path / "repo"
    source.mkdir()
    (source / "main.py").write_text("print(1)\n")
    (source / "requirements.txt").write_text("pandas\npython-dateutil==2.8.1\n")
    stager = RepoStager(staging_root=tmp_path / "staging")
    staged = stager.stage_repository(paper_id="conflict", source=str(source))
    stderr = ("x" * 3000 + "\nERROR: Cannot install -r " + str(staged.staged_path / "requirements.txt")
              + " (line 1) and python-dateutil==2.8.1 because these package versions have conflicting dependencies.\n\n"
              "The conflict is caused by:\n    The user requested python-dateutil==2.8.1\n"
              "    pandas 3.0.6 depends on python-dateutil>=2.8.2\n\n" + "y" * 1500)
    monkeypatch.setattr("src.sandbox.stager.subprocess.run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", stderr if "-r" in cmd else ""))
    result = stager.bundle_dependencies(staged)
    assert result["dependency_conflicts"][0]["cannot_install"] == ["pandas (requirements.txt line 1)", "python-dateutil==2.8.1"]
    assert "pandas 3.0.6 depends on python-dateutil>=2.8.2" in result["dependency_conflicts"][0]["caused_by"]
    assert "caused by" not in result["stderr"]  # the stored excerpt alone would have lost it
    json.dumps(result)
