"""SHA-256 manifests of run directories (#29)."""

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from src.artifact_hash import (
    MANIFEST_NAME,
    build_manifest,
    classify,
    combined_hash,
    compare_manifests,
    hash_file,
    load_manifest,
    store_hashes,
    summarize,
    verify_manifest,
    write_manifest,
)
from src.database import get_session, init_db
from src.models import PaperORM, RunORM

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import hash_run


def _run_dir(root, weights=b"w" * 10, log="took 1.0 s\n"):
    root.mkdir(parents=True)
    (root / "stdout.log").write_text(log, encoding="utf-8")
    (root / "execution_meta.json").write_text('{"duration_seconds": 1.0}', encoding="utf-8")
    (root / "predictions.csv").write_text("id,pred\n1,0.5\n", encoding="utf-8")
    (root / "models").mkdir()
    (root / "models" / "weights.bin").write_bytes(weights)
    return root


def test_hash_file_matches_hashlib_for_a_file_larger_than_one_chunk(tmp_path):
    data = os.urandom((1 << 20) + 123)
    path = tmp_path / "big.bin"
    path.write_bytes(data)
    assert hash_file(path) == hashlib.sha256(data).hexdigest()


def test_manifest_lists_every_file_with_size_hash_and_category(tmp_path):
    manifest = build_manifest(_run_dir(tmp_path / "run"))
    by_path = {f["path"]: f for f in manifest["files"]}
    assert sorted(by_path) == ["execution_meta.json", "models/weights.bin", "predictions.csv", "stdout.log"]
    assert by_path["models/weights.bin"]["sha256"] == hashlib.sha256(b"w" * 10).hexdigest()
    assert by_path["models/weights.bin"]["bytes"] == 10
    assert {p: f["category"] for p, f in by_path.items()} == {
        "execution_meta.json": "metadata", "models/weights.bin": "artifact", "predictions.csv": "artifact",
        "stdout.log": "log"}
    assert manifest["file_count"] == 4 and manifest["total_bytes"] == sum(f["bytes"] for f in manifest["files"])
    assert manifest["skipped"] == []


def test_hashes_are_the_sha256sum_format_and_do_not_depend_on_file_order(tmp_path):
    manifest = build_manifest(_run_dir(tmp_path / "run"))
    lines = "".join(f"{f['sha256']}  {f['path']}\n" for f in manifest["files"])
    assert manifest["manifest_sha256"] == hashlib.sha256(lines.encode()).hexdigest()
    shuffled = list(reversed(manifest["files"]))
    assert combined_hash(shuffled) == manifest["manifest_sha256"]
    artifacts = [f for f in manifest["files"] if f["category"] == "artifact"]
    assert manifest["outputs_sha256"] == combined_hash(artifacts)


def test_two_identical_runs_have_the_same_outputs_hash_even_when_logs_differ(tmp_path):
    a = build_manifest(_run_dir(tmp_path / "a", log="took 1.0 s\n"))
    b = build_manifest(_run_dir(tmp_path / "b", log="took 9.9 s\n"))
    assert a["outputs_sha256"] == b["outputs_sha256"] and a["manifest_sha256"] != b["manifest_sha256"]
    comparison = compare_manifests(a, b)
    assert comparison["same_outputs_hash"] and comparison["outputs_reproduced"]
    assert comparison["log"]["differing"] == ["stdout.log"] and comparison["artifact"]["identical"] == 2
    assert "paper output files reproduced byte for byte: yes" in summarize(comparison)


def test_a_changed_output_file_is_reported(tmp_path):
    a = build_manifest(_run_dir(tmp_path / "a"))
    b = build_manifest(_run_dir(tmp_path / "b", weights=b"different"))
    comparison = compare_manifests(a, b)
    assert not comparison["same_outputs_hash"] and not comparison["outputs_reproduced"]
    assert comparison["artifact"]["differing"] == ["models/weights.bin"]
    assert "differing: models/weights.bin" in summarize(comparison)


def test_files_in_only_one_run_are_reported(tmp_path):
    first = _run_dir(tmp_path / "a")
    second = _run_dir(tmp_path / "b")
    (second / "extra.txt").write_text("x", encoding="utf-8")
    comparison = compare_manifests(build_manifest(first), build_manifest(second))
    assert comparison["artifact"]["only_in_second"] == ["extra.txt"] and not comparison["outputs_reproduced"]


def test_a_run_without_paper_files_has_no_outputs_hash_and_is_not_reproduced(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    (root / "stdout.log").write_text("x", encoding="utf-8")
    manifest = build_manifest(root)
    assert manifest["outputs_sha256"] is None
    assert not compare_manifests(manifest, manifest)["outputs_reproduced"]


def test_verify_finds_modified_missing_and_added_files(tmp_path):
    root = _run_dir(tmp_path / "run")
    manifest = build_manifest(root)
    assert verify_manifest(root, manifest) == {"ok": True, "modified": [], "missing": [], "added": [], "files_checked": 4}
    (root / "predictions.csv").write_text("id,pred\n1,0.9\n", encoding="utf-8")
    (root / "stdout.log").unlink()
    (root / "new.txt").write_text("n", encoding="utf-8")
    report = verify_manifest(root, manifest)
    assert report["ok"] is False
    assert (report["modified"], report["missing"], report["added"]) == (["predictions.csv"], ["stdout.log"], ["new.txt"])


def test_the_manifest_file_is_not_part_of_the_manifest(tmp_path):
    root = _run_dir(tmp_path / "run")
    first = build_manifest(root)
    write_manifest(root, first)
    assert (root / MANIFEST_NAME).exists()
    assert build_manifest(root) == first
    assert load_manifest(root) == first
    assert verify_manifest(root, load_manifest(root))["ok"]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symbolic links")
def test_symbolic_links_are_skipped_not_followed(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("host file", encoding="utf-8")
    root = _run_dir(tmp_path / "run")
    try:
        os.symlink(secret, root / "link.txt")
        os.symlink(tmp_path, root / "dirlink", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this account cannot create symbolic links")
    manifest = build_manifest(root)
    assert "link.txt" not in [f["path"] for f in manifest["files"]]
    assert not any(f["path"].startswith("dirlink") for f in manifest["files"])
    assert {s["path"] for s in manifest["skipped"]} == {"link.txt", "dirlink"}
    assert all("symbolic link" in s["reason"] for s in manifest["skipped"])


def test_an_unreadable_file_is_listed_as_skipped(tmp_path, monkeypatch):
    root = _run_dir(tmp_path / "run")
    real = hash_file

    def flaky(path):
        if path.name == "predictions.csv":
            raise PermissionError(13, "denied")
        return real(path)

    monkeypatch.setattr("src.artifact_hash.hash_file", flaky)
    manifest = build_manifest(root)
    assert [s["path"] for s in manifest["skipped"]] == ["predictions.csv"]
    assert "unreadable: PermissionError (errno 13)" == manifest["skipped"][0]["reason"]
    assert "predictions.csv" not in [f["path"] for f in manifest["files"]]


def test_classify():
    assert classify("a/b/console.log") == "log"
    assert classify("run_report.json") == "metadata"
    assert classify("sub/run_report.json") == "metadata"
    assert classify("results.json") == "artifact"


def test_not_a_directory(tmp_path):
    with pytest.raises(NotADirectoryError):
        build_manifest(tmp_path / "missing")


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}", future=True)
    init_db(engine)
    session = get_session(engine)
    session.add(PaperORM(paper_id="paper_001", title="T", year=2021, venue="V", repo_url="https://x", license="MIT",
                         target_script="a.py", expected_claims="{}", source_table_or_section="{}"))
    session.add(RunORM(run_id="r1", paper_id="paper_001", status="COMPLETED"))
    session.commit()
    return engine, session


def test_hashes_are_saved_in_the_runs_table(tmp_path):
    engine, session = _session(tmp_path)
    manifest = build_manifest(_run_dir(tmp_path / "run"))
    store_hashes(session, "r1", manifest)
    session.close()
    with engine.connect() as conn:
        row = conn.exec_driver_sql("SELECT artifact_manifest_sha256, outputs_sha256 FROM runs WHERE run_id = 'r1'").one()
    assert row == (manifest["manifest_sha256"], manifest["outputs_sha256"])


def test_saving_for_an_unknown_run_fails(tmp_path):
    _, session = _session(tmp_path)
    with pytest.raises(KeyError, match="no run 'nope'"):
        store_hashes(session, "nope", build_manifest(_run_dir(tmp_path / "run")))
    session.close()


def test_command_line_write_verify_compare_and_store(tmp_path, capsys):
    root = _run_dir(tmp_path / "run")
    other = _run_dir(tmp_path / "other", log="took 5 s\n")
    assert hash_run.main([str(root)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["file_count"] == 4 and not (root / MANIFEST_NAME).exists()
    assert hash_run.main([str(root), "--write"]) == 0
    capsys.readouterr()
    assert hash_run.main([str(root), "--verify"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    (root / "predictions.csv").write_text("changed", encoding="utf-8")
    assert hash_run.main([str(root), "--verify"]) == 1
    assert json.loads(capsys.readouterr().out)["modified"] == ["predictions.csv"]
    assert hash_run.main([str(other), "--compare", str(tmp_path / "other")]) == 0
    assert "paper output files reproduced byte for byte: yes" in capsys.readouterr().out
    url = f"sqlite:///{tmp_path / 'cli.sqlite'}"
    assert hash_run.main([str(other), "--store", "missing-run", "--db-url", url]) == 2
    assert "no run 'missing-run'" in capsys.readouterr().err
