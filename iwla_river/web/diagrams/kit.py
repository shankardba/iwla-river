"""Drawing kit for the findings diagrams, after Omniscala's figure conventions.

- Shapes are smooth outlines through sparse control points (Catmull-Rom curves), filled with one
  shaded gradient per tone (light upper left, dark rim). No filters, masks or blend modes.
- Colours are CSS variables named for what they show (--dg-water, --dg-stone, ...), with light and
  dark values in assets/site.css; gradient stops read them, so diagrams follow the page theme.
- Labels: a dot on the object, a short leader, then the words.
- Anything drawn larger than true sits in a lens: an amber ring at its true place and size, tangent
  lines out to a double-ringed frame, and a "not to scale" badge.
Every diagram is built once, at site build time, as a static SVG string.
"""

from __future__ import annotations

import math
from html import escape

TONES = ["water", "water-deep", "stone", "stone-dark", "sand", "soil", "leaf", "leaf-dark", "bark", "grass",
         "roof", "wall", "road", "snow", "salt", "olive", "amber", "brown", "dark", "copper", "green",
         "tan", "rust", "pink", "blood", "grey", "beige", "accent"]


def n(x: float) -> str:
    """Compact number for SVG attributes."""
    s = f"{x:.1f}"
    return s[:-2] if s.endswith(".0") else s


def pts(points) -> str:
    return " ".join(f"{n(x)},{n(y)}" for x, y in points)


def smooth(points, closed: bool = True) -> str:
    """Catmull-Rom curve through the points, as cubic Bézier path data."""
    p = [(float(x), float(y)) for x, y in points]
    m = len(p)
    if m < 3:
        return "M" + " L".join(f"{n(x)} {n(y)}" for x, y in p)
    d = f"M{n(p[0][0])} {n(p[0][1])}"
    last = m if closed else m - 1
    for i in range(last):
        p0 = p[(i - 1) % m] if closed else p[max(i - 1, 0)]
        p1, p2 = p[i], p[(i + 1) % m]
        p3 = p[(i + 2) % m] if closed else p[min(i + 2, m - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{n(c1[0])} {n(c1[1])} {n(c2[0])} {n(c2[1])} {n(p2[0])} {n(p2[1])}"
    return d + ("Z" if closed else "")


def mirror_outline(spine) -> list:
    """Closed outline of a bilaterally symmetric body. spine: [(y, half_width)] head to tail."""
    right = [(w, y) for y, w in spine]
    left = [(-w, y) for y, w in reversed(spine)]
    return right + left


def defs(prefix: str, tones=TONES) -> str:
    """One shaded radial gradient per tone, a water gradient, and arrow markers."""
    g = []
    for t in tones:
        g.append(
            f'<radialGradient id="{prefix}-{t}" cx="35%" cy="30%" r="80%">'
            f'<stop offset="0" style="stop-color:color-mix(in srgb, var(--dg-{t}) 62%, white)"/>'
            f'<stop offset=".55" style="stop-color:var(--dg-{t})"/>'
            f'<stop offset="1" style="stop-color:color-mix(in srgb, var(--dg-{t}) 70%, black)"/></radialGradient>')
    g.append(f'<linearGradient id="{prefix}-wcol" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" style="stop-color:var(--dg-water)"/><stop offset="1" style="stop-color:var(--dg-water-deep)"/></linearGradient>')
    g.append(f'<linearGradient id="{prefix}-sky" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" style="stop-color:var(--dg-sky)"/><stop offset="1" style="stop-color:var(--surface)"/></linearGradient>')
    g.append(f'<marker id="{prefix}-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             f'<path d="M0 0L10 5L0 10z" style="fill:var(--dg-flow)"/></marker>')
    g.append(f'<marker id="{prefix}-arrow-ink" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             f'<path d="M0 0L10 5L0 10z" style="fill:var(--muted)"/></marker>')
    return "<defs>" + "".join(g) + "</defs>"


def fill(prefix: str, tone: str) -> str:
    return f'fill="url(#{prefix}-{tone})"'


def shape(d: str, prefix: str, tone: str, stroke: str = "var(--dg-line)", sw: float = 1, extra: str = "") -> str:
    return f'<path d="{d}" {fill(prefix, tone)} style="stroke:{stroke}" stroke-width="{n(sw)}" stroke-linejoin="round" {extra}/>'


def line(points, stroke="var(--dg-line)", sw=1.0, extra="") -> str:
    return f'<polyline points="{pts(points)}" fill="none" style="stroke:{stroke}" stroke-width="{n(sw)}" stroke-linecap="round" stroke-linejoin="round" {extra}/>'


def text(x, y, words, cls="t-label", anchor="start", extra="") -> str:
    return f'<text class="{cls}" x="{n(x)}" y="{n(y)}" text-anchor="{anchor}" {extra}>{escape(str(words))}</text>'


def label(at, to, words, sub=None, anchor="start", cls="dg-name") -> str:
    """Dot on the object at `at`, leader to `to`, words beyond it (sub-line underneath)."""
    (x0, y0), (x1, y1) = at, to
    dx = 4 if anchor == "start" else -4 if anchor == "end" else 0
    s = (f'<circle cx="{n(x0)}" cy="{n(y0)}" r="2.6" style="fill:var(--ink)"/>'
         f'<line x1="{n(x0)}" y1="{n(y0)}" x2="{n(x1)}" y2="{n(y1)}" style="stroke:var(--ink)" stroke-width=".9"/>')
    s += text(x1 + dx, y1 + 4, words, cls, anchor)
    if sub:
        s += text(x1 + dx, y1 + 19, sub, "dg-sub", anchor)
    return s


def lens(prefix: str, key: str, at, r, c, R, content: str, badge: str = "not to scale") -> str:
    """Magnifier inset: amber ring at the true spot, tangent lines, double-ringed clipped frame, badge."""
    (ax, ay), (cx, cy) = at, c
    d = math.hypot(cx - ax, cy - ay)
    s = ""
    if d > abs(R - r):
        phi = math.atan2(cy - ay, cx - ax)
        a = math.acos((r - R) / d)
        for sign in (1, -1):
            t = phi + sign * a
            p1 = (ax + r * math.cos(t), ay + r * math.sin(t))
            p2 = (cx + R * math.cos(t), cy + R * math.sin(t))
            s += f'<line x1="{n(p1[0])}" y1="{n(p1[1])}" x2="{n(p2[0])}" y2="{n(p2[1])}" style="stroke:var(--dg-nts)" stroke-width="1" opacity=".8"/>'
    cid = f"{prefix}-clip-{key}"
    s += (f'<circle cx="{n(ax)}" cy="{n(ay)}" r="{n(r)}" fill="none" style="stroke:var(--dg-nts)" stroke-width="1.6"/>'
          f'<clipPath id="{cid}"><circle cx="{n(cx)}" cy="{n(cy)}" r="{n(R - 3)}"/></clipPath>'
          f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(R)}" style="fill:var(--surface);stroke:var(--dg-nts)" stroke-width="2"/>'
          f'<g clip-path="url(#{cid})">{content}</g>'
          f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(R - 3)}" fill="none" style="stroke:var(--dg-nts)" stroke-width=".8"/>')
    if badge:
        w = 7 * len(badge) + 14
        s += (f'<rect x="{n(cx - w / 2)}" y="{n(cy + R - 9)}" width="{n(w)}" height="18" rx="9" style="fill:var(--surface);stroke:var(--dg-nts)"/>'
              f'<text class="dg-nts" x="{n(cx)}" y="{n(cy + R + 4)}" text-anchor="middle">{escape(badge)}</text>')
    return s


def place(svg: str, x, y, scale=1.0, rotate=0.0) -> str:
    return f'<g transform="translate({n(x)} {n(y)}) rotate({n(rotate)}) scale({scale:.3f})">{svg}</g>'


def figure(prefix: str, width: int, height: int, title: str, body: str, flow: bool = False) -> str:
    """Whole diagram: theme-aware SVG with its own gradient ids."""
    return (f'<svg class="dg{" dg-anim" if flow else ""}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
            f'{defs(prefix)}{body}</svg>')
