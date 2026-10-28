"""Edge cases of the environment cache: symlinks, empty trees, corrupt or mismatching entries, replacement, Docker errors (#557)."""

import json
import os
import subprocess

import pytest

from src.sandbox import env_cache
from src.sandbox.env_cache import (
    ENTRY_FILE,
    EnvironmentCache,
    environment_key,
    file_sha256,
    image_id,
    tree_digest,
)


def test_the_digest_of_an_empty_tree_is_stable_and_counts_nothing(tmp_path):
    digest, files, total = tree_digest(tmp_path)
    assert (files, total) == (0, 0) and digest == tree_digest(tmp_path)[0]


def test_the_digest_follows_content_names_and_empty_directories(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "f.txt").write_text("one", encoding="utf-8")
    base, files, total = tree_digest(tmp_path)
    assert (files, total) == (1, 3)
    (tmp_path / "a" / "f.txt").write_text("two", encoding="utf-8")
    assert tree_digest(tmp_path)[0] != base
    (tmp_path / "a" / "f.txt").write_text("one", encoding="utf-8")
    assert tree_digest(tmp_path)[0] == base
    (tmp_path / "empty_dir").mkdir()
    assert tree_digest(tmp_path)[0] != base
    (tmp_path / "empty_dir").rmdir()
    (tmp_path / "a" / "f.txt").rename(tmp_path / "a" / "g.txt")
    assert tree_digest(tmp_path)[0] != base


def test_a_symlink_counts_by_its_target_text_not_as_a_file(tmp_path):
    (tmp_path / "real.txt").write_text("x", encoding="utf-8")
    try:
        os.symlink("real.txt", tmp_path / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not allowed on this machine")
    digest, files, _ = tree_digest(tmp_path)
    assert files == 1  # the link is not a counted file
    os.remove(tmp_path / "link.txt")
    os.symlink("other.txt", tmp_path / "link.txt")
    assert tree_digest(tmp_path)[0] != digest


def test_file_sha256_of_an_empty_file_and_of_unicode_content(tmp_path):
    (tmp_path / "e").write_bytes(b"")
    assert file_sha256(tmp_path / "e") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    (tmp_path / "u").write_text("准确率", encoding="utf-8")
    assert len(file_sha256(tmp_path / "u")) == 64


def test_the_key_refuses_an_image_that_docker_does_not_know(tmp_path, monkeypatch):
    monkeypatch.setattr(env_cache, "image_id", lambda image: None)
    packages = tmp_path / "p"
    repo = tmp_path / "r"
    packages.mkdir()
    repo.mkdir()
    with pytest.raises(LookupError, match="not known to Docker"):
        environment_key("img", packages, repo, [])


def test_without_requirement_files_the_mode_is_all_bundled_wheels(tmp_path, monkeypatch):
    monkeypatch.setattr(env_cache, "image_id", lambda image: "sha256:one")
    packages = tmp_path / "p"
    repo = tmp_path / "r"
    packages.mkdir()
    repo.mkdir()
    _, inputs = environment_key("img", packages, repo, ["b", "a"])
    assert inputs["mode"] == "all_bundled_wheels" and inputs["extra_requirements"] == ["a", "b"]


@pytest.mark.parametrize("failure", [FileNotFoundError(), subprocess.TimeoutExpired("docker", 60)])
def test_image_id_is_none_when_docker_is_missing_or_slow(monkeypatch, failure):
    def run(*args, **kwargs):
        raise failure
    monkeypatch.setattr(subprocess, "run", run)
    assert image_id("img") is None


@pytest.mark.parametrize("stdout,returncode,expected", [("sha256:abc\n", 0, "sha256:abc"), ("", 0, None), ("Error", 1, None), ("   \n", 0, None)])
def test_image_id_reads_the_docker_answer(monkeypatch, stdout, returncode, expected):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, returncode, stdout=stdout, stderr=""))
    assert image_id("img") == expected


def make_entry(tmp_path):
    deps = tmp_path / "deps_src"
    deps.mkdir()
    (deps / "pkg.py").write_text("x = 1\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    (out / "install.log").write_text("ok", encoding="utf-8")
    cache = EnvironmentCache(tmp_path / "cache")
    key = "k" * 64
    cache.store(key, {"image": "img", "bundle": {"a.whl": "1"}}, deps, out)
    return cache, key


def test_lookup_without_an_entry_says_so(tmp_path):
    entry, info = EnvironmentCache(tmp_path / "cache").lookup("z" * 64)
    assert entry is None and info["reason"] == "no entry for this key"


def test_a_stored_entry_is_a_hit_and_keeps_the_install_files(tmp_path):
    cache, key = make_entry(tmp_path)
    entry, info = cache.lookup(key)
    assert entry is not None and info["reason"] == "hit" and info["files"] == 1
    assert (entry / "install.log").read_text(encoding="utf-8") == "ok"


def test_a_changed_file_in_the_entry_deletes_it(tmp_path):
    cache, key = make_entry(tmp_path)
    (cache.entry_dir(key) / "deps" / "pkg.py").write_text("x = 2\n", encoding="utf-8")
    entry, info = cache.lookup(key)
    assert entry is None and "does not match" in info["reason"] and not cache.entry_dir(key).exists()


@pytest.mark.parametrize("content", ["", "{not json"])
def test_an_unreadable_entry_file_deletes_the_entry(tmp_path, content):
    cache, key = make_entry(tmp_path)
    (cache.entry_dir(key) / ENTRY_FILE).write_text(content, encoding="utf-8")
    entry, info = cache.lookup(key)
    assert entry is None and "unreadable" in info["reason"] and not cache.entry_dir(key).exists()


def test_an_entry_stored_under_another_key_is_refused(tmp_path):
    cache, key = make_entry(tmp_path)
    meta_path = cache.entry_dir(key) / ENTRY_FILE
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["key"] = "other"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    assert cache.lookup(key)[0] is None


def test_storing_the_same_key_again_replaces_the_entry(tmp_path):
    cache, key = make_entry(tmp_path)
    deps = tmp_path / "deps_two"
    deps.mkdir()
    (deps / "other.py").write_text("y = 2\n", encoding="utf-8")
    cache.store(key, {"image": "img", "bundle": {}}, deps, tmp_path / "out")
    entry, _ = cache.lookup(key)
    assert entry is not None and (entry / "deps" / "other.py").is_file() and not (entry / "deps" / "pkg.py").exists()
    assert not [p for p in cache.root.iterdir() if p.name.startswith(".tmp-")]
