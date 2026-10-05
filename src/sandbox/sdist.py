"""Download source distributions without running them (#193).

`pip download` of an sdist prepares its metadata, which runs the package's build code on the host. The build phase
needs the sdist files only, so they are fetched from the PyPI JSON API and checked against PyPI's SHA-256 digest;
nothing in them runs before the build phase, inside the sandbox.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

PYPI_JSON = "https://pypi.org/pypi/{name}/{version}/json"


def parse_pin(requirement: str) -> tuple[str, str]:
    """`name==version` -> (name, version); other forms are refused, because the sdist must be exact."""
    name, sep, version = requirement.partition("==")
    if not sep or not name.strip() or not version.strip() or any(c in version for c in "<>=!~,;* "):
        raise ValueError(f"an sdist to build must be pinned as name==version: {requirement!r}")
    return name.strip(), version.strip()


def sdist_info(name: str, version: str, opener=urllib.request.urlopen) -> dict[str, str]:
    """URL, file name, and SHA-256 of the release's sdist on PyPI."""
    with opener(PYPI_JSON.format(name=name, version=version), timeout=60) as response:
        data = json.load(response)
    sdists = [u for u in data.get("urls", []) if u.get("packagetype") == "sdist"]
    if not sdists:
        raise ValueError(f"{name}=={version} has no sdist on PyPI")
    url = sdists[0]
    return {"url": url["url"], "filename": url["filename"], "sha256": url["digests"]["sha256"]}


def download_sdist(requirement: str, dest_dir: Path, opener=urllib.request.urlopen) -> Path:
    """Download the pinned sdist into dest_dir and verify its SHA-256; returns the file path."""
    name, version = parse_pin(requirement)
    info = sdist_info(name, version, opener)
    if "/" in info["filename"] or "\\" in info["filename"]:
        raise ValueError(f"unexpected sdist file name: {info['filename']!r}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / info["filename"]
    with opener(info["url"], timeout=120) as response:
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != info["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {info['filename']}: {digest} != {info['sha256']}")
    target.write_bytes(payload)
    return target
