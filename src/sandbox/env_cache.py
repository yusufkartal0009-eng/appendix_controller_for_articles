"""Cache of the installed environment, one entry per locked package list (#380).

The install phase (a network-isolated container, binary wheels only, no package code runs) turns the bundled wheels into
a directory that the run phase mounts read-only at /workspace/deps. For a paper that is run again with the same locked
packages, that directory is the same, so the second run can skip the install container and mount the stored copy.

What goes into the key (everything that decides the content of the directory):

- the ID of the sandbox image (a rebuilt image, a new Python or pip, gives a new key),
- the name and SHA-256 of every file in the bundle (the locked package list: exact wheels, not requirement lines),
- the name and SHA-256 of every ``*requirements*.txt`` in the repository root (what the install phase reads),
- the extra requirements of the run setup, and whether the install used the requirement files or every bundled wheel.

Safety: an entry holds only the output of an install phase that ended INSTALLED, so no paper code ever wrote to it. Before
each use the SHA-256 digest of the whole tree is compared with the digest taken when the entry was stored; a mismatch deletes
the entry and the install phase runs. The run phase still mounts the directory read-only, as before, so paper code can
neither change a cached entry nor add executables to it. The cache is a host directory that is not mounted writable into any
container. See ``docs/DECISIONS.md`` (D-010).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CHUNK_BYTES = 1024 * 1024
ENTRY_FILE = "entry.json"
DEPS_DIR = "deps"
# Files of the install phase that the report reads; they are stored beside the deps directory.
INSTALL_FILES = ("install.log", "installed_packages.json", "install_meta.json")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_digest(root: Path) -> tuple[str, int, int]:
    """SHA-256 over the relative paths, sizes, and contents of a tree (a symlink counts by its target text).

    Returns the digest, the number of files, and their total size in bytes.
    """
    digest = hashlib.sha256()
    files = 0
    total = 0
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            digest.update(f"L {relative} {os.readlink(path)}\n".encode())
        elif path.is_file():
            size = path.stat().st_size
            digest.update(f"F {relative} {size} {file_sha256(path)}\n".encode())
            files += 1
            total += size
        else:
            digest.update(f"D {relative}\n".encode())
    return digest.hexdigest(), files, total


def image_id(image: str) -> str | None:
    """The ID (content digest) of a local image, or None if Docker does not know it."""
    try:
        out = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", image], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    value = out.stdout.strip()
    return value if out.returncode == 0 and value else None


def environment_key(image: str, packages_dir: Path, repo_dir: Path, extra_requirements: list[str]) -> tuple[str, dict[str, Any]]:
    """The cache key of an install phase and the inputs it was made from (for the record)."""
    bundle = {p.relative_to(packages_dir).as_posix(): file_sha256(p) for p in sorted(packages_dir.rglob("*")) if p.is_file()}
    requirement_files = {p.name: file_sha256(p) for p in sorted(repo_dir.glob("*requirements*.txt")) if p.is_file()}
    inputs = {
        "image": image,
        "image_id": image_id(image),
        "bundle": bundle,
        "requirement_files": requirement_files,
        # without requirement files the entrypoint installs every bundled wheel without dependency resolution
        "mode": "requirement_files" if requirement_files else "all_bundled_wheels",
        "extra_requirements": sorted(extra_requirements),
    }
    if not inputs["image_id"]:
        raise LookupError(f"image {image} is not known to Docker, so its ID cannot be part of the key")
    key = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    return key, inputs


class EnvironmentCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def entry_dir(self, key: str) -> Path:
        return self.root / key[:32]

    def lookup(self, key: str) -> tuple[Path | None, dict[str, Any]]:
        """Return the entry directory if it exists and its digest still holds; else None with the reason and timings."""
        info: dict[str, Any] = {"verify_seconds": 0.0}
        entry = self.entry_dir(key)
        meta_path = entry / ENTRY_FILE
        if not meta_path.is_file():
            info["reason"] = "no entry for this key"
            return None, info
        start = time.time()
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            digest, files, total = tree_digest(entry / DEPS_DIR)
        except (OSError, ValueError) as exc:
            shutil.rmtree(entry, ignore_errors=True)
            info.update(reason=f"entry unreadable ({type(exc).__name__}); deleted", verify_seconds=round(time.time() - start, 3))
            return None, info
        info["verify_seconds"] = round(time.time() - start, 3)
        if meta.get("key") != key or meta.get("deps_sha256") != digest:
            shutil.rmtree(entry, ignore_errors=True)
            info["reason"] = "digest of the stored environment does not match; entry deleted"
            return None, info
        info.update(reason="hit", files=files, bytes=total, stored=meta)
        return entry, info

    def store(self, key: str, inputs: dict[str, Any], deps_dir: Path, output_dir: Path) -> dict[str, Any]:
        """Store a finished install phase (the caller has checked that it ended INSTALLED). Atomic: a rename at the end."""
        start = time.time()
        self.root.mkdir(parents=True, exist_ok=True)
        temp = self.root / f".tmp-{uuid.uuid4().hex[:12]}"
        shutil.copytree(deps_dir, temp / DEPS_DIR, symlinks=True)
        for name in INSTALL_FILES:
            if (output_dir / name).is_file():
                shutil.copy2(output_dir / name, temp / name)
        digest, files, total = tree_digest(temp / DEPS_DIR)
        meta = {"key": key, "created_at": datetime.now(UTC).isoformat(timespec="seconds"), "deps_sha256": digest,
                "files": files, "bytes": total, "inputs": {k: v for k, v in inputs.items() if k != "bundle"},
                "bundle_files": len(inputs["bundle"])}
        (temp / ENTRY_FILE).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        final = self.entry_dir(key)
        if final.exists():
            shutil.rmtree(final)
        temp.rename(final)
        return {"store_seconds": round(time.time() - start, 3), "files": files, "bytes": total}
