#!/usr/bin/env python3
"""Measure the diagnosis classifier against hand-written labels of real failures (#36).

    python scripts/evaluate_diagnosis_classifier.py            # write data/diagnosis_validation/results.json and the document
    python scripts/evaluate_diagnosis_classifier.py --check    # exit 1 if either differs from what the labels and runs give

Inputs: `data/diagnosis_validation/labels.json` (real runs of Pilots 1 to 4, the memory runs, the CPU runs, and the first
attempts kept as evidence; labeled by hand from the error line, see the file's `label_source`), `labels_synthetic.json`
(invented error lines that probe the edges of the rules; reported separately), and `analysis.json` (why each wrong answer is
wrong, written by hand after the first evaluation). The document is `docs/DIAGNOSIS_VALIDATION.md`.

A prediction is compared with the label on three levels: the category, the name given to an `OTHER` (or to a run without a
failure category), and the phase in which the run stopped.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.diagnosis.classifier import Classification, classify_run

VALIDATION_DIR = project_root / "data" / "diagnosis_validation"
RESULTS_PATH = VALIDATION_DIR / "results.json"
DOC_PATH = project_root / "docs" / "DIAGNOSIS_VALIDATION.md"
NO_FAILURE = "NO_FAILURE"
NO_CATEGORY = "NO_FAILURE_CATEGORY"  # the run is not a success but has no failure category (ran without installed dependencies)


def predicted(classification: Classification) -> dict[str, Any]:
    """The classifier's answer in the vocabulary of the labels."""
    if classification.pilot_success:
        return {"category": NO_FAILURE, "name": None, "phase": None}
    return {"category": classification.category or NO_CATEGORY, "name": classification.other_name,
            "phase": classification.phase}


def compare(label: dict[str, Any], got: dict[str, Any]) -> dict[str, bool | None]:
    category_ok = label["category"] == got["category"]
    named = label["category"] in ("OTHER", NO_CATEGORY)
    name_ok = (label.get("name") == got["name"]) if named else None
    phase_ok = (label.get("phase") == got["phase"]) if "phase" in label and label["category"] != NO_FAILURE else None
    return {"category": category_ok, "name": name_ok, "phase": phase_ok,
            "all": category_ok and name_ok is not False and phase_ok is not False}


def synthetic_run(root: Path, case: dict[str, Any]) -> Path:
    """A run folder whose only failure is the error line of the case (install fine, run FAILED with exit code 1)."""
    folder = root / case["id"]
    folder.mkdir(parents=True)
    (folder / "pilot_record.json").write_text(json.dumps({"stage": {"status": "STAGED", "target_script_exists": True}}))
    (folder / "run_report.json").write_text(json.dumps({"docker_used": True, "isolated": True, "status": "FAILED",
                                                        "exit_code": 1, "dependency_install_status": "INSTALLED"}))
    (folder / "stderr.log").write_text(case["stderr"], encoding="utf-8")
    return folder


def evaluate(root: Path = project_root) -> dict[str, Any]:
    labels = json.loads((root / "data/diagnosis_validation/labels.json").read_text(encoding="utf-8"))
    synthetic = json.loads((root / "data/diagnosis_validation/labels_synthetic.json").read_text(encoding="utf-8"))
    real: list[dict[str, Any]] = []
    for entry in labels["runs"]:
        classification = classify_run(root / entry["run_dir"])
        got = predicted(classification)
        real.append({"id": entry["id"], "run_dir": entry["run_dir"], "label": entry["label"], "predicted": got,
                     "evidence_quoted_by_classifier": classification.evidence, "match": compare(entry["label"], got)})
    probes: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="diagnosis_probes_") as tmp:
        for case in synthetic["cases"]:
            classification = classify_run(synthetic_run(Path(tmp), case))
            got = predicted(classification)
            label = {**case["label"], "phase": "run"}
            probes.append({"id": case["id"], "last_line": case["stderr"].strip().splitlines()[-1], "label": label,
                           "predicted": got, "match": compare(label, got)})
    return {"real": real, "synthetic": probes, "summary": {"real": summarize(real), "synthetic": summarize(probes)}}


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    def rate(key: str) -> dict[str, Any]:
        scored = [i["match"][key] for i in items if i["match"][key] is not None]
        return {"correct": sum(scored), "of": len(scored)}

    return {"n": len(items), "category": rate("category"), "name": rate("name"), "phase": rate("phase"), "all": rate("all"),
            "wrong": [i["id"] for i in items if not i["match"]["all"]]}


def render(results: dict[str, Any], analysis: dict[str, str]) -> str:
    def pct(r: dict[str, Any]) -> str:
        return f"{r['correct']} / {r['of']}" + (f" ({r['correct'] / r['of']:.1%})" if r["of"] else "")

    out = ["# Validation of the failure classifier", "",
           "<!-- Generated by scripts/evaluate_diagnosis_classifier.py from data/diagnosis_validation/; do not edit by hand. -->", "",
           "Issue: #36. The classifier is `src/diagnosis/classifier.py` (docs/DIAGNOSIS.md section 5).", ""]
    labels = json.loads((VALIDATION_DIR / "labels.json").read_text(encoding="utf-8"))
    out += ["## 1. How the labels were made", "", labels["label_source"], "",
            ("**Consequences.** The real runs are the logs the rules were written from, so the accuracy below is an upper bound "
             "for new papers, not an estimate of it. The labeler also knew the rules. The synthetic probes (section 4) are the "
             "only part written to find gaps."), ""]
    s = results["summary"]["real"]
    out += ["## 2. Real runs", "", f"{s['n']} stored runs (Pilots 1 to 4, the memory and CPU runs, and the first attempts kept as evidence).", "",
            "| Level | Correct |", "|---|---|", f"| Category | {pct(s['category'])} |",
            f"| Name of an `OTHER` (or of a run without a failure category) | {pct(s['name'])} |",
            f"| Phase in which the run stopped | {pct(s['phase'])} |", f"| All three levels | {pct(s['all'])} |", ""]
    wrong = [r for r in results["real"] if not r["match"]["all"]]
    if wrong:
        out += ["Wrong answers:", "", "| Id | Run | Label | Classifier | Why |", "|---|---|---|---|---|"]
        for r in wrong:
            out.append(f"| {r['id']} | `{r['run_dir']}` | {fmt(r['label'])} | {fmt(r['predicted'])} | {analysis.get(r['id'], '(no analysis written)')} |")
        out.append("")
    else:
        out += ["No wrong answer among the real runs.", ""]
    out += ["## 3. Count by label (real runs)", "", "| Label | Runs |", "|---|---|"]
    counts: dict[str, int] = {}
    for r in results["real"]:
        key = r["label"]["name"] or r["label"]["category"] if r["label"]["category"] in ("OTHER", NO_CATEGORY) else r["label"]["category"]
        counts[key] = counts.get(key, 0) + 1
    out += [f"| {k} | {v} |" for k, v in sorted(counts.items())] + [""]
    p = results["summary"]["synthetic"]
    out += ["## 4. Synthetic probes (not real runs)", "",
            "Invented error lines, labeled by the category definitions. They are not part of the numbers of section 2.", "",
            f"Category correct: {pct(p['category'])}; name correct: {pct(p['name'])}; all levels: {pct(p['all'])}.", "",
            "| Id | Last line | Label | Classifier | Right? | Why, if wrong |", "|---|---|---|---|---|---|"]
    for r in results["synthetic"]:
        out.append(f"| {r['id']} | `{r['last_line'][:90]}` | {fmt(r['label'])} | {fmt(r['predicted'])} | "
                   f"{'yes' if r['match']['all'] else 'no'} | {'' if r['match']['all'] else analysis.get(r['id'], '(no analysis written)')} |")
    papers = {re.search(r"paper_\d+", r["run_dir"]).group(0) for r in results["real"]}
    out += ["", "## 5. What this does not show", "",
            (f"- Accuracy on papers outside these logs. The real set is small, comes from {len(papers)} papers, and is "
             "dominated by missing packages."),
            ("- That a category is the *cause*. The classifier reads the deciding line; a missing package can itself be the "
             "result of a pin or a platform limit (several first attempts were tool defects with the same line)."),
            "- That the labels are right. They are one person's reading of the definitions, not blind."]
    return "\n".join(out) + "\n"


def fmt(label: dict[str, Any]) -> str:
    parts = [str(label.get("category"))]
    if label.get("name"):
        parts.append(f"/ {label['name']}")
    if label.get("phase"):
        parts.append(f"({label['phase']})")
    return " ".join(parts)


def build(root: Path = project_root) -> tuple[str, str]:
    results = evaluate(root)
    analysis_path = root / "data/diagnosis_validation/analysis.json"
    analysis = json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.is_file() else {}
    return json.dumps(results, indent=2, ensure_ascii=False) + "\n", render(results, analysis)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    results_text, doc_text = build()
    if args.check:
        stored = RESULTS_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") if RESULTS_PATH.is_file() else ""
        doc = DOC_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") if DOC_PATH.is_file() else ""
        if stored != results_text or doc != doc_text:
            print("results.json or DIAGNOSIS_VALIDATION.md differ from the labels; run scripts/evaluate_diagnosis_classifier.py",
                  file=sys.stderr)
            return 1
        return 0
    RESULTS_PATH.write_text(results_text, encoding="utf-8", newline="\n")
    DOC_PATH.write_text(doc_text, encoding="utf-8", newline="\n")
    summary = json.loads(results_text)["summary"]
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
