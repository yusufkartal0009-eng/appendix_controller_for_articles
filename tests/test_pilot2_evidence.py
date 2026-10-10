"""The committed Pilot 2 evidence is consistent with its stored records, and its report matches them (#171)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import categorize_pilot_failures as cat
import pilot2_attempts
import pilot_compare
import pilot_measurements as pm
import report_numbers as rn

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "pilot2_runs"
PROTOCOL = ROOT / "docs" / "PILOT_2.md"
PAPERS = [e["paper_id"] for e in json.loads((ROOT / "data" / "seed_papers.json").read_text(encoding="utf-8"))]


def test_every_paper_has_a_record_and_the_protocol_name():
    for paper_id in PAPERS:
        record = json.loads((RUNS / paper_id / "pilot_record.json").read_text(encoding="utf-8"))
        assert record["protocol"] == "docs/PILOT_2.md" and record["paper_id"] == paper_id
        assert record["stage"]["matches_pinned_commit"] is True


def test_committed_measurements_categories_and_comparison_match_the_stored_runs():
    measured = pm.measure(RUNS)
    assert json.loads((RUNS / "measurements.json").read_text(encoding="utf-8")) == measured
    assert (RUNS / "measurements.md").read_text(encoding="utf-8") == pm.to_markdown(measured)
    assert json.loads((RUNS / "failure_categories.json").read_text(encoding="utf-8")) == cat.categorize(RUNS)
    comparison = pilot_compare.compare()
    assert json.loads((RUNS / "comparison.json").read_text(encoding="utf-8")) == comparison
    assert (RUNS / "comparison.md").read_text(encoding="utf-8") == pilot_compare.to_markdown(comparison)


def test_the_attempts_index_matches_the_stored_attempts_and_every_attempt_has_a_reason():
    attempts = RUNS / "first_attempts"
    rows = pilot2_attempts.index(attempts)
    assert rows and all(r["superseded_because"] for r in rows)
    assert json.loads((attempts / "index.json").read_text(encoding="utf-8")) == rows
    assert (attempts / "README.md").read_text(encoding="utf-8") == pilot2_attempts.to_markdown(rows)


def test_the_pilot_2_report_numbers_are_the_generated_blocks():
    text = PROTOCOL.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert rn.mismatches(text) == []
    for name in ("pilot2summary", "pilot2measurements", "pilot2", "pilot2failures"):
        assert f"<!-- numbers:{name}:start -->" in text


def test_an_earlier_attempt_is_never_a_counted_result():
    counted = {p: json.loads((RUNS / p / "pilot_record.json").read_text(encoding="utf-8")) for p in PAPERS}
    for row in pilot2_attempts.index(RUNS / "first_attempts"):
        # A kept attempt is its own directory; the counted record of the paper is a different file
        assert counted[row["paper_id"]]["started_at"] != json.loads(
            (RUNS / "first_attempts" / row["attempt"] / "pilot_record.json").read_text(encoding="utf-8"))["started_at"]


def test_the_stored_comparison_does_not_depend_on_the_machine_that_generated_it():
    """#246: its source paths are repository-relative, and the evidence tests pass in any checkout."""
    comparison = json.loads((RUNS / "comparison.json").read_text(encoding="utf-8"))
    paths = [p for group in comparison["sources"].values() for p in group]
    assert paths and all(p.startswith("data/") and ":" not in p for p in paths)
