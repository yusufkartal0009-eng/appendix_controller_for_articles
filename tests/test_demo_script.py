"""The demo script names only files that exist and keeps its honest limits in the text (#444)."""

import re

from src.config import PROJECT_ROOT

DOC = (PROJECT_ROOT / "docs" / "DEMO_SCRIPT.md").read_text(encoding="utf-8")


def test_every_linked_screenshot_exists():
    links = re.findall(r"\]\((evidence/demo/[^)]+)\)", DOC)
    assert len(links) == 2
    for link in links:
        assert (PROJECT_ROOT / "docs" / link).is_file(), link


def test_every_step_says_what_it_shows_and_does_not_show():
    steps = re.split(r"^## Step \d+\.", DOC, flags=re.MULTILINE)[1:]
    assert len(steps) == 9
    for step in steps:
        assert "- Shows:" in step and "- Does **not** show:" in step


def test_the_limits_and_the_hand_made_warning_are_in_the_text():
    for needle in ("1 of 6", "0 of 14", "3.0 % to 56.4 %", "0 of 65", "hand-made claims, not an error of a real paper",
                   "have not been measured", "No candidate\n  passed"):
        assert needle in DOC, needle
    assert "Users" not in DOC and "@" not in re.sub(r"`[^`]*`", "", DOC)
