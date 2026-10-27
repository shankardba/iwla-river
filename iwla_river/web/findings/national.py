"""Findings from the national Clean Water Hub data and the expected-score model."""

from __future__ import annotations

from ..db import PROTO, fmt, pct
from ..registry import Page, chart, finding, links, section, table, text

section("national", "National picture",
        "What thousands of volunteer surveys across the country show, and the expected-score model trained on them "
        "that the chapter's sites are judged against.", order=40)


@finding("national", "paving", "Paved watersheds lose sensitive animals", order=10, key=True)
def paving(db):
    if not db.has("expected"):
        return None
    ib = db.rows("""
        WITH b AS (SELECT e.observed, e.site_id, c.ws_impervious_pct AS imp,
                     CASE WHEN imp < 2 THEN 0 WHEN imp < 5 THEN 1 WHEN imp < 10 THEN 2 WHEN imp < 15 THEN 3 WHEN imp < 25 THEN 4 ELSE 5 END AS bin
                   FROM expected e JOIN site_context c USING (site_id)
                   WHERE e.target = 'sensitive_share' AND c.ws_impervious_pct IS NOT NULL)
        SELECT bin, ['0–2%', '2–5%', '5–10%', '10–15%', '15–25%', '25% +'][bin + 1] AS label,
               count(*) AS surveys, count(DISTINCT site_id) AS sites, avg(observed) AS mean
        FROM b GROUP BY ALL ORDER BY bin""")
    ctx = db.context(467)
    ci = ctx.get("ws_impervious_pct")
    ch_bin = None if ci is None else 0 if ci < 2 else 1 if ci < 5 else 2 if ci < 10 else 3 if ci < 15 else 4 if ci < 25 else 5
    spec = {"type": "bars", "title": f"Sensitive animals make up {pct(ib[0]['mean'])} of groups found in near-natural watersheds and {pct(ib[-1]['mean'])} where a quarter is paved",
            "y": {"min": 0, "max": 0.5, "ticks": [0, 0.1, 0.2, 0.3, 0.4, 0.5], "fmt": "pct"},
            "xLabel": "share of the watershed that is paved or roofed", "height": 310,
            "cats": [{"label": r["label"], "sub": f"{fmt(r['sites'])} sites", "value": r["mean"], "valueLabel": pct(r["mean"]),
                      "color": "accent" if r["bin"] == ch_bin else "grey", "opacity": 1 if r["bin"] == ch_bin else 0.55,
                      "note": f"Great Seneca ({ci:.1f}%)" if r["bin"] == ch_bin else None,
                      "tip": f"{r['label']} paved: {pct(r['mean'])} sensitive, {fmt(r['surveys'])} surveys at {fmt(r['sites'])} sites"} for r in ib]}
    return Page(
        headline=f"Nationally, sensitive animals fall from {pct(ib[0]['mean'])} of groups found in near-natural watersheds to {pct(ib[-1]['mean'])} where a quarter or more is paved.",
        status="info",
        numbers=[(f"{ci:.1f}%", "of the chapter's watershed paved or roofed (2019)") if ci is not None else ("—", ""),
                 (f"{ctx.get('ws_forest_pct', 0):.0f}%", "of it forest")],
        blocks=[text("Stream ecologists call this the urban stream syndrome: the more of a watershed is paved or roofed, the faster "
                     "rain runs off it, carrying heat, salt and sediment, and the fewer pollution-sensitive animals live downstream."),
                chart(spec, "All usable biological surveys with watershed land cover (EPA StreamCat, NLCD 2019). Observed averages, not model output."),
                text(f"The watershed above the chapter's sites is {ci:.1f}% paved and roofed, in the band where losses usually start to "
                     "show. Paving there grew only from 11.8% to 12.8% between 2001 and 2019 (StreamCat), so the next step is to look for "
                     "local causes that land-cover maps miss: construction, stormwater outfalls, sewer leaks or a spill."),
                links([("model", "the model that turns this pattern into an expected value for each survey")])])


@finding("national", "model", "How the expected-score model works", order=20)
def model(db):
    if not db.has("model_metrics"):
        return None
    mm = db.rows("SELECT * FROM model_metrics")
    ms = next(m for m in mm if m["target"] == "sensitive_share")
    imp = db.rows("""SELECT "group", r2_drop FROM model_importance WHERE target = 'sensitive_share' AND r2_drop > -0.01 ORDER BY r2_drop DESC""")
    rain = ms["rain_coverage"] > 0.5
    spec = {"type": "hbars", "title": f"{imp[0]['group']} carries most of the prediction",
            "rows": [{"label": r["group"], "value": r["r2_drop"], "valueLabel": f"{r['r2_drop']:.2f}",
                      "color": "accent" if i == 0 else "grey", "opacity": 1 if i == 0 else 0.6} for i, r in enumerate(imp)]}
    return Page(
        headline=f"Trained on {fmt(ms['surveys'])} surveys at {fmt(ms['sites'])} sites, it explains {round(100 * ms['r2'])}% of the variation at sites it never saw.",
        status="info",
        numbers=[(f"{ms['r2']:.2f}", "held-out R², sensitive share"), (f"{max(0, ms['baseline_r2']):.2f}", "season and form alone")],
        blocks=[text("For every usable biological survey, the model predicts what it should find given its season, survey form, "
                     "watershed (paved and urban share, forest, farmland, soils, elevation, climate), "
                     f"{'rain and air temperature in the week before, ' if rain else ''}water temperature, flow and team. "
                     "It never sees the year, so change over time stays in the gap between observed and expected.",
                     "Every expected value comes from a version of the model that never saw any survey from that site (five folds "
                     "grouped by site), which is how a site is judged by what the rest of the country predicts for it."),
                table([("Predicts",), ("Surveys", 1), ("Sites", 1), ("Held-out R²", 1), ("Season and form only", 1), ("Typical error", 1)],
                      [[m["label"], fmt(m["surveys"]), fmt(m["sites"]), f"{m['r2']:.2f}", f"{max(0, m['baseline_r2']):.2f}",
                        f"{round(100 * m['mae'])} pts" if m["target"] == "sensitive_share" else f"{round(m['mae'])} percentile pts"] for m in mm]),
                chart(spec, "Drop in held-out accuracy (R²) when each group of inputs is scrambled; larger means the model leans on it more."),
                text(f"Rainfall in the week before each survey {'is included' if rain else 'is still being added'}. Volunteer data is "
                     "noisy, so an R² near 0.4 at unseen sites is useful: enough to set an expected range for each survey and to tell "
                     "a change in the stream from a change in the season or team."),
                links([("expected", "what the model says about the chapter's sites"), ("paving", "the land-cover pattern it relies on")])],
        method="scikit-learn HistGradientBoostingRegressor (500 iterations, learning rate 0.04, 15 leaves, at least 40 surveys per "
               "leaf); importance by scrambling each input group on held-out folds.")


@finding("national", "monitoring-growth", "Volunteer monitoring took off after 2017", order=30)
def monitoring_growth(db):
    rows = db.rows("""SELECT year(survey_date) AS year, protocol, count(*) AS n FROM usable_surveys
                      WHERE year(survey_date) >= 2000 GROUP BY ALL ORDER BY year, protocol""")
    if not rows:
        return None
    protos = sorted({r["protocol"] for r in rows}, key=lambda p: list(PROTO).index(p) if p in PROTO else 99)
    years = sorted({r["year"] for r in rows})
    tot = {y: sum(r["n"] for r in rows if r["year"] == y) for y in years}
    peak = max(tot, key=tot.get)
    step = 2000 if tot[peak] > 4000 else 500
    top = -(-tot[peak] // step) * step
    colors = ["c1", "c2", "c3", "c4", "accent", "grey"]
    spec = {"type": "stack", "title": f"Volunteer monitoring took off after 2017, peaking at {fmt(tot[peak])} surveys in {peak}",
            "legend": [{"name": PROTO.get(p, p), "color": colors[i % 6], "shape": "square"} for i, p in enumerate(protos)],
            "y": {"max": top, "ticks": list(range(0, top + 1, step)), "fmt": "comma"}, "height": 330,
            "bars": [{"label": str(y) if y % 5 == 0 else "", "segs": [{"v": next((r["n"] for r in rows if r["year"] == y and r["protocol"] == p), 0),
                      "color": colors[i % 6], "tip": f"{y}, {PROTO.get(p, p)}: {fmt(next((r['n'] for r in rows if r['year'] == y and r['protocol'] == p), 0))}"}
                      for i, p in enumerate(protos)]} for y in years]}
    bio = db.one("SELECT count(*) FROM usable_surveys WHERE protocol IN ('sos_bio', 'va_rocky', 'va_muddy')")
    total = db.one("SELECT count(*) FROM usable_surveys")
    return Page(
        headline=f"The Hub holds {fmt(total)} usable surveys; {fmt(bio)} are biological, enough to train a national model.",
        status="info",
        blocks=[chart(spec, "Usable surveys per year, all Hub sites, by survey form (2000 on)."),
                text("Salt Watch and Nitrate Watch kits, mailed free to volunteers, account for most of the growth since 2019. "
                     "The biological surveys, which take training and a net, grow more slowly but carry the ecology.")])
