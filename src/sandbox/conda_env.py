"""Convert a conda environment file into pinned pip requirements (#159).

Repro Radar does not run conda. A conda environment file pins every package of an environment, so its Python
packages can be fetched as binary wheels with `pip download --no-deps` and installed offline like any other bundle
(src/sandbox/stager.py). Packages without a PyPI wheel (system libraries, CUDA, conda-only builds) are reported, not
installed. The conversion is lossy by design: the report says what was left out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# conda package name -> PyPI name, where they differ.
CONDA_TO_PIP = {
    "pytorch": "torch",
    "py-xgboost": "xgboost",
    "py-lightgbm": "lightgbm",
    "matplotlib-base": "matplotlib",
    "msgpack-python": "msgpack",
    "pytables": "tables",
    "faiss-cpu": "faiss-cpu",
    "tensorflow-base": "tensorflow",
}

# Conda packages that are never pip-installable (or must not be installed in the CPU sandbox). `setuptools`,
# `wheel`, and `certifi` are NOT skipped (#225): they are ordinary PyPI packages that other packages require
# (ipython needs setuptools, requests needs certifi), and the install phase is offline with an empty target.
_SKIP_EXACT = {"python", "pip", "cudatoolkit", "cudnn", "pytorch-cuda", "faiss-gpu", "mkl",
               "blas", "libblas", "libcblas", "liblapack", "ca-certificates", "openssl"}
_SKIP_PREFIXES = ("_", "lib", "cuda-", "nvidia-", "gcc", "gxx", "ld_impl", "xorg-", "font", "intel-openmp")


@dataclass
class CondaConversion:
    env_file: str
    python_version: str | None = None  # e.g. "3.9" from python=3.9.16
    requirements: list[str] = field(default_factory=list)  # pip specifiers, name==version
    skipped: list[dict[str, str]] = field(default_factory=list)  # {"package", "reason"}

    def to_dict(self) -> dict[str, Any]:
        return {"env_file": self.env_file, "python_version": self.python_version,
                "requirements": self.requirements, "skipped": self.skipped}


def find_conda_env_files(repo_dir: Path) -> list[str]:
    """Conda environment files in the repository root (environment.yml, saint_environment.yml, ...)."""
    names = {p.name for pattern in ("*environment*.yml", "*environment*.yaml") for p in repo_dir.glob(pattern)}
    return sorted(names)


def _parse_conda_spec(spec: str) -> tuple[str, str | None]:
    """'numpy=1.20.2=py38h2d18471_0' -> ('numpy', '1.20.2'); 'numpy' -> ('numpy', None)."""
    spec = spec.strip()
    channel_free = spec.split("::")[-1]
    m = re.match(r"^([A-Za-z0-9_.\-]+)\s*(?:==?\s*([^=\s]+))?", channel_free)
    if not m:
        return channel_free, None
    return m.group(1).lower(), m.group(2)


def convert_env_file(path: Path) -> CondaConversion:
    import yaml  # imported here: the sandbox code path stays importable without PyYAML

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    result = CondaConversion(env_file=path.name)
    for dep in data.get("dependencies") or []:
        if isinstance(dep, dict):
            for pip_req in dep.get("pip") or []:
                pip_req = str(pip_req).strip()
                if pip_req.startswith("-"):
                    result.skipped.append({"package": pip_req, "reason": "pip option, not a package"})
                else:
                    result.requirements.append(pip_req)
            continue
        name, version = _parse_conda_spec(str(dep))
        if name == "python":
            if version:
                result.python_version = ".".join(version.split(".")[:2])
            continue
        if name in _SKIP_EXACT or name.startswith(_SKIP_PREFIXES):
            result.skipped.append({"package": str(dep), "reason": "system, CUDA, or packaging library; not pip-installed"})
            continue
        if version is None or "*" in version:
            result.skipped.append({"package": str(dep), "reason": "no exact version pinned"})
            continue
        result.requirements.append(f"{CONDA_TO_PIP.get(name, name)}=={version}")
    # Two conda names can map to one PyPI package (py-xgboost and xgboost): keep the first.
    seen: set[str] = set()
    unique = []
    for req in result.requirements:
        key = re.split(r"[=<>!~ ]", req, maxsplit=1)[0].lower()
        if key not in seen:
            seen.add(key)
            unique.append(req)
    result.requirements = unique
    return result
