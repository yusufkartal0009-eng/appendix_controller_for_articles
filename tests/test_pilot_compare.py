"""Pilot 2 measurement tools understand the build phase and compare with Pilot 1 (#219)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import categorize_pilot_failures as cat
import pilot_compare
import pilot_measurements as pm

PAPERS = [e["paper_id"] for e in json.loads((Path(__file__).resolve().parent.parent / "data" / "seed_papers.json").read_text(encoding="utf-8"))]


def write_run(runs_dir, paper_id, *, build=None, build_log=None, report=None, stderr=None, stage="STAGED"):
    d = runs_dir / paper_id
    d.mkdir(parents=True)
    record = {"stage": {"status": stage}}
    if build:
        record["build"] = {"status": build}
    (d / "pilot_record.json").write_text(json.dumps(record))
    if build_log:
        (d / "build.log").write_text(build_log)
    if report:
        (d / "run_report.json").write_text(json.dumps(report))
    if stderr:
        (d / "stderr.log").write_text(stderr)


def test_a_failed_build_is_missing_dependency_in_the_build_phase(tmp_path):
    write_run(tmp_path, "paper_005", build="FAILED",
              build_log="Processing x\nerror: command 'gcc' failed with exit code 1\nERROR: Failed building wheel for fastsk\n")
    result = cat.categorize_paper("paper_005", tmp_path)
    assert (result["category"], result["phase"], result["pilot_success"]) == ("MISSING_DEPENDENCY", "build", False)
    assert result["evidence"]["file"] == "build.log" and "gcc" in result["evidence"]["line"]


def test_staging_failure_still_comes_first_and_a_missing_report_is_named(tmp_path):
    write_run(tmp_path, "paper_002", stage="FAILED", build="FAILED")
    assert cat.categorize_paper("paper_002", tmp_path)["other_name"] == "STAGING_FAILED"
    write_run(tmp_path, "paper_003")
    result = cat.categorize_paper("paper_003", tmp_path)
    assert (result["category"], result["other_name"]) == ("OTHER", "NO_RUN_REPORT")


def test_pilot_1_categories_are_unchanged_for_a_normal_run(tmp_path):
    write_run(tmp_path, "paper_008", report={"dependency_install_status": "INSTALLED", "docker_used": True, "isolated": True,
                                              "exit_code": 1, "status": "FAILED"},
              stderr="Traceback\nFileNotFoundError: [Errno 2] No such file or directory: './data/x.csv'\n")
    result = cat.categorize_paper("paper_008", tmp_path)
    assert (result["category"], result["phase"]) == ("DATA_NOT_ACCESSIBLE", "run")


def test_measurements_record_the_build_status_and_the_protocol(tmp_path):
    runs = tmp_path / "pilot2_runs"
    write_run(runs, "paper_005", build="FAILED")
    m = pm.paper_measurement("paper_005", runs)
    assert m["build_status"] == "FAILED" and m["install_success"] is False and m["pilot_success"] is False
    assert pm.measure(runs)["protocol"] == "docs/PILOT_2.md"
    assert pm.measure(tmp_path)["protocol"] == "docs/PILOT_WEEK2.md"


def _stored(dir_, successes):
    dir_.mkdir(parents=True)
    papers = [{"paper_id": p, "pilot_success": p in successes} for p in PAPERS]
    n = len(PAPERS)

    def rate(c):
        return {"count": c, "of": n, "rate": round(c / n, 3)}
    (dir_ / "measurements.json").write_text(json.dumps({
        "papers": papers, "install_success_rate": rate(len(successes)), "run_success_rate": rate(len(successes)),
        "pilot_success_rate": rate(len(successes)), "valid_runs": rate(n)}))
    (dir_ / "failure_categories.json").write_text(json.dumps({
        "papers": [{"paper_id": p, "category": None if p in successes else "MISSING_DEPENDENCY", "other_name": None,
                    "phase": None if p in successes else "install"} for p in PAPERS],
        "counts": {"MISSING_DEPENDENCY": n - len(successes), "TIMEOUT": 0}}))


def test_comparison_copies_both_pilots_unchanged(tmp_path):
    _stored(tmp_path / "p1", set())
    _stored(tmp_path / "p2", {PAPERS[0], PAPERS[1]})
    result = pilot_compare.compare(tmp_path / "p1", tmp_path / "p2")
    assert result["rates"]["pilot_success_rate"]["pilot1"]["count"] == 0
    assert result["rates"]["pilot_success_rate"]["pilot2"]["count"] == 2
    md = pilot_compare.to_markdown(result)
    assert "| Pilot success | 0 / 6 (0.0) | 2 / 6 (0.333) |" in md
    assert f"| `{PAPERS[0]}` | MISSING_DEPENDENCY (install) | success |" in md
    assert pilot_compare.main(["--pilot1-dir", str(tmp_path / "p1"), "--pilot2-dir", str(tmp_path / "p2")]) == 0
    assert (tmp_path / "p2" / "comparison.md").read_text(encoding="utf-8") == md


def test_comparison_of_the_stored_pilot_1_with_itself_matches_the_pilot_1_report():
    runs = Path(__file__).resolve().parent.parent / "data" / "pilot_runs"
    result = pilot_compare.compare(runs, runs)
    assert result["rates"]["pilot_success_rate"]["pilot1"] == {"count": 0, "of": 6, "rate": 0.0}
    assert result["rates"]["install_success_rate"]["pilot1"] == {"count": 1, "of": 6, "rate": 0.167}


def test_a_paper_without_a_record_is_not_run_and_the_header_names_its_directory(tmp_path):
    result = cat.categorize_paper("paper_004", tmp_path)
    assert (result["category"], result["other_name"], result["pilot_success"]) == ("OTHER", "NOT_RUN", False)
    runs = tmp_path / "pilot2_runs"
    write_run(runs, "paper_005", build="FAILED")
    assert "from data/pilot2_runs/;" in pm.to_markdown(pm.measure(runs))
    assert "from data/pilot_runs/;" in pm.to_markdown(pm.measure(tmp_path))


def test_terminal_colors_do_not_hide_a_missing_dependency(tmp_path):
    """#243: a Jupyter traceback prints its last line with color codes."""
    esc = chr(27)
    write_run(tmp_path, "paper_002", report={"dependency_install_status": "INSTALLED", "docker_used": True, "isolated": True,
                                              "exit_code": 1, "status": "FAILED"},
              stderr=f"Traceback\n{esc}[0;31mModuleNotFoundError{esc}[0m: No module named 'lightgbm'\n")
    result = cat.categorize_paper("paper_002", tmp_path)
    assert (result["category"], result["phase"]) == ("MISSING_DEPENDENCY", "run")
    assert result["evidence"]["line"] == "ModuleNotFoundError: No module named 'lightgbm'"
