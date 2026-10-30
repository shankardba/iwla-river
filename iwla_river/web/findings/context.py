"""Volunteer data in context: IWLA surveys checked against USGS, EPA, state and Census data.

Numbers come from context_results.json, written by `python -m iwla_river.context` (the script names every test).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..db import fmt
from ..registry import Page, chart, finding, links, section, table, text

RES = Path(__file__).with_name("context_results.json")

section("context", "In context",
        "The volunteer data checked against public measurements: agency laboratory chloride, professional bug surveys, "
        "state lists of impaired waters, land cover, permits and census data.", order=20)


def res(key):
    if not RES.exists():
        return None
    return json.loads(RES.read_text()).get(key)


def p_(p):
    if p is None:
        return "—"
    return "p < 0.001" if p < 0.001 else f"p = {p:.2g}" if p < 0.01 else f"p = {p:.2f}"


def ci(c, d=2):
    return f"95% CI {c[0]:.{d}f} to {c[1]:.{d}f}"


def inputs():
    r = json.loads(RES.read_text())["inputs"]
    return f"Clean Water Hub snapshot of {r['clean_water_hub_snapshot']}; joined public data as of {r['streams_dataset']}"


@finding("context", "chloride-check", "Volunteer chloride tracks agency lab chloride", order=10, key=True)
def chloride_check(db):
    v = res("chloride_validation")
    if not v:
        return None
    a, b = v["sos_chem"], v["salt"]
    rows = [[name, fmt(x["pairs"]), fmt(x["sites"]), fmt(x["watersheds"]), f"{x['log_r']:.2f} ({x['log_r_ci'][0]:.2f}–{x['log_r_ci'][1]:.2f})",
             f"{round(100 * x['within_factor_2'])}%", f"{x['median_ratio']:.2f}"]
            for name, x in (("SOS chemistry kit", a), ("Salt Watch strip", b))]
    return Page(refs=["cwh", "sos", "wqp", "wbd", "spearman", "efron1979", "wilcoxon1945"],
        headline=f"Where a state or federal agency measured chloride in the same small watershed within a week, volunteer SOS "
                 f"chemistry readings agree closely (correlation {a['log_r']:.2f}; {round(100 * a['within_factor_2'])}% within a "
                 f"factor of two); Salt Watch strips agree more loosely ({b['log_r']:.2f}).",
        status="good",
        numbers=[(f"{a['log_r']:.2f}", "SOS chemistry vs agency lab (log scale)"), (f"{b['log_r']:.2f}", "Salt Watch strip vs agency lab"),
                 (fmt(a["pairs"] + b["pairs"]), "matched readings")],
        blocks=[text("Volunteer chloride can only inform decisions if it measures what a laboratory would. Each volunteer reading "
                     "was paired with the median of agency laboratory chloride results reported to the Water Quality Portal from the "
                     "same 12-digit watershed (HUC12, about 100 km²) within seven days. Readings of exactly 0 and the one impossible "
                     "value were left out."),
                table([("Method",), ("Pairs", 1), ("Sites", 1), ("Watersheds", 1), ("Correlation (log), 95% CI", 1),
                       ("Within a factor of 2", 1), ("Median volunteer ÷ agency", 1)], rows,
                      "Correlation of log10 chloride; interval from 2,000 bootstrap resamples of whole watersheds."),
                text(f"The SOS chemistry kit's median ratio to the agency value is {a['median_ratio']:.2f}: no overall bias. Salt "
                     f"Watch strips read in coarse colour steps, so they scatter more. In winter they read higher than the agency "
                     f"results ({b['winter_vol_median']:.0f} vs {b['winter_agency_median']:.0f} mg/L median, {fmt(b['winter_pairs'])} "
                     f"pairs, Wilcoxon signed-rank {p_(b['winter_wilcoxon_p'])}), likely because volunteers test after storms and "
                     f"near roads while agencies sample on fixed schedules at fixed stations.",
                     "A watershed-and-week match is looser than a same-spot, same-hour match, so these correlations understate "
                     "how well the kits measure."),
                links([("chloride-sites", "how chloride is changing at long-record sites")])],
        method=f"Pairs: chloride_pairs in the joined dataset ({inputs()}). Pearson correlation of log10 values; Spearman rank "
               f"correlation {a['rho']:.2f} (SOS) and {b['rho']:.2f} (Salt Watch); cluster bootstrap by watershed; Wilcoxon "
               f"signed-rank test on winter log ratios. Code: iwla_river/context.py.")


@finding("context", "chloride-sites", "Chloride is rising at more sites than it is falling", order=20, key=True)
def chloride_sites(db):
    t = res("chloride_trend")
    if not t:
        return None
    n, up, dn = t["site_tests"], t["sites_rising_q05"], t["sites_falling_q05"]
    spec = {"type": "hbars", "title": f"{up} of {n} long-record sites show rising chloride, {dn} falling",
            "rows": [{"label": "Rising", "value": up, "valueLabel": fmt(up), "color": "bad"},
                     {"label": "Falling", "value": dn, "valueLabel": fmt(dn), "color": "good"},
                     {"label": "No clear trend", "value": n - up - dn, "valueLabel": fmt(n - up - dn), "color": "grey", "opacity": 0.6}]}
    return Page(refs=["cwh", "mann", "hirsch1982", "sen1968", "bh1995", "kaushal2005", "kaushal2018", "corsi2010"],
        headline=f"Of {n} sites with at least eight chloride readings over four or more years, {up} show a rising trend and "
                 f"{dn} a falling one after correcting for testing many sites at once.",
        status="watch",
        numbers=[(fmt(up), "sites rising"), (fmt(dn), "sites falling"), (f"+{t['rising_median_pct_per_year']:.0f}%", "a year, median at rising sites")],
        blocks=[chart(spec, "Seasonal Kendall test at each site on log chloride; false discovery rate held at 5% (Benjamini–Hochberg)."),
                text(f"Freshwater across the northern United States has been getting saltier for decades, mainly from road salt, "
                     f"and chloride above 230 mg/L harms stream animals. Among the volunteer sites with long enough records, rising "
                     f"sites outnumber falling ones {up} to {dn}; at the rising sites chloride climbs by a median of "
                     f"{t['rising_median_pct_per_year']:.0f}% a year.",
                     f"Across the whole network the picture is not significant (seasonal Kendall on monthly medians of each "
                     f"reading relative to its own site: {t['pct_per_decade']:+.0f}% a decade, {p_(t['sk_p'])}). That network figure "
                     f"mixes thousands of short-lived Salt Watch sites that join and leave, so the site-by-site count is the "
                     f"better measure of change.",
                     f"Data quality: {fmt(t['zero_readings'])} chloride readings are exactly 0, which a kit cannot read in a "
                     f"salted stream (most likely blanks or 'below detection'), and one reading is {fmt(t['max_reading'])} mg/L, "
                     f"about 28 times seawater. All of these were left out."),
                links([("chloride-check", "how well volunteer chloride matches agency labs"), ("development-salt", "whether salt or paving drives bug scores")])],
        method=f"{fmt(t['readings'])} readings at {fmt(t['sites'])} sites, {t['first']} to {t['last']} ({inputs()}). Per site: "
               f"seasonal Kendall test on log10 chloride with seasons as quarters, Sen slope; Benjamini–Hochberg q < 0.05. "
               f"Network: monthly median of each reading minus its site's median, months with 3+ readings. Code: iwla_river/context.py.")


@finding("context", "development-salt", "Paved land, more than winter salt, tracks low bug scores", order=30, key=True)
def development_salt(db):
    d = res("development_vs_salt")
    if not d:
        return None
    rows = [["Winter salt alone", f"{d['salt_alone_coef']:+.2f} per SD of salt", p_(d["salt_alone_p"])],
            ["Paving, with salt in the model", f"{d['between_imperv_coef']:+.3f} per point of paving ({10 * d['between_imperv_coef']:+.1f} per 10 points)", p_(d["between_imperv_p"])],
            ["Salt, with paving in the model", f"{d['between_salt_coef']:+.2f} per SD of salt", p_(d["between_salt_p"])],
            ["Saltier winter than usual, same watershed", f"{d['within_salt_coef']:+.2f} per SD (SE {d['within_salt_se']:.2f})", p_(d["within_salt_p"])]]
    return Page(refs=["cwh", "wqp", "nwis", "annual-nlcd", "wbd", "white1980", "cameron-miller2015", "walsh2005", "paul-meyer2001",
                      "corsi2010", "kaushal2018"],
        headline=f"Across {d['watersheds']} watersheds, saltier winters go with lower spring bug scores, but that link disappears "
                 f"once paved area is accounted for; paving remains a strong predictor ({p_(d['between_imperv_p'])}).",
        status="info",
        numbers=[(f"{d['corr_imperv_salt']:.2f}", "correlation of paving with winter salt"), (f"{10 * d['between_imperv_coef']:+.1f}", "SD of score per 10 points of paving"),
                 (fmt(d["watershed_years"]), "watershed-years")],
        blocks=[text("Road salt and pavement come together: the more a watershed is paved, the more salt goes on it. To separate "
                     "them, each watershed's winter salt was measured from agency laboratory chloride, USGS gauge conductance and "
                     "volunteer chloride (each on a log scale, standardised and averaged), and set against the next spring's bug "
                     "scores and the watershed's paved share from the annual national land cover maps."),
                table([("Model",), ("Change in spring score (SD)", 1), ("Test",)], rows,
                      "Scores standardised within each survey form (SOS, Virginia SOS) so both can be combined."),
                text(f"Paving and salt are strongly linked (r = {d['corr_imperv_salt']:.2f}), so on their own both look harmful. "
                     f"With both in the model, paving keeps its effect and salt adds nothing. Within the same watershed, a winter "
                     f"saltier than usual is followed by a slightly lower spring score, but not reliably "
                     f"({d['within_watersheds']} watersheds with two or more years, {p_(d['within_salt_p'])}).",
                     "This does not clear road salt. Salt is one of the ways paving harms streams, and spring bug surveys may miss "
                     "short winter spikes. It does mean the volunteer data cannot yet show a salt effect separate from development.")],
        method=f"Between watersheds: least squares on watershed means with heteroskedasticity-robust (HC1) standard errors. "
               f"Within: watershed and year effects removed by two-way demeaning, standard errors clustered by watershed. "
               f"Paving interpolated between the 5-yearly Annual NLCD maps. {inputs()}. Code: iwla_river/context.py.")


@finding("context", "impaired-biology", "State impairment listings match the bug surveys", order=40)
def impaired_biology(db):
    d = res("impaired_biology")
    if not d:
        return None
    label = {"va": ("Virginia SOS (volunteer)", "score 0–12"), "sos": ("Original SOS (volunteer)", "score"),
             "nrsa_VA": ("EPA NRSA, Virginia (professional)", "MMI 0–100"), "mbss_MD": ("Maryland MBSS (professional)", "IBI 1–5")}
    rows = [[label[k][0], f"{x['impaired_median']:g} vs {x['other_median']:g} ({label[k][1]})", f"{fmt(x['impaired_sites'])} / {fmt(x['other_sites'])}", p_(x["p"])]
            for k, x in d.items() if k in label]
    va = d["va"]
    return Page(refs=["cwh", "attains", "nrsa", "mbss", "wbd", "mann-whitney", "va-deq-partners"],
        headline=f"Volunteer sites in watersheds the state lists as impaired for aquatic life score lower ({va['impaired_median']:g} vs "
                 f"{va['other_median']:g} on the Virginia SOS scale), and professional surveys show the same gap.",
        status="info",
        numbers=[(f"{va['impaired_median']:g} vs {va['other_median']:g}", "Virginia SOS median, listed vs not"), (fmt(va["impaired_sites"]), "volunteer sites in listed watersheds")],
        blocks=[table([("Survey",), ("Median: listed vs other watersheds",), ("Sites", 1), ("Mann–Whitney",)], rows,
                      "Listed = a water in the HUC12 is impaired for biology (macroinvertebrates, fish or aquatic life) in EPA ATTAINS."),
                text("Virginia's Department of Environmental Quality accepts volunteer data for its assessments, so part of the "
                     "Virginia agreement could be circular: the listing may rest on the same volunteer surveys. The professional "
                     "surveys break that circle. EPA's own national survey and Maryland's state survey also score lower in listed "
                     "watersheds, so the listings reflect real biological damage.",
                     f"Original SOS sites show no gap ({d['sos']['impaired_median']:g} vs {d['sos']['other_median']:g}, {p_(d['sos']['p'])}); "
                     "its coarser count of animal groups may be less able to separate impaired from healthy streams.")],
        method=f"Each site's median score; watersheds flagged from the ATTAINS national geospatial snapshot (January 2025). "
               f"Two-sided Mann–Whitney U tests. {inputs()}. Code: iwla_river/context.py.")


@finding("context", "volunteers-vs-professionals", "Volunteers and professionals mostly agree, but volunteers rate generously", order=50, key=True)
def volunteers_vs_professionals(db):
    d = res("volunteer_vs_professional")
    if not d:
        return None
    show = [("va_rocky|mbss|within 1 km", "Virginia SOS vs Maryland MBSS, within 1 km"),
            ("va_rocky|nrsa|same watershed", "Virginia SOS vs EPA NRSA, same watershed"),
            ("va_rocky|mbss|same watershed", "Virginia SOS vs Maryland MBSS, same watershed"),
            ("sos_bio|mbss|same watershed", "Original SOS vs Maryland MBSS, same watershed"),
            ("sos_bio|nrsa|same watershed", "Original SOS vs EPA NRSA, same watershed"),
            ("stream_waders|mbss|within 1 km", "Benchmark: Maryland Stream Waders vs MBSS, within 1 km")]
    rows = [[lab, fmt(x["pairs"]), f"{x['rho']:.2f} ({p_(x['rho_p'])})", f"{round(100 * x['same_class'])}%", f"{x['kappa_w']:.2f}",
             f"{x['vol_higher']} / {x['vol_lower']}"] for k, lab in show if (x := d.get(k))]
    near, nr, wd = d["va_rocky|mbss|within 1 km"], d["va_rocky|nrsa|same watershed"], d["stream_waders|mbss|within 1 km"]
    return Page(refs=["cwh", "sos", "nrsa", "mbss", "stream-waders", "wbd", "spearman", "cohen1968", "engel-voshell2002"],
        headline=f"Where a Virginia SOS survey sits within 1 km of a Maryland state survey, the two agree on condition "
                 f"{round(100 * near['same_class'])}% of the time (weighted kappa {near['kappa_w']:.2f}), as well as Maryland's own trained "
                 f"volunteers do; volunteers more often call a stream healthier than the professionals.",
        status="info",
        numbers=[(f"{near['rho']:.2f}", "rank correlation, Virginia SOS vs MBSS within 1 km"), (f"{wd['rho']:.2f}", "Stream Waders vs MBSS (benchmark)"),
                 (f"{nr['vol_good_pro_fair_or_poor']} of {nr['vol_good']}", "volunteer 'Good' rated Fair or Poor by EPA NRSA")],
        blocks=[table([("Comparison",), ("Pairs", 1), ("Rank correlation", 1), ("Same condition class", 1), ("Weighted kappa", 1),
                       ("Volunteer higher / lower", 1)], rows,
                      "Condition classes Good, Fair, Poor from each program's own thresholds. Kappa: 0 = chance agreement, 1 = perfect."),
                text("Professional and volunteer surveys rarely visit the same spot on the same day, so most pairs are matched by "
                     "watershed and year, which adds disagreement that has nothing to do with skill. The closest matches (within "
                     "1 km) are few: 18 pairs at 7 sites. They agree as well as Maryland's trained Stream Waders volunteers do "
                     "with the state's professionals, which is the fairest benchmark.",
                     "The Virginia SOS method, built to track professional assessments, agrees far better than the original SOS "
                     "count of animal groups, which barely tracks the professional surveys. When volunteers and professionals "
                     "differ, volunteers usually rate the stream higher, as earlier studies of volunteer biomonitoring found.")],
        method=f"Pairs from pro_pairs and md_volunteer_pairs in the joined dataset ({inputs()}). Spearman rank correlation of "
               f"scores; Cohen's weighted kappa (linear weights) on condition classes. Code: iwla_river/context.py.")


@finding("context", "monitoring-gaps", "Most high-need watersheds have no volunteer monitor", order=60, key=True)
def monitoring_gaps(db):
    g = res("monitoring_gaps")
    if not g:
        return None
    cov = g["coverage_by_need"]
    spec = {"type": "bars", "title": "Watersheds with more pressure are more often monitored, but coverage stays low",
            "y": {"min": 0, "max": 0.06, "ticks": [0, 0.02, 0.04, 0.06], "fmt": "pct"}, "xLabel": "need score (count of pressures)",
            "height": 280, "cats": [{"label": k, "sub": f"{fmt(v[0])} watersheds", "value": v[1] / v[0], "valueLabel": f"{100 * v[1] / v[0]:.1f}%",
                                     "color": "accent", "tip": f"Need {k}: {fmt(v[1])} of {fmt(v[0])} watersheds have an active bug site"} for k, v in cov.items()]}
    top = [[w, f"{km:.0f} km", n] for w, _, km, n in g["top_recruitable"]]
    return Page(refs=["cwh", "wbd", "attains", "echo", "annual-nlcd", "usmin", "acs", "mann-whitney"],
        headline=f"Of {fmt(g['high_need'])} watersheds with five or more pressures, {fmt(g['high_need_unmonitored'])} have no active "
                 f"volunteer bug site; {fmt(g['high_need_unmonitored_within_25km'])} of those are within 25 km of one.",
        status="concern",
        numbers=[(fmt(g["with_active_bug_site"]), f"of {fmt(g['watersheds'])} watersheds with an active bug site"),
                 (fmt(g["high_need_unmonitored"]), "high-need watersheds unmonitored"), (fmt(g["high_need_unmonitored_within_25km"]), "of them within 25 km of a volunteer")],
        blocks=[text("Every small watershed (HUC12) in the river basins where IWLA volunteers work was scored for need: one point "
                     "each for any impaired water, a salt impairment, a major discharge permit, a discharger in significant "
                     "noncompliance, 10% or more paved, 5 or more points of new paving since 1985 and coal or hard-rock mine "
                     "features, and two for impaired biology."),
                chart(spec, "Share of watersheds with an IWLA bug site surveyed since 2021, by need score."),
                text(f"Monitored high-need watersheds are wealthier than unmonitored ones (median household income "
                     f"${fmt(g['income_monitored_high_need'])} vs ${fmt(g['income_unmonitored_high_need'])}, {p_(g['income_p'])}). "
                     f"Within 25 km of an active volunteer the gap shrinks (${fmt(g['income_near_monitored'])} vs "
                     f"${fmt(g['income_near_unmonitored'])}, {p_(g['income_near_p'])}), so it mostly follows where volunteers live."),
                table([("High-need watershed with no volunteer",), ("Nearest active site", 1), ("Need score", 1)], top,
                      "The closest unmonitored high-need watersheds: candidates for recruiting nearby volunteers.")],
        method=f"{fmt(g['watersheds'])} HUC12s from the USGS Watershed Boundary Dataset; pressures from EPA ATTAINS, EPA ECHO, "
               f"Annual NLCD and USGS USMIN; income from ACS 2020–2024 tracts. Mann–Whitney U tests. {inputs()}. Code: iwla_river/context.py.")


@finding("context", "restoration", "Stream restoration: no gain beyond what a placebo shows", order=70)
def restoration(db):
    r = res("restoration")
    if not r or "did_mean" not in r.get("real", {}):
        return None
    a, p = r["real"], r["placebo"]
    rows = [["At completion", fmt(a["projects"]), f"{a['treated_change']:+.2f}", f"{a['control_change']:+.2f}", f"{a['did_mean']:+.2f} ({ci(a['did_ci'])})"],
            ["Placebo: 5 years earlier", fmt(p["projects"]), f"{p['treated_change']:+.2f}", f"{p['control_change']:+.2f}", f"{p['did_mean']:+.2f} ({ci(p['did_ci'])})"]]
    return Page(refs=["cwh", "restoration", "efron1979", "barnett2005", "bernhardt2005"],
        headline=f"Virginia SOS scores near completed stream restorations rise {a['did_mean']:+.2f} points more than at comparison "
                 f"sites, but a fake completion date five years earlier shows a rise just as large ({p['did_mean']:+.2f}).",
        status="info",
        numbers=[(f"{a['did_mean']:+.2f}", "gain vs comparison sites"), (f"{p['did_mean']:+.2f}", "same test with a fake date"),
                 (f"{a['treated_start']:.1f} vs {a['control_start']:.1f}", "starting scores, restored vs comparison")],
        blocks=[table([("Test",), ("Projects", 1), ("Change near project", 1), ("Change at comparison sites", 1), ("Difference", 1)], rows,
                      "Mean Virginia SOS score 1–5 years after minus 1–5 years before; sites within 5 km of a project; comparison "
                      "sites in the same state with no project of any kind within 5 km."),
                text(f"Sites near restorations start far lower ({a['treated_start']:.1f} vs {a['control_start']:.1f} on a 0–12 "
                     f"scale), and low scores tend to drift back up whatever happens. The placebo test, with each project's date "
                     f"moved five years earlier, shows that drift: the gain appears before any work was done.",
                     "So the volunteer data cannot show a restoration benefit. That is not proof restorations fail. Many aim at "
                     "channel stability or nutrient credits rather than stream animals, and recovery can take longer than five years.")],
        method=f"Completed stream restoration projects 1995–2022 with a place and year; difference in differences with "
               f"comparison sites; 95% intervals from 2,000 bootstrap resamples of projects. {inputs()}. Code: iwla_river/context.py.")


@finding("context", "enrichment", "What each public dataset added", order=5)
def enrichment(db):
    e = res("enrichment")
    if not e:
        return None
    rows = [
        ["Watershed Boundary Dataset (USGS, NRCS)", "The 12-digit watershed (HUC12) of every site: the key every other dataset joins on", f"{fmt(e['watersheds_with_sites'])} watersheds with sites; {fmt(e['gap_watersheds'])} in the basins studied"],
        ["NHDPlus V2 and NLDI (USGS)", "The stream segment (COMID) under each public site", f"{fmt(e['sites_public'])} public sites"],
        ["EPA StreamCat", "Watershed roads, permits, mines, dams, septic, fertilizer and manure for public sites", f"{fmt(e['streamcat_catchments'])} catchments"],
        ["USGS Water Data (NWIS)", "Daily streamflow and conductance: was the creek high, or had it stormed, before each survey", f"{fmt(e['usgs_gauges'])} gauges; {fmt(e['surveys_with_flow'])} surveys with flow"],
        ["Water Quality Portal", "Agency laboratory chloride to check volunteer kits against", f"{fmt(e['wqp_stations'])} stations; {fmt(e['chloride_pairs'])} matched readings"],
        ["Annual NLCD 1.2 (USGS)", "Share of each watershed paved or built, year by year", f"{e['nlcd_years']} years × {fmt(e['nlcd_watersheds'])} watersheds"],
        ["EPA ATTAINS", "State lists of impaired waters, including impaired biology and salt", "every watershed studied"],
        ["EPA ECHO", "Discharge permits and serious noncompliance", "every watershed studied"],
        ["USGS USMIN", "Coal and hard-rock mine features", "every watershed studied"],
        ["Census ACS 2020–2024", "Population, median household income and poverty", "every watershed studied"],
        ["EPA NRSA, Maryland MBSS, Stream Waders", "Professional (and state volunteer) bug surveys to compare with IWLA", f"{fmt(e['prof_visits'])} visits"],
        ["County and state project records, American Rivers", "Completed stream restorations, pond retrofits and dam removals with a year", f"{fmt(e['restoration_events'])} projects"],
        ["EPA Section 319 (GRTS)", "Nonpoint-source projects by watershed", f"{fmt(e['epa319_projects'])} projects"],
        ["Open-Meteo (ERA5)", "Rain and air temperature in the week before each survey", "every survey"],
    ]
    return Page(refs=["cwh", "sos", "wbd", "nhdplus", "nldi", "streamcat", "nwis", "wqp", "annual-nlcd", "attains", "echo", "usmin",
                      "acs", "nrsa", "mbss", "stream-waders", "restoration", "epa319", "openmeteo", "era5"],
        headline=f"The {fmt(e['sites'])} Save Our Streams sites were joined to 20 public datasets from USGS, EPA, the Census Bureau, "
                 f"Maryland and county governments, so each survey can be read against its watershed, its weather and other "
                 f"people's measurements.",
        status="info",
        numbers=[("20", "public datasets joined"), (fmt(e["watersheds_with_sites"]), "watersheds with IWLA sites"),
                 (fmt(e["gap_watersheds"]), "watersheds compared in all")],
        blocks=[table([("Dataset",), ("What it adds",), ("Coverage",)], rows,
                      "Full citations for every dataset are listed under Sources below and on the References page."),
                text("Every join goes through the watershed code or the stream segment, never a home address. Kit and tap sites, "
                     "which are often homes, join by watershed only, and nothing site-level from them is published.",
                     "The joining was done in a separate, private workbench; this site shows only the aggregate results."),
                links([("chloride-check", "volunteer chloride against agency labs"), ("development-trend", "paving over time"),
                       ("monitoring-gaps", "watersheds with no volunteer monitor")])],
        method=f"{inputs()}. Code for the statistics: iwla_river/context.py.")


@finding("context", "development-trend", "Paving keeps spreading, fastest where volunteers work", order=35)
def development_trend(db):
    t = res("development_trend")
    if not t:
        return None
    mi, mo = t["median_iwla"], t["median_other"]
    yrs = t["years"]
    spec = {"type": "time", "title": "Median share paved, watersheds with and without IWLA bug sites",
            "legend": [{"name": "With IWLA bug sites", "color": "accent"}, {"name": "Other watersheds in the same basins", "color": "grey"}],
            "y": {"min": 0, "max": 2.5, "ticks": [0, 0.5, 1, 1.5, 2, 2.5], "unit": "%"}, "height": 280,
            "x": {"from": f"{yrs[0]}-01-01", "to": f"{yrs[-1] + 1}-01-01"},
            "series": [{"color": c, "line": True, "r": 3.5, "points": [{"x": f"{y}-07-01", "y": m[str(y)],
                        "tip": f"{y}: median {m[str(y)]:.2f}% paved ({name})"} for y in yrs]}
                       for m, c, name in ((mi, "accent", "with IWLA sites"), (mo, "grey", "other watersheds"))]}
    return Page(refs=["cwh", "annual-nlcd", "wbd", "cameron-miller2015", "walsh2005", "paul-meyer2001"],
        headline=f"The median watershed with an IWLA bug site went from {mi[str(yrs[0])]:.1f}% to {mi[str(yrs[-1])]:.1f}% paved between "
                 f"{yrs[0]} and {yrs[-1]}, gaining more than other watersheds nearby ({t['iwla_gain_median']:+.1f} vs "
                 f"{t['other_gain_median']:+.2f} points); within a watershed, bug scores have not yet tracked that growth.",
        status="watch",
        numbers=[(f"{mi[str(yrs[0])]:.1f}% → {mi[str(yrs[-1])]:.1f}%", f"median paved, IWLA watersheds, {yrs[0]}–{yrs[-1]}"),
                 (f"{round(100 * t['iwla_gain5_share'])}%", "of IWLA watersheds gained 5+ points of paving"),
                 (f"p = {t['within_imperv_p']:.2f}", "score change as a watershed paves")],
        blocks=[chart(spec, f"USGS Annual NLCD impervious surface averaged over each 12-digit watershed; {t['n_years']} of the 41 "
                            f"annual maps so far. {fmt(t['iwla_watersheds'])} watersheds with IWLA bug surveys, "
                            f"{fmt(t['other_watersheds'])} others in the same river basins."),
                text(f"Volunteers monitor where people live, so their watersheds are more built up to begin with and are being "
                     f"built up faster. {round(100 * t['iwla_gain5_share'])}% of them gained five or more percentage points of "
                     f"paving since {yrs[0]}, and {round(100 * t['iwla_gain10_share'])}% gained ten or more.",
                     f"Between watersheds, more paving goes with lower bug scores (see the salt and development page). Within "
                     f"a watershed over time, the change is too small and slow to show yet: comparing each watershed with itself "
                     f"across years ({fmt(t['within_watersheds'])} watersheds, {fmt(t['within_rows'])} watershed-years), spring "
                     f"scores move {t['within_imperv_coef']:+.3f} standard deviations per point of new paving (p = "
                     f"{t['within_imperv_p']:.2f}). Most of these watersheds gained under one point in the years volunteers "
                     f"surveyed them."),
                links([("development-salt", "paved land and winter salt against bug scores"), ("enrichment", "every dataset joined")])],
        method=f"Annual NLCD fractional impervious, pixels averaged inside each HUC12 outline. Within-watershed test: spring "
               f"scores (SOS and Virginia forms on one standardised scale) and paving with watershed and year means removed, "
               f"least squares with standard errors clustered by watershed; watersheds with three or more surveyed years. "
               f"{inputs()}. Code: iwla_river/context.py.")


@finding("context", "storm-timing", "A storm the week before does not change a site's score", order=37)
def storm_timing(db):
    t = res("storm_timing")
    if not t:
        return None
    return Page(refs=["cwh", "nwis", "cameron-miller2015"],
        headline=f"Comparing each site with itself, surveys taken in the week after high water score the same as calm-week "
                 f"surveys ({t['within_storm_coef']:+.3f} standard deviations, 95% CI {t['within_storm_ci'][0]:+.2f} to "
                 f"{t['within_storm_ci'][1]:+.2f}).",
        status="good",
        numbers=[(fmt(t["surveys"]), "surveys with a gauge reading"), (fmt(t["sites"]), "sites surveyed both after storms and in calm weeks"),
                 (f"{round(100 * t['storm_share'])}%", "of those surveys followed high water")],
        blocks=[text(f"A spate can scour animals off the stream bed, so a survey soon after one might undercount them. Each bug "
                     f"survey was matched to the nearest USGS stream gauge in its watershed; a storm week is one where daily flow "
                     f"reached the top 10% for that gauge in the seven days before.",
                     f"Taken at face value, post-storm surveys score lower ({t['raw_storm_z']:+.2f} vs {t['raw_calm_z']:+.2f} "
                     f"standard deviations). That gap comes from which sites and years get stormy, not from the storm itself: "
                     f"once each site is compared with itself and year-to-year swings are removed, it disappears (p = "
                     f"{t['within_storm_p']:.2f}). On this evidence, surveying soon after high water does not bias a site's score.")],
        method=f"Flow percentile of the nearest gauge in the same HUC12 (else HUC10), from USGS daily values. Scores standardised "
               f"within each form (SOS, Virginia SOS). Site and year means removed; least squares with standard errors clustered "
               f"by site; sites with both storm and calm surveys. {inputs()}. Code: iwla_river/context.py.")


def _scope(states):
    named = [f"{s} {round(100 * share)}%" for s, _, share in states if s != "unknown"][:3]
    return ", ".join(named)


def _q(v):
    """q-values near the 0.05 cut-off get three decimals so a borderline result is not shown as passing."""
    return f"q = {v:.3f}" if 0.03 < v < 0.07 else f"q = {v:.2g}"


@finding("context", "site-visits", "Three surveys capture most of what a site is", order=80, key=True)
def site_visits(db):
    a = res("site_reliability")
    if not a:
        return None
    rel = a["reliability"]
    spec = {"type": "bars", "title": "How well the average of a site's surveys predicts its long-run average",
            "y": {"min": 0, "max": 1, "ticks": [0, 0.25, 0.5, 0.75, 1], "fmt": "int"}, "xLabel": "surveys averaged",
            "height": 280, "cats": [{"label": k, "sub": f"{v[1]:.2f}–{v[2]:.2f}", "value": v[0], "valueLabel": f"{v[0]:.2f}",
                                     "color": "accent", "tip": f"{k} survey{'s' if k != '1' else ''}: reliability {v[0]:.2f} (95% CI {v[1]:.2f}–{v[2]:.2f})"}
                                    for k, v in rel.items()]}
    return Page(refs=["cwh", "sos", "laird-ware1982", "statsmodels", "shrout-fleiss1979", "spearman1910", "brown1910", "efron1979"],
        headline=f"{round(100 * a['icc'])}% of the variation in a bug survey's share of sensitive animals is the site itself, "
                 f"so the average of {a['visits_for_0_8']} surveys predicts a site's long-run average with reliability "
                 f"{rel['3'][0]:.2f}; past about six surveys, more visits add little.",
        status="info",
        numbers=[(f"{a['icc']:.2f}", f"share of variation between sites (95% CI {a['icc_lo']:.2f} to {a['icc_hi']:.2f})"),
                 (f"{rel['3'][0]:.2f}", "reliability of a 3-survey average"),
                 (fmt(a["sites_with_1_visit"]), f"of {fmt(a['sites'])} sites surveyed only once")],
        blocks=[chart(spec, "Reliability: the correlation expected between the average of that many surveys and the site's "
                            "true long-run average. Labels under the bars: 95% intervals from resampling whole sites."),
                text(f"A linear mixed model gives every site its own baseline and separates two kinds of variation: between "
                     f"sites (one stream is simply richer than another) and from one survey to the next at the same site "
                     f"(season, weather, which riffle was kicked, who sorted the net). Between sites is "
                     f"{round(100 * a['icc'])}% of the total once the season is allowed for.",
                     f"For running a program, that means a single survey already says a fair amount about a site "
                     f"(reliability {rel['1'][0]:.2f}), {a['visits_for_0_8']} surveys reach 0.8 and {a['visits_for_0_9']} reach 0.9. "
                     f"Half the sites here have {a['median_visits_per_site']:.0f} surveys or fewer, and {fmt(a['sites_with_1_visit'])} "
                     f"have one. Bringing a once-surveyed site up to three adds more than taking a well-surveyed site from ten to twenty. "
                     f"Detecting change over time is a different question that needs more visits; see the trend findings."),
                text(f"The surveys are the {fmt(a['surveys'])} bug surveys with a sensitive-animal share, at {fmt(a['sites'])} sites "
                     f"({_scope(a['states'])}). Most come from Virginia, which runs the largest volunteer bug program.")],
        method=f"Linear mixed model, sensitive share ~ season, random intercept per site, fitted by REML (statsmodels). "
               f"Intraclass correlation = between-site variance / total. Reliability of a k-survey average by the Spearman–Brown "
               f"formula. 95% intervals from {a['boot_rounds']} bootstrap resamples of whole sites. {inputs()}. "
               f"Code: iwla_river/survey_models.py.")


@finding("context", "maps-vs-local", "Maps predict about half of why sites differ; the rest is local", order=82, key=True)
def maps_vs_local(db):
    b = res("mapped_vs_local")
    if not b:
        return None
    rows = [[lab, f"{x['r2']:.2f} ({x['r2_lo']:.2f}–{x['r2_hi']:.2f})", f"{x['site_r2']:.2f} ({x['site_r2_lo']:.2f}–{x['site_r2_hi']:.2f})"]
            for lab, x in (("All 20 inputs: land, pollution, flow, weather, season, state", b["all"]),
                           ("Land and pollution only", b["land_only"]), ("Share paved alone", b["paved_only"]),
                           ("Road density alone", b["road_only"]))]
    al = b["all"]
    return Page(refs=["cwh", "sos", "streamcat", "annual-nlcd", "echo", "attains", "usmin", "nwis", "openmeteo", "era5",
                      "lightgbm", "sklearn", "spearman"],
        headline=f"Mapped land, pollution, flow and weather data predict {round(100 * al['site_r2'])}% of the differences between "
                 f"sites' average share of sensitive animals at sites the model never saw; most of the rest is local, and only a "
                 f"survey finds it.",
        status="info",
        numbers=[(f"{al['site_r2']:.2f}", "R² for site averages at unseen sites"), (f"{al['r2']:.2f}", "R² for single surveys"),
                 (f"{b['paved_only']['site_r2']:.2f}", "share paved alone, site averages")],
        blocks=[table([("Inputs",), ("Single surveys, R² (range)", 1), ("Site averages, R² (range)", 1)], rows,
                      f"R² on held-out sites: every survey of a site is held out together, so the model is always predicting "
                      f"places it has not seen. Range across {b['repeats']} repeats of {b['folds']}-fold cross-validation. Site "
                      f"averages use the {fmt(b['sites_3_plus'])} sites with 3 or more surveys."),
                text("Most of what the maps predict comes from land and pollution; flow, recent rain, heat and season add "
                     "little. Paving alone gets most of the way. Road density alone does less well, and the two largely measure "
                     f"the same development (rank correlation {b['road_paved_rho']:.2f}), so neither should be read as the cause.",
                     "The half the maps miss is what makes two streams in similar watersheds different: shade and banks, "
                     "a culvert, a spring, a recent spill. That part can only be found by sampling, and it is where volunteer "
                     "surveys add information that no national dataset has. A smaller part of what is missed is plain survey-to-survey "
                     "noise: even a perfect map could not predict an average of only a few surveys exactly "
                     "(see how many surveys it takes to know a site).")],
        method=f"LightGBM gradient-boosted trees (300 trees) predicting each survey's sensitive share from {b['inputs']} inputs "
               f"(StreamCat road density, septic, fertiliser and manure; Annual NLCD paving; ECHO permits; ATTAINS impairments; "
               f"USMIN mines; USGS gauge flow percentile; Open-Meteo rain and heat; season; state). Cross-validation grouped by "
               f"site (scikit-learn GroupKFold), {b['repeats']} shuffled repeats. Spearman rank correlation for road density "
               f"vs paving. {fmt(b['surveys'])} surveys at {fmt(b['sites'])} sites. {inputs()}. Code: iwla_river/survey_models.py.")


@finding("context", "watershed-types", "Urban watersheds stand apart; livestock watersheds score like low-pressure ones", order=84, key=True)
def watershed_types(db):
    w = res("watershed_types")
    if not w:
        return None
    T = {t["name"]: t for t in w["types"]}
    order = [n for n in ("low-pressure", "livestock", "mining", "cropland", "urban") if n in T] + [n for n in T if n not in
             ("low-pressure", "livestock", "mining", "cropland", "urban")]
    q = {frozenset((a, b)): qq for a, b, _, qq in w["pairs"]}
    lp = "low-pressure"
    pr = lambda t: t["profile"]
    rows = [[n.capitalize(), fmt(T[n]["watersheds"]), f"{pr(T[n])['impervious_at_survey']:.0f}%", f"{pr(T[n])['npdes_permits']:.0f}",
             f"{pr(T[n])['fertilizer_upstream']:.0f}", f"{pr(T[n])['manure_upstream']:.0f}", f"{pr(T[n])['mine_features']:.0f}",
             f"{round(100 * T[n]['share_median'])}%", "—" if n == lp else _q(q[frozenset((n, lp))]),
             f"{T[n]['stability']:.2f}", ", ".join(s for s, _ in T[n]["states"] if s != "unknown")] for n in order]
    u, lv, cr = T.get("urban"), T.get("livestock"), T.get("cropland")
    return Page(refs=["cwh", "sos", "wbd", "streamcat", "annual-nlcd", "echo", "attains", "usmin", "lloyd1982", "rousseeuw1987",
                      "hubert-arabie1985", "hennig2007", "sklearn", "kruskal", "mann-whitney", "bh1995"],
        headline=f"Grouped by their pressures alone, {fmt(w['watersheds'])} small watersheds fall into {w['k']} stable types: urban "
                 f"watersheds have the fewest sensitive animals ({round(100 * u['share_median'])}% vs "
                 f"{round(100 * T[lp]['share_median'])}% in low-pressure ones), while livestock watersheds are no different from "
                 f"low-pressure ones.",
        status="concern",
        numbers=[(f"{round(100 * u['share_median'])}%", "sensitive share, urban watersheds"),
                 (f"{round(100 * T[lp]['share_median'])}%", "low-pressure watersheds"),
                 (f"{round(100 * lv['share_median'])}%", "livestock watersheds")],
        blocks=[table([("Type",), ("HUC12s", 1), ("Paved", 1), ("Permits", 1), ("Fertiliser", 1), ("Manure", 1), ("Mine features", 1),
                       ("Sensitive share", 1), ("vs low-pressure", 1), ("Stability", 1), ("Main states",)], rows,
                      "Medians per type. Fertiliser and manure: StreamCat kg N per hectare per year upstream. Stability: average "
                      "Jaccard overlap when the watersheds are re-clustered from random 80% subsets (above 0.75 is dependable). "
                      "q: Benjamini–Hochberg across all pairs of types."),
                text(f"The types come from pressures only: paving, road density, discharge permits, mine features, impaired "
                     f"waters, septic systems, fertiliser and manure. The bug results were not used to form them, so comparing "
                     f"their streams afterwards is a fair test. They differ (Kruskal–Wallis H = {w['kruskal_h']}, {p_(w['kruskal_p'])}).",
                     f"Urban watersheds ({pr(u)['impervious_at_survey']:.0f}% paved, {pr(u)['npdes_permits']:.0f} permits) have the "
                     f"lowest share. Livestock watersheds, with heavy manure inputs but little paving, score as well as low-pressure "
                     f"ones (q = {q[frozenset(('livestock', lp))]:.2f}). That is a result about these {fmt(lv['watersheds'])} mostly "
                     f"Virginia watersheds, not a finding that manure does no harm: StreamCat's manure figure is a county-based estimate.",
                     (f"Mining watersheds ({fmt(T['mining']['watersheds'])}, with many mapped mine features and permits) sit right at "
                      f"the line against low-pressure ones ({_q(q[frozenset(('mining', lp))])}) and are the least stable type "
                      f"({T['mining']['stability']:.2f}); treat them as tentative." if "mining" in T else ""),
                     f"Cropland watersheds are lower too, but all {fmt(cr['watersheds'])} are in "
                     f"{', '.join(s for s, _ in cr['states'])}, where stream animals differ from the East; region and farming "
                     f"cannot be told apart here." if cr else ""),
                links([("development-salt", "paving and winter salt"), ("maps-vs-local", "how much maps predict at all")])],
        method=f"HUC12 medians of 8 pressures for watersheds with {w['min_surveys']} or more bug surveys, scaled by median and "
               f"interquartile range. k-means (scikit-learn) with k chosen by silhouette (k = {w['k']}). Stability from "
               f"{w['rounds']} re-clusterings of random 80% subsets (mean adjusted Rand index {w['ari_mean']:.2f}; Jaccard per type). "
               f"Sensitive share compared by Kruskal–Wallis, then Mann–Whitney U for each pair with BH q-values. {inputs()}. "
               f"Code: iwla_river/survey_models.py.")
