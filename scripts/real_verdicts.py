#!/usr/bin/env python3
"""Verdicts of the scorer on the real stored runs, and the K2 positive control (#494).

    python scripts/real_verdicts.py            # reads the stored runs, writes data/real_verdicts/verdicts.json and docs/REAL_VERDICTS.md
    python scripts/real_verdicts.py --render   # rewrites docs/REAL_VERDICTS.md from the stored verdicts.json (no PDFs needed)
    python scripts/real_verdicts.py --check    # fails if docs/REAL_VERDICTS.md differs from verdicts.json

Every row comes from stored files: the accepted claims (`data/claims/review_decisions.json`), the run records
(`pilot_record.json`, `run_report.json`, `stdout.log` of each run directory), and `src/score_run.py`. Nothing is run in
the sandbox and no database is written: `score_run` needs none, so `data/repro_radar.db` is not touched.

Two views are kept apart on purpose:

- *as scored*: what `cli.py score --from-run` does. Since #509 the claims go through `data/claim_metric_map.json`
  (`docs/CLAIM_METRIC_MAP.md`); the result *before the mapping* (claims keyed by their question ID) is kept next to it;
- *aligned*: only where the stored output shows that the run trained the same model on the same dataset, the claim is
  compared with the run's metric of the same name. The pairing and its evidence (a string that must occur in the
  run's `stdout.log`) are written in `PAIRINGS` below; a claim without a pairing is not compared.

K2 (`scripts/auto_search3.py`, `evaluate_k2`) looks up the meaningful numbers of a run's output in the paper's text.
It needs the paper's PDF in `data/pdfs/` (not committed); the stored result is what the document is rendered from.
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

from src.claim_metric_map import load_claim_map
from src.config import DEFAULT_TOLERANCE
from src.multi_seed import load_seed_metric_results
from src.score_run import load_run, score_run

DATA = project_root / "data"
DECISIONS_PATH = DATA / "claims" / "review_decisions.json"
OUT_JSON = DATA / "real_verdicts" / "verdicts.json"
OUT_DOC = project_root / "docs" / "REAL_VERDICTS.md"
PDF_DIR = DATA / "pdfs"

# (paper_id, label of the condition, run directory relative to data/, license of the paper's repository)
RUNS: list[tuple[str, str, str, str]] = [
    ("paper_003", "Pilot 3", "pilot3_runs/paper_003", "Apache-2.0"),
    ("paper_003", "memory run 1", "memory_runs/paper_003", "Apache-2.0"),
    ("paper_003", "memory run 2", "memory_runs/paper_003_run2", "Apache-2.0"),
    ("paper_003", "CPU run", "cpu_runs/paper_003", "Apache-2.0"),
    ("paper_003", "env-cache run 1", "env_cache_runs/first_run/paper_003", "Apache-2.0"),
    ("paper_003", "env-cache run 2", "env_cache_runs/second_run/paper_003", "Apache-2.0"),
    ("paper_004", "memory run", "memory_runs/paper_004", "MIT"),
    ("paper_006", "Pilot 3", "pilot3_runs/paper_006", "Apache-2.0"),
    ("paper_006", "memory run 2", "memory_runs/paper_006_run2", "Apache-2.0"),
    ("paper_006", "CPU run", "cpu_runs/paper_006", "Apache-2.0"),
    ("paper_102", "Pilot 4", "pilot4_runs/paper_102", "MIT"),
    ("synthetic_control", "run 1", "synthetic_control/run1/synthetic_control", "MIT"),
    ("synthetic_control", "run 2", "synthetic_control/run2/synthetic_control", "MIT"),
]

# Claims of the synthetic control paper (scripts/synthetic_control.py): one true, one false on purpose. They are not
# in review_decisions.json because the paper is not a seed paper.
SYNTHETIC_CLAIMS = [
    {"paper_id": "synthetic_control", "query_id": "true_claim", "metric_name": "accuracy", "dataset": "none (fixed print)",
     "model_variant": "none", "value": 0.9},
    {"paper_id": "synthetic_control", "query_id": "false_claim", "metric_name": "accuracy", "dataset": "none (fixed print)",
     "model_variant": "none", "value": 0.5},
]
# K2 needs the paper's text; the PDF of each paper in data/pdfs/
PDFS = {"paper_003": "paper_003.pdf", "paper_004": "paper_004.pdf", "paper_006": "paper_006.pdf",
        "paper_102": "2602.13045.pdf"}

# (paper_id, query_id) -> pairing. `metric`: the run metric the claim is compared with, or None when the run does not
# measure what the claim states. `evidence`: strings that must occur in the run's stdout.log, otherwise the pairing is
# reported as unverified. `reason`: why the comparison is or is not meaningful.
PAIRINGS: dict[tuple[str, str], dict[str, Any]] = {
    ("paper_003", "ft_transformer_rmse"): {
        "metric": "rmse", "evidence": ["ft_transformer_default_0", "california_housing"],
        "reason": "the run trains FT-Transformer on California Housing (config path and output directory in stdout.log) and "
                  "prints the final test RMSE, which the extractor stored as `rmse`"},
    ("paper_003", "resnet_rmse"): {
        "metric": None, "evidence": ["ft_transformer_default_0"],
        "reason": "the run trains FT-Transformer only; a ResNet number is never produced, so nothing can be compared"},
    ("paper_003", "xgboost_rmse"): {
        "metric": None, "evidence": ["ft_transformer_default_0"],
        "reason": "the run trains FT-Transformer only; an XGBoost number is never produced, so nothing can be compared"},
    ("paper_004", "tabr_average_rank"): {
        "metric": None, "evidence": ["lr"],
        "reason": "the paper claims an average rank over a benchmark; the stored metrics of the run are `lr` and "
                  "`weight_decay`, which are hyperparameters printed by the training script, not results"},
    ("paper_004", "xgboost_average_rank"): {
        "metric": None, "evidence": ["lr"],
        "reason": "the paper claims an average rank over a benchmark for XGBoost; the run is a TabR training and its stored "
                  "metrics are hyperparameters (`lr`, `weight_decay`)"},
    ("paper_006", "arcene_auroc"): {
        "metric": None, "evidence": ["dset_id=1461"],
        "reason": "the claim belongs to the Arcene dataset; the run reads OpenML dataset 1461 (bank-marketing). The claim and "
                  "the run do not match, so the decision is meaningless"},
    ("paper_006", "xgboost_arcene_auroc"): {
        "metric": None, "evidence": ["dset_id=1461"],
        "reason": "the claim is an XGBoost number on Arcene; the run trains SAINT on OpenML dataset 1461 (bank-marketing). "
                  "The claim and the run do not match, so the decision is meaningless"},
}


def accepted_claims() -> list[dict[str, Any]]:
    data = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
    return [c for c in data["claims"] if c.get("review_status") == "accepted"]


def evidence_found(run_dir: Path, needles: list[str]) -> bool:
    stdout = run_dir / "stdout.log"
    text = stdout.read_text(encoding="utf-8", errors="replace") if stdout.is_file() else ""
    return bool(needles) and all(n in text for n in needles)


def _scored(paper_id: str, license_name: str, claims: dict[str, float], record: dict[str, Any], report: dict[str, Any],
            run_dir: Path, claim_map: dict[str, Any] | None = None) -> dict[str, Any]:
    result = score_run(paper_id, license_name, claims, record, report, run_dir, None, claim_map=claim_map,
                       seed_metric_results=load_seed_metric_results(paper_id))
    bd = result["breakdown"]
    return {"tier1": bd.tier1_build, "tier2": bd.tier2_metrics, "total": bd.total_score, "status": bd.status_label}


def verdict_rows(run_root: Path = DATA, claims: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """One row per (run, accepted claim); a paper without an accepted claim gets one row without a claim."""
    claims = (accepted_claims() if claims is None else claims) + SYNTHETIC_CLAIMS
    claim_map = load_claim_map()
    rows: list[dict[str, Any]] = []
    for paper_id, label, rel, license_name in RUNS:
        run_dir = run_root / rel
        record, report = load_run(run_dir)
        paper_claims = [c for c in claims if c["paper_id"] == paper_id]
        by_id = {c["query_id"]: c["value"] for c in paper_claims}
        # The synthetic claims are scored one at a time and keyed by metric name (scripts/synthetic_control.py): there is no
        # CLI view for them
        no_view = {"tier2": None, "status": None, "total": None}
        as_scored = (_scored(paper_id, license_name, by_id, record, report, run_dir, claim_map) if paper_id != "synthetic_control"
                     else no_view)
        before = (_scored(paper_id, license_name, by_id, record, report, run_dir, None) if paper_id != "synthetic_control"
                  else no_view)
        metrics = {k: float(v) for k, v in (report.get("metrics") or {}).items() if isinstance(v, (int, float))}
        base = {"paper_id": paper_id, "run": label, "run_dir": f"data/{rel}", "run_status": (record.get("run") or {}).get("status"),
                "run_metrics": metrics, "cli_tier2": as_scored["tier2"], "cli_status": as_scored["status"],
                "cli_total": as_scored["total"], "before_tier2": before["tier2"], "before_status": before["status"],
                "before_total": before["total"]}
        if not paper_claims:
            rows.append({**base, "query_id": None, "map_decision": None, "claimed": None, "reproduced": None, "abs_diff": None,
                         "rel_diff": None, "aligned_tier2": None, "aligned_status": None, "comparable": False,
                         "reason": "no claim of this paper has been accepted, so Tier 2 is the neutral 70.0 baseline for 'no "
                                   "claims', not a measurement; a run with nothing compared is labeled Needs Review (#540)"})
            continue
        for claim in paper_claims:
            pairing = PAIRINGS.get((paper_id, claim["query_id"]))
            decision = ((claim_map or {}).get(paper_id) or {}).get(claim["query_id"], {}).get("decision")
            row = {**base, "query_id": claim["query_id"], "map_decision": decision, "metric_name": claim["metric_name"],
                   "dataset": claim["dataset"], "model_variant": claim["model_variant"], "claimed": claim["value"], "reproduced": None, "abs_diff": None,
                   "rel_diff": None, "aligned_tier2": None, "aligned_status": None, "comparable": False}
            if paper_id == "synthetic_control":
                pairing = {"metric": "accuracy", "evidence": ["accuracy"],
                           "reason": "the script prints the fixed line `accuracy: 0.9000`; the claim 0.9 is true and 0.5 is false by construction"}
            if pairing is None:
                row["reason"] = "no pairing between this claim and the run's output was established: not compared"
            else:
                ok = evidence_found(run_dir, pairing["evidence"])
                row["reason"] = pairing["reason"] + ("" if ok else " (evidence string not found in this run's stdout.log: not verified)")
                metric = pairing["metric"]
                if metric and ok and metric in metrics:
                    value = metrics[metric]
                    aligned = _scored(paper_id, license_name, {metric: claim["value"]}, record, report, run_dir)
                    row.update({"comparable": True, "reproduced": value, "abs_diff": abs(value - claim["value"]),
                                "rel_diff": abs(value - claim["value"]) / max(abs(claim["value"]), 1e-6),
                                "aligned_tier2": aligned["tier2"], "aligned_status": aligned["status"]})
            rows.append(row)
    return rows


def _run_metrics(run_dir: Path) -> dict[str, float]:
    _, report = load_run(run_dir)
    return {k: float(v) for k, v in (report.get("metrics") or {}).items() if isinstance(v, (int, float))}


def _in_paper(a3: Any, pages: list[str], value: float) -> dict[str, Any]:
    """Does the number occur in the paper's text, as a fraction (`0.459`) or as a percent (`45.9`)? Literal string match."""
    spellings = [repr(value), repr(round(value * 100, 6))]
    for spelling in spellings:
        hits = a3.match_numbers([{"number": spelling, "line": "", "percent": False}], pages)
        if hits:
            return {"found": True, "as": spelling, "page": hits[0]["pages"][0]["page"], "paper_line": hits[0]["pages"][0]["line"]}
    return {"found": False, "as": None, "page": None, "paper_line": None}


def k2_results(run_root: Path = DATA, pdf_dir: Path = PDF_DIR, claims: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """K2 on each run's stdout.log against the paper's PDF; a missing PDF is reported, not guessed.

    Besides the K2 verdict, two direct checks per run: does each accepted claim value occur in the paper (a sanity check
    of the claim), and does each headline metric the extractor stored for the run occur in the paper?
    """
    from scripts import auto_search3 as a3
    from src.pdf_text import extract_pdf_text

    claims = accepted_claims() if claims is None else claims

    pages_of: dict[str, list[str] | None] = {}
    out = []
    for paper_id, label, rel, _ in RUNS:
        if paper_id not in PDFS:
            continue
        if paper_id not in pages_of:
            path = pdf_dir / PDFS[paper_id]
            pages_of[paper_id] = extract_pdf_text(path, cache_dir=None).pages if path.is_file() else None
        item = {"paper_id": paper_id, "run": label, "run_dir": f"data/{rel}", "pdf": f"data/pdfs/{PDFS[paper_id]}"}
        pages = pages_of[paper_id]
        stdout = run_root / rel / "stdout.log"
        if pages is None:
            item.update({"available": False, "note": "PDF missing, not verified"})
        elif not stdout.is_file():
            item.update({"available": False, "note": "stdout.log missing, not verified"})
        else:
            result = a3.evaluate_k2(stdout.read_text(encoding="utf-8", errors="replace"), pages)
            item.update({"available": True, "passed": result["passed"], "numbers_in_output": result["numbers_in_output"],
                         "numbers_found_in_paper": result["numbers_found_in_paper"],
                         "numbers_found_on_table_page": result["numbers_found_on_table_page"], "pdf_pages": result["pdf_pages"],
                         "claim_values": [{"query_id": c["query_id"], "value": c["value"], **_in_paper(a3, pages, c["value"])}
                                          for c in claims if c["paper_id"] == paper_id],
                         "run_metrics_in_paper": [{"metric": k, "value": v, **_in_paper(a3, pages, v)} for k, v in
                                                  _run_metrics(run_root / rel).items()
                                                  if a3.significant_digits(repr(v)) >= a3.MIN_SIGNIFICANT_DIGITS],
                         "examples": [{"number": m["number"], "page": m["pages"][0]["page"], "paper_line": m["pages"][0]["line"],
                                       "output_line": m["line"]} for m in result["matches"] if m["on_table_page"]][:3]})
        out.append(item)
    return out


# ---------------------------------------------------------------- the document


def _f(value: float | None, digits: int = 4) -> str:
    return "-" if value is None else f"{value:.{digits}f}".rstrip("0").rstrip(".") if value != int(value) else f"{value:.0f}"


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.2f}%"


def render(doc: dict[str, Any]) -> str:
    rows, k2 = doc["rows"], doc["k2"]
    out = [
        "# Real Verdicts", "",
        ("> Generated by `scripts/real_verdicts.py` from `data/real_verdicts/verdicts.json` (#494). Every number below comes "
        "from a stored run record, the accepted claims in `data/claims/review_decisions.json`, `src/score_run.py`, or the K2 "
        "check of `scripts/auto_search3.py`. Nothing is simulated and nothing was run for this document."), "",
        "## 1. What this document shows and does not show", "",
        "**It shows**", "",
        ("- What the scorer says today on every real, completed, stored run, next to the claims a person accepted, with the "
        "reason why each decision is meaningful or not, and what it said before the claim map existed (#507, #509)."),
        ("- That a run whose model, dataset and metric match a claim (`paper_003`, FT-Transformer on California Housing) is "
        "now compared by the CLI path through the claim map: the numbers are close and the scorer agrees. This is one claim and "
        "one number, not a confirmed reproduction."),
        ("- What the K2 check (numbers of the run's output occur in the paper's text) does on the real runs: it passes "
        "`paper_003` by coincidence of dense numbers, and fails `paper_006` and `paper_102` (section 4). The expected "
        "positive control was not obtained."),
        "- That the synthetic control, whose answer is known, gets the right decision for a true and for a false claim.", "",
        "**It does not show**", "",
        ("- That any paper's table was reproduced by its README command. `paper_003` is one number close to one claim; every "
        "other claim of the real papers is either not produced by the run or belongs to another dataset."),
        ("- That the scorer is right on real papers in general. For a real paper nobody knows the true answer; a label that "
        "follows from the numbers is not a validation. The only known-answer cases are the synthetic control and the "
        "hand-made claims of the tolerance probe (`docs/TOLERANCE_PROBE.md`)."),
        "- A success rate. The runs are the ones that happened to complete; they are not a sample.",
        "- Anything about claims nobody accepted. `paper_102` has none, so its Tier 2 is a neutral baseline.", "",
        "## 2. The scorer as the CLI uses it, before and with the claim map", "",
        ("`cli.py score --from-run` scores all accepted claims of a paper together. An accepted claim is keyed by its question ID "
        "(for example `ft_transformer_rmse`); the run's metrics are keyed by the name the extractor found (`rmse`). **Before the "
        "mapping** (the state until #509) the two never agreed, so every real claim was reported as not found: Tier 2 was 0 and "
        "the label `Needs Review`. **With the map** (`data/claim_metric_map.json`, `docs/CLAIM_METRIC_MAP.md`) a claim is compared "
        "with the run metric of the same model, dataset, measure and split; a claim for which the run has no counterpart does not "
        "enter Tier 2. When no claim is left, Tier 2 is the neutral baseline of 'no claims'. The 'before' column is kept so that "
        "the change can be read."), "",
        ("| Paper | Run | Run status | Run metrics | Before the mapping: Tier 2 / total / label | With the map: Tier 2 / total / label |"),
        "|---|---|---|---|---|---|"]
    seen = set()
    for r in rows:
        key = (r["paper_id"], r["run"])
        if key in seen:
            continue
        seen.add(key)
        metrics = ", ".join(f"{k}={_f(v)}" for k, v in list(r["run_metrics"].items())[:4]) or "none"
        if len(r["run_metrics"]) > 4:
            metrics += f", ... ({len(r['run_metrics'])} in all)"
        if r["cli_status"] is None:
            before = now = "- (scored one claim at a time)"
        else:
            before = f"{_f(r['before_tier2'], 1)} / {_f(r['before_total'], 2)} / {r['before_status']}"
            now = f"{_f(r['cli_tier2'], 1)} / {_f(r['cli_total'], 2)} / {r['cli_status']}"
        out.append(f"| {r['paper_id']} | {r['run']} (`{r['run_dir']}`) | {r['run_status']} | {metrics} | {before} | {now} |")
    out += ["", "## 3. Claim by claim", "",
            (f"Tolerance: {DEFAULT_TOLERANCE:.0%} (`DEFAULT_TOLERANCE`). \"Aligned\" is the Tier 2 of that single claim compared with "
            "the run's metric of the same name, only where the pairing is established; `-` means not compared."), "",
            "| Paper | Run | Claim (question ID) | Map decision | Claimed | Reproduced | Abs diff | Rel diff | Aligned Tier 2 | Aligned label | Why |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        claim = r["query_id"] or "(none accepted)"
        out.append(f"| {r['paper_id']} | {r['run']} | {claim} | {r['map_decision'] or '-'} | {_f(r['claimed'])} | {_f(r['reproduced'])} | {_f(r['abs_diff'])} | "
                   f"{_pct(r['rel_diff'])} | {_f(r['aligned_tier2'], 1)} | {r['aligned_status'] or '-'} | {r['reason']} |")
    out += ["", "## 4. K2 positive control", "",
            ("K2 passes when at least 2 different meaningful numbers of the run's output occur in the paper's text and at least "
            "one of them on a page with a `Table` caption (`scripts/auto_search3.py`, `evaluate_k2`). A pass is a string match, "
            "not a verified result. PDFs are in `data/pdfs/` (not committed)."), "",
            "| Paper | Run | K2 passed | Numbers in output | Found in paper | Found on a table page | PDF pages |", "|---|---|---|---|---|---|---|"]
    for k in k2:
        if k["available"]:
            out.append(f"| {k['paper_id']} | {k['run']} | {'yes' if k['passed'] else 'no'} | {k['numbers_in_output']} | "
                       f"{k['numbers_found_in_paper']} | {k['numbers_found_on_table_page']} | {k['pdf_pages']} |")
        else:
            out.append(f"| {k['paper_id']} | {k['run']} | {k['note']} | - | - | - | - |")
    out += ["", ("Do the claim values and the run's own headline metrics occur in the paper? (literal match, as a fraction or as a "
            "percent; first run of each paper)"), "",
            "| Paper | What | Value | In the paper |", "|---|---|---|---|"]
    shown = set()
    for k in k2:
        if k["available"] and k["paper_id"] not in shown:
            shown.add(k["paper_id"])
            for c in k["claim_values"]:
                where = f"yes, `{c['as']}` on page {c['page']}" if c["found"] else "no"
                out.append(f"| {k['paper_id']} | accepted claim `{c['query_id']}` | {_f(c['value'])} | {where} |")
            for c in k["run_metrics_in_paper"]:
                where = f"yes, `{c['as']}` on page {c['page']}" if c["found"] else "no"
                out.append(f"| {k['paper_id']} | run metric `{c['metric']}` ({k['run']}) | {_f(c['value'])} | {where} |")
            if not k["run_metrics_in_paper"]:
                out.append(f"| {k['paper_id']} | run metrics ({k['run']}) | - | none has three significant digits |")
    out += ["", "Numbers K2 matched for `paper_003` (first run; the numbers are the same in every run of it):", ""]
    for k in k2:
        if k["available"] and k["paper_id"] == "paper_003" and k["examples"]:
            for e in k["examples"]:
                out.append(f"- `{e['number']}` on page {e['page']}: output line `{e['output_line'][:70]}`; paper line `{e['paper_line'][:90]}`")
            break
    p6 = next((r for r in rows if r["paper_id"] == "paper_006"), None)
    findings = FINDINGS.replace("@P6@", f"Tier 2 {_f(p6['cli_tier2'], 1)}, total {_f(p6['cli_total'], 2)}, `{p6['cli_status']}`" if p6 else "-")
    out += ["", doc["k2_reading"], "", findings, ""]
    return "\n".join(out) + "\n"


K2_READING = """### Reading the K2 result

The expectation was that the runs of `paper_003`, `paper_006` and `paper_102` pass K2. The stored records say otherwise:

- **`paper_003`: K2 passes, but not for the reason a positive control needs.** The matched numbers are values from the
  training log (`rmse = 0.503`, `0.499`, `0.486`, ...) that the paper's tables print for *other* models (MLP, SNN, ResNet,
  ...). The run's final test RMSE (`0.473`) does not occur in the paper, and the claim it should reproduce (`0.459`) is
  not printed by the run. With about 190 three-decimal numbers in the output and many tables in the paper, a few chance
  matches are expected. The pass is a coincidence of dense numbers, not a table match.
- **`paper_006`: K2 fails, for two reasons that K2 cannot tell apart.** The run prints AUROC as a fraction with three
  decimals (`0.929`) and accuracy as a percent with three decimals; the paper prints percent with one or two decimals
  (`93.3` for SAINT on Bank, Table 2, page 7). A literal match cannot cross that scale. Even after the conversion the run's
  best-model AUROC (0.929) is not the paper's printed value (0.933). The accepted claims (`91.04`, `81.41`) belong to
  Arcene, which the run never reads.
- **`paper_102`: K2 fails, and it should.** `code/examples/quick_start.py` (read at the pinned commit
  `ebb98157451122b6a1189d2597a77eca0839ac4c`) builds its data with `sklearn.datasets.make_classification` (`n_samples=1200`,
  `random_state=42`); its output (`AUPRC 0.7131`, `0.7461`) is the result of a toy example, not a table of the paper.
  No claim of this paper was accepted, so there was nothing to compare in any case.
- **`paper_004`:** the output holds hyperparameters; K2 says nothing about the paper's results.

**Conclusion.** K2 has not caught a real "the run reproduces a printed table value" case in this repository, because no
such case exists here: of the completed real runs, only `paper_003` produces a number for an accepted claim, and it is
0.473 against the printed 0.459, a different number. K2 as written also cannot match a fraction against a percent. A
positive control for K2 still needs a run whose output prints a table value of its paper. This is a finding, not a
defect that this document fixes."""


FINDINGS = """## 5. Findings

1. **Before the mapping the CLI path never matched a real claim; now it does where the run has a counterpart.** Claims were
   keyed by question ID (`ft_transformer_rmse`), the run's metrics by the extracted name (`rmse`), so Tier 2 was 0.0 and the
   label `Needs Review` for every real run, even where the run printed a number for the claim (`paper_003`). With the claim map
   (section 2, "with the map") the CLI path compares `ft_transformer_rmse` with `rmse`; the other claims are excluded from Tier 2
   with the reason. The 'before' column keeps the old result. The map is a proposal that the owner may revise.
2. **`paper_003`, with the map: the decision is meaningful, for one claim.** Same model, dataset and metric; 0.473 against 0.459 is
   3.05% apart, inside the 5% tolerance, so Tier 2 is 100 and the label `Verified`. It is one claim and one number, not a confirmed
   reproduction. Whether a 0.014 RMSE gap should count as reproduced is a tolerance question (`docs/TOLERANCE_PROBE.md`), not a
   fact this document can settle. The ResNet and XGBoost claims of the paper are not produced by the run (`no_counterpart`).
3. **`paper_006`: claim and run do not match, so the claims are excluded.** Both accepted claims are Arcene numbers; the run reads
   OpenML dataset 1461 (bank-marketing). With the map nothing is left to compare: @P6@. Nothing was compared, so the label is
   `Needs Review` (finding 6); Tier 2 is not a measurement. The paper's own table has a SAINT value for Bank (`93.3`, page 7), but nobody
   accepted it as a claim, so it is not scored here.
4. **`paper_006`: the stored `auroc` (0.892) is the last logged test line, not the run's "AUROC on best model: 0.929".** The
   extractor keeps the last occurrence of a name; here that is an epoch line. Reported, not changed.
5. **`paper_004`: the stored metrics are hyperparameters** (`lr`, `weight_decay`); the claims are average ranks, so both claims
   are excluded (`no_counterpart`) and Tier 2 is the neutral baseline.
6. **A label without a comparison (fixed in #540): `paper_102` (no claim accepted), and with the map every paper whose claims are
   all `no_counterpart`.** With no claim compared Tier 2 is a neutral 70.0, and with a clean build the total reached the partial
   threshold, so these papers were labeled `Partially Verified` on the build tiers alone. Since #540 a run with nothing compared is
   labeled `Needs Review` and its summary says that no accepted claim could be compared; `Verified` and `Partially Verified` need at
   least one claim compared with a metric of the run. The thresholds and the neutral 70.0 are unchanged.
7. **The synthetic control behaves as designed.** The true claim (0.9) scores 100 / `Verified`, the false claim (0.5) scores
   0 / `Needs Review`, on both runs. This is the only known-answer case among the rows.
8. **K2:** see section 4."""


def build(run_root: Path = DATA, pdf_dir: Path = PDF_DIR) -> dict[str, Any]:
    return {"note": "generated by scripts/real_verdicts.py; do not edit by hand", "tolerance": DEFAULT_TOLERANCE,
            "rows": verdict_rows(run_root), "k2": k2_results(run_root, pdf_dir), "k2_reading": K2_READING}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--render", action="store_true", help="rewrite the document from the stored verdicts.json")
    parser.add_argument("--check", action="store_true", help="fail if the document differs from verdicts.json")
    args = parser.parse_args(argv)
    if args.render or args.check:
        text = render(json.loads(OUT_JSON.read_text(encoding="utf-8")))
        if args.check:
            if OUT_DOC.read_text(encoding="utf-8") != text:
                print(f"{OUT_DOC} is out of date: run scripts/real_verdicts.py --render")
                return 1
            print("docs/REAL_VERDICTS.md matches data/real_verdicts/verdicts.json")
            return 0
    else:
        doc = build()
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        text = render(doc)
    OUT_DOC.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_DOC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
