"""Diagnosis input schema and prompt templates (#31, docs/DIAGNOSIS.md)."""

import json
from pathlib import Path

import pytest

from src.config import STATUS_FAILED, STATUS_VERIFIED
from src.diagnosis import load_diagnosis_input
from src.diagnosis.prompts import (
    LOADED_WORDS,
    PROMPTS_DIR,
    TASK_FILES,
    check_neutral_language,
    fill,
    numbers_in,
    render_prompt,
)
from src.diagnosis.schema import FIELD_SOURCES, log_tail

REPO = Path(__file__).resolve().parent.parent


def make_run(tmp_path, record=None, report=None, stderr=None):
    if record is not None:
        (tmp_path / "pilot_record.json").write_text(json.dumps(record), encoding="utf-8")
    if report is not None:
        (tmp_path / "run_report.json").write_text(json.dumps(report), encoding="utf-8")
    if stderr is not None:
        (tmp_path / "stderr.log").write_text(stderr, encoding="utf-8")
    return tmp_path


def test_fields_are_read_from_their_documented_place(tmp_path):
    record = {"paper_id": "p", "protocol": "docs/PILOT_3.md", "limits": {"cpus": 2.0, "memory_limit": "6g"},
              "stage": {"status": "STAGED"}}
    report = {"status": "COMPLETED", "exit_code": 0, "duration_seconds": 12.5, "dependency_install_status": "INSTALLED",
              "meta": {"peak_memory_bytes": 100, "timeout_limit_seconds": 3600}, "metrics": {"acc": 0.9}}
    got = load_diagnosis_input(make_run(tmp_path, record, report))
    assert (got.paper_id, got.run_status, got.exit_code, got.cpus, got.memory_limit) == ("p", "COMPLETED", 0, 2.0, "6g")
    assert got.metrics == {"acc": 0.9}
    assert got.sources["run_status"] == "run_report.json: status"
    assert got.sources["cpus"] == "pilot_record.json: limits.cpus"


def test_a_missing_value_stays_unknown_and_says_so(tmp_path):
    got = load_diagnosis_input(make_run(tmp_path, {"paper_id": "p"}, {}))
    assert got.peak_memory_bytes is None and got.metrics is None and got.gpu_requested is None
    assert "peak_memory_bytes" not in got.sources
    assert got.source_of("peak_memory_bytes").endswith("(not present)")
    assert not got.source_of("paper_id").endswith("(not present)")


def test_the_pilot_record_is_the_fallback_when_there_is_no_run_report(tmp_path):
    record = {"paper_id": "p", "run": {"status": "FAILED", "exit_code": 1, "duration_seconds": 3.0,
                                       "dependency_install_status": "FAILED", "peak_memory_bytes": 5}}
    got = load_diagnosis_input(make_run(tmp_path, record))
    assert (got.run_status, got.exit_code, got.install_status) == ("FAILED", 1, "FAILED")
    assert got.sources["run_status"] == "pilot_record.json: run.status"


def test_an_empty_or_broken_folder_gives_all_unknown(tmp_path):
    (tmp_path / "pilot_record.json").write_text("{not json", encoding="utf-8")
    got = load_diagnosis_input(tmp_path)
    assert got.paper_id is None and got.sources == {}


def test_a_folder_that_does_not_exist_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_diagnosis_input(tmp_path / "nope")


def test_log_tail_keeps_real_line_numbers_and_drops_color_codes(tmp_path):
    (tmp_path / "stderr.log").write_text("a\n\n\x1b[31mred\x1b[0m\nlast\n", encoding="utf-8")
    tail = log_tail(tmp_path / "stderr.log", count=2)
    assert [(t.line_number, t.text) for t in tail] == [(3, "red"), (4, "last")]
    assert log_tail(tmp_path / "missing.log") == []


def test_metrics_keep_numbers_only(tmp_path):
    got = load_diagnosis_input(make_run(tmp_path, {}, {"metrics": {"acc": 0.5, "name": "x", "flag": True}}))
    assert got.metrics == {"acc": 0.5}


def test_every_stored_field_has_a_source_and_loads_from_a_real_run():
    assert all(isinstance(v, tuple) and len(v) == 2 for v in FIELD_SOURCES.values())
    run = REPO / "data" / "cpu_runs" / "paper_003"
    got = load_diagnosis_input(run)
    assert got.paper_id == "paper_003" and got.run_status == "COMPLETED" and got.cpus == 8.0
    assert got.cpus_override is not None and got.stderr_tail is not None


# ---------------------------------------------------------------- prompts


def test_every_status_has_a_template_file():
    assert set(TASK_FILES) >= {STATUS_VERIFIED, STATUS_FAILED}
    for name in [*TASK_FILES.values(), "system.md"]:
        assert (PROMPTS_DIR / name).is_file()


def test_templates_use_only_known_placeholders_and_are_neutral():
    for name in [*TASK_FILES.values(), "system.md"]:
        text = (PROMPTS_DIR / name).read_text(encoding="utf-8")
        assert set(__import__("re").findall(r"\{\{(\w+)\}\}", text)) <= {
            "rule_based_report", "quoted_log_lines", "locked_numbers"}
        # the system prompt names the loaded words it forbids, so it is the one file allowed to contain them
        if name != "system.md":
            assert check_neutral_language(text) == []


def test_render_prompt_locks_the_numbers_of_the_report():
    system, task = render_prompt(STATUS_VERIFIED, "The run took 12.5 s and reproduced 0.9 of 0.91.")
    assert "12.5, 0.9, 0.91" in system
    assert "reproduced 0.9 of 0.91" in task
    assert "{{" not in system + task


def test_failed_prompt_includes_the_quoted_lines():
    _, task = render_prompt(STATUS_FAILED, "report", quoted_log_lines="stderr.log:4: ModuleNotFoundError")
    assert "stderr.log:4: ModuleNotFoundError" in task


def test_render_prompt_refuses_an_unknown_status():
    with pytest.raises(ValueError):
        render_prompt("Great", "x")


def test_fill_refuses_a_placeholder_without_a_value():
    with pytest.raises(ValueError):
        fill("{{a}} {{b}}", {"a": "1"})


def test_numbers_in_keeps_order_and_drops_repeats():
    assert numbers_in("0.9 then 12 and 0.9, 3.5e-3, 40%") == ["0.9", "12", "3.5e-3", "40%"]


def test_neutral_language_check_flags_loaded_words_only_as_whole_words():
    assert check_neutral_language("The authors were careless and the numbers fake.") == ["careless", "fake"]
    assert check_neutral_language("A relief for the believer, a fakery-free table") == []
    assert all(w == w.lower() for w in LOADED_WORDS)
