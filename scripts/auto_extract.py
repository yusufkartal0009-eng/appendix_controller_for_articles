#!/usr/bin/env python3
"""Three independent extraction passes per paper, and the claims they agree on (#381).

    python scripts/auto_extract.py run --name gold18 --papers paper_002,paper_003 [--workers 3]
    python scripts/auto_extract.py consensus --name gold18            # recompute the consensus from the stored passes
    python scripts/auto_extract.py evaluate --name gold18             # precision and recall against the gold set
    python scripts/auto_extract.py import --name gold18 --db-url sqlite:///x.db   # store the candidates as pending claims

`run` writes, for every paper and every pass, a blind packet in a folder outside the repository (the questions, the rules
of `scripts/make_blind_packet.py`, the page text of the pinned PDF, an answer template) and starts a **fresh** `claude -p`
process in that folder with only the tools Read, Write, Edit, Glob, and Grep, and permission mode `dontAsk` (anything not
allowed is refused, so the process cannot leave the folder or use the network). The processes share nothing. Each answer
is then checked by the same rules as `scripts/import_pass.py`: it must follow the claim schema, its page must exist, and
its quote must be found on that page and contain the printed value. An answer that fails a check is not a vote.

Consensus, per question: a claim becomes a **candidate** when at least two passes gave the same normalized value and each
of those claims passed the checks. Two passes that say "not found" make a consensus "not found". Anything else is left to a
person (`no_consensus`). A candidate is stored (`import`) as a pending claim with `verified_by = auto-consensus`; it is never
marked accepted, and a claim a person has reviewed is never touched. Nothing here decides what counts as correct: the
`evaluate` command only reports precision and recall against the owner's gold set, with no threshold.

Files: `data/auto_extract/<name>/raw/pass_<k>/<paper_id>.json` (the answers as written), `.../meta.json` (the command,
the duration, and the cost the CLI reported), and `.../consensus.json`.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from pydantic import ValidationError

from scripts import evaluate_gold
from scripts.make_blind_packet import RULES, SCHEMA
from src.claim_schema import ExtractedClaim
from src.config import DATA_DIR
from src.pdf_text import extract_pdf_text
from src.quote_guard import find_on_page

OUT_DIR = DATA_DIR / "auto_extract"
QUERIES_DIR = DATA_DIR / "claim_queries"
PDF_DIR = DATA_DIR / "pdfs"
GOLD_DIR = evaluate_gold.GOLD_DIR
TOOLS = "Read,Write,Edit,Glob,Grep"
DEFAULT_PASSES = 3
MIN_AGREEING_PASSES = 2
CALL_TIMEOUT_SECONDS = 1800
ATTEMPTS = 2  # a pass whose process failed or wrote no readable answers is started once more, in a new process
VALUE_DIGITS = 9

PROMPT = (
    "Read README.md, RULES.md, and SCHEMA.md in this folder. Answer every question in questions.json using only the page "
    "text in paper.txt, following RULES.md exactly, and write the answers into answers.json in the format of SCHEMA.md "
    "(start from the template that is already there; keep every paper_id and query_id). Work only inside this folder: do "
    "not read, search, or open any other folder, repository, website, or earlier conversation, and do not look up this "
    "paper anywhere else. When finished, check that answers.json is valid JSON, that every value_as_printed occurs inside "
    "its source_quote, and that every source_quote occurs on the page you cite. Then reply with the single word: done."
)
README = ("# Extraction packet\n\nThis folder is self-contained. Work only with the files in it: RULES.md, SCHEMA.md, "
          "questions.json, paper.txt (the page text of one paper), and answers.json (the template to fill).\n")

Runner = Callable[[Path, int], dict[str, Any]]


# --- packets --------------------------------------------------------------------------------------------------------

def build_packet(folder: Path, paper_id: str, queries: list[dict[str, str]], pdf_text: Any) -> None:
    """Write a blind packet for one paper: nothing from any earlier extraction, only the question and the page text."""
    folder.mkdir(parents=True, exist_ok=True)
    pages = "\n".join(f"=== PAGE {n} ===\n{page}" for n, page in enumerate(pdf_text.pages, start=1))
    (folder / "paper.txt").write_text(pages, encoding="utf-8")
    (folder / "questions.json").write_text(json.dumps({"paper_id": paper_id, "queries": queries}, indent=2) + "\n", encoding="utf-8")
    template = {paper_id: {q["query_id"]: {"status": None, "reason": "", "claim": None} for q in queries}}
    (folder / "answers.json").write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    # The rules name `papers/<paper_id>.txt`; in this packet the single paper is paper.txt.
    (folder / "RULES.md").write_text(RULES.replace("`papers/<paper_id>.txt`", "`paper.txt`"), encoding="utf-8")
    (folder / "SCHEMA.md").write_text(SCHEMA, encoding="utf-8")
    (folder / "README.md").write_text(README, encoding="utf-8")


def claude_command(claude: str) -> list[str]:
    return [claude, "-p", PROMPT, "--tools", TOOLS, "--allowedTools", TOOLS, "--permission-mode", "dontAsk",
            "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
            "--output-format", "json"]


def run_claude(folder: Path, timeout: int = CALL_TIMEOUT_SECONDS) -> dict[str, Any]:
    """One fresh `claude -p` process in the packet folder. Returns what the CLI reported (cost, duration) and its exit code."""
    claude = shutil.which("claude")
    if claude is None:
        raise FileNotFoundError("the `claude` command is not on the PATH")
    command = claude_command(claude)
    start = time.time()
    try:
        done = subprocess.run(command, cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "error": f"timeout after {timeout} s", "seconds": round(time.time() - start, 1)}
    info: dict[str, Any] = {"exit_code": done.returncode, "seconds": round(time.time() - start, 1)}
    try:
        report = json.loads(done.stdout)
        info.update(cost_usd=report.get("total_cost_usd"), models=sorted(report.get("modelUsage", {})),
                    terminal_reason=report.get("terminal_reason"), is_error=report.get("is_error"))
    except ValueError:
        info["stdout_tail"] = done.stdout[-300:]
    if done.returncode != 0:
        info["stderr_tail"] = done.stderr[-300:]
    return info


# --- checking an answer -----------------------------------------------------------------------------------------------

def check_answer(answer: Any, pdf_text: Any) -> tuple[str, str | None]:
    """('found' | 'not_found' | 'invalid', problem). A found claim must follow the schema and have its quote on its page."""
    if not isinstance(answer, dict):
        return "invalid", "answer is not an object"
    status = answer.get("status")
    if status == "not_found":
        if answer.get("claim") is not None or not answer.get("reason"):
            return "invalid", "not_found needs a reason and no claim"
        return "not_found", None
    if status != "found":
        return "invalid", f"status must be found or not_found, got {status!r}"
    try:
        claim = ExtractedClaim(**{k: v for k, v in (answer.get("claim") or {}).items() if k != "value_normalized"})
    except (ValidationError, TypeError, ValueError) as exc:
        return "invalid", f"invalid claim: {str(exc).splitlines()[0]}"
    if not 1 <= claim.page <= len(pdf_text.pages):
        return "invalid", f"page {claim.page} does not exist"
    if find_on_page(claim.source_quote, pdf_text.page(claim.page)) is None:
        return "invalid", f"source_quote not on page {claim.page}"
    answer["claim"]["value_normalized"] = claim.value_normalized
    return "found", None


def value_key(claim: dict[str, Any]) -> str:
    """Claims agree when their normalized values are the same number (to VALUE_DIGITS significant digits)."""
    return f"{float(claim['value_normalized']):.{VALUE_DIGITS}g}"


def consensus_for_question(votes: list[dict[str, Any]], minimum: int = MIN_AGREEING_PASSES) -> dict[str, Any]:
    """Outcome of one question from the checked answers of the passes (each vote: pass, state, claim, problem)."""
    valid_found = [v for v in votes if v["state"] == "found"]
    groups: dict[str, list[dict[str, Any]]] = {}
    for vote in valid_found:
        groups.setdefault(value_key(vote["claim"]), []).append(vote)
    ranked = sorted(groups.values(), key=len, reverse=True)
    summary = [{"pass": v["pass"], "state": v["state"], "problem": v.get("problem"),
                "value_as_printed": (v["claim"] or {}).get("value_as_printed") if v["claim"] else None} for v in votes]
    if ranked and len(ranked[0]) >= minimum and (len(ranked) == 1 or len(ranked[1]) < len(ranked[0])):
        best = max(ranked[0], key=lambda v: v["claim"].get("confidence", 0))
        return {"outcome": "candidate", "candidate": best["claim"], "agreeing_passes": sorted(v["pass"] for v in ranked[0]),
                "votes": summary}
    if sum(1 for v in votes if v["state"] == "not_found") >= minimum and not valid_found:
        return {"outcome": "consensus_not_found", "candidate": None, "agreeing_passes": sorted(
            v["pass"] for v in votes if v["state"] == "not_found"), "votes": summary}
    return {"outcome": "no_consensus", "candidate": None, "agreeing_passes": [], "votes": summary}


def build_consensus(raw: dict[int, dict[str, dict[str, Any]]], pdfs: dict[str, Any], queries: dict[str, list[str]],
                    minimum: int = MIN_AGREEING_PASSES) -> dict[str, Any]:
    """{paper_id: {query_id: outcome}} from raw[pass][paper_id] = {query_id: answer} (the answers are checked here)."""
    papers: dict[str, Any] = {}
    for paper_id, query_ids in queries.items():
        out: dict[str, Any] = {}
        for query_id in query_ids:
            votes = []
            for pass_no in sorted(raw):
                answer = raw[pass_no].get(paper_id, {}).get(query_id)
                state, problem = check_answer(answer, pdfs[paper_id]) if answer is not None else ("invalid", "no answer")
                votes.append({"pass": pass_no, "state": state, "problem": problem,
                              "claim": answer.get("claim") if state == "found" else None})
            out[query_id] = consensus_for_question(votes, minimum)
        papers[paper_id] = {"pdf_sha256": pdfs[paper_id].sha256, "questions": out}
    return papers


# --- running the passes -----------------------------------------------------------------------------------------------

def read_answers(folder: Path, paper_id: str) -> dict[str, Any] | None:
    try:
        data = json.loads((folder / "answers.json").read_text(encoding="utf-8"))
        answers = data[paper_id]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return answers if isinstance(answers, dict) else None


def unanswered(answers: dict[str, Any] | None) -> bool:
    return answers is None or all(isinstance(a, dict) and a.get("status") is None for a in answers.values())


def run_one(work: Path, pass_no: int, paper_id: str, queries: list[dict[str, str]], pdf_text: Any, runner: Runner,
            timeout: int) -> tuple[int, str, dict[str, Any] | None, dict[str, Any]]:
    folder = work / f"pass_{pass_no}" / paper_id
    attempts: list[dict[str, Any]] = []
    answers = None
    for attempt in range(1, ATTEMPTS + 1):
        shutil.rmtree(folder, ignore_errors=True)  # every attempt starts from a clean packet
        build_packet(folder, paper_id, queries, pdf_text)
        try:
            info = runner(folder, timeout)
        except Exception as exc:  # noqa: BLE001 - a process that cannot start is recorded, not raised
            info = {"exit_code": None, "error": f"{type(exc).__name__}: {exc}"}
        info["attempt"] = attempt
        attempts.append(info)
        answers = read_answers(folder, paper_id)
        if not unanswered(answers):
            break
    return pass_no, paper_id, answers, {"attempts": attempts}


def run_passes(name: str, paper_ids: list[str], passes: int = DEFAULT_PASSES, workers: int = 3, out_root: Path = OUT_DIR,
               queries_dir: Path = QUERIES_DIR, pdf_dir: Path = PDF_DIR, runner: Runner = run_claude,
               timeout: int = CALL_TIMEOUT_SECONDS, work_root: Path | None = None) -> dict[str, Any]:
    out = out_root / name
    work = Path(work_root) if work_root else Path(tempfile.mkdtemp(prefix=f"auto_extract_{name}_"))
    project = project_root.resolve()
    if work.resolve() == project or project in work.resolve().parents:
        raise ValueError("the packets must be written outside the repository, where earlier extractions can be seen")
    queries: dict[str, list[dict[str, str]]] = {}
    pdfs: dict[str, Any] = {}
    for paper_id in paper_ids:
        spec = json.loads((queries_dir / f"{paper_id}.json").read_text(encoding="utf-8"))
        queries[paper_id] = [{"query_id": q["query_id"], "question": q["question"]} for q in spec["queries"]]
        pdfs[paper_id] = extract_pdf_text(pdf_dir / f"{paper_id}.pdf")
    tasks = [(k, pid) for k in range(1, passes + 1) for pid in paper_ids]
    raw: dict[int, dict[str, dict[str, Any]]] = {k: {} for k in range(1, passes + 1)}
    meta: dict[str, Any] = {"started_at": datetime.now().astimezone().isoformat(timespec="seconds"), "passes": passes,
                            "papers": paper_ids, "tools": TOOLS, "prompt": PROMPT, "command": claude_command("claude"), "runs": {}}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(run_one, work, k, pid, queries[pid], pdfs[pid], runner, timeout) for k, pid in tasks]
        for future in futures:
            pass_no, paper_id, answers, info = future.result()
            meta["runs"][f"pass_{pass_no}/{paper_id}"] = info
            if answers is not None:
                raw[pass_no][paper_id] = answers
                target = out / "raw" / f"pass_{pass_no}"
                target.mkdir(parents=True, exist_ok=True)
                (target / f"{paper_id}.json").write_text(json.dumps(answers, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    meta["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    out.mkdir(parents=True, exist_ok=True)
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return write_consensus(name, out_root, queries_dir, pdf_dir, paper_ids)


def load_raw(out: Path) -> dict[int, dict[str, dict[str, Any]]]:
    raw: dict[int, dict[str, dict[str, Any]]] = {}
    for folder in sorted((out / "raw").glob("pass_*")):
        raw[int(folder.name.split("_")[1])] = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))}
    return raw


def write_consensus(name: str, out_root: Path = OUT_DIR, queries_dir: Path = QUERIES_DIR, pdf_dir: Path = PDF_DIR,
                    paper_ids: list[str] | None = None, minimum: int = MIN_AGREEING_PASSES) -> dict[str, Any]:
    out = out_root / name
    raw = load_raw(out)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8")) if (out / "meta.json").is_file() else {}
    paper_ids = paper_ids or meta.get("papers") or sorted({p for passes in raw.values() for p in passes})
    queries = {}
    pdfs = {}
    for paper_id in paper_ids:
        spec = json.loads((queries_dir / f"{paper_id}.json").read_text(encoding="utf-8"))
        queries[paper_id] = [q["query_id"] for q in spec["queries"]]
        pdfs[paper_id] = extract_pdf_text(pdf_dir / f"{paper_id}.pdf")
    result = {"name": name, "passes": sorted(raw), "minimum_agreeing_passes": minimum,
              "rule": ("candidate: at least two passes with the same normalized value, each with its quote found on its page; "
                       "consensus_not_found: at least two passes say not found and none found a valid claim; otherwise "
                       "no_consensus (left to a person). Candidates are not accepted claims."),
              "papers": build_consensus(raw, pdfs, queries, minimum)}
    (out / "consensus.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


# --- accuracy against the gold set ----------------------------------------------------------------------------------------

def main_value(text: str) -> str:
    """The number before a "±" part, without spaces: the value without its spread."""
    return evaluate_gold.normalize(re.split(r"±|\+/-", text, maxsplit=1)[0])


def _classify(found_value: str | None, gold: dict[str, Any], main_only: bool = False) -> str:
    """TP, FP, FP+FN, FN or TN. By default values are compared as printed ignoring spaces (as `evaluate_gold.py` does);
    with `main_only` a "±" spread is ignored on both sides."""
    key = main_value if main_only else evaluate_gold.normalize
    accepted = {key(v) for v in gold["accepted_values"]}
    if found_value is not None:
        if key(found_value) in accepted:
            return "TP"
        return "FP+FN" if accepted else "FP"
    return "FN" if accepted else "TN"


def evaluate(result: dict[str, Any], gold_sets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Precision and recall of the consensus, and of each single pass, against the gold questions (no threshold)."""
    rows = []
    for paper_id, gold in sorted(gold_sets.items()):
        paper = result["papers"].get(paper_id)
        if paper is None:
            continue
        for query_id, g in sorted(gold["questions"].items()):
            outcome = paper["questions"].get(query_id)
            if outcome is None or g.get("needs_decision"):
                continue
            cand = (outcome["candidate"] or {}).get("value_as_printed")
            row = {"question": f"{paper_id}:{query_id}", "gold": g["accepted_values"], "gold_not_in_paper": g["not_in_paper"],
                   "consensus": outcome["outcome"], "candidate": cand, "agreeing_passes": outcome["agreeing_passes"],
                   "per_pass": {v["pass"]: v["value_as_printed"] or v["state"] for v in outcome["votes"]}}
            if outcome["outcome"] == "no_consensus":
                row["result"] = "left_to_person"
            else:
                row["result"] = _classify(cand, g)
            row["result_main_value_only"] = "left_to_person" if outcome["outcome"] == "no_consensus" else _classify(cand, g, True)
            row["single_pass_results"] = {
                v["pass"]: _classify(v["value_as_printed"], g) if v["state"] == "found" else
                ("FN" if g["accepted_values"] else "TN") for v in outcome["votes"]}
            rows.append(row)

    def rates(results: list[str]) -> dict[str, Any]:
        tp = sum("TP" in r for r in results)
        fp = sum("FP" in r for r in results)
        fn = sum("FN" in r for r in results)
        return {"tp": tp, "fp": fp, "fn": fn, "tn": sum(r == "TN" for r in results),
                "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                "recall": round(tp / (tp + fn), 3) if tp + fn else None}

    decided = [r["result"] for r in rows if r["result"] != "left_to_person"]
    left = [r for r in rows if r["result"] == "left_to_person"]
    with_value = [r for r in rows if r["gold"]]
    tp = sum(r["result"] == "TP" for r in rows)
    pass_numbers = sorted({p for r in rows for p in r["single_pass_results"]})
    summary = {
        "name": result["name"], "gold_questions": len(rows), "gold_questions_with_a_value": len(with_value),
        "gold_questions_not_in_paper": len(rows) - len(with_value),
        "decided_by_consensus": len(decided), "left_to_a_person": len(left),
        "left_to_a_person_questions": [r["question"] for r in left],
        "consensus_decisions": rates(decided),
        # the same, ignoring a "±" spread on both sides (a pass that printed 0.433 where the gold has 0.433±1.6e-3)
        "consensus_decisions_main_value_only": rates([r["result_main_value_only"] for r in rows if r["result"] != "left_to_person"]),
        # recall over every gold question that has a value, counting a question left to a person as missed
        "consensus_recall_over_all_gold_values": round(tp / len(with_value), 3) if with_value else None,
        "single_passes": {f"pass_{p}": rates([r["single_pass_results"][p] for r in rows if p in r["single_pass_results"]])
                          for p in pass_numbers},
        "rows": rows,
        "note": "Reported without a threshold. Candidates are pending claims; nothing here accepts a claim.",
    }
    return summary


# --- importing the candidates ----------------------------------------------------------------------------------------------

def import_candidates(result: dict[str, Any], session: Any, source_file: str) -> dict[str, int]:
    """Store the candidates as pending claims with verified_by = auto-consensus. A reviewed claim is never touched."""
    from src.claim_store import save_extracted_claim
    from src.models import ExtractedClaimORM

    counts: dict[str, int] = {}
    for paper_id, paper in result["papers"].items():
        for query_id, outcome in paper["questions"].items():
            if outcome["outcome"] != "candidate":
                counts[outcome["outcome"]] = counts.get(outcome["outcome"], 0) + 1
                continue
            existing = session.get(ExtractedClaimORM, f"{paper_id}:{query_id}")
            if existing is not None and existing.review_status != "pending":
                counts["skipped (already reviewed by a person)"] = counts.get("skipped (already reviewed by a person)", 0) + 1
                continue
            claim = outcome["candidate"]
            _, what = save_extracted_claim(session, {
                "paper_id": paper_id, "query_id": query_id, "metric_name": claim["metric_name"], "dataset": claim.get("dataset"),
                "model_variant": claim.get("model_variant"), "split": claim.get("split"), "value": float(claim["value_normalized"]),
                "value_as_printed": claim["value_as_printed"], "higher_is_better": claim.get("higher_is_better"),
                "page": int(claim["page"]), "table_or_section": claim.get("table_or_figure"), "quote": claim["source_quote"],
                "source_file": source_file, "pdf_sha256": paper["pdf_sha256"],
                "extractor_version": f"auto-consensus of passes {outcome['agreeing_passes']} (scripts/auto_extract.py)",
                "verified_by": "auto-consensus"})
            counts[what] = counts.get(what, 0) + 1
    session.commit()
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent extraction passes and their consensus candidates (#381).")
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="start the passes and write the consensus")
    p_run.add_argument("--name", required=True)
    p_run.add_argument("--papers", required=True, help="comma-separated paper ids with a file in the queries directory")
    p_run.add_argument("--passes", type=int, default=DEFAULT_PASSES)
    p_run.add_argument("--workers", type=int, default=3)
    p_run.add_argument("--timeout", type=int, default=CALL_TIMEOUT_SECONDS)
    p_run.add_argument("--queries-dir", default=str(QUERIES_DIR))
    p_run.add_argument("--pdf-dir", default=str(PDF_DIR))
    p_cons = sub.add_parser("consensus", help="recompute the consensus from the stored passes")
    p_cons.add_argument("--name", required=True)
    p_cons.add_argument("--queries-dir", default=str(QUERIES_DIR))
    p_cons.add_argument("--pdf-dir", default=str(PDF_DIR))
    p_eval = sub.add_parser("evaluate", help="precision and recall against the gold set")
    p_eval.add_argument("--name", required=True)
    p_eval.add_argument("--gold", default=str(GOLD_DIR))
    p_imp = sub.add_parser("import", help="store the candidates as pending claims (verified_by auto-consensus)")
    p_imp.add_argument("--name", required=True)
    p_imp.add_argument("--db-url", required=True, help="a database that has the papers (never needed for the gold evaluation)")
    args = parser.parse_args(argv)

    if args.command == "run":
        result = run_passes(args.name, args.papers.split(","), args.passes, args.workers, queries_dir=Path(args.queries_dir),
                            pdf_dir=Path(args.pdf_dir), timeout=args.timeout)
    elif args.command == "consensus":
        result = write_consensus(args.name, queries_dir=Path(args.queries_dir), pdf_dir=Path(args.pdf_dir))
    elif args.command == "evaluate":
        result = json.loads((OUT_DIR / args.name / "consensus.json").read_text(encoding="utf-8"))
        summary = evaluate(result, evaluate_gold.load_gold(Path(args.gold)))
        (OUT_DIR / args.name / "evaluation.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2, ensure_ascii=False))
        return 0
    else:
        from src.database import get_engine, get_session

        session = get_session(get_engine(args.db_url))
        result = json.loads((OUT_DIR / args.name / "consensus.json").read_text(encoding="utf-8"))
        print(json.dumps(import_candidates(result, session, f"data/auto_extract/{args.name}/consensus.json"), indent=2))
        return 0
    counts: dict[str, int] = {}
    for paper in result["papers"].values():
        for outcome in paper["questions"].values():
            counts[outcome["outcome"]] = counts.get(outcome["outcome"], 0) + 1
    print(json.dumps({"name": args.name, "outcomes": counts}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
