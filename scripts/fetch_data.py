#!/usr/bin/env python3
"""Fetch the datasets of a paper's run setup into the host data cache (#166).

The sandbox has no network, so data that a paper downloads by hand (README) or at run time is fetched here, on
the host, and mounted read-only into the run. Each item lands in `<cache>/<paper_id>/<name>/`; a `.complete`
marker is written only after the download matched its expected size and was unpacked.

    python scripts/fetch_data.py paper_003 --dry-run     # list the items and their sizes, download nothing
    python scripts/fetch_data.py paper_003

`openml` items need the `openml` package on the host, in the version the paper uses (the cache layout differs
between versions); it is not a project dependency.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import DATA_CACHE_DIR, SEED_PAPERS_PATH
from src.sandbox.run_setup import data_dir, is_cached, run_setup_of


def download(url: str, dest: Path, expected_bytes: int | None) -> int:
    with urllib.request.urlopen(url, timeout=60) as response, dest.open("wb") as out:
        shutil.copyfileobj(response, out, length=1 << 20)
    size = dest.stat().st_size
    if expected_bytes is not None and size != expected_bytes:
        raise ValueError(f"downloaded {size} bytes, expected {expected_bytes}: {url}")
    return size


def unpack(archive: Path, fmt: str, target: Path) -> None:
    if fmt == "tar":
        with tarfile.open(archive) as tar:
            tar.extractall(target, filter="data")  # refuses absolute paths, '..', and device files
    elif fmt == "zip":
        with zipfile.ZipFile(archive) as zf:
            for name in zf.namelist():
                if name.startswith("/") or ".." in Path(name).parts:
                    raise ValueError(f"unsafe path in zip: {name}")
            zf.extractall(target)
    else:
        shutil.copy2(archive, target / archive.name)


def fetch_item(paper_id: str, item: dict[str, Any], cache_root: Path) -> dict[str, Any]:
    out = data_dir(cache_root, paper_id, item)
    if is_cached(cache_root, paper_id, item):
        return {"name": item["name"], "status": "CACHED", "path": str(out)}
    if out.exists():
        shutil.rmtree(out)  # an earlier attempt that did not complete
    out.mkdir(parents=True)
    if item["kind"] == "url":
        archive = out.parent / f".{item['name']}.download"
        try:
            size = download(item["url"], archive, item.get("bytes"))
            unpack(archive, item["unpack"], out)
        finally:
            archive.unlink(missing_ok=True)
        result = {"name": item["name"], "status": "FETCHED", "bytes": size, "path": str(out)}
    else:
        import openml  # host-only; see the module docstring

        openml.config.cache_directory = str(out)
        openml.datasets.get_dataset(item["dataset_id"], download_data=True)
        result = {"name": item["name"], "status": "FETCHED", "openml_version": openml.__version__, "path": str(out)}
    (out / ".complete").write_text(json.dumps(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a paper's datasets into the host data cache.")
    parser.add_argument("paper_id")
    parser.add_argument("--cache", default=str(DATA_CACHE_DIR))
    parser.add_argument("--dry-run", action="store_true", help="List the items without downloading.")
    args = parser.parse_args(argv)
    entries = {e["paper_id"]: e for e in json.loads(SEED_PAPERS_PATH.read_text(encoding="utf-8"))}
    if args.paper_id not in entries:
        print(f"unknown paper: {args.paper_id}", file=sys.stderr)
        return 2
    items = run_setup_of(entries[args.paper_id]).get("data", [])
    if not items:
        print(f"{args.paper_id}: no data items")
        return 0
    status = 0
    for item in items:
        if args.dry_run:
            print(json.dumps({k: item.get(k) for k in ("name", "kind", "url", "dataset_id", "bytes", "target")}))
            continue
        try:
            print(json.dumps(fetch_item(args.paper_id, item, Path(args.cache))))
        except Exception as exc:  # noqa: BLE001 - reported per item; the other items are still fetched
            print(json.dumps({"name": item["name"], "status": "FAILED", "error": str(exc)}))
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
