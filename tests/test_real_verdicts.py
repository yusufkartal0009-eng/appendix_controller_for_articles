"""The verdicts on the real stored runs come from stored files, and the document is rendered from their record (#494)."""

import json

from scripts import real_verdicts as rv


def stored():
    return json.loads(rv.OUT_JSON.read_text(encoding="utf-8"))


def test_the_document_is_rendered_from_the_stored_verdicts():
    assert rv.OUT_DOC.read_text(encoding="utf-8") == rv.render(stored())


def test_the_stored_verdicts_are_what_the_stored_runs_give_today():
    assert rv.verdict_rows() == stored()["rows"]


def test_every_run_of_the_list_has_rows_and_a_directory_that_exists():
    rows = rv.verdict_rows()
    for _, label, rel, _ in rv.RUNS:
        assert (rv.DATA / rel / "pilot_record.json").is_file(), rel
        assert any(r["run"] == label and r["run_dir"] == f"data/{rel}" for r in rows), rel


def test_only_accepted_claims_are_used_and_the_cli_view_never_finds_a_real_claim():
    accepted = {c["query_id"] for c in rv.accepted_claims()}
    rows = [r for r in rv.verdict_rows() if r["paper_id"] in {"paper_003", "paper_004", "paper_006"}]
    assert {r["query_id"] for r in rows} <= accepted
    assert all(r["cli_tier2"] == 0.0 for r in rows)  # the keys (question IDs) never equal the extracted metric names


def test_paper_003_is_compared_with_the_same_model_only():
    rows = [r for r in rv.verdict_rows() if r["paper_id"] == "paper_003" and r["run"] == "Pilot 3"]
    by_id = {r["query_id"]: r for r in rows}
    assert by_id["ft_transformer_rmse"]["comparable"] and by_id["ft_transformer_rmse"]["reproduced"] == 0.473
    assert round(by_id["ft_transformer_rmse"]["rel_diff"], 4) == round(0.014 / 0.459, 4)
    assert not by_id["resnet_rmse"]["comparable"] and not by_id["xgboost_rmse"]["comparable"]


def test_paper_006_claims_are_never_compared_with_the_bank_run():
    for r in (r for r in rv.verdict_rows() if r["paper_id"] == "paper_006"):
        assert not r["comparable"] and "do not match" in r["reason"]


def test_a_paper_without_accepted_claims_gets_the_neutral_baseline_and_says_so():
    (row,) = [r for r in rv.verdict_rows() if r["paper_id"] == "paper_102"]
    assert row["query_id"] is None and row["cli_tier2"] == 70.0 and "neutral 70.0" in row["reason"]


def test_the_synthetic_control_gets_the_right_decision_for_a_true_and_a_false_claim():
    rows = [r for r in rv.verdict_rows() if r["paper_id"] == "synthetic_control"]
    assert len(rows) == 4
    for r in rows:
        if r["query_id"] == "true_claim":
            assert r["aligned_tier2"] == 100.0 and r["aligned_status"] == "Verified"
        else:
            assert r["aligned_tier2"] == 0.0 and r["aligned_status"] != "Verified"


def test_evidence_must_occur_in_the_run_output(tmp_path):
    (tmp_path / "stdout.log").write_text("model ft_transformer_default_0 on california_housing\n", encoding="utf-8")
    assert rv.evidence_found(tmp_path, ["ft_transformer_default_0", "california_housing"])
    assert not rv.evidence_found(tmp_path, ["dset_id=1461"])
    assert not rv.evidence_found(tmp_path, [])
    assert not rv.evidence_found(tmp_path / "missing", ["x"])


def test_the_stored_k2_records_say_what_the_document_says():
    k2 = {(k["paper_id"], k["run"]): k for k in stored()["k2"]}
    assert k2[("paper_003", "Pilot 3")]["passed"] is True
    assert k2[("paper_006", "Pilot 3")]["passed"] is False and k2[("paper_102", "Pilot 4")]["passed"] is False
    final = [m for m in k2[("paper_003", "Pilot 3")]["run_metrics_in_paper"] if m["metric"] == "rmse"]
    assert final and final[0]["found"] is False  # the run's final value is not in the paper
