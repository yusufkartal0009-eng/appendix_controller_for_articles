"""Verification tests for data/seed_papers.json dataset."""

import json
import re
from pathlib import Path
from src.config import ALLOWED_LICENSES, SEED_PAPERS_PATH
from src.models import PaperCreate


def test_seed_papers_json_completeness():
    """Verify seed_papers.json fulfills all Week 1 discovery infrastructure requirements."""
    assert SEED_PAPERS_PATH.exists(), f"Seed file missing at {SEED_PAPERS_PATH}"

    with open(SEED_PAPERS_PATH, "r", encoding="utf-8") as f:
        papers = json.load(f)

    # 1. At least 5 entries (the pilot minimum); each must also pass scripts/verify_corpus.py in CI
    assert len(papers) >= 5, f"Expected at least 5 seed papers, got {len(papers)}"

    seen_ids = set()
    for paper_dict in papers:
        # 2. Pydantic validation passes
        p = PaperCreate(**paper_dict)

        # 3. Unique paper_id
        assert p.paper_id not in seen_ids, f"Duplicate paper_id found: {p.paper_id}"
        seen_ids.add(p.paper_id)

        # 4. Publication year between 2020 and 2024
        assert 2020 <= p.year <= 2024, f"Paper {p.paper_id} year {p.year} is outside 2020-2024 range"

        # 4b. Repository pinned to a full commit SHA so the verified script cannot drift
        commit = paper_dict.get("repo_commit", "")
        assert re.fullmatch(r"[0-9a-f]{40}", commit), f"Paper {p.paper_id} needs a 40-character repo_commit"

        # 5. Open source license compliance
        assert any(
            allowed.lower() in p.license.lower()
            for allowed in ALLOWED_LICENSES
        ), f"Paper {p.paper_id} license '{p.license}' is not in allowed open licenses"

        # 6. Non-empty expected_claims dict with numeric values
        assert len(p.expected_claims) >= 1, f"Paper {p.paper_id} has empty expected_claims"
        for metric_name, val in p.expected_claims.items():
            assert isinstance(val, (int, float)), f"Metric {metric_name} in {p.paper_id} must be numeric"

        # 7. Valid target_script
        assert p.target_script.endswith(".py"), f"Paper {p.paper_id} target script must be a .py file"

        # 8. Source table or section references provided for reproducibility audit
        assert p.source_table_or_section is not None, f"Paper {p.paper_id} missing source references"
        assert len(p.source_table_or_section) >= 1, f"Paper {p.paper_id} has empty source references"
