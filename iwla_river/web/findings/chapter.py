"""Findings about the Rockville Chapter's own sites on Great Seneca Creek."""

from __future__ import annotations

from ..db import CHAPTER, LABEL, PROTO, fmt, mean, pct, pfmt, season, verdict_pill, year
from ..diagrams import plates
from ..registry import Page, chart, diagram, finding, links, pill, section, table, text

section("chapter", "Great Seneca Creek",
        "The Rockville Chapter's two monitoring sites on Great Seneca Creek in Germantown, Maryland, "
        "surveyed since 2005: how stream health has moved, which animals are changing and how the creek "
        "compares with what its setting predicts.", order=10)

SITE_COLOR = {467: "accent", 468: "grey"}
LEGEND_SITES = [{"name": "Site 1", "color": "accent"}, {"name": "Site 2", "color": "grey"}]


@finding("chapter", "score-trend", "The score has held steady", order=10, key=True)
def score_trend(db):
    sos = db.sos()
    if not sos:
        return None
    early = [r["total"] for r in sos if r["date"] < "2013-01-01"]
    late = [r["total"] for r in sos if r["date"] >= "2013-01-01"]
    mE, mL = mean(early), mean(late)
    by_date = {}
    for r in sos:
        by_date.setdefault(r["date"], {})[r["site_id"]] = r["total"]
    pairs = [abs(v[467] - v[468]) for v in by_date.values() if 467 in v and 468 in v]
    first, last = year(sos[0]["date"]), year(sos[-1]["date"])
    gaps = [y for y in range(first, last + 1) if not any(year(r["date"]) == y for r in sos)]
    spec = {
        "type": "time", "title": f"Scores held near {mE:.1f} before 2013 and {mL:.1f} since",
        "legend": LEGEND_SITES, "y": {"min": 0, "max": 30, "ticks": [0, 10, 20, 30]},
        "x": {"from": f"{first}-01-01", "to": f"{last + 1}-01-01"},
        "series": [{"color": SITE_COLOR[s], "points": [{"x": r["date"], "y": r["total"],
                    "tip": f"{LABEL[s]}, {r['date']}: score {r['total']:.0f}"} for r in sos if r["site_id"] == s]}
                   for s in (467, 468)],
        "refs": [{"y": mE, "x0": f"{first}-01-01", "x1": "2012-12-31"}, {"y": mL, "x0": "2013-01-01", "x1": f"{last}-12-31"}],
        "notes": [{"text": f"No SOS survey in {', '.join(map(str, gaps))}"}] if gaps else [],
    }
    return Page(
        headline=f"Scores held near {mE:.1f} before 2013 and {mL:.1f} since; the overall score shows no trend.",
        status="steady",
        numbers=[(f"{mE:.1f} → {mL:.1f}", "mean SOS score, before and since 2013"),
                 (f"{mean(pairs):.1f}", "points between the two sites on the same day")],
        blocks=[
            text("The SOS score adds up the pollution-sensitive, less-sensitive and tolerant animal groups "
                 f"found in a survey. Single surveys range from {min(r['total'] for r in sos):.0f} to "
                 f"{max(r['total'] for r in sos):.0f}, but the average has not moved."),
            chart(spec, "Clean Water Hub, SOS Biological surveys at the two chapter sites. One dot per survey; dashed lines are the mean of each period."),
            text(f"The two sites, a few hundred metres apart and sampled on the same day {len(pairs)} times, differ by "
                 f"{mean(pairs):.1f} points on average. A change smaller than that is within sampling noise."),
            links([("species-mix", "the steady total hides a shift in which animals are found"),
                   ("expected", "how the creek compares with what its setting predicts")]),
        ])


@finding("chapter", "species-mix", "The mix of animals is shifting", order=20, key=True)
def species_mix(db):
    rows = db.rows(f"""SELECT taxon, tolerance, period, sum(found)::int AS found, sum(surveys)::int AS surveys
                       FROM taxa_by_period WHERE site_id IN ({CHAPTER}) AND protocol = 'sos_bio'
                       GROUP BY ALL ORDER BY tolerance, taxon, period""") if db.has("taxa_by_period") else []
    if not rows:
        return None
    periods = sorted({r["period"] for r in rows})
    by = {}
    for r in rows:
        by.setdefault(r["taxon"], {"tol": r["tolerance"], "p": {}})["p"][r["period"]] = r
    share = lambda x, p: (x["p"][p]["found"] / x["p"][p]["surveys"]) if p in x["p"] and x["p"][p]["surveys"] else 0
    taxa = {k: v for k, v in by.items() if any(share(v, p) > 0 for p in periods)}
    n_per = {p: max(r["surveys"] for r in rows if r["period"] == p) for p in periods}
    first, last = periods[0], periods[-1]
    change = sorted(taxa, key=lambda k: share(taxa[k], last) - share(taxa[k], first))
    drops, rises = change[:2], change[::-1][:2]
    blocks_spec = []
    for key, name in [("sensitive", "Pollution-sensitive"), ("less_sensitive", "Less sensitive"), ("tolerant", "Tolerant")]:
        ks = sorted([k for k, v in taxa.items() if v["tol"] == key], key=lambda k: -sum(share(taxa[k], p) for p in periods))
        blocks_spec.append({"name": name, "rows": [{"label": k, "cells": [
            {"v": share(taxa[k], p), "text": pct(share(taxa[k], p)),
             "tip": f"{k}, {p}: found in {taxa[k]['p'].get(p, {}).get('found', 0)} of {n_per[p]} surveys"} for p in periods]} for k in ks]})
    sh = lambda k: f"{pct(share(taxa[k], first))} → {pct(share(taxa[k], last))}" if k in taxa else ""
    drift = db.rows(f"""SELECT site_id, round(avg(similarity_to_baseline) FILTER (WHERE year(survey_date) < 2013), 2) AS early,
                               round(avg(similarity_to_baseline) FILTER (WHERE year(survey_date) >= 2013), 2) AS late
                        FROM baseline_drift WHERE site_id IN ({CHAPTER}) AND protocol = 'sos_bio' GROUP BY 1 ORDER BY 1""")
    d = ", ".join(f"{LABEL[r['site_id']]} {r['early']} → {r['late']}" for r in drift)
    spec = {"type": "heat", "title": f"Fewer {' and '.join(drops)}; more {' and '.join(rises)}",
            "subtitle": f"Share of surveys finding each group, {first} to {last}",
            "cols": periods, "colNotes": [f"{n_per[p]} surveys" for p in periods], "blocks": blocks_spec}
    plate = plates.community("mix", [{"taxon": k, "tolerance": v["tol"], "early": share(v, first), "late": share(v, last)}
                                     for k, v in taxa.items()], first, last)
    return Page(
        headline=f"Between {first} and {last}, {drops[0]} and {drops[1]} became rarer while {rises[0]} and {rises[1]} became regulars.",
        status="watch",
        numbers=[(sh("damselflies"), "damselflies, share of surveys"), (sh("aquatic worms"), "aquatic worms, share of surveys")],
        blocks=[
            text("The total score hides a change in which animals live in the riffles."),
            chart(spec, "Share of SOS surveys at the two chapter sites that found each animal group, by five-year period."),
            text(f"Stoneflies ({sh('stoneflies')}), damselflies ({sh('damselflies')}) and common net-spinning caddisflies "
                 f"({sh('common net-spinning caddisflies')}) were found less often, while aquatic worms ({sh('aquatic worms')}) "
                 f"and dobsonflies ({sh('dobsonflies')}) became regulars.",
                 f"Each site's surveys now share fewer groups with its first five years (average similarity before and since 2013: {d}).",
                 "Some of this may come from changes in who sorts and identifies the animals, which the survey records cannot show."),
            diagram(plate, "Field-guide drawings, illustrative and not to scale. Bars: share of SOS surveys at the two chapter sites finding each group."),
            links([("trend-tests", "whether the shift is statistically clear"), ("expected", "whether season, weather or team explain it")]),
        ])


@finding("chapter", "trend-tests", "Trend tests", order=30)
def trend_tests(db):
    ch = [r for r in db.trends() if r["is_chapter_site"]]
    if not ch:
        return None
    def change(r):
        v = r["slope_per_decade"]
        if v is None or v != v:
            return "—"
        if r["measure"] == "sensitive_share":
            return f"{'+' if v > 0 else ''}{100 * v:.0f} pts"
        if r["measure"] == "ept_found":
            return "under 0.1 groups" if abs(v) < 0.05 else f"{'+' if v > 0 else ''}{v:.1f} groups"
        return f"{'+' if v > 0 else ''}{v:.1f} points"
    g = lambda s, m: next((r for r in ch if r["site_id"] == s and r["measure"] == m), {})
    s1, ss, ept = g(467, "score"), g(467, "sensitive_share"), g(467, "ept_found")
    turn = db.rows("SELECT split_before, p FROM turning_points WHERE site_id = 467") if db.has("turning_points") else []
    tn = (f"No sudden shift stands out at either site: the strongest candidate at Site 1, around {year(turn[0]['split_before'])}, "
          f"would arise by chance {round(100 * turn[0]['p'])}% of the time.") if turn else ""
    return Page(
        headline=f"At Site 1 the share of pollution-sensitive groups is {ss.get('verdict')} ({pfmt(ss['p'])}) while the total score shows {s1.get('verdict')}.",
        status="concern" if ss.get("verdict") == "declining" else "steady",
        blocks=[
            text("A seasonal Kendall test compares each survey only with surveys from the same season in other years, "
                 "so the spring-summer gap cannot pose as a trend. One value per season and year is used, and a "
                 "trend is reported only with at least 10 same-season comparisons."),
            table([("Site",), ("Measure",), ("Surveys", 1), ("Result",), ("Evidence", 1), ("Change per decade", 1)],
                  [[LABEL[r["site_id"]], r["label"], r["n"], verdict_pill(r["verdict"]), pfmt(r["p"]), change(r)] for r in ch]),
            text(f"Mayfly, stonefly and caddisfly groups at Site 1 are {'also declining' if ept.get('verdict') == 'declining' else ept.get('verdict')} "
                 f"({pfmt(ept['p'])}). Site 2 has fewer surveys and shows no clear trend. {tn}",
                 "Results with p between 0.05 and 0.1 are a signal to watch rather than proof."),
            links([("expected", "the same test on observed minus expected")]),
        ],
        method="Seasonal Kendall test (Hirsch, Slack and Smith 1982) on season-year medians; seasonal Sen slope; "
               "turning points by a permutation test of the strongest mean shift (999 shuffles).")


@finding("chapter", "expected", "Compared with what its setting predicts", order=5, key=True)
def expected(db):
    if not db.has("expected"):
        return None
    m = {r["target"]: r for r in db.rows("SELECT * FROM model_metrics")}
    ms = m.get("sensitive_share")
    rt = {(r["site_id"], r["target"]): r for r in db.resid_trends()}
    s1, s2, p1 = rt.get((467, "sensitive_share"), {}), rt.get((468, "sensitive_share"), {}), rt.get((467, "score_pct"), {})
    rows = db.rows(f"""SELECT site_id, protocol, survey_date::DATE AS date, observed, expected, exp_lo, exp_hi, resid, outside
                       FROM expected WHERE site_id IN ({CHAPTER}) AND target = 'sensitive_share' ORDER BY date""")
    rain = ms["rain_coverage"] > 0.5
    per = {}
    for r in rows:
        if r["site_id"] == 467:
            per.setdefault(year(r["date"]) // 5 * 5, []).append(r["resid"])
    med = lambda a: sorted(a)[len(a) // 2]
    first_med = med(per[min(per)]) if per else 0
    spec = {
        "type": "time",
        "title": ("Site 1 has slipped from about what its setting predicts to below it" if abs(first_med) < 0.03
                  else "Site 1 has fallen further below what its setting predicts") if s1.get("verdict") == "declining"
                 else "Observed minus expected, chapter sites",
        "legend": LEGEND_SITES + [{"name": "Site 1, median per five years", "color": "accent", "shape": "line"}],
        "y": {"min": -0.4, "max": 0.4, "ticks": [-0.4, -0.2, 0, 0.2, 0.4], "fmt": "signedpct"},
        "x": {"from": f"{year(rows[0]['date'])}-01-01", "to": f"{year(rows[-1]['date']) + 1}-01-01"},
        "band": {"lo": ms["band_lo"], "hi": ms["band_hi"]},
        "yNotes": [{"y": 0.4, "text": "more sensitive animals than expected"}, {"y": -0.4, "text": "fewer than expected", "below": True}],
        "series": [{"color": "accent", "line": True, "dots": False, "lineWidth": 2.5,
                    "points": [{"x": f"{p + 2}-07-01", "y": med(a)} for p, a in sorted(per.items())]}] +
                  [{"color": SITE_COLOR[s], "r": 4.5, "points": [{"x": r["date"], "y": r["resid"],
                    "tip": f"{LABEL[s]}, {r['date']}: found {pct(r['observed'])} sensitive, expected {pct(r['expected'])}"}
                    for r in rows if r["site_id"] == s]} for s in (467, 468)],
    }
    s1r = [r for r in rows if r["site_id"] == 467][-3:][::-1]
    below = sum(r["outside"] == "below" for r in s1r)
    words = ["None", "One", "Two", "All three"]
    latest = s1r[0] if s1r else None
    alert = (f"{words[below]} of Site 1's last three surveys fell below the range"
             + (f", including the most recent on {latest['date']}." if latest and latest["outside"] == "below"
                else f"; the most recent, on {latest['date']}, was {latest['outside']} it." if latest else "."))
    recent = rows[-6:][::-1]
    word = {"below": ("bad", "below expected"), "above": ("good", "above expected"), "within": ("neutral", "within range")}
    declining = s1.get("verdict") == "declining"
    firm = declining and s1["p"] < 0.05  # p from 0.05 to 0.1: a signal to watch, not a settled result
    widening = "is widening" if firm else "appears to be widening"
    return Page(
        headline=(f"Site 1 finds fewer pollution-sensitive animals than its setting predicts, and the gap {widening} "
                  f"({pfmt(s1['p'])}, about {abs(round(100 * s1['slope_per_decade']))} percentage points a decade).") if declining
                 else f"Site 1 shows {s1.get('verdict')} against what its setting predicts ({pfmt(s1.get('p', 1))}).",
        status="concern" if firm else "watch" if declining else "steady",
        numbers=[(f"{abs(round(100 * s1['slope_per_decade']))} pts", "per decade, widening gap at Site 1") if declining else ("—", ""),
                 (f"{below} of 3", "latest Site 1 surveys below the expected range")],
        blocks=[
            text("A model learned from every other site in the country what a survey should find given its season, survey "
                 f"form, watershed, {'recent rain, ' if rain else ''}water temperature, flow and team. It never sees the year, so "
                 "change over time stays in the gap between what a site finds and what it should find."),
            chart(spec, "Observed minus expected share of pollution-sensitive groups. Expected values come from a model that never saw these sites. "
                        "Shaded band: the range 80% of held-out surveys fall in."),
            text(f"At Site 1 the gap {widening if declining else 'shows ' + str(s1.get('verdict'))} ({pfmt(s1.get('p', 1))}): "
                 f"the loss of sensitive animals is {'not ' if declining else ''}explained by season, "
                 f"{'recent rain, ' if rain else ''}water temperature, flow or team. Site 2 shows {s2.get('verdict')} "
                 f"({pfmt(s2.get('p', 1))}), and Site 1's overall score percentile shows {p1.get('verdict')} ({pfmt(p1.get('p', 1))}).",
                 "" if firm or not declining else "With p between 0.05 and 0.1 this is a signal to watch rather than proof; "
                 "a few more years of surveys, ideally in the same season each year, would settle it."),
            text(f"Each new survey can be checked against its expected range as soon as it is entered. {alert}"),
            table([("Date",), ("Site",), ("Form",), ("Sensitive share found", 1), ("Expected range", 1), ("Status",)],
                  [[r["date"], LABEL[r["site_id"]], PROTO.get(r["protocol"], r["protocol"]), pct(r["observed"]),
                    f"{pct(max(0, r['exp_lo']))}–{pct(min(1, r['exp_hi']))}", pill(*word[r["outside"]])] for r in recent]),
            links([("model", "how the model works and how accurate it is"), ("paving", "the national pattern behind it")]),
        ],
        method="Gradient-boosted trees, five folds grouped by site; residual trend by the seasonal Kendall test.")


@finding("chapter", "score-parts", "What moves the score", order=40)
def score_parts(db):
    sos = db.sos()
    if not sos:
        return None
    sens = [r["sens"] for r in sos]
    tol = [r["tol"] for r in sos]
    top = 30
    keys = [("sens", "Sensitive", 1), ("less", "Less sensitive", 0.55), ("tol", "Tolerant", 0.25)]
    charts = []
    for i, s in enumerate((467, 468)):
        rs = [r for r in sos if r["site_id"] == s]
        last_y, bars_ = None, []
        for r in rs:
            y = year(r["date"])
            lab = str(y) if last_y is None or y - last_y >= 2 else ""
            if lab:
                last_y = y
            bars_.append({"label": lab, "segs": [{"v": r[k], "color": "accent", "opacity": o,
                          "tip": f"{LABEL[s]}, {r['date']}: {n.lower()} {r[k]:.0f} of {r['total']:.0f}"} for k, n, o in keys]})
        spec = {"type": "stack", "title": (f"Sensitive animals swing from {min(sens):.0f} to {max(sens):.0f} points; "
                                           f"tolerant ones stay at {min(tol):.0f}–{max(tol):.0f}") if i == 0 else LABEL[s],
                "subtitle": LABEL[s] if i == 0 else None,
                "legend": [{"name": n, "color": "accent", "opacity": o, "shape": "square"} for _, n, o in keys] if i == 0 else [],
                "y": {"max": top, "ticks": [0, 15, 30]}, "height": 250 if i == 0 else 190, "maxBar": 22, "bars": bars_}
        charts.append(chart(spec, "Sub-scores from each survey, stacked. Darker = more sensitive to pollution." if i == 1 else ""))
    latest = [r for r in sos if r["site_id"] == 467][-1]
    groups = db.rows(f"""SELECT t.taxon, t.tolerance FROM taxa t JOIN usable_surveys u USING (survey_uid)
                         WHERE u.site_id = 467 AND u.protocol = 'sos_bio' AND u.survey_date = DATE '{latest['date']}' AND t.present
                         ORDER BY t.tolerance, t.taxon""")
    build_svg = plates.score_build("score", {"site": LABEL[467], "date": latest["date"], "groups": groups,
                                             "sens": latest["sens"], "less": latest["less"], "tol": latest["tol"], "total": latest["total"]})
    return Page(
        headline=f"Pollution-sensitive animals drive the swings: they add {min(sens):.0f} to {max(sens):.0f} points per survey.",
        status="info",
        blocks=[text("The SOS score counts three points for each pollution-sensitive group found, two for each less-sensitive "
                     "group and one for each tolerant group."),
                diagram(build_svg, "Site 1's most recent SOS survey. Drawings are illustrative and not to scale."), *charts,
                text("Finding or missing one or two sensitive groups such as mayflies, stoneflies or riffle beetles moves the total "
                     "by several points. Tolerant animals such as midges and worms add little in any year, which is a good sign."),
                links([("species-mix", "which groups are being found less often")])])


@finding("chapter", "season", "Season matters", order=50)
def season_effect(db):
    sos = db.sos()
    if not sos:
        return None
    groups = [(n, [r for r in sos if season(r["date"]) == n]) for n in ("Spring", "Summer", "Fall")]
    means = {n: mean(r["total"] for r in g) for n, g in groups}
    diff = means["Spring"] - means["Summer"]
    spec = {"type": "strip", "title": f"Spring surveys average {diff:.1f} points more than summer ones",
            "x": {"min": 0, "max": 30, "ticks": [0, 10, 20, 30]},
            "groups": [{"label": n, "sub": f"{len(g)} surveys", "mean": means[n], "meanLabel": f"{means[n]:.1f}",
                        "values": [{"v": r["total"], "tip": f"{n} {r['date']}: {r['total']:.0f}"} for r in g]} for n, g in groups]}
    return Page(
        headline=f"Spring surveys average {diff:.1f} points more than summer ones, so trends must compare like seasons.",
        status="info",
        blocks=[chart(spec, "Spring = March to June, summer = July to September, fall = October to February."),
                text("Many insects emerge as adults by mid-summer, which likely leaves fewer larvae in the riffles, and summer flows "
                     "are lower and warmer. Comparing a spring survey with a summer one can show a change that is only the calendar, "
                     "so every trend on this site compares like seasons."),
                links([("trend-tests", "the season-aware trend tests")])])


@finding("chapter", "survey-forms", "The chapter changed survey forms in 2024", order=60)
def survey_forms(db):
    va, sos = db.va(), db.sos()
    if not va:
        return None
    cls = lambda c: "good" if (c or "").lower().startswith("accept") else "warn" if "gray" in (c or "").lower() else "bad"
    same = lambda r: next((x["total"] for x in sos if x["date"] == r["date"] and x["site_id"] == r["site_id"]), None)
    both = [r for r in va if same(r) is not None]
    return Page(
        headline=f"Since {year(va[0]['date'])} the chapter has also used the Virginia form, which the Hub's own site page does not chart.",
        status="info",
        blocks=[text("The Virginia Save Our Streams form scores 0 to 12 and rates a stream Acceptable (9 and up), Gray Zone (8) or "
                     "Unacceptable (7 and below). It also counts every animal, which allows diversity measures."),
                table([("Date",), ("Site",), ("VA score (0–12)", 1), ("Rating",), ("SOS score same day", 1)],
                      [[r["date"], LABEL[r["site_id"]], fmt(r["mms"]), pill(cls(r["cond"]), r["cond"]),
                        fmt(same(r)) if same(r) is not None else "—"] for r in va]),
                text(f"The two scales cannot be compared directly. {'One survey was' if len(both) == 1 else f'{len(both)} surveys were'} "
                     "scored on both forms the same day, a first calibration point. The share of sensitive groups found works on "
                     "both forms, which is why the model and trend tests use it.")])
