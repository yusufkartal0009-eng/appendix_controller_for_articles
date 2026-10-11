#!/usr/bin/env python3
"""Fetch the datasets of a paper's run setup into the host data cache (#166).

The sandbox has no network, so data that a paper downloads by hand (README) or at run time is fetched here, on
the host, and mounted read-only into the run. Each item lands in `<cache>/<paper_id>/<name>/`; a `.complete`
marker is written only after the download matched its expected size and was unpacked.

    python scripts/fetch_data.py paper_003 --dry-run     # list the items and their sizes, download nothing
    python scripts/fetch_data.py paper_003

`openml` items are fetched over plain HTTP from the OpenML REST API, without the openml package (#193): for each
dataset its description, features, and qualities XML and its ARFF file (MD5-checked), laid out as openml-python
0.11 and 0.12 read their cache (`<cache>/org/openml/www/datasets/<id>/`). openml writes into its cache when it
loads a dataset, so these items are mounted as a writable per-run copy (`"writable": true`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import DATA_CACHE_DIR, SEED_PAPERS_PATH
from src.sandbox.run_setup import data_dir, is_cached, openml_ids, run_setup_of

OPENML_API = "https://www.openml.org/api/v1/xml"
OML = "{http://openml.org/openml}"


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


def require_tar_filters() -> None:
    """Stop with a clear message when this Python cannot extract tar archives safely (#252).

    `tarfile.extractall(filter=...)` exists from Python 3.11.4. On an older patch release it fails in the middle of a
    download with an AttributeError that does not say what is wrong.
    """
    if not hasattr(tarfile, "data_filter"):
        raise SystemExit(
            f"fetch_data.py needs Python 3.11.4 or newer (this is {sys.version.split()[0]}): older releases cannot "
            "extract tar archives safely. Install a newer Python and run it again."
        )


def fetch_openml_dataset(dataset_id: int, cache_dir: Path, api: str = OPENML_API) -> int:
    """Write one dataset into an openml-python cache layout; returns the bytes written."""
    did_dir = cache_dir / "org" / "openml" / "www" / "datasets" / str(dataset_id)
    did_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, path in (("description.xml", f"data/{dataset_id}"), ("features.xml", f"data/features/{dataset_id}"),
                       ("qualities.xml", f"data/qualities/{dataset_id}")):
        with urllib.request.urlopen(f"{api}/{path}", timeout=60) as response:
            payload = response.read()
        (did_dir / name).write_bytes(payload)
        total += len(payload)
    description = ElementTree.parse(did_dir / "description.xml").getroot()
    url = description.findtext(f"{OML}url")
    md5 = description.findtext(f"{OML}md5_checksum")
    if not url:
        raise ValueError(f"OpenML dataset {dataset_id}: no file URL in its description")
    arff = did_dir / "dataset.arff"
    total += download(url, arff, None)
    if md5 and hashlib.md5(arff.read_bytes()).hexdigest() != md5:  # OpenML publishes MD5 checksums
        raise ValueError(f"OpenML dataset {dataset_id}: MD5 mismatch")
    return total


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
        size = sum(fetch_openml_dataset(dataset_id, out) for dataset_id in openml_ids(item))
        result = {"name": item["name"], "status": "FETCHED", "bytes": size, "datasets": openml_ids(item),
                  "path": str(out)}
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
    if not args.dry_run:
        require_tar_filters()
    items = run_setup_of(entries[args.paper_id]).get("data", [])
    if not items:
        print(f"{args.paper_id}: no data items")
        return 0
    status = 0
    for item in items:
        if args.dry_run:
            print(json.dumps({k: item.get(k) for k in ("name", "kind", "url", "dataset_ids", "bytes", "target", "writable")}))
            continue
        try:
            print(json.dumps(fetch_item(args.paper_id, item, Path(args.cache))))
        except Exception as exc:  # noqa: BLE001 - reported per item; the other items are still fetched
            print(json.dumps({"name": item["name"], "status": "FAILED", "error": str(exc)}))
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
