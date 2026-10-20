"""Multi-seed execution (#48, docs/MULTI_SEED.md): the seed spec, the summary, and Tier 3 from real seed results."""

import json
import math
import random

import pytest

from src.multi_seed import (
    apply_seed,
    load_seed_settings,
    seed_spec_of,
    summarize_seed_runs,
    validate_seed_spec,
)
from src.score_run import score_run
from src.scoring import (
    ReproducibilityScorer,
    Tier3StabilityEvaluator,
    coefficient_of_variation,
)

ENTRY = {
    "paper_id": "p",
    "run_setup": {"decision": "fix", "reason": "r", "args": ["--x", "1"], "env": {"A": "s{seed}"}},
}


def spec(**overrides):
    return {"values": [1, 2, 3], "arg": "--set_seed", "source": "train.py line 36", **overrides}


# ---------------------------------------------------------------- the spec


def test_apply_seed_appends_the_seed_option_and_leaves_the_entry_alone():
    out = apply_seed(ENTRY, spec(), 2)
    assert out["run_setup"]["args"] == ["--x", "1", "--set_seed", "2"]
    assert ENTRY["run_setup"]["args"] == ["--x", "1"]


def test_apply_seed_replaces_the_placeholder_in_args_and_env():
    template = {"values": [0, 1], "args": ["conf/{seed}.toml", "-o", "out_{seed}"], "source": "repo config files"}
    out = apply_seed(ENTRY, template, 1)
    assert out["run_setup"]["args"] == ["conf/1.toml", "-o", "out_1"]
    assert out["run_setup"]["env"] == {"A": "s1"}


@pytest.mark.parametrize("bad", [
    {"values": [1], "arg": "--s", "source": "x"},                     # fewer than two seeds
    {"values": [1, 1], "arg": "--s", "source": "x"},                  # not distinct
    {"values": [1, True], "arg": "--s", "source": "x"},               # a bool is not a seed
    {"values": [1, 2], "arg": "--s"},                                 # no source
    {"values": [1, 2], "source": "x"},                                # no way to pass the seed
    {"values": [1, 2], "arg": "set_seed", "source": "x"},             # an option starts with a dash
    {"values": [1, 2], "args": ["no placeholder"], "source": "x"},    # args without {seed}
    {"values": [1, 2], "arg": "--s", "args": ["{seed}"], "source": "x"},  # both ways at once
])
def test_validate_seed_spec_refuses_a_malformed_spec(bad):
    with pytest.raises(ValueError):
        validate_seed_spec("p", bad)


def test_seed_spec_of_prefers_the_settings_file_and_falls_back_to_the_run_setup(tmp_path):
    settings = tmp_path / "s.json"
    settings.write_text(json.dumps({"papers": {"p": {"seed": spec()}}}), encoding="utf-8")
    assert seed_spec_of(ENTRY, load_seed_settings(settings))["arg"] == "--set_seed"
    inside = {**ENTRY, "run_setup": {**ENTRY["run_setup"], "seed": spec(values=[7, 8])}}
    assert seed_spec_of(inside, {})["values"] == [7, 8]
    assert seed_spec_of(ENTRY, {}) is None


# ---------------------------------------------------------------- the summary


def test_summary_mean_std_cv_match_a_hand_calculation():
    runs = {1: {"acc": 0.8}, 2: {"acc": 0.9}, 3: {"acc": 1.0}}
    metrics = summarize_seed_runs(runs)
    acc = metrics["acc"]
    assert acc["values"] == [0.8, 0.9, 1.0]
    assert acc["mean"] == pytest.approx(0.9)
    assert acc["std_population"] == pytest.approx(math.sqrt(0.02 / 3))
    assert acc["std_sample"] == pytest.approx(math.sqrt(0.02 / 2))
    assert acc["cv"] == pytest.approx(math.sqrt(0.02 / 3) / 0.9)


def test_summary_keeps_only_metrics_found_in_every_seed_run():
    metrics = summarize_seed_runs({1: {"acc": 0.8, "loss": 1.0}, 2: {"acc": 0.8}})
    assert set(metrics) == {"acc"}


def test_coefficient_of_variation_matches_the_tier3_formula():
    values = [0.842, 0.844, 0.841]
    mean = sum(values) / 3
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / 3)
    assert coefficient_of_variation(values) == pytest.approx(std / mean)


# ---------------------------------------------------------------- Tier 3


def test_tier3_by_metric_scores_the_least_stable_metric():
    results = {"stable": [0.9, 0.9, 0.9], "wobbly": [0.5, 0.9, 0.7]}
    score, notes = Tier3StabilityEvaluator.evaluate_by_metric(results)
    assert score == 40.0
    assert any("wobbly" in note for note in notes)


def test_tier3_by_metric_all_equal_values_is_100():
    assert Tier3StabilityEvaluator.evaluate_by_metric({"a": [0.5, 0.5, 0.5]})[0] == 100.0


def test_tier3_by_metric_without_two_values_keeps_the_single_run_baseline():
    score, notes = Tier3StabilityEvaluator.evaluate_by_metric({"a": [0.5]})
    assert score == 75.0
    assert "baseline" in notes[0]
    assert Tier3StabilityEvaluator.evaluate_by_metric(None)[0] == 75.0


def test_tier3_by_metric_is_zero_when_execution_failed():
    assert Tier3StabilityEvaluator.evaluate_by_metric({"a": [0.5, 0.5]}, execution_succeeded=False)[0] == 0.0


def test_evaluate_paper_run_uses_the_seed_metric_results():
    kwargs = {"paper_id": "p", "clone_success": True, "deps_installed": True, "script_executed": True,
              "exit_code": 0, "claimed_metrics": {"acc": 0.9}, "reproduced_metrics": {"acc": 0.9},
              "license_name": "MIT"}
    single = ReproducibilityScorer.evaluate_paper_run(**kwargs)["breakdown"]
    stable = ReproducibilityScorer.evaluate_paper_run(**kwargs, seed_metric_results={"acc": [0.9, 0.9]})["breakdown"]
    noisy = ReproducibilityScorer.evaluate_paper_run(**kwargs, seed_metric_results={"acc": [0.5, 0.9]})["breakdown"]
    assert (single.tier3_stability, stable.tier3_stability, noisy.tier3_stability) == (75.0, 100.0, 40.0)


def test_score_run_passes_the_seed_results_on(tmp_path):
    record = {"stage": {"status": "STAGED"}, "run": {"status": "COMPLETED", "exit_code": 0,
                                                       "dependency_install_status": "SKIPPED"}}
    report = {"metrics": {"acc": 0.9}, "dependency_install_status": "SKIPPED"}
    result = score_run("p", "MIT", {"acc": 0.9}, record, report, tmp_path, seed_metric_results={"acc": [0.9, 0.9]})
    assert result["breakdown"].tier3_stability == 100.0


def test_a_seeded_metric_computed_on_the_host_is_stable_across_python_processes():
    # the synthetic paper's expected values come from this: the same seed gives the same number
    assert [random.Random(s).random() for s in (1, 2)] == [random.Random(s).random() for s in (1, 2)]


# ---------------------------------------------------------------- the runner and the synthetic papers (no Docker)


def fake_run_paper(metrics_by_seed, failing=()):
    """A stand-in for run_pilot.run_paper that stores a record like the real one."""
    def run_paper(paper_id, staging_dir, record_root=None, entry_override=None, record_extra=None, **_):
        seed = int(entry_override["run_setup"]["args"][-1])
        folder = record_root / paper_id
        folder.mkdir(parents=True)
        done = seed not in failing
        record = {"paper_id": paper_id, "limits": {"cpus": 4.0}, "stage": {"status": "STAGED"}, **record_extra,
                  "run": {"status": "COMPLETED" if done else "FAILED", "exit_code": 0 if done else 1,
                          "duration_seconds": 1.0}}
        (folder / "pilot_record.json").write_text(json.dumps(record), encoding="utf-8")
        (folder / "run_report.json").write_text(json.dumps({"metrics": metrics_by_seed[seed] if done else {}}),
                                                encoding="utf-8")
        return record
    return run_paper


def test_run_seeds_stores_one_record_per_seed_and_scores_tier3(tmp_path, monkeypatch):
    from scripts import run_multi_seed

    monkeypatch.setattr(run_multi_seed.run_pilot, "run_paper",
                        fake_run_paper({1: {"acc": 0.9}, 2: {"acc": 0.9}, 3: {"acc": 0.9}}))
    summary = run_multi_seed.run_seeds(ENTRY, spec(), tmp_path, tmp_path / "staging")
    assert sorted(p.name for p in (tmp_path / "p").glob("seed_*")) == ["seed_1", "seed_2", "seed_3"]
    assert not list((tmp_path / "p").glob(".scratch*"))
    assert summary["successful_seed_runs"] == 3
    assert summary["tier3"]["score"] == 100.0
    record = json.loads((tmp_path / "p" / "seed_2" / "pilot_record.json").read_text(encoding="utf-8"))
    assert record["multi_seed"]["seed"] == 2
    assert (tmp_path / "p" / "multi_seed_summary.json").is_file()


def test_run_seeds_keeps_a_failed_seed_but_uses_only_the_successful_ones(tmp_path, monkeypatch):
    from scripts import run_multi_seed

    monkeypatch.setattr(run_multi_seed.run_pilot, "run_paper",
                        fake_run_paper({1: {"acc": 0.9}, 2: {"acc": 0.5}, 3: {"acc": 0.9}}, failing=(2,)))
    summary = run_multi_seed.run_seeds(ENTRY, spec(), tmp_path, tmp_path / "staging")
    assert summary["successful_seed_runs"] == 2
    assert [r["used"] for r in summary["runs"]] == [True, False, True]
    assert summary["metrics"]["acc"]["values"] == [0.9, 0.9]
    assert (tmp_path / "p" / "seed_2").is_dir()


def test_run_seeds_with_one_successful_seed_keeps_the_baseline(tmp_path, monkeypatch):
    from scripts import run_multi_seed

    monkeypatch.setattr(run_multi_seed.run_pilot, "run_paper",
                        fake_run_paper({1: {"acc": 0.9}}, failing=(2, 3)))
    summary = run_multi_seed.run_seeds(ENTRY, spec(), tmp_path, tmp_path / "staging")
    assert summary["tier3"]["score"] == 75.0
    assert "not a stability measurement" in summary["tier3"]["basis"]


def test_run_seeds_does_not_overwrite_a_stored_seed_run(tmp_path, monkeypatch):
    from scripts import run_multi_seed

    (tmp_path / "p" / "seed_1").mkdir(parents=True)
    monkeypatch.setattr(run_multi_seed.run_pilot, "run_paper", fake_run_paper({1: {"acc": 0.9}}))
    with pytest.raises(FileExistsError):
        run_multi_seed.run_seeds(ENTRY, spec(), tmp_path, tmp_path / "staging")


def test_synthetic_seeded_metric_is_deterministic_and_the_free_one_constant():
    from scripts import synthetic_seeds

    first = synthetic_seeds.expected_metrics("synthetic_seeded", [1, 2, 3])
    assert first == synthetic_seeds.expected_metrics("synthetic_seeded", [1, 2, 3])
    assert len({m["accuracy"] for m in first.values()}) == 3
    assert {m["accuracy"] for m in synthetic_seeds.expected_metrics("synthetic_seed_free", [1, 2, 3]).values()} == {0.9}
    assert all(0.60 <= m["accuracy"] <= 0.95 for m in first.values())


def test_synthetic_comparison_reports_a_mismatch():
    from scripts import synthetic_seeds

    seeds = [1, 2]
    wrong = {"metrics": summarize_seed_runs({1: {"accuracy": 0.9}, 2: {"accuracy": 0.8}}),
             "runs": [{"seed": 1, "metrics": {"accuracy": 0.9}}, {"seed": 2, "metrics": {"accuracy": 0.8}}]}
    assert synthetic_seeds.compare_with_expected(wrong, "synthetic_seed_free", seeds)["all_match"] is False
    right = {"metrics": summarize_seed_runs({1: {"accuracy": 0.9}, 2: {"accuracy": 0.9}}),
             "runs": [{"seed": 1, "metrics": {"accuracy": 0.9}}, {"seed": 2, "metrics": {"accuracy": 0.9}}]}
    assert synthetic_seeds.compare_with_expected(right, "synthetic_seed_free", seeds)["all_match"] is True


def test_the_seed_papers_settings_are_valid_and_pass_the_seed_to_the_paper():
    from scripts import run_pilot

    settings = load_seed_settings()
    assert set(settings) == {"paper_003", "paper_006"}
    for paper_id in settings:
        entry = run_pilot.load_entry(paper_id)
        found = seed_spec_of(entry, settings)
        applied = apply_seed(entry, found, found["values"][-1])
        assert applied["run_setup"]["args"] != entry["run_setup"]["args"]
        assert str(found["values"][-1]) in " ".join(applied["run_setup"]["args"])
        assert "seed" not in entry["run_setup"]  # data/seed_papers.json is not edited for this


def test_run_setup_refuses_a_malformed_seed_object():
    from src.sandbox.run_setup import run_setup_of

    entry = {"paper_id": "p", "run_setup": {"decision": "fix", "reason": "r", "seed": {"values": [1]}}}
    with pytest.raises(ValueError):
        run_setup_of(entry)
