"""Link-preview images: the share card and the site icons, rendered with headless Chrome.

Follows ClaudeHub webapp-conventions/link-preview-cards-on-github-pages-project-sites:
  og-image.png          1200 x 630, text about 100 px inside the edges
  apple-touch-icon.png  180 x 180, full bleed, no transparency (iOS rounds it)
  favicon-32.png        32 x 32
  icon.svg              vector icon for browser tabs
Bump SHARE_VERSION whenever the images change: Messages caches previews per URL.

Usage: python -m iwla_river.web.share     (then rebuild the site)
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .. import config as C
from .db import DB, fmt
from .diagrams import bugs
from .diagrams.kit import figure, place

SHARE_VERSION = 3
HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700'
         '&family=IBM+Plex+Mono:wght@500&display=swap">')


def _shot(html: str, out: Path, w: int, h: int) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "card.html"
        page.write_text(html)
        out.unlink(missing_ok=True)
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                            f"--user-data-dir={tmp}/profile", "--no-first-run", "--no-default-browser-check",
                            f"--window-size={w},{h}", "--virtual-time-budget=6000", f"--screenshot={out}", page.as_uri()],
                           capture_output=True, text=True, timeout=120)
        if not out.exists():  # Chrome's exit code is unreliable; the file is the test
            raise RuntimeError(f"headless Chrome made no image: {r.stderr[-400:]}")


def _css() -> str:
    return (ASSETS / "site.css").read_text()


# Sources that feed the analysis, drawn as tributaries: (label, colour, source x, source y).
SOURCES = [("Volunteer samples", "#5fb3d3", 70, 52), ("Lab chemistry", "#c296c7", 300, 96),
           ("EPA assessments", "#e0a84a", 520, 52), ("Land cover 1985–2025", "#9cc46a", 740, 96)]


def _rand(seed: int):
    """Small fixed generator so the picture is the same on every build."""
    x = seed
    while True:
        x = (x * 1103515245 + 12345) % 2**31
        yield x / 2**31


def integration_art() -> str:
    """Dark river scene: four data sources run down as tributaries, join one river, and come out as a trend."""
    W, H, RY = 1200, 330, 262  # RY: main river centre line
    r = _rand(7)
    s = ['<defs><linearGradient id="og-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0f1719"/>'
         '<stop offset="1" stop-color="#10221f"/></linearGradient>'
         '<linearGradient id="og-river" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1d4f66"/>'
         '<stop offset=".75" stop-color="#2f6f8c"/><stop offset="1" stop-color="#3f88a8"/></linearGradient>'
         '<radialGradient id="og-glow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#e0a84a" stop-opacity=".18"/>'
         '<stop offset="1" stop-color="#e0a84a" stop-opacity="0"/></radialGradient></defs>',
         ]
    # Two ridges of hills with a few conifers, darkest at the back.
    s.append('<path d="M0 150 C120 118 210 132 330 140 S560 112 690 128 S920 150 1040 126 S1170 120 1200 128 V330 H0Z" fill="#13272a"/>')
    s.append('<path d="M0 196 C150 170 260 186 400 182 S640 168 780 186 S1000 196 1200 176 V330 H0Z" fill="#162f2c"/>')
    for x in range(30, 1200, 46):
        if 880 < x < 1180:
            continue
        y = 150 + 28 * next(r) if x % 92 else 186 + 8 * next(r)
        h = 22 + 22 * next(r)
        s.append(f'<path d="M{x} {y - h:.0f} L{x + h * .32:.0f} {y:.0f} H{x - h * .32:.0f}Z" fill="#1f3d33" opacity=".9"/>')
    # Tributaries: one coloured stream per source, dotted with "data" flowing down into the river.
    for i, (label, col, sx, sy) in enumerate(SOURCES):
        jx = sx + 150
        d = f"M{sx} {sy + 10} C{sx + 6} {sy + 90} {jx - 70} {RY - 22} {jx} {RY - 6}"
        s.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="5" stroke-opacity=".38" stroke-linecap="round"/>')
        s.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="7" stroke-linecap="round" stroke-dasharray="0 17"/>')
        s.append(f'<circle cx="{sx}" cy="{sy}" r="9" fill="#0f1719" stroke="{col}" stroke-width="3"/>')
        s.append(f'<text x="{sx + 18}" y="{sy + 7}" font-family="Archivo, sans-serif" font-weight="600" font-size="20" fill="{col}">{label}</text>')
    # The main river, with flow lines, stones on the bed and a few nymphs holding on (they face upstream).
    bank = f"M-10 {RY - 20} C200 {RY - 30} 420 {RY - 14} 640 {RY - 22} S860 {RY - 24} 952 {RY + 4}"
    bed = f"C900 {RY + 20} 840 {RY + 26} 640 {RY + 24} S120 {RY + 24} -10 {RY + 26}Z"
    s.append(f'<path d="{bank} {bed}" fill="url(#og-river)"/>')
    for y, a, b in ((RY - 8, 20, 860), (RY + 4, 90, 900), (RY + 14, 40, 780)):
        s.append(f'<path d="M{a} {y} H{b}" stroke="#9fd0e4" stroke-opacity=".28" stroke-width="2" stroke-dasharray="38 22 12 30"/>')
    for x in range(10, 880, 37):
        w = 16 + 14 * next(r)
        s.append(f'<ellipse cx="{x + 10 * next(r):.0f}" cy="{RY + 30:.0f}" rx="{w:.0f}" ry="{w * .42:.0f}" fill="#4a4740" stroke="#5a574f"/>')
    s.append(f'<rect x="0" y="{RY + 34}" width="{W}" height="{H - RY - 34}" fill="#1e1a15"/>')
    for bug, x, sc in ((bugs.mayfly, 230, .42), (bugs.stonefly, 500, .42), (bugs.mayfly, 760, .36)):
        s.append(place(bug("og"), x, RY + 2, sc, -90))
    # Where the river comes out: the joined data as a scatter with a trend and its band.
    px, py, pw, ph = 952, RY - 150, 206, 146
    s.append(f'<ellipse cx="{px + pw / 2}" cy="{py + ph / 2}" rx="190" ry="140" fill="url(#og-glow)"/>')
    s.append(f'<path d="M{px} {py} V{py + ph} H{px + pw}" fill="none" stroke="#6f8083" stroke-width="2"/>')
    s.append(f'<path d="M{px} {py + ph - 22} L{px + pw} {py + 34} V{py + 64} L{px} {py + ph - 2}Z" fill="#e0a84a" opacity=".16"/>')
    for k in range(34):
        t = next(r)
        y = py + ph - 12 - t * (ph - 58) - 30 * (next(r) - .5)
        col = SOURCES[k % 4][1]
        s.append(f'<circle cx="{px + 8 + t * (pw - 16):.0f}" cy="{min(py + ph - 6, y):.0f}" r="4.2" fill="{col}" opacity=".85"/>')
    s.append(f'<path d="M{px} {py + ph - 12} L{px + pw} {py + 49}" stroke="#e0a84a" stroke-width="4" stroke-linecap="round"/>')
    s.append(f'<text x="{px + pw}" y="{py - 16}" text-anchor="end" font-family="Archivo, sans-serif" font-weight="600" font-size="20" fill="#e3ebea">Cited findings</text>')
    return figure("og", W, H, "Data sources joining one river of analysis", "".join(s))


def card_html(db: DB) -> str:
    usable = db.one("SELECT count(*) FROM surveys WHERE usable")
    return f"""<!doctype html><html data-theme="dark"><head><meta charset="utf-8">{FONTS}<style>{_css()}
      html, body {{ margin: 0; width: 1200px; height: 630px; overflow: hidden; background: linear-gradient(#0f1719 0 55%, #11211f); }}
      :root {{ padding: 0 !important; }}
      .card {{ position: relative; width: 1200px; height: 630px; }}
      .art {{ position: absolute; left: 0; right: 0; bottom: 0; height: 330px; }}
      .art svg {{ width: 1200px; height: 330px; display: block; }}
      .txt {{ position: absolute; left: 100px; top: 54px; right: 100px; display: flex; flex-direction: column; gap: 14px; }}
      .eb {{ font: 600 22px/1.2 Archivo, sans-serif; letter-spacing: .08em; text-transform: uppercase; color: #5fb3d3; }}
      h1 {{ font: 700 78px/1 Archivo, sans-serif; margin: 0; color: #e3ebea; letter-spacing: -.01em; }}
      .sub {{ font: 500 28px/1.3 Archivo, sans-serif; color: #9db0b2; }}
      .sub b {{ color: #e3ebea; font-weight: 600; }}
    </style></head><body><div class="card">
      <div class="txt">
        <div class="eb">Independent analysis · Save Our Streams data</div>
        <h1>Save Our Streams Record</h1>
        <div class="sub"><b>{fmt(usable)}</b> volunteer stream samples, joined with EPA,<br>USGS and land-cover data · every result cited</div>
      </div>
      <div class="art">{integration_art()}</div>
    </div></body></html>"""


def icon_svg() -> str:
    """A mayfly nymph on the site's river blue: the animal the whole score leans on."""
    body = f'<rect width="100" height="100" fill="#1d6a86"/>' + place(bugs.mayfly("ic"), 50, 6, 0.86)
    svg = figure("ic", 100, 100, "Save Our Streams Record", body)
    # Icons do not follow the page theme: pin the palette to light values.
    return svg.replace('<svg class="dg"', '<svg xmlns="http://www.w3.org/2000/svg" class="dg" data-theme="light"', 1)


def icon_html(size: int) -> str:
    return (f'<!doctype html><html data-theme="light"><head><meta charset="utf-8"><style>{_css()}'
            f'html,body{{margin:0;width:{size}px;height:{size}px;overflow:hidden;background:#1d6a86}}:root{{padding:0!important}}'
            f'svg{{width:{size}px;height:{size}px;display:block}}</style></head><body>{icon_svg()}</body></html>')


def build(db_path=C.DB_PATH) -> None:
    db = DB(db_path)
    _shot(card_html(db), ASSETS / "og-image.png", 1200, 630)
    _shot(icon_html(180), ASSETS / "apple-touch-icon.png", 180, 180)
    _shot(icon_html(32), ASSETS / "favicon-32.png", 32, 32)
    # Standalone SVG icon: inline the palette values it needs, since it is loaded without the stylesheet.
    css = _css()
    root = css[css.rindex(":root", 0, css.index("--dg-line")):]
    root = root[:root.index("}") + 1]
    svg = icon_svg().replace("<defs>", f"<style>{root.replace(':root', 'svg')}</style><defs>", 1)
    (ASSETS / "icon.svg").write_text(svg)
    for f in ("og-image.png", "apple-touch-icon.png", "favicon-32.png", "icon.svg"):
        print(f, (ASSETS / f).stat().st_size)


if __name__ == "__main__":
    build()
