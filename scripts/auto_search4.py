#!/usr/bin/env python3
"""Automatic search, round 4 (#517): the walk of round 3 with the improved match test K2 v2.

    python scripts/auto_search4.py pool [--stage 9]   # run the searches of one stage once; write data/auto_search4/pool.json
    python scripts/auto_search4.py run                # S1 to S6, K1 in the sandbox, K2 v1 and v2 against the paper; resumable
    python scripts/auto_search4.py report             # the results section of docs/AUTO_SEARCH_ROUND4.md, from the stored files
    python scripts/auto_search4.py reeval             # K2 v2 on the stored outputs of the K1 passers of round 3

The rules are in docs/AUTO_SEARCH_ROUND4.md (K2 v2 is its section 3); everything else is docs/AUTO_SEARCH_ROUND3.md. K2 v1 is the
function of scripts/auto_search3.py, unchanged; K2 v2 is new and additional, and both results are stored for every run. A K2 pass
is a "match candidate", never a verified result, and the list is selected and not a success rate.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts import auto_search3 as a3
from scripts import corpus_expansion as ce
from scripts import demo_set
from src.config import SEED_PAPERS_PATH
from src.pdf_text import extract_pdf_text, repair_split_numbers

OUT_DIR = project_root / "data" / "auto_search4"
PDF_DIR = project_root / "data" / "pdfs" / "auto_search4"
ROUND3_DIR = project_root / "data" / "auto_search3"
RULES_DOC = "docs/AUTO_SEARCH_ROUND4.md"
STAGE_TOPICS: dict[int, list[str]] = {
    8: ["optimal-control", "robotics", "computer-vision", "remote-sensing", "geoscience", "climate", "finance", "healthcare",
        "materials-science", "astronomy", "speech", "audio", "tabular-deep-learning", "automl", "interpretability",
        "uncertainty-estimation"],
    9: ["federated-learning", "active-learning", "transfer-learning", "domain-adaptation", "anomaly-detection", "clustering",
        "graph-neural-networks", "reinforcement-learning", "knowledge-graph", "text-classification", "sentiment-analysis",
        "machine-translation", "image-classification", "object-detection", "segmentation", "forecasting"],
    10: ["medical-image-analysis", "time-series-classification", "representation-learning", "contrastive-learning",
         "self-supervised-learning", "meta-learning", "few-shot-learning", "continual-learning", "multi-task-learning",
         "neural-architecture-search", "model-compression", "adversarial-attacks", "adversarial-robustness", "graph-embedding",
         "link-prediction", "community-detection"],
    11: ["causal-discovery", "counterfactual", "fairness", "privacy", "differential-privacy", "recommendation",
         "collaborative-filtering", "matrix-factorization", "tensor-decomposition", "compressed-sensing", "dictionary-learning",
         "manifold-learning", "kernel-density-estimation", "bandits", "multi-armed-bandit", "sparse-regression"],
    12: ["variational-inference", "mcmc", "normalizing-flows", "diffusion-models", "gan", "vae", "autoencoder", "attention",
         "lstm", "cnn", "rnn", "transformer", "bert", "word-embeddings", "question-answering", "named-entity-recognition"],
    13: ["traffic", "energy", "power-systems", "drug-discovery", "protein", "molecular-dynamics", "cheminformatics",
         "agriculture", "earth-observation", "weather", "hydrology", "seismology", "fluid-dynamics", "wireless-communication",
         "scheduling", "combinatorial-optimization"],
    14: ["data-augmentation", "knowledge-distillation", "graph-learning", "hypergraph", "point-cloud",
        "3d-reconstruction", "pose-estimation", "video-understanding", "visual-question-answering",
        "image-generation", "super-resolution", "denoising", "ocr", "speaker-recognition", "music", "eeg"],
    15: ["bayesian-neural-networks", "conformal-prediction", "calibration", "out-of-distribution-detection",
        "outlier-detection", "imbalanced-learning", "semi-supervised-learning", "weak-supervision", "crowdsourcing",
        "ranking", "learning-to-rank", "metric-learning", "similarity-search", "hashing", "sketching",
        "streaming-algorithms"],
    16: ["numerical-optimization", "convex-optimization", "stochastic-optimization", "gradient-descent", "sgd",
        "adam", "learning-rate", "regularization", "dropout", "batch-normalization", "activation-functions",
        "loss-functions", "neural-ode", "physics-informed", "pinn", "surrogate-model"],
    17: ["survival", "epidemic", "covid-19", "genetics", "single-cell", "proteomics", "neuroimaging", "fmri", "ecg",
        "clinical", "electronic-health-records", "drug-repurposing", "ecology-modeling", "crop",
        "remote-sensing-imagery", "satellite"],
    18: ["decision-tree", "gradient-boosting", "logistic-regression", "linear-regression", "naive-bayes", "k-means",
        "pca", "nearest-neighbors", "knn", "hidden-markov-model", "kalman-filter", "particle-filter",
        "state-space-model", "gaussian-mixture-model", "expectation-maximization", "markov-chain"],
    19: ["lasso", "ridge-regression", "elastic-net", "bootstrap", "hypothesis-testing", "bayesian-statistics",
        "mixed-effects", "time-series-decomposition", "spectral-analysis", "wavelet", "fourier-transform",
        "filtering", "change-point-detection", "sequence-alignment", "phylogenetics", "protein-structure"],
    20: ["policy-gradient", "q-learning", "multi-agent", "imitation-learning", "offline-reinforcement-learning",
        "model-based-rl", "planning", "reward-learning", "inverse-reinforcement-learning", "control",
        "trajectory-optimization", "model-predictive-control", "path-planning", "slam", "autonomous-driving",
        "drone"],
    21: ["text-generation", "language-model", "summarization", "information-extraction", "text-mining", "retrieval",
        "information-retrieval", "search-engine", "embeddings", "dialogue", "chatbot", "prompt",
        "in-context-learning", "fine-tuning", "lora", "tokenization"],
}
ID_PREFIX = "a4_"
MAX_BOTH = 5
ROUNDED_DIGITS = 3
VARIANT_ORDER = ("same", "x100", "div100")


# ---------------------------------------------------------------- the pool


def queries(stage: int) -> list[str]:
    return [f"{a3.COMMON} topic:{topic}" for topic in STAGE_TOPICS[stage]]


def earlier_round_repos(root: Path = project_root) -> set[str]:
    """Round 3's list of earlier repositories, and the whole pool of round 3 (checked or not)."""
    names = a3.earlier_round_repos(root)
    for path in sorted((root / "data" / "auto_search3").glob("pool*.json")):
        names |= {c["full_name"].lower() for c in json.loads(path.read_text(encoding="utf-8"))["candidates_in_order"]}
    return names


# ---------------------------------------------------------------- K2 v2


def normalize_output(text: str) -> str:
    """Read a decimal comma of the output as a decimal point (`0,8886` is `0.8886`, `88,86` is `88.86`). A group of exactly
    three digits stays a thousands separator, and a comma that stands in a list (`1,2,3`, `10,20,30`) is left as it is."""
    return re.sub(r"(?<![\d.,])(-?\d{1,3}),(\d{1,2}|\d{4,})(?![\d,.])", r"\1.\2", text)


def shift(canonical: str, places: int) -> str:
    """An exact decimal shift: `0.8886` by 2 is `88.86`, `88.86` by -2 is `0.8886`."""
    return format(Decimal(canonical).scaleb(places), "f")


def round_significant(canonical: str, digits: int = ROUNDED_DIGITS) -> str:
    """Round half up to `digits` significant digits, in plain notation (`0.8886` is `0.889`, `88.86` is `88.9`)."""
    value = Decimal(canonical)
    quantum = Decimal(1).scaleb(value.adjusted() - digits + 1)
    return format(value.quantize(quantum, rounding=ROUND_HALF_UP), "f")


def spellings(canonical: str) -> list[tuple[str, str]]:
    """The (variant, spelling) pairs of one number, in the order of docs/AUTO_SEARCH_ROUND4.md section 3."""
    out = [("same", canonical)]
    if re.search(r"[eE]", canonical):
        return out
    try:
        magnitude = abs(Decimal(canonical))
        if 0 < magnitude <= 1:
            out.append(("x100", shift(canonical, 2)))
        if 1 < magnitude <= 100:
            out.append(("div100", shift(canonical, -2)))
        for variant, text in list(out):
            if "." in text and a3.significant_digits(text) > ROUNDED_DIGITS:
                rounded = round_significant(text)
                if rounded != text:
                    out.append((f"{variant}+round3", rounded))
    except (InvalidOperation, ValueError):
        pass
    return out


def match_numbers_v2(numbers: list[dict[str, Any]], pages: list[str]) -> list[dict[str, Any]]:
    """The numbers of the output that the paper holds in one of the spellings (the first that is found is stored). A match
    by a variant other than `same` counts only on a page with a `Table <n>` line (the guard against a chance match)."""
    pages = [repair_split_numbers(p) for p in pages]
    on_table = [a3.table_page(p) for p in pages]
    hits = []
    for item in numbers:
        for variant, spelling in spellings(item["number"]):
            pattern = a3.paper_pattern(spelling)
            found = []
            for index, text in enumerate(pages):
                if variant != "same" and not on_table[index]:
                    continue
                match = pattern.search(text)
                if match:
                    found.append({"page": index + 1, "table_page": on_table[index], "line": a3.line_around(text, match.start())})
            if found:
                hits.append({**item, "variant": variant, "searched": spelling, "pages": found[:a3.MAX_PAGES_STORED],
                             "pages_total": len(found), "on_table_page": any(f["table_page"] for f in found)})
                break
    return hits


def evaluate_k2v2(output: str, pages: list[str]) -> dict[str, Any]:
    """K2 v2: at least 2 different meaningful numbers of the output are found in the paper (same spelling, a fraction as a
    percent or the reverse, or rounded to 3 significant digits) and at least one of them on a page with a `Table <n>` line."""
    numbers = a3.meaningful_numbers(normalize_output(output))
    hits = match_numbers_v2(numbers, pages)
    return {"passed": len(hits) >= a3.MIN_MATCHED_NUMBERS and any(h["on_table_page"] for h in hits),
            "numbers_in_output": len(numbers), "numbers_found_in_paper": len(hits),
            "numbers_found_on_table_page": sum(1 for h in hits if h["on_table_page"]), "pdf_pages": len(pages), "matches": hits,
            "note": "match candidate only; a string match with scale conversion and rounding, not verified"}


def k2_both(output: str, pages: list[str]) -> dict[str, Any]:
    """The v1 result with the v2 result inside it under `v2`: both are stored for every run."""
    return {**a3.evaluate_k2(output, pages), "v2": evaluate_k2v2(output, pages)}


def k2_for_run(entry: dict[str, Any], record_dir: Path, throttle: a3.Throttle | None = None,
               pdf_folder: Path = PDF_DIR) -> dict[str, Any]:
    arxiv_id = ce.find_arxiv_id(entry["paper_url"]) or ""
    try:
        path = a3.fetch_pdf(arxiv_id, throttle or a3.Throttle(), pdf_folder)
        pages = extract_pdf_text(path, cache_dir=None).pages
    except Exception as exc:  # noqa: BLE001 - the paper could not be read: no K2 pass, and the record says why
        failed = {"passed": False, "error": f"{type(exc).__name__}: {exc}"[:300], "matches": []}
        return {**failed, "v2": dict(failed)}
    stdout = record_dir / "stdout.log"
    output = stdout.read_text(encoding="utf-8", errors="replace") if stdout.is_file() else ""
    return {**k2_both(output, pages), "arxiv_id": arxiv_id}


# ---------------------------------------------------------------- the walk


def v2_passed(candidate: dict[str, Any]) -> bool:
    return bool(((candidate.get("k2") or {}).get("v2") or {}).get("passed"))


class Search(a3.Search):
    """The walk of round 3 with another identifier prefix and document, and with K2 v2 counted next to K1 and K2 v1."""

    rules_doc = RULES_DOC
    id_prefix = ID_PREFIX
    note = ("selected, non-representative list; not a success rate; K2 v1 and v2 passers are match candidates, not verified; "
            "K2 v2 can match by chance")

    def counts(self) -> dict[str, int]:
        ran = [c for c in self.evaluations if c.get("k1")]
        k1 = [c for c in ran if c["k1"]["k1_passed"]]
        v1 = [c for c in ran if (c.get("k2") or {}).get("passed")]
        v2 = [c for c in ran if v2_passed(c)]
        return {"evaluated": len(self.evaluations), "runs": len(ran), "k1_passed": len(k1), "k2_passed": len(v1),
                "k2v2_passed": len(v2),
                "both_passed": sum(1 for c in k1 if (c.get("k2") or {}).get("passed") or v2_passed(c)),
                "both_passed_v1": sum(1 for c in k1 if (c.get("k2") or {}).get("passed")),
                "both_passed_v2": sum(1 for c in k1 if v2_passed(c))}

    def stop_reason(self) -> str:
        reason = super().stop_reason()
        return "five_passed_both" if reason == "eight_passed_both" else reason


# ---------------------------------------------------------------- the report


def _interval(passed: int, total: int) -> str:
    return a3._interval(passed, total)


def render_results(document: dict[str, Any], papers: list[dict[str, Any]]) -> str:
    """The results section of docs/AUTO_SEARCH_ROUND4.md, from the stored files only (no hand-typed number)."""
    candidates = document["candidates"]
    ran = [c for c in candidates if c.get("k1")]
    entry = {p["paper_id"]: p for p in papers}
    k1 = [c for c in ran if c["k1"]["k1_passed"]]
    v1 = [c for c in ran if (c.get("k2") or {}).get("passed")]
    v2 = [c for c in ran if v2_passed(c)]
    both1 = [c for c in k1 if (c.get("k2") or {}).get("passed")]
    both2 = [c for c in k1 if v2_passed(c)]
    total = len(ran)
    computed = sum(1 for c in ran if c.get("k2") is not None)
    out = [(f"Generated by `scripts/auto_search4.py report` from `data/auto_search4/evaluation.json` (written "
            f"{document['written_at']}, search started {document['started_at']}) and `data/auto_search4/runs/`; do not edit by hand. "
            f"The search stopped because: `{document['stopped_because']}`."), "",
           ("**This is a selected, non-representative list. The shares below describe only the candidates that were run, under these "
            "rules and this pool. They are not a success rate and not the reproducibility of any field. A K2 pass is a match "
            "candidate (a string match), not a verified result. K2 v2 converts scales and rounds, so it can match by chance.**"), "",
           "### Results 1: What was tried", "",
           f"- Candidates checked against S1 to S6: {len(candidates)}.",
           f"- Candidates that passed S1 to S6 and were run once in the sandbox (tried): {total}.",
           f"- Passed K1: {len(k1)} of {total} (Wilson 95%: {_interval(len(k1), total)}).",
           (f"- Passed K2 v1: {len(v1)} of {total} (Wilson 95%: {_interval(len(v1), total)}); K2 was computed for "
            f"{computed} runs that completed with exit code 0."),
           f"- Passed K2 v2: {len(v2)} of {total} (Wilson 95%: {_interval(len(v2), total)}).",
           f"- Passed both K1 and K2 v1: {len(both1)} of {total} (Wilson 95%: {_interval(len(both1), total)}).",
           f"- Passed both K1 and K2 v2: {len(both2)} of {total} (Wilson 95%: {_interval(len(both2), total)}).", ""]
    rules: dict[str, int] = {}
    for c in candidates:
        if c.get("failed_rule"):
            rules[c["failed_rule"]] = rules.get(c["failed_rule"], 0) + 1
    out += ["First failed static rule of the checked candidates:", "", "| Rule | Candidates |", "|---|---|"]
    out += [f"| {r} | {rules[r]} |" for r in (*demo_set.RULES, "static_error") if r in rules] + [""]
    reasons: dict[str, int] = {}
    for c in ran:
        key = "passed K1" if c["k1"]["k1_passed"] else c["k1"]["category"]
        reasons[key] = reasons.get(key, 0) + 1
    out += ["Outcome of the run test K1 (failure reasons):", "", "| Outcome | Candidates |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in sorted(reasons.items())] + [""]
    out += ["### Results 2: Every run", "",
            "| Id | Repository | Command | Install | Run | Exit | Seconds | K1 | K2 v1 | K2 v2 | Deciding log line |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in ran:
        r = c["k1"]
        e = entry[c["paper_id"]]
        line = (r["log_line"] or "").replace("|", "\\|")
        k2 = c.get("k2")
        first = "-" if k2 is None else ("passed" if k2["passed"] else "no")
        second = "-" if k2 is None else ("passed" if v2_passed(c) else "no")
        out.append(f"| {c['paper_id']} | `{c['full_name']}` | `{e['run_command']}` | {r['install_status']} | {r['run_status']} | "
                   f"{r['exit_code']} | {r['duration_seconds']} | {'passed' if r['k1_passed'] else r['category']} | {first} | {second} | `{line}` |")
    out += ["", "### Results 3: Match candidates (K2 v1 or K2 v2 passed)", ""]
    matched = [c for c in ran if (c.get("k2") or {}).get("passed") or v2_passed(c)]
    if not matched:
        out += ["No candidate passed K2 v1 or K2 v2.", ""]
    for c in matched:
        e = entry[c["paper_id"]]
        r, m = c["k1"], c["k2"]["v2"]
        out += [f"#### {c['paper_id']}: {e['title']}", "",
                f"- Paper: {e['paper_url']}", f"- Repository: {e['repo_url']} at commit `{e['repo_commit']}` ({e['license']})",
                f"- Command: `{e['run_command']}`",
                (f"- Run phase: {r['duration_seconds']} s; install: {r['install_status']}; K1: {'passed' if r['k1_passed'] else r['category']}; "
                 f"K2 v1: {'passed' if c['k2']['passed'] else 'no'}; K2 v2: {'passed' if m['passed'] else 'no'}"),
                (f"- K2 v2: numbers of the output found in the paper: {m['numbers_found_in_paper']} of {m['numbers_in_output']} "
                 f"({m['numbers_found_on_table_page']} on a page with a `Table <n>` line). A string match with scale conversion; not verified."),
                "", "| Number | Variant | Searched | Output line | PDF pages | On a table page |", "|---|---|---|---|---|---|"]
        for h in m["matches"][:30]:
            pages = ", ".join(str(p["page"]) for p in h["pages"])
            out.append(f"| {h['number']} | {h['variant']} | {h['searched']} | `{h['line'][:80].replace('|', chr(92) + '|')}` | {pages} | "
                       f"{'yes' if h['on_table_page'] else 'no'} |")
        out.append("")
    return "\n".join(out) + "\n"


def command_report(out_dir: Path) -> str:
    document = json.loads((out_dir / "evaluation.json").read_text(encoding="utf-8"))
    papers = json.loads((out_dir / "papers.json").read_text(encoding="utf-8"))
    return render_results(document, papers)


# ---------------------------------------------------------------- the re-evaluation of round 3


def command_reeval(round3_dir: Path = ROUND3_DIR, pdf_dir: Path | None = None) -> dict[str, Any]:
    """K2 v2 on the stored outputs (`stdout.log`) of the candidates of round 3 that passed K1. Nothing is run."""
    document = json.loads((round3_dir / "evaluation.json").read_text(encoding="utf-8"))
    papers = {p["paper_id"]: p for p in json.loads((round3_dir / "papers.json").read_text(encoding="utf-8"))}
    pdf_dir = pdf_dir or project_root / "data" / "pdfs" / "auto_search3"
    rows = []
    for c in document["candidates"]:
        if not (c.get("k1") and c["k1"]["k1_passed"]):
            continue
        paper = papers[c["paper_id"]]
        arxiv_id = ce.find_arxiv_id(paper["paper_url"]) or ""
        stdout = round3_dir / "runs" / c["paper_id"] / "stdout.log"
        pdf = a3.pdf_path(arxiv_id, pdf_dir)
        row: dict[str, Any] = {"paper_id": c["paper_id"], "full_name": c["full_name"], "arxiv_id": arxiv_id,
                               "run_command": paper["run_command"], "k2_v1_in_round_3": bool((c.get("k2") or {}).get("passed"))}
        if not stdout.is_file() or not pdf.is_file():
            row.update({"evaluated": False, "note": "stored output or PDF missing: not verified"})
        else:
            pages = extract_pdf_text(pdf, cache_dir=None).pages
            text = stdout.read_text(encoding="utf-8", errors="replace")
            row.update({"evaluated": True, "stdout_truncated": "bytes cut" in text, "v1": a3.evaluate_k2(text, pages),
                        "v2": evaluate_k2v2(text, pages)})
        rows.append(row)
    return {"source": "data/auto_search3/evaluation.json and data/auto_search3/runs/<id>/stdout.log",
            "rules": RULES_DOC, "rows": rows}


def render_reeval(result: dict[str, Any]) -> str:
    out = [f"Generated by `scripts/auto_search4.py reeval` from {result['source']}; nothing was run again.", "",
           "| Id | Repository | arXiv | Output truncated | K2 v1 | K2 v2 | Output numbers | Found (v1) | Found (v2) |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        if not r["evaluated"]:
            out.append(f"| {r['paper_id']} | `{r['full_name']}` | {r['arxiv_id']} | - | - | - | - | - | {r['note']} |")
            continue
        out.append(f"| {r['paper_id']} | `{r['full_name']}` | {r['arxiv_id']} | {'yes' if r['stdout_truncated'] else 'no'} | "
                   f"{'passed' if r['v1']['passed'] else 'no'} | {'passed' if r['v2']['passed'] else 'no'} | "
                   f"{r['v1']['numbers_in_output']} | {r['v1']['numbers_found_in_paper']} | {r['v2']['numbers_found_in_paper']} |")
    out.append("")
    for r in result["rows"]:
        if r.get("evaluated") and r["v2"]["matches"]:
            out += [f"Numbers found by K2 v2 for `{r['paper_id']}` (first 20):", "",
                    "| Number | Variant | Searched | Output line | PDF pages | On a table page |", "|---|---|---|---|---|---|"]
            for h in r["v2"]["matches"][:20]:
                pages = ", ".join(str(p["page"]) for p in h["pages"])
                out.append(f"| {h['number']} | {h['variant']} | {h['searched']} | `{h['line'][:80].replace('|', chr(92) + '|')}` | {pages} | "
                           f"{'yes' if h['on_table_page'] else 'no'} |")
            out.append("")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- the command line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automatic search, round 4: docs/AUTO_SEARCH_ROUND4.md.")
    parser.add_argument("command", choices=["pool", "run", "report", "reeval"])
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    parser.add_argument("--staging-dir", default=".sandbox_staging")
    parser.add_argument("--stage", type=int, choices=sorted(STAGE_TOPICS), default=8, help="pool: which stage to search")
    parser.add_argument("--started-at", default=None, help="run: start of the search as an ISO time with offset (first run only)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)
    if args.command == "report":
        print(demo_set.sanitize(command_report(out_dir)), end="")
        return 0
    if args.command == "reeval":
        print(demo_set.sanitize(json.dumps(command_reeval(), indent=2)), end="\n")
        return 0
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    fetcher = a3.ThrottledFetcher(token, pdf_folder=PDF_DIR)
    excluded = earlier_round_repos()

    def store(stage: int) -> dict[str, Any]:
        return a3.command_pool(fetcher, out_dir, stage, excluded, queries_of=queries, rules=RULES_DOC)

    if args.command == "pool":
        pool = store(args.stage)
        stage = pool["stages"][str(args.stage)]
        print(f"stage {args.stage}: {len(stage['searches'])} searches; {len(stage['removed_as_earlier_round'])} repositories "
              f"of earlier rounds removed; {len(pool['candidates_in_order'])} candidates in the pool")
        return 0
    from scripts import preflight

    preflight.ensure_ready()
    pool = json.loads((out_dir / "pool.json").read_text(encoding="utf-8"))
    staging = Path(args.staging_dir)
    stages_left = [s for s in sorted(STAGE_TOPICS) if str(s) not in pool["stages"]]

    def extend_pool() -> list[str]:
        if not stages_left:
            return []
        return [c["full_name"] for c in store(stages_left.pop(0))["candidates_in_order"]]

    def runner(entry: dict[str, Any], corpus: Path, record_root: Path) -> dict[str, Any]:
        return a3.sandbox_runner(entry, corpus, record_root, staging)

    throttle = fetcher.throttle
    search = Search([c["full_name"] for c in pool["candidates_in_order"]], fetcher,
                    ce.seed_repo_names(SEED_PAPERS_PATH) | ce.seed_repo_names(demo_set.CORPUS_EXPANSION_PATH) | excluded,
                    ce.seed_arxiv_ids(SEED_PAPERS_PATH) | ce.seed_arxiv_ids(demo_set.CORPUS_EXPANSION_PATH), out_dir, runner,
                    lambda entry, record_dir: k2_for_run(entry, record_dir, throttle), extend_pool, max_both=MAX_BOTH,
                    started_at=datetime.fromisoformat(args.started_at).timestamp() if args.started_at else None)
    summary = search.run()
    for name in ("evaluation.json", "papers.json"):
        path = out_dir / name
        path.write_text(demo_set.sanitize(path.read_text(encoding="utf-8")), encoding="utf-8")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
