"""Name dependency conflicts from pip's resolver output (#160).

When pip cannot resolve a set of requirements it prints, for example:

    ERROR: Cannot install -r requirements.txt (line 4) and python-dateutil==2.8.1 because these package versions
    have conflicting dependencies.

    The conflict is caused by:
        The user requested python-dateutil==2.8.1
        pandas 3.0.6 depends on python-dateutil>=2.8.2

`parse_dependency_conflicts` turns every such block into a record, so the bundle and run reports can name the
conflicting packages instead of only reporting PARTIAL or FAILED.
"""

from __future__ import annotations

import re
from pathlib import Path

_CANNOT = re.compile(r"ERROR: Cannot install (?P<what>.+?) because these package versions have conflicting dependencies\.")


def _split_requirements(what: str) -> list[str]:
    """'a, b and c' -> ['a', 'b', 'c'] (requirement strings may contain commas inside parentheses)."""
    parts = re.split(r",\s+(?![^()]*\))|\s+and\s+(?![^()]*\))", what)
    return [p.strip() for p in parts if p.strip()]


def parse_dependency_conflicts(text: str) -> list[dict[str, list[str]]]:
    """One record per conflict block: {"cannot_install": [...], "caused_by": [...]}. Empty if there is none."""
    if not text:
        return []
    lines = text.splitlines()
    conflicts: list[dict[str, list[str]]] = []
    for i, line in enumerate(lines):
        match = _CANNOT.search(line)
        if not match:
            continue
        caused_by: list[str] = []
        for j in range(i + 1, len(lines)):
            if lines[j].strip() == "The conflict is caused by:":
                for cause in lines[j + 1:]:
                    if not cause.strip():
                        break
                    caused_by.append(cause.strip())
                break
            if _CANNOT.search(lines[j]):
                break
        conflicts.append({"cannot_install": _split_requirements(match.group("what")), "caused_by": caused_by})
    return conflicts


_REQ_LINE = re.compile(r"^-r (?P<path>\S+) \(line (?P<line>\d+)\)$")


def name_requirement_lines(conflicts: list[dict[str, list[str]]], repo_dir: str | Path) -> list[dict[str, list[str]]]:
    """Replace "-r <file> (line N)" by that line's text, read from the staged repository, so the report names it."""
    for conflict in conflicts:
        named = []
        for item in conflict["cannot_install"]:
            m = _REQ_LINE.match(item)
            path = Path(repo_dir) / Path(m.group("path")).name if m else None
            if m and path.is_file():
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
                n = int(m.group("line"))
                if 1 <= n <= len(lines) and lines[n - 1].strip():
                    item = f"{lines[n - 1].strip()} ({path.name} line {n})"
            named.append(item)
        conflict["cannot_install"] = named
    return conflicts
