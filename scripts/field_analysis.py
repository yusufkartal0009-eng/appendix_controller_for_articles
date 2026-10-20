#!/usr/bin/env python3
"""Week 6 field analysis over the 12 papers of Pilots 1 to 4 (#413, docs/FIELD_ANALYSIS.md).

    python scripts/field_analysis.py                       # compute from the stored records; write data/field_analysis/result.json
    python scripts/field_analysis.py --check               # exit 1 if result.json or the generated part of the document differs
    python scripts/field_analysis.py --extract-features    # needs the clones in .sandbox_staging/: write features.json

Everything printed comes from stored files: the measurements of Pilots 1, 3, and 4, the pilot settings, the first-attempt
folders, the claim decisions, and `data/field_analysis/features.json` (README and requirement features read from the clones at
the pinned commits). Nothing is typed in. The analysis is exploratory (n = 12): there is no test of significance and the factor
table is descriptive only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

DATA = project_root / "data"
FEATURES_PATH = DATA / "field_analysis" / "features.json"
RESULT_PATH = DATA / "field_analysis" / "result.json"
DOC_PATH = project_root / "docs" / "FIELD_ANALYSIS.md"
START, END = "<!-- field-analysis:start -->", "<!-- field-analysis:end -->"
STAGING = project_root / ".sandbox_staging"

SEED_IDS = ("paper_002", "paper_003", "paper_004", "paper_005", "paper_006", "paper_008")
EXPANSION_IDS = ("paper_101", "paper_102", "paper_103", "paper_104", "paper_105", "paper_106")
POOL = (*SEED_IDS, *EXPANSION_IDS)
SUBPOOLS = {"seed papers": SEED_IDS, "expansion papers": EXPANSION_IDS, "all 12 papers": POOL}


def subpool_of(paper_id: str) -> str:
    return "seed" if paper_id in SEED_IDS else "expansion"


def read_json(relative: str) -> Any:
    return json.loads((DATA / relative).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- reference runs and rates


def reference_runs() -> dict[str, dict[str, dict[str, Any]]]:
    """{paper_id: {"first": {...}, "final": {...}}} from the stored measurements (docs/FIELD_ANALYSIS.md section 2)."""
    pilot1 = {p["paper_id"]: p for p in read_json("pilot_runs/measurements.json")["papers"]}
    pilot3 = {p["paper_id"]: p for p in read_json("pilot3_runs/measurements.json")["papers"]}
    pilot4 = {p["paper_id"]: p for p in read_json("pilot4_runs/summary.json")["papers"]}
    keys = ("install_success", "run_success", "pilot_success")
    runs: dict[str, dict[str, dict[str, Any]]] = {}
    for pid in SEED_IDS:
        runs[pid] = {"first": {**{k: pilot1[pid][k] for k in keys}, "source": "Pilot 1"},
                     "final": {**{k: pilot3[pid][k] for k in keys}, "source": "Pilot 3"}}
    for pid in EXPANSION_IDS:
        runs[pid] = {"first": {**{k: pilot4[pid]["strict"][k] for k in keys}, "source": "Pilot 4 first attempt"},
                     "final": {**{k: pilot4[pid]["corrected"][k] for k in keys}, "source": "Pilot 4 after the correction round"}}
        runs[pid]["first"]["category"] = pilot4[pid]["strict"].get("category")
        runs[pid]["final"]["category"] = pilot4[pid]["corrected"].get("category")
    return runs


def rates(runs: dict[str, dict[str, dict[str, Any]]]) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    out: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for pool_name, ids in SUBPOOLS.items():
        out[pool_name] = {}
        for which in ("first", "final"):
            out[pool_name][which] = {}
            for key in ("install_success", "run_success", "pilot_success"):
                k = sum(1 for pid in ids if runs[pid][which][key])
                out[pool_name][which][key] = {"k": k, "n": len(ids), "proportion": round(k / len(ids), 3)}
    return out


# ---------------------------------------------------------------- interventions and autonomy


def interventions() -> dict[str, dict[str, Any]]:
    """I1 to I4 of docs/FIELD_ANALYSIS.md section 4, read from stored files."""
    pilot3_listed = set(read_json("pilot3_settings.json")["papers"])
    summary = {p["paper_id"]: p for p in read_json("pilot4_runs/summary.json")["papers"]}
    attempts = read_json("pilot2_runs/first_attempts/index.json")
    tool_defect_papers = {a["paper_id"] for a in attempts if "No defect" not in a.get("superseded_because", "")}
    pilot4_attempt_dir = DATA / "pilot4_runs" / "first_attempts"
    tool_defect_papers |= {re.match(r"(paper_\d+)", p.name).group(1) for p in pilot4_attempt_dir.iterdir()
                           if p.is_dir() and "tool_defect" in p.name}
    accepted = {c["paper_id"] for c in read_json("claims/review_decisions.json")["claims"]
                if c.get("review_status") == "accepted" and c.get("verified_by") == "human"}
    result = {}
    for pid in POOL:
        result[pid] = {
            "I1_command_or_setup_by_a_person": pid in SEED_IDS,
            "I2_correction_or_setting_after_a_failure": pid in pilot3_listed or bool(summary.get(pid, {}).get("correction_round")),
            "I3_tool_change_for_this_paper": pid in tool_defect_papers,
            "I4_claim_accepted_by_a_person": pid in accepted,
        }
    return result


def autonomy(runs: dict[str, dict[str, dict[str, Any]]], intervened: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Concluded / succeeded autonomously (docs/FIELD_ANALYSIS.md section 5, with the clarification of section 8).

    The first reference run counts I1 only (I2 and I3 are made after a first run); the final run counts I1 to I3.
    """
    out: dict[str, Any] = {}
    for pool_name, ids in SUBPOOLS.items():
        out[pool_name] = {}
        for which in ("first", "final"):
            def hand(pid: str, which: str = which) -> bool:
                i = intervened[pid]
                flags = ["I1_command_or_setup_by_a_person"]
                if which == "final":
                    flags += ["I2_correction_or_setting_after_a_failure", "I3_tool_change_for_this_paper"]
                return any(i[f] for f in flags)

            concluded = sum(1 for pid in ids if not hand(pid))  # every paper of the pool has a stored outcome
            succeeded = sum(1 for pid in ids if not hand(pid) and runs[pid][which]["pilot_success"])
            out[pool_name][which] = {"concluded_autonomously": {"k": concluded, "n": len(ids)},
                                     "succeeded_autonomously": {"k": succeeded, "n": len(ids)}}
        out[pool_name]["papers_with_an_accepted_claim_I4"] = {
            "k": sum(1 for pid in ids if intervened[pid]["I4_claim_accepted_by_a_person"]), "n": len(ids)}
    return out


# ---------------------------------------------------------------- features


def readme_checks(text: str) -> dict[str, bool]:
    lowered = text.lower()
    fenced = re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.DOTALL)
    commands = [line for block in fenced for line in block.splitlines()]
    return {
        "readme_exists": True,
        "installation_instruction": bool(re.search(r"pip install|conda (create|install|env)|requirements\.txt|environment\.ya?ml|setup\.py", lowered)),
        "run_command_in_code_block": any(re.match(r"\s*(\$ )?(python3?|bash|sh|make|jupyter)\b", line) for line in commands),
        "data_described": bool(re.search(r"\bdata(set)?s?\b", lowered)) and bool(re.search(r"download|prepare", lowered)),
    }


def requirement_count(repo: Path, requirement_files: list[str]) -> tuple[int, list[dict[str, Any]]]:
    import yaml

    from src.sandbox.conda_env import find_conda_env_files

    detail: list[dict[str, Any]] = []
    for name in requirement_files:
        lines = [ln.strip() for ln in (repo / name).read_text(encoding="utf-8", errors="replace").splitlines()]
        n = sum(1 for ln in lines if ln and not ln.startswith(("#", "-")))
        detail.append({"file": name, "entries": n})
    for name in find_conda_env_files(repo):
        data = yaml.safe_load((repo / name).read_text(encoding="utf-8", errors="replace")) or {}
        n = 0
        for dep in data.get("dependencies", []) or []:
            n += len(dep.get("pip", [])) if isinstance(dep, dict) else 1
        detail.append({"file": name, "entries": n, "kind": "conda environment"})
    return sum(d["entries"] for d in detail), detail


def extract_features(staging: Path = STAGING) -> dict[str, Any]:
    final_records = {pid: read_json(f"pilot3_runs/{pid}/pilot_record.json") for pid in SEED_IDS}
    final_records |= {pid: read_json(f"pilot4_runs/{pid}/pilot_record.json") for pid in EXPANSION_IDS}
    first_records = {pid: read_json(f"pilot_runs/{pid}/pilot_record.json") for pid in SEED_IDS}
    first_records |= {pid: read_json(f"pilot4_runs/{pid}/pilot_record.json") for pid in EXPANSION_IDS}
    first_records["paper_106"] = read_json("pilot4_runs/first_attempts/paper_106_attempt1/pilot_record.json")
    features: dict[str, Any] = {}
    for pid in POOL:
        repo = staging / pid
        commit = final_records[pid]["pinned_commit"]
        head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        if head != commit:
            raise RuntimeError(f"{pid}: the clone is at {head}, not at the pinned commit {commit}")
        readme = next(p for p in sorted(repo.iterdir()) if p.name.lower().startswith("readme"))
        text = readme.read_text(encoding="utf-8", errors="replace")
        checks = readme_checks(text)
        commit_date = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%cI", commit], capture_output=True,
                                     text=True, check=True).stdout.strip()
        started = first_records[pid]["started_at"]
        age_years = (datetime.fromisoformat(started) - datetime.fromisoformat(commit_date)).days / 365.25
        count, detail = requirement_count(repo, final_records[pid]["stage"].get("requirements_files", []))
        features[pid] = {
            "pinned_commit": commit, "readme_file": readme.name,
            "readme_sha256": hashlib.sha256(readme.read_bytes()).hexdigest(), "readme_checks": checks,
            "F1_documentation_quality": sum(checks.values()),
            "commit_date": commit_date, "first_protocol_run_started_at": started,
            "F2_code_age_years": round(age_years, 2),
            "F3_declared_dependencies": count, "dependency_files": detail,
        }
    return {"protocol": "docs/FIELD_ANALYSIS.md section 6", "papers": features}


def factor_table(runs: dict[str, dict[str, dict[str, Any]]], features: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for pid in POOL:
        f = features["papers"][pid]
        rows.append({"paper_id": pid, "pool": subpool_of(pid), "F1": f["F1_documentation_quality"],
                     "F2": f["F2_code_age_years"], "F3": f["F3_declared_dependencies"],
                     "first_pilot_success": runs[pid]["first"]["pilot_success"],
                     "final_pilot_success": runs[pid]["final"]["pilot_success"]})
    medians: dict[str, Any] = {}
    for which in ("first_pilot_success", "final_pilot_success"):
        medians[which] = {}
        for factor in ("F1", "F2", "F3"):
            groups = {"with pilot success": [r[factor] for r in rows if r[which]],
                      "without pilot success": [r[factor] for r in rows if not r[which]]}
            medians[which][factor] = {name: {"n": len(v), "median": statistics.median(v) if v else None}
                                      for name, v in groups.items()}
    return {"rows": rows, "medians": medians}


# ---------------------------------------------------------------- output


def compute() -> dict[str, Any]:
    runs = reference_runs()
    intervened = interventions()
    result = {
        "protocol": "docs/FIELD_ANALYSIS.md", "pool": list(POOL), "reference_runs": runs, "rates": rates(runs),
        "interventions": intervened, "autonomy": autonomy(runs, intervened),
    }
    if FEATURES_PATH.is_file():
        result["factors"] = factor_table(runs, json.loads(FEATURES_PATH.read_text(encoding="utf-8")))
    return result


def fraction(d: dict[str, Any]) -> str:
    return f"{d['k']} / {d['n']}" + (f" ({d['k'] / d['n']:.0%})" if d["n"] else "")


def render(result: dict[str, Any]) -> str:
    out = ["## 8. Results (generated)", "",
           ("Generated by `scripts/field_analysis.py` from the stored records; do not edit by hand. Exploratory, n = 12 (6 + 6): "
           "no test of significance is made and no relationship is claimed."), "",
           "### 8.1 Clarification written with the script (before the first computation)", "",
           ("Section 5 does not say which reference run the autonomy rate is computed for. It is computed for **both**: for the "
           "first protocol run only I1 counts (I2 and I3 are, by their definition, made after a first run); for the final "
           "protocol run I1, I2, and I3 count. Concluded and succeeded autonomously are counted over all papers of the pool."), "",
           "### 8.2 Success rates", ""]
    for which, title in (("first", "First protocol run (Pilot 1 for seed papers, Pilot 4 first attempt for expansion papers)"),
                         ("final", "Final protocol run (Pilot 3 for seed papers, Pilot 4 after the correction round for expansion papers)")):
        out += [f"**{title}**", "", "| Pool | Setup success | Run success | Pilot success |", "|---|---|---|---|"]
        for pool_name in SUBPOOLS:
            r = result["rates"][pool_name][which]
            out.append(f"| {pool_name} | {fraction(r['install_success'])} | {fraction(r['run_success'])} | {fraction(r['pilot_success'])} |")
        out.append("")
    out += ["### 8.3 Human intervention per paper", "",
            "| Paper | Pool | I1 command or setup by a person | I2 correction or setting after a failure | I3 tool change for the paper | I4 claim accepted by a person |",
            "|---|---|---|---|---|---|"]
    for pid in POOL:
        i = result["interventions"][pid]
        yes = lambda v: "yes" if v else "no"
        out.append(f"| `{pid}` | {subpool_of(pid)} | {yes(i['I1_command_or_setup_by_a_person'])} | "
                   f"{yes(i['I2_correction_or_setting_after_a_failure'])} | {yes(i['I3_tool_change_for_this_paper'])} | "
                   f"{yes(i['I4_claim_accepted_by_a_person'])} |")
    out += ["", "### 8.4 AI autonomy rate", "",
            "For the seed papers I1 holds by definition, so their rate is 0 by construction (section 5).", "",
            "| Pool | Run | Concluded autonomously | Succeeded autonomously |", "|---|---|---|---|"]
    for pool_name in SUBPOOLS:
        for which in ("first", "final"):
            a = result["autonomy"][pool_name][which]
            out.append(f"| {pool_name} | {which} | {fraction(a['concluded_autonomously'])} | {fraction(a['succeeded_autonomously'])} |")
    out += ["", "Papers with at least one claim accepted by a person (I4, not part of the rate): " + ", ".join(
        f"{name} {fraction(result['autonomy'][name]['papers_with_an_accepted_claim_I4'])}" for name in SUBPOOLS) + ".", ""]
    if "factors" in result:
        out += ["### 8.5 Factors (descriptive table, not a test)", "",
                "| Paper | Pool | F1 documentation (0-4) | F2 code age (years) | F3 declared dependencies | Pilot success, first run | Pilot success, final run |",
                "|---|---|---|---|---|---|---|"]
        for r in result["factors"]["rows"]:
            out.append(f"| `{r['paper_id']}` | {r['pool']} | {r['F1']} | {r['F2']} | {r['F3']} | "
                       f"{'yes' if r['first_pilot_success'] else 'no'} | {'yes' if r['final_pilot_success'] else 'no'} |")
        out += ["", ("F3 sums all requirement files and conda environment files of a repository (`data/field_analysis/features.json` lists "
                "them). A conda environment file lists every package of an environment, system libraries included, so it counts far "
                "more than a requirements file; the two kinds of file are not comparable."), "",
                ("Median of each factor among the papers with and without a pilot success of the **final** run "
                "(the numbers of papers are in parentheses; with so few papers a median says little):"), "",
                "| Factor | With pilot success | Without pilot success |", "|---|---|---|"]
        for factor, name in (("F1", "F1 documentation"), ("F2", "F2 code age"), ("F3", "F3 dependencies")):
            m = result["factors"]["medians"]["final_pilot_success"][factor]
            cell = lambda g: f"{g['median']} (n={g['n']})" if g["n"] else "- (n=0)"
            out.append(f"| {name} | {cell(m['with pilot success'])} | {cell(m['without pilot success'])} |")
        out.append("")
    else:
        out += ["### 8.5 Factors", "", ("`data/field_analysis/features.json` does not exist yet; run "
                "`python scripts/field_analysis.py --extract-features`."), ""]
    return "\n".join(out)


def update_document(text: str, generated: str) -> str:
    block = f"{START}\n{generated}\n{END}"
    if START in text:
        return re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.DOTALL)
    return text.rstrip("\n") + "\n\n" + block + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--extract-features", action="store_true")
    parser.add_argument("--staging", default=str(STAGING), help="Where the repositories are cloned (with --extract-features).")
    args = parser.parse_args(argv)
    if args.extract_features:
        FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
        FEATURES_PATH.write_text(json.dumps(extract_features(Path(args.staging)), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {FEATURES_PATH}")
        return 0
    result = compute()
    result_text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    doc_text = update_document(DOC_PATH.read_text(encoding="utf-8").replace("\r\n", "\n"), render(result))
    if args.check:
        stored = RESULT_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") if RESULT_PATH.is_file() else ""
        if stored != result_text or DOC_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") != doc_text:
            print("result.json or the generated part of FIELD_ANALYSIS.md differ; run scripts/field_analysis.py", file=sys.stderr)
            return 1
        return 0
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(result_text, encoding="utf-8", newline="\n")
    DOC_PATH.write_text(doc_text, encoding="utf-8", newline="\n")
    print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
