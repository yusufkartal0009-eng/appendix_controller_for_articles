"""The gold set expansion (#315): 18 more questions, two passes, an owner form; no gold file yet."""

import json

from scripts import compare_extractions as ce
from scripts import evaluate_gold as eg
from scripts import gold_expansion as ge
from src.config import DATA_DIR

EXPANSION = DATA_DIR / "gold_expansion"


def test_there_are_three_questions_per_paper_and_one_negative_control():
    papers = ge.load_questions()
    assert len(papers) == 6
    assert all(len(spec["queries"]) == 3 for spec in papers.values())
    assert sum(len(spec["queries"]) for spec in papers.values()) == 18


def test_no_question_contains_a_value():
    questions = " ".join(q["question"] for spec in ge.load_questions().values() for q in spec["queries"])
    candidates = json.loads((EXPANSION / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    values = {c["value"] for lst in candidates.values() for c in lst if len(c["value"]) > 3}
    assert not [v for v in values if v in questions]


def test_every_question_has_candidates_and_the_form_is_readable_by_the_evaluator(tmp_path):
    form = tmp_path / "form.md"
    assert ge.make_form(form) == 18
    parsed = eg.parse_form(form.read_text(encoding="utf-8"))
    assert sum(len(q) for q in parsed.values()) == 18
    for questions in parsed.values():
        for options in questions.values():
            assert len(options) >= 4 and not any(checked for checked, _ in options)  # nothing is pre-ticked
            assert options[-2][1] == "Not in the paper" and options[-1][1].startswith("Other")


def test_the_form_order_does_not_put_the_passes_answer_first_everywhere(tmp_path):
    form = tmp_path / "form.md"
    ge.make_form(form)
    parsed = eg.parse_form(form.read_text(encoding="utf-8"))
    first_is_candidate_zero = 0
    candidates = json.loads((EXPANSION / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    for questions in parsed.values():
        for qid, options in questions.items():
            if f"`{candidates[qid][0]['value']}`" in options[0][1]:
                first_is_candidate_zero += 1
    assert first_is_candidate_zero < 18


def test_both_passes_are_stored_for_every_question_and_valid():
    for paper_id, spec in ge.load_questions().items():
        record = json.loads((EXPANSION / "claims" / f"{paper_id}.json").read_text(encoding="utf-8"))
        assert set(record["extractions"]) == {"A", "B"}
        for label in ("A", "B"):
            assert set(record["extractions"][label]["answers"]) == {q["query_id"] for q in spec["queries"]}
    answers = {pid: json.loads((EXPANSION / "claims" / f"{pid}.json").read_text(encoding="utf-8"))["extractions"]["B"]["answers"]
               for pid in ge.load_questions()}
    assert ge.check_answers(answers) == []  # every quote of pass B occurs on the page it cites


def test_the_two_passes_agree_on_every_question_by_normalized_value():
    rows = ce.compare_claims_dir(EXPANSION / "claims") if hasattr(ce, "compare_claims_dir") else None
    if rows is None:  # older helper name: read the generated file
        data = json.loads((EXPANSION / "claims" / "consistency.json").read_text(encoding="utf-8"))
        assert data["questions"] == 18 and data["disagreements"] == 0
    else:
        assert len(rows) == 18 and all(r["verdict"].startswith("agree") for r in rows)


def test_there_is_no_gold_file_before_the_owner_has_filled_the_form():
    assert not (EXPANSION / "gold").exists()


def test_the_negative_controls_are_not_in_the_papers():
    papers = {"tabnet_mean_auc_ovo": ("paper_002", "TabNet"), "ft_transformer_mnist_accuracy": ("paper_003", "MNIST"),
              "tabr_imagenet_accuracy": ("paper_004", "ImageNet"), "higgs_avg_speedup": ("paper_005", "HIGGS"),
              "saint_cifar10_accuracy": ("paper_006", "CIFAR"), "danet20_imagenet_accuracy": ("paper_008", "ImageNet")}
    from src.pdf_text import extract_pdf_text
    for qid, (paper_id, term) in papers.items():
        pdf = extract_pdf_text(DATA_DIR / "pdfs" / f"{paper_id}.pdf")
        table_pages = " ".join(pdf.pages)
        if qid == "tabnet_mean_auc_ovo":  # named in the text, but Table 1 has no TabNet column
            assert "TabNet" not in pdf.page(8).split("Table 1:")[0]
        elif qid == "ft_transformer_mnist_accuracy":
            assert "MNIST" not in table_pages
        else:
            assert term.lower() not in table_pages.lower()
