#!/usr/bin/env python3
"""Tolerance probe: where does the Tier 2 decision change when a claim is moved away from a real run's own value? (#440)

    python scripts/tolerance_probe.py            # write data/tolerance_probe/results.json and docs/TOLERANCE_PROBE.md
    python scripts/tolerance_probe.py --check    # the committed files equal what the stored runs give now

For every stored, completed run listed in RUNS (and every candidate run that passed, data/candidates/runs/evaluation.json)
the metrics that the metric extractor found in the run's output (`run_report.json`) are taken as they were printed. The
"claim" of a row is then made by hand from that run's own value:

- deviation 0: the run's own value, a claim that is true by construction;
- deviation +-0.5 %, 1 %, 2 %, 5 %, 10 %, 20 %: every metric of the run moved by that share, up and down.

Each row is scored by `src/score_run.py` (the Tier 2 calculation of `src/scoring.py`, and the composite with the run's own Tier 1,
3 and 4 inputs). The claims are made up by this script: they are not claims of a paper, and a row says nothing about the rate of
false positives or false negatives in the real world. Every number in the output is computed here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src import config
from src.score_run import load_run, score_run
from src.scoring import Tier2MetricsEvaluator

RESULTS_PATH = project_root / "data" / "tolerance_probe" / "results.json"
DOC_PATH = project_root / "docs" / "TOLERANCE_PROBE.md"
CANDIDATE_RUNS = project_root / "data" / "candidates" / "runs" / "evaluation.json"
DEVIATION_PERCENTS = (0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0)
# (paper id, stored run folder relative to the repository root): completed runs of the repository, read only
RUNS: tuple[tuple[str, str], ...] = (
    ("paper_003", "data/pilot3_runs/paper_003"),
    ("paper_006", "data/pilot2_runs/paper_006"),
    ("paper_006", "data/pilot3_runs/paper_006"),
    ("paper_006", "data/cpu_runs/paper_006"),
    ("paper_006", "data/memory_runs/paper_006_run2"),
    ("paper_102", "data/pilot4_runs/paper_102"),
)
CORPUS_FILES = ("data/seed_papers.json", "data/corpus_expansion/papers.json", "data/candidates/papers.json")
DECISIONS_PATH = project_root / "data" / "claims" / "review_decisions.json"
WARNING = ("These are hand-made claims, not an error of a real paper. The false-positive and false-negative rates of the scorer "
           "in the real world have not been measured.")


def deviations() -> list[float]:
    """The signed deviations in percent, in the order of the table: 0, then -0.5, +0.5, -1, +1 and so on."""
    out = [0.0]
    for percent in DEVIATION_PERCENTS[1:]:
        out += [-percent, percent]
    return out


def perturb(metrics: dict[str, float], percent: float) -> dict[str, float]:
    """The claims of one row: every metric of the run moved by `percent` percent of its own value."""
    return {name: value * (1.0 + percent / 100.0) for name, value in metrics.items()}


def licenses() -> dict[str, str]:
    found: dict[str, str] = {}
    for name in CORPUS_FILES:
        path = project_root / name
        if path.is_file():
            for entry in json.loads(path.read_text(encoding="utf-8")):
                found.setdefault(entry["paper_id"], entry.get("license") or "")
    return found


def candidate_runs() -> list[tuple[str, str]]:
    """(paper id, run folder) of every candidate run that passed, from the stored results of the candidate runs."""
    if not CANDIDATE_RUNS.is_file():
        return []
    results = json.loads(CANDIDATE_RUNS.read_text(encoding="utf-8"))["results"]
    return [(r["paper_id"], f"data/candidates/runs/{r['paper_id']}") for r in results if r["passed"]]


def label_counts(claim_details: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {"MATCHED": 0, "PARTIAL": 0, "DIVERGED": 0, "NOT FOUND": 0}
    for detail in claim_details.values():
        if detail["reproduced"] is None:
            counts["NOT FOUND"] += 1
        else:
            counts["MATCHED" if detail["points"] == 1.0 else "PARTIAL" if detail["points"] == 0.5 else "DIVERGED"] += 1
    return counts


def matched_limits(metrics: dict[str, float]) -> dict[str, dict[str, float]]:
    """For each metric alone: the largest tested deviation, down and up, at which Tier 2 still gives it a full point."""
    limits: dict[str, dict[str, float]] = {}
    for name, value in metrics.items():
        limit = {"down": 0.0, "up": 0.0}
        for percent in DEVIATION_PERCENTS[1:]:
            for direction, sign in (("down", -1.0), ("up", 1.0)):
                _, details, _ = Tier2MetricsEvaluator.evaluate({name: value * (1.0 + sign * percent / 100.0)}, {name: value})
                if details[name]["matches"]:
                    limit[direction] = percent
        limits[name] = limit
    return limits


def probe_run(paper_id: str, license_name: str, run_dir: Path) -> dict[str, Any]:
    """All rows of one stored run. The run's metrics come from its run report; nothing is run."""
    record, report = load_run(run_dir)
    metrics = {k: float(v) for k, v in (report.get("metrics") or {}).items() if isinstance(v, (int, float))}
    rows = []
    for percent in deviations():
        scored = score_run(paper_id, license_name, perturb(metrics, percent), record, report, run_dir)
        breakdown = scored["breakdown"]
        rows.append({"deviation_percent": percent, "tier2": round(breakdown.tier2_metrics, 2),
                     "labels": label_counts(scored["claim_details"]), "total": breakdown.total_score,
                     "status": breakdown.status_label})
    return {"paper_id": paper_id, "run_dir": run_dir.relative_to(project_root).as_posix(), "metrics": metrics,
            "matched_limits": matched_limits(metrics), "rows": rows}


def accepted_claims_that_match(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Accepted claims of the owner whose question ID is a metric of a probed run. The scorer matches by question ID only."""
    if not DECISIONS_PATH.is_file():
        return []
    claims = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))["claims"]
    found = []
    for run in runs:
        for claim in claims:
            if claim["paper_id"] == run["paper_id"] and claim["query_id"] in run["metrics"]:
                found.append({"paper_id": run["paper_id"], "run_dir": run["run_dir"], "query_id": claim["query_id"],
                              "claimed": claim["value"], "reproduced": run["metrics"][claim["query_id"]]})
    return found


def build() -> dict[str, Any]:
    license_of = licenses()
    probed = [probe_run(pid, license_of.get(pid, ""), project_root / folder)
              for pid, folder in (*RUNS, *candidate_runs())]
    accepted = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))["claims"] if DECISIONS_PATH.is_file() else []
    return {"note": WARNING, "tolerance": config.DEFAULT_TOLERANCE, "runs": probed,
            "accepted_claims_total": len(accepted),
            "accepted_claims_matching_a_probed_run": accepted_claims_that_match(probed)}


def _group(runs: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Runs with identical metrics and identical rows share one table."""
    groups: list[list[dict[str, Any]]] = []
    for run in runs:
        for group in groups:
            if group[0]["metrics"] == run["metrics"] and group[0]["rows"] == run["rows"]:  # same values, same decisions
                group.append(run)
                break
        else:
            groups.append([run])
    return groups


def _first_change(rows: list[dict[str, Any]], sign: int) -> str:
    """The smallest deviation of the given sign whose status differs from the status of the true claim."""
    base = rows[0]["status"]
    for row in sorted((r for r in rows if r["deviation_percent"] * sign > 0), key=lambda r: abs(r["deviation_percent"])):
        if row["status"] != base:
            return f"{row['deviation_percent']:+g} % ({base} -> {row['status']})"
    return "none up to 20 %"


def render(data: dict[str, Any]) -> str:
    tolerance = data["tolerance"]
    lines = [
        "<!-- Generated by `python scripts/tolerance_probe.py`; do not edit by hand. -->",
        "# Tolerance probe", "",
        ("Issue #440. **" + WARNING + "** The rows below are produced by moving the value of a real, completed run by a chosen "
         "share and asking the scorer what it decides. They show where the scorer changes its decision, nothing more."), "",
        "## 1. The tolerance rule (`src/scoring.py`, `Tier2MetricsEvaluator.evaluate`)", "",
        (f"Tolerance `t = DEFAULT_TOLERANCE = {tolerance}` (`src/config.py`). For each claim that is found in the run's output "
         "(matched by its question ID, never guessed), with `claimed` and `reproduced`:"), "",
        ("- `abs_diff = |reproduced - claimed|`, `rel_error = abs_diff / max(|claimed|, 1e-6)`: the error is relative to the "
         "**claimed** value."),
        ("- A metric whose name contains one of `sec`, `second`, `time`, `latency`, `ms`, `runtime`, `duration` (substring, lower "
         "case) is a time metric: 1 point if `rel_error <= t`, 0.5 point if `rel_error <= 2t`, else 0."),
        ("- Any other metric: 1 point if `rel_error <= t`, or if the claimed value is in [0, 1] and `abs_diff <= t`; 0.5 point if "
         "`rel_error <= 2t`, or if the claimed value is in [0, 1] and `abs_diff <= 2t`; else 0."),
        ("- Tier 2 = points earned / number of claims x 100. A claim whose name is not in the output earns 0; no claims gives the "
         "neutral 70.0; claims with an empty output give 0."),
        (f"- Composite = {config.TIER1_BUILD_WEIGHT} Tier 1 + {config.TIER2_METRICS_WEIGHT} Tier 2 + "
         f"{config.TIER3_STABILITY_WEIGHT} Tier 3 + {config.TIER4_ARTIFACTS_WEIGHT} Tier 4. Status (`calculate_composite_score`): "
         f"Failed if Tier 1 < 50 or the run failed; Verified if total >= {config.SCORE_VERIFIED_THRESHOLD:g}, Tier 2 >= 80 and "
         f"Tier 1 >= 90; Partially Verified if total >= {config.SCORE_PARTIALLY_VERIFIED_THRESHOLD:g} (Needs Review instead when "
         "Tier 2 < 50 and Tier 1 >= 80); otherwise Needs Review when Tier 1 >= 75, else Failed."), "",
        "## 2. What was probed", "",
        ("Every row moves **all** metrics of the run by the same share at once. The claim of deviation 0 is the run's own value (a "
         "true claim by construction). Tier 1, 3 and 4 are those of the stored run (`src/score_run.py`; the staged repository is not "
         "available, so the README counts as absent in Tier 4, the same for every row of a run). Runs with identical metrics and "
         "identical rows share one table."), "",
    ]
    for number, group in enumerate(_group(data["runs"]), start=1):
        first = group[0]
        same = "" if len(group) == 1 else " (identical metrics, identical rows)"
        metrics = ", ".join(f"{k} = {v:g}" for k, v in first["metrics"].items())
        lines += [f"### 2.{number} {', '.join(sorted({r['paper_id'] for r in group}))}", "",
                  "Runs: " + ", ".join(f"`{r['run_dir']}`" for r in group) + same, "",
                  f"Metrics of the run (as printed): {metrics}", "",
                  "| Deviation of the claim | Tier 2 | MATCHED | PARTIAL | DIVERGED | Composite | Status |",
                  "|---|---|---|---|---|---|---|"]
        for row in first["rows"]:
            counts = row["labels"]
            percent = "0 (the run's own value)" if row["deviation_percent"] == 0 else f"{row['deviation_percent']:+g} %"
            lines.append(f"| {percent} | {row['tier2']} | {counts['MATCHED']} | {counts['PARTIAL']} | {counts['DIVERGED']} | "
                         f"{row['total']} | {row['status']} |")
        lines += ["", (f"First deviation that changes the status of the true claim: downward {_first_change(first['rows'], -1)}; "
                        f"upward {_first_change(first['rows'], 1)}."), "",
                  ("Each metric alone: the largest tested deviation at which it still earns a full point (MATCHED); a metric whose "
                   "value is between 0 and 1 is judged by the absolute difference as well, which makes a small value lenient."), "",
                  "| Metric | Value | Largest MATCHED deviation, claim moved down | Largest MATCHED deviation, claim moved up |",
                  "|---|---|---|---|"]
        for name, limit in first["matched_limits"].items():
            down = "none of the tested" if limit["down"] == 0 else f"-{limit['down']:g} %"
            up = "none of the tested" if limit["up"] == 0 else f"+{limit['up']:g} %"
            lines.append(f"| {name} | {first['metrics'][name]:g} | {down} | {up} |")
        lines.append("")
    matches = data["accepted_claims_matching_a_probed_run"]
    lines += ["## 3. A real accepted claim that matches a run", ""]
    if matches:
        lines += ["| Paper | Run | Question ID | Accepted claim | Run's value |", "|---|---|---|---|---|"]
        lines += [f"| {m['paper_id']} | `{m['run_dir']}` | {m['query_id']} | {m['claimed']} | {m['reproduced']} |" for m in matches]
    else:
        lines += [(f"None. The owner accepted {data['accepted_claims_total']} claims; the scorer matches a claim to the output by "
                   "its question ID, and no accepted claim has the question ID of a metric of any probed run (the runs print "
                   "`rmse`, `accuracy`, `auroc` and so on; the accepted claims are named after the model, for example "
                   "`ft_transformer_rmse`). Whether a run's value belongs to an accepted claim is therefore **not verified**, "
                   "and no row compares them.")]
    lines += ["", "## 4. What this shows, and what it does not", "",
              ("- It shows the tolerance as implemented: where, for these values, a hand-moved claim stops being MATCHED, becomes "
               "PARTIAL and then DIVERGED, and at which deviation the status of the paper changes."),
              ("- The error is measured relative to the claimed value, so a claim moved down by x % is judged on a slightly "
               "different error than a claim moved up by x % (compare the paired rows)."),
              ("- It does **not** show how often the scorer is wrong on real papers: the claims are made by hand from the run's "
               "own value, the metric extractor and the question-ID matching are not exercised, and no paper's real error is in "
               "these rows."),
              "- It does not show that any run reproduces a claim of its paper.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe the tolerance of the Tier 2 scorer on real stored runs.")
    parser.add_argument("--check", action="store_true", help="fail if the committed files differ from the stored runs")
    args = parser.parse_args(argv)
    data = build()
    text = json.dumps(data, indent=2) + "\n"
    document = render(data)
    if args.check:
        same = (RESULTS_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") == text
                and DOC_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") == document)
        print("tolerance probe files match the stored runs" if same else "tolerance probe files DIFFER from the stored runs")
        return 0 if same else 1
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(text, encoding="utf-8", newline="\n")
    DOC_PATH.write_text(document, encoding="utf-8", newline="\n")
    print(f"wrote {RESULTS_PATH.relative_to(project_root)} and {DOC_PATH.relative_to(project_root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
