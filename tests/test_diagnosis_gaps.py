"""The six gaps of the failure classifier that docs/DIAGNOSIS_VALIDATION.md listed (#424), one case per log line."""

import pytest

from src.diagnosis.classifier import classify_exception, classify_log_text

CASES = [
    # the real line of the validation run R41 (a stored first attempt of paper_006)
    ("PermissionError: [Errno 13] Permission denied: '/workspace/home/.openml/config'", "OTHER", "PERMISSION_DENIED"),
    ("RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB (GPU 0; 8.00 GiB total capacity)", "OTHER", "GPU_OUT_OF_MEMORY"),
    ("OSError: [Errno 28] No space left on device", "OTHER", "NO_SPACE_LEFT"),
    ("urllib.error.HTTPError: HTTP Error 404: Not Found", "DATA_NOT_ACCESSIBLE", None),
    ("ConnectionRefusedError: [Errno 111] Connection refused", "DATA_NOT_ACCESSIBLE", None),
    ("FileNotFoundError: [Errno 2] No such file or directory: 'checkpoints/pretrained.pt'", "DATA_NOT_ACCESSIBLE", None),
]


@pytest.mark.parametrize("line,category,name", CASES)
def test_each_gap_is_closed(line, category, name):
    assert classify_exception(line) == (category, name)


@pytest.mark.parametrize("line,category,name", CASES)
def test_the_last_line_of_a_traceback_decides(line, category, name):
    text = f"Traceback (most recent call last):\n  File \"train.py\", line 3, in <module>\n{line}\n"
    assert classify_log_text(text)[:2] == (category, name)


@pytest.mark.parametrize("line,expected", [
    ("RuntimeError: CUDA error: no kernel image is available for execution on the device", ("HARDWARE_GPU_REQUIRED", None)),
    ("AssertionError: Torch not compiled with CUDA enabled", ("HARDWARE_GPU_REQUIRED", None)),
    ("FileNotFoundError: [Errno 2] No such file or directory: 'config/model.yaml'", ("OTHER", "MISSING_FILE")),
    ("OSError: [Errno 30] Read-only file system: '/workspace/repo/out.txt'", ("OTHER", "WRITE_TO_READ_ONLY_REPOSITORY")),
    ("ValueError: could not convert string to float: 'abc'", ("OTHER", None)),
    ("ModuleNotFoundError: No module named 'numpy'", ("MISSING_DEPENDENCY", None)),
])
def test_the_new_rules_leave_other_lines_as_they_were(line, expected):
    assert classify_exception(line) == expected
