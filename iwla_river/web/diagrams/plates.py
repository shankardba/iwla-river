"""The diagrams on the findings site. Each function takes the data it shows and returns static SVG.

  riffle(p)                         where the animals live and how volunteers sample (overview)
  community(p, rows, first, last)   field-guide plate of each group, how often found then and now
  score_build(p, survey)            one survey's groups, weights and total
  watershed(p, bins, ctx)           forested versus paved watershed, with national figures and Great Seneca's land cover
  salt(p, peak, summer, md, epa)    road salt's path to the creek and the creek's chloride on a gauge
  model_flow(p, m, gaps)            how the expected-score model works, with its own numbers
"""

from __future__ import annotations

import math
import random

from . import bugs
from .kit import figure, label, lens, line, n, place, shape, smooth, text

TOL_TITLE = {"sensitive": "Pollution-sensitive", "less_sensitive": "Less sensitive", "tolerant": "Tolerant"}
WEIGHT = {"sensitive": 3, "less_sensitive": 2, "tolerant": 1}


def _cobble(p, x, y, rx, ry, tone="stone", rot=0):
    pts = [(x + rx * math.cos(a) * (1 + 0.08 * math.sin(3 * a + rot)), y + ry * math.sin(a) * (1 + 0.06 * math.cos(2 * a)))
           for a in [i * math.pi / 5 for i in range(10)]]
    return shape(smooth(pts), p, tone, sw=0.8)


def _flow(x0, y0, x1, y1, bend=0, p=""):
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2 + bend
    return (f'<path class="flow" d="M{n(x0)} {n(y0)} Q{n(mx)} {n(my)} {n(x1)} {n(y1)}" fill="none" '
            f'style="stroke:var(--dg-flow)" stroke-width="1.6" stroke-linecap="round" marker-end="url(#{p}-arrow)"/>')


# ---------------------------------------------------------------- 1. riffle
def riffle(p="rf", labels=True):
    W, H = 760, 340
    surf = [(0, 96), (120, 96), (200, 94), (240, 90), (280, 93), (320, 89), (360, 93), (400, 89), (440, 93), (480, 90), (520, 95), (600, 100), (760, 100)]
    bed = [(0, 236), (140, 226), (220, 200), (520, 198), (580, 232), (640, 262), (760, 266)]
    s = f'<rect width="{W}" height="{H}" fill="url(#{p}-sky)"/>'
    # ground and gravel
    s += shape(smooth([(0, 236), (140, 226), (220, 200), (520, 198), (580, 232), (640, 262), (760, 266), (760, 340), (0, 340)], closed=False) + "Z", p, "sand", sw=0)
    rnd = random.Random(2)
    for _ in range(150):
        x = rnd.uniform(0, W)
        top = 266 if x > 640 else 232 if x > 580 else 198 if x > 220 else 226
        y = rnd.uniform(top + 8, 334)
        s += f'<ellipse cx="{n(x)}" cy="{n(y)}" rx="{n(rnd.uniform(1.2, 3.4))}" ry="{n(rnd.uniform(1, 2.4))}" style="fill:var(--dg-stone-dark)" opacity=".55"/>'
    # water
    s += f'<path d="{smooth(surf, closed=False)} L760 266 L640 262 L580 232 L520 198 L220 200 L140 226 L0 236Z" fill="url(#{p}-wcol)" opacity=".92"/>'
    s += f'<path d="{smooth(surf, closed=False)}" fill="none" style="stroke:var(--dg-flow)" stroke-width="1.4"/>'
    # cobbles in the riffle
    for x, y, rx, ry in [(232, 198, 20, 13), (268, 194, 26, 15), (306, 197, 18, 12), (338, 192, 28, 17), (378, 197, 20, 12),
                         (410, 191, 26, 16), (446, 197, 19, 12), (478, 193, 24, 14), (508, 199, 16, 10), (160, 222, 18, 11), (600, 240, 20, 12)]:
        s += _cobble(p, x, y, rx, ry, rot=x)
    # flow
    for y, b in ((120, 0), (150, 4), (176, -3)):
        s += _flow(30, y, 200, y - 4, b, p) + _flow(250, y - 8, 520, y - 10, -b, p)
    s += _flow(560, 150, 730, 170, 6, p) + _flow(560, 200, 730, 230, 6, p)
    # kick net, downstream of the riffle
    s += line([(545, 60), (552, 212)], "var(--dg-bark)", 3) + line([(585, 60), (592, 236)], "var(--dg-bark)", 3)
    for y in range(110, 225, 9):
        s += line([(548 + (y - 60) * 0.046, y), (588 + (y - 60) * 0.046, y + 4)], "var(--dg-line)", 0.5)
    for x in range(552, 590, 7):
        s += line([(x, 104), (x + 6, 224)], "var(--dg-line)", 0.5)
    # lens on the underside of a cobble: animals cling to the stone's underside in the current
    inner = f'<rect x="-100" y="-100" width="200" height="200" fill="url(#{p}-wcol)"/>'
    inner += shape(smooth([(-100, -100), (100, -100), (100, -40), (60, -18), (0, -8), (-60, -16), (-100, -36)]), p, "stone", sw=1)
    inner += place(bugs.mayfly(p), -42, -6, 0.62, 168) + place(bugs.caddis_case(p), 4, -2, 0.56, 186) + place(bugs.stonefly(p), 48, -10, 0.58, 194)
    s += lens(p, "stone", (346, 206), 6, (118, 162), 76, place(inner, 118, 168))
    if not labels:  # artwork only, for the share card
        return figure(p, W, H, "A riffle", s)
    # labels
    s += label((360, 91), (380, 34), "Riffle: fast, shallow water over stones", "where Save Our Streams samples")
    s += label((690, 140), (700, 72), "Pool: slower and deeper", anchor="end")
    s += label((570, 150), (748, 296), "Kick-seine net", "stir the stones upstream; animals wash in", anchor="end")
    s += text(118, 284, "Most animals counted cling to", "dg-sub", "middle") + text(118, 299, "and under the stones", "dg-sub", "middle")
    return figure(p, W, H, "A riffle: where stream animals live and how volunteers sample them", s, flow=True)


SHORT = {"caddisflies (most)": "caddisflies", "common net-spinning caddisflies": "net-spinning caddisflies",
         "hellgrammites/fishflies/alderflies": "hellgrammites", "dragonflies and damselflies": "dragon- and damselflies"}


def _name(cx, y, taxon, cls="dg-name"):
    """Animal name, wrapped onto two lines when long."""
    words = SHORT.get(taxon, taxon)
    if len(words) <= 14 or " " not in words:
        return text(cx, y, words, cls, "middle")
    a, b = words.rsplit(" ", 1)
    return (f'<text class="{cls}" x="{n(cx)}" y="{n(y - 7)}" text-anchor="middle"><tspan x="{n(cx)}">{a}</tspan>'
            f'<tspan x="{n(cx)}" dy="13">{b}</tspan></text>')


# ---------------------------------------------------------------- 2. community
def community(p, rows, first, last):
    """rows: [{taxon, tolerance, early, late}] share of surveys finding the group in the first and last period."""
    W, cw, ch, L = 760, 106, 164, 12
    per_row = (W - L) // cw
    bands = [(k, [r for r in rows if r["tolerance"] == k and r["taxon"] in bugs.DRAW]) for k in ("sensitive", "less_sensitive", "tolerant")]
    H = 40 + sum(34 + math.ceil(len(b) / per_row) * ch for _, b in bands if b) + 10
    s = text(0, 18, f"Who lives in the riffle: share of surveys finding each group, {first} and {last}", "dg-big")
    s += (f'<rect x="{W - 250}" y="30" width="12" height="8" style="fill:var(--grey)" opacity=".7"/>' + text(W - 234, 38, first, "dg-sub")
          + f'<rect x="{W - 140}" y="30" width="12" height="8" style="fill:var(--accent)"/>' + text(W - 124, 38, last, "dg-sub"))
    y = 46
    for key, items in bands:
        if not items:
            continue
        s += f'<rect x="0" y="{y}" width="{W}" height="{30 + math.ceil(len(items) / per_row) * ch - 6}" rx="8" style="fill:var(--bg)" opacity=".9"/>'
        s += text(12, y + 20, TOL_TITLE[key], "dg-name") + text(12 + 7.6 * len(TOL_TITLE[key]) + 10, y + 20, f"{WEIGHT[key]} point{'s' if WEIGHT[key] > 1 else ''} each in the SOS score", "dg-sub")
        y += 30
        for i, r in enumerate(sorted(items, key=lambda r: -(r["early"] + r["late"]))):
            cx = L + (i % per_row) * cw + cw / 2
            cy = y + (i // per_row) * ch
            s += place(bugs.DRAW[r["taxon"]](p), cx, cy + 4, 0.76)
            s += _name(cx, cy + 96, r["taxon"])
            for j, (v, col) in enumerate(((r["early"], "var(--grey)"), (r["late"], "var(--accent)"))):
                by = cy + 114 + j * 13
                s += (f'<rect x="{n(cx - 40)}" y="{n(by)}" width="80" height="9" rx="2" style="fill:var(--rule)" opacity=".7"/>'
                      f'<rect x="{n(cx - 40)}" y="{n(by)}" width="{n(max(1.5, 80 * v))}" height="9" rx="2" style="fill:{col}" opacity="{".7" if j == 0 else "1"}"/>')
            d = r["late"] - r["early"]
            arrow = "▲" if d > 0.05 else "▼" if d < -0.05 else "•"
            cls = "dg-up" if d > 0.05 else "dg-down" if d < -0.05 else "dg-sub"
            s += (f'<text class="dg-num" x="{n(cx)}" y="{n(cy + 154)}" text-anchor="middle">{round(100 * r["early"])}% → {round(100 * r["late"])}% '
                  f'<tspan class="{cls}">{arrow}</tspan></text>')
        y += math.ceil(len(items) / per_row) * ch + 4
    return figure(p, W, H, "Stream animal groups and how often surveys found them", s)


# ---------------------------------------------------------------- 3. score build
def score_build(p, survey):
    """survey: {site, date, groups: [{taxon, tolerance}], sens, less, tol, total}"""
    W, rowH, L = 760, 104, 170
    H = 50 + 3 * rowH + 44
    s = text(0, 18, f"How a score is built: {survey['site']}, {survey['date']}", "dg-big")
    s += text(0, 38, "Each kind of animal found counts once, weighted by how sensitive it is to pollution", "dg-sub")
    y = 52
    for key, sub in (("sensitive", "sens"), ("less_sensitive", "less"), ("tolerant", "tol")):
        items = [g for g in survey["groups"] if g["tolerance"] == key and g["taxon"] in bugs.DRAW]
        s += f'<rect x="0" y="{y}" width="{W}" height="{rowH - 8}" rx="8" style="fill:var(--bg)"/>'
        s += text(14, y + 30, TOL_TITLE[key], "dg-name") + text(14, y + 48, f"{len(items)} group{'s' if len(items) != 1 else ''} × {WEIGHT[key]}", "dg-sub")
        for i, g in enumerate(items[:7]):
            cx = L + i * 72 + 30
            s += place(bugs.DRAW[g["taxon"]](p), cx, y + 4, 0.55) + _name(cx, y + 86, g["taxon"], "dg-sub")
        if not items:
            s += text(L, y + 50, "none found", "dg-sub")
        s += text(W - 20, y + 52, f"= {survey[sub]:.0f}", "dg-big", "end")
        y += rowH
    s += line([(W - 120, y + 2), (W - 16, y + 2)], "var(--ink)", 1)
    s += text(W - 20, y + 28, f"Score {survey['total']:.0f}", "dg-big", "end")
    return figure(p, W, H, f"How the SOS score of {survey['total']:.0f} is built", s)


# ---------------------------------------------------------------- 4. watershed
def _tree(p, x, y, h):
    s = line([(x, y), (x, y - h * 0.45)], "var(--dg-bark)", max(2, h * 0.07))
    s += shape(smooth([(x - h * 0.28, y - h * 0.35), (x - h * 0.33, y - h * 0.65), (x - h * 0.12, y - h * 0.95), (x + h * 0.15, y - h * 0.97),
                       (x + h * 0.34, y - h * 0.68), (x + h * 0.27, y - h * 0.36)]), p, "leaf", sw=0.7)
    return s


def _house(p, x, y, w):
    h = w * 0.65
    return (shape(f"M{n(x)} {n(y)}H{n(x + w)}V{n(y - h)}H{n(x)}Z", p, "wall", sw=0.7)
            + shape(f"M{n(x - 4)} {n(y - h)}L{n(x + w / 2)} {n(y - h - w * 0.45)}L{n(x + w + 4)} {n(y - h)}Z", p, "roof", sw=0.7)
            + f'<rect x="{n(x + w * 0.4)}" y="{n(y - h * 0.55)}" width="{n(w * 0.2)}" height="{n(h * 0.55)}" style="fill:var(--dg-bark)"/>')


def _panel(p, x0, kind):
    """One half: a slope down to a stream channel at its right edge. Ground surface y from 150 (left) to 210."""
    w = 360
    gy = lambda x: 150 + (x - x0) / w * 52
    s = f'<rect x="{x0}" y="40" width="{w}" height="170" fill="url(#{p}-sky)"/>'
    ground = [(x0, 150), (x0 + w - 70, gy(x0 + w - 70)), (x0 + w - 50, 222), (x0 + w - 20, 222), (x0 + w, 205), (x0 + w, 300), (x0, 300)]
    s += shape(f"M{pts_(ground)}Z", p, "soil", sw=0.8)
    s += shape(f"M{n(x0 + w - 52)} 218 Q{n(x0 + w - 35)} 228 {n(x0 + w - 18)} 218Z", p, "water", sw=0)
    # clouds and rain
    s += shape(smooth([(x0 + 40, 70), (x0 + 70, 52), (x0 + 110, 56), (x0 + 140, 50), (x0 + 175, 66), (x0 + 150, 80), (x0 + 60, 82)]), p, "snow", sw=0.6)
    for i in range(14):
        rx = x0 + 52 + i * 8.5
        s += f'<line class="drip" x1="{n(rx)}" y1="86" x2="{n(rx - 6)}" y2="{n(gy(rx) - 6)}" style="stroke:var(--dg-flow)" stroke-width="1.1" opacity=".75"/>'
    if kind == "forest":
        s += "".join(_tree(p, x0 + 20 + i * 38, gy(x0 + 20 + i * 38) + 2, 46 + (i % 3) * 8) for i in range(7))
        s += shape(f"M{pts_([(x0, 150), (x0 + w - 70, gy(x0 + w - 70)), (x0 + w - 70, gy(x0 + w - 70) + 6), (x0, 156)])}Z", p, "grass", sw=0)
        for i in range(5):  # soaking in, then seeping to the stream as groundwater
            gx = x0 + 70 + i * 40
            s += f'<path class="flow" d="M{n(gx)} {n(gy(gx) + 8)} L{n(gx + 4)} {n(gy(gx) + 40)}" style="stroke:var(--dg-flow)" stroke-width="1.6" marker-end="url(#{p}-arrow)"/>'
        s += f'<path class="flow" d="M{x0 + 70} 252 Q{x0 + 200} 272 {x0 + w - 40} 232" fill="none" style="stroke:var(--dg-flow)" stroke-width="1.8" marker-end="url(#{p}-arrow)"/>'
        s += label((x0 + 150, gy(x0 + 150) + 30), (x0 + 24, 284), "Rain soaks in", "and seeps slowly to the stream")
    else:
        s += shape(f"M{pts_([(x0, 148), (x0 + w - 70, gy(x0 + w - 70) - 2), (x0 + w - 70, gy(x0 + w - 70) + 5), (x0, 155)])}Z", p, "road", sw=0)
        s += "".join(_house(p, x0 + 14 + i * 62, gy(x0 + 14 + i * 62) - 2, 34) for i in range(4))
        dx = x0 + 262
        s += f'<rect x="{n(dx - 7)}" y="{n(gy(dx) - 2)}" width="14" height="6" style="fill:var(--dg-dark)"/>'
        s += shape(f"M{n(dx - 4)} {n(gy(dx) + 4)} L{n(dx + 4)} {n(gy(dx) + 4)} L{n(dx + 4)} 244 L{n(x0 + w - 44)} 230 L{n(x0 + w - 44)} 238 L{n(dx - 4)} 252Z", p, "stone-dark", sw=0.6)
        for i in range(4):
            rx = x0 + 40 + i * 52
            s += f'<path class="flow" d="M{n(rx)} {n(gy(rx) - 5)} L{n(rx + 40)} {n(gy(rx + 40) - 5)}" style="stroke:var(--dg-flow)" stroke-width="2.2" marker-end="url(#{p}-arrow)"/>'
        s += f'<path class="flow" d="M{n(dx)} {n(gy(dx) + 8)} L{n(dx)} 246 L{n(x0 + w - 46)} 234" fill="none" style="stroke:var(--dg-flow)" stroke-width="2.2" marker-end="url(#{p}-arrow)"/>'
        s += label((dx, gy(dx)), (x0 + 24, 284), "Rain runs off into storm drains", "and reaches the stream in minutes")
    return s


def pts_(points):
    return " L".join(f"{n(x)} {n(y)}" for x, y in points)


def watershed(p, bins, ctx):
    """bins: [{label, mean}] national sensitive share by paved band; ctx: chapter watershed land cover."""
    W, H = 760, 420
    s = text(0, 18, "Two watersheds after the same storm", "dg-big")
    s += text(180, 36, "Forested", "dg-name", "middle") + text(580, 36, "Paved", "dg-name", "middle")
    s += _panel(p, 0, "forest") + _panel(p, 400, "paved")
    lo, hi = bins[0], bins[-1]
    s += text(180, 322, f"Watersheds {lo['label']} paved: sensitive animals are", "dg-sub", "middle")
    s += text(180, 340, f"{round(100 * lo['mean'])}% of the groups found", "dg-name", "middle")
    s += text(580, 322, f"Watersheds {hi['label']} paved: sensitive animals are", "dg-sub", "middle")
    s += text(580, 340, f"{round(100 * hi['mean'])}% of the groups found", "dg-name", "middle")
    # Great Seneca's land cover as a bar
    dev, forest = ctx.get("ws_urban_pct") or 0, ctx.get("ws_forest_pct") or 0
    farm = (ctx.get("ws_crop_pct") or 0) + (ctx.get("ws_hay_pct") or 0)
    other = max(0, 100 - dev - forest - farm)
    s += text(0, 372, f"Above the chapter's sites: {ctx.get('ws_impervious_pct', 0):.1f}% paved or roofed", "dg-name")
    x = 0
    for v, nm, col in ((dev, "developed", "var(--dg-roof)"), (forest, "forest", "var(--dg-leaf)"), (farm, "farm and hay", "var(--dg-grass)"), (other, "water, wetland, other", "var(--dg-water)")):
        w = 760 * v / 100
        s += f'<rect x="{n(x)}" y="382" width="{n(w)}" height="16" style="fill:{col}"/>'
        if w > 70:
            s += text(x + 6, 413, f"{nm} {v:.0f}%", "dg-sub")
        x += w
    return figure(p, W, H, "Forested and paved watersheds after rain", s, flow=True)


# ---------------------------------------------------------------- 5. salt
def salt(p, peak, summer, md, epa=230):
    W, H = 760, 350
    s = f'<rect width="600" height="200" fill="url(#{p}-sky)"/>'
    s += shape("M0 160 L430 160 L470 196 L520 196 L560 214 L600 214 L600 350 L0 350Z", p, "soil", sw=0.6)
    s += shape("M0 150 L300 150 L300 162 L0 162Z", p, "road", sw=0)
    s += "".join(f'<rect x="{x}" y="155" width="14" height="2" style="fill:var(--dg-snow)" opacity=".8"/>' for x in range(10, 300, 34))
    s += shape(smooth([(-10, 150), (20, 136), (60, 140), (90, 132), (130, 141), (160, 150)], closed=False) + "Z", p, "snow", sw=0.6)
    s += shape(smooth([(200, 150), (230, 140), (270, 137), (300, 146), (310, 150)], closed=False) + "Z", p, "snow", sw=0.6)
    rnd = random.Random(5)
    s += "".join(f'<circle cx="{n(rnd.uniform(20, 300))}" cy="{n(rnd.uniform(150, 160))}" r="1.3" style="fill:var(--dg-salt);stroke:var(--dg-line)" stroke-width=".3"/>' for _ in range(60))
    # storm drain and pipe to the creek
    s += f'<rect x="318" y="158" width="18" height="6" style="fill:var(--dg-dark)"/>'
    s += shape("M322 164 L332 164 L332 236 L520 222 L520 232 L322 246Z", p, "stone-dark", sw=0.6)
    s += f'<path class="flow" d="M150 158 L316 160" style="stroke:var(--dg-flow)" stroke-width="2.2" marker-end="url(#{p}-arrow)"/>'
    s += f'<path class="flow" d="M327 168 L327 238 L516 226" fill="none" style="stroke:var(--dg-flow)" stroke-width="2.2" marker-end="url(#{p}-arrow)"/>'
    s += shape("M470 196 Q520 238 560 214 L560 214 L520 196Z", p, "water", sw=0)
    s += shape(smooth([(470, 198), (500, 212), (530, 218), (556, 214)], closed=False) + " L556 214 L470 198Z", p, "water", sw=0)
    s += label((150, 156), (90, 100), "Road salt dissolves in meltwater")
    s += label((420, 230), (360, 290), "Storm drains carry it straight to the creek")
    s += label((520, 205), (470, 120), "Great Seneca Creek")
    # lens: a gill plate in salty water
    inner = shape(smooth([(-30, -40), (20, -50), (40, 0), (16, 46), (-28, 36), (-40, 0)]), p, "amber", sw=1)
    for i in range(-30, 40, 12):
        inner += line([(-24, i), (26, i * 0.9)], "var(--dg-line)", 0.5)
    for k in range(14):
        a = k * 2 * math.pi / 14 + 0.2
        rad = 54 + (k % 3) * 5
        x, y = rad * math.cos(a), rad * math.sin(a) * 0.95
        pos = k % 2 == 0
        inner += (f'<circle cx="{n(x)}" cy="{n(y)}" r="{5 if pos else 7}" style="fill:{"var(--dg-accent)" if pos else "var(--dg-salt)"};stroke:var(--dg-line)" stroke-width=".6"/>'
                  f'<text class="dg-sub" x="{n(x)}" y="{n(y + 3.5)}" text-anchor="middle" font-size="9">{"Na+" if pos else "Cl−"}</text>')
    s += lens(p, "gill", (528, 214), 4, (150, 250), 66, place(inner, 150, 250, 0.85))
    s += text(150, 342, "Insects keep salts in balance through their gills", "dg-sub", "middle")
    # gauge
    gx, g0, g1 = 640, 300, 50
    Y = lambda v: g0 - (v / 250) * (g0 - g1)
    s += f'<rect x="{gx - 10}" y="{g1}" width="20" height="{g0 - g1}" rx="10" style="fill:var(--bg);stroke:var(--rule)"/>'
    s += f'<rect x="{gx - 6}" y="{n(Y(peak))}" width="12" height="{n(g0 - Y(peak) - 4)}" rx="6" style="fill:var(--dg-flow)"/>'
    s += f'<line x1="{gx - 18}" x2="{gx + 18}" y1="{n(Y(epa))}" y2="{n(Y(epa))}" style="stroke:var(--bad)" stroke-width="2"/>'
    s += text(gx - 22, Y(epa) + 4, f"EPA limit {epa}", "dg-sub", "end")
    for v, words in ((peak, f"winter peak {peak:.0f}"), (md, f"MD median {md:.0f}"), (summer, f"summer {summer:.0f}")):
        s += f'<line x1="{gx + 10}" x2="{gx + 18}" y1="{n(Y(v))}" y2="{n(Y(v))}" style="stroke:var(--ink)"/>' + text(gx + 22, Y(v) + 4, words, "dg-sub")
    s += text(gx, 36, "Chloride, mg/L", "dg-name", "middle")
    return figure(p, W, H, "Road salt's path to the creek and the creek's chloride", s, flow=True)


# ---------------------------------------------------------------- 6. model flow
def model_flow(p, m, gaps):
    """m: model metrics for the sensitive share; gaps: [(year, median gap)] for Site 1."""
    W, H = 760, 300
    s = text(0, 18, "How each survey is judged against what its setting predicts", "dg-big")
    inputs = ["Season", "Survey form", "Watershed land cover", "Soil, elevation, climate", "Recent rain and heat" if m["rain_coverage"] > 0.5 else "Recent rain (being added)", "Water temperature and flow", "Team size"]
    for i, t in enumerate(inputs):
        y = 44 + i * 34
        s += f'<rect x="0" y="{y}" width="190" height="26" rx="13" style="fill:var(--bg);stroke:var(--rule)"/>' + text(12, y + 17, t, "dg-sub")
        s += f'<path d="M190 {y + 13} C215 {y + 13} 215 150 236 150" fill="none" style="stroke:var(--rule)" stroke-width="1.2"/>'
    s += f'<rect x="238" y="104" width="190" height="92" rx="10" style="fill:var(--surface);stroke:var(--accent)" stroke-width="1.6"/>'
    s += text(333, 130, "Model", "dg-name", "middle") + text(333, 150, f"trained on {m['surveys']:,} surveys", "dg-sub", "middle")
    s += text(333, 166, f"at {m['sites']:,} other sites", "dg-sub", "middle") + text(333, 184, "(never sees the year)", "dg-sub", "middle")
    s += f'<line x1="428" y1="150" x2="468" y2="150" style="stroke:var(--muted)" stroke-width="1.4" marker-end="url(#{p}-arrow-ink)"/>'
    # expected range and an observed survey
    s += text(560, 72, "Expected range for a survey", "dg-name", "middle")
    s += f'<rect x="480" y="90" width="160" height="22" rx="4" style="fill:var(--grey)" opacity=".25"/>'
    s += f'<line x1="560" x2="560" y1="86" y2="116" style="stroke:var(--muted)" stroke-dasharray="3 3"/>' + text(560, 128, "expected", "dg-sub", "middle")
    s += f'<circle cx="500" cy="101" r="6" style="fill:var(--accent)"/>' + text(500, 145, "found", "dg-sub", "middle")
    s += f'<line x1="500" y1="133" x2="500" y2="108" style="stroke:var(--accent)" stroke-width=".8"/>'
    s += text(560, 166, "gap = found − expected", "dg-sub", "middle")
    # gap over time
    if gaps:
        x0, x1, y0 = 480, 715, 240
        ys = [g for _, g in gaps]
        lo, hi = min(min(ys), -0.1), max(max(ys), 0.05)
        X = lambda i: x0 + i * (x1 - x0) / max(1, len(gaps) - 1)
        Y = lambda v: y0 - (v - lo) / (hi - lo) * 50 + 25
        s += f'<line x1="{x0}" x2="{x1}" y1="{n(Y(0))}" y2="{n(Y(0))}" style="stroke:var(--grey)"/>' + text(x1, Y(0) - 4, "as expected", "dg-sub", "end")
        s += line([(X(i), Y(g)) for i, (_, g) in enumerate(gaps)], "var(--accent)", 2.2)
        for i, (yr, g) in enumerate(gaps):
            s += f'<circle cx="{n(X(i))}" cy="{n(Y(g))}" r="3.5" style="fill:var(--accent)"/>' + text(X(i), 296, str(yr), "dg-sub", "middle")
        s += text(470, 196, "Site 1's median gap, by five-year period", "dg-name")
    s += text(0, 296, f"Held-out accuracy: R² {m['r2']:.2f}, against {max(0, m['baseline_r2']):.2f} for season and form alone", "dg-sub")
    return figure(p, W, H, "How the expected-score model works", s)
