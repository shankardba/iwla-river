"""Watershed findings: the zoomable explorer and the chapter's place in its nested watersheds."""

from __future__ import annotations

from ... import config as C
from ..db import fmt, pct
from ..registry import Page, finding, links, section, table, text

section("watersheds", "Watersheds",
        "Zoom from the whole country into nested USGS watersheds, from regions down to small subwatersheds, "
        "and compare each one's stream health, land and water chemistry with the unit around it.", order=15)

LEVEL = {2: "Region", 4: "Subregion", 6: "Basin", 8: "Subbasin", 10: "Watershed", 12: "Subwatershed"}


def complete(db) -> bool:
    """Show watershed pages only once nearly every site has been placed in a watershed."""
    if not db.has("site_huc") or not db.has("watershed_metrics"):
        return False
    placed = db.one("SELECT count(*) FROM site_huc")
    total = db.one("SELECT count(DISTINCT site_id) FROM usable_surveys WHERE lat IS NOT NULL")
    return bool(total) and placed / total >= 0.95


def chapter_huc(db):
    if not complete(db):
        return None
    return db.one("SELECT huc12 FROM site_huc WHERE site_id = 467")


@finding("watersheds", "explorer", "Watershed explorer", order=10, key=True)
def explorer(db):
    if not complete(db):
        return None
    huc = chapter_huc(db) or ""
    n = db.one("SELECT count(*) FROM watershed_metrics WHERE digits = 12")
    return Page(
        headline=f"Explore {fmt(n)} subwatersheds with surveys, from US regions down to the chapter's own Great Seneca Creek.",
        status="info",
        blocks=[{"kind": "explorer", "chapter": huc},
                text("Each bubble is a watershed inside the one you are looking at, placed at the average position of its sites "
                     "and sized by how many sites and surveys it holds. Its colour compares the share of pollution-sensitive animals "
                     "found with what the expected-score model predicts for each survey's season and setting. Click a bubble or a "
                     "row to zoom in; at the smallest level each site opens in Google Maps.",
                     "Watersheds are USGS hydrologic units (Watershed Boundary Dataset): 2-digit regions, 4-digit subregions, "
                     "6-digit basins, 8-digit subbasins, 10-digit watersheds and 12-digit subwatersheds. No map tiles are loaded."),
                links([("great-seneca", "the chapter's watershed compared with each unit around it"), ("model", "how expected values are made")])],
        method="Sites are placed in USGS hydrologic units by a point-in-polygon test against the Watershed Boundary Dataset. "
               "A watershed's figures pool every usable survey from its sites; its gap trend is a seasonal Kendall test on the "
               "median gap per season and year, shown only with at least 10 same-season comparisons.")


@finding("watersheds", "great-seneca", "Great Seneca Creek within its watersheds", order=20, key=False)
def great_seneca(db):
    huc = chapter_huc(db)
    if not huc:
        return None
    codes = ",".join(f"'{huc[:d]}'" for d in (12, 10, 8, 6, 4, 2))
    rows = db.rows(f"SELECT * FROM watershed_metrics WHERE code IN ({codes}) ORDER BY digits DESC")
    if not rows:
        return None
    me = rows[0]
    gv = lambda r: r["gap_verdict"] if r.get("gap_verdict") == r.get("gap_verdict") and r.get("gap_verdict") else "—"
    num = lambda v, f: "—" if v is None or v != v else f(v)
    up = next((r for r in rows[1:] if r["sens_obs"] == r["sens_obs"] and r["sens_obs"] is not None), None)
    return Page(
        headline=(f"Great Seneca Creek's subwatershed finds {pct(me['sens_obs'])} sensitive groups against {pct(me['sens_exp'])} expected; "
                  f"its wider {LEVEL[up['digits']].lower()}, {up['name']}, finds {pct(up['sens_obs'])}.") if up and me["sens_obs"] == me["sens_obs"]
                 else f"Great Seneca Creek sits in subwatershed {huc}.",
        status="info",
        blocks=[text("The same measures for the chapter's subwatershed and each larger unit it sits inside. Open the explorer to "
                     "compare it with its neighbours at any level."),
                table([("Level",), ("Name",), ("Sites", 1), ("Biological surveys", 1), ("Sensitive found", 1), ("Expected", 1),
                       ("Gap trend",), ("Paved", 1), ("Chloride median", 1)],
                      [[f"{LEVEL[r['digits']]} ({r['code']})", r["name"] or "—", fmt(r["sites"]), fmt(r["bio_surveys"]),
                        num(r["sens_obs"], pct), num(r["sens_exp"], pct), gv(r), num(r["imperv"], lambda v: f"{v:.1f}%"),
                        num(r["cl_median"], lambda v: f"{v:.0f} mg/L")] for r in rows]),
                links([("explorer", "zoom in and out from here"), ("expected", "the chapter's own sites against expectations")])])
