"""Findings from the chapter's Salt Watch and Nitrate Watch readings."""

from __future__ import annotations

from ... import config as C
from ..db import CHEM, fmt, mean, year
from ..diagrams import plates
from ..registry import Page, chart, diagram, finding, links, section, table, text

section("chemistry", "Water chemistry",
        "Chloride from road salt and nitrate from fertilizer and sewage, measured with Salt Watch and Nitrate Watch "
        "strips at the chapter's creek and lake since 2024.", order=20)

CHEM_LABEL = C.CHAPTER_CHEM_SITES


def readings(db, parameter):
    return db.rows(f"""SELECT s.site_id, s.survey_date AS date, c.value FROM chemistry c JOIN usable_surveys s USING (survey_uid)
                       WHERE s.site_id IN ({CHEM}) AND c.parameter = '{parameter}' ORDER BY date""")


@finding("chemistry", "road-salt", "Road salt reaches the creek every winter", order=10, key=True)
def road_salt(db):
    cl = readings(db, "chloride")
    if not cl:
        return None
    creek_id, lake_id = list(CHEM_LABEL)
    creek = [r for r in cl if r["site_id"] == creek_id]
    month = lambda r: int(r["date"][5:7])
    summer = sorted(r["value"] for r in creek if month(r) in (6, 7, 8, 9))
    s_med = summer[len(summer) // 2] if summer else None
    winters = {}
    for r in creek:
        if month(r) in (12, 1, 2, 3):
            w = year(r["date"]) + (1 if month(r) == 12 else 0)
            winters[w] = max(winters.get(w, 0), r["value"])
    peak = max(winters.values())
    md = db.one("""SELECT round(median(c.value)) FROM chemistry c JOIN usable_surveys s USING (survey_uid)
                   WHERE c.protocol = 'salt' AND c.parameter = 'chloride' AND s.state = 'MD'""")
    wp = ", ".join(f"{w - 1}–{str(w)[2:]}: {v:.0f}" for w, v in sorted(winters.items()))
    spec = {"type": "time", "title": f"Chloride in Seneca Creek peaks at {peak:.0f} mg/L in winter, against about {s_med:.0f} in summer",
            "legend": [{"name": CHEM_LABEL[creek_id], "color": "accent"}, {"name": CHEM_LABEL[lake_id], "color": "grey"}],
            "y": {"min": 0, "max": 250, "ticks": [0, 50, 100, 150, 200, 250], "unit": "mg/L"},
            "refs": [{"y": 230, "label": "EPA chronic aquatic-life level, 230"}], "height": 300,
            "series": [{"color": c, "line": True, "r": 4, "points": [{"x": r["date"], "y": r["value"],
                        "tip": f"{CHEM_LABEL[s]}, {r['date']}: {r['value']:.0f} mg/L chloride"} for r in cl if r["site_id"] == s]}
                       for s, c in ((creek_id, "accent"), (lake_id, "grey"))]}
    return Page(refs=["cwh", "sos", "epa-chloride", "kaushal2005", "kaushal2018", "corsi2010"], 
        headline=f"Chloride in the creek climbs from about {s_med:.0f} mg/L in summer to winter peaks of {peak:.0f}, still below the EPA's 230.",
        status="watch",
        numbers=[(f"{peak:.0f} mg/L", "highest winter chloride in the creek"), (f"{md:.0f} mg/L", "Maryland Salt Watch median")],
        blocks=[text(f"Since {year(cl[0]['date'])} the chapter has tested its creek and lake for chloride with Salt Watch strips."),
                diagram(plates.salt("salt", peak, s_med, md), "Illustration of the path; the gauge uses the chapter's readings. The gill and ions in the lens are drawn far larger than true."),
                chart(spec, "Salt Watch chloride readings from the chapter's own sampling points. Dashed line: EPA chronic aquatic-life criterion for chloride, 230 mg/L."),
                text(f"Road salt shows up every winter: winter peaks were {wp}. All readings so far sit below the EPA's chronic "
                     f"aquatic-life level of 230 mg/L and below the Maryland Salt Watch median of {md:.0f} mg/L.",
                     "Two winters is too short for a trend; more years will show whether the peaks keep rising. Salt is a likely "
                     "suspect for the loss of sensitive animals, since mayflies and stoneflies are among the first to suffer."),
                links([("expected", "the loss of sensitive animals at Site 1")])])


@finding("chemistry", "nitrate", "Nitrate stays low", order=20)
def nitrate(db):
    no3 = readings(db, "nitrate")
    if not no3:
        return None
    rows = []
    for s, name in CHEM_LABEL.items():
        v = [r["value"] for r in no3 if r["site_id"] == s]
        if v:
            rows.append([name, len(v), f"{min(v):g}", f"{max(v):g}", f"{no3[0]['date'][:4]}–{no3[-1]['date'][:4]}"])
    creek_vals = sorted({r["value"] for r in no3 if r["site_id"] == list(CHEM_LABEL)[0]})
    return Page(refs=["cwh", "sos", "epa-nitrate"], 
        headline=f"Nitrate strips have read {' or '.join(f'{v:g}' for v in creek_vals)} mg/L at the creek on every visit.",
        status="good",
        blocks=[table([("Sampling point",), ("Readings", 1), ("Lowest, mg/L", 1), ("Highest, mg/L", 1), ("Years",)], rows),
                text("Test strips read in coarse colour steps, so a steady 2 means the creek sits in a low band rather than at exactly 2. "
                     "That is well below the EPA's 10 mg/L drinking-water limit for nitrate as nitrogen. Strips cannot show small "
                     "changes, so nitrate is unlikely to explain the loss of sensitive animals on this evidence.")])
