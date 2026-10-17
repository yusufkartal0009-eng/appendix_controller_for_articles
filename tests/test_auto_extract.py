"""Consensus candidates from independent extraction passes (#381)."""

import json
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from scripts import auto_extract as ae
from src.claim_review import claims_for_scoring
from src.claim_store import consensus_candidates, record_review
from src.database import get_engine, get_session, init_db, seed_database
from src.models import ExtractedClaimORM
from src.pdf_text import PdfText

PAGE = "Table 2: FT-T 0.459 0.391 and MLP 0.512 on California Housing"


def pdf():
    return PdfText(sha256="a" * 64, pages=[PAGE], extractor="fake")


def claim(value="0.459", quote="FT-T 0.459 0.391", page=1, confidence=0.9):
    return {"metric_name": "rmse", "value_as_printed": value, "unit": "none", "dataset": "California Housing",
            "model_variant": "FT-T", "split": "test", "higher_is_better": False, "table_or_figure": "Table 2", "page": page,
            "source_quote": quote, "confidence": confidence}


def found(**kw):
    return {"status": "found", "reason": "", "claim": claim(**kw)}


NOT_FOUND = {"status": "not_found", "reason": "not in the paper", "claim": None}


def consensus(*answers):
    raw = {i: {"paper_003": {"q": a}} for i, a in enumerate(answers, start=1) if a is not None}
    return ae.build_consensus(raw, {"paper_003": pdf()}, {"paper_003": ["q"]})["paper_003"]["questions"]["q"]


def test_two_of_three_passes_with_the_same_value_make_a_candidate():
    out = consensus(found(), found(confidence=0.5), found(value="0.391", quote="0.459 0.391"))
    assert out["outcome"] == "candidate" and out["agreeing_passes"] == [1, 2]
    assert out["candidate"]["value_as_printed"] == "0.459" and out["candidate"]["confidence"] == 0.9


def test_three_different_values_are_left_to_a_person():
    out = consensus(found(), found(value="0.391", quote="0.459 0.391"), found(value="0.512", quote="MLP 0.512"))
    assert out["outcome"] == "no_consensus" and out["candidate"] is None


def test_a_quote_that_is_not_on_the_page_is_not_a_vote():
    out = consensus(found(), found(quote="FT-T 0.459 0.999"), found(value="0.391", quote="0.459 0.391"))
    assert out["outcome"] == "no_consensus"
    assert [v["problem"] for v in out["votes"]][1] == "source_quote not on page 1"


def test_a_page_that_does_not_exist_and_a_broken_claim_are_not_votes():
    out = consensus(found(), found(page=9), {"status": "found", "reason": "", "claim": {"metric_name": "x"}})
    assert out["outcome"] == "no_consensus"
    assert out["votes"][1]["problem"] == "page 9 does not exist" and out["votes"][2]["problem"].startswith("invalid claim")


def test_the_same_number_printed_differently_agrees():
    out = consensus(found(), found(value="0.4590"), found(value="0.391", quote="0.459 0.391"))
    # "0.4590" is not in the page text, so its quote fails; with a quote that contains it, the values agree
    assert out["outcome"] == "no_consensus"
    page = PdfText(sha256="a" * 64, pages=["FT-T 0.459 and FT-T 0.4590"], extractor="fake")
    raw = {1: {"paper_003": {"q": found(quote="FT-T 0.459")}}, 2: {"paper_003": {"q": found(value="0.4590", quote="FT-T 0.4590")}}}
    assert ae.build_consensus(raw, {"paper_003": page}, {"paper_003": ["q"]})["paper_003"]["questions"]["q"]["outcome"] == "candidate"


def test_two_not_found_answers_make_a_consensus_not_found_unless_a_pass_found_a_valid_claim():
    assert consensus(NOT_FOUND, NOT_FOUND, found())["outcome"] == "no_consensus"
    assert consensus(NOT_FOUND, NOT_FOUND, None)["outcome"] == "consensus_not_found"
    assert consensus(NOT_FOUND, NOT_FOUND, found(quote="not on the page 0.459"))["outcome"] == "consensus_not_found"
    assert consensus(NOT_FOUND, found(), None)["outcome"] == "no_consensus"


def test_a_not_found_answer_without_a_reason_is_invalid():
    assert ae.check_answer({"status": "not_found", "reason": "", "claim": None}, pdf()) == ("invalid", "not_found needs a reason and no claim")


GOLD = {"paper_003": {"questions": {"q": {"accepted_values": ["0.459"], "not_in_paper": False},
                                    "r": {"accepted_values": [], "not_in_paper": True}}}}


def result(q_outcome, r_outcome):
    def entry(outcome, value=None):
        votes = [{"pass": i, "state": "found" if value else "not_found", "problem": None, "value_as_printed": value} for i in (1, 2, 3)]
        return {"outcome": outcome, "candidate": {"value_as_printed": value} if value else None, "agreeing_passes": [1, 2], "votes": votes}
    return {"name": "t", "papers": {"paper_003": {"questions": {"q": entry(*q_outcome), "r": entry(*r_outcome)}}}}


def test_evaluation_counts_true_and_false_positives_and_what_is_left_to_a_person():
    ok = ae.evaluate(result(("candidate", "0.459"), ("consensus_not_found",)), GOLD)
    assert ok["consensus_decisions"]["tp"] == 1 and ok["consensus_decisions"]["tn"] == 1
    assert ok["consensus_decisions"]["precision"] == 1.0 and ok["consensus_recall_over_all_gold_values"] == 1.0
    wrong = ae.evaluate(result(("candidate", "0.999"), ("candidate", "0.1")), GOLD)
    assert wrong["consensus_decisions"]["fp"] == 2 and wrong["consensus_decisions"]["fn"] == 1
    assert wrong["consensus_decisions"]["precision"] == 0.0
    left = ae.evaluate(result(("no_consensus",), ("no_consensus",)), GOLD)
    assert left["left_to_a_person"] == 2 and left["decided_by_consensus"] == 0
    assert left["consensus_recall_over_all_gold_values"] == 0.0 and left["consensus_decisions"]["precision"] is None


def fake_runner(answers_by_pass):
    calls = []

    def runner(folder: Path, timeout: int):
        calls.append(folder)
        assert (folder / "paper.txt").read_text(encoding="utf-8").startswith("=== PAGE 1 ===")
        assert sorted(p.name for p in folder.iterdir()) == ["README.md", "RULES.md", "SCHEMA.md", "answers.json", "paper.txt", "questions.json"]
        pass_no = int(folder.parent.name.split("_")[1])
        answer = answers_by_pass[pass_no]
        if answer is not None:
            (folder / "answers.json").write_text(json.dumps({"paper_003": {"q": answer}}), encoding="utf-8")
        return {"exit_code": 0, "seconds": 0.1}

    runner.calls = calls
    return runner


@pytest.fixture
def setup(tmp_path, monkeypatch):
    queries = tmp_path / "queries"
    queries.mkdir()
    (queries / "paper_003.json").write_text(json.dumps({"paper_id": "paper_003", "queries": [{"query_id": "q", "question": "RMSE of FT-T?"}]}))
    monkeypatch.setattr(ae, "extract_pdf_text", lambda path: pdf())
    return queries


def test_run_passes_uses_a_clean_packet_per_pass_and_writes_raw_answers_meta_and_consensus(tmp_path, setup):
    runner = fake_runner({1: found(), 2: found(), 3: NOT_FOUND})
    out = ae.run_passes("t", ["paper_003"], out_root=tmp_path / "out", queries_dir=setup, pdf_dir=tmp_path, runner=runner,
                        work_root=tmp_path / "work", workers=1)
    assert out["papers"]["paper_003"]["questions"]["q"]["outcome"] == "candidate"
    assert len(runner.calls) == 3 and len({str(c) for c in runner.calls}) == 3
    assert sorted(p.name for p in (tmp_path / "out" / "t" / "raw").iterdir()) == ["pass_1", "pass_2", "pass_3"]
    meta = json.loads((tmp_path / "out" / "t" / "meta.json").read_text(encoding="utf-8"))
    assert meta["tools"] == "Read,Write,Edit,Glob,Grep" and meta["runs"]["pass_1/paper_003"]["attempts"][0]["attempt"] == 1
    assert ae.write_consensus("t", tmp_path / "out", setup, tmp_path)["papers"] == out["papers"]  # recomputed from the stored passes


def test_a_pass_that_wrote_nothing_is_started_once_more_and_then_counts_as_no_answer(tmp_path, setup):
    runner = fake_runner({1: found(), 2: found(), 3: None})
    out = ae.run_passes("t", ["paper_003"], out_root=tmp_path / "out", queries_dir=setup, pdf_dir=tmp_path, runner=runner,
                        work_root=tmp_path / "work", workers=1)
    assert len(runner.calls) == 1 + 1 + ae.ATTEMPTS  # the failed pass was started twice
    meta = json.loads((tmp_path / "out" / "t" / "meta.json").read_text(encoding="utf-8"))
    assert len(meta["runs"]["pass_3/paper_003"]["attempts"]) == ae.ATTEMPTS
    assert out["papers"]["paper_003"]["questions"]["q"]["outcome"] == "candidate"  # two valid passes still agree


def test_packets_must_be_outside_the_repository(tmp_path, setup):
    with pytest.raises(ValueError, match="outside the repository"):
        ae.run_passes("t", ["paper_003"], out_root=tmp_path, queries_dir=setup, runner=fake_runner({}),
                      work_root=ae.project_root / "packets")


def test_the_claude_command_allows_only_the_file_tools_and_refuses_everything_else():
    command = ae.claude_command("claude")
    assert command[command.index("--tools") + 1] == "Read,Write,Edit,Glob,Grep"
    assert command[command.index("--permission-mode") + 1] == "dontAsk"
    for flag in ("--no-session-persistence", "--disable-slash-commands", "--strict-mcp-config"):
        assert flag in command
    assert not any(tool in command[command.index("--tools") + 1] for tool in ("Bash", "WebFetch", "WebSearch"))


@pytest.fixture
def session(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    init_db(engine)
    s = get_session(engine)
    seed_database(session=s)
    yield s
    s.close()


def stored_result():
    return {"papers": {"paper_003": {"pdf_sha256": "a" * 64, "questions": {
        "ft_transformer_rmse": {"outcome": "candidate", "agreeing_passes": [1, 2],
                                "candidate": {**claim(), "value_normalized": 0.459}},
        "other": {"outcome": "no_consensus", "candidate": None, "agreeing_passes": [], "votes": []}}}}}


def test_candidates_are_stored_pending_with_verified_by_auto_consensus_and_never_reach_the_default_score(session):
    counts = ae.import_candidates(stored_result(), session, "data/auto_extract/t/consensus.json")
    assert counts == {"added": 1, "no_consensus": 1}
    row = session.get(ExtractedClaimORM, "paper_003:ft_transformer_rmse")
    assert row.verified_by == "auto-consensus" and row.review_status == "pending"
    assert [c.query_id for c in consensus_candidates(session, "paper_003")] == ["ft_transformer_rmse"]
    assert claims_for_scoring(session, "paper_003") == {}  # the default score uses only claims a person accepted
    assert claims_for_scoring(session, "paper_003", include_auto_consensus=True) == {"ft_transformer_rmse": 0.459}


def test_a_candidate_cannot_be_marked_accepted_without_a_person(session):
    ae.import_candidates(stored_result(), session, "x")
    row = session.get(ExtractedClaimORM, "paper_003:ft_transformer_rmse")
    row.review_status = "accepted"  # verified_by is still auto-consensus
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_claim_a_person_reviewed_is_never_touched_and_wins_over_a_candidate(session):
    ae.import_candidates(stored_result(), session, "x")
    record_review(session, "paper_003:ft_transformer_rmse", "accepted")
    session.commit()
    again = stored_result()
    again["papers"]["paper_003"]["questions"]["ft_transformer_rmse"]["candidate"]["value_as_printed"] = "0.46"
    again["papers"]["paper_003"]["questions"]["ft_transformer_rmse"]["candidate"]["value_normalized"] = 0.46
    counts = ae.import_candidates(again, session, "x")
    assert counts["skipped (already reviewed by a person)"] == 1
    row = session.get(ExtractedClaimORM, "paper_003:ft_transformer_rmse")
    assert (row.verified_by, row.review_status, row.value) == ("human", "accepted", 0.459)
    assert claims_for_scoring(session, "paper_003", include_auto_consensus=True) == {"ft_transformer_rmse": 0.459}


def test_the_main_value_variant_ignores_a_spread_on_both_sides_and_the_default_does_not():
    gold = {"accepted_values": ["0.433±1.6e-3"], "not_in_paper": False}
    assert ae._classify("0.433", gold) == "FP+FN"
    assert ae._classify("0.433", gold, main_only=True) == "TP"
    assert ae._classify("0.434", gold, main_only=True) == "FP+FN"
    assert ae.main_value("1.3± 0.9") == "1.3"
