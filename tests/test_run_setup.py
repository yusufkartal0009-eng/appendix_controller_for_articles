"""Per-paper run setups and the sandbox options they need (#166)."""

import io
import json
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from src.config import SEED_PAPERS_PATH
from src.sandbox.run_setup import run_setup_of, sandbox_options
from src.sandbox.runner import (
    DockerSandboxRunner,
    SandboxConfig,
    SandboxUnavailableError,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fetch_data

ENTRIES = {e["paper_id"]: e for e in json.loads(SEED_PAPERS_PATH.read_text(encoding="utf-8"))}


def test_every_seed_paper_has_a_decision_and_none_is_replaced():
    assert sorted(ENTRIES) == ["paper_002", "paper_003", "paper_004", "paper_005", "paper_006", "paper_008"]
    decisions = {pid: run_setup_of(e)["decision"] for pid, e in ENTRIES.items()}
    assert decisions.pop("paper_008") == "report_as_is"
    assert set(decisions.values()) == {"fix"}
    assert run_setup_of(ENTRIES["paper_008"])["expected_outcome"] == "DATA_NOT_ACCESSIBLE"


def test_run_setups_build_valid_sandbox_configs(tmp_path):
    for pid, entry in ENTRIES.items():
        for item in run_setup_of(entry).get("data", []):  # pretend the data is cached
            marker = tmp_path / pid / item["name"] / ".complete"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("{}")
        opts = sandbox_options(entry, tmp_path)
        SandboxConfig(python_version=entry.get("python_version", "3.11"), env_vars=opts["env_vars"],
                      working_dir=opts["working_dir"], writable_repo=opts["writable_repo"],
                      data_mounts=opts["data_mounts"])


def test_missing_data_is_refused(tmp_path):
    with pytest.raises(ValueError, match="fetch_data.py"):
        sandbox_options(ENTRIES["paper_003"], tmp_path)


def test_malformed_run_setup_is_refused():
    with pytest.raises(ValueError, match="reason"):
        run_setup_of({"paper_id": "p", "run_setup": {"decision": "fix"}})
    with pytest.raises(ValueError, match="decision"):
        run_setup_of({"paper_id": "p", "run_setup": {"decision": "replace", "reason": "x"}})
    with pytest.raises(ValueError, match="unpack"):
        run_setup_of({"paper_id": "p", "run_setup": {"decision": "fix", "reason": "x",
                                                     "data": [{"name": "d", "kind": "url", "url": "u", "target": "data"}]}})


def test_paths_must_stay_inside_the_sandbox():
    with pytest.raises(ValueError):
        SandboxConfig(working_dir="../outside")
    with pytest.raises(ValueError):
        SandboxConfig(working_dir="/etc")
    with pytest.raises(ValueError):
        SandboxConfig(data_mounts={"/etc/passwd": "x"})
    with pytest.raises(ValueError):
        SandboxConfig(data_mounts={"data/../../x": "x"})
    assert SandboxConfig(working_dir="./results/").working_dir == "results"


def test_docker_command_has_working_dir_writable_repo_and_read_only_data(tmp_path):
    cache = tmp_path / "cache"
    config = SandboxConfig(working_dir="results", writable_repo=True,
                           data_mounts={"data": str(cache), "/workspace/home/.openml/cache": str(cache)})
    cmd = DockerSandboxRunner(config).build_docker_command(tmp_path / "repo", tmp_path / "out", ["python", "x.py"])
    joined = " ".join(cmd)
    assert cmd[cmd.index("-w") + 1] == "/workspace/repo/results"
    assert "SANDBOX_WORKDIR=/workspace/repo/results" in cmd
    assert f"{(tmp_path / 'repo').resolve()}:/workspace/repo:rw" in cmd
    assert f"{cache.resolve()}:/workspace/repo/data:ro" in cmd
    assert f"{cache.resolve()}:/workspace/home/.openml/cache:ro" in cmd
    default = " ".join(DockerSandboxRunner(SandboxConfig()).build_docker_command(tmp_path / "repo", tmp_path / "out", ["x"]))
    assert ":/workspace/repo:ro" in default and "-w /workspace/repo " in default
    assert "--read-only" in joined and "--network none" in joined  # the isolation flags stay


def test_writable_copy_and_mount_points(tmp_path):
    repo = tmp_path / "repo"
    (repo / "exp").mkdir(parents=True)
    (repo / "exp" / "0.toml").write_text("x")
    (repo / ".git").mkdir()
    copy = DockerSandboxRunner._writable_copy(repo, tmp_path / "out")
    assert (copy / "exp" / "0.toml").read_text() == "x" and not (copy / ".git").exists()
    runner = DockerSandboxRunner(SandboxConfig(data_mounts={"data/sub": str(tmp_path)}))
    runner._create_mount_points(copy)
    assert (copy / "data" / "sub").is_dir()
    assert not (repo / "data").exists()  # the staged repository is not changed


def test_local_fallback_refuses_a_run_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *a, **k: False))
    runner = DockerSandboxRunner(SandboxConfig(working_dir="results", allow_unsafe_local=True))
    with pytest.raises(SandboxUnavailableError, match="run setup"):
        runner.run(paper_id="p", repo_dir=tmp_path, target_script="x.py")


def _tar_with_data(path: Path) -> int:
    with tarfile.open(path, "w:gz") as tar:
        payload = b"a,b\n1,2\n"
        info = tarfile.TarInfo("data/california/X.csv")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    return path.stat().st_size


def test_fetch_downloads_checks_size_and_unpacks(tmp_path):
    archive = tmp_path / "data.tar.gz"
    size = _tar_with_data(archive)
    item = {"name": "d", "kind": "url", "url": archive.as_uri(), "bytes": size, "unpack": "tar",
            "path_in_archive": "data", "target": "data"}
    cache = tmp_path / "cache"
    assert fetch_data.fetch_item("paper_x", item, cache)["status"] == "FETCHED"
    assert (cache / "paper_x" / "d" / "data" / "california" / "X.csv").read_text() == "a,b\n1,2\n"
    assert fetch_data.fetch_item("paper_x", item, cache)["status"] == "CACHED"
    entry = {"paper_id": "paper_x", "run_setup": {"decision": "fix", "reason": "r", "data": [item]}}
    assert sandbox_options(entry, cache)["data_mounts"] == {"data": str(cache / "paper_x" / "d" / "data")}


def test_fetch_size_mismatch_leaves_no_cache(tmp_path):
    archive = tmp_path / "data.tar.gz"
    size = _tar_with_data(archive)
    item = {"name": "d", "kind": "url", "url": archive.as_uri(), "bytes": size + 1, "unpack": "tar", "target": "data"}
    with pytest.raises(ValueError, match="expected"):
        fetch_data.fetch_item("paper_x", item, tmp_path / "cache")
    assert not (tmp_path / "cache" / "paper_x" / "d" / ".complete").exists()


def test_fetch_refuses_unsafe_archive_paths(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("../escape.txt", "x")
    with pytest.raises(ValueError, match="unsafe"):
        fetch_data.unpack(bad, "zip", tmp_path / "out")
    bad_tar = tmp_path / "bad.tar"
    with tarfile.open(bad_tar, "w") as tar:
        info = tarfile.TarInfo("../escape.txt")
        tar.addfile(info, io.BytesIO(b""))
    with pytest.raises(tarfile.FilterError):
        fetch_data.unpack(bad_tar, "tar", tmp_path / "out")
