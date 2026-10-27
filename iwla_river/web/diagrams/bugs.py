"""Field-guide drawings of the stream animals Save Our Streams volunteers count.

Each function returns SVG for one animal seen from above, head up, in a box about 100 units tall
centred on x = 0. Shapes follow the identification sheets: a mayfly has plate gills along its
abdomen and usually three tails; a stonefly has two tails and two pairs of wing pads; and so on.
Drawings are illustrative, not measured.
"""

from __future__ import annotations

import math

from .kit import line, mirror_outline, n, shape, smooth

LINE = "var(--dg-line)"


def _leg(x, y, side, angles, lengths, w=2.2):
    """Jointed leg from (x, y): segments at the given angles (degrees, 0 = sideways out, + = backwards)."""
    s, px, py = "", x, y
    for i, (a, L) in enumerate(zip(angles, lengths)):
        r = math.radians(a)
        nx, ny = px + side * L * math.cos(r), py + L * math.sin(r)
        s += line([(px, py), (nx, ny)], LINE, max(w - i * 0.7, 0.8))
        px, py = nx, ny
    return s


def legs(rows, w=2.2):
    """rows: [(y, x_from_midline, angles, lengths)] drawn on both sides."""
    return "".join(_leg(side * x, y, side, ang, ln, w) for y, x, ang, ln in rows for side in (1, -1))


def _tail(x0, y0, x1, y1, bend, w=1.1, hairs=0):
    mid = ((x0 + x1) / 2 + bend, (y0 + y1) / 2)
    s = f'<path d="M{n(x0)} {n(y0)} Q{n(mid[0])} {n(mid[1])} {n(x1)} {n(y1)}" fill="none" style="stroke:{LINE}" stroke-width="{w}" stroke-linecap="round"/>'
    for i in range(1, hairs + 1):  # fine setae along the tail
        t = i / (hairs + 1)
        hx = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * mid[0] + t * t * x1
        hy = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * mid[1] + t * t * y1
        s += line([(hx - 2.2, hy + 1.2), (hx + 2.2, hy + 1.2)], LINE, 0.5)
    return s


def _segments(ys, halfw, curve=1.6, sw=0.6):
    """Faint arcs across a body at the given heights; halfw(y) gives the half width there."""
    out = ""
    for y in ys:
        w = halfw(y) * 0.92
        out += f'<path d="M{n(-w)} {n(y)} Q0 {n(y + curve)} {n(w)} {n(y)}" fill="none" style="stroke:{LINE}" stroke-width="{sw}" opacity=".55"/>'
    return out


def _interp(spine):
    def hw(y):
        for (y0, w0), (y1, w1) in zip(spine, spine[1:]):
            if y0 <= y <= y1:
                return w0 + (w1 - w0) * (y - y0) / ((y1 - y0) or 1)
        return spine[-1][1]
    return hw


def _eyes(y, x, r, p):
    return "".join(f'<ellipse cx="{n(s * x)}" cy="{n(y)}" rx="{n(r)}" ry="{n(r * 0.8)}" style="fill:var(--dg-dark)"/>' for s in (1, -1))


def _antennae(y, x, L, spread=30, w=0.8):
    return "".join(_tail(s * x, y, s * (x + L * math.sin(math.radians(spread))), y - L * math.cos(math.radians(spread)), s * 3, w)
                   for s in (1, -1))


# ---------------- pollution-sensitive ----------------

def mayfly(p):
    spine = [(4, 5), (9, 8), (15, 8.5), (19, 9.5), (26, 11), (33, 10.5), (38, 9.5), (46, 8.5), (54, 7), (62, 5), (68, 3), (71, 1.5)]
    body = shape(smooth(mirror_outline(spine)), p, "olive")
    gills = ""
    for i, y in enumerate([40, 45.5, 51, 56.5, 62]):
        w = _interp(spine)(y)
        for s in (1, -1):
            gills += shape(smooth([(s * (w - 1), y - 1.5), (s * (w + 4), y - 2.5), (s * (w + 5), y + 1), (s * w, y + 1.8)]), p, "amber", sw=0.5, extra='opacity=".9"')
    pads = "".join(shape(smooth([(s * 3, 24), (s * 10, 26), (s * 9, 37), (s * 3, 33)]), p, "brown", sw=0.6) for s in (1, -1))
    s = _antennae(6, 3, 10, 35) + gills + legs([(20, 9, (25, 70, 95), (9, 9, 5)), (27, 10.5, (15, 65, 80), (10, 10, 5)), (33, 10, (5, 55, 70), (11, 11, 6))])
    s += body + pads + _segments(range(41, 68, 5), _interp(spine)) + _eyes(10, 6, 2.2, p)
    s += _tail(-1.2, 71, -9, 99, -3, 1.0, 5) + _tail(0, 71, 0, 100, 0, 1.0, 5) + _tail(1.2, 71, 9, 99, 3, 1.0, 5)
    return s


def stonefly(p):
    spine = [(3, 5), (8, 8), (13, 8), (17, 9), (24, 10), (31, 9.5), (37, 10), (44, 9), (52, 8), (60, 6.5), (68, 4.5), (73, 2.5)]
    body = shape(smooth(mirror_outline(spine)), p, "amber")
    pads = "".join(shape(smooth([(s * 2, 21), (s * 10, 22), (s * 12, 31), (s * 3, 28)]), p, "brown", sw=0.6)
                   + shape(smooth([(s * 2, 32), (s * 10, 33), (s * 12, 42), (s * 3, 39)]), p, "brown", sw=0.6) for s in (1, -1))
    s = _antennae(4, 3, 22, 25) + legs([(19, 9, (30, 75, 100), (10, 11, 5)), (29, 9.5, (15, 65, 90), (11, 12, 6)), (39, 9.5, (0, 55, 80), (12, 13, 6))], 2.4)
    s += body + pads + _segments(range(46, 72, 4), _interp(spine)) + _eyes(8, 6, 2, p)
    s += _tail(-1.5, 73, -12, 99, -4, 1.1) + _tail(1.5, 73, 12, 99, 4, 1.1)
    return s


def caddis_case(p):
    case = smooth([(-9, 22), (9, 22), (10, 50), (8, 80), (5, 98), (-5, 98), (-8, 80), (-10, 50)])
    s = shape(case, p, "stone", sw=1)
    import random
    rnd = random.Random(4)
    for _ in range(46):  # pebbles of the case
        y = rnd.uniform(25, 95)
        half = 9.5 - (y - 22) * 0.055
        x = rnd.uniform(-half + 2, half - 2)
        r = rnd.uniform(1.6, 3.2)
        s += f'<ellipse cx="{n(x)}" cy="{n(y)}" rx="{n(r)}" ry="{n(r * 0.8)}" fill="url(#{p}-stone-dark)" style="stroke:{LINE}" stroke-width=".4" transform="rotate({rnd.randint(0, 90)} {n(x)} {n(y)})"/>'
    s += legs([(14, 6, (-20, 40, 70), (7, 7, 4)), (18, 6.5, (-5, 50, 80), (8, 8, 4)), (21, 7, (10, 60, 90), (8, 8, 4))], 1.8)
    s += shape(smooth([(-5, 4), (5, 4), (7, 13), (8, 22), (-8, 22), (-7, 13)]), p, "brown", sw=0.8) + _eyes(8, 3, 1.4, p)
    return s


def riffle_beetle(p):
    s = _antennae(20, 3, 9, 30) + legs([(36, 9, (20, 70, 100), (9, 9, 5)), (46, 11, (5, 60, 90), (10, 11, 5)), (56, 11, (-10, 50, 80), (11, 12, 6))], 1.8)
    s += shape(smooth([(-5, 18), (5, 18), (8, 24), (-8, 24)]), p, "dark", sw=0.6)
    s += shape(smooth([(-9, 25), (9, 25), (11, 33), (-11, 33)]), p, "brown", sw=0.7)
    s += shape(smooth([(0, 34), (11, 36), (13, 52), (9, 68), (0, 74), (-9, 68), (-13, 52), (-11, 36)]), p, "brown", sw=0.8)
    s += line([(0, 34), (0, 73)], LINE, 0.7)
    for y in range(39, 70, 5):  # punctures in rows on the wing covers
        for x in (3.5, 7.5):
            s += f'<circle cx="{n(x)}" cy="{y}" r=".7" style="fill:var(--dg-line)" opacity=".6"/><circle cx="{n(-x)}" cy="{y}" r=".7" style="fill:var(--dg-line)" opacity=".6"/>'
    return s


def water_penny(p):
    s = shape(smooth([(0, 22), (17, 28), (25, 46), (22, 66), (0, 78), (-22, 66), (-25, 46), (-17, 28)]), p, "copper", sw=1)
    for k, y in enumerate([31, 38, 46, 54, 62, 70]):
        w = 18 - abs(y - 50) * 0.35
        s += f'<path d="M{n(-w)} {y} Q0 {y + 3} {n(w)} {y}" fill="none" style="stroke:{LINE}" stroke-width=".6" opacity=".55"/>'
    for a in range(0, 360, 20):  # fringe of the plates
        r = math.radians(a)
        s += line([(22 * math.cos(r) * 1.0, 50 + 26 * math.sin(r)), (24.5 * math.cos(r), 50 + 28.5 * math.sin(r))], LINE, 0.6)
    s += line([(0, 26), (0, 74)], LINE, 0.6)
    return s


# ---------------- less sensitive ----------------

def dobsonfly(p):
    spine = [(8, 7), (16, 8), (20, 6.5), (24, 7.5), (30, 7), (34, 7.5), (40, 8), (55, 8), (70, 7), (84, 5.5), (92, 3.5)]
    s = legs([(23, 7, (20, 70, 95), (7, 7, 4)), (29, 7, (5, 60, 85), (7, 8, 4)), (35, 7.5, (-5, 55, 80), (8, 8, 4))], 1.8)
    hw = _interp(spine)
    for y in range(42, 86, 5):  # lateral filaments
        w = hw(y)
        s += line([(w, y), (w + 7, y + 3)], LINE, 1.0) + line([(-w, y), (-w - 7, y + 3)], LINE, 1.0)
    s += shape(smooth(mirror_outline(spine)), p, "dark") + _segments(range(40, 90, 5), hw)
    s += "".join(f'<path d="M{n(sg * 3)} 9 Q{n(sg * 9)} 3 {n(sg * 4)} -1" fill="none" style="stroke:{LINE}" stroke-width="2" stroke-linecap="round"/>' for sg in (1, -1))
    s += _eyes(12, 5, 1.5, p) + _antennae(9, 4, 6, 40, 0.7)
    s += "".join(line([(sg * 3, 92), (sg * 6, 98), (sg * 4, 100)], LINE, 1.6) for sg in (1, -1))
    return s


def damselfly(p):
    spine = [(6, 6), (10, 10), (14, 7), (20, 6), (28, 6.5), (34, 5), (45, 3.5), (60, 3), (70, 2.6), (74, 2)]
    s = legs([(18, 5, (30, 75, 100), (12, 13, 6)), (24, 5.5, (10, 65, 90), (13, 14, 6)), (29, 5.5, (-5, 55, 80), (14, 15, 7))], 1.3)
    s += shape(smooth(mirror_outline(spine)), p, "green") + _segments(range(36, 74, 5), _interp(spine), 1, 0.5)
    s += "".join(shape(smooth([(0, 22), (sg * 6, 23), (sg * 7, 34), (sg * 1, 30)]), p, "leaf-dark", sw=0.5) for sg in (1, -1))
    s += _eyes(10, 9, 3, p)
    for dx, bend in ((-4, -3), (0, 0), (4, 3)):  # three leaf-like tail gills
        s += shape(smooth([(dx * 0.3, 74), (dx + bend * 0.6 + 2.2, 86), (dx + bend, 99), (dx + bend * 0.6 - 2.2, 86)]), p, "leaf", sw=0.5)
    return s


def netspinner(p):
    spine = [(4, 5.5), (12, 6.5), (18, 7), (26, 8), (40, 8.5), (55, 8), (70, 7), (82, 5), (90, 3)]
    hw = _interp(spine)
    s = legs([(14, 6, (20, 70, 95), (7, 7, 4)), (19, 6.5, (5, 60, 85), (8, 8, 4)), (24, 7, (-5, 55, 80), (8, 8, 4))], 1.6)
    for y in range(32, 80, 6):  # branched gill tufts
        w = hw(y)
        for sg in (1, -1):
            s += line([(sg * w, y), (sg * (w + 4), y + 1)], LINE, 0.7) + line([(sg * (w + 2), y + 0.5), (sg * (w + 4), y - 2)], LINE, 0.5)
    s += shape(smooth(mirror_outline(spine)), p, "tan") + _segments(range(28, 86, 6), hw)
    s += shape(smooth([(-5, 2), (5, 2), (6.5, 10), (-6.5, 10)]), p, "brown", sw=0.6)
    s += "".join(shape(smooth([(sg * 1, 12), (sg * 6.5, 13), (sg * 7, 24), (sg * 1, 24)]), p, "brown", sw=0.5) for sg in (1, -1))
    s += "".join(line([(sg * 2, 90), (sg * 5, 97), (sg * 3, 99)], LINE, 1.3) for sg in (1, -1))
    return s


def crane_fly(p):
    spine = [(6, 4), (12, 8), (25, 11), (45, 12), (65, 11.5), (80, 10), (88, 8), (92, 6)]
    s = shape(smooth(mirror_outline(spine)), p, "tan") + _segments(range(16, 88, 6), _interp(spine), 2, 0.7)
    for a in (-50, -20, 20, 50):  # fleshy lobes around the breathing disc
        r = math.radians(a + 90)
        x, y = 9 * math.cos(r) * 0.9, 92 + 7 * math.sin(r)
        s += shape(smooth([(x * 0.4, 92), (x + 2, y), (x * 1.2, y + 4), (x - 2, y)]), p, "tan", sw=0.5)
    s += '<circle cx="-2.5" cy="92" r="1.3" style="fill:var(--dg-dark)"/><circle cx="2.5" cy="92" r="1.3" style="fill:var(--dg-dark)"/>'
    s += shape(smooth([(-3, 3), (3, 3), (4, 9), (-4, 9)]), p, "dark", sw=0.5)
    return s


def crayfish(p):
    s = _antennae(16, 3, 30, 22, 0.8)
    for sg in (1, -1):  # claws on long arms
        s += line([(sg * 6, 26), (sg * 13, 18), (sg * 16, 8)], LINE, 2.4)
        s += shape(smooth([(sg * 12, 8), (sg * 20, 6), (sg * 22, -6), (sg * 17, -2), (sg * 15, 2)]), p, "rust", sw=0.8)
        s += shape(smooth([(sg * 14, 6), (sg * 15, -8), (sg * 12, -4)]), p, "rust", sw=0.6)
    s += legs([(34, 7, (20, 60), (9, 8)), (39, 7.5, (10, 55), (10, 9)), (44, 7.5, (0, 50), (10, 9)), (49, 7, (-10, 45), (9, 8))], 1.4)
    s += shape(smooth([(0, 14), (8, 22), (9, 40), (7, 52), (-7, 52), (-9, 40), (-8, 22)]), p, "rust")
    s += f'<path d="M-7 36 Q0 39 7 36" fill="none" style="stroke:{LINE}" stroke-width=".7"/>'
    for i, y in enumerate(range(53, 80, 6)):
        w = 7 - i * 0.6
        s += shape(smooth([(-w, y), (w, y), (w - 0.5, y + 6), (-w + 0.5, y + 6)]), p, "rust", sw=0.6)
    s += "".join(shape(smooth([(0, 83), (sg * 4, 84), (sg * 9, 96), (sg * 2, 98)]), p, "rust", sw=0.6) for sg in (1, 0.0001, -1))
    s += _eyes(16, 3, 1.4, p)
    return s


def clam(p):
    s = shape(smooth([(0, 22), (16, 26), (26, 42), (24, 62), (10, 76), (-10, 76), (-24, 62), (-26, 42), (-16, 26)]), p, "beige", sw=1)
    for k in range(1, 6):  # growth rings from the hinge
        f = 1 - k * 0.15
        s += f'<path d="{smooth([(0, 22 + (1 - f) * 4), (16 * f, 26 + (1 - f) * 12), (26 * f, 42), (24 * f, 62 * f + 22 * (1 - f)), (10 * f, 76 * f + 22 * (1 - f)), (-10 * f, 76 * f + 22 * (1 - f)), (-24 * f, 62 * f + 22 * (1 - f)), (-26 * f, 42), (-16 * f, 26 + (1 - f) * 12)])}" fill="none" style="stroke:{LINE}" stroke-width=".5" opacity=".5"/>'
    return s


# ---------------- tolerant ----------------

def worm(p):
    path = [(0, 2), (6, 14), (-5, 30), (5, 46), (-4, 62), (4, 78), (0, 98)]
    d = smooth(path, closed=False)
    s = f'<path d="{d}" fill="none" style="stroke:var(--dg-line)" stroke-width="7.4" stroke-linecap="round"/>'
    s += f'<path d="{d}" fill="none" style="stroke:var(--dg-pink)" stroke-width="5.6" stroke-linecap="round"/>'
    s += f'<path d="{d}" fill="none" style="stroke:var(--dg-line)" stroke-width="5.6" stroke-dasharray=".6 3" opacity=".45"/>'
    return s


def midge(p):
    path = [(-8, 14), (-14, 34), (-12, 56), (-2, 74), (12, 82)]
    d = smooth(path, closed=False)
    s = f'<path d="{d}" fill="none" style="stroke:var(--dg-line)" stroke-width="5.2" stroke-linecap="round"/>'
    s += f'<path d="{d}" fill="none" style="stroke:var(--dg-blood)" stroke-width="3.8" stroke-linecap="round"/>'
    s += f'<path d="{d}" fill="none" style="stroke:var(--dg-line)" stroke-width="3.8" stroke-dasharray=".5 4.5" opacity=".5"/>'
    s += shape(smooth([(-11, 6), (-5, 6), (-5, 14), (-11, 14)]), p, "dark", sw=0.5)
    s += line([(-9, 19), (-4, 21)], LINE, 1.2) + line([(10, 80), (15, 86)], LINE, 1.2) + line([(13, 81), (18, 84)], LINE, 1.0)
    return s


def black_fly(p):
    s = shape(smooth([(0, 18), (5, 22), (6, 34), (5, 48), (8, 62), (11, 76), (9, 88), (0, 92), (-9, 88), (-11, 76), (-8, 62), (-5, 48), (-6, 34), (-5, 22)]), p, "grey")
    s += _segments(range(30, 88, 6), lambda y: 6 + max(0, y - 48) * 0.12, 1.4, 0.5)
    for sg in (1, -1):  # head fans
        for a in range(-60, 30, 15):
            r = math.radians(a - 90)
            s += line([(sg * 2.5, 17), (sg * (2.5 + 12 * math.cos(r) * -sg * sg), 17 + 12 * math.sin(r))], LINE, 0.5)
    s += shape(smooth([(-4, 12), (4, 12), (5, 20), (-5, 20)]), p, "dark", sw=0.5)
    s += f'<ellipse cx="0" cy="94" rx="7" ry="2" style="fill:var(--dg-dark)" opacity=".7"/>'
    return s


def leech(p):
    spine = [(4, 3), (12, 6), (30, 10), (50, 12), (70, 11), (86, 8), (94, 6)]
    s = shape(smooth(mirror_outline(spine)), p, "olive") + _segments(range(10, 92, 3), _interp(spine), 0.8, 0.4)
    s += f'<ellipse cx="0" cy="93" rx="5.5" ry="4" fill="url(#{p}-dark)" style="stroke:{LINE}" stroke-width=".5"/>'
    s += "".join(f'<circle cx="{n(x)}" cy="9" r=".8" style="fill:var(--dg-dark)"/>' for x in (-2, 0, 2))
    return s


DRAW = {
    "mayflies": mayfly, "stoneflies": stonefly, "caddisflies (most)": caddis_case, "riffle beetles": riffle_beetle,
    "beetles": riffle_beetle, "water pennies": water_penny, "dobsonflies": dobsonfly,
    "hellgrammites/fishflies/alderflies": dobsonfly, "damselflies": damselfly, "dragonflies and damselflies": damselfly,
    "common net-spinning caddisflies": netspinner, "crane flies": crane_fly, "crayfish": crayfish, "clams": clam,
    "mussels": clam, "aquatic worms": worm, "midges": midge, "black flies": black_fly, "leeches": leech,
}
