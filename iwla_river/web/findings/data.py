"""Data quality, sources and methods."""

from __future__ import annotations

from ..db import CHAPTER, LABEL, PROTO, fmt, year
from ..registry import Page, chart, finding, section, table, text

section("data", "Data and methods",
        "Where the numbers come from, how they were cleaned, and the problems found in the volunteer data along the way.",
        order=90)


@finding("data", "data-quality", "How clean the data is", order=10)
def data_quality(db):
    rows = db.rows("""SELECT protocol, count(*) AS records, sum(usable::int) AS usable, sum((survey_date IS NULL)::int) AS no_date,
                             sum(is_deleted::int) AS deleted, sum((duplicate_of IS NOT NULL)::int) AS duplicates,
                             count(DISTINCT site_id) AS sites, min(survey_date) FILTER (WHERE usable) AS first,
                             max(survey_date) FILTER (WHERE usable) AS last
                      FROM surveys GROUP BY protocol ORDER BY records DESC""")
    comp = db.rows("""SELECT protocol, count(*) AS usable, round(100 * avg((water_temp_c IS NOT NULL)::int)) AS temp,
                             round(100 * avg((flow_rate IS NOT NULL)::int)) AS flow,
                             round(100 * avg((weather_today IS NOT NULL OR weather_72h IS NOT NULL)::int)) AS weather,
                             round(100 * avg((group_size IS NOT NULL)::int)) AS team
                      FROM usable_surveys WHERE protocol IN ('sos_bio', 'va_rocky', 'va_muddy') GROUP BY 1 ORDER BY usable DESC""")
    total, usable = sum(r["records"] for r in rows), sum(r["usable"] for r in rows)
    return Page(refs=["cwh"], 
        headline=f"{fmt(usable)} of {fmt(total)} records ({round(100 * usable / total)}%) are usable after removing undated, deleted and duplicate surveys.",
        status="info",
        numbers=[(fmt(total), "records downloaded"), (fmt(usable), "usable")],
        blocks=[text("A survey is usable when it has a date between 1969 and the download, is not deleted or archived, and is not a "
                     "duplicate (same form, site and date with identical counts or readings)."),
                table([("Survey form",), ("Records", 1), ("Usable", 1), ("No usable date", 1), ("Deleted", 1), ("Duplicates", 1), ("Sites", 1), ("Span",)],
                      [[PROTO.get(r["protocol"], r["protocol"]), fmt(r["records"]), fmt(r["usable"]), fmt(r["no_date"]), fmt(r["deleted"]),
                        fmt(r["duplicates"]), fmt(r["sites"]), f"{year(r['first'])}–{year(r['last'])}" if r["first"] else ""] for r in rows]),
                text("How often the context the model needs is filled in, biological surveys nationwide:"),
                table([("Survey form",), ("Usable", 1), ("Water temp", 1), ("Flow", 1), ("Weather", 1), ("Team size", 1)],
                      [[PROTO.get(r["protocol"], r["protocol"]), fmt(r["usable"]), f"{r['temp']:.0f}%", f"{r['flow']:.0f}%",
                        f"{r['weather']:.0f}%", f"{r['team']:.0f}%"] for r in comp])])


@finding("data", "temperature-units", "Water temperature switches units", order=20)
def temperature_units(db):
    rows = db.rows(f"""SELECT survey_date AS date, site_id, water_temp_raw AS raw, temp_rule AS rule, water_temp_c AS c
                       FROM usable_surveys WHERE site_id IN ({CHAPTER}) AND water_temp_raw IS NOT NULL ORDER BY date""")
    if not rows:
        return None
    nat = db.rows("SELECT temp_rule AS rule, count(*) AS n FROM surveys WHERE temp_rule <> 'missing' GROUP BY 1")
    n = {r["rule"]: r["n"] for r in nat}
    first_f = next((year(r["date"]) for r in rows if r["rule"] == "fahrenheit_converted"), None)
    color = {"celsius": "accent", "fahrenheit_converted": "warn"}
    spec = {"type": "time", "title": f"Readings jump from Celsius to Fahrenheit in {first_f}" if first_f else "Water temperature as entered",
            "legend": [{"name": "Read as °C", "color": "accent"}, {"name": "Read as °F, converted", "color": "warn"}, {"name": "Unclear, left blank", "color": "bad"}],
            "y": {"min": 0, "max": 90, "ticks": [0, 30, 60, 90]}, "height": 270,
            "series": [{"color": c, "opacity": 1, "points": [{"x": r["date"], "y": r["raw"],
                        "tip": f"{LABEL[r['site_id']]}, {r['date']}: entered {r['raw']:g}" + (f" → {r['c']:g} °C" if r["c"] is not None else "")}
                        for r in rows if color.get(r["rule"], "bad") == c]} for c in ("accent", "warn", "bad")]}
    return Page(refs=["cwh"], 
        headline=f"The Hub stores no temperature unit; chapter readings switch from °C to °F in {first_f}, and {fmt(n.get('fahrenheit_converted', 0))} readings nationwide needed converting.",
        status="info",
        blocks=[chart(spec, "Water temperature as entered at the chapter sites."),
                text(f"Entries move from Celsius (under 30) to what can only be Fahrenheit (50 to 80) from {first_f}, sometimes on the "
                     f"same day at the two sites. Readings up to 32 are taken as °C, 41 and up as °F and converted, and 32 to 41 is "
                     f"left blank as unclear ({fmt(n.get('ambiguous', 0))} readings nationwide). Without this fix any temperature trend would be meaningless.")])


@finding("data", "methods", "Sources and methods", order=30)
def methods(db):
    snap = db.snapshot()
    return Page(refs=["cwh", "sos", "nldi", "nhdplus", "streamcat", "nlcd2019", "openmeteo", "era5", "wbd", "mann", "hirsch1982", "sen1968", "good2005", "friedman2001", "sklearn"], 
        headline=f"Built from a Clean Water Hub snapshot of {snap}, with public land-cover and weather data.",
        status="info",
        blocks=[table([("Source",), ("What it provides",)], [
                    ["Clean Water Hub (Izaak Walton League)", "Every Save Our Streams survey: biological, chemical, Virginia SOS, Salt Watch, Nitrate Watch"],
                    ["USGS NLDI", "The NHDPlus stream segment each site sits on"],
                    ["EPA StreamCat", "Watershed land cover (NLCD 2019), soils, elevation, 1981–2010 climate, road crossings, population"],
                    ["Open-Meteo archive", "Daily rainfall and air temperature for the week before each survey"],
                    ["Google Maps (links only)", "Every map dot and site name opens the spot in Google Maps; no map tiles are loaded here"]]),
                text("Personal details (emails, phone numbers, names) are removed when the data is downloaded and never appear here.",
                     "Trends use the seasonal Kendall test, which compares a survey only with surveys from the same season in other "
                     "years, with Sen slopes and at least 10 same-season comparisons. Turning points use a permutation test. Species "
                     "groups are matched across the SOS and Virginia forms by a shared list of groups and pollution tolerance.",
                     "The expected-score model is gradient-boosted trees validated with five folds grouped by site, so each "
                     "expected value comes from a model that never saw that site.",
                     "Code, tests and the full method notes: github.com/shankardba/iwla-river.")])


@finding("data", "downloads", "Downloads", order=40)
def downloads(db):
    import os
    from ... import config as C
    docs = C.ROOT / "docs"
    def size(p):
        f = docs / p
        return f"{f.stat().st_size / 1e6:.1f} MB" if f.exists() and f.stat().st_size > 1e6 else (f"{f.stat().st_size / 1e3:.0f} KB" if f.exists() else "")
    rows = [
        [{"href": "data/watershed_metrics.csv", "text": "watershed_metrics.csv"}, "Every watershed at every level: sites, surveys, sensitive share found and expected, gap and its trend, paved, forest, chloride, nitrate", size("data/watershed_metrics.csv")],
        [{"href": "findings.json", "text": "findings.json"}, "Every finding on this site: title, headline, status and key figures", size("findings.json")],
        [{"href": "data/watersheds.json", "text": "watersheds.json"}, "Regions to subbasins and the sample heat cells, as used by Explore", size("data/watersheds.json")],
    ]
    return Page(refs=["cwh"], 
        headline="Watershed-level figures and every finding, free to download.",
        status="info",
        blocks=[table([("File",), ("What it holds",), ("Size", 1)], rows),
                text("Downloads are aggregates. Site-level records stay with the Izaak Walton League's Clean Water Hub, "
                     "where volunteers entered them; many sites are home taps and are not republished here.",
                     "Code that rebuilds everything from the Hub: github.com/shankardba/iwla-river.")])


@finding("data", "references", "References", order=35)
def references(db):
    from ..refs import REFS
    n = {k: sum(1 for r in REFS.values() if r["kind"] == k) for k in ("data", "method", "science")}
    return Page(
        headline=f"Every number on this site traces to {n['data']} data sources, {n['method']} published methods and "
                 f"{n['science']} studies that explain what the readings mean.",
        status="info",
        blocks=[text("Each finding lists its own sources at the foot of the page. Below is the full list, with the findings "
                     "that cite each source. DOIs were checked against Crossref and DataCite; data sources show when they "
                     "were accessed for this site.")])
