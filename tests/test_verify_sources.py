"""Source lookups for the report's related-work section (#270): the checks, with a fake HTTP client."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import verify_sources as vs

CROSSREF_OK = json.dumps({"message": {
    "title": ["Repeatability in computer systems research"], "author": [{"given": "Christian", "family": "Collberg"},
                                                                         {"given": "Todd", "family": "Proebsting"}],
    "issued": {"date-parts": [[2016, 2, 25]]}, "container-title": ["Communications of the ACM"], "page": "62-69",
    "abstract": "<jats:p>To encourage <jats:italic>repeatable</jats:italic> research.</jats:p>", "volume": "59", "issue": "3",
    "URL": "http://dx.doi.org/10.1145/2812803"}})
ARXIV_OK = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1909.06674v1</id>
<published>2019-09-14T00:00:00Z</published><title>A Step Toward Quantifying
 Independently Reproducible Machine Learning Research</title><summary> What makes a paper
 reproducible? </summary><author><name>Edward Raff</name></author></entry></feed>"""
ARXIV_EMPTY = """<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

ENTRY_DOI = {"ref": "[10]", "expected_title": "Repeatability in computer systems research",
             "first_author_family": "Collberg", "year": 2016, "doi": "10.1145/2812803"}
ENTRY_ARXIV = {"ref": "[9]", "expected_title": "A Step Toward Quantifying Independently Reproducible Machine Learning Research",
               "first_author_family": "Raff", "year": 2019, "arxiv_id": "1909.06674"}


def fake(responses):
    def get(url, timeout=30):
        for marker, reply in responses.items():
            if marker in url:
                return reply
        return 404, ""
    return get


def no_pause(_seconds):
    return None


def test_crossref_source_is_verified_and_the_abstract_markup_is_removed():
    result = vs.verify_source(ENTRY_DOI, fake({"crossref": (200, CROSSREF_OK)}), no_pause)
    assert result["status"] == "VERIFIED" and result["reasons"] == []
    found = result["lookups"]["crossref"]
    assert found["authors"] == ["Christian Collberg", "Todd Proebsting"] and found["volume"] == "59"
    assert found["abstract"] == "To encourage repeatable research."


def test_arxiv_source_is_verified_and_whitespace_in_the_title_is_collapsed():
    result = vs.verify_source(ENTRY_ARXIV, fake({"arxiv": (200, ARXIV_OK)}), no_pause)
    assert result["status"] == "VERIFIED"
    assert result["lookups"]["arxiv"]["abstract"] == "What makes a paper reproducible?"


def test_wrong_title_author_or_year_makes_the_source_not_verified():
    wrong = {**ENTRY_DOI, "expected_title": "A different paper", "first_author_family": "Smith", "year": 2010}
    result = vs.verify_source(wrong, fake({"crossref": (200, CROSSREF_OK)}), no_pause)
    assert result["status"] == "NOT_VERIFIED"
    assert [r.split(":")[1].split(" (")[0].strip() for r in result["reasons"]] == [
        "title differs", "first author differs", "year differs"]


def test_unknown_identifier_is_not_found():
    result = vs.verify_source(ENTRY_DOI, fake({}), no_pause)
    assert result["status"] == "NOT_VERIFIED" and "not found (HTTP 404)" in result["reasons"][0]
    result = vs.verify_source(ENTRY_ARXIV, fake({"arxiv": (200, ARXIV_EMPTY)}), no_pause)
    assert result["status"] == "NOT_VERIFIED"


def test_entry_without_an_identifier_cannot_be_verified():
    result = vs.verify_source({k: v for k, v in ENTRY_DOI.items() if k != "doi"}, fake({}), no_pause)
    assert result["status"] == "NOT_VERIFIED" and result["reasons"] == ["no doi or arxiv_id to look up"]


def test_a_preprint_may_be_a_year_earlier_than_the_published_paper():
    early = ARXIV_OK.replace("2019-09-14", "2018-09-14")
    assert vs.verify_source(ENTRY_ARXIV, fake({"arxiv": (200, early)}), no_pause)["status"] == "VERIFIED"
    much_earlier = ARXIV_OK.replace("2019-09-14", "2015-09-14")
    assert vs.verify_source(ENTRY_ARXIV, fake({"arxiv": (200, much_earlier)}), no_pause)["status"] == "NOT_VERIFIED"


def test_preprint_title_can_differ_from_the_published_title_when_the_input_says_so():
    longer = ARXIV_OK.replace("Machine Learning Research", "Machine Learning Research, with examples from the R environment")
    assert vs.verify_source(ENTRY_ARXIV, fake({"arxiv": (200, longer)}), no_pause)["status"] == "NOT_VERIFIED"
    entry = {**ENTRY_ARXIV, "arxiv_expected_title": ENTRY_ARXIV["expected_title"] + ", with examples from the R environment"}
    assert vs.verify_source(entry, fake({"arxiv": (200, longer)}), no_pause)["status"] == "VERIFIED"


def test_both_lookups_must_agree_and_arxiv_waits_after_crossref():
    both = {**ENTRY_DOI, "arxiv_id": "1909.06674"}
    pauses = []
    result = vs.verify_source(both, fake({"crossref": (200, CROSSREF_OK), "arxiv": (200, ARXIV_OK)}), pauses.append)
    assert result["status"] == "NOT_VERIFIED" and all(r.startswith("arxiv:") for r in result["reasons"])
    assert pauses == [vs.ARXIV_PAUSE_SECONDS]


def test_the_stored_verification_covers_every_input_source_and_all_are_verified():
    entries = json.loads(vs.SOURCES_PATH.read_text(encoding="utf-8"))["sources"]
    stored = json.loads(vs.OUTPUT_PATH.read_text(encoding="utf-8"))
    by_ref = {s["ref"]: s for s in stored["sources"]}
    assert [e["ref"] for e in entries] == [s["ref"] for s in stored["sources"]]
    assert {r: by_ref[r]["status"] for r in by_ref} == {r: "VERIFIED" for r in by_ref}
    assert 5 <= len(entries) <= 10 + 2  # the report asks for 5-10 new sources; [6] and [7] are re-checked too


def test_every_source_the_draft_cites_is_in_the_sources_table():
    report = (Path(__file__).resolve().parent.parent / "docs" / "report" / "REPORT.md").read_text(encoding="utf-8")
    start, end = report.index("## 3. Related work"), report.index("## 4. Method")
    section = report[start:end]
    table = (Path(__file__).resolve().parent.parent / "docs" / "report" / "RELATED_WORK_SOURCES.md").read_text(encoding="utf-8")
    cited = {m for group in re.findall(r"\[(\d+(?:,\s*\d+)*)\]", section) for m in group.replace(" ", "").split(",")}
    for number in cited:
        assert f"| [{number}] |" in table, number
