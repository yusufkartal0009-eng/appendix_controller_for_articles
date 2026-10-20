"""The synthetic GPU paper (#169): the checks it makes, judged from the container's own output and the run report."""

import json
from pathlib import Path

from scripts import gpu_paper_check as g

REPO = Path(__file__).resolve().parent.parent
GOOD_REPORT = {"status": "COMPLETED", "exit_code": 0, "isolated": True, "docker_used": True,
               "gpu": {"requested": "all", "available": True, "used": True, "devices": [{"name": "GPU"}]}}
GOOD_OUTPUT = {"cuda_available": "True", "tensor_device": "cuda:0", "matmul_matches_cpu": "True"}


def test_parse_output_reads_key_value_lines_only():
    text = "torch_version: 2.8.0+cu128\nsome noise without a colon\ntensor_device: cuda:0\nmatmul_matches_cpu: True\n"
    assert g.parse_output(text) == {"torch_version": "2.8.0+cu128", "tensor_device": "cuda:0", "matmul_matches_cpu": "True"}


def test_a_full_pass_needs_every_fact():
    assert all(g.judge(GOOD_REPORT, GOOD_OUTPUT).values())
    for broken_output in ({**GOOD_OUTPUT, "tensor_device": "cpu"}, {**GOOD_OUTPUT, "matmul_matches_cpu": "False"},
                          {**GOOD_OUTPUT, "cuda_available": "False"}):
        assert not all(g.judge(GOOD_REPORT, broken_output).values())
    no_gpu = {**GOOD_REPORT, "gpu": {"requested": "all", "available": False, "used": None}}
    checks = g.judge(no_gpu, GOOD_OUTPUT)
    assert not checks["gpu_visible_in_container"] and not checks["report_gpu_used"]
    assert not g.judge({**GOOD_REPORT, "exit_code": 1}, GOOD_OUTPUT)["run_completed_exit_0"]


def test_the_synthetic_paper_asks_for_a_modern_torch_and_the_gpu():
    assert g.TORCH_REQUIREMENT == "torch==2.8.0"
    assert "torch.cuda.is_available()" in g.TRAIN_PY and 'to("cuda")' in g.TRAIN_PY and "torch.equal(result.cpu(), expected)" in g.TRAIN_PY


def test_the_stored_result_is_a_complete_pass_with_the_isolation_intact():
    result = json.loads((REPO / "data" / "gpu_check" / "result.json").read_text(encoding="utf-8"))
    assert result["all_checks_pass"] is True and all(result["checks"].values())
    out = result["container_output"]
    assert out["tensor_device"].startswith("cuda") and out["torch_cuda_version"] == "12.8" and "sm_120" in out["arch_list"]
    gpu = result["gpu_block_of_run_report"]
    assert gpu["used"] is True and gpu["peak_memory_used_mib"] > gpu["devices"][0]["memory_used_before_mib"]
    assert result["run"]["docker_used"] is True and result["run"]["isolated"] is True
    assert "not a protocol run" in result["gpus_override"]["note"] and "synthetic" in result["note"]


def test_the_stored_record_has_no_local_user_path():
    for path in (REPO / "data" / "gpu_check").rglob("*"):
        if path.is_file() and path.suffix in {".json", ".log", ".txt"}:
            assert "Users" not in path.read_text(encoding="utf-8", errors="replace").replace("Users/runner", ""), path
