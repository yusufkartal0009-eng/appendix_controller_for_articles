"""Integrity checks for every seed corpus entry against GitHub (network test).

For each entry in data/seed_papers.json: the repository is reachable, its GitHub license is allowed and
equals the declared license, and target_script exists at the pinned repo_commit.

Skipped unless REPRO_RADAR_NETWORK_TESTS=1 (CI enables it in the corpus job). Set GITHUB_TOKEN or
GH_TOKEN to avoid API rate limits.
"""

import json
import os

import pytest

from scripts.verify_corpus import UrlHttp, check_repo_and_license, check_script
from src.config import SEED_PAPERS_PATH

ENTRIES = json.loads(SEED_PAPERS_PATH.read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(
    os.environ.get("REPRO_RADAR_NETWORK_TESTS") != "1",
    reason="network test: set REPRO_RADAR_NETWORK_TESTS=1 to run",
)


@pytest.fixture(scope="module")
def http():
    return UrlHttp(token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))


@pytest.mark.parametrize("entry", ENTRIES, ids=[e["paper_id"] for e in ENTRIES])
def test_seed_entry_integrity(entry, http):
    repo, license_check, full_name = check_repo_and_license(entry, http)
    assert repo.ok, f"repository: {repo.detail}"
    assert license_check.ok, f"license: {license_check.detail}"
    script = check_script(entry, full_name, http)
    assert script.ok, f"script: {script.detail}"
