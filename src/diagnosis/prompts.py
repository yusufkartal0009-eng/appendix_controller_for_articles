"""Prompt templates for the optional LLM step of the diagnosis (#31, docs/DIAGNOSIS.md), and the neutral-language check.

The templates are files in `docs/prompts/`: `system.md` and one task file per status. Nothing here calls a model.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.config import (
    STATUS_FAILED,
    STATUS_NEEDS_REVIEW,
    STATUS_PARTIALLY_VERIFIED,
    STATUS_VERIFIED,
)

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "prompts"
TASK_FILES = {
    STATUS_VERIFIED: "verified.md",
    STATUS_PARTIALLY_VERIFIED: "partially_verified.md",
    STATUS_NEEDS_REVIEW: "needs_review.md",
    STATUS_FAILED: "failed.md",
}
PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")
NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?")

# Words that describe the people or their intent instead of the run. A report and a model answer must not contain them.
LOADED_WORDS = (
    "fraud", "fraudulent", "fake", "faked", "lie", "lied", "lying", "dishonest", "misleading", "deceptive", "cheat",
    "cheating", "sloppy", "careless", "lazy", "incompetent", "bogus", "suspicious", "manipulated", "fabricated",
)


def load_template(name: str, prompts_dir: Path | None = None) -> str:
    return ((prompts_dir or PROMPTS_DIR) / name).read_text(encoding="utf-8")


def fill(template: str, values: dict[str, str]) -> str:
    """Replace every {{name}}; a placeholder without a value, or a value without a placeholder, is an error."""
    names = set(PLACEHOLDER_RE.findall(template))
    missing = sorted(names - set(values))
    if missing:
        raise ValueError(f"no value for the placeholders {missing}")
    return PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], template)


def numbers_in(text: str) -> list[str]:
    """The numbers of a text as written, in order of first appearance, without repeats."""
    seen: dict[str, None] = {}
    for match in NUMBER_RE.finditer(text):
        seen.setdefault(match.group(0), None)
    return list(seen)


def render_prompt(status: str, rule_based_report: str, quoted_log_lines: str = "(none)",
                  prompts_dir: Path | None = None) -> tuple[str, str]:
    """(system prompt, task prompt) for one status. The numbers of the report are listed in the system prompt as locked."""
    if status not in TASK_FILES:
        raise ValueError(f"unknown status {status!r}; choose from {sorted(TASK_FILES)}")
    system = fill(load_template("system.md", prompts_dir), {"locked_numbers": ", ".join(numbers_in(rule_based_report)) or "none"})
    task_template = load_template(TASK_FILES[status], prompts_dir)
    values = {"rule_based_report": rule_based_report, "quoted_log_lines": quoted_log_lines}
    task = fill(task_template, {k: v for k, v in values.items() if k in PLACEHOLDER_RE.findall(task_template)})
    return system, task


def check_neutral_language(text: str) -> list[str]:
    """The loaded words that occur in the text (whole words, any case); [] when the text is neutral."""
    lowered = text.lower()
    return sorted({w for w in LOADED_WORDS if re.search(rf"\b{re.escape(w)}\b", lowered)})
