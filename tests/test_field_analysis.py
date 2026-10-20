"""The week 6 field analysis (#413, docs/FIELD_ANALYSIS.md): every number comes from stored files."""

import json
from pathlib import Path

import pytest

import scripts.field_analysis as fa

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"


def test_the_pool_is_the_12_papers_and_the_corpora_agree():
    seed_ids = [e["paper_id"] for e in json.loads((DATA / "seed_papers.json").read_text(encoding="utf-8"))]
    expansion_ids = [e["paper_id"] for e in json.loads((DATA / "corpus_expansion" / "papers.json").read_text(encoding="utf-8"))]
    assert sorted(fa.SEED_IDS) == sorted(seed_ids) and sorted(fa.EXPANSION_IDS) == sorted(expansion_ids)
    assert len(fa.POOL) == 12


def test_rates_equal_a_direct_recount_of_the_measurement_files():
    runs = fa.reference_runs()
    rates = fa.rates(runs)
    pilot1 = json.loads((DATA / "pilot_runs" / "measurements.json").read_text(encoding="utf-8"))["papers"]
    assert rates["seed papers"]["first"]["pilot_success"]["k"] == sum(p["pilot_success"] for p in pilot1)
    pilot3 = json.loads((DATA / "pilot3_runs" / "measurements.json").read_text(encoding="utf-8"))["papers"]
    assert rates["seed papers"]["final"]["install_success"]["k"] == sum(p["install_success"] for p in pilot3)
    strict = json.loads((DATA / "pilot4_runs" / "summary.json").read_text(encoding="utf-8"))["papers"]
    assert rates["expansion papers"]["first"]["run_success"]["k"] == sum(p["strict"]["run_success"] for p in strict)
    total = rates["all 12 papers"]["final"]["pilot_success"]
    assert total["n"] == 12 and total["k"] == (rates["seed papers"]["final"]["pilot_success"]["k"]
                                                + rates["expansion papers"]["final"]["pilot_success"]["k"])


def test_every_seed_paper_has_i1_and_no_expansion_paper_does():
    flags = fa.interventions()
    assert all(flags[p]["I1_command_or_setup_by_a_person"] for p in fa.SEED_IDS)
    assert not any(flags[p]["I1_command_or_setup_by_a_person"] for p in fa.EXPANSION_IDS)


def test_interventions_come_from_the_stored_files():
    flags = fa.interventions()
    assert flags["paper_106"]["I2_correction_or_setting_after_a_failure"] and flags["paper_106"]["I3_tool_change_for_this_paper"]
    assert flags["paper_003"]["I2_correction_or_setting_after_a_failure"] and not flags["paper_003"]["I3_tool_change_for_this_paper"]
    assert flags["paper_005"]["I3_tool_change_for_this_paper"]
    assert flags["paper_006"]["I4_claim_accepted_by_a_person"] and not flags["paper_102"]["I4_claim_accepted_by_a_person"]


def test_autonomy_counts_i1_for_the_first_run_and_i1_to_i3_for_the_final_run():
    runs = {p: {w: {"pilot_success": True} for w in ("first", "final")} for p in fa.POOL}
    base = {"I1_command_or_setup_by_a_person": False, "I2_correction_or_setting_after_a_failure": False,
            "I3_tool_change_for_this_paper": False, "I4_claim_accepted_by_a_person": True}
    flags = {p: dict(base) for p in fa.POOL}
    flags["paper_101"]["I2_correction_or_setting_after_a_failure"] = True
    flags["paper_102"]["I1_command_or_setup_by_a_person"] = True
    result = fa.autonomy(runs, flags)["expansion papers"]
    assert result["first"]["concluded_autonomously"]["k"] == 5  # only I1 counts for the first run
    assert result["final"]["concluded_autonomously"]["k"] == 4  # I2 counts for the final run
    assert result["final"]["succeeded_autonomously"]["k"] == 4


def test_a_failed_run_is_concluded_but_not_succeeded():
    runs = {p: {w: {"pilot_success": False} for w in ("first", "final")} for p in fa.POOL}
    flags = {p: {"I1_command_or_setup_by_a_person": False, "I2_correction_or_setting_after_a_failure": False,
                 "I3_tool_change_for_this_paper": False, "I4_claim_accepted_by_a_person": False} for p in fa.POOL}
    result = fa.autonomy(runs, flags)["all 12 papers"]["final"]
    assert result["concluded_autonomously"]["k"] == 12 and result["succeeded_autonomously"]["k"] == 0


def test_i4_is_not_part_of_the_rate():
    result = fa.compute()["autonomy"]
    assert result["seed papers"]["papers_with_an_accepted_claim_I4"]["k"] == 6
    assert result["expansion papers"]["final"]["concluded_autonomously"]["k"] >= 1  # a pool with 0 accepted claims still has a rate


@pytest.mark.parametrize("text, expected", [
    ("# T\npip install -r requirements.txt\n```bash\npython train.py\n```\nDownload the data first.",
     {"installation_instruction": True, "run_command_in_code_block": True, "data_described": True}),
    ("# T\nA paper.\n", {"installation_instruction": False, "run_command_in_code_block": False, "data_described": False}),
    ("python train.py outside a code block, data only\n",
     {"installation_instruction": False, "run_command_in_code_block": False, "data_described": False}),
    ("```\n$ make train\n```", {"installation_instruction": False, "run_command_in_code_block": True, "data_described": False}),
])
def test_readme_checks(text, expected):
    got = fa.readme_checks(text)
    assert got["readme_exists"] is True
    assert {k: got[k] for k in expected} == expected


def test_requirement_count_skips_comments_and_options_and_counts_conda_entries(tmp_path):
    (tmp_path / "requirements.txt").write_text("# c\n\nnumpy==1.0\n-r other.txt\n--index-url x\ntorch\n", encoding="utf-8")
    (tmp_path / "environment.yml").write_text("name: e\ndependencies:\n  - python=3.8\n  - numpy\n  - pip:\n    - a\n    - b\n",
                                              encoding="utf-8")
    total, detail = fa.requirement_count(tmp_path, ["requirements.txt"])
    assert total == 2 + 4
    assert {d["file"]: d["entries"] for d in detail} == {"requirements.txt": 2, "environment.yml": 4}


def test_the_stored_features_cover_the_pool_and_name_the_readme_hash():
    features = json.loads(fa.FEATURES_PATH.read_text(encoding="utf-8"))["papers"]
    assert sorted(features) == sorted(fa.POOL)
    for pid, f in features.items():
        assert len(f["readme_sha256"]) == 64 and f["F1_documentation_quality"] == sum(f["readme_checks"].values()), pid
        assert f["pinned_commit"] and f["F2_code_age_years"] >= 0


def test_the_factor_table_has_no_test_of_significance():
    text = fa.render(fa.compute())
    assert "not a test" in text and "no relationship is claimed" in text
    for forbidden in ("p-value", "p =", "significant at", "correlation coefficient"):
        assert forbidden not in text


def test_the_stored_result_and_the_generated_document_match_the_records():
    assert fa.main(["--check"]) == 0
