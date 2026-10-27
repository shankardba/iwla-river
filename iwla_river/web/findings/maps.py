"""Maps: where monitoring happens, nationally and around the chapter. Every dot opens in Google Maps.

No basemap is loaded: dots are placed by their own coordinates, which keeps the site light.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from ... import config as C
from ..db import fmt, pfmt, public_site, year
from ..registry import Page, chart, finding, gmaps, links, text

GEO = Path(__file__).resolve().parent.parent / "geo" / "lower48.json"


def outline_paths(P) -> list:
    """State lines and the national outline, projected with P and thinned to about one pixel."""
    if not GEO.exists():
        return []
    geo = json.loads(GEO.read_text())
    out = []
    for kind in ("inner", "border"):
        for arc in geo[kind]:
            pts, last = [], None
            for lo, la in arc:
                x, y = P(*albers(la, lo))
                if last is None or abs(x - last[0]) + abs(y - last[1]) >= 0.9:
                    pts.append((x, y))
                    last = (x, y)
            if len(pts) >= 2:
                out.append({"k": kind, "d": "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts)})
    return out


KIND = {"sos_bio": "bio", "va_rocky": "bio", "va_muddy": "bio", "sos_chem": "chem", "salt": "chem", "nitrate": "chem"}


def albers(lat, lon, lat0=23.0, lon0=-96.0, p1=29.5, p2=45.5):
    """Albers equal-area conic, the usual projection for the lower 48 states (unit sphere)."""
    f1, f2, f0 = map(math.radians, (p1, p2, lat0))
    nn = (math.sin(f1) + math.sin(f2)) / 2
    c = math.cos(f1) ** 2 + 2 * nn * math.sin(f1)
    rho0 = math.sqrt(c - 2 * nn * math.sin(f0)) / nn
    rho = math.sqrt(c - 2 * nn * math.sin(math.radians(lat))) / nn
    th = nn * math.radians(lon - lon0)
    return rho * math.sin(th), rho0 - rho * math.cos(th)


@finding("national", "map", "Where volunteers monitor", order=5, key=True)
def national_map(db):
    rows = db.rows("""SELECT s.site_id, s.lat, s.lon, u.protocol, count(*) AS n FROM usable_surveys u JOIN sites s USING (site_id)
                      WHERE s.lat BETWEEN 24 AND 50 AND s.lon BETWEEN -125 AND -66 GROUP BY ALL""")
    if not rows:
        return None
    # Group into cells of a quarter degree so the page stays light; a cell's colour is its main kind of survey.
    cells = {}
    for r in rows:
        key = (round(r["lat"] * 4) / 4, round(r["lon"] * 4) / 4)
        c = cells.setdefault(key, {"bio": 0, "chem": 0, "sites": set()})
        c[KIND.get(r["protocol"], "chem")] += r["n"]
        c["sites"].add(r["site_id"])
    if len(cells) < 2:
        return None
    proj = {k: albers(*k) for k in cells}
    # Fit the frame to the lower-48 outline (or the dots, if the outline file is missing).
    frame = [albers(la, lo) for kind in ("border",) for arc in (json.loads(GEO.read_text())[kind] if GEO.exists() else [])
             for lo, la in arc] or list(proj.values())
    xs, ys = [p[0] for p in frame], [p[1] for p in frame]
    W, pad = 760, 10
    sc = (W - 2 * pad) / (max(xs) - min(xs))
    H = (max(ys) - min(ys)) * sc + 2 * pad
    P = lambda x, y: (round(pad + (x - min(xs)) * sc, 1), round(H - pad - (y - min(ys)) * sc, 1))
    pts = []
    # Biological cells drawn last so the much more numerous salt and nitrate cells cannot hide them.
    for (la, lo), c in sorted(cells.items(), key=lambda kv: (kv[1]["bio"] > 0, -(kv[1]["bio"] + kv[1]["chem"]))):
        n = c["bio"] + c["chem"]
        x, y = P(*proj[(la, lo)])
        pts.append({"x": x, "y": y, "r": round(min(9, 1.6 + math.sqrt(n) * 0.45), 1),
                    "c": "c4" if c["bio"] else "c1", "ll": [la, lo],
                    "tip": f"{len(c['sites'])} sites: {c['bio']} bio, {c['chem']} chem"})
    site = db.rows("SELECT lat, lon FROM sites WHERE site_id = 467")[0]
    cx, cy = P(*albers(site["lat"], site["lon"]))
    pts.append({"x": cx, "y": cy, "r": 6, "color": "bad", "opacity": 1, "ring": True, "href": gmaps(site["lat"], site["lon"]),
                "tip": "Great Seneca Creek, the chapter's teaching site. Click for Google Maps."})
    states = db.rows("""SELECT state, count(DISTINCT site_id) AS sites FROM usable_surveys WHERE state IS NOT NULL
                        GROUP BY 1 ORDER BY sites DESC LIMIT 5""")
    n_sites = sum(len(c["sites"]) for c in cells.values())
    spec = {"type": "map", "title": f"{fmt(n_sites)} monitored sites in the lower 48 states",
            "legend": [{"name": "Has biological surveys", "color": "c4"}, {"name": "Salt, nitrate or chemistry only", "color": "c1"},
                       {"name": "Great Seneca Creek", "color": "bad"}],
            "height": round(H), "points": pts, "opacity": 0.6, "paths": outline_paths(P),
            "labels": [{"x": cx, "y": cy, "tx": cx - 50, "ty": cy + 70, "text": "Great Seneca Creek", "anchor": "end"}],
            "note": "Dot size: surveys in each quarter-degree cell. Alaska and Hawaii not shown. Outlines: US Census Bureau. Click a dot to open it in Google Maps."}
    return Page(
        headline=f"{fmt(n_sites)} sites across the lower 48 states have usable surveys; most are in {', '.join(s['state'] for s in states[:3])}.",
        status="info",
        numbers=[(fmt(n_sites), "sites with usable surveys"), (", ".join(s["state"] for s in states[:5]), "states with the most sites")],
        blocks=[chart(spec, "Clean Water Hub sites with at least one usable survey, grouped into quarter-degree cells and drawn on an Albers equal-area projection."),
                text("Biological surveys, which the expected-score model learns from, cluster in the mid-Atlantic and upper Midwest. "
                     "Salt Watch and Nitrate Watch kits spread monitoring much more widely. No map tiles are loaded: the dots are "
                     "placed by each site's own coordinates, and each opens in Google Maps."),
                links([("local-map", "the sites around Great Seneca Creek"), ("model", "the model trained on these surveys")])])


@finding("region", "local-map", "Map of sites around the creek", order=5, key=False)
def local_map(db):
    c = db.rows("SELECT lat, lon FROM sites WHERE site_id = 467")[0]
    lat0, lon0 = c["lat"], c["lon"]
    R = C.NEIGHBOUR_KM
    rows = db.rows(f"""
        WITH s AS (SELECT site_id, site_name, stream, lat, lon,
                     6371 * 2 * asin(sqrt(pow(sin(radians(lat - {lat0}) / 2), 2) + cos(radians({lat0})) * cos(radians(lat)) *
                     pow(sin(radians(lon - {lon0}) / 2), 2))) AS km FROM sites WHERE lat IS NOT NULL)
        SELECT s.*, any_value(st.water_source) AS water_source, count(u.survey_uid) AS n, string_agg(DISTINCT u.protocol, ',') AS forms
        FROM s JOIN usable_surveys u USING (site_id) LEFT JOIN sites st USING (site_id) WHERE s.km <= {R}
        GROUP BY s.site_id, s.site_name, s.stream, s.lat, s.lon, s.km""")
    trends = {r["site_id"]: r for r in db.trends() if r["measure"] == "score"}
    W = 760
    H = W * 0.8
    sc = (H / 2 - 20) / R  # px per km
    P = lambda la, lo: (round(W / 2 + (lo - lon0) * math.cos(math.radians(lat0)) * 111.32 * sc, 1),
                        round(H / 2 - (la - lat0) * 110.57 * sc, 1))
    color = {"improving": "good", "declining": "bad"}
    paths = []
    if GEO.exists():
        geo = json.loads(GEO.read_text())
        for kind in ("inner", "border"):
            for arc in geo[kind]:
                xy = [P(la, lo) for lo, la in arc]
                inside = [(x, y) for x, y in xy if -40 <= x <= W + 40 and -40 <= y <= H + 40]
                if len(inside) >= 2:
                    paths.append({"k": kind, "d": "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in inside)})
    pts = []
    for r in sorted(rows, key=lambda r: r["site_id"] in trends):
        bio = any(KIND.get(f) == "bio" for f in (r["forms"] or "").split(","))
        name, r["lat"], r["lon"] = public_site(r["site_name"], r["lat"], r["lon"], bio, r["water_source"])
        if name != r["site_name"]:
            r["stream"] = None
        r["site_name"] = name
        x, y = P(r["lat"], r["lon"])
        if not (0 <= x <= W):
            continue
        t = trends.get(r["site_id"])
        p = {"x": x, "y": y, "r": 6 if t else 3.5 if bio else 2.5,
             "c": color.get(t["verdict"], "grey") if t else ("c4" if bio else "c1"),
             "ll": [round(r["lat"], 5), round(r["lon"], 5)],
             "tip": f"{(r['stream'] or r['site_name'] or 'site')[:40]}, {r['km']:.0f} km, {r['n']} surveys" + (f", {t['verdict']}" if t else "")}
        if t:
            p["opacity"] = 0.95
        pts.append(p)
    cx, cy = P(lat0, lon0)
    pts.append({"x": cx, "y": cy, "r": 7, "color": "accent", "opacity": 1, "ring": True, "href": gmaps(lat0, lon0),
                "tip": "Great Seneca Creek, the chapter's sites. Click for Google Maps."})
    n_trend = sum(1 for r in rows if r["site_id"] in trends)
    spec = {"type": "map", "title": f"{len(rows)} sites with surveys within {R} km; {n_trend} have a score-trend test",
            "legend": [{"name": "Improving", "color": "good"}, {"name": "No clear trend", "color": "grey"}, {"name": "Declining", "color": "bad"},
                       {"name": "Other biological", "color": "c4"}, {"name": "Salt, nitrate, chemistry", "color": "c1"}],
            "height": round(H), "points": pts, "opacity": 0.55, "paths": paths, "clip": True,
            "rings": [{"cx": cx, "cy": cy, "r": round(k * sc, 1), "label": f"{k} km"} for k in (10, 20, 30)],
            "labels": [{"x": cx, "y": cy, "tx": cx + 70, "ty": cy - 60, "text": "Great Seneca Creek", "sub": "chapter sites"}],
            "words": [{"x": cx + 110, "y": cy + 60, "text": "MARYLAND"}, {"x": cx - 170, "y": cy + 175, "text": "VIRGINIA"}],
            "note": "North is up. Big dots: sites with a score-trend test. Click any dot to open it in Google Maps."}
    return Page(
        headline=f"{len(rows)} Clean Water Hub sites with surveys lie within {R} km of the chapter; the long-record ones cluster to the southwest, across the Potomac.",
        status="info",
        blocks=[chart(spec, "Sites placed by their own coordinates (kilometres from the chapter's teaching site); no basemap is loaded."),
                text("The tested sites, mostly Fairfax County streams scored on the Virginia form, sit 14 to 30 km away across the "
                     "Potomac. On the Maryland side, nearby sites mostly carry salt and nitrate readings. Open any dot in Google Maps "
                     "to see the stream, the roads and the land around it."),
                links([("neighbour-trends", "their trends in detail"), ("nearby-sites", "the closest sites as a table")])])
