#!/usr/bin/env python3
"""Why runs failed: counts of the first failure of every stored run, by simple text rules (docs/FAILURE_STATISTICS.md).

    python scripts/failure_statistics.py           # reads the stored runs, writes data/failure_statistics.json and docs/FAILURE_STATISTICS.md
    python scripts/failure_statistics.py --check   # fails if either file differs from what the stored runs give today

Three groups of stored runs are counted, each in its own table (the groups are never added together):

1. Pilots 1 to 4: 12 papers, 24 attempts (6 papers in Pilots 1 to 3, 6 other papers in Pilot 4). The first failure of an attempt.
2. The candidate list: round 1 (one run each) and the repair round.
3. The automatic searches of rounds 3 and 4: the line that decided the K1 outcome of each run.

The category of a failure comes from the line of the log that decided it (the stored `log_line`, `evidence.line` or
`deciding_line`), by the ordered rules in `LINE_RULES`, applied in this order, first match wins. A few outcomes are not log lines
and are taken from the record (`RECORD_RULES`). Nothing is run; no number is typed by hand. The lists are selected, not
samples: see the selection warning in the document. These are counts of why selected runs failed, not a success rate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
DATA = project_root / "data"
OUT_JSON = DATA / "failure_statistics.json"
OUT_DOC = project_root / "docs" / "FAILURE_STATISTICS.md"

PASSED = "passed"
UNCLASSIFIED = "other"

# (category, what it means). The order is the order of the columns of the tables.
CATEGORIES: list[tuple[str, str]] = [
    ("missing_python_module", "the program stopped because a Python module was not installed (`No module named ...`)"),
    ("install_package_not_found", ("the installation of the listed requirements failed: no matching distribution (package or wheel), no "
                                  "version satisfies the pin, or the pins conflict")),
    ("read_only_write", "the program tried to write into the repository, which is mounted read-only (`Read-only file system`)"),
    ("data_or_network_missing", ("a data file was not there, or a download needed a network (the sandbox has none): `No such file or "
                                "directory`, name resolution failures, connection errors")),
    ("ran_no_metric_line", "the command finished (exit code 0) but printed no line with a metric that the extractor can read"),
    ("timeout", "the run reached its time limit"),
    ("out_of_memory", "the container was killed for using more memory than its limit"),
    ("api_key_missing", "the program asked for an API key that the sandbox does not have"),
    ("wrong_argument", "the command line was rejected (`unrecognized arguments`, a required argument missing)"),
    ("not_run_command_incomplete", "not run: the README command holds only placeholders"),
    ("not_run_judged_not_repairable", "not run in any round: the repair round judged from the repository's files that no allowed repair could make it run"),
    ("staging_failed", "the repository could not be staged (cloned and prepared) for the run"),
    ("ran_without_installed_dependencies", "the install failed but the command ran and exited with 0 (a script that needs no package)"),
    (UNCLASSIFIED, "none of the rules above matched the deciding line (or there is no deciding line)"),
]
CATEGORY_NAMES = [name for name, _ in CATEGORIES]

# Ordered text rules for the deciding log line: (category, regular expression, shown pattern in the document)
LINE_RULES: list[tuple[str, str]] = [
    ("read_only_write", r"Read-only file system"),
    ("install_package_not_found", (r"No matching distribution found|Could not find a version that satisfies|ResolutionImpossible|"
                                  r"conflicting dependencies|Cannot install .* because")),
    ("missing_python_module", r"No module named"),
    ("data_or_network_missing", (r"FileNotFoundError|No such file or directory|Temporary failure in name resolution|NameResolutionError|"
                               r"Failed to resolve|ConnectionError|Max retries exceeded|LocalEntryNotFoundError|URLError")),
    ("api_key_missing", r"API key|api_key|API_KEY"),
    ("wrong_argument", r"unrecognized arguments|the following arguments are required"),
    ("timeout", r"status: TIMEOUT"),
    ("out_of_memory", r"status: OOM_KILLED"),
]
# Outcomes that the record states and that are not a log line: (field value in the stored record) -> category
RECORD_RULES: dict[str, str] = {
    "no_metric_line": "ran_no_metric_line",
    "command_incomplete": "not_run_command_incomplete",
    "not_run_not_repairable": "not_run_judged_not_repairable",
    "staging": "staging_failed",
    "RAN_WITHOUT_INSTALLED_DEPENDENCIES": "ran_without_installed_dependencies",
}
LINE_LIMIT = 160
SELECTION_WARNING: list[str] = [
    '**Every list here is selected, not sampled.** The six seed papers were picked by hand; Pilot 4 added six more by hand; the candidate list was collected by hand; the automatic searches (rounds 3 and 4) took repositories from GitHub through filter rules written before the runs. None of them is a random draw from all research code.',
    '**GPU requirements look like zero because of the filters.** The rules of the automatic searches (rule S3, `docs/AUTO_SEARCH_ROUND3.md` and `docs/AUTO_SEARCH_ROUND4.md`) rejected every repository whose README or requirement files mention `gpu` or `cuda`. A category for a GPU requirement therefore does not appear in the tables of the automatic searches, and its absence says nothing about how often research code needs a GPU. Whether the hand-collected lists had such a filter is not verified here.',
    '**The searches also required a runnable README command** (rule S2) and a license rule (S1), so they favor small repositories that document one command. Their failures are failures of those repositories, not of research code in general.',
    '**Pilot 3 used settings chosen after the failures of Pilot 2 had been seen** (`docs/PILOT_3.md`). Its numbers describe a setting tuned on these six papers, not a protocol fixed in advance.',
    '**The groups are not added together**, because their selection differs. A share in a table is a share of the failed runs of that table, never a share of all research code.',
    '**A category is a reading of one log line.** The first error that decides an outcome is not always the root cause (a missing module may follow a failed install; a missing file may follow a download that needed a network).',
]


def categorize_line(line: str | None) -> str:
    """The category of a deciding log line by `LINE_RULES` (first match wins); `other` if none matches or the line is empty."""
    for category, pattern in LINE_RULES:
        if line and re.search(pattern, line):
            return category
    return UNCLASSIFIED


def categorize(record_value: str | None, line: str | None) -> str:
    """A record outcome that is not a log line wins (`RECORD_RULES`); otherwise the log line decides."""
    if record_value in RECORD_RULES:
        return RECORD_RULES[record_value]
    return categorize_line(line)


def short(line: str | None) -> str | None:
    if line is None:
        return None
    line = " ".join(line.split())
    return line if len(line) <= LINE_LIMIT else line[:LINE_LIMIT - 3] + "..."


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def row(run_id: str, group: str, category: str, line: str | None, source: str, recorded: str | None = None) -> dict[str, Any]:
    return {"run": run_id, "group": group, "category": category, "line": short(line), "recorded_category": recorded, "source": source}


def count(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Counts per category, in the order of CATEGORY_NAMES, plus `passed`; categories that do not occur are 0."""
    found = Counter(r["category"] for r in rows)
    unknown = set(found) - set(CATEGORY_NAMES) - {PASSED}
    if unknown:
        raise ValueError(f"unknown categories: {sorted(unknown)}")
    return {name: found.get(name, 0) for name in [PASSED, *CATEGORY_NAMES]}


def pilot_rows(root: Path = DATA) -> list[dict[str, Any]]:
    """One row per paper and pilot: the first failure of the attempt that the pilot recorded (24 attempts)."""
    rows: list[dict[str, Any]] = []
    for number, folder in ((1, "pilot_runs"), (2, "pilot2_runs"), (3, "pilot3_runs")):
        path = root / folder / "failure_categories.json"
        for item in read(path)["papers"]:
            source = f"data/{folder}/failure_categories.json"
            run_id = f"Pilot {number} {item['paper_id']}"
            if item["pilot_success"]:
                rows.append(row(run_id, f"Pilot {number}", PASSED, None, source))
                continue
            line = (item.get("evidence") or {}).get("line")
            recorded = item.get("other_name") or item.get("category")
            rows.append(row(run_id, f"Pilot {number}", categorize(None, line), line, source, recorded))
    summary = read(root / "pilot4_runs" / "summary.json")
    for item in summary["papers"]:
        strict = item["strict"]  # the first attempt, before any correction
        run_id = f"Pilot 4 {item['paper_id']}"
        source = "data/pilot4_runs/summary.json"
        if strict["pilot_success"]:
            rows.append(row(run_id, "Pilot 4", PASSED, None, source))
        else:
            rows.append(row(run_id, "Pilot 4", categorize(strict["category"], strict.get("deciding_line")), strict.get("deciding_line"),
                            source, strict["category"]))
    return rows


def candidate_rows(root: Path = DATA) -> dict[str, list[dict[str, Any]]]:
    """Round 1 of the candidate list (14 listed, one run each) and the repair round (14 listed)."""
    round1: list[dict[str, Any]] = []
    for item in read(root / "candidates" / "runs" / "evaluation.json")["results"]:
        source = "data/candidates/runs/evaluation.json"
        if item["passed"]:
            round1.append(row(item["paper_id"], "round 1", PASSED, None, source))
            continue
        round1.append(row(item["paper_id"], "round 1", categorize(item["category"], item.get("log_line")), item.get("log_line"),
                          source, item["category"]))
    repair: list[dict[str, Any]] = []
    for item in read(root / "candidates" / "round2" / "evaluation.json")["results"]:
        source = "data/candidates/round2/evaluation.json"
        if item["passed"]:
            repair.append(row(item["paper_id"], "repair round", PASSED, None, source))
            continue
        stopped = item.get("stopped") or {}
        recorded = item.get("final_category") or stopped.get("status")
        line = item.get("final_log_line") or stopped.get("log_line")
        # the repair round stores a metric dictionary, not a log line, when the run finished without a readable metric line
        marker = recorded if recorded in RECORD_RULES else None
        if stopped.get("at_attempt") == 0 and not item.get("in_round_1"):  # judged from the files, never run in any round
            marker, recorded = "not_run_not_repairable", "not_repairable (not run)"
        repair.append(row(item["paper_id"], "repair round", categorize(marker, line), None if marker else line, source, recorded))
    return {"round 1": round1, "repair round": repair}


def search_rows(folder: str, label: str, root: Path = DATA) -> list[dict[str, Any]]:
    """One row per stored run of an automatic search: the line that decided its K1 outcome (`k1_k2.json`)."""
    rows: list[dict[str, Any]] = []
    for run_dir in sorted((root / folder / "runs").iterdir()):
        k1 = read(run_dir / "k1_k2.json")["k1"]
        source = f"data/{folder}/runs/{run_dir.name}/k1_k2.json"
        if k1["k1_passed"]:
            rows.append(row(run_dir.name, label, PASSED, None, source))
        else:
            rows.append(row(run_dir.name, label, categorize(k1["category"], k1.get("log_line")), k1.get("log_line"), source,
                            k1["category"]))
    return rows


def evaluation_runs(folder: str, root: Path = DATA) -> int:
    return read(root / folder / "evaluation.json")["runs"]


def build(root: Path = DATA) -> dict[str, Any]:
    pilots = pilot_rows(root)
    candidates = candidate_rows(root)
    round3 = search_rows("auto_search3", "round 3", root)
    round4 = search_rows("auto_search4", "round 4", root)
    tables: dict[str, Any] = {}

    def table(key: str, title: str, rows: list[dict[str, Any]], sources: list[str], extra: dict[str, Any] | None = None) -> None:
        counts = count(rows)
        failed = sum(v for k, v in counts.items() if k != PASSED and not k.startswith("not_run"))
        shares = {k: (v / failed if failed else None) for k, v in counts.items() if k != PASSED and not k.startswith("not_run")}
        tables[key] = {"title": title, "attempts": len(rows), "counts": counts, "failed": failed, "share_of_failed": shares,
                       "sources": sources, "rows": rows, **(extra or {})}

    table("pilots", "Pilots 1 to 4 (12 papers, 24 attempts; the first failure of each attempt)", pilots,
          ["data/pilot_runs/failure_categories.json", "data/pilot2_runs/failure_categories.json",
           "data/pilot3_runs/failure_categories.json", "data/pilot4_runs/summary.json"])
    for pilot in ("Pilot 1", "Pilot 2", "Pilot 3", "Pilot 4"):
        tables["pilots"].setdefault("by_pilot", {})[pilot] = count([r for r in pilots if r["group"] == pilot])
    table("candidates_round1", "Candidate list, round 1 (one run each; 14 listed, 1 not run)", candidates["round 1"],
          ["data/candidates/runs/evaluation.json"])
    table("candidates_repair", "Candidate list, repair round (15 entries: the 14 of round 1 and cand_020, which only the repair round considered; the state after the repairs of the protocol)",
          candidates["repair round"], ["data/candidates/round2/evaluation.json"])
    table("auto_search3", "Automatic search, round 3 (the K1 outcome of each stored run)", round3,
          ["data/auto_search3/runs/*/k1_k2.json"], {"runs_in_evaluation_json": evaluation_runs("auto_search3", root)})
    table("auto_search4", "Automatic search, round 4 (the K1 outcome of each stored run)", round4,
          ["data/auto_search4/runs/*/k1_k2.json"], {"runs_in_evaluation_json": evaluation_runs("auto_search4", root)})
    return {
        "note": "generated by scripts/failure_statistics.py; do not edit by hand. Counts of why selected runs failed, not a success rate "
                "(selected, non-representative lists; docs/FAILURE_STATISTICS.md, selection bias).",
        "selection_warning": SELECTION_WARNING,
        "categories": [{"name": name, "meaning": meaning} for name, meaning in CATEGORIES],
        "line_rules": [{"category": c, "pattern": p} for c, p in LINE_RULES],
        "record_rules": RECORD_RULES,
        "tables": tables,
    }


def md_cell(text: str | None) -> str:
    return (text or "-").replace("|", "\\|").replace("`", "'")


def count_table(data: dict[str, Any], key: str) -> list[str]:
    counts, failed, shares = (data["tables"][key][f] for f in ("counts", "failed", "share_of_failed"))
    lines = ["| Category | Runs | Share of the failed runs |", "|---|---|---|"]
    for name in [PASSED, *CATEGORY_NAMES]:
        n = counts[name]
        if n == 0 and name not in (PASSED,):
            continue
        share = "-" if name == PASSED or name.startswith("not_run") or not failed else f"{shares[name]:.1%}"
        lines.append(f"| `{name}` | {n} | {share} |")
    lines.append(f"| failed (not counting `passed` and not-run) | {failed} | 100.0% |")
    return lines


def render(data: dict[str, Any]) -> str:
    t = data["tables"]
    out = [
        "# Failure Statistics",
        "",
        ("> Generated by `scripts/failure_statistics.py` from the stored runs; do not edit by hand "
        "(`python scripts/failure_statistics.py --check` fails if this file or `data/failure_statistics.json` differs)."),
        "",
        ("These are counts of **why selected runs failed**. They are not a success rate and not an estimate of how reproducible research code "
        "is in general (see the selection warning)."),
        "",
        "## 1. Selection warning (read this first)",
        "",
        *[f"- {item}" for item in SELECTION_WARNING],
        "",
        "## 2. How the categories are assigned",
        "",
        ("The category comes from the line of the log that decided the outcome (the stored `log_line`, `evidence.line` or `deciding_line`), "
        "by the following rules, tried in this order, first match wins. The line is read as text; nothing is guessed from the paper."),
        "",
        "| Order | Category | Rule (regular expression on the deciding line) |",
        "|---|---|---|",
    ]
    for i, rule in enumerate(data["line_rules"], 1):
        out.append(f"| {i} | `{rule['category']}` | `{md_cell(rule['pattern'])}` |")
    out += [
        "",
        "Outcomes that the record states and that are not a log line are taken from the record first: "
        + ", ".join(f"`{k}` -> `{v}`" for k, v in data["record_rules"].items())
        + f". A line that matches no rule is `{UNCLASSIFIED}`.",
        "",
        "| Category | Meaning |",
        "|---|---|",
    ]
    for item in data["categories"]:
        out.append(f"| `{item['name']}` | {md_cell(item['meaning'])} |")
    out += [
        "",
        "## 3. Pilots 1 to 4",
        "",
        f"{t['pilots']['title']}. Source: " + ", ".join(f"`{s}`" for s in t["pilots"]["sources"]) + ". Pilot 4 uses the first attempt "
        "(`strict`), before the one correction round.",
        "",
    ]
    out += count_table(data, "pilots")
    out += ["", "By pilot:", "", "| Pilot | " + " | ".join(f"`{n}`" for n in [PASSED, *CATEGORY_NAMES] if any(
        t["pilots"]["by_pilot"][p][n] for p in t["pilots"]["by_pilot"])) + " |"]
    shown = [n for n in [PASSED, *CATEGORY_NAMES] if any(t["pilots"]["by_pilot"][p][n] for p in t["pilots"]["by_pilot"])]
    out.append("|---|" + "---|" * len(shown))
    for pilot, counts in t["pilots"]["by_pilot"].items():
        out.append(f"| {pilot} | " + " | ".join(str(counts[n]) for n in shown) + " |")
    out += ["", "Every attempt:", "", "| Attempt | Category | Recorded category | Deciding line |", "|---|---|---|---|"]
    for r in t["pilots"]["rows"]:
        out.append(f"| {r['run']} | `{r['category']}` | {md_cell(r['recorded_category'])} | {md_cell(r['line'])} |")
    out += ["", "## 4. Candidate list", ""]
    for key, number in (("candidates_round1", "4a"), ("candidates_repair", "4b")):
        out += [f"### {number}. {t[key]['title']}", "", "Source: " + ", ".join(f"`{s}`" for s in t[key]["sources"]) + ".", ""]
        out += count_table(data, key)
        out.append("")
    out += [("`not_run_*` rows are entries that were not run (the README command held placeholders; or the files showed that no allowed repair could work). In the repair round `passed` is the state after the repairs allowed by the protocol (`docs/CANDIDATE_RUNS_ROUND2.md`), "
            "so the two tables describe the same candidates at two points in time."), ""]
    out += ["## 5. Automatic searches (rounds 3 and 4)", "",
            ("The category is that of the line that decided the K1 outcome of each stored run (`k1_k2.json`, `k1.log_line`). K1 means that the "
            "command ran and printed a readable metric line."), ""]
    for key, number in (("auto_search3", "5a"), ("auto_search4", "5b")):
        item = t[key]
        note = ""
        if item["runs_in_evaluation_json"] != item["attempts"]:
            note = (f" `evaluation.json` counts {item['runs_in_evaluation_json']} runs; {item['attempts']} run folders with a `k1_k2.json` are "
                    "stored. The tables count the stored folders.")
        out += [f"### {number}. {item['title']}", "", f"Runs counted: {item['attempts']}.{note}", ""]
        out += count_table(data, key)
        out.append("")
    out += ["## 6. What these tables do not show", "",
            "- No success rate. The `passed` rows are the runs of selected lists that passed their own check; they are not a share of research code.",
            "- No cause. A category is the kind of the first deciding error, read from one log line.",
            "- No GPU result (see the selection warning).",
            ("- Nothing about papers that were never run: the searches rejected most repositories before running them (the counts are in "
            "`docs/AUTO_SEARCH_ROUND3.md` and `docs/AUTO_SEARCH_ROUND4.md`)."),
            ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail if data/failure_statistics.json or the document differs from the stored runs")
    args = parser.parse_args(argv)
    data = build()
    text_json = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    text_doc = render(data)
    if args.check:
        ok = True
        for path, text in ((OUT_JSON, text_json), (OUT_DOC, text_doc)):
            current = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.is_file() else None
            if current != text:
                print(f"{path} is out of date: run scripts/failure_statistics.py")
                ok = False
        if ok:
            print("data/failure_statistics.json and docs/FAILURE_STATISTICS.md match the stored runs")
        return 0 if ok else 1
    OUT_JSON.write_text(text_json, encoding="utf-8", newline="\n")
    OUT_DOC.write_text(text_doc, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_JSON} and {OUT_DOC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
