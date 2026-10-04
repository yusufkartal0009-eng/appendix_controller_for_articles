"""Installed package versions recorded and compared with what the repository asks for (#161)."""

import json

from src.sandbox.installed_versions import read_installed, requested_vs_installed

INSTALLED = [{"name": "torch", "version": "2.7.1"}, {"name": "category-encoders", "version": "2.11.1"},
             {"name": "PyYAML", "version": "6.0.3"}, {"name": "numpy", "version": "2.4.6"}]


def test_loose_request_is_satisfied_but_drift_is_visible():
    """paper_008's case: torch>=1.4.0 was installed as 2.7.1."""
    rows = {r["name"]: r for r in requested_vs_installed(["torch>=1.4.0", "category_encoders", "pyyaml"], INSTALLED)}
    assert rows["torch"] == {"requirement": "torch>=1.4.0", "name": "torch", "requested": ">=1.4.0",
                             "installed": "2.7.1", "satisfied": True, "pinned": False}
    assert rows["category_encoders"]["installed"] == "2.11.1"  # names are compared in canonical form
    assert rows["category_encoders"]["requested"] == "any"
    assert rows["pyyaml"]["installed"] == "6.0.3"


def test_pinned_mismatch_and_missing_package():
    rows = {r["name"]: r for r in requested_vs_installed(["numpy==1.21.2", "catboost==0.24.4"], INSTALLED)}
    assert rows["numpy"]["satisfied"] is False and rows["numpy"]["pinned"] is True
    assert rows["catboost"]["installed"] is None and rows["catboost"]["satisfied"] is None


def test_comments_options_and_unparseable_lines():
    rows = requested_vs_installed(["# comment", "-r other.txt", "torch>=1.4.0  # needs GPU", "not a ==== req"], INSTALLED)
    assert [r["requirement"] for r in rows] == ["torch>=1.4.0", "not a ==== req"]
    assert rows[1]["note"] == "not a parseable requirement"


def test_read_installed(tmp_path):
    path = tmp_path / "installed_packages.json"
    assert read_installed(path) == []  # missing file (no install phase ran)
    path.write_text(json.dumps([{"name": "toolz", "version": "0.12.1", "location": "/workspace/deps"}]))
    assert read_installed(path) == [{"name": "toolz", "version": "0.12.1"}]
    path.write_text("not json")
    assert read_installed(path) == []
