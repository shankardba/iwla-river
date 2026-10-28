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
        "state lists of impaired waters, land cover, permits and census data.", order=45)


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
