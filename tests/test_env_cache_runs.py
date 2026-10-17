"""The table of the installed-environment cache runs is read from stored records (#380)."""

import json

from scripts import env_cache_runs as ecr


def write_run(root, rel, *, cache=None, install=100.0, run=500.0, total=620.0, bundle=30.0, metrics=None, started="2026-10-17T10:00:00+00:00",
              finished="2026-10-17T10:12:00+00:00", exit_code=0):
    folder = root / rel
    folder.mkdir(parents=True)
    record = {"paper_id": "paper_003", "started_at": started, "finished_at": finished, "sandbox_duration_seconds": total,
              "limits": {"cpus": 2.0, "memory_limit": "14265m"}, "bundle": {"duration_seconds": bundle},
              "run": {"status": "COMPLETED", "exit_code": exit_code, "duration_seconds": run, "dependency_install_status": "INSTALLED"},
              "install_meta": {"status": "INSTALLED", "duration_seconds": install}}
    if cache is not None:
        record["env_cache"] = cache
    (folder / "pilot_record.json").write_text(json.dumps(record), encoding="utf-8")
    (folder / "run_report.json").write_text(json.dumps({"metrics": metrics or {"rmse": 0.46}}), encoding="utf-8")


def build(tmp_path, hit_metrics=None):
    write_run(tmp_path, "memory_runs/paper_003", install=1000.0, total=2500.0, finished="2026-10-17T10:45:00+00:00")
    write_run(tmp_path, "env_cache_runs/first_run/paper_003", cache={"enabled": True, "hit": False, "stored": {"store_seconds": 40.0}},
              install=1010.0, total=2510.0, finished="2026-10-17T10:46:00+00:00")
    write_run(tmp_path, "env_cache_runs/second_run/paper_003", cache={"enabled": True, "hit": True, "verify_seconds": 12.0},
              install=25.0, total=1520.0, finished="2026-10-17T10:30:00+00:00", metrics=hit_metrics)


def test_the_second_run_is_compared_with_the_runs_without_the_cache(tmp_path):
    build(tmp_path)
    result = ecr.measure(tmp_path)
    assert [r["cache"] for r in result["runs"]] == ["off", "miss", "hit"]
    (gain,) = result["gains_of_the_second_run"]
    assert gain["install_seconds_saved"] == 975.0 and gain["sandbox_seconds_saved"] == 980.0 and gain["wall_seconds_saved"] == 900.0
    assert result["same_status_and_exit_code"] is True and result["same_metrics"] is True
    text = ecr.markdown(result)
    assert "with cache, second run (hit)" in text and "975.0" in text and "Same metrics in all 3 runs: **yes**" in text


def test_different_metrics_are_reported_as_different(tmp_path):
    build(tmp_path, hit_metrics={"rmse": 0.50})
    result = ecr.measure(tmp_path)
    assert result["same_metrics"] is False
    assert "Same metrics in all 3 runs: **no**" in ecr.markdown(result)


def test_without_a_hit_run_nothing_is_claimed(tmp_path):
    write_run(tmp_path, "memory_runs/paper_003")
    assert "gains_of_the_second_run" not in ecr.measure(tmp_path)
    assert "No run with a cache hit is stored yet" in ecr.markdown(ecr.measure(tmp_path))


def test_the_block_replaces_only_the_generated_part():
    text = f"before\n{ecr.START}\nold\n{ecr.END}\nafter\n"
    new = ecr.apply_block(text, f"{ecr.START}\nnew\n{ecr.END}")
    assert new == f"before\n{ecr.START}\nnew\n{ecr.END}\nafter\n"
