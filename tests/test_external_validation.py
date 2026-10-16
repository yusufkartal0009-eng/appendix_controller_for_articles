"""Selection of ReScience C articles by the rules of docs/EXTERNAL_VALIDATION.md (#383)."""

import hashlib
import json

import pytest

from scripts import external_validation as ev

ARTICLE_TEXT = ["Table 1: results\nrow 0.12 0.34 0.56", "Table 2: more\n" + " ".join(f"{i}.5" for i in range(25))]
YAML = """
title: A Replication of Something
language: Python 3
review:
  - url: https://github.com/ReScience/submission/issues/7
code:
  - url: https://github.com/someone/code
  - doi: 10.5281/zenodo.1
dates:
  - received: March 1, 2020
  - published: May 3, 2020
"""
README = "# Code\n\n```\npython run.py --n 3\n```\n"
PDF = b"%PDF fake"
NULLS = """title: T
language:
review:
  - url:
code:
  - url:
  - doi:
"""


class Fake:
    def __init__(self, **overrides):
        self.yaml = overrides.get("yaml", YAML)
        self.pdf = overrides.get("pdf", PDF)
        self.meta_ = overrides.get("meta", {"full_name": "someone/code", "language": "Python", "archived": False, "private": False,
                                            "size": 500, "default_branch": "main", "license": {"spdx_id": "MIT"}})
        self.readme = overrides.get("readme", README)
        self.paths = overrides.get("paths", ["run.py", "requirements.txt"])
        self.files = overrides.get("files", {"requirements.txt": "numpy\n"})
        self.resolved = []

    def article_dirs(self):
        return "c" * 40, ["10.5281_zenodo.1"]

    def article_yaml(self, commit, directory):
        return self.yaml

    def article_pdf(self, commit, directory):
        return self.pdf

    def meta(self, full_name):
        return self.meta_

    def resolve(self, full_name, ref):
        self.resolved.append(ref)
        return "a" * 40

    def readme_at(self, full_name, sha):
        return self.readme

    def tree(self, full_name, sha):
        return [{"path": p, "type": "blob"} for p in self.paths]

    def file(self, full_name, sha, path):
        return self.files.get(path)


@pytest.fixture(autouse=True)
def text(monkeypatch):
    monkeypatch.setattr(ev, "pdf_text", lambda pdf: ARTICLE_TEXT)


def run(fake, seed=frozenset(), taken=frozenset()):
    return ev.evaluate_article("10.5281_zenodo.1", "c" * 40, fake, set(seed), set(taken))


def test_an_article_that_meets_every_rule_passes_with_a_complete_entry():
    result = run(Fake())
    assert result["passed"] and result["failed_rule"] is None
    entry = result["entry"]
    assert entry["repo_url"] == "https://github.com/someone/code" and entry["repo_commit"] == "a" * 40
    assert entry["run_command"] == "python run.py --n 3" and entry["target_script"] == "run.py"
    assert entry["review_url"] == "https://github.com/ReScience/submission/issues/7" and entry["year"] == 2020
    assert entry["paper_url"] == "https://zenodo.org/records/1" and entry["venue"] == "ReScience C"
    assert entry["article_pdf_sha256"] == hashlib.sha256(PDF).hexdigest()
    assert entry["article_yaml_url"].endswith("/10.5281_zenodo.1/article.yaml")


@pytest.mark.parametrize(("fake", "rule"), [
    (Fake(yaml="not: [valid"), "E1"),
    (Fake(yaml=YAML.replace("https://github.com/ReScience/submission/issues/7", "https://example.org/review")), "E1"),
    (Fake(pdf=None), "E1"),
    (Fake(yaml=YAML.replace("Python 3", "R")), "E2"),
    (Fake(yaml=YAML.replace("url: https://github.com/someone/code", "url: https://example.org/code")), "E3"),
    (Fake(meta={"full_name": "someone/code", "language": "Julia", "archived": False}), "E3"),
    (Fake(meta={"full_name": "someone/code", "language": "Python", "archived": True}), "E3"),
    (Fake(readme="# no command here"), "E4"),
    (Fake(readme="```\npython missing.py\n```"), "E4"),
    (Fake(readme="```\npython setup.py install\n```", paths=["setup.py"]), "E4"),
    (Fake(readme=README + "Needs a GPU."), "E5"),
    (Fake(files={"requirements.txt": "torch\n# cuda 11\n"}), "E5"),
    (Fake(meta={"full_name": "someone/code", "language": "Python", "archived": False, "size": 200_000,
                "license": {"spdx_id": "MIT"}}), "E6"),
    (Fake(readme=README + "The data is 600 MB."), "E6"),
    (Fake(meta={"full_name": "someone/code", "language": "Python", "archived": False, "size": 5,
                "license": {"spdx_id": "NOASSERTION"}}), "E6"),
])
def test_the_first_failed_rule_is_reported(fake, rule):
    result = run(fake)
    assert not result["passed"] and result["failed_rule"] == rule


def test_an_article_with_too_little_in_its_tables_fails_e7(monkeypatch):
    monkeypatch.setattr(ev, "pdf_text", lambda pdf: ["Table 1: only one caption 0.5"])
    assert run(Fake())["failed_rule"] == "E7"
    # decimals outside the pages that hold a caption are not counted
    monkeypatch.setattr(ev, "pdf_text", lambda pdf: ["Table 1: a\nTable 2: b\n0.1", " ".join(f"{i}.5" for i in range(40))])
    assert run(Fake())["failed_rule"] == "E7"


def test_a_repository_in_a_corpus_or_already_selected_fails_e8():
    assert run(Fake(), seed={"someone/code"})["failed_rule"] == "E8"
    assert run(Fake(), taken={"someone/code"})["failed_rule"] == "E8"


def test_a_tree_or_tag_in_the_code_url_is_the_pinned_ref():
    fake = Fake(yaml=YAML.replace("url: https://github.com/someone/code", "url: https://github.com/someone/code/tree/v1.2"))
    assert run(fake)["passed"] and fake.resolved == ["v1.2"]
    tag = Fake(yaml=YAML.replace("url: https://github.com/someone/code", "url: https://github.com/someone/code/releases/tag/r3"))
    assert run(tag)["passed"] and tag.resolved == ["r3"]
    plain = Fake()
    run(plain)
    assert plain.resolved == ["main"]  # the head of the default branch


def test_the_fields_can_be_a_mapping_or_a_list_of_mappings_and_null_values_are_empty():
    mapping = Fake(yaml="""
title: T
language: [Python]
review: {url: https://github.com/ReScience/submission/issues/7}
code: {url: https://github.com/someone/code}
dates: {published: 2019-01-01}
""")
    assert run(mapping)["passed"]
    assert run(mapping)["entry"]["year"] == 2019
    nulls = Fake(yaml=NULLS)
    assert run(nulls)["failed_rule"] == "E1"
    archive = "  - url: https://example.org/archive"+chr(10)+"  - url: https://github.com/someone/code"
    first_archive = Fake(yaml=YAML.replace("  - url: https://github.com/someone/code", archive))
    assert run(first_archive)["passed"]


def test_the_order_is_the_hash_of_the_directory_name_and_ignores_case_and_duplicates():
    names = ["b", "a", "c", "a"]
    ordered = ev.order_directories(names)
    assert sorted(ordered) == ["a", "b", "c"]
    assert ordered == sorted(set(names), key=lambda n: hashlib.sha256(n.encode()).hexdigest())


class Http:
    def __init__(self, ok=True):
        self.ok = ok

    def get(self, url):
        if "/contents/" in url:
            return (200, json.dumps({"type": "file"})) if self.ok else (404, "")
        return 200, json.dumps({"full_name": "someone/code", "license": {"spdx_id": "MIT"}})


def test_select_takes_the_first_passing_articles_and_replaces_one_that_fails_verification(monkeypatch):
    class Many(Fake):
        pass

    fake = Many()
    monkeypatch.setattr(ev, "verify_selected", lambda entry, http, pdf=None: [("script", False, "not found")])
    evaluations, chosen = ev.select(["x"], "c" * 40, fake, set(), Http(False), count=1)
    assert chosen == [] and evaluations[0]["failed_rule"] == "verify" and "entry" not in evaluations[0]
    monkeypatch.setattr(ev, "verify_selected", lambda entry, http, pdf=None: [("script", True, "ok")])
    evaluations, chosen = ev.select(["x", "y"], "c" * 40, Fake(), set(), Http(), count=1)
    assert len(chosen) == 1 and len(evaluations) == 1  # stops at the count


def test_papers_json_numbers_the_entries_from_201_and_carries_the_reference():
    chosen = [run(Fake())]
    (entry,) = ev.papers_json(chosen)
    assert entry["paper_id"] == "paper_201" and entry["review_url"].startswith("https://github.com/")
    assert entry["expected_claims"] == {} and entry["run_command"] == "python run.py --n 3"


def test_verify_selected_checks_repository_script_and_the_title_in_the_pdf(monkeypatch):
    entry = dict(run(Fake())["entry"], paper_id="paper_201")
    monkeypatch.setattr(ev, "pdf_text", lambda pdf: ["A Replication of Something\nAuthors"])
    checks = ev.verify_selected(entry, Http(), PDF)
    assert {name: ok for name, ok, _ in checks} == {"repo": True, "license": True, "script": True, "article": True}
    monkeypatch.setattr(ev, "pdf_text", lambda pdf: ["Another title altogether"])
    assert {n: ok for n, ok, _ in ev.verify_selected(entry, Http(), PDF)}["article"] is False


def test_a_ref_in_the_code_url_that_does_not_exist_falls_back_to_the_default_branch_head():
    class NoTag(Fake):
        def resolve(self, full_name, ref):
            self.resolved.append(ref)
            return None if ref == "v9" else "b" * 40

    fake = NoTag(yaml=YAML.replace("url: https://github.com/someone/code", "url: https://github.com/someone/code/releases/tag/v9"))
    result = run(fake)
    assert result["passed"] and fake.resolved == ["v9", "main"] and result["entry"]["repo_commit"] == "b" * 40
    assert "v9 named in the code URL does not exist" in result["detail"]
    broken = NoTag(yaml=YAML)
    broken.resolve = lambda full_name, ref: None
    assert run(broken)["failed_rule"] == "E3"  # no ref in the URL and the default branch cannot be resolved
