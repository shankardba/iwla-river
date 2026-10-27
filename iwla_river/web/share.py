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
from .diagrams import bugs, plates
from .diagrams.kit import figure, place

SHARE_VERSION = 1
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


def card_html(db: DB) -> str:
    sos, va = db.sos(), db.va()
    first = min(int(r["date"][:4]) for r in sos)
    last = max(int(r["date"][:4]) for r in sos + va)
    usable = db.one("SELECT count(*) FROM surveys WHERE usable")
    art = plates.riffle("og", labels=False).replace('viewBox="0 0 760 340"', 'viewBox="0 70 760 230" preserveAspectRatio="xMidYMid slice"')
    return f"""<!doctype html><html data-theme="light"><head><meta charset="utf-8">{FONTS}<style>{_css()}
      html, body {{ margin: 0; width: 1200px; height: 630px; overflow: hidden; background: var(--bg); }}
      :root {{ padding: 0 !important; }}
      .card {{ position: relative; width: 1200px; height: 630px; }}
      .art {{ position: absolute; left: 0; right: 0; bottom: 0; height: 300px; }}
      .art svg {{ width: 1200px; height: 300px; display: block; }}
      .txt {{ position: absolute; left: 100px; top: 64px; right: 100px; display: flex; flex-direction: column; gap: 14px; }}
      .eb {{ font: 600 22px/1.2 Archivo, sans-serif; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }}
      h1 {{ font: 700 78px/1 Archivo, sans-serif; margin: 0; color: var(--ink); letter-spacing: -.01em; }}
      .sub {{ font: 500 28px/1.3 Archivo, sans-serif; color: var(--muted); }}
      .sub b {{ color: var(--ink); font-weight: 600; }}
    </style></head><body><div class="card">
      <div class="txt">
        <div class="eb">IWLA Rockville Chapter · Save Our Streams</div>
        <h1>Great Seneca Creek Record</h1>
        <div class="sub">Stream surveys since <b>{first}</b>, read against <b>{fmt(usable)}</b> nationwide</div>
      </div>
      <div class="art">{art}</div>
    </div></body></html>"""


def icon_svg() -> str:
    """A mayfly nymph on the site's river blue: the animal the whole score leans on."""
    body = f'<rect width="100" height="100" fill="#1d6a86"/>' + place(bugs.mayfly("ic"), 50, 6, 0.86)
    svg = figure("ic", 100, 100, "Great Seneca Creek Record", body)
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
    root = css[css.index(":root {\n  --dg-line"):]
    root = root[:root.index("}") + 1]
    svg = icon_svg().replace("<defs>", f"<style>{root.replace(':root', 'svg')}</style><defs>", 1)
    (ASSETS / "icon.svg").write_text(svg)
    for f in ("og-image.png", "apple-touch-icon.png", "favicon-32.png", "icon.svg"):
        print(f, (ASSETS / f).stat().st_size)


if __name__ == "__main__":
    build()
