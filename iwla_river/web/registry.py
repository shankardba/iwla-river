"""The findings registry: sections, findings and the content blocks a finding returns.

To add a finding, write a function in a module under iwla_river/web/findings/ and decorate it:

    @finding("chapter", "score-trend", "The score has held steady", order=10, key=True)
    def score_trend(db):
        ...
        return Page(headline="Scores held near 16.5 before 2013 and 16.6 since", status="steady",
                    blocks=[text("..."), chart({...}, "caption"), table([...], [...])])

The build finds it automatically, gives it a page, lists it in its section and the sidebar,
and (with key=True) puts it on the home page. Return None to leave a finding out when its
data is missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Section:
    id: str
    title: str
    intro: str
    order: int


@dataclass
class Finding:
    section: str
    id: str
    title: str
    order: int
    key: bool
    fn: Callable


@dataclass
class Page:
    headline: str                      # one sentence: the result, with its number
    status: str = "info"               # concern | watch | steady | good | info
    blocks: list = field(default_factory=list)
    numbers: list = field(default_factory=list)   # [(value, label)] shown as key figures
    method: str | None = None          # short note on how the result was worked out
    refs: list = field(default_factory=list)      # keys into refs.REFS: every source the page relies on


SECTIONS: dict[str, Section] = {}
FINDINGS: list[Finding] = []

STATUS_WORDS = {"concern": "Concern", "watch": "Watch", "steady": "Steady", "good": "Good news", "info": "Context"}


def section(id: str, title: str, intro: str, order: int) -> None:
    SECTIONS[id] = Section(id, title, intro, order)


def finding(section: str, id: str, title: str, order: int = 50, key: bool = False):
    def register(fn):
        FINDINGS.append(Finding(section, id, title, order, key, fn))
        return fn
    return register


# ---------- content blocks ----------

def text(*paras: str) -> dict:
    return {"kind": "text", "paras": [p for p in paras if p]}


def chart(spec: dict, caption: str = "") -> dict:
    return {"kind": "chart", "spec": spec, "caption": caption}


def table(cols: list, rows: list, note: str = "") -> dict:
    """cols: [(heading, numeric?)]; cells: plain values or {"pill": status, "text": words}."""
    return {"kind": "table", "cols": [{"h": c[0], "num": bool(c[1]) if len(c) > 1 else False} for c in cols],
            "rows": rows, "note": note}


def maplink(words: str, lat, lon) -> dict:
    """Table cell linking to the spot in Google Maps."""
    return {"href": gmaps(lat, lon), "text": words} if lat is not None and lon is not None else words


def gmaps(lat, lon) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat:.5f},{lon:.5f}"


def pill(status: str, words: str) -> dict:
    return {"pill": status, "text": words}


def diagram(svg: str, caption: str = "") -> dict:
    """A drawn diagram (static SVG from iwla_river.web.diagrams)."""
    return {"kind": "diagram", "svg": svg, "caption": caption}


def links(items: list) -> dict:
    """Related findings: [(finding_id, why)]."""
    return {"kind": "links", "items": items}
