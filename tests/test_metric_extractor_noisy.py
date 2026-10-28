"""Metric extraction from noisy console logs: ANSI color codes, progress bars, line endings, odd values (#30, #557)."""

import pytest

from src.metric_extractor import MetricExtractor

ESC = "\x1b"


@pytest.fixture()
def extractor() -> MetricExtractor:
    return MetricExtractor()


@pytest.mark.parametrize(
    "text,expected",
    [
        (f"{ESC}[32maccuracy: 0.85{ESC}[0m\n", {"accuracy": 0.85}),
        (f"{ESC}[1;32mtest rmse = 0.473{ESC}[0m\n", {"rmse": 0.473}),
        (f"{ESC}[0maccuracy{ESC}[0m: 0.85", {"accuracy": 0.85}),
        (f"{ESC}]0;window title\x07F1: 0.7\n", {"f1": 0.7}),
        (f"{ESC}[2K\rEpoch 3 | loss: 0.5 | val_acc: 0.91\n", {"loss": 0.5, "accuracy": 0.91}),
        (f"{ESC}[38;5;208mAUROC{ESC}[0m = {ESC}[1m93.3{ESC}[0m\n", {"auroc": 0.933}),
    ],
)
def test_ansi_escape_codes_do_not_enter_a_metric_name(extractor, text, expected):
    """Before the fix `ESC[32maccuracy: 0.85` was extracted as the metric `32maccuracy`, which no claim can match."""
    assert extractor.extract_metrics(text) == expected


def test_a_log_with_and_without_color_gives_the_same_metrics(extractor):
    plain = "Epoch 1\nloss: 0.5\nTest accuracy: 0.81\nTest auroc: 0.9\n"
    colored = "".join(f"{ESC}[36m{line}{ESC}[0m\n" for line in plain.splitlines())
    assert extractor.extract_metrics(colored) == extractor.extract_metrics(plain)


def test_progress_bar_lines_do_not_hide_the_final_metric(extractor):
    text = (
        "Epoch 1/3: 100%|##########| 10/10 [00:01<00:00,  9.90it/s]\r"
        "Epoch 2/3: 100%|##########| 10/10 [00:01<00:00,  9.90it/s]\n"
        "F1: 0.7\n"
    )
    assert extractor.extract_metrics(text) == {"f1": 0.7}


def test_later_occurrence_wins_and_line_endings_do_not_matter(extractor):
    assert extractor.extract_metrics("accuracy: 0.8\r\naccuracy: 0.9\r\n") == {"accuracy": 0.9}
    assert extractor.extract_metrics("accuracy: 0.8\naccuracy: 0.9\n") == {"accuracy": 0.9}


@pytest.mark.parametrize("text", ["", "   \n\n", "no numbers here", "\x00\x00\x00", "accuracy:", "accuracy: abc"])
def test_empty_and_meaningless_text_gives_no_metrics(extractor, text):
    assert extractor.extract_metrics(text) == {}


def test_nul_bytes_between_text_do_not_break_extraction(extractor):
    assert extractor.extract_metrics("\x00\x00accuracy: 0.8\x00\n") == {"accuracy": 0.8}


@pytest.mark.parametrize("text", ["accuracy: nan\n", "accuracy: inf\n", "accuracy: -inf\n"])
def test_non_finite_values_in_a_log_line_are_not_metrics(extractor, text):
    assert extractor.extract_metrics(text) == {}


def test_negative_and_huge_values_are_kept_as_they_are(extractor):
    assert extractor.extract_metrics("accuracy: -0.5\n") == {"accuracy": -0.5}
    assert extractor.extract_metrics("accuracy: 99999999999999999999\n") == {"accuracy": 1e20}


def test_percent_is_converted_to_a_fraction_for_bounded_metrics(extractor):
    assert extractor.extract_metrics("accuracy: 85%\n") == {"accuracy": 0.85}
    assert extractor.extract_metrics("AUROC = 93.3\n") == {"auroc": 0.933}


def test_unicode_names_and_text_do_not_crash_and_do_not_invent_metrics(extractor):
    assert extractor.extract_metrics("précision: 0.8\n准确率: 0.9\naccuracy: 0.7\n") == {"accuracy": 0.7}


def test_name_case_and_json_and_python_dict_forms(extractor):
    assert extractor.extract_metrics("ACCURACY: 0.85\n") == {"accuracy": 0.85}
    assert extractor.extract_metrics('{"accuracy": 0.9, "auroc": 0.8}\n') == {"accuracy": 0.9, "auroc": 0.8}
    assert extractor.extract_metrics("metrics = {'accuracy': 0.85, 'auroc': 0.9}\n") == {"accuracy": 0.85, "auroc": 0.9}


def test_broken_json_falls_back_to_the_line_patterns(extractor):
    assert extractor.extract_metrics("{broken json accuracy: 0.8\n") == {"accuracy": 0.8}


def test_run_directory_with_colored_stdout_and_a_bad_results_file(tmp_path, extractor):
    (tmp_path / "stdout.log").write_text(f"{ESC}[32mTest accuracy: 0.81{ESC}[0m\n", encoding="utf-8")
    (tmp_path / "results.json").write_text("{not json", encoding="utf-8")
    assert extractor.extract_from_run_dir(tmp_path) == {"accuracy": 0.81}
    assert (tmp_path / "extracted_metrics.json").exists()


def test_missing_run_directory_is_an_error(tmp_path, extractor):
    with pytest.raises(FileNotFoundError):
        extractor.extract_from_run_dir(tmp_path / "missing")
