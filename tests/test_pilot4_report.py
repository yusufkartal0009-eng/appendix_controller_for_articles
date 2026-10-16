"""Pilot 4 results (#351): strict and corrected rates, the first attempt kept apart, and the side-by-side table."""

import json

import pytest

from scripts import pilot4_report


def _run_dir(directory, install="INSTALLED", exit_code=0, status="COMPLETED", stderr="", correction=None):
    directory.mkdir(parents=True)
    report = {"docker_used": True, "isolated": True, "dependency_install_status": install, "exit_code": exit_code,
              "status": status, "duration_seconds": 12.5, "meta": {"peak_memory_bytes": 1024 ** 3}}
    record = {"stage": {"status": "STAGED"}, "run": {"status": status, "exit_code": exit_code},
              "pilot4": {"correction": correction}}
    (directory / "run_report.json").write_text(json.dumps(report), encoding="utf-8")
    (directory / "pilot_record.json").write_text(json.dumps(record), encoding="utf-8")
    (directory / "stdout.log").write_text("", encoding="utf-8")
    (directory / "stderr.log").write_text(stderr, encoding="utf-8")
    (directory / "install_meta.json").write_text(json.dumps({"peak_memory_bytes": 1}), encoding="utf-8")


@pytest.fixture
def world(tmp_path):
    data = tmp_path / "data"
    corpus = [{"paper_id": f"paper_10{i}", "title": f"T{i}", "repo_url": f"https://github.com/o/r{i}",
               "run_command": f"python s{i}.py --x 1"} for i in (1, 2, 3)]
    (data / "corpus_expansion").mkdir(parents=True)
    (data / "corpus_expansion" / "papers.json").write_text(json.dumps(corpus), encoding="utf-8")
    runs = data / "pilot4_runs"
    # paper_101 works at once; paper_102 fails, then works after a correction; paper_103 fails and fails again
    _run_dir(runs / "paper_101")
    change = [{"change": "add numpy", "log_line": "ModuleNotFoundError: No module named 'numpy'"}]
    _run_dir(runs / "first_attempts" / "paper_102_attempt1", exit_code=1, stderr="ModuleNotFoundError: No module named 'numpy'\n")
    _run_dir(runs / "paper_102", correction={"changes": change})
    _run_dir(runs / "first_attempts" / "paper_103_attempt1", exit_code=1, stderr="ModuleNotFoundError: No module named 'a'\n")
    _run_dir(runs / "paper_103", exit_code=1, stderr="OSError: [Errno 30] Read-only file system: 'x'\n",
             correction={"changes": change})
    for name, folder in (("pilot1", "pilot_runs"), ("pilot2", "pilot2_runs"), ("pilot3", "pilot3_runs")):
        (data / folder).mkdir()
        rate = {"count": 1, "of": 6, "rate": 0.167}
        (data / folder / "measurements.json").write_text(json.dumps(
            {"install_success_rate": rate, "run_success_rate": rate, "pilot_success_rate": rate}), encoding="utf-8")
    return data, runs, data / "corpus_expansion" / "papers.json"


def test_strict_and_corrected_rates_differ_by_the_correction_round(world):
    data, runs, corpus = world
    result = pilot4_report.build(data, runs, corpus)
    assert result["rates"]["strict"]["pilot_success_rate"] == {"count": 1, "of": 3, "rate": 0.333}
    assert result["rates"]["corrected"]["pilot_success_rate"] == {"count": 2, "of": 3, "rate": 0.667}
    assert all(result["rates"][k]["pilot_success_rate"]["of"] == 3 for k in ("strict", "corrected"))


def test_each_paper_keeps_its_first_attempt_its_category_and_its_corrections(world):
    data, runs, corpus = world
    rows = {p["paper_id"]: p for p in pilot4_report.build(data, runs, corpus)["papers"]}
    assert rows["paper_101"]["correction_round"] is False and rows["paper_101"]["strict"]["pilot_success"] is True
    assert rows["paper_102"]["strict"]["category"] == "MISSING_DEPENDENCY" and rows["paper_102"]["corrected"]["pilot_success"]
    assert rows["paper_102"]["corrections"][0]["change"] == "add numpy"
    assert rows["paper_103"]["strict"]["category"] == "MISSING_DEPENDENCY"
    assert rows["paper_103"]["corrected"]["category"] == "OTHER" and rows["paper_103"]["corrected"]["deciding_line"].startswith("OSError")


def test_a_paper_without_a_record_counts_in_the_denominator(world):
    data, runs, corpus = world
    corpus_list = json.loads(corpus.read_text(encoding="utf-8")) + [
        {"paper_id": "paper_104", "title": "T4", "repo_url": "https://github.com/o/r4", "run_command": "python s4.py"}]
    corpus.write_text(json.dumps(corpus_list), encoding="utf-8")
    result = pilot4_report.build(data, runs, corpus)
    assert result["rates"]["strict"]["pilot_success_rate"]["of"] == 4 and result["rates"]["strict"]["pilot_success_rate"]["count"] == 1


def test_the_markdown_has_the_four_pilots_side_by_side_and_every_correction(world):
    data, runs, corpus = world
    table = pilot4_report.to_markdown(pilot4_report.build(data, runs, corpus))
    assert "| Pilot success | 1 / 6 (0.167) | 1 / 6 (0.167) | 1 / 6 (0.167) | 1 / 3 (0.333) | 2 / 3 (0.667) |" in table
    assert "add numpy" in table and "`python s1.py --x 1`" in table and "no correction round" in table


def test_the_first_attempt_directory_is_not_modified(world):
    data, runs, corpus = world
    before = sorted(p.name for p in (runs / "first_attempts").iterdir())
    pilot4_report.build(data, runs, corpus)
    assert sorted(p.name for p in (runs / "first_attempts").iterdir()) == before
