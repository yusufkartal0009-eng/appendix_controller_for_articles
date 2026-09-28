"""The pilot protocol (docs/PILOT_WEEK2.md) must cover exactly the papers in data/seed_papers.json.

Each seed entry needs one row in the per-paper command table with its repository, pinned commit, and target script,
and the command must run that target script inside the container.
"""

import json
import re

from src.config import PROJECT_ROOT, SEED_PAPERS_PATH

ENTRIES = json.loads(SEED_PAPERS_PATH.read_text(encoding="utf-8"))
PROTOCOL = (PROJECT_ROOT / "docs" / "PILOT_WEEK2.md").read_text(encoding="utf-8")


def _command_rows():
    return {
        m.group(1): line
        for line in PROTOCOL.splitlines()
        for m in [re.match(r"\| `(paper_\d{3})` [^|]+\|", line)]
        if m and "python /workspace/repo/" in line
    }


def test_protocol_has_one_command_row_per_seed_paper():
    rows = _command_rows()
    assert set(rows) == {e["paper_id"] for e in ENTRIES}


def test_protocol_rows_match_repository_commit_and_script():
    rows = _command_rows()
    for entry in ENTRIES:
        row = rows[entry["paper_id"]]
        repo = entry["repo_url"].split("github.com/")[1]
        assert f"`{repo}` @ `{entry['repo_commit'][:7]}`" in row, entry["paper_id"]
        assert f"`{entry['target_script']}`" in row, entry["paper_id"]
        assert f"python /workspace/repo/{entry['target_script']}" in row, entry["paper_id"]


def test_protocol_states_the_three_definitions():
    for term in ("**Install success**", "**Run success**", "**Pilot success rate**"):
        assert term in PROTOCOL
    assert "`dependency_install_status: INSTALLED`" in PROTOCOL
