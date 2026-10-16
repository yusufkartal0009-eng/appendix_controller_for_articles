"""Corpus expansion (#335): the rules of docs/CORPUS_EXPANSION.md, the order, and the selection loop. No network."""

import hashlib
import json

import pytest

from scripts import corpus_expansion as ce
from src.config import PROJECT_ROOT

FENCE = "`" * 3
LINK = "https://arxiv.org/abs/2101.00001"
README = f"# Tool\nPaper: {LINK}\n\n{FENCE}bash\npip install -r requirements.txt\npython train.py --data small\npython other.py\n{FENCE}\n"
GOOD_TEXT = "\n".join(f"Table {i}. Results" for i in (1, 2)) + "\n" + " ".join(f"0.{n:03d}" for n in range(30))
MIT = {"spdx_id": "MIT"}


def _readme(command, extra=""):
    return f"{FENCE}\n{command}\n{FENCE}\n{extra} {LINK}\n"


class Fetcher:
    """A repository per name; `repos[name]` overrides the defaults of a passing repository."""

    def __init__(self, repos=None, arxiv=None):
        self.repos = repos or {}
        self.paper = arxiv or {"title": "A Paper", "year": 2021, "text": GOOD_TEXT}

    def _get(self, name):
        base = {"meta": {"full_name": name, "language": "Python", "archived": False, "fork": False, "private": False,
                         "license": MIT, "size": 500, "default_branch": "main"},
                "readme": README, "sha": "a" * 40, "paths": ["train.py", "requirements.txt", "other.py"],
                "files": {"requirements.txt": "numpy\n"}}
        base.update(self.repos.get(name, {}))
        return base

    def search(self, query):
        return list(self.repos)

    def meta(self, full_name):
        return self._get(full_name)["meta"]

    def readme(self, full_name):
        return self._get(full_name)["readme"]

    def head_sha(self, full_name, branch):
        return self._get(full_name)["sha"]

    def tree(self, full_name, sha):
        return [{"path": p, "type": "blob"} for p in self._get(full_name)["paths"]]

    def file(self, full_name, sha, path):
        return self._get(full_name)["files"].get(path)

    def arxiv(self, arxiv_id):
        return self.paper


def _evaluate(arxiv=None, **override):
    return ce.evaluate_candidate("o/r", Fetcher({"o/r": override}, arxiv), set(), set())


def _meta(**kw):
    return dict({"full_name": "o/r", "language": "Python", "license": MIT}, **kw)


def test_the_order_is_the_sha256_of_the_lower_case_name_and_ignores_case_and_duplicates():
    ordered = ce.order_candidates(["B/two", "a/One", "b/TWO", "c/three"])
    keys = [hashlib.sha256(n.lower().encode()).hexdigest() for n in ordered]
    assert keys == sorted(keys) and len(ordered) == 3


def test_a_good_repository_passes_and_gets_the_first_readme_command():
    result = _evaluate()
    assert result["passed"] and result["failed_rule"] is None
    entry = result["entry"]
    assert entry["run_command"] == "python train.py --data small" and entry["target_script"] == "train.py"
    assert entry["repo_commit"] == "a" * 40 and entry["paper_url"] == LINK


@pytest.mark.parametrize("override,rule", [
    ({"meta": _meta(language="R")}, "R1"),
    ({"meta": _meta(archived=True)}, "R1"),
    ({"meta": _meta(fork=True)}, "R1"),
    ({"meta": _meta(license={"spdx_id": "GPL-3.0"})}, "R2"),
    ({"meta": _meta(license=None)}, "R2"),
    ({"readme": f"No commands here {LINK}"}, "R3"),
    ({"readme": _readme("python3 train.py")}, "R3"),  # `python3` is not `python `
    ({"readme": _readme("python missing.py")}, "R3"),  # the script does not exist
    ({"readme": _readme("python train.py", "Needs a GPU.")}, "R4"),
    ({"files": {"requirements.txt": "torch\ncudatoolkit\n"}}, "R4"),
    ({"readme": _readme("python train.py --device cuda")}, "R4"),
    ({"meta": _meta(size=100001)}, "R5"),
    ({"paths": ["train.py", ".gitattributes"], "files": {".gitattributes": "*.bin filter=lfs diff=lfs\n"}}, "R5"),
    ({"readme": _readme("python train.py", "The data is 2 GB.")}, "R5"),
    ({"readme": f"{FENCE}\npython train.py\n{FENCE}\nno paper link\n"}, "R6"),
])
def test_each_rule_rejects_and_names_itself(override, rule):
    result = _evaluate(**override)
    assert not result["passed"] and result["failed_rule"] == rule, result


@pytest.mark.parametrize("text", ["Table 1. only one\n" + "0.1 " * 30, "Table 1.\nTable 2.\n0.1 0.2", ""])
def test_r6_needs_two_table_captions_and_twenty_decimal_numbers(text):
    result = _evaluate(arxiv={"title": "A Paper", "year": 2021, "text": text})
    assert result["failed_rule"] == "R6"


def test_r6_fails_when_the_paper_is_not_available():
    assert ce.evaluate_candidate("o/r", Fetcher({"o/r": {}}, arxiv={"title": None}), set(), set())["failed_rule"] == "R6"


def test_the_first_failed_rule_is_the_one_recorded():
    assert _evaluate(meta=_meta(license={"spdx_id": "GPL-3.0"}, archived=True))["failed_rule"] == "R1"


def test_a_repository_of_the_corpus_or_a_chosen_one_is_rejected_by_r7():
    fetcher = Fetcher({"o/r": {}})
    assert ce.evaluate_candidate("o/r", fetcher, {"o/r"}, set())["failed_rule"] == "R7"
    assert ce.evaluate_candidate("o/r", fetcher, set(), {"o/r"})["failed_rule"] == "R7"


def test_stated_sizes_in_the_readme():
    assert ce.stated_sizes_mb("about 1.5 GB and 20 MB, 3mb") == [1536.0, 20.0, 3.0]


def test_selection_takes_the_first_passing_candidates_in_order_and_records_the_rest():
    names = ["a/1", "a/2", "a/3", "a/4"]
    fetcher = Fetcher({"a/2": {"meta": {"full_name": "a/2", "language": "R", "license": MIT}}})
    evaluations, chosen = ce.select(names, fetcher, set(), None, count=2)
    assert [c["full_name"] for c in chosen] == ["a/1", "a/3"]
    assert [(e["full_name"], e["failed_rule"]) for e in evaluations] == [("a/1", None), ("a/2", "R1"), ("a/3", None)]
    assert [e["paper_id"] for e in ce.papers_json(chosen)] == ["paper_101", "paper_102"]


class _Report:
    def __init__(self, ok):
        self.ok = ok
        self.checks = [type("Check", (), {"name": "repo", "ok": ok, "detail": "gone"})()]


def test_a_candidate_that_fails_verify_corpus_is_eliminated_and_the_next_takes_its_place(monkeypatch):
    monkeypatch.setattr(ce, "verify_entry", lambda entry, http: _Report(not entry["repo_url"].endswith("/2")))
    evaluations, chosen = ce.select(["a/1", "a/2", "a/3"], Fetcher(), set(), http=object(), count=2)
    assert [c["full_name"] for c in chosen] == ["a/1", "a/3"]
    eliminated = evaluations[1]
    assert eliminated["failed_rule"] == "verify_corpus" and "repo: gone" in eliminated["detail"]
    assert "entry" not in eliminated and [e["paper_id"] for e in ce.papers_json(chosen)] == ["paper_101", "paper_102"]


def test_the_pool_is_stored_with_the_queries_and_the_hash_order(tmp_path):
    pool = ce.command_pool(Fetcher({"b/two": {}, "a/one": {}}), tmp_path)
    assert [s["query"] for s in pool["searches"]] == ce.QUERIES
    stored = json.loads((tmp_path / "pool.json").read_text(encoding="utf-8"))
    assert [c["full_name"] for c in stored["candidates_in_order"]] == ce.order_candidates(["b/two", "a/one"])


def test_the_rules_in_the_code_are_the_rules_of_the_document():
    text = (PROJECT_ROOT / "docs" / "CORPUS_EXPANSION.md").read_text(encoding="utf-8")
    for query in ce.QUERIES:
        assert f"`{query}`" in text
    for rule in ce.RULES:
        assert f"| {rule} " in text
    assert "100,000 KB" in text and "500 MB" in text and f"first {ce.POOL_PER_QUERY} results" in text
