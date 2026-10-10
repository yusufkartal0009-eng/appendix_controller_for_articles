"""Build phase, sdist download, writable data copies, and run setup bundling (#193)."""

import hashlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import SEED_PAPERS_PATH
from src.sandbox import runner as runner_module
from src.sandbox import stager as stager_module
from src.sandbox.run_setup import run_setup_of, sandbox_options
from src.sandbox.runner import (
    DockerSandboxRunner,
    SandboxConfig,
    SandboxUnavailableError,
    build_image_for,
)
from src.sandbox.sdist import download_sdist, parse_pin
from src.sandbox.stager import RepoStager, StagedRepo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fetch_data

ENTRIES = {e["paper_id"]: e for e in json.loads(SEED_PAPERS_PATH.read_text(encoding="utf-8"))}


def test_build_image_names():
    assert build_image_for("3.11") == "repro-radar-sandbox:build"
    assert build_image_for("3.8") == "repro-radar-sandbox:py3.8-build"
    with pytest.raises(ValueError):
        build_image_for("2.7")


def test_writable_data_needs_a_mount_and_gets_a_rw_copy(tmp_path):
    with pytest.raises(ValueError, match="without a data mount"):
        SandboxConfig(writable_data=["/workspace/home/x"])
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "description.xml").write_text("<x/>")
    runner = DockerSandboxRunner(SandboxConfig(data_mounts={"/workspace/home/.openml/cache": str(cache), "data": str(cache)},
                                               writable_data=["/workspace/home/.openml/cache"]))
    runner._run_data_hosts = runner._writable_data_copies(tmp_path / "out")
    cmd = runner.build_docker_command(tmp_path / "repo", tmp_path / "out", ["x"])
    # #231: mounted through its top-level directory, so the parent `.openml` exists and is writable by uid 1000
    overlay = (tmp_path / "out" / "home_mounts" / ".openml").resolve()
    assert f"{overlay}:/workspace/home/.openml:rw" in cmd
    assert not any(a.endswith(":/workspace/home/.openml/cache:rw") for a in cmd)
    assert f"{cache.resolve()}:/workspace/repo/data:ro" in cmd  # not listed as writable: stays read-only
    assert (overlay / "cache" / "description.xml").read_text() == "<x/>"
    (overlay / "config").write_text("a sibling of the cache can be created")


def test_build_wheels_refuses_without_docker(tmp_path, monkeypatch):
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *a, **k: False))
    with pytest.raises(SandboxUnavailableError):
        DockerSandboxRunner(SandboxConfig()).build_wheels("p", tmp_path, tmp_path, ["/workspace/repo"])


def test_build_wheels_command(tmp_path, monkeypatch):
    monkeypatch.setattr(DockerSandboxRunner, "is_docker_available", staticmethod(lambda *a, **k: True))
    monkeypatch.setattr(runner_module, "SANDBOX_RUNS_DIR", tmp_path / "runs")
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        out = tmp_path / "runs" / "p.build"
        (out / "built_wheels").mkdir()
        (out / "built_wheels" / "fastsk-0.0.2-cp38-cp38-linux_x86_64.whl").write_text("w")
        (out / "build_meta.json").write_text(json.dumps({"status": "BUILT", "duration_seconds": 1.5}))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "setup.py").write_text("")
    result = DockerSandboxRunner(SandboxConfig(python_version="3.8", working_dir="results")).build_wheels(
        "p", repo, tmp_path, ["/workspace/repo"], ["pybind11==2.6.2"], from_repo=True)
    cmd = " ".join(seen["cmd"])
    assert result["status"] == "BUILT" and result["wheels"][0].endswith("linux_x86_64.whl")
    assert "repro-radar-sandbox:py3.8-build" in seen["cmd"] and "--network none" in cmd and "--read-only" in cmd
    assert "SANDBOX_PHASE=build" in seen["cmd"] and "SANDBOX_BUILD_REQUIREMENTS=pybind11==2.6.2" in seen["cmd"]
    assert ":/workspace/repo:rw" in cmd and "repo_copy" in cmd  # built from a writable copy, never the staged repo
    assert "-w /workspace/repo " in cmd + " "  # the run's working_dir does not apply to the build


def test_parse_pin():
    assert parse_pin("openml==0.11.0") == ("openml", "0.11.0")
    for bad in ("openml", "openml>=0.11", "openml==", "openml==0.11.*"):
        with pytest.raises(ValueError):
            parse_pin(bad)


def _fake_pypi(payload: bytes, digest: str):
    meta = {"urls": [{"packagetype": "bdist_wheel", "url": "x", "filename": "x.whl", "digests": {"sha256": "0"}},
                     {"packagetype": "sdist", "url": "https://files/openml-0.11.0.tar.gz",
                      "filename": "openml-0.11.0.tar.gz", "digests": {"sha256": digest}}]}

    def opener(url, timeout):
        return io.BytesIO(json.dumps(meta).encode() if "pypi.org" in url else payload)
    return opener


def test_download_sdist_checks_the_digest(tmp_path):
    payload = b"sdist bytes"
    path = download_sdist("openml==0.11.0", tmp_path, _fake_pypi(payload, hashlib.sha256(payload).hexdigest()))
    assert path.name == "openml-0.11.0.tar.gz" and path.read_bytes() == payload
    with pytest.raises(ValueError, match="SHA-256"):
        download_sdist("openml==0.11.0", tmp_path / "x", _fake_pypi(payload, "0" * 64))
    assert not (tmp_path / "x" / "openml-0.11.0.tar.gz").exists()


def test_fetch_openml_dataset_writes_the_cache_layout(tmp_path):
    api = tmp_path / "api"
    arff = b"@relation x\n@data\n1\n"
    (api / "data" / "features").mkdir(parents=True)
    (api / "data" / "qualities").mkdir(parents=True)
    (tmp_path / "file.arff").write_bytes(arff)
    (api / "data" / "7").write_text(
        '<oml:data_set_description xmlns:oml="http://openml.org/openml"><oml:id>7</oml:id>'
        f"<oml:url>{(tmp_path / 'file.arff').as_uri()}</oml:url>"
        f"<oml:md5_checksum>{hashlib.md5(arff).hexdigest()}</oml:md5_checksum></oml:data_set_description>")
    (api / "data" / "features" / "7").write_text("<f/>")
    (api / "data" / "qualities" / "7").write_text("<q/>")
    fetch_data.fetch_openml_dataset(7, tmp_path / "cache", api=api.as_uri())
    did = tmp_path / "cache" / "org" / "openml" / "www" / "datasets" / "7"
    assert sorted(p.name for p in did.iterdir()) == ["dataset.arff", "description.xml", "features.xml", "qualities.xml"]
    (tmp_path / "file.arff").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="MD5"):
        fetch_data.fetch_openml_dataset(7, tmp_path / "cache2", api=api.as_uri())


def test_seed_run_setups_for_193():
    s002, s005, s006 = (run_setup_of(ENTRIES[p]) for p in ("paper_002", "paper_005", "paper_006"))
    assert s002["build"]["sdists"] == ["openml==0.12.2", "liac-arff==2.5.0"]
    assert s002["extra_requirements"] == ["nbconvert", "ipykernel"]
    assert len(s002["data"][0]["dataset_ids"]) == 30 and s002["data"][0]["writable"]
    assert s002["open_items"]  # the OpenML listing request needs network: owner decision
    assert ENTRIES["paper_005"]["python_version"] == "3.8"
    assert s005["build"]["from_repo"] and s005["build"]["build_requirements"] == ["pybind11==2.6.2"]
    assert "pandas==1.2.4" in s005["constraints"] and s005["constraints_source"]
    assert s006["build"]["sdists"] == ["openml==0.11.0", "liac-arff==2.5.0"] and s006["data"][0]["writable"]
    for sdist in s002["build"]["sdists"] + s006["build"]["sdists"]:
        parse_pin(sdist)


def test_sandbox_options_carry_the_new_fields(tmp_path):
    entry = ENTRIES["paper_006"]
    marker = tmp_path / "paper_006" / "openml_1461" / ".complete"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}")
    opts = sandbox_options(entry, tmp_path)
    assert opts["writable_data"] == ["/workspace/home/.openml/cache"]
    assert opts["build"]["sdists"] and opts["constraints"] == []
    SandboxConfig(python_version="3.8", data_mounts=opts["data_mounts"], writable_data=opts["writable_data"])


def test_bundle_passes_extras_constraints_and_built_wheels(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("python-dateutil==2.8.1\npandas\n")
    built = tmp_path / "built"
    built.mkdir()
    (built / "fastsk-0.0.2-cp38-cp38-linux_x86_64.whl").write_text("w")
    stager = RepoStager(staging_root=tmp_path / "staging")
    staged = StagedRepo(paper_id="p", source=str(repo), staged_path=repo, commit_hash="x",
                        manifest=stager.analyze_dependencies(repo), built_dir=built)
    seen = []
    monkeypatch.setattr(stager_module.subprocess, "run",
                        lambda cmd, **k: seen.append(cmd) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    report = stager.bundle_dependencies(staged, python_version="3.8", extra_requirements=["fastsk==0.0.2"],
                                        constraints=["pandas==1.2.4"])
    cmd = seen[0]
    assert cmd[-1] == "fastsk==0.0.2" and "-c" in cmd and "--find-links" in cmd and "linux_x86_64" in cmd
    assert (tmp_path / "staging" / "p_constraints.txt").read_text() == "pandas==1.2.4\n"
    assert (tmp_path / "staging" / "p_packages" / "fastsk-0.0.2-cp38-cp38-linux_x86_64.whl").exists()
    assert report["built_wheels"] == ["fastsk-0.0.2-cp38-cp38-linux_x86_64.whl"]
    assert report["constraints"] == ["pandas==1.2.4"]


def test_bundling_in_docker_runs_pip_in_the_target_image(tmp_path, monkeypatch):
    """#215: pip must evaluate environment markers for the sandbox's Linux and Python, not the host's."""
    stager = RepoStager(staging_root=tmp_path / "staging", bundle_in_docker=True)
    bundle = stager.staging_root / "p_packages"
    req = stager.staging_root / "p" / "requirements.txt"
    cons = stager.staging_root / "p_constraints.txt"
    host = stager._pip_download_command(bundle, "3.8") + ["-c", str(cons), "-r", str(req), "--find-links",
                                                          str(stager.staging_root / "p_built"), "torch>=1.4.0"]
    cmd = stager._docker_pip_command(host)
    assert cmd[:3] == ["docker", "run", "--rm"] and "--entrypoint" in cmd
    assert cmd[cmd.index("--entrypoint") + 1:cmd.index("--entrypoint") + 6] == ["python", "repro-radar-sandbox:py3.8", "-m", "pip", "download"]
    tail = cmd[cmd.index("download") + 1:]
    assert tail == ["-d", "/staging/p_packages", "--only-binary=:all:", "-c", "/staging/p_constraints.txt",
                    "-r", "/staging/p/requirements.txt", "--find-links", "/staging/p_built", "torch>=1.4.0"]
    for dropped in ("--platform", "--python-version", "--implementation", "manylinux2014_x86_64", "cp"):
        assert dropped not in cmd
    assert f"{stager.staging_root}:/staging" in cmd and "no-new-privileges:true" in cmd
    assert cmd[cmd.index("--user") + 1] == "1000:1000"
    assert "--network" not in cmd  # the network is on for this one step (wheels only)


def test_bundling_in_docker_refuses_paths_outside_the_staging_directory(tmp_path):
    stager = RepoStager(staging_root=tmp_path / "staging", bundle_in_docker=True)
    with pytest.raises(ValueError, match="outside the staging directory"):
        stager._docker_pip_command(stager._pip_download_command(tmp_path / "elsewhere", "3.11"))


def test_host_bundling_stays_the_default(tmp_path, monkeypatch):
    stager = RepoStager(staging_root=tmp_path / "staging")
    seen = []
    monkeypatch.setattr(stager_module.subprocess, "run", lambda cmd, **k: seen.append(cmd) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    stager._run_pip(stager._pip_download_command(tmp_path, "3.8"), 10)
    assert seen[0][1:4] == ["-m", "pip", "download"] and "--platform" in seen[0]


def test_two_writable_copies_under_one_top_level_directory_share_one_mount(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        d.mkdir()
        (d / "f.txt").write_text(d.name)
    runner = DockerSandboxRunner(SandboxConfig(
        data_mounts={"/workspace/home/.x/one": str(a), "/workspace/home/.x/two": str(b)},
        writable_data=["/workspace/home/.x/one", "/workspace/home/.x/two"]))
    runner._run_data_hosts = runner._writable_data_copies(tmp_path / "out")
    cmd = runner.build_docker_command(tmp_path / "repo", tmp_path / "out", ["x"])
    assert sum(arg.endswith(":/workspace/home/.x:rw") for arg in cmd) == 1
    overlay = tmp_path / "out" / "home_mounts" / ".x"
    assert (overlay / "one" / "f.txt").read_text() == "a" and (overlay / "two" / "f.txt").read_text() == "b"
