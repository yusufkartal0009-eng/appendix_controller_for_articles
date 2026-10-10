"""The earlier Pilot 2 attempts are indexed from their stored records (#237)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pilot2_attempts as pa


def write_attempt(root, name, *, commit="abcdef1234", stage="STAGED", build=None, install="INSTALLED", run=None):
    d = root / name
    d.mkdir(parents=True)
    record = {"repro_radar_commit": commit, "stage": {"status": stage}}
    if build:
        record["build"] = {"status": build}
    if run:
        record["run"] = {"status": run[0], "exit_code": run[1], "dependency_install_status": install}
    (d / "pilot_record.json").write_text(json.dumps(record))
    if run:
        (d / "run_report.json").write_text(json.dumps({"dependency_install_status": install}))


def test_rows_come_from_the_stored_records_and_are_ordered(tmp_path):
    write_attempt(tmp_path, "paper_006_attempt2", build="BUILT", install="FAILED", run=("FAILED", 1))
    write_attempt(tmp_path, "paper_006_attempt10", commit="1234567fff", build="BUILT", run=("COMPLETED", 0))
    write_attempt(tmp_path, "paper_004_attempt1", stage="FAILED")
    (tmp_path / "notes").mkdir()  # not an attempt
    (tmp_path / "reasons.json").write_text(json.dumps({"paper_006_attempt2": "pyrsistent had no wheel (#227)"}))
    rows = pa.index(tmp_path)
    assert [r["attempt"] for r in rows] == ["paper_004_attempt1", "paper_006_attempt2", "paper_006_attempt10"]
    a2 = rows[1]
    assert (a2["repro_radar_commit"], a2["build"], a2["install"], a2["run"], a2["exit_code"]) == ("abcdef1", "BUILT", "FAILED", "FAILED", 1)
    assert a2["superseded_because"] == "pyrsistent had no wheel (#227)" and rows[2]["superseded_because"] is None
    assert rows[0]["stage"] == "FAILED" and rows[0]["run"] is None


def test_markdown_and_cli_report_a_missing_reason(tmp_path, capsys):
    write_attempt(tmp_path, "paper_005_attempt1", run=("FAILED", 1))
    assert pa.main(["--dir", str(tmp_path)]) == 1  # no reasons.json entry
    assert "no reason in reasons.json for: paper_005_attempt1" in capsys.readouterr().err
    (tmp_path / "reasons.json").write_text(json.dumps({"paper_005_attempt1": "extras were not installed (#223)"}))
    assert pa.main(["--dir", str(tmp_path)]) == 0
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "| `paper_005_attempt1` | `abcdef1` | STAGED | none | INSTALLED | FAILED | 1 | extras were not installed (#223) |" in readme
    assert json.loads((tmp_path / "index.json").read_text())[0]["number"] == 1


def test_a_non_attempt_directory_is_refused():
    with pytest.raises(ValueError):
        pa.describe(Path("paper_001_final"), {})
