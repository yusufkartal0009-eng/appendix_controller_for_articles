"""Unit tests for the corpus verifier, using an in-memory HTTP client (no network)."""

import json

import pytest

from scripts import verify_corpus as vc

SHA = "a" * 40
GOOD = {
    "paper_id": "paper_x",
    "title": "Revisiting Deep Learning Models for Tabular Data",
    "paper_url": "https://arxiv.org/abs/2106.11959",
    "repo_url": "https://github.com/org/repo",
    "license": "MIT",
    "target_script": "bin/run.py",
    "repo_commit": SHA,
}


class FakeHttp:
    """Maps URL -> (status, body) or an Exception to raise."""

    def __init__(self, routes):
        self.routes = routes
        self.requested = []

    def get(self, url):
        self.requested.append(url)
        if url not in self.routes:
            return 404, ""
        route = self.routes[url]
        if isinstance(route, Exception):
            raise route
        return route


def abs_page(title):
    return 200, f'<html><head><meta name="citation_title" content="{title}" /></head></html>'


def repo_json(full_name="org/repo", spdx="MIT"):
    return 200, json.dumps({"full_name": full_name, "license": {"spdx_id": spdx} if spdx else None})


def contents_json():
    return 200, json.dumps({"type": "file", "path": "bin/run.py"})


def routes_for(entry=GOOD, title=None, repo=None, full_name="org/repo", contents=None):
    return {
        "https://arxiv.org/abs/2106.11959": abs_page(title or entry["title"]),
        "https://api.github.com/repos/org/repo": repo or repo_json(full_name),
        f"https://api.github.com/repos/{full_name}/contents/bin/run.py?ref={SHA}": contents or contents_json(),
    }


def failed(report):
    return {c.name for c in report.checks if not c.ok}


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://arxiv.org/abs/2106.11959", "2106.11959"),
        ("https://arxiv.org/abs/2106.11959v3", "2106.11959"),
        ("https://arxiv.org/pdf/2106.11959.pdf", "2106.11959"),
        ("https://openreview.net/forum?id=abc", None),
    ],
)
def test_parse_arxiv_id(url, expected):
    assert vc.parse_arxiv_id(url) == expected


def test_parse_github_repo():
    assert vc.parse_github_repo("https://github.com/Org/Repo.git/") == ("Org", "Repo")
    assert vc.parse_github_repo("https://gitlab.com/org/repo") is None


def test_titles_match_ignores_case_and_punctuation_but_not_content():
    assert vc.titles_match("TabR: Tabular Data Modeling Meets Nearest Neighbors", "tabr tabular data modeling meets nearest-neighbors")
    assert not vc.titles_match(
        "FastSK: Fast Sequence Kernel SVM", "Spline Moment Models for the one-dimensional Boltzmann-BGK equation"
    )


def test_valid_entry_passes_all_checks():
    report = vc.verify_entry(GOOD, FakeHttp(routes_for()))
    assert report.ok, [(c.name, c.detail) for c in report.checks]
    assert [c.name for c in report.checks] == ["paper", "repo", "license", "script"]


def test_paper_title_mismatch_fails():
    http = FakeHttp(routes_for(title="Spline Moment Models for the one-dimensional Boltzmann-BGK equation"))
    report = vc.verify_entry(GOOD, http)
    assert failed(report) == {"paper"}
    assert "Boltzmann" in next(c.detail for c in report.checks if c.name == "paper")


def test_missing_repository_fails_repo_and_dependent_checks():
    routes = routes_for()
    del routes["https://api.github.com/repos/org/repo"]
    report = vc.verify_entry(GOOD, FakeHttp(routes))
    assert {"repo", "license", "script"} <= failed(report)


def test_renamed_repository_passes_and_checks_script_in_new_location():
    http = FakeHttp(routes_for(full_name="neworg/newrepo"))
    report = vc.verify_entry(GOOD, http)
    assert report.ok
    assert "neworg/newrepo" in next(c.detail for c in report.checks if c.name == "repo")
    assert f"https://api.github.com/repos/neworg/newrepo/contents/bin/run.py?ref={SHA}" in http.requested


def test_license_not_matching_declared_license_fails():
    report = vc.verify_entry(GOOD, FakeHttp(routes_for(repo=repo_json(spdx="Apache-2.0"))))
    assert failed(report) == {"license"}


def test_disallowed_or_missing_license_fails():
    entry = dict(GOOD, license="GPL-3.0")
    report = vc.verify_entry(entry, FakeHttp(routes_for(repo=repo_json(spdx="GPL-3.0"))))
    assert "license" in failed(report)
    report = vc.verify_entry(GOOD, FakeHttp(routes_for(repo=repo_json(spdx=None))))
    assert "license" in failed(report)


def test_missing_pinned_commit_fails_script_check():
    entry = {k: v for k, v in GOOD.items() if k != "repo_commit"}
    report = vc.verify_entry(entry, FakeHttp(routes_for()))
    assert failed(report) == {"script"}
    assert "repo_commit" in next(c.detail for c in report.checks if c.name == "script")


def test_script_absent_at_pinned_commit_fails():
    report = vc.verify_entry(GOOD, FakeHttp(routes_for(contents=(404, ""))))
    assert failed(report) == {"script"}


def test_network_error_is_a_failure_not_a_pass():
    routes = routes_for()
    routes["https://arxiv.org/abs/2106.11959"] = OSError("connection reset")
    report = vc.verify_entry(GOOD, FakeHttp(routes))
    assert "paper" in failed(report)
    assert "network error" in next(c.detail for c in report.checks if c.name == "paper")


def test_main_exit_code_reflects_any_failure(tmp_path, capsys):
    corpus = tmp_path / "corpus.json"
    bad = dict(GOOD, paper_id="paper_bad", license="Apache-2.0")
    corpus.write_text(json.dumps([GOOD]), encoding="utf-8")
    assert vc.main([str(corpus)], http=FakeHttp(routes_for())) == 0

    corpus.write_text(json.dumps([GOOD, bad]), encoding="utf-8")
    assert vc.main([str(corpus)], http=FakeHttp(routes_for())) == 1
    out = capsys.readouterr().out
    assert "paper_bad" in out and "FAIL" in out
