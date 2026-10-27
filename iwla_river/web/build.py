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


def write_watershed_data(db: DB, out: Path) -> None:
    """data/watersheds.json for regions to subbasins; data/huc4/<code>.json for smaller units and sites."""
    from .findings.watersheds import complete
    if not complete(db):
        if (out / "data").exists():
            shutil.rmtree(out / "data")
        return
    keys = {"code": "c", "name": "n", "parent": "p", "sites": "s", "bio_surveys": "bv", "first_year": "fy", "last_year": "ly",
            "lat": "la", "lon": "lo", "imperv": "im", "forest": "fo", "sens_obs": "so", "sens_exp": "se", "gap": "g",
            "gap_p": "gp", "gap_verdict": "gv", "score_pct": "sp", "cl_median": "cm", "cl_n": "cn", "no3_median": "nm", "no3_n": "nn"}
    rnd = {"la": 4, "lo": 4, "im": 1, "fo": 1, "so": 3, "se": 3, "g": 3, "gp": 4, "sp": 1, "cm": 1, "nm": 2}

    def pack(r):
        o = {}
        for k, short in keys.items():
            v = r.get(k)
            if v is None or v != v or v == "":
                continue
            if isinstance(v, float):
                v = round(v, rnd.get(short, 0)) if short in rnd else int(round(v))
            o[short] = v
        return o

    rows = db.rows("SELECT * FROM watershed_metrics")
    top = {r["code"]: pack(r) for r in rows if r["digits"] <= 8}
    us = db.rows("""SELECT count(DISTINCT site_id) AS sites FROM site_huc""")[0]
    bio = db.one("SELECT sum(bio_surveys) FROM watershed_metrics WHERE digits = 2")
    so = db.rows("SELECT avg(observed) AS so, avg(expected) AS se, avg(resid) AS g FROM expected WHERE target = 'sensitive_share'")[0]
    top[""] = pack({"code": "", "name": "United States", "sites": us["sites"], "bio_surveys": bio, **{k: so[k] for k in ("so", "se", "g")}}) | \
        {"so": round(so["so"], 3), "se": round(so["se"], 3), "g": round(so["g"], 3)}
    (out / "data" / "huc4").mkdir(parents=True, exist_ok=True)
    (out / "data" / "watersheds.json").write_text(json.dumps({"w": top}, separators=(",", ":")))
    geo = HERE / "geo" / "lower48.json"
    if geo.exists():
        shutil.copy(geo, out / "data" / "lower48.json")
    sites = db.rows("""
        SELECT h.huc12, u.site_id, round(any_value(u.lat), 5) AS lat, round(any_value(u.lon), 5) AS lon,
               count(*) FILTER (WHERE u.protocol IN ('sos_bio', 'va_rocky', 'va_muddy')) AS bio,
               count(*) FILTER (WHERE u.protocol NOT IN ('sos_bio', 'va_rocky', 'va_muddy')) AS other,
               left(coalesce(any_value(u.site_name), ''), 40) AS name
        FROM usable_surveys u JOIN site_huc h USING (site_id) GROUP BY h.huc12, u.site_id""")
    small = {}
    for r in rows:
        if r["digits"] >= 10:
            small.setdefault(r["code"][:4], {})[r["code"]] = pack(r)
    by4 = {}
    for s in sites:
        by4.setdefault(s["huc12"][:4], []).append([s["site_id"], s["lat"], s["lon"], s["huc12"], s["bio"], s["other"], s["name"]])
    for p in (out / "data" / "huc4").glob("*.json"):
        p.unlink()
    for h in set(small) | set(by4):
        (out / "data" / "huc4" / f"{h}.json").write_text(json.dumps({"w": small.get(h, {}), "sites": by4.get(h, [])}, separators=(",", ":")))


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
    from .share import SHARE_VERSION
    import hashlib
    asset_v = {a.name: hashlib.sha1(a.read_bytes()).hexdigest()[:8] for a in (HERE / "assets").iterdir() if a.is_file()}
    common = {"sections": sections, "meta": meta, "status_words": STATUS_WORDS, "by_id": by_id, "asset_v": asset_v,
              "site_url": C.SITE_URL, "share_v": SHARE_VERSION}

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

    from .diagrams import plates
    pages = {"index.html": render("home.html", "index.html", hero_svg=plates.riffle("home"),
                                  key=[i for s in sections for i in s["findings"] if i["key"]])}
    for s in sections:
        pages[s["url"]] = render("section.html", s["url"], section=s)
        for n, i in enumerate(s["findings"]):
            prev = s["findings"][n - 1] if n else None
            nxt = s["findings"][n + 1] if n + 1 < len(s["findings"]) else None
            pages[i["url"]] = render("finding.html", i["url"], section=s, item=i, prev=prev, next=nxt)
    for name, html in pages.items():
        (out / name).write_text(html)

    write_watershed_data(db, out)

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
