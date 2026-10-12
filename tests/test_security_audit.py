"""The security audit document stays in step with its evidence (#46). No Docker is needed here."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import security_audit

ROWS = [
    {"id": "a", "area": "network", "title": "TCP", "expect": "fails", "observed": "Network is unreachable", "verdict": "PASS"},
    {"id": "b", "area": "privilege", "title": "Caps | dropped", "expect": "0", "observed": "CapBnd=1", "verdict": "FAIL"},
    {"id": "c", "area": "filesystem", "title": "Output", "expect": "allowed", "observed": "written", "verdict": "INFO"},
]
DATA = {"run_at": "2026-10-12T00:00+03:00", "image": "repro-radar-sandbox:latest", "docker": "29.8.2", "rows": ROWS}


def test_table_counts_and_escapes_pipes():
    table = security_audit.render_table(DATA)
    assert "**Totals: 1 PASS, 1 FAIL, 1 INFO.**" in table
    assert "Caps | dropped" not in table and "Caps / dropped" in table


def test_verdict_rules():
    assert security_audit.verdict(True, "fails") == "PASS"
    assert security_audit.verdict(False, "fails") == "FAIL"
    assert security_audit.verdict(True, "allowed") == "INFO"


def test_splice_replaces_only_the_marked_block():
    doc = f"before\n{security_audit.MARKER_START}\nold\n{security_audit.MARKER_END}\nafter\n"
    out = security_audit.splice(doc, "NEW")
    assert out == f"before\n{security_audit.MARKER_START}\nNEW\n{security_audit.MARKER_END}\nafter\n"


def test_committed_document_matches_committed_results():
    data = json.loads(security_audit.RESULTS_PATH.read_text(encoding="utf-8"))
    doc = security_audit.DOC_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert security_audit.splice(doc, security_audit.render_table(data)) == doc
    assert {r["verdict"] for r in data["rows"]} <= {"PASS", "FAIL", "INFO"}


def test_every_probe_id_is_unique():
    data = json.loads(security_audit.RESULTS_PATH.read_text(encoding="utf-8"))
    ids = [r["id"] for r in data["rows"]]
    assert len(ids) == len(set(ids))
