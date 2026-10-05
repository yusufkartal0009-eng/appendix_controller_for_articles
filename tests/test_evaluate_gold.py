"""Gold set form parsing and precision/recall of the extraction (W5, #133).

The form below only mirrors the structure of the owner's form; its values are made up for the test and are not
the gold set.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import evaluate_gold as eg

FORM = """# Gold set form

## paper_003 - FT-Transformer

**S4. `ft_transformer_rmse`**
- [x] `0.459` - Table 2, p. 7
- [ ] `0.448` - Table 3, p. 7
- [ ] Not in the paper
- [ ] Other: ______ (page: __)

**S5. `resnet_rmse`**
- [ ] `0.486` - Table 2, p. 7
- [x] Table 11, p. 17: values by tuning budget (0.488 ... 0.481)
- [ ] Not in the paper
- [ ] Other: ______ (page: __)

**S6. `xgboost_rmse`** *(accepted earlier as `0.433`)*
- [ ] `0.433` - Table 8
- [ ] Not in the paper
- [x] Other: 0.431 (page: 8)

## paper_005 - FastSK

**S10. `ep3602_auroc`** and **S11. `ep3602_accuracy`**
- The dataset is not in the paper (note line, not an option).
- S10: [x] Not in the paper   [ ] Other: ______ (page: __)
- S11: [ ] Not in the paper   [ ] Other: ______ (page: __)

**S12. `kernel_speedup_factor`**
- [x] Not in the paper (Figure 4 shows no speedup)
- [ ] Other: ______ (page: __)
"""


def test_form_is_read_by_structure():
    gold = eg.gold_sets_from_form(FORM)
    assert sorted(gold) == ["paper_003", "paper_005"]
    q3 = gold["paper_003"]["questions"]
    assert q3["ft_transformer_rmse"] == {"accepted_values": ["0.459"], "not_in_paper": False}
    assert "needs_decision" in q3["resnet_rmse"]  # a range is not a single value
    assert q3["xgboost_rmse"] == {"accepted_values": ["0.431"], "not_in_paper": False,
                                  "pages_of_other_values": {"0.431": 8}}  # the free "other" answer
    q5 = gold["paper_005"]["questions"]
    assert q5["ep3602_auroc"] == {"accepted_values": [], "not_in_paper": True}  # inline options
    assert "ep3602_accuracy" not in q5  # unanswered questions stay out of the gold set
    assert q5["kernel_speedup_factor"] == {"accepted_values": [], "not_in_paper": True}  # digits in the label are ignored


def test_contradictions_and_blank_other_need_a_decision():
    both = eg.gold_from_options([(True, "`0.459` - Table 2"), (True, "Not in the paper"), (False, "Other: __")])
    assert both["needs_decision"] == ["both a value and 'not in the paper' are checked"]
    blank = eg.gold_from_options([(False, "`0.459`"), (False, "Not in the paper"), (True, "Other: ______ (page: __)")])
    assert "no value written" in blank["needs_decision"][0]
    assert eg.gold_from_options([(False, "`0.459`"), (False, "Other")]) is None


def _claims(tmp_path, paper_id, answers):
    (tmp_path / f"{paper_id}.json").write_text(json.dumps({"extractions": {"A": {"answers": answers}}}), encoding="utf-8")


def found(value):
    return {"status": "found", "claim": {"value_as_printed": value}}


def test_precision_recall_and_regression_cases(tmp_path):
    gold = {
        "paper_003": {"questions": {
            "a": {"accepted_values": ["0.459"], "not_in_paper": False},      # TP (spaces ignored)
            "b": {"accepted_values": ["0.486"], "not_in_paper": False},      # wrong value: FP+FN
            "c": {"accepted_values": ["0.433"], "not_in_paper": False},      # missed: FN
            "d": {"accepted_values": [], "not_in_paper": True, "needs_decision": ["x"]},  # left out
        }},
        "paper_005": {"questions": {
            "ep3602_auroc": {"accepted_values": [], "not_in_paper": True},   # TN
            "ep3602_accuracy": {"accepted_values": [], "not_in_paper": True},  # invented: FP
        }},
    }
    _claims(tmp_path, "paper_003", {"a": found("0 .459"), "b": found("0.478"), "c": {"status": "not_found"}})
    _claims(tmp_path, "paper_005", {"ep3602_auroc": {"status": "not_found"}, "ep3602_accuracy": found("0.9")})
    result = eg.score(gold, tmp_path, "A")
    assert (result["tp"], result["fp"], result["fn"], result["tn"]) == (1, 2, 2, 1)
    assert result["precision"] == 0.333 and result["recall"] == 0.333
    assert result["scored_questions"] == 5 and result["needs_decision"] == ["paper_003:d"]
    assert result["regression_cases"] == {"paper_005:ep3602_auroc": "TN", "paper_005:ep3602_accuracy": "FP",
                                          "paper_008:higgs_auroc": "not in the gold set"}


def test_cli_round_trip(tmp_path, capsys):
    form = tmp_path / "form.md"
    form.write_text(FORM, encoding="utf-8")
    assert eg.main(["from-form", str(form), "--out", str(tmp_path / "gold")]) == 1  # resnet_rmse needs a decision
    data = json.loads((tmp_path / "gold" / "paper_003.json").read_text(encoding="utf-8"))
    assert data["made_by"] == "owner" and "needs_decision" in data["questions"]["resnet_rmse"]
    assert eg.main(["score", "--gold", str(tmp_path / "empty")]) == 2
    capsys.readouterr()


def test_score_runs_on_the_real_extraction_files(tmp_path):
    gold = {"paper_008": {"questions": {"higgs_auroc": {"accepted_values": [], "not_in_paper": True}}}}
    result = eg.score(gold, eg.CLAIMS_DIR, "A")
    assert result["regression_cases"]["paper_008:higgs_auroc"] in ("TN", "FP")
