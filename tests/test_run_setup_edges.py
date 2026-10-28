"""Edge cases of the run-setup validation: every refusal, and the shapes that are accepted (#557)."""

from pathlib import Path

import pytest

from src.sandbox.run_setup import data_dir, openml_ids, run_setup_of


def entry(**setup_overrides):
    setup = {"decision": "fix", "reason": "because of the logs"}
    setup.update(setup_overrides)
    return {"paper_id": "paper_x", "run_setup": setup}


def test_a_minimal_setup_is_accepted_and_returned_as_it_is():
    assert run_setup_of(entry())["decision"] == "fix"
    assert run_setup_of(entry(decision="report_as_is"))["decision"] == "report_as_is"


@pytest.mark.parametrize("bad", [{}, {"paper_id": "paper_x"}, {"paper_id": "paper_x", "run_setup": None}, {"paper_id": "paper_x", "run_setup": []},
                                 {"paper_id": "paper_x", "run_setup": "fix"}])
def test_a_missing_or_non_object_run_setup_is_refused(bad):
    with pytest.raises(ValueError, match="no run_setup"):
        run_setup_of(bad)


@pytest.mark.parametrize("decision", [None, "", "skip", "FIX", 1])
def test_an_unknown_decision_is_refused(decision):
    with pytest.raises(ValueError, match="decision must be"):
        run_setup_of(entry(decision=decision))


@pytest.mark.parametrize("reason", [None, ""])
def test_a_decision_without_a_reason_is_refused(reason):
    with pytest.raises(ValueError, match="needs a reason"):
        run_setup_of(entry(reason=reason))


@pytest.mark.parametrize("item,message", [
    ({"kind": "ftp", "name": "d", "target": "t"}, "data kind"),
    ({"name": "d", "target": "t"}, "data kind"),
    ({"kind": "url", "target": "t", "url": "u", "unpack": "tar"}, "name and a target"),
    ({"kind": "url", "name": "d", "url": "u", "unpack": "tar"}, "name and a target"),
    ({"kind": "url", "name": "d", "target": "t", "unpack": "tar"}, "needs a url"),
    ({"kind": "url", "name": "d", "target": "t", "url": "u", "unpack": "rar"}, "unpack"),
    ({"kind": "url", "name": "d", "target": "t", "url": "u"}, "unpack"),
    ({"kind": "openml", "name": "d", "target": "t"}, "integer dataset_ids"),
    ({"kind": "openml", "name": "d", "target": "t", "dataset_ids": []}, "integer dataset_ids"),
    ({"kind": "openml", "name": "d", "target": "t", "dataset_ids": ["61"]}, "integer dataset_ids"),
    ({"kind": "openml", "name": "d", "target": "t", "dataset_ids": [True]}, "integer dataset_ids"),
])
def test_a_malformed_data_item_is_refused(item, message):
    with pytest.raises(ValueError, match=message):
        run_setup_of(entry(data=[item]))


def test_valid_data_items_are_accepted():
    items = [{"kind": "url", "name": "d", "target": "t", "url": "https://example.org/d.zip", "unpack": "zip"},
             {"kind": "url", "name": "e", "target": "t", "url": "https://example.org/e", "unpack": "none"},
             {"kind": "openml", "name": "f", "target": "t", "dataset_ids": [61, 62]},
             {"kind": "openml", "name": "g", "target": "t", "dataset_id": 7}]
    assert run_setup_of(entry(data=items))["data"] == items


@pytest.mark.parametrize("build", ["x", [], {}, {"sdists": []}, {"other": 1}])
def test_a_build_without_sdists_or_from_repo_is_refused(build):
    with pytest.raises(ValueError, match="build needs"):
        run_setup_of(entry(build=build))


def test_a_build_with_sdists_or_from_repo_is_accepted():
    assert run_setup_of(entry(build={"sdists": ["a==1"]}))["build"]
    assert run_setup_of(entry(build={"from_repo": True}))["build"]


def test_constraints_need_a_source():
    with pytest.raises(ValueError, match="constraints_source"):
        run_setup_of(entry(constraints=["numpy<2"]))
    assert run_setup_of(entry(constraints=["numpy<2"], constraints_source="README line 4"))["constraints"] == ["numpy<2"]
    assert run_setup_of(entry(constraints=[]))["constraints"] == []


def test_a_malformed_seed_spec_is_refused():
    with pytest.raises(ValueError):
        run_setup_of(entry(seed={"kind": "no_such_kind"}))


@pytest.mark.parametrize("item,expected", [
    ({"dataset_ids": [1, 2]}, [1, 2]), ({"dataset_id": 3}, [3]), ({}, []), ({"dataset_ids": []}, []),
    ({"dataset_ids": [1, "2"]}, []), ({"dataset_ids": [1.0]}, []), ({"dataset_ids": [True]}, []), ({"dataset_id": None}, []),
])
def test_openml_ids(item, expected):
    assert openml_ids(item) == expected


def test_data_dir_joins_the_cache_the_paper_and_the_item_name():
    assert data_dir(Path("cache"), "paper_x", {"name": "ds"}) == Path("cache") / "paper_x" / "ds"
    assert data_dir("cache", "paper_é", {"name": "准确率"}) == Path("cache") / "paper_é" / "准确率"
