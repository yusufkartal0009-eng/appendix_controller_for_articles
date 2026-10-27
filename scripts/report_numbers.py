#!/usr/bin/env python3
"""Render the numbers of the final report from the stored files (AGENTS.md §6.5, #221).

    python scripts/report_numbers.py              # print every block
    python scripts/report_numbers.py --write      # replace the blocks in docs/report/REPORT.md
    python scripts/report_numbers.py --check      # exit 1 if a block in the report differs from its rendering

A block in the report is the text between `<!-- numbers:NAME:start -->` and `<!-- numbers:NAME:end -->`. Blocks:

- `pilot1`: Pilot 1 rates and failure categories (`data/pilot_runs/measurements.json`, `failure_categories.json`)
- `pilot2`: Pilot 1 and Pilot 2 side by side (`data/pilot2_runs/comparison.json`, from scripts/pilot_compare.py)
- `pilot2measurements`: the rates and the per-paper table of Pilot 2 (`data/pilot2_runs/measurements.md`)
- `pilot2summary`: one sentence with the three rates of Pilot 2 next to Pilot 1's (`data/pilot2_runs/comparison.json`)
- `pilot3`, `pilot3measurements`, `pilot3summary`, `pilot3failures`: the same for Pilot 3, with all three pilots side by
  side (`data/pilot3_runs/`, #292)
- `abstractnumbers`: the same sentence as `pilot3summary`, under its own name because a block name can be used once
  per document (the abstract and section 6.1a both show it; #299)
- `pilot2failures`: per paper of Pilot 2, the failure category, the phase, and the deciding log line
  (`data/pilot2_runs/failure_categories.json`)
- `memoryruns`: per paper, the outcome and the memory limit of Pilot 3 and of the memory re-run
  (`data/memory_runs/`, `data/pilot3_runs/`; `scripts/memory_runs.py`, #327)
- `syntheticcontrol`: the synthetic control paper: two runs, a true and a false claim, and the bug it found
  (`data/synthetic_control/result.json`, `result_before_fix.json`; #313)
- `stability`: repeated runs of the completed papers (`scripts/run_stability.py`, #329)
- `goldexpansion`: the extended gold set: agreement of the two passes and the owner's answers
  (`data/gold_expansion/claims/consistency.json`, `data/gold_expansion/gold/`; #315)
- `pilot4`: Pilot 4 (six new papers): strict and corrected rates next to Pilots 1 to 3, the per-paper table with the README
  command and every correction, and the failure categories (`data/pilot4_runs/summary.md`, `scripts/pilot4_report.py`, #376)
- `extraction`: the claim extraction: quote guard, A/B agreement, the owner's review, and the gold set
  (`data/claims/guard_report.json`, `consistency.json`, `review_decisions.json`, `gold_score_pass_A.json`)
- `multiseed`: Tier 3 from real seed runs: the synthetic papers and the real papers (`data/synthetic_seeds/result.json`,
  `data/multi_seed_runs/*/multi_seed_summary.json`; #48)
- `gpucheck`: the synthetic paper that needs a modern PyTorch, run with the local GPU (`data/gpu_check/result.json`; #169)
- `diagnosisvalidation`: the failure classifier against hand-written labels (`data/diagnosis_validation/results.json`; #36)
- `fieldanalysis`: the week 6 field analysis over 12 papers (`data/field_analysis/result.json`; #413)
- `rescience`: the selection of external-validation articles (`data/external_validation/evaluation.json`; #400)
- `candidateruns`: the 14 selected candidate papers run once in the sandbox: tried, passed, Wilson interval, causes
  (`data/candidates/runs/evaluation.json`; #437)
- `candidateround2`: the repair round of the candidates: first attempt, with repair, considered, run, Wilson intervals
  (`data/candidates/round2/*/repair_log.json`; #457)
- `autosearch3`: the automatic search of round 3: checked, run, K1, K2 and both with Wilson intervals, causes of the failures
  (`data/auto_search3/evaluation.json`; #473)
- `autosearch4`: the automatic search of round 4: checked, run, K1, K2 v1, K2 v2 and both with Wilson intervals, causes of the failures
  (`data/auto_search4/evaluation.json`; #521)
- `toleranceprobe`: where the Tier 2 decision changes when a hand-made claim is moved away from a real run's value
  (`data/tolerance_probe/results.json`; #442)

- `realverdicts`: what the scorer decides on the real stored runs next to the accepted claims, and the K2 control
  (`data/real_verdicts/verdicts.json`, `scripts/real_verdicts.py`; #494)
- `pilotintervals`: pilot success of the seed papers, the new papers and all twelve, with Wilson intervals
  (`data/field_analysis/result.json`; #503)
- `cleanclone`: the fresh run of `paper_006` from a clean clone, read from the walk-through document
  (`docs/evidence/clean_clone/WALKTHROUGH.md`, Update 2; #441, #503)

Nothing in a block is typed by hand: a hand edit makes `--check` (and its test) fail.
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

from scripts import memory_runs, run_stability, tolerance_probe
from scripts.candidates_build import failure_cause, round2_numbers, wilson_interval

REPORT_PATH = project_root / "docs" / "report" / "REPORT.md"
DATA = project_root / "data"
HEADER = "<!-- Generated by scripts/report_numbers.py from {sources}; do not edit by hand. -->"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _rate(rate: dict[str, Any]) -> str:
    return f"{rate['count']} / {rate['of']} ({rate['rate']})"


def pilot1_block(data: Path = DATA) -> str:
    m = _load(data / "pilot_runs" / "measurements.json")
    c = _load(data / "pilot_runs" / "failure_categories.json")
    lines = [HEADER.format(sources="data/pilot_runs/measurements.json and failure_categories.json"), "",
             "| Measure (Pilot 1) | Count (rate) |", "|---|---|",
             f"| Install success | {_rate(m['install_success_rate'])} |",
             f"| Run success | {_rate(m['run_success_rate'])} |",
             f"| Pilot success | {_rate(m['pilot_success_rate'])} |",
             f"| Valid runs | {_rate(m['valid_runs'])} |", "",
             "| Failure category (Pilot 1) | Papers |", "|---|---|"]
    lines += [f"| `{name}` | {count} |" for name, count in c["counts"].items() if count]
    return "\n".join(lines)


def pilot2_block(data: Path = DATA) -> str:
    comparison = _load(data / "pilot2_runs" / "comparison.json")
    body = (data / "pilot2_runs" / "comparison.md").read_text(encoding="utf-8")
    body = "\n".join(line for line in body.splitlines() if not line.startswith("<!--")).strip()
    assert comparison["rates"], "empty comparison"
    return "\n".join([HEADER.format(sources="data/pilot2_runs/comparison.json (scripts/pilot_compare.py)"), "", body])


def pilot2measurements_block(data: Path = DATA) -> str:
    source = data / "pilot2_runs" / "measurements.md"
    if not source.is_file():
        raise FileNotFoundError(f"{source} not found")
    lines = [line for line in source.read_text(encoding="utf-8").splitlines() if not line.startswith("<!--")]
    header = HEADER.format(sources="data/pilot2_runs/measurements.md (scripts/pilot_measurements.py)")
    return "\n".join([header, "", "\n".join(lines).strip()])


def pilot2summary_block(data: Path = DATA) -> str:
    rates = _load(data / "pilot2_runs" / "comparison.json")["rates"]

    def pair(key: str) -> str:
        return f"{_rate(rates[key]['pilot2'])} (Pilot 1: {_rate(rates[key]['pilot1'])})"
    sentence = (f"Install success: {pair('install_success_rate')}. Run success: {pair('run_success_rate')}. "
                f"Pilot success: {pair('pilot_success_rate')}.")
    return "\n".join([HEADER.format(sources="data/pilot2_runs/comparison.json"), "", sentence])


def pilot2failures_block(data: Path = DATA, runs: str = "pilot2_runs") -> str:
    papers = _load(data / runs / "failure_categories.json")["papers"]
    lines = [HEADER.format(sources=f"data/{runs}/failure_categories.json"), "",
             "| Paper | Category | Phase | Deciding line |", "|---|---|---|---|"]
    for p in papers:
        category = p["category"] or p["other_name"] or "none"
        if p["category"] == "OTHER" and p["other_name"]:
            category = f"OTHER ({p['other_name']})"
        evidence = p.get("evidence") or {}
        line = str(evidence.get("line") or "").replace("|", "\\|").replace("`", "'").strip()
        lines.append(f"| `{p['paper_id']}` | {'success' if p['pilot_success'] else category} | "
                     f"{p['phase'] or 'n/a'} | {('`' + line[:240] + '`') if line and not p['pilot_success'] else 'n/a'} |")
    return "\n".join(lines)


def pilot3_block(data: Path = DATA) -> str:
    comparison = _load(data / "pilot3_runs" / "comparison.json")
    body = (data / "pilot3_runs" / "comparison.md").read_text(encoding="utf-8")
    body = "\n".join(line for line in body.splitlines() if not line.startswith("<!--")).strip()
    assert comparison["rates"], "empty comparison"
    return "\n".join([HEADER.format(sources="data/pilot3_runs/comparison.json (scripts/pilot_compare.py --pilot3-dir)"), "", body])


def pilot3measurements_block(data: Path = DATA) -> str:
    source = data / "pilot3_runs" / "measurements.md"
    if not source.is_file():
        raise FileNotFoundError(f"{source} not found")
    lines = [line for line in source.read_text(encoding="utf-8").splitlines() if not line.startswith("<!--")]
    header = HEADER.format(sources="data/pilot3_runs/measurements.md (scripts/pilot_measurements.py)")
    return "\n".join([header, "", "\n".join(lines).strip()])


def pilot3summary_block(data: Path = DATA) -> str:
    rates = _load(data / "pilot3_runs" / "comparison.json")["rates"]

    def triple(key: str) -> str:
        return f"{_rate(rates[key]['pilot3'])} (Pilot 1: {_rate(rates[key]['pilot1'])}; Pilot 2: {_rate(rates[key]['pilot2'])})"
    sentence = (f"Install success: {triple('install_success_rate')}. Run success: {triple('run_success_rate')}. "
                f"Pilot success: {triple('pilot_success_rate')}.")
    return "\n".join([HEADER.format(sources="data/pilot3_runs/comparison.json"), "", sentence])


def pilot3failures_block(data: Path = DATA) -> str:
    return pilot2failures_block(data, "pilot3_runs")


def memoryruns_block(data: Path = DATA) -> str:
    rows = memory_runs.measure(data)
    assert rows, "no memory re-run records"
    header = HEADER.format(sources="data/memory_runs/ and data/pilot3_runs/ (scripts/memory_runs.py)")
    return "\n".join([header, "", memory_runs.to_sentence(rows)])


def syntheticcontrol_block(data: Path = DATA) -> str:
    result = _load(data / "synthetic_control" / "result.json")
    before = _load(data / "synthetic_control" / "result_before_fix.json")["scores"]
    after, same = result["scores"], result["comparison"]["same"]
    files = result["comparison"]["files"]["log"]

    def row(label: str, scores: dict[str, Any]) -> str:
        t, f = scores["true_claim"], scores["false_claim"]
        return (f"| {label} | {t['tier2_metrics']:g} / {t['total_score']:g} ({t['status_label']}) | "
                f"{f['tier2_metrics']:g} / {f['total_score']:g} ({f['status_label']}) |")
    summary = (f"Metric `{result['metric']}`, reproduced {after['true_claim']['reproduced'][result['metric']]:g} in both runs; "
               f"true claim {after['true_claim']['claimed']:g}, false claim {after['false_claim']['claimed']:g}. "
               f"Two runs agree on status ({str(same['run_status']).lower()}), exit code ({str(same['exit_code']).lower()}), "
               f"and metrics ({str(same['metrics']).lower()}); log files identical: {files['identical']} of {files['files']}.")
    lines = [HEADER.format(sources="data/synthetic_control/result.json and result_before_fix.json"), "", summary, "",
             "| Scored | True claim: Tier 2 / total | False claim: Tier 2 / total |", "|---|---|---|",
             row("Before the fix (a repository without requirements counted as a failed install)", before),
             row("After the fix", after)]
    return "\n".join(lines)


def stability_block(data: Path = DATA) -> str:
    result = run_stability.measure(data)
    assert result, "no repeated runs"
    header = HEADER.format(sources="data/pilot2_runs/, data/pilot3_runs/, data/memory_runs/ (scripts/run_stability.py)")
    return "\n".join([header, "", run_stability.to_markdown(result), "", run_stability.to_sentence(result)])


def goldexpansion_block(data: Path = DATA) -> str:
    consistency = _load(data / "gold_expansion" / "claims" / "consistency.json")
    gold_dir = data / "gold_expansion" / "gold"
    answers = len(list(gold_dir.glob("*.json"))) if gold_dir.is_dir() else 0
    statement = ("the owner's answers exist, see docs/GOLD_SET_EXPANSION.md" if answers
                 else "the owner's answers do not exist yet, so no precision or recall is computed or claimed")
    sentence = (f"Extended gold set: {consistency['questions']} new questions; pass A and the blind pass B agree on "
                f"{consistency['agreements']} of {consistency['questions']} (disagreements: {consistency['disagreements']}); {statement}.")
    return "\n".join([HEADER.format(sources="data/gold_expansion/"), "", sentence])


def pilot4_block(data: Path = DATA) -> str:
    source = data / "pilot4_runs" / "summary.md"
    if not source.is_file():
        raise FileNotFoundError(f"{source} not found")
    lines = [line for line in source.read_text(encoding="utf-8").splitlines() if not line.startswith("<!--")]
    header = HEADER.format(sources="data/pilot4_runs/summary.md (scripts/pilot4_report.py)")
    return "\n".join([header, "", "\n".join(lines).strip()])


def extraction_block(data: Path = DATA) -> str:
    guard = _load(data / "claims" / "guard_report.json")
    consistency = _load(data / "claims" / "consistency.json")
    review = _load(data / "claims" / "review_decisions.json")
    gold = _load(data / "claims" / "gold_score_pass_A.json")
    summary = review["summary"]
    lines = [HEADER.format(sources="data/claims/{guard_report,consistency,review_decisions,gold_score_pass_A}.json"), "",
             "| Claim extraction | Value |", "|---|---|",
             f"| Questions (6 papers) | {consistency['questions']} |",
             f"| Answers over both passes | {guard['answers']} |",
             f"| Claims found | {guard['found_claims']} (all from a table: {guard['from_table']}) |",
             f"| Quote guard: quote and value found in the paper text | {guard['auto_quote_match']} / {guard['found_claims']} (unverified: {guard['unverified']}) |",
             f"| Passes A and B agree | {consistency['agreements']} / {consistency['questions']} (disagreements: {consistency['disagreements']}) |",
             f"| Reviewed by the owner | accepted {summary.get('accepted', 0)}, rejected {summary.get('rejected', 0)}, pending {summary.get('pending', 0)} |",
             f"| Gold set (pass A), scored questions | {gold['scored_questions']} |",
             f"| True positives / false positives / false negatives / true negatives | {gold['tp']} / {gold['fp']} / {gold['fn']} / {gold['tn']} |",
             f"| Precision / recall | {gold['precision']} / {gold['recall']} |",
             f"| Regression cases (must be true negatives) | {', '.join(f'`{k}`: {v}' for k, v in gold['regression_cases'].items())} |"]
    return "\n".join(lines)


def _fmt(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def _metric_rows(label: str, summary: dict[str, Any]) -> list[str]:
    rows = []
    for name, m in sorted(summary["metrics"].items()):
        rows.append(f"| {label} | `{name}` | {m['n']} | {_fmt(m['mean'])} | {_fmt(m['std_population'])} | "
                    f"{_fmt(m['std_sample'])} | {m['cv'] * 100:.3f}% |")
    return rows


def multiseed_block(data: Path = DATA) -> str:
    synthetic = _load(data / "synthetic_seeds" / "result.json")
    lines = [HEADER.format(sources="data/synthetic_seeds/result.json and data/multi_seed_runs/*/multi_seed_summary.json"), "",
             "| Paper | Metric | Seed runs | Mean | Std (population) | Std (sample) | CV |", "|---|---|---|---|---|---|---|"]
    rows: list[tuple[str, Any, Any, str, str]] = []  # label, successful runs, score, basis, deciding metric and each metric alone
    for paper_id, result in synthetic["papers"].items():
        summary = _load(data / "synthetic_seeds" / paper_id / "multi_seed_summary.json")
        lines += _metric_rows(f"`{paper_id}` (synthetic)", summary)
        rows.append((f"`{paper_id}` (synthetic)", result["successful_seed_runs"], result["tier3"]["score"],
                     result["tier3"]["basis"], _alone(summary)))
    real_dir = data / "multi_seed_runs"
    for path in sorted(real_dir.glob("*/multi_seed_summary.json")) if real_dir.is_dir() else []:
        summary = _load(path)
        lines += _metric_rows(f"`{summary['paper_id']}`", summary)
        rows.append((f"`{summary['paper_id']}`", f"{summary['successful_seed_runs']} of {len(summary['runs'])}",
                     summary["tier3"]["score"], summary["tier3"]["basis"], _alone(summary)))
    lines += ["", "| Paper | Successful seed runs | Tier 3 score | Basis | Decided by; score of each metric alone |",
              "|---|---|---|---|---|"]
    lines += [f"| {label} | {runs} | {score} | {basis} | {alone} |" for label, runs, score, basis, alone in rows]
    match = ", ".join(f"`{pid}` {'yes' if r['comparison']['all_match'] else 'NO'}" for pid, r in synthetic["papers"].items())
    lines += ["", f"The synthetic papers' summary equals the mean and standard deviation computed on the host from the same seeds: {match}."]
    return "\n".join(lines)


def _alone(summary: dict[str, Any]) -> str:
    by_metric = summary.get("tier3_by_metric")
    if not by_metric:
        return "n/a"
    decided = summary["tier3"].get("decided_by")
    alone = ", ".join(f"`{name}` {m['score_if_this_metric_alone']}" for name, m in sorted(by_metric.items()))
    return f"`{decided}`; {alone}"


def gpucheck_block(data: Path = DATA) -> str:
    result = _load(data / "gpu_check" / "result.json")
    out = result["container_output"]
    gpu = result["gpu_block_of_run_report"] or {}
    devices = ", ".join(f"{d['name']} (driver {d['driver']}, {d['memory_total_mib']} MiB)" for d in gpu.get("devices", [])) or "none"
    lines = [HEADER.format(sources="data/gpu_check/result.json"), "",
             "| Fact | Value |", "|---|---|",
             f"| Requirement of the synthetic paper | `{result['requirement']}` |",
             f"| torch / CUDA build seen in the container | {out.get('torch_version', 'n/a')} / {out.get('torch_cuda_version', 'n/a')} |",
             f"| Device seen by torch | {out.get('device_name', 'n/a')}, capability {out.get('device_capability', 'n/a')} |",
             f"| Tensor operation on | {out.get('tensor_device', 'n/a')}; result equal to the CPU result: {out.get('matmul_matches_cpu', 'n/a')} |",
             (f"| Run report `gpu` block | requested {gpu.get('requested')}, available {gpu.get('available')}, used {gpu.get('used')}; "
             f"devices: {devices}; peak GPU memory {gpu.get('peak_memory_used_mib')} MiB |"),
             f"| Bundled wheels | {result['bundled_packages_gib']} GiB, bundling took {result['bundle_seconds']} s |",
             f"| Sandbox time (install and run) | {result['sandbox_duration_seconds']} s |",
             f"| Checks passed | {sum(result['checks'].values())} of {len(result['checks'])} |"]
    failed = [name for name, ok in result["checks"].items() if not ok]
    if failed:
        lines.append(f"| Checks failed | {', '.join(failed)} |")
    return "\n".join(lines)


def diagnosisvalidation_block(data: Path = DATA) -> str:
    summary = _load(data / "diagnosis_validation" / "results.json")["summary"]

    def frac(d: dict[str, Any]) -> str:
        return f"{d['correct']} / {d['of']}"

    real, synthetic = summary["real"], summary["synthetic"]
    lines = [HEADER.format(sources="data/diagnosis_validation/results.json"), "",
             "| Set | Items | Category correct | Name of an OTHER correct | Phase correct | All levels correct | Wrong |",
             "|---|---|---|---|---|---|---|",
             f"| Real runs | {real['n']} | {frac(real['category'])} | {frac(real['name'])} | {frac(real['phase'])} | {frac(real['all'])} | {', '.join(real['wrong']) or 'none'} |",
             f"| Synthetic probes | {synthetic['n']} | {frac(synthetic['category'])} | {frac(synthetic['name'])} | {frac(synthetic['phase'])} | {frac(synthetic['all'])} | {', '.join(synthetic['wrong']) or 'none'} |"]
    return "\n".join(lines)


def fieldanalysis_block(data: Path = DATA) -> str:
    result = _load(data / "field_analysis" / "result.json")

    def frac(d: dict[str, Any]) -> str:
        return f"{d['k']} / {d['n']}"

    lines = [HEADER.format(sources="data/field_analysis/result.json (scripts/field_analysis.py)"), "",
             "| Pool | Run | Setup success | Run success | Pilot success | Concluded autonomously | Succeeded autonomously |",
             "|---|---|---|---|---|---|---|"]
    for pool, runs in result["rates"].items():
        for which in ("first", "final"):
            r, a = runs[which], result["autonomy"][pool][which]
            lines.append(f"| {pool} | {which} | {frac(r['install_success'])} | {frac(r['run_success'])} | {frac(r['pilot_success'])} | "
                         f"{frac(a['concluded_autonomously'])} | {frac(a['succeeded_autonomously'])} |")
    accepted = ", ".join(f"{pool} {frac(v['papers_with_an_accepted_claim_I4'])}" for pool, v in result["autonomy"].items())
    lines += ["", f"Papers with at least one claim accepted by a person (not part of the autonomy rate): {accepted}."]
    return "\n".join(lines)


def rescience_block(data: Path = DATA) -> str:
    evaluation = _load(data / "external_validation" / "evaluation.json")
    stopped: dict[str, int] = {}
    for article in evaluation["articles"]:
        if not article["passed"]:
            stopped[article["failed_rule"]] = stopped.get(article["failed_rule"], 0) + 1
    by_rule = ", ".join(f"{rule} {count}" for rule, count in sorted(stopped.items(), key=lambda kv: (-kv[1], kv[0])))
    return "\n".join([HEADER.format(sources="data/external_validation/evaluation.json"), "",
                      (f"Articles of ReScience C evaluated: {evaluation['evaluated']}; selected: {evaluation['selected']}. "
                      f"Rule that stopped each article (the first failed rule): {by_rule}.")])


def candidateruns_block(data: Path = DATA) -> str:
    results = _load(data / "candidates" / "runs" / "evaluation.json")["results"]
    ran = [r for r in results if r["category"] != "command_incomplete"]
    passed = [r for r in results if r["passed"]]
    low, high = wilson_interval(len(passed), len(results))
    causes: dict[str, int] = {}
    for r in results:
        if not r["passed"]:
            causes[failure_cause(r)] = causes.get(failure_cause(r), 0) + 1
    by_cause = ", ".join(f"{name} {count}" for name, count in sorted(causes.items(), key=lambda kv: (-kv[1], kv[0])))
    names = ", ".join(r["paper_id"] for r in passed) or "none"
    return "\n".join([HEADER.format(sources="data/candidates/runs/evaluation.json (scripts/candidate_runs.py)"), "",
                      (f"Selected candidates: {len(results)}; run once in the sandbox: {len(ran)}; passed: {len(passed)} ({names}). "
                       f"Pilot ratio {len(passed)} / {len(results)}, Wilson 95 % interval {100 * low:.1f} % to {100 * high:.1f} %. "
                       f"Cause of the failures (rules of the failure classifier): {by_cause}. "
                       "This is a selected list, not a sample; it is not a success rate.")])


def candidateround2_block(data: Path = DATA) -> str:
    n = round2_numbers(_load(data / "candidates" / "runs" / "evaluation.json"), data / "candidates" / "round2")
    lo1, hi1 = wilson_interval(n["first_passed"], n["first_total"])
    lo2, hi2 = wilson_interval(len(n["repaired_passed"]), n["repaired_total"])
    lo3, hi3 = wilson_interval(len(n["passed"]), len(n["considered"]))
    names = ", ".join(n["passed"]) or "none"
    return "\n".join([HEADER.format(sources="data/candidates/round2/*/repair_log.json (scripts/candidate_round2.py)"), "",
                      (f"First attempt without repair (round 1): {n['first_passed']} of {n['first_total']}, Wilson 95 % interval "
                       f"{100 * lo1:.1f} % to {100 * hi1:.1f} %. With repair (round 2, the same {n['repaired_total']}): "
                       f"{len(n['repaired_passed'])} of {n['repaired_total']}, {100 * lo2:.1f} % to {100 * hi2:.1f} % ({names}). "
                       f"Considered in round 2 (those and the risky candidates that qualified): {len(n['passed'])} of "
                       f"{len(n['considered'])}, {100 * lo3:.1f} % to {100 * hi3:.1f} %; run in the sandbox at least once: "
                       f"{len(n['ran'])}. This is a selected list, not a sample; it is not a success rate.")])


def autosearch3_block(data: Path = DATA) -> str:
    document = _load(data / "auto_search3" / "evaluation.json")
    ran = [c for c in document["candidates"] if c.get("k1")]
    total = len(ran)
    k1 = [c for c in ran if c["k1"]["k1_passed"]]
    k2 = [c for c in ran if (c.get("k2") or {}).get("passed")]
    both = [c for c in k1 if (c.get("k2") or {}).get("passed")]

    def interval(count: int) -> str:
        low, high = wilson_interval(count, total)
        return f"{count} of {total}, Wilson 95 % interval {100 * low:.1f} % to {100 * high:.1f} %"

    causes: dict[str, int] = {}
    for c in ran:
        if not c["k1"]["k1_passed"]:
            causes[c["k1"]["category"]] = causes.get(c["k1"]["category"], 0) + 1
    by_cause = ", ".join(f"{name} {count}" for name, count in sorted(causes.items(), key=lambda kv: (-kv[1], kv[0])))
    names = ", ".join(c["paper_id"] for c in both) or "none"
    return "\n".join([HEADER.format(sources="data/auto_search3/evaluation.json (scripts/auto_search3.py)"), "",
                      (f"Candidates checked against the static rules: {len(document['candidates'])}; run once in the sandbox: {total}. "
                       f"Passed K1 (the run test): {interval(len(k1))}. Passed K2 (numbers of the output found in the paper's text): "
                       f"{interval(len(k2))}. Passed both: {interval(len(both))} ({names}). Cause of the K1 failures: {by_cause}. "
                       f"The search stopped because: {document['stopped_because']}. This is a selected, non-representative list; "
                       "it is not a success rate, and a K2 pass would be a match candidate, not a verified result.")])


def autosearch4_block(data: Path = DATA) -> str:
    document = _load(data / "auto_search4" / "evaluation.json")
    ran = [c for c in document["candidates"] if c.get("k1")]
    total = len(ran)
    k1 = [c for c in ran if c["k1"]["k1_passed"]]
    v1 = [c for c in ran if (c.get("k2") or {}).get("passed")]
    v2 = [c for c in ran if ((c.get("k2") or {}).get("v2") or {}).get("passed")]
    both1 = [c for c in k1 if c in v1]
    both2 = [c for c in k1 if c in v2]

    def interval(count: int) -> str:
        low, high = wilson_interval(count, total)
        return f"{count} of {total}, Wilson 95 % interval {100 * low:.1f} % to {100 * high:.1f} %"

    causes: dict[str, int] = {}
    for c in ran:
        if not c["k1"]["k1_passed"]:
            causes[c["k1"]["category"]] = causes.get(c["k1"]["category"], 0) + 1
    by_cause = ", ".join(f"{name} {count}" for name, count in sorted(causes.items(), key=lambda kv: (-kv[1], kv[0])))
    k1_names = ", ".join(c["paper_id"] for c in k1) or "none"
    v2_names = ", ".join(c["paper_id"] for c in v2) or "none"
    both_names = ", ".join(c["paper_id"] for c in both1 + [c for c in both2 if c not in both1]) or "none"
    return "\n".join([HEADER.format(sources="data/auto_search4/evaluation.json (scripts/auto_search4.py)"), "",
                      (f"Candidates checked against the static rules: {len(document['candidates'])}; run once in the sandbox: {total}. "
                       f"Passed K1 (the run test): {interval(len(k1))} ({k1_names}). Passed K2 v1 (numbers of the output found in the "
                       f"paper's text, same spelling): {interval(len(v1))}. Passed K2 v2 (the same with fraction/percent conversion and "
                       f"rounding): {interval(len(v2))} ({v2_names}). Passed K1 and K2 v1: {interval(len(both1))}. Passed K1 and K2 v2: "
                       f"{interval(len(both2))}; passed K1 and either K2: {len(both1) + len([c for c in both2 if c not in both1])} "
                       f"({both_names}). Cause of the K1 failures: {by_cause}. The search stopped because: "
                       f"{document['stopped_because']}. This is a selected, non-representative list; it is not a success rate, and "
                       "K2 v2 can match by chance: a pass is a match candidate, not a verified result.")])


def toleranceprobe_block(data: Path = DATA) -> str:
    probe = _load(data / "tolerance_probe" / "results.json")
    lines = [HEADER.format(sources="data/tolerance_probe/results.json (scripts/tolerance_probe.py)"), "",
             (f"Tolerance {probe['tolerance']}. Hand-made claims moved from the value of a real run; first deviation at which the "
              "status of the true claim changes:"), "", "| Paper | Runs | Metrics | Downward | Upward |", "|---|---|---|---|---|"]
    for group in tolerance_probe._group(probe["runs"]):
        first = group[0]
        lines.append(f"| {', '.join(sorted({r['paper_id'] for r in group}))} | {len(group)} | {len(first['metrics'])} | "
                     f"{tolerance_probe._first_change(first['rows'], -1)} | {tolerance_probe._first_change(first['rows'], 1)} |")
    matching = len(probe["accepted_claims_matching_a_probed_run"])
    lines += ["", (f"Accepted claims of the owner that match a probed run by question ID: {matching} "
                   f"of {probe['accepted_claims_total']}.")]
    return "\n".join(lines)


def realverdicts_block(data: Path = DATA) -> str:
    doc = _load(data / "real_verdicts" / "verdicts.json")
    rows, k2 = doc["rows"], doc["k2"]
    real = [r for r in rows if r["paper_id"] != "synthetic_control"]

    def runs_of(paper: str) -> set[str]:
        return {r["run"] for r in real if r["paper_id"] == paper}

    with_claims = [r for r in real if r["query_id"]]
    cli_runs = {(r["paper_id"], r["run"]) for r in with_claims}
    cli_zero = {(r["paper_id"], r["run"]) for r in with_claims if r["before_tier2"] == 0.0}
    compared = {(r["paper_id"], r["run"]) for r in with_claims if r["map_decision"] == "map"}
    p3 = [r for r in real if r["paper_id"] == "paper_003" and r["comparable"]]
    p6 = [r for r in real if r["paper_id"] == "paper_006"]
    p4 = [r for r in real if r["paper_id"] == "paper_004"]
    p102 = [r for r in real if r["paper_id"] == "paper_102"]
    syn = [r for r in rows if r["paper_id"] == "synthetic_control"]
    syn_true = [r for r in syn if r["query_id"] == "true_claim"]
    syn_false = [r for r in syn if r["query_id"] == "false_claim"]

    def k2_of(paper: str) -> str:
        items = [k for k in k2 if k["paper_id"] == paper and k["available"]]
        return f"{sum(1 for k in items if k['passed'])} of {len(items)} runs"

    first = p3[0]
    p3k2 = next(k for k in k2 if k["paper_id"] == "paper_003" and k["available"])
    final = next(m for m in p3k2["run_metrics_in_paper"] if m["metric"] == "rmse")
    claim = next(c for c in p3k2["claim_values"] if c["query_id"] == first["query_id"])
    lines = [HEADER.format(sources="data/real_verdicts/verdicts.json (scripts/real_verdicts.py)"), "",
             "| Paper | Stored runs scored | What the scorer says | Meaning of the decision |", "|---|---|---|---|",
             (f"| `paper_003` | {len(runs_of('paper_003'))} | before the claim map (claims by question ID): Tier 2 0.0 in "
              f"{sum(1 for k in cli_zero if k[0] == 'paper_003')} of {len(runs_of('paper_003'))}; with the map (same model, dataset "
              f"and metric): claimed {first['claimed']}, reproduced {first['reproduced']}, relative difference {first['rel_diff'] * 100:.2f} %, "
              f"Tier 2 {first['cli_tier2']:g}, `{first['cli_status']}` in {sum(1 for r in p3 if r['cli_status'] == first['cli_status'])} "
              f"of {len(runs_of('paper_003'))} runs | "
              "comparable for one of three claims (the run trains FT-Transformer only); one claim and one number, not a confirmed reproduction |"),
             (f"| `paper_006` | {len(runs_of('paper_006'))} | before the claim map: Tier 2 0.0 in {sum(1 for k in cli_zero if k[0] == 'paper_006')} of "
              f"{len(runs_of('paper_006'))}; with the map: {sum(1 for r in p6 if r['map_decision'] == 'no_counterpart')} of {len(p6)} claim rows "
              f"have no counterpart (Arcene numbers, the run reads another dataset), Tier 2 {p6[0]['cli_tier2']:g} (neutral baseline), "
              f"`{p6[0]['cli_status']}` | none comparable; nothing was compared, so the label is Needs Review |"),
             (f"| `paper_004` | {len(runs_of('paper_004'))} | before the claim map: Tier 2 0.0; with the map: no counterpart, Tier 2 "
              f"{p4[0]['cli_tier2']:g} (neutral baseline), `{p4[0]['cli_status']}` | none comparable: the stored metrics are hyperparameters "
              f"({', '.join(p4[0]['run_metrics'])}) |"),
             (f"| `paper_102` | {len(runs_of('paper_102'))} | no accepted claim; Tier 2 {p102[0]['cli_tier2']:g} (neutral baseline), "
              f"`{p102[0]['cli_status']}` | no comparison was made |"),
             (f"| synthetic control (known answer) | {len({r['run'] for r in syn})} | true claim: Tier 2 "
              f"{syn_true[0]['aligned_tier2']:g}, `{syn_true[0]['aligned_status']}` in {len(syn_true)} of {len(syn_true)} runs; false claim: Tier 2 "
              f"{syn_false[0]['aligned_tier2']:g}, `{syn_false[0]['aligned_status']}` in {len(syn_false)} of {len(syn_false)} runs | "
              "the only known-answer rows |"),
             "",
             (f"Before the claim map the claims never matched a run's metrics: Tier 2 was 0.0 in {len(cli_zero)} of the {len(cli_runs)} real "
              "runs that have accepted claims (question IDs against extracted metric names). With the map a claim is compared in "
              f"{len(compared)} of the {len(cli_runs)} runs (the one claim of `paper_003`); in the others no accepted claim has a "
              "counterpart in the run and Tier 2 is the neutral baseline. "
              f"K2 (numbers of the output found in the paper's text) passed {k2_of('paper_003')} of `paper_003`, {k2_of('paper_006')} of "
              f"`paper_006`, {k2_of('paper_102')} of `paper_102` and {k2_of('paper_004')} of `paper_004`. For `paper_003` the claimed value "
              f"{claim['value']} is {'printed' if claim['found'] else 'not printed'} in the paper (page {claim['page']}), while the run's final "
              f"{final['metric']} {final['value']} is {'printed' if final['found'] else 'not printed'} in it.")]
    return "\n".join(lines)


def pilotintervals_block(data: Path = DATA) -> str:
    result = _load(data / "field_analysis" / "result.json")
    lines = [HEADER.format(sources="data/field_analysis/result.json (scripts/field_analysis.py); Wilson intervals by scripts/candidates_build.py"), "",
             "| Pool | Run | Pilot success | Wilson 95 % interval |", "|---|---|---|---|"]
    for pool, runs in result["rates"].items():
        for which in ("first", "final"):
            k, n = runs[which]["pilot_success"]["k"], runs[which]["pilot_success"]["n"]
            low, high = wilson_interval(k, n)
            lines.append(f"| {pool} | {which} | {k} / {n} | {100 * low:.1f} % to {100 * high:.1f} % |")
    return "\n".join(lines)


def cleanclone_block(data: Path = DATA) -> str:
    text = (data.parent / "docs" / "evidence" / "clean_clone" / "WALKTHROUGH.md").read_text(encoding="utf-8")
    section = text[text.index("## Update 2"):]

    def grab(pattern: str) -> re.Match[str]:
        match = re.search(pattern, section)
        if match is None:
            raise ValueError(f"the walk-through no longer holds: {pattern}")
        return match

    total = grab(r"Total from the clone to the end of `diagnose`: \*\*([\d,]+) s\*\*").group(1)
    run_phase = grab(r"run phase ([\d,.]+) s").group(1)
    metrics = grab(r"metrics `([^`]+)`").group(1)
    tier2 = grab(r"\| Tier 2 \(metrics\) \| (\d+)").group(1)
    total_score = grab(r"\| Total \| ([\d.]+), status ([A-Za-z ]+)").groups()
    used = grab(r"\*\*Accepted claims used: (\d+)\*\*").group(1)
    source = ("docs/evidence/clean_clone/WALKTHROUGH.md (Update 2; a hand-kept transcript of timed console steps, "
              "the run record itself is not in the repository)")
    return "\n".join([HEADER.format(sources=source), "",
                      (f"A fresh clone of the public repository followed through the README for `paper_006`: the run completed; total time from "
                       f"the clone to the end of `diagnose` {total} s, run phase {run_phase} s; metrics `{metrics}`; accepted claims used: {used}, "
                       f"none found in the output (the run reads another dataset); Tier 2 {tier2}, total {total_score[0]}, status {total_score[1].strip()}.")])


BLOCKS = {"realverdicts": realverdicts_block, "pilotintervals": pilotintervals_block, "cleanclone": cleanclone_block, "candidateruns": candidateruns_block, "autosearch3": autosearch3_block, "autosearch4": autosearch4_block, "candidateround2": candidateround2_block, "toleranceprobe": toleranceprobe_block, "multiseed": multiseed_block, "gpucheck": gpucheck_block, "diagnosisvalidation": diagnosisvalidation_block,
          "fieldanalysis": fieldanalysis_block, "rescience": rescience_block, "pilot1": pilot1_block, "pilot2": pilot2_block, "pilot2measurements": pilot2measurements_block,
          "pilot2summary": pilot2summary_block,
          "pilot2failures": pilot2failures_block, "pilot3": pilot3_block,
          "pilot3measurements": pilot3measurements_block, "pilot3summary": pilot3summary_block,
          "pilot3failures": pilot3failures_block, "abstractnumbers": pilot3summary_block, "memoryruns": memoryruns_block, "pilot4": pilot4_block,
          "syntheticcontrol": syntheticcontrol_block, "stability": stability_block, "goldexpansion": goldexpansion_block,
          "extraction": extraction_block}
BLOCK_RE = re.compile(r"(<!-- numbers:(?P<name>[a-z0-9]+):start -->\n)(?P<body>.*?)(\n<!-- numbers:(?P=name):end -->)", re.DOTALL)


def render(name: str, data: Path = DATA) -> str:
    return BLOCKS[name](data)


def apply(text: str, data: Path = DATA) -> str:
    """The report text with every numbers block replaced by its rendering."""
    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in BLOCKS:
            raise KeyError(f"unknown numbers block: {name}")
        return f"{match.group(1)}{render(name, data)}{match.group(4)}"
    return BLOCK_RE.sub(replace, text)


def mismatches(text: str, data: Path = DATA) -> list[str]:
    return [m.group("name") for m in BLOCK_RE.finditer(text) if m.group("body") != render(m.group("name"), data)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the numbers of the final report from the stored files.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--report", default=str(REPORT_PATH))
    args = parser.parse_args(argv)
    path = Path(args.report)
    if args.write or args.check:
        raw = path.read_bytes().decode("utf-8")
        text = raw.replace("\r\n", "\n")
        if args.check:
            bad = mismatches(text)
            print(json.dumps({"in_sync": not bad, "blocks_that_differ": bad}))
            return 1 if bad else 0
        new = apply(text)
        path.write_bytes((new.replace("\n", "\r\n") if "\r\n" in raw else new).encode("utf-8"))
        print(f"updated {path}")
        return 0
    for name in BLOCKS:
        try:
            print(f"### {name}\n{render(name)}\n")
        except FileNotFoundError as exc:
            print(f"### {name}\n(not available yet: {exc})\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
