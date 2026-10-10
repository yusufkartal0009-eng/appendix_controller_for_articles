"""Conda environment files converted to pinned pip requirements and bundled offline (#159)."""

import subprocess

import pytest

from src.sandbox.conda_env import (
    _parse_conda_spec,
    convert_env_file,
    find_conda_env_files,
)
from src.sandbox.stager import RepoStager

ENV = """name: demo
channels: [conda-forge]
dependencies:
  - _libgcc_mutex=0.1=conda_forge
  - python=3.8.10=h49503c6_1_cpython
  - numpy=1.20.2=py38h2d18471_0
  - pytorch=1.8.1=py3.8_cuda11.1_cudnn8.0.5_0
  - py-xgboost=1.4.0=py38h06a4308_0
  - xgboost=1.4.0
  - cudatoolkit=11.1.1=h6406543_8
  - libgcc-ng=9.3.0
  - tqdm
  - pip:
    - delu==0.0.15
    - --extra-index-url https://example.org
"""


@pytest.mark.parametrize("spec, parsed", [
    ("numpy=1.20.2=py38h2d18471_0", ("numpy", "1.20.2")),
    ("conda-forge::pandas=1.5.3", ("pandas", "1.5.3")),
    ("scipy==1.6.2", ("scipy", "1.6.2")),
    ("tqdm", ("tqdm", None)),
])
def test_parse_conda_spec(spec, parsed):
    assert _parse_conda_spec(spec) == parsed


def test_conversion_maps_pins_skips_system_packages_and_reads_python(tmp_path):
    (tmp_path / "saint_environment.yml").write_text(ENV)
    result = convert_env_file(tmp_path / "saint_environment.yml")
    assert result.python_version == "3.8"
    assert result.requirements == ["numpy==1.20.2", "torch==1.8.1", "xgboost==1.4.0", "delu==0.0.15"]
    skipped = {s["package"].split("=")[0]: s["reason"] for s in result.skipped}
    assert {"_libgcc_mutex", "cudatoolkit", "libgcc-ng", "tqdm", "--extra-index-url https://example.org"} == set(skipped)
    assert "no exact version" in skipped["tqdm"]


def test_env_files_are_found_by_name(tmp_path):
    for name in ("environment.yaml", "saint_environment.yml", "requirements.txt", "env.yml"):
        (tmp_path / name).write_text("dependencies: []\n")
    assert find_conda_env_files(tmp_path) == ["environment.yaml", "saint_environment.yml"]


def test_conda_only_repository_is_bundled_one_requirement_at_a_time(tmp_path, monkeypatch):
    source = tmp_path / "repo"
    source.mkdir()
    (source / "train.py").write_text("print(1)\n")
    (source / "environment.yml").write_text(ENV)
    stager = RepoStager(staging_root=tmp_path / "staging")
    staged = stager.stage_repository(paper_id="conda_demo", source=str(source))
    assert staged.manifest.conda_env_files == ["environment.yml"] and staged.manifest.has_conda_env

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        missing = cmd[-1] == "torch==1.8.1"  # pretend this one has no wheel
        return subprocess.CompletedProcess(cmd, 1 if missing else 0, "", "ERROR: No matching distribution" if missing else "")

    monkeypatch.setattr("src.sandbox.stager.subprocess.run", fake_run)
    result = stager.bundle_dependencies(staged, python_version="3.8")
    assert all("--no-deps" in c and c[c.index("--python-version") + 1] == "3.8" for c in calls)
    assert [c[-1] for c in calls] == ["numpy==1.20.2", "torch==1.8.1", "xgboost==1.4.0", "delu==0.0.15"]
    assert result["source"] == "conda_env" and result["status"] == "PARTIAL"
    assert result["env_python_versions"] == ["3.8"]
    assert result["conda_only"] == [{"requirement": "torch==1.8.1", "reason": "ERROR: No matching distribution"}]
    assert result["downloaded"] == ["numpy==1.20.2", "xgboost==1.4.0", "delu==0.0.15"]


def test_requirements_files_still_take_precedence(tmp_path, monkeypatch):
    source = tmp_path / "repo"
    source.mkdir()
    (source / "main.py").write_text("print(1)\n")
    (source / "environment.yml").write_text(ENV)
    (source / "requirements.txt").write_text("toolz==0.12.1\n")
    stager = RepoStager(staging_root=tmp_path / "staging")
    staged = stager.stage_repository(paper_id="both", source=str(source))
    monkeypatch.setattr("src.sandbox.stager.subprocess.run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "", ""))
    assert "source" not in stager.bundle_dependencies(staged)


def test_setuptools_wheel_and_certifi_are_converted_but_pip_and_python_are_not(tmp_path):
    """#225: ipython needs setuptools and requests needs certifi; the install phase is offline with an empty target."""
    env = tmp_path / "environment.yml"
    env.write_text(
        "name: demo\ndependencies:\n  - python=3.8.10=h49503c6_1_cpython\n  - pip=21.1.3=pyhd8ed1ab_0\n"
        "  - setuptools=49.6.0=py38h578d9bd_3\n  - wheel=0.36.2=pyhd3deb0d_0\n  - certifi=2021.5.30=py38h578d9bd_0\n"
        "  - openssl=1.1.1k=h7f98852_0\n  - ca-certificates=2021.5.30=ha878542_0\n", encoding="utf-8")
    result = convert_env_file(env)
    assert result.requirements == ["setuptools==49.6.0", "wheel==0.36.2", "certifi==2021.5.30"]
    skipped = {s["package"].split("=")[0] for s in result.skipped}
    assert {"pip", "openssl", "ca-certificates"} <= skipped
    assert result.python_version == "3.8"  # python is not pip-installed; its minor version selects the sandbox image
