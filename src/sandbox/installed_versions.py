"""Compare what a repository asks for with what the install phase actually installed (#161).

The install phase writes `installed_packages.json` (`pip list --path /workspace/deps --format=json`). For every
requirement of the repository (its requirement files, or the pins converted from its conda environment file), the
run report shows the requested specifier, the installed version, and whether the installed version satisfies the
request. A satisfied but loose request (`torch>=1.4.0` installed as `2.7.1`) is the drift this makes visible.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version


def read_installed(path: Path) -> list[dict[str, str]]:
    """The installed packages as written by the install phase; [] if the file is missing or unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [{"name": p["name"], "version": p["version"]} for p in data if isinstance(p, dict) and "name" in p]


def requested_vs_installed(requirements: list[str], installed: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_name = {canonicalize_name(p["name"]): p["version"] for p in installed}
    rows: list[dict[str, Any]] = []
    for line in requirements:
        line = line.split(" #")[0].strip()
        if not line or line.startswith(("#", "-")):
            continue
        try:
            req = Requirement(line)
        except InvalidRequirement:
            rows.append({"requirement": line, "name": None, "installed": None, "satisfied": None,
                         "note": "not a parseable requirement"})
            continue
        version = by_name.get(canonicalize_name(req.name))
        satisfied: bool | None = None
        if version is not None:
            try:
                satisfied = (not req.specifier) or req.specifier.contains(Version(version), prereleases=True)
            except InvalidVersion:
                satisfied = None
        rows.append({"requirement": line, "name": req.name, "requested": str(req.specifier) or "any",
                     "installed": version, "satisfied": satisfied,
                     "pinned": any(s.operator in ("==", "===") for s in req.specifier)})
    return rows
