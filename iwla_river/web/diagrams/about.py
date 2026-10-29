"""About-page diagrams: how the datasets join the volunteer record, and how each finding is made.

Both are plain boxes and arrows in the site palette (CSS variables), so they follow light and dark mode.
The join rules drawn here mirror DataLab's streams recipe and iwla_river/context.py; change them together.
"""

from __future__ import annotations

from html import escape

from .kit import figure

FONT = "font-family:var(--display)"


def _t(x, y, s, size=12.5, weight=500, col="--ink", anchor="start"):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" style="{FONT};font-size:{size}px;font-weight:{weight};fill:var({col})">'
            f'{escape(s)}</text>')


def _box(x, y, w, h, title, lines=(), col="--rule", fill="--surface", tsize=13, center=False):
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" style="fill:var({fill});stroke:var({col});stroke-width:1.4"/>'
         f'<rect x="{x}" y="{y + 6}" width="3.5" height="{h - 12}" rx="1.5" style="fill:var({col})"/>' if not center else
         f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" style="fill:var({fill});stroke:var({col});stroke-width:1.6"/>')
    tx, an = (x + w / 2, "middle") if center else (x + 12, "start")
    s += _t(tx, y + 19, title, tsize, 650, "--ink", an)
    for i, ln in enumerate(lines):
        s += _t(tx, y + 36 + i * 15, ln, 11.5, 500, "--muted", an)
    return s


def _arrow(x1, y1, x2, y2, col="--muted"):
    return (f'<path d="M{x1} {y1} L{x2} {y2}" style="stroke:var({col});stroke-width:1.5;fill:none" marker-end="url(#ab-arr)"/>')


ARROW_DEF = ('<defs><marker id="ab-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             '<path d="M0 0 L10 5 L0 10z" style="fill:var(--muted)"/></marker></defs>')

# Join keys (column header, colour) and the datasets under each: (name, two short lines).
JOINS = [
    (("Same stream segment", "--c1"), [
        ("EPA StreamCat", ["Catchment land cover,", "soils, dams, climate"]),
        ("EPA NRSA surveys", ["Professional bug surveys:", "segment, ≤1 km or HUC12"]),
    ]),
    (("Same watershed (HUC12)", "--c3"), [
        ("USGS Annual NLCD", ["Paved share, every year", "1985–2025"]),
        ("EPA ATTAINS", ["Impaired waters", "and their causes"]),
        ("EPA ECHO", ["Discharge permits,", "major and minor"]),
        ("USGS USMIN", ["Mine features"]),
        ("Census ACS", ["Population, income,", "poverty"]),
    ]),
    (("Same watershed and date", "--c2"), [
        ("Water Quality Portal", ["Agency lab chloride", "within 7 days"]),
        ("USGS stream gauges", ["Flow percentile that day;", "HUC10 gauge if none"]),
    ]),
    (("Distance and date", "--c4"), [
        ("MBSS and Stream Waders", ["Maryland pros vs volunteers", "≤1 km, ≤2 years"]),
        ("Restoration projects", ["EPA 319 and county records,", "≤5 km, before and after"]),
        ("Open-Meteo (ERA5)", ["Rain 1, 3 and 7 days", "before each survey"]),
    ]),
]


def joins(sites: int, samples: int) -> str:
    W, cw, gap, x0 = 760, 178, 9, 8
    s = ARROW_DEF
    s += _box(170, 6, 420, 64, "Save Our Streams volunteer record",
              [f"{sites:,} sites · {samples:,} usable samples · Clean Water Hub"], "--accent", center=True, tsize=14.5)
    s += _arrow(380, 70, 380, 94)
    s += (f'<rect x="{x0}" y="96" width="{W - 2 * x0}" height="58" rx="8" style="fill:color-mix(in srgb, var(--accent) 10%, var(--surface));stroke:var(--accent);stroke-width:1.2"/>')
    s += _t(380, 118, "The spine: every site is placed in its HUC12 watershed (USGS WBD)", 12.5, 650, "--ink", "middle")
    s += _t(380, 137, "and on its stream segment (NHDPlus V2 COMID, via USGS NLDI). Kit and tap sites: watershed only.", 11.5, 500, "--muted", "middle")
    for i, ((head, col), items) in enumerate(JOINS):
        x = x0 + i * (cw + gap)
        cx = x + cw / 2
        s += _arrow(cx, 154, cx, 176, col)
        s += (f'<rect x="{x}" y="178" width="{cw}" height="26" rx="13" style="fill:color-mix(in srgb, var({col}) 22%, var(--surface));stroke:var({col})"/>'
              + _t(cx, 195.5, head, 12, 650, "--ink", "middle"))
        for j, (name, lines) in enumerate(items):
            s += _box(x, 214 + j * 64, cw, 56, name, lines, col)
    H = 214 + 5 * 64
    return figure("ab", W, H, "How the public datasets join the volunteer record", s)


def pipeline(units: int) -> str:
    W = 760
    s = ARROW_DEF
    stages = [("1  Snapshot", ["Clean Water Hub API;", "personal fields removed", "at download"]),
              ("2  Clean and place", ["Usable surveys only;", "units checked; each site", "in its HUC12 and segment"]),
              ("3  Join", ["Public datasets by", "segment, watershed,", "date and distance"])]
    bw, gap = 230, 26
    for i, (t, ln) in enumerate(stages):
        x = 8 + i * (bw + gap)
        s += _box(x, 6, bw, 84, t, ln, "--accent")
        if i:
            s += _arrow(x - gap + 2, 48, x - 3, 48)
    s += _arrow(380, 90, 380, 114)
    tests = [("Trends", ["Seasonal Kendall", "Sen slope"]),
             ("Differences", ["Permutation test,", "Mann–Whitney,", "Wilcoxon"]),
             ("Associations", ["OLS, watershed + year", "effects, clustered SEs"]),
             ("Drivers", ["LightGBM, 5×5 CV", "grouped by site; SHAP"]),
             ("Agreement, policy", ["Weighted kappa;", "DiD with placebo date"])]
    s += (f'<rect x="8" y="116" width="{W - 16}" height="132" rx="9" style="fill:color-mix(in srgb, var(--c2) 8%, var(--surface));stroke:var(--c2);stroke-width:1.2"/>'
          + _t(22, 138, "4  Test: the method fits the question", 13.5, 650))
    tw = (W - 16 - 24 - 4 * 8) / 5
    for i, (t, ln) in enumerate(tests):
        s += _box(20 + i * (tw + 8), 150, tw, 84, t, ln, "--c2", tsize=12.5)
    s += _arrow(380, 248, 380, 272)
    rep = [("Effect + 95% interval", ["Cluster bootstrap: repeat", "visits never count twice"]),
           ("q-value", ["Benjamini–Hochberg across", "every test in the family"]),
           ("Sources", ["Every dataset and method", "cited; nulls kept"])]
    s += (f'<rect x="8" y="274" width="{W - 16}" height="132" rx="9" style="fill:color-mix(in srgb, var(--good) 8%, var(--surface));stroke:var(--good);stroke-width:1.2"/>'
          + _t(22, 296, f"5  Report: nationally, and for each of {units:,} watersheds", 13.5, 650))
    rw = (W - 16 - 24 - 2 * 10) / 3
    for i, (t, ln) in enumerate(rep):
        s += _box(20 + i * (rw + 10), 308, rw, 84, t, ln, "--good", tsize=12.5)
    return figure("ap", W, 412, "How each finding is made: snapshot, clean, join, test, report", s)
