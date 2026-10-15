"""SVG reproducibility badges (#39): a two-part badge, a gray 'repro radar' label and a colored '<score> · <status>'.

The owner chose this design (shields.io style). The text comes from a stored score; a paper without a score gets a gray
'not scored' badge, never an invented number. Every text is escaped, and the badge is a pure function of its inputs, so
its hash works as a cache validator.
"""

from __future__ import annotations

import hashlib
from html import escape

LABEL = "repro radar"
NOT_SCORED_TEXT = "not scored"
COLORS = {
    "Verified": "#2da44e",
    "Partially Verified": "#bf8700",
    "Needs Review": "#0969da",
    "Failed": "#cf222e",
}
NOT_SCORED_COLOR = "#8c959f"
LABEL_COLOR = "#57606a"
CHAR_WIDTH = 6.6  # average width of a 11px sans-serif character, in pixels
PADDING = 10
HEIGHT = 20


def _width(text: str) -> int:
    return round(len(text) * CHAR_WIDTH) + 2 * PADDING


def format_value(score: float | None, status: str | None) -> tuple[str, str]:
    """The right-hand text and its color. No score (or no status) means 'not scored', in gray."""
    if score is None or status is None:
        return NOT_SCORED_TEXT, NOT_SCORED_COLOR
    return f"{score:g} · {status}", COLORS.get(status, NOT_SCORED_COLOR)


def render_badge(score: float | None, status: str | None) -> str:
    value, color = format_value(score, status)
    left, right = _width(LABEL), _width(value)
    total = left + right
    title = f"{LABEL}: {value}"
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{total}' height='{HEIGHT}' role='img' "
        f"aria-label='{escape(title, quote=True)}'><title>{escape(title)}</title>"
        f"<clipPath id='r'><rect width='{total}' height='{HEIGHT}' rx='3'/></clipPath>"
        f"<g clip-path='url(#r)'><rect width='{left}' height='{HEIGHT}' fill='{LABEL_COLOR}'/>"
        f"<rect x='{left}' width='{right}' height='{HEIGHT}' fill='{color}'/></g>"
        "<g fill='#fff' text-anchor='middle' font-family='Verdana,DejaVu Sans,sans-serif' font-size='11'>"
        f"<text x='{left / 2:g}' y='14'>{escape(LABEL)}</text>"
        f"<text x='{left + right / 2:g}' y='14'>{escape(value)}</text></g></svg>"
    )


def badge_etag(svg: str) -> str:
    return '"' + hashlib.sha256(svg.encode("utf-8")).hexdigest()[:16] + '"'
