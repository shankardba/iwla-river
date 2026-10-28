"""Findings that compare the chapter with nearby streams."""

from __future__ import annotations

import math

from ... import config as C
from ..db import CHAPTER, fmt, pfmt, public_site, year
from ..registry import Page, chart, finding, gmaps, links, maplink, section, table, text

section("region", "Neighbouring streams",
        f"Every Clean Water Hub site within {C.NEIGHBOUR_KM} km of the chapter with a long enough record, most of them "
        "Fairfax County streams across the Potomac: are they changing the same way?", order=30)


@finding("region", "neighbour-trends", "Streams across the Potomac are mostly improving", order=10, key=True)
def neighbour_trends(db):
    rows = [r for r in db.trends() if not r["is_chapter_site"] and r["measure"] == "score"
            and r["verdict"] != "too few repeat seasons"]
    if not rows:
        return None
    rows.sort(key=lambda r: (-r["slope_per_decade"], r["p"]))
    for r in rows:
        r["site_name"] = public_site(r["site_name"], 0.0, 0.0, True)[0]
    ll = {}
    for r in db.rows("SELECT site_id, site_name, lat, lon, water_source FROM sites WHERE lat IS NOT NULL"):
        _, r["lat"], r["lon"] = public_site(r["site_name"], r["lat"], r["lon"], True, r["water_source"])
        ll[r["site_id"]] = r
    imp = sum(r["verdict"] == "improving" for r in rows)
    dec = sum(r["verdict"] == "declining" for r in rows)
    va = sum(r["state"] == "VA" for r in rows)
    lim = math.ceil(max(abs(r["slope_per_decade"]) for r in rows))
    step = 2 if lim > 4 else 1
    color = {"improving": "good", "declining": "bad"}
    spec = {"type": "dotrank", "title": f"{imp} of {len(rows)} long-record neighbour sites are improving; {dec} {'is' if dec == 1 else 'are'} declining",
            "legend": [{"name": "Improving", "color": "good"}, {"name": "No clear trend", "color": "grey"}, {"name": "Declining", "color": "bad"}],
            "x": {"min": -lim, "max": lim, "ticks": list(range(-lim, lim + 1, step)), "label": "change in score per decade"},
            "rows": [{"label": r["stream"] or r["site_name"], "note": f"{r['km']} km", "x": r["slope_per_decade"],
                      "href": gmaps(ll[r["site_id"]]["lat"], ll[r["site_id"]]["lon"]) if r["site_id"] in ll else None,
                      "color": color.get(r["verdict"], "grey"),
                      "tip": f"{r['site_name']} ({r['stream']}), {r['n']} surveys {year(r['first'])}–{year(r['last'])}: "
                             f"{r['slope_per_decade']:.1f} per decade, {pfmt(r['p'])}"} for r in rows]}
    return Page(refs=["cwh", "mann", "hirsch1982", "sen1968"], 
        headline=f"{imp} of {len(rows)} long-record sites within {C.NEIGHBOUR_KM} km show improving scores, the opposite of Site 1's direction.",
        status="good",
        numbers=[(f"{imp} of {len(rows)}", "neighbour sites improving"), (f"about {round(len(rows) * 0.1)}", "expected by chance alone")],
        blocks=[text(f"The same seasonal Kendall test ran on every Hub site within {C.NEIGHBOUR_KM} km with at least 8 surveys over "
                     f"5 or more years and 10 same-season comparisons. {va} of the {len(rows)} are across the Potomac in Northern Virginia, "
                     "mostly Fairfax County streams such as Snakeden Branch, Colvin Run and Sugarland Run, scored on the Virginia form (0–12)."),
                chart(spec, "Seasonal Kendall trend in the survey score at each neighbouring site, in points per decade on the site's own form."),
                text(f"{imp} improving where chance alone would flag about {round(len(rows) * 0.1)}. The chapter's slow loss of sensitive "
                     "animals runs against that direction, so a cause local to the Great Seneca watershed is worth looking for. "
                     "These streams sit in other watersheds and use a different form, so the comparison is a pointer, not proof."),
                links([("expected", "the model-based test, which judges every site against its own setting")])])


@finding("region", "nearby-sites", "Sites nearby", order=20)
def nearby_sites(db):
    rows = db.rows(f"""
        WITH c AS (SELECT lat, lon FROM sites WHERE site_id = 467), d AS (
          SELECT s.site_id, s.site_name, s.stream, s.lat, s.lon, s.water_source,
            round(6371 * 2 * asin(sqrt(pow(sin(radians(s.lat - c.lat) / 2), 2) +
              cos(radians(c.lat)) * cos(radians(s.lat)) * pow(sin(radians(s.lon - c.lon) / 2), 2))), 1) AS km
          FROM sites s, c WHERE s.lat IS NOT NULL AND s.site_id NOT IN ({CHAPTER}))
        SELECT d.*, (SELECT count(*) FROM usable_surveys u WHERE u.site_id = d.site_id) AS surveys,
               (SELECT string_agg(DISTINCT u.protocol, ', ') FROM usable_surveys u WHERE u.site_id = d.site_id) AS forms,
               (SELECT max(survey_date) FROM usable_surveys u WHERE u.site_id = d.site_id) AS last
        FROM d WHERE km <= 10 AND surveys > 0 ORDER BY km LIMIT 25""")
    if not rows:
        return None
    for r in rows:
        bio = any(f in (r["forms"] or "") for f in ("sos_bio", "va_rocky", "va_muddy"))
        name, r["lat"], r["lon"] = public_site(r["site_name"], r["lat"], r["lon"], bio, r["water_source"])
        if name != r["site_name"]:
            r["stream"] = ""
        r["site_name"] = name
    names = {"sos_bio": "SOS bio", "va_rocky": "VA rocky", "va_muddy": "VA muddy", "sos_chem": "SOS chem", "salt": "Salt", "nitrate": "Nitrate"}
    return Page(refs=["cwh"], 
        headline=f"{len(rows)} other Hub sites within 10 km have usable surveys, mostly salt and nitrate readings.",
        status="info",
        blocks=[text("Site names open in Google Maps. Sites with many surveys can show whether a change at Great Seneca Creek is local or shared across the area. "
                     "The chapter's own Salt Watch and Nitrate Watch points appear here too, filed as separate sites."),
                table([("Site",), ("Stream",), ("Distance", 1), ("Surveys", 1), ("Forms",), ("Latest",)],
                      [[maplink(r["site_name"] or f"Site {r['site_id']}", r["lat"], r["lon"]), r["stream"] or "", f"{r['km']} km", fmt(r["surveys"]),
                        ", ".join(names.get(f.strip(), f) for f in (r["forms"] or "").split(",")), r["last"] or "—"] for r in rows])])
