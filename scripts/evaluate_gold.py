#!/usr/bin/env python3
"""Gold claim set: read the owner's filled form, then measure the extraction's precision and recall (W5, #133).

    python scripts/evaluate_gold.py from-form <form.md>     # write tests/data/gold_claims/<paper_id>.json
    python scripts/evaluate_gold.py score [--pass A]        # compare an extraction pass with the gold set

The form is a Markdown file outside the repository, filled by the owner (the gold values come from the paper text,
not from the extraction). Its structure is read, not its wording:

- `## paper_XXX ...` starts a paper; `**S<n>. `<query_id>`**` starts a question (several may share a line).
- Checkbox options (`- [x] ...`, or inline `- S<n>: [x] ... [ ] ...`) belong to the last question named.
- An option with a value in backticks is a candidate value. In every question the last option is the free "other"
  answer (`<label>: <value> (<label>: <page>)`), and the last option without a backtick value before it means
  "not in the paper". Any other checked option without a backtick value (for example a range of values) cannot be
  read safely: it is reported as `needs_decision` and kept out of the scores until it is resolved in the JSON.

Scoring, per question in the gold set (unanswered and `needs_decision` questions are left out):

- found, value in the gold set -> true positive
- found, value not in the gold set (or the gold set says "not in the paper") -> false positive; if the gold set has a
  value, also a false negative
- not found, gold set has a value -> false negative
- not found, gold set says "not in the paper" -> true negative (the regression cases EP3602 and HIGGS, #133)

Values are compared as printed, ignoring spaces.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import DATA_DIR, PROJECT_ROOT

GOLD_DIR = PROJECT_ROOT / "tests" / "data" / "gold_claims"
CLAIMS_DIR = DATA_DIR / "claims"
# Regression cases of #133: the paper does not report them, so the extraction must answer "not found".
REGRESSION_CASES = ("paper_005:ep3602_auroc", "paper_005:ep3602_accuracy", "paper_008:higgs_auroc")

PAPER_RE = re.compile(r"^##\s+(paper_\d+)\b")
QUESTION_RE = re.compile(r"\*\*S(\d+)\.\s+`([A-Za-z0-9_]+)`")
OPTION_LINE_RE = re.compile(r"^\s*-\s+\[( |x|X)\]\s*(.*)$")
INLINE_LINE_RE = re.compile(r"^\s*-\s+S(\d+):\s*(.*)$")
INLINE_BOX_RE = re.compile(r"\[( |x|X)\]\s*([^\[]*)")
BACKTICK_RE = re.compile(r"`([^`]+)`")


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value)


def parse_form(text: str) -> dict[str, dict[str, list[tuple[bool, str]]]]:
    """{paper_id: {query_id: [(checked, option text), ...]}} in form order."""
    papers: dict[str, dict[str, list[tuple[bool, str]]]] = {}
    numbers: dict[str, tuple[str, str]] = {}  # "S10" -> (paper_id, query_id)
    paper = None
    current: str | None = None
    for line in text.splitlines():
        if m := PAPER_RE.match(line):
            paper = m.group(1)
            papers.setdefault(paper, {})
            current = None
            continue
        questions = QUESTION_RE.findall(line)
        if questions and paper:
            for number, query_id in questions:
                papers[paper].setdefault(query_id, [])
                numbers[number] = (paper, query_id)
            current = questions[-1][1]
            continue
        if (m := INLINE_LINE_RE.match(line)) and m.group(1) in numbers:
            owner_paper, query_id = numbers[m.group(1)]
            for box, option in INLINE_BOX_RE.findall(m.group(2)):
                papers[owner_paper][query_id].append((box.lower() == "x", option.strip()))
            continue
        if (m := OPTION_LINE_RE.match(line)) and paper and current:
            papers[paper][current].append((m.group(1).lower() == "x", m.group(2).strip()))
    return papers


def _other_answer(option: str) -> tuple[str | None, int | None]:
    """Value and page written into the free "other" option, or (None, None) if it was left blank."""
    body = option.split(":", 1)[1] if ":" in option else option
    value_part = body.split("(", 1)[0].strip().strip("_").strip()
    pages = re.findall(r"\((?:[^():]*:)?\s*(\d+)\s*\)", body)
    if not value_part or not re.search(r"\d", value_part):
        return None, None
    return value_part, int(pages[-1]) if pages else None


def gold_from_options(options: list[tuple[bool, str]]) -> dict[str, Any] | None:
    """The gold answer of one question, or None when nothing is checked."""
    if not any(checked for checked, _ in options):
        return None
    last = len(options) - 1
    no_value = [i for i, (_, text) in enumerate(options[:last]) if not BACKTICK_RE.search(text)]
    not_found_index = no_value[-1] if no_value else None
    values: list[str] = []
    other_pages: dict[str, int] = {}
    not_in_paper = False
    unclear: list[str] = []
    for i, (checked, text) in enumerate(options):
        if not checked:
            continue
        if i == last:
            value, page = _other_answer(text)
            if value is None:
                unclear.append(f"'other' checked but no value written: {text}")
            else:
                values.append(value)
                if page is not None:
                    other_pages[value] = page
        elif m := BACKTICK_RE.search(text):
            values.append(m.group(1))
        elif i == not_found_index:
            not_in_paper = True
        else:
            unclear.append(f"checked option without a single value: {text}")
    if not_in_paper and values:
        unclear.append("both a value and 'not in the paper' are checked")
    gold: dict[str, Any] = {"accepted_values": values, "not_in_paper": not_in_paper}
    if other_pages:
        gold["pages_of_other_values"] = other_pages
    if unclear:
        gold["needs_decision"] = unclear
    return gold


def gold_sets_from_form(text: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for paper_id, questions in parse_form(text).items():
        answered = {q: g for q, opts in questions.items() if (g := gold_from_options(opts)) is not None}
        if answered:
            out[paper_id] = {"paper_id": paper_id, "made_by": "owner", "source": "owner's gold set form (W5, #133)",
                             "questions": answered}
    return out


def score(gold_sets: dict[str, dict[str, Any]], claims_dir: Path, pass_name: str) -> dict[str, Any]:
    rows = []
    for paper_id, gold in sorted(gold_sets.items()):
        answers = json.loads((claims_dir / f"{paper_id}.json").read_text(encoding="utf-8"))["extractions"][pass_name]["answers"]
        for query_id, g in sorted(gold["questions"].items()):
            if g.get("needs_decision"):
                rows.append({"question": f"{paper_id}:{query_id}", "outcome": "needs_decision"})
                continue
            answer = answers.get(query_id, {"status": "missing"})
            found = answer.get("status") == "found"
            extracted = answer["claim"]["value_as_printed"] if found else None
            accepted = {normalize(v) for v in g["accepted_values"]}
            if found and normalize(extracted) in accepted:
                outcome = ["TP"]
            elif found:
                outcome = ["FP"] + (["FN"] if accepted else [])
            else:
                outcome = ["FN"] if accepted else ["TN"]
            rows.append({"question": f"{paper_id}:{query_id}", "extracted": extracted, "gold": g["accepted_values"],
                         "gold_not_in_paper": g["not_in_paper"], "outcome": "+".join(outcome)})
    tp = sum("TP" in r["outcome"] for r in rows)
    fp = sum("FP" in r["outcome"] for r in rows)
    fn = sum("FN" in r["outcome"] for r in rows)
    tn = sum(r["outcome"] == "TN" for r in rows)
    by_question = {r["question"]: r["outcome"] for r in rows}
    return {
        "pass": pass_name,
        "scored_questions": sum(r["outcome"] != "needs_decision" for r in rows),
        "needs_decision": [r["question"] for r in rows if r["outcome"] == "needs_decision"],
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "regression_cases": {q: by_question.get(q, "not in the gold set") for q in REGRESSION_CASES},
        "rows": rows,
    }


def load_gold(gold_dir: Path) -> dict[str, dict[str, Any]]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(gold_dir.glob("paper_*.json"))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gold claim set and precision/recall of the extraction.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_form = sub.add_parser("from-form", help="Convert the owner's filled form into gold JSON files.")
    p_form.add_argument("form")
    p_form.add_argument("--out", default=str(GOLD_DIR))
    p_score = sub.add_parser("score", help="Compare an extraction pass with the gold set.")
    p_score.add_argument("--pass", dest="pass_name", default="A")
    p_score.add_argument("--gold", default=str(GOLD_DIR))
    p_score.add_argument("--claims-dir", default=str(CLAIMS_DIR))
    args = parser.parse_args(argv)

    if args.command == "from-form":
        gold_sets = gold_sets_from_form(Path(args.form).read_text(encoding="utf-8"))
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        unclear = []
        for paper_id, gold in gold_sets.items():
            (out / f"{paper_id}.json").write_text(json.dumps(gold, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            unclear += [f"{paper_id}:{q}: {g['needs_decision']}" for q, g in gold["questions"].items() if g.get("needs_decision")]
        print(json.dumps({"papers": sorted(gold_sets), "questions": sum(len(g["questions"]) for g in gold_sets.values()),
                          "needs_decision": unclear}, indent=2, ensure_ascii=False))
        return 1 if unclear else 0

    gold_sets = load_gold(Path(args.gold))
    if not gold_sets:
        print(f"No gold set in {args.gold}; fill the form and run 'from-form' first.", file=sys.stderr)
        return 2
    result = score(gold_sets, Path(args.claims_dir), args.pass_name)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
