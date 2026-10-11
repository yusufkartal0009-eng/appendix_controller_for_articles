"""SHA-256 manifests of run directories: proof that outputs did not change, and a summary of what two runs share (#29).

A run leaves a directory of files (logs, run metadata, and whatever the paper wrote: predictions, metrics, model
weights). `build_manifest` records the SHA-256 of every file in it, so that later `verify_manifest` can show that
nothing was edited, added, or removed, and `compare_manifests` can show which files two runs of the same paper
produced identically.

Two hashes are kept per manifest, because they answer different questions:

- `manifest_sha256`: every file, logs and metadata included. Changes if anything in the directory changes (integrity).
- `outputs_sha256`: only the files the paper wrote. Logs and the sandbox's own metadata hold timings and paths that differ from run to run,
  so they are left out; equal `outputs_sha256` in two runs means the paper's own files are byte for byte the same
  (reproducibility). `None` when the run wrote no such file.

Both are the SHA-256 of the sorted lines `<file sha256>  <relative path>` (the `sha256sum` format), so they can be
checked with ordinary tools. Symbolic links are never followed, and files that cannot be read are listed under
`skipped` with the reason: a run can create both in its output folder (docs/SECURITY_AUDIT.md).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.models import RunORM

MANIFEST_NAME = "artifact_manifest.json"
ALGORITHM = "sha256"
CHUNK_BYTES = 1 << 20

# Files the sandbox and the pilot tools write about a run (timings, paths, commits). They are hashed, but are not
# part of `outputs_sha256`.
METADATA_NAMES = frozenset({
    "execution_meta.json", "run_report.json", "pilot_record.json", "install_meta.json", "build_meta.json",
    "environment.txt",
})


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(relative_path: str) -> str:
    """'log', 'metadata' (written by the sandbox), or 'artifact' (written by the paper's code)."""
    name = relative_path.rsplit("/", 1)[-1]
    if name.endswith(".log"):
        return "log"
    if name in METADATA_NAMES:
        return "metadata"
    return "artifact"


def combined_hash(files: list[dict[str, Any]]) -> str:
    lines = "".join(f"{f['sha256']}  {f['path']}\n" for f in sorted(files, key=lambda f: f["path"]))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def build_manifest(run_dir: str | Path) -> dict[str, Any]:
    """The manifest of every file under `run_dir`, except an earlier manifest file."""
    root = Path(run_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")
    files: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        base = Path(current)
        for name in list(dirnames):
            if (base / name).is_symlink():
                dirnames.remove(name)
                skipped.append({"path": (base / name).relative_to(root).as_posix(), "reason": "symbolic link (not followed)"})
        for name in sorted(filenames):
            path = base / name
            relative = path.relative_to(root).as_posix()
            if relative == MANIFEST_NAME:
                continue
            if path.is_symlink():
                skipped.append({"path": relative, "reason": "symbolic link (not followed)"})
                continue
            try:
                size = path.stat().st_size
                digest = hash_file(path)
            except OSError as exc:
                skipped.append({"path": relative, "reason": f"unreadable: {type(exc).__name__} (errno {exc.errno})"})
                continue
            files.append({"path": relative, "bytes": size, "sha256": digest, "category": classify(relative)})
    files.sort(key=lambda f: f["path"])
    artifacts = [f for f in files if f["category"] == "artifact"]
    return {
        "algorithm": ALGORITHM,
        "generator": "src/artifact_hash.py",
        "file_count": len(files),
        "total_bytes": sum(f["bytes"] for f in files),
        "manifest_sha256": combined_hash(files),
        "outputs_sha256": combined_hash(artifacts) if artifacts else None,
        "files": files,
        "skipped": sorted(skipped, key=lambda s: s["path"]),
    }


def write_manifest(run_dir: str | Path, manifest: dict[str, Any]) -> Path:
    path = Path(run_dir) / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return path


def load_manifest(run_dir: str | Path) -> dict[str, Any]:
    return json.loads((Path(run_dir) / MANIFEST_NAME).read_text(encoding="utf-8"))


def verify_manifest(run_dir: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Compare the directory as it is now with a stored manifest: modified, missing, and added files."""
    stored = {f["path"]: f["sha256"] for f in manifest["files"]}
    current_manifest = build_manifest(run_dir)
    current = {f["path"]: f["sha256"] for f in current_manifest["files"]}
    modified = sorted(p for p in stored if p in current and stored[p] != current[p])
    missing = sorted(p for p in stored if p not in current)
    added = sorted(p for p in current if p not in stored)
    return {"ok": not (modified or missing or added), "modified": modified, "missing": missing, "added": added,
            "files_checked": len(stored)}


def compare_manifests(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Which files two runs produced identically. Logs and sandbox metadata are counted apart from the paper's files."""
    files_a = {f["path"]: f for f in a["files"]}
    files_b = {f["path"]: f for f in b["files"]}
    result: dict[str, Any] = {}
    for category in ("artifact", "log", "metadata"):
        names = sorted(p for p in {*files_a, *files_b}
                       if (files_a.get(p) or files_b.get(p))["category"] == category)
        same = [p for p in names if p in files_a and p in files_b and files_a[p]["sha256"] == files_b[p]["sha256"]]
        differ = [p for p in names if p in files_a and p in files_b and files_a[p]["sha256"] != files_b[p]["sha256"]]
        result[category] = {
            "files": len(names), "identical": len(same), "differing": differ,
            "only_in_first": [p for p in names if p not in files_b], "only_in_second": [p for p in names if p not in files_a],
        }
    artifacts = result["artifact"]
    result["same_outputs_hash"] = a["outputs_sha256"] is not None and a["outputs_sha256"] == b["outputs_sha256"]
    # "reproduced" needs at least one file the paper wrote, and all of them identical in both runs.
    result["outputs_reproduced"] = bool(artifacts["files"]) and artifacts["identical"] == artifacts["files"]
    return result


def summarize(comparison: dict[str, Any]) -> str:
    """One line per file category, for a report or a pull request."""
    lines = []
    for category, label in (("artifact", "paper output files"), ("log", "log files"), ("metadata", "sandbox metadata files")):
        c = comparison[category]
        lines.append(f"{label}: {c['identical']} of {c['files']} identical"
                     + (f"; differing: {', '.join(c['differing'])}" if c["differing"] else "")
                     + (f"; only in the first run: {', '.join(c['only_in_first'])}" if c["only_in_first"] else "")
                     + (f"; only in the second run: {', '.join(c['only_in_second'])}" if c["only_in_second"] else ""))
    lines.append("paper output files reproduced byte for byte: " + ("yes" if comparison["outputs_reproduced"] else "no"))
    return "\n".join(lines)


def store_hashes(session: Session, run_id: str, manifest: dict[str, Any]) -> RunORM:
    """Save the manifest's two hashes in the run's row. Raises KeyError when the run is not in the database."""
    run = session.get(RunORM, run_id)
    if run is None:
        raise KeyError(f"no run {run_id!r} in the runs table")
    run.artifact_manifest_sha256 = manifest["manifest_sha256"]
    run.outputs_sha256 = manifest["outputs_sha256"]
    session.commit()
    return run
