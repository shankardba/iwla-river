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
    nat = db.rows("""SELECT (SELECT avg(ws_impervious_pct) FROM site_context) AS imperv, (SELECT avg(ws_forest_pct) FROM site_context) AS forest,
                            (SELECT median(value) FROM chemistry WHERE parameter = 'chloride') AS cl_median,
                            (SELECT count(*) FROM chemistry WHERE parameter = 'chloride') AS cl_n,
                            (SELECT median(value) FROM chemistry WHERE parameter IN ('nitrate', 'nitrate_n')) AS no3_median,
                            (SELECT count(*) FROM chemistry WHERE parameter IN ('nitrate', 'nitrate_n')) AS no3_n,
                            (SELECT avg(observed) FROM expected WHERE target = 'score_pct') AS score_pct""")[0]
    top[""] = pack({"code": "", "name": "United States", "sites": us["sites"], "bio_surveys": bio, **nat}) | \
        {"so": round(so["so"], 3), "se": round(so["se"], 3), "g": round(so["g"], 3)}
    (out / "data" / "huc4").mkdir(parents=True, exist_ok=True)
    # Heat cells of a quarter degree (about 25 km) by sample type, each placed at its samples' average position
    # rounded to 0.01 degree (no finer than public_site), so the map shows where samples are, not a grid.
    heat = db.rows("""
        SELECT round(avg(lat), 2) AS la, round(avg(lon), 2) AS lo,
               count(*) FILTER (WHERE protocol IN ('sos_bio', 'va_rocky', 'va_muddy')) AS bio,
               count(*) FILTER (WHERE protocol = 'salt') AS salt,
               count(*) FILTER (WHERE protocol = 'nitrate') AS no3,
               count(*) FILTER (WHERE protocol = 'sos_chem') AS chem
        FROM usable_surveys WHERE lat IS NOT NULL AND lon IS NOT NULL GROUP BY round(lat * 4), round(lon * 4)""")
    heat = [[r["la"], r["lo"], r["bio"], r["salt"], r["no3"], r["chem"]] for r in heat]
    # States: the same measures per state, plus the subbasins with sites in each (to step into watersheds).
    st = {}
    if db.has("state_metrics"):
        subs = {}
        for r in db.rows("SELECT state, huc8, sites, bio_surveys FROM state_subbasins ORDER BY state, bio_surveys DESC, sites DESC"):
            subs.setdefault(r["state"], []).append([r["huc8"], r["sites"], r["bio_surveys"]])
        for r in db.rows("SELECT * FROM state_metrics"):
            st[r["code"]] = pack(r) | {"hb": subs.get(r["code"], [])}
    (out / "data" / "watersheds.json").write_text(json.dumps({"w": top, "heat": heat, "st": st}, separators=(",", ":")))
    # Finer heat inside each state (cells of 0.05 degree, about 5 km), fetched when a state is opened.
    if db.has("site_state"):
        hd = out / "data" / "states"
        if hd.exists():
            shutil.rmtree(hd)
        hd.mkdir(parents=True)
        cells = db.rows("""
            SELECT s.state, round(avg(u.lat), 2) AS la, round(avg(u.lon), 2) AS lo,
                   count(*) FILTER (WHERE u.protocol IN ('sos_bio', 'va_rocky', 'va_muddy')) AS bio,
                   count(*) FILTER (WHERE u.protocol = 'salt') AS salt, count(*) FILTER (WHERE u.protocol = 'nitrate') AS no3,
                   count(*) FILTER (WHERE u.protocol = 'sos_chem') AS chem
            FROM usable_surveys u JOIN site_state s USING (site_id) WHERE s.state <> ''
            GROUP BY s.state, round(u.lat * 20), round(u.lon * 20)""")
        by_state = {}
        for r in cells:
            by_state.setdefault(r["state"], []).append([round(r["la"], 2), round(r["lo"], 2), r["bio"], r["salt"], r["no3"], r["chem"]])
        for k, v in by_state.items():
            (hd / f"{k}.json").write_text(json.dumps(v, separators=(",", ":")))
    sg = HERE / "geo" / "states.json"
    if sg.exists():
        (out / "data" / "geo").mkdir(parents=True, exist_ok=True)
        shutil.copy(sg, out / "data" / "geo" / "states.json")
    geo = HERE / "geo" / "lower48.json"
    if geo.exists():
        shutil.copy(geo, out / "data" / "lower48.json")
    sites = db.rows("""
        SELECT h.huc12, u.site_id, round(any_value(u.lat), 5) AS lat, round(any_value(u.lon), 5) AS lon,
               count(*) FILTER (WHERE u.protocol IN ('sos_bio', 'va_rocky', 'va_muddy')) AS bio,
               count(*) FILTER (WHERE u.protocol NOT IN ('sos_bio', 'va_rocky', 'va_muddy')) AS other,
               left(coalesce(any_value(u.site_name), ''), 40) AS name, any_value(st.water_source) AS water_source,
               count(*) FILTER (WHERE u.protocol = 'salt') AS salt, count(*) FILTER (WHERE u.protocol = 'nitrate') AS no3,
               count(*) FILTER (WHERE u.protocol = 'sos_chem') AS chem
        FROM usable_surveys u JOIN site_huc h USING (site_id) LEFT JOIN sites st USING (site_id)
        GROUP BY h.huc12, u.site_id""")
    from .db import public_site
    for s in sites:  # no home addresses, names or exact home locations in published files
        s["name"], s["lat"], s["lon"] = public_site(s["name"], s["lat"], s["lon"], s["bio"] > 0, s["water_source"])
    small = {}
    for r in rows:
        if r["digits"] >= 10:
            small.setdefault(r["code"][:4], {})[r["code"]] = pack(r)
    by4 = {}
    for s in sites:
        by4.setdefault(s["huc12"][:4], []).append([s["site_id"], s["lat"], s["lon"], s["huc12"], s["bio"], s["other"], s["name"],
                                                   s["salt"], s["no3"], s["chem"]])
    for p in (out / "data" / "huc4").glob("*.json"):
        p.unlink()
    # Survey history of each biological site: [date, form, score, sensitive share found, expected], for the site panel.
    hist = db.rows("""
        SELECT h.huc12, f.site_id, f.survey_date::DATE AS d, f.protocol AS form, f.score, f.sensitive_share AS ss, e.expected AS ex
        FROM features f JOIN site_huc h USING (site_id)
        LEFT JOIN expected e ON e.survey_uid = f.survey_uid AND e.target = 'sensitive_share'
        ORDER BY f.site_id, d""") if db.has("expected") else []
    series = {}
    short = {"sos_bio": "SOS", "va_rocky": "VA", "va_muddy": "VA muddy"}
    for r in hist:
        rd = lambda v, k=3: None if v is None or v != v else round(v, k)
        series.setdefault(r["huc12"][:4], {}).setdefault(str(r["site_id"]), []).append(
            [r["d"], short.get(r["form"], r["form"]), rd(r["score"], 1), rd(r["ss"]), rd(r["ex"])])
    for h in set(small) | set(by4):
        (out / "data" / "huc4" / f"{h}.json").write_text(json.dumps(
            {"w": small.get(h, {}), "sites": by4.get(h, []), "series": series.get(h, {})}, separators=(",", ":")))

    # Watershed boundaries, packaged by the view that draws them: regions (top), subregions per region,
    # and everything smaller per subregion. Rings are [lon, lat] pairs, rounded and de-duplicated.
    cache = C.DATA / "cache"
    geo = {d: json.loads((cache / f"wbd_{d}.json").read_text()) for d in (2, 4, 6, 8, 10, 12) if (cache / f"wbd_{d}.json").exists()}
    if geo:
        def thin(rings, nd):
            out = []
            for ring in rings:
                pts, last = [], None
                for lo, la in ring:
                    q = [round(lo, nd), round(la, nd)]
                    if q != last:
                        pts.append(q)
                        last = q
                if len(pts) >= 4:
                    out.append(pts)
            return out
        gdir = out / "data" / "geo"
        for f in gdir.glob("*.json") if gdir.exists() else []:
            if f.name != "states.json":
                f.unlink()
        gdir.mkdir(parents=True, exist_ok=True)
        (gdir / "top.json").write_text(json.dumps({c: thin(r, 2) for c, r in geo.get(2, {}).items()}, separators=(",", ":")))
        reg = {}
        for c, r in geo.get(4, {}).items():
            reg.setdefault(c[:2], {})[c] = thin(r, 3)
        for h, d in reg.items():
            (gdir / f"r{h}.json").write_text(json.dumps(d, separators=(",", ":")))
        sub = {}
        for lvl, nd in ((6, 3), (8, 3), (10, 4), (12, 4)):
            for c, r in geo.get(lvl, {}).items():
                sub.setdefault(c[:4], {})[c] = thin(r, nd)
        for h, d in sub.items():
            (gdir / f"s{h}.json").write_text(json.dumps(d, separators=(",", ":")))

    # Rivers: every named river in each subbasin with biological surveys, packaged per subregion (data/rivers/<huc4>.json).
    rivers = write_rivers(out)

    # Search index: every named watershed, and biological sites under their public names.
    search = {"w": [[r["code"], r["name"]] for r in rows if r["name"]],
              "s": [[s["site_id"], s["name"], s["huc12"]] for s in sites if s["bio"] > 0 and s["name"] != "Biological monitoring site"],
              "r": rivers}
    (out / "data" / "search.json").write_text(json.dumps(search, separators=(",", ":")))

    # Download: metrics for every watershed (aggregates only).
    import csv
    cols = ["code", "digits", "name", "parent", "sites", "bio_sites", "bio_surveys", "chem_readings", "first_year", "last_year",
            "sens_obs", "sens_exp", "gap", "gap_p", "gap_slope", "gap_verdict", "score_pct", "imperv", "forest",
            "cl_median", "cl_p90", "cl_n", "no3_median", "no3_n"]
    with open(out / "data" / "watershed_metrics.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(cols)
        for r in sorted(rows, key=lambda r: (r["digits"], r["code"])):
            wr.writerow(["" if r.get(c) is None or r.get(c) != r.get(c) else (round(r[c], 4) if isinstance(r[c], float) else r[c]) for c in cols])


def tidal(rows):
    """A river whose mouth is at sea level reaches tidal water, whatever line it touches there."""
    for r in rows:
        if r.get("me") is not None and r["me"] <= 2:
            r["t"], r["f"] = True, None


def link_mouths(rows):
    """Name what each river flows into when the extractor could not: the nearest other line at its mouth (within ~200 m)."""
    import math
    cell = 0.003
    grid = {}
    for j, r in enumerate(rows):
        for path in r["p"]:
            for x, y in path:
                grid.setdefault((int(x // cell), int(y // cell)), set()).add(j)
    for i, r in enumerate(rows):
        if r.get("f") or r.get("t") or not r.get("m"):
            continue
        mx, my = r["m"]
        best, bd = None, 0.002
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((int(mx // cell) + dx, int(my // cell) + dy), ()):
                    if j == i or rows[j]["n"] == r["n"]:
                        continue
                    for path in rows[j]["p"]:
                        for x, y in path:
                            d = math.hypot((x - mx) * math.cos(math.radians(my)), y - my)
                            if d < bd:
                                best, bd = rows[j]["n"], d
        if best:
            r["f"] = best


def write_rivers(out: Path) -> list:
    """Pack data/cache/rivers_osm/<huc8>.json into data/rivers/<huc4>.json; returns search rows [name, huc8, index]."""
    src = C.DATA / "cache" / "rivers_osm"
    rdir = out / "data" / "rivers"
    for f in rdir.glob("*.json") if rdir.exists() else []:
        f.unlink()
    if not src.exists():
        return []
    rdir.mkdir(parents=True, exist_ok=True)
    pack, search = {}, []
    for f in sorted(src.glob("*.json")):
        d = json.loads(f.read_text())
        rows = []
        for r in d["rivers"]:
            if r["len_in_km"] < 1:
                continue
            search.append([r["name"], d["huc8"], len(rows)])
            rows.append({"n": r["name"], "k": r["kind"], "L": r["len_km"], "Li": r["len_in_km"], "s": r["source"], "se": r["source_elev_m"],
                         "si": r["source_in_unit"], "m": r["mouth"], "me": r["mouth_elev_m"], "f": r["flows_into"], "t": r.get("tidal", False),
                         "fb": r["formed_by"], "u": r["u"], "p": r["paths"]})
        pack.setdefault(d["huc8"][:4], {})[d["huc8"]] = rows
    from .. import terrain   # heights at both ends and along each river, from terrain tiles
    for v in pack.values():
        for rows in v.values():
            terrain.fill_rivers(rows)
            tidal(rows)
            link_mouths(rows)
    for h, v in pack.items():
        (rdir / f"{h}.json").write_text(json.dumps(v, separators=(",", ":")))
    nat = C.DATA / "cache" / "rivers_national.json"
    if nat.exists():
        rows = [{"n": r["name"], "k": "river", "L": r["len_km"], "Li": r["len_km"], "s": r["source"], "se": r["source_elev_m"], "si": True,
                 "m": r["mouth"], "me": r["mouth_elev_m"], "f": r["flows_into"], "t": r["tidal"], "fb": r["formed_by"], "u": r["u"], "p": r["paths"]}
                for r in json.loads(nat.read_text())["rivers"]]
        terrain.fill_rivers(rows)
        tidal(rows)
        # Country view: the longest rivers, coarsely; each region: its own major rivers.
        def coarse(r, nd, step):
            pts = [[[round(x, nd), round(y, nd)] for x, y in path[::step] + [path[-1]]] for path in r["p"]]
            return {**r, "p": [q for q in pts if len(q) > 1]}
        (rdir / "national.json").write_text(json.dumps([coarse(r, 2, 3) for r in rows if r["L"] >= 250], separators=(",", ":")))
        regions = {}
        for r in rows:
            for k in r["u"]:
                if len(k) == 2:
                    regions.setdefault(k, []).append(coarse(r, 3, 1))
        for k, v in regions.items():
            (rdir / f"n{k}.json").write_text(json.dumps(v, separators=(",", ":")))
        known = {s[0] for s in search}
        search += [[r["n"], max(r["u"], key=lambda k: (len(k) == 6, r["u"][k])) if r["u"] else "", -1] for r in rows if r["n"] not in known and r["u"]]
    return search


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
    from .findings.watersheds import chapter_huc, complete
    pages = {"index.html": render("home.html", "index.html",
                                  explorer_chapter=(chapter_huc(db) or "") if complete(db) else None,
                                  key=[i for s in sections for i in s["findings"] if i["key"]])}
    key = [i for s in sections for i in s["findings"] if i["key"]]
    pages["findings.html"] = render("findings.html", "findings.html", key=key)
    pages["about.html"] = render("about.html", "about.html", hero_svg=plates.riffle("about"))
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
    head_start = home.index("<head>") + 6
    body_tag = home.index("<body")
    body_start = home.index(">", body_tag) + 1
    cls = home[body_tag:body_start]
    # Keep the body's class on a wrapper so app-only styles still apply.
    klass = cls.split('class="')[1].split('"')[0] if 'class="' in cls else ""
    body = (home[head_start:home.index("</head>")] + f'<div class="{klass}">' + home[body_start:home.index("</body>")] + "</div>")
    (body_out / "index.html").write_text(body)
    print({"pages": len(pages), "findings": len(index), "out": str(out)})
    return out


if __name__ == "__main__":
    build()
