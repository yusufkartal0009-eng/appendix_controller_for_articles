"""Small command-line tools without tests before: the pilot environment record, claim extraction (no API call), the dashboard
entry point (#272)."""

import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.web.app
from src.pdf_text import PdfText

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import extract_claims as ec
import record_pilot2_environment as rpe


def test_run_returns_output_stderr_and_exit_code():
    ok = rpe.run([sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"])
    assert ok == "out\n\n[stderr]\nerr\n[exit code 3]"
    assert rpe.run([sys.executable, "-c", "print('only out')"]) == "only out\n[exit code 0]"


def test_run_reports_a_command_that_cannot_start():
    assert rpe.run(["no-such-program-for-the-repro-radar-tests"]).startswith("FAILED to run:")


def test_the_record_lists_python_first_and_ends_with_the_disk_usage(tmp_path, monkeypatch, capsys):
    out = tmp_path / "pilot2" / "environment.txt"
    monkeypatch.setattr(rpe, "OUT", out)
    monkeypatch.setattr(rpe, "COMMANDS", [("python --version", [sys.executable, "--version"])])
    assert rpe.main() == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("Pilot 2 environment, recorded ") and "=== python --version\nPython 3." in text
    assert "=== disk usage of the drive holding the repository" in text and "free=" in text
    assert "wrote" in capsys.readouterr().out


def test_the_real_command_list_starts_with_the_python_version():
    assert rpe.COMMANDS[0][0] == "python --version"


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_download_pdf_keeps_an_existing_file_and_checks_what_it_gets(tmp_path, monkeypatch):
    existing = tmp_path / "have.pdf"
    existing.write_bytes(b"%PDF-existing")
    monkeypatch.setattr(ec.urllib.request, "urlopen", lambda *a, **k: pytest.fail("must not download"))
    assert ec.download_pdf("https://example.org/p.pdf", existing) == existing
    monkeypatch.setattr(ec.urllib.request, "urlopen", lambda *a, **k: FakeResponse(b"<html>not a pdf"))
    with pytest.raises(ValueError, match="did not return a PDF"):
        ec.download_pdf("https://example.org/p.pdf", tmp_path / "sub" / "new.pdf")
    monkeypatch.setattr(ec.urllib.request, "urlopen", lambda *a, **k: FakeResponse(b"%PDF-1.7 data"))
    saved = ec.download_pdf("https://example.org/p.pdf", tmp_path / "sub" / "new.pdf")
    assert saved.read_bytes() == b"%PDF-1.7 data"


@pytest.fixture
def paper(tmp_path, monkeypatch):
    queries = tmp_path / "queries"
    queries.mkdir()
    (queries / "paper_900.json").write_text(json.dumps({
        "paper_id": "paper_900", "pdf_url": "https://example.org/p.pdf",
        "queries": [{"query_id": "q1", "question": "What is x?"}, {"query_id": "q2", "question": "What is y?"}]}),
        encoding="utf-8")
    monkeypatch.setattr(ec, "QUERIES_DIR", queries)
    monkeypatch.setattr(ec, "PDF_DIR", tmp_path / "pdfs")
    monkeypatch.setattr(ec, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(ec, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(ec, "download_pdf", lambda url, dest: dest)
    monkeypatch.setattr(ec, "extract_pdf_text", lambda path: PdfText(sha256="a" * 64, extractor="t", pages=["page"]))
    return tmp_path


def test_an_uncached_extraction_needs_an_api_key(paper, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(ec, "extract_claims", lambda *a, **k: pytest.fail("must not be called"))
    assert ec.main(["paper_900"]) == 2
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err


def test_a_failed_extraction_exits_with_1(paper, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")

    def fail(*args, **kwargs):
        raise ec.ExtractionError("model refused")

    monkeypatch.setattr(ec, "extract_claims", fail)
    assert ec.main(["paper_900"]) == 1
    assert "EXTRACTION FAILED: model refused" in capsys.readouterr().err


def test_a_cached_extraction_runs_without_a_key_and_is_written_and_printed(paper, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cache = paper / "data" / "llm_cache"
    cache.mkdir(parents=True)
    queries = [ec.Query("q1", "What is x?"), ec.Query("q2", "What is y?")]
    (cache / f"{ec.cache_key(PdfText(sha256='a' * 64, extractor='t', pages=['page']), queries)}.json").write_text("{}")
    claim = SimpleNamespace(value_as_printed="0.9", page=3, table_or_figure="Table 1")
    result = SimpleNamespace(
        answers={"q1": {"status": "found", "claim_index": 0}, "q2": {"status": "not_found", "reason": "absent"}},
        claim_set=SimpleNamespace(claims=[claim], model_dump=lambda: {"claims": 1}),
        meta={"model_served": "m", "fallback_used": False, "usage": {"in": 1}, "estimated_cost_usd": 0.01, "from_cache": True})
    monkeypatch.setattr(ec, "extract_claims", lambda *a, **k: result)
    assert ec.main(["paper_900"]) == 0
    out = capsys.readouterr().out
    assert "q1: FOUND '0.9' (page 3, Table 1)" in out and "q2: NOT_FOUND absent" in out and "from cache: True" in out
    written = json.loads((paper / "out" / "paper_900.json").read_text(encoding="utf-8"))
    assert written["paper_id"] == "paper_900" and [q["query_id"] for q in written["queries"]] == ["q1", "q2"]


def test_the_dashboard_binds_to_localhost_only(monkeypatch):
    started = {}
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: started.update(app=app, host=host, port=port))
    monkeypatch.setattr(src.web.app, "create_app", lambda db_url=None: ("app", db_url))
    monkeypatch.setattr(sys, "argv", ["src.web", "--port", "8123", "--db-url", "sqlite://"])
    runpy.run_module("src.web", run_name="__main__")
    assert started == {"app": ("app", "sqlite://"), "host": "127.0.0.1", "port": 8123}
