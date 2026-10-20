"""The stored real seed runs (#48, docs/MULTI_SEED.md): the summary equals what the stored folders give."""

import json
import shutil
from pathlib import Path

import pytest

from scripts import run_multi_seed
from src.multi_seed import load_seed_settings

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "data" / "multi_seed_runs"
PAPERS = sorted(p.name for p in ROOT.iterdir() if p.is_dir()) if ROOT.is_dir() else []

pytestmark = pytest.mark.skipif(not PAPERS, reason="no real seed run is stored")


def summary_of(paper):
    return json.loads((ROOT / paper / "multi_seed_summary.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("paper", PAPERS)
def test_the_stored_summary_equals_a_fresh_summary_of_the_stored_folders(paper, tmp_path):
    copy = tmp_path / paper
    shutil.copytree(ROOT / paper, copy)
    spec = load_seed_settings()[paper]["seed"]
    fresh = run_multi_seed.summarize_stored(paper, copy, spec, run_multi_seed.stored_seeds(copy))
    stored = summary_of(paper)
    for key in ("successful_seed_runs", "metrics", "tier3", "tier3_by_metric", "seed_spec", "limits"):
        assert fresh[key] == stored[key], key
    assert [r["metrics"] for r in fresh["runs"]] == [r["metrics"] for r in stored["runs"]]


@pytest.mark.parametrize("paper", PAPERS)
def test_every_seed_folder_is_a_record_that_names_its_seed_and_says_it_is_not_a_protocol_run(paper):
    spec = load_seed_settings()[paper]["seed"]
    folders = sorted(p for p in (ROOT / paper).glob("seed_*") if p.is_dir())
    assert [int(p.name.split("_")[1]) for p in folders] == sorted(spec["values"])
    for folder in folders:
        record = json.loads((folder / "pilot_record.json").read_text(encoding="utf-8"))
        assert record["multi_seed"]["seed"] == int(folder.name.split("_")[1])
        assert "not a protocol run" in record["multi_seed"]["note"]
        assert record["limits"]["cpus"] == 4.0 and record["cpus_override"]["requested"] == 4.0
        assert record["run"]["docker_used"] is True and record["run"]["isolated"] is True


@pytest.mark.parametrize("paper", PAPERS)
def test_the_summary_values_are_the_metrics_of_the_run_reports(paper):
    stored = summary_of(paper)
    for run in stored["runs"]:
        report = json.loads((ROOT / paper / f"seed_{run['seed']}" / "run_report.json").read_text(encoding="utf-8"))
        assert run["metrics"] == {k: float(v) for k, v in report["metrics"].items()}
    for name, metric in stored["metrics"].items():
        by_seed = {r["seed"]: r["metrics"][name] for r in stored["runs"] if r["used"]}
        assert metric["values"] == [by_seed[s] for s in metric["seeds"]]


@pytest.mark.parametrize("paper", PAPERS)
def test_the_tier3_score_is_that_of_the_deciding_metric_and_the_per_metric_table_is_consistent(paper):
    stored = summary_of(paper)
    decided = stored["tier3"]["decided_by"]
    by_metric = stored["tier3_by_metric"]
    assert by_metric[decided]["cv"] == max(m["cv"] for m in by_metric.values())
    assert stored["tier3"]["score"] == by_metric[decided]["score_if_this_metric_alone"]
    assert stored["tier3"]["score"] == min(m["score_if_this_metric_alone"] for m in by_metric.values())


@pytest.mark.parametrize("paper", PAPERS)
def test_the_stored_folders_carry_no_local_path(paper):
    for path in (ROOT / paper).rglob("*"):
        if path.is_file():
            assert "Users" not in path.read_text(encoding="utf-8", errors="replace"), path


def test_seed_0_of_paper_003_gives_the_metrics_of_the_earlier_single_runs():
    if "paper_003" not in PAPERS:
        pytest.skip("paper_003 seed runs are not stored")
    earlier = json.loads((REPO / "data" / "cpu_runs" / "paper_003" / "run_report.json").read_text(encoding="utf-8"))["metrics"]
    seed_0 = json.loads((ROOT / "paper_003" / "seed_0" / "run_report.json").read_text(encoding="utf-8"))["metrics"]
    assert seed_0 == earlier  # the config file 0.toml is the one every earlier run used
