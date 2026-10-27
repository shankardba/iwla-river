"""Build the findings site into docs/ from data/river.duckdb.

Pages (flat file names, so links work the same on GitHub Pages and in a hosted preview):
  index.html                 home: key findings, every section
  <section>.html             a section and its findings
  <section>--<finding>.html  one finding
  findings.json              machine-readable index of every finding

Usage: python -m iwla_river.web.build
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import config as C
from . import findings as findings_pkg
from .db import DB, fmt
from .registry import FINDINGS, SECTIONS, STATUS_WORDS

HERE = Path(__file__).resolve().parent
OUT = C.ROOT / "docs"
BODY_OUT = C.REPORTS / "site"  # body-only copy of index.html for hosts that add their own <html> shell


def load_findings() -> None:
    for mod in pkgutil.iter_modules(findings_pkg.__path__):
        importlib.import_module(f"{findings_pkg.__name__}.{mod.name}")


def url(sec: str, fid: str | None = None) -> str:
    return f"{sec}--{fid}.html" if fid else f"{sec}.html"


def run_findings(db: DB) -> list[dict]:
    """Run every registered finding; keep those that return a page."""
    out = []
    for f in FINDINGS:
        page = f.fn(db)
        if page is None:
            continue
        out.append({"section": f.section, "id": f.id, "title": f.title, "order": f.order, "key": f.key,
                    "url": url(f.section, f.id), "page": page})
    return out


def build(db_path=C.DB_PATH, out: Path = OUT, body_out: Path = BODY_OUT) -> Path:
    load_findings()
    db = DB(db_path)
    items = run_findings(db)
    by_id = {i["id"]: i for i in items}
    sections = []
    for s in sorted(SECTIONS.values(), key=lambda s: s.order):
        fs = sorted([i for i in items if i["section"] == s.id], key=lambda i: i["order"])
        if fs:
            sections.append({"id": s.id, "title": s.title, "intro": s.intro, "url": url(s.id), "findings": fs})
    totals = db.rows("""SELECT count(*) FILTER (WHERE usable) AS usable, count(DISTINCT site_id) FILTER (WHERE usable) AS sites
                        FROM surveys""")[0]
    sos, va = db.sos(), db.va()
    meta = {"snapshot": db.snapshot(), "chapter_surveys": len(sos) + len(va),
            "first_year": min(int(r["date"][:4]) for r in sos) if sos else None,
            "last_year": max(int(r["date"][:4]) for r in sos + va) if sos else None,
            "usable": totals["usable"], "sites": totals["sites"]}

    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["fmt"] = fmt
    common = {"sections": sections, "meta": meta, "status_words": STATUS_WORDS, "by_id": by_id}

    def render(template: str, name: str, **ctx) -> str:
        specs = []
        html = env.get_template(template).render(**common, **ctx, specs=specs, page_name=name)
        # Chart specs are collected while rendering; write them where the template left the marker.
        return html.replace("__CHART_SPECS__", json.dumps(specs, default=str).replace("</", "<\\/"))

    if out.exists():
        for p in out.glob("*.html"):
            p.unlink()
    (out / "assets").mkdir(parents=True, exist_ok=True)
    for a in (HERE / "assets").iterdir():
        shutil.copy(a, out / "assets" / a.name)

    pages = {"index.html": render("home.html", "index.html",
                                  key=[i for s in sections for i in s["findings"] if i["key"]])}
    for s in sections:
        pages[s["url"]] = render("section.html", s["url"], section=s)
        for n, i in enumerate(s["findings"]):
            prev = s["findings"][n - 1] if n else None
            nxt = s["findings"][n + 1] if n + 1 < len(s["findings"]) else None
            pages[i["url"]] = render("finding.html", i["url"], section=s, item=i, prev=prev, next=nxt)
    for name, html in pages.items():
        (out / name).write_text(html)

    index = [{"section": i["section"], "id": i["id"], "title": i["title"], "url": i["url"], "key": i["key"],
              "headline": i["page"].headline, "status": i["page"].status,
              "numbers": [{"value": v, "label": l} for v, l in i["page"].numbers if l]} for s in sections for i in s["findings"]]
    (out / "findings.json").write_text(json.dumps({"snapshot": meta["snapshot"], "findings": index}, indent=1))

    # Body-only home page: the same page minus <!doctype>, <html>, <head> and <body> wrappers.
    body_out.mkdir(parents=True, exist_ok=True)
    home = pages["index.html"]
    head_start, body_start = home.index("<head>") + 6, home.index("<body>") + 6
    body = home[head_start:home.index("</head>")] + home[body_start:home.index("</body>")]
    (body_out / "index.html").write_text(body)
    print({"pages": len(pages), "findings": len(index), "out": str(out)})
    return out


if __name__ == "__main__":
    build()
