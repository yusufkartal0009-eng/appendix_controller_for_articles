"""The candidates corpus is read from GitHub and the papers' pages, and kept apart from the seed corpus (#433)."""

import base64
import json
import re

import pytest

from scripts import candidates_build
from src.config import ALLOWED_LICENSES, DATA_DIR

CANDIDATES = DATA_DIR / "candidates"
RUNS = CANDIDATES / "runs" / "evaluation.json"
SHA = "a" * 40


class FakeHttp:
    def __init__(self, repo_license="MIT", readme="see arXiv 1803.01422"):
        self.repo_license, self.readme, self.urls = repo_license, readme, []

    def get(self, url):
        self.urls.append(url)
        if "/readme" in url:
            return 200, json.dumps({"content": base64.b64encode(self.readme.encode()).decode()})
        if "/commits/" in url:
            return 200, json.dumps({"sha": SHA, "commit": {"committer": {"date": "2026-10-01T00:00:00Z"}}})
        if "api.github.com/repos/" in url:
            return 200, json.dumps({"full_name": "o/r", "default_branch": "main", "license": {"spdx_id": self.repo_license},
                                    "size": 12, "archived": False, "fork": False, "language": "Python", "pushed_at": "x"})
        if "arxiv.org/abs/" in url:
            return 200, '<meta name="citation_title" content="A Title"><meta name="citation_date" content="2018/03/04">'
        return 404, ""


ITEM = {"repo": "o/r", "paper": "1803.01422", "script": "a.py", "command": "python a.py", "status": "ready", "source": "scan",
        "notes": "n"}


def test_an_entry_has_the_seed_format_the_head_commit_and_no_claims():
    entry, record = candidates_build.build_entry(1, ITEM, FakeHttp(), sleep=lambda s: None)
    assert entry["paper_id"] == "cand_001" and entry["repo_commit"] == SHA and entry["expected_claims"] == {}
    assert entry["title"] == "A Title" and entry["year"] == 2018 and entry["license"] == "MIT"
    assert record["readme_names_the_paper"] is True and record["commit_supplied_by_list"] is False


def test_a_commit_supplied_by_the_list_is_kept_and_no_head_is_read():
    http = FakeHttp()
    entry, record = candidates_build.build_entry(1, {**ITEM, "supplied_commit": "b" * 40}, http, sleep=lambda s: None)
    assert entry["repo_commit"] == "b" * 40 and record["commit_supplied_by_list"] is True
    assert not any("/commits/" in url for url in http.urls)


def test_a_readme_that_does_not_name_the_paper_is_recorded_as_such():
    _, record = candidates_build.build_entry(1, ITEM, FakeHttp(readme="nothing here"), sleep=lambda s: None)
    assert record["readme_names_the_paper"] is False


def test_a_missing_repository_is_an_error_in_the_record_not_a_crash():
    class Missing(FakeHttp):
        def get(self, url):
            return (404, "") if "api.github.com" in url else super().get(url)

    entry, record = candidates_build.build_entry(1, ITEM, Missing(), sleep=lambda s: None)
    assert record["repo_error"] and entry["repo_commit"] == ""


def test_the_committed_candidates_are_well_formed_and_not_in_the_seed_corpus():
    entries = json.loads((CANDIDATES / "papers.json").read_text(encoding="utf-8"))
    seed = json.loads((DATA_DIR / "seed_papers.json").read_text(encoding="utf-8"))
    seed_repos = {item["repo_url"].lower() for item in seed}
    assert len(entries) == 29 and len({e["paper_id"] for e in entries}) == 29
    for entry in entries:
        assert re.fullmatch(r"[0-9a-f]{40}", entry["repo_commit"]), entry["paper_id"]
        assert entry["license"] in ALLOWED_LICENSES and entry["expected_claims"] == {}
        assert entry["status"] in {"ready", "fixable", "risky", "two_step", "excluded"}
        assert entry["repo_url"].lower() not in seed_repos


def test_every_committed_candidate_passed_the_four_checks():
    results = json.loads((CANDIDATES / "verify_corpus.json").read_text(encoding="utf-8"))
    assert len(results) == 29 and all(item["ok"] for item in results)


def test_the_document_is_generated_from_the_data_files():
    evaluation = json.loads((CANDIDATES / "evaluation.json").read_text(encoding="utf-8"))
    text = candidates_build.render_doc(
        json.loads((CANDIDATES / "papers.json").read_text(encoding="utf-8")), evaluation["candidates"],
        json.loads((CANDIDATES / "verify_corpus.json").read_text(encoding="utf-8")), evaluation["excluded_without_entry"],
        evaluation["retrieved_at"][:10],
        json.loads(RUNS.read_text(encoding="utf-8")) if RUNS.is_file() else None,
        candidates_build.render_round2_results(json.loads(RUNS.read_text(encoding="utf-8"))))
    committed = (DATA_DIR.parent / "docs" / "CANDIDATES.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert text == committed


def test_the_wilson_interval_matches_known_values_and_refuses_impossible_input():
    low, high = candidates_build.wilson_interval(5, 10)
    assert (round(low, 4), round(high, 4)) == (0.2366, 0.7634)
    low, high = candidates_build.wilson_interval(0, 14)
    assert low == 0.0 and round(high, 4) == 0.2153
    low, high = candidates_build.wilson_interval(1, 6)
    assert (round(low, 4), round(high, 4)) == (0.0301, 0.5635)
    for passed, total in ((1, 0), (-1, 5), (6, 5)):
        with pytest.raises(ValueError):
            candidates_build.wilson_interval(passed, total)


RESULT = {"repository": "https://github.com/o/r", "command": "python a.py", "working_dir": "", "install_status": "INSTALLED",
          "run_status": "COMPLETED", "exit_code": 0, "duration_seconds": 3.5, "metric_lines": ["acc: 0.91"], "log_line": ""}


def _runs(*outcomes):
    results = []
    for index, outcome in enumerate(outcomes, start=1):
        passed = outcome == "passed"
        results.append({**RESULT, "paper_id": f"cand_{index:03d}", "passed": passed, "category": None if passed else outcome})
    return {"written_at": "2026-10-24T20:00:00+00:00", "limits": {"memory": "50%", "cpus": 4.0, "run_timeout_seconds": 1800},
            "results": results}


def test_the_run_results_count_pass_and_fail_from_the_records_and_say_it_is_not_a_success_rate():
    text = "\n".join(candidates_build.render_run_results(_runs("passed", "run", "install", "command_incomplete")))
    assert "Selected candidates (status ready, fixable, two_step): **4**" in text
    assert "Not run because the listed command is incomplete (`command_incomplete`): 1" in text
    assert "Run once in the sandbox: 3" in text and "Passed" in text and "**1**" in text
    assert "1 of 4 selected candidates, Wilson 95 % interval 4.6 % to 69.9 %" in text
    assert "1 of 3, Wilson 95 % interval 6.1 % to 79.2 %" in text
    assert "not a representative sample" in text and "not a success rate" in text
    assert "`acc: 0.91`" in text and "| run | 1 | cand_002 |" in text


def test_the_document_without_a_pass_says_none_and_without_results_it_says_nothing_was_run():
    assert "None." in "\n".join(candidates_build.render_run_results(_runs("run", "run")))
    evaluation = json.loads((CANDIDATES / "evaluation.json").read_text(encoding="utf-8"))
    args = (json.loads((CANDIDATES / "papers.json").read_text(encoding="utf-8")), evaluation["candidates"],
            json.loads((CANDIDATES / "verify_corpus.json").read_text(encoding="utf-8")), evaluation["excluded_without_entry"], "2026-10-22")
    assert "None of them has been run" in candidates_build.render_doc(*args)
    with_runs = candidates_build.render_doc(*args, run_results=_runs("passed") | {"results": _runs("passed")["results"] * 14})
    assert "# Candidate papers\n" in with_runs and "## Run results" in with_runs and "None of them has been run" not in with_runs


def test_the_cause_of_a_failure_comes_from_the_classifier_rules_on_the_deciding_line():
    base = {"passed": False, "log_line": ""}
    assert candidates_build.failure_cause({**base, "category": "command_incomplete"}) == "COMMAND_INCOMPLETE"
    assert candidates_build.failure_cause({**base, "category": "install"}).startswith("MISSING_DEPENDENCY")
    cases = {"ModuleNotFoundError: No module named 'x'": "MISSING_DEPENDENCY",
             "OSError: [Errno 30] Read-only file system: 'out'": "WRITE_TO_READ_ONLY_REPOSITORY",
             "FileNotFoundError: [Errno 2] No such file or directory: 'a/b.png'": "MISSING_FILE",
             "FileNotFoundError: [Errno 2] No such file or directory: '/x/data/y.npy'": "DATA_NOT_ACCESSIBLE"}
    for line, cause in cases.items():
        assert candidates_build.failure_cause({**base, "category": "run", "log_line": line}) == cause
    text = "\n".join(candidates_build.render_run_results(_runs("run", "install")))
    assert "### Cause of the failures by the rules of the failure classifier" in text


# Bug hunt suspicion 6 (#498): the README was read at the head of the default branch, also when the list supplied a commit
def test_the_readme_is_read_at_the_pinned_commit_when_the_list_supplies_one():
    http = FakeHttp()
    candidates_build.build_entry(1, {**ITEM, "supplied_commit": "b" * 40}, http, sleep=lambda s: None)
    (url,) = [u for u in http.urls if "/readme" in u]
    assert url.endswith("/readme?ref=" + "b" * 40)


def test_the_readme_is_read_at_the_head_commit_that_was_recorded_when_none_is_supplied():
    http = FakeHttp()
    entry, _ = candidates_build.build_entry(1, ITEM, http, sleep=lambda s: None)
    (url,) = [u for u in http.urls if "/readme" in u]
    assert entry["repo_commit"] == SHA and url.endswith("/readme?ref=" + SHA)
