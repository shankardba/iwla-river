"""Terrain for the Explore map: heights from AWS Terrain Tiles, river height profiles,
shaded-relief images in the map's own Albers projection, and named mountain peaks.

DEM: AWS Terrain Tiles (open data, terrarium encoding), elevation m = R*256 + G + B/256 - 32768.
Tiles are cached in NOMAD's map library (or data/cache/terrain when that is not writable).

    python -m iwla_river.terrain --stage tiles|relief|peaks|rivers|all
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import math
import os
import time
import urllib.request
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from . import config as C

URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
LIBRARY = Path("/Volumes/OricoArray/Daemon/library/maps")
PMTILES = LIBRARY / "pmtiles"
DOCS = C.ROOT / "docs" / "data"
OUT = DOCS / "terrain"
R_EARTH = 6371000.0

# Same parameters as COUNTRY[...].proj in web/assets/explorer.js: [lon0, lat0, parallel1, parallel2].
PROJ = {"us": (-96, 23, 29.5, 45.5), "in": (80, 8, 12, 28)}

# Hypsometric ramp (metres -> RGB). terrain.js carries the same stops for its legend.
RAMP = [(0, (200, 224, 184)), (150, (214, 231, 186)), (400, (230, 226, 178)), (800, (226, 206, 156)),
        (1300, (206, 176, 128)), (2000, (178, 144, 108)), (3000, (152, 124, 104)), (4000, (196, 186, 178)),
        (5200, (244, 244, 246))]


def _tile_dir() -> Path:
    d = LIBRARY / "terrain" / "terrarium"
    try:
        d.mkdir(parents=True, exist_ok=True)
        t = d / ".w"
        t.write_bytes(b"")
        t.unlink()
        return d
    except OSError:
        d = C.DATA / "cache" / "terrain"
        d.mkdir(parents=True, exist_ok=True)
        return d


TILES = _tile_dir()


# ---------- projection (copied from explorer.js albers) ----------
def albers(lat, lon, country="us"):
    L0, P0, P1, P2 = PROJ[country]
    r = math.pi / 180
    f1, f2, f0 = P1 * r, P2 * r, P0 * r
    n = (math.sin(f1) + math.sin(f2)) / 2
    c = math.cos(f1) ** 2 + 2 * n * math.sin(f1)
    rho0 = math.sqrt(c - 2 * n * math.sin(f0)) / n
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    rho = np.sqrt(c - 2 * n * np.sin(lat * r)) / n
    th = n * (lon - L0) * r
    return rho * np.sin(th), rho0 - rho * np.cos(th)


def albers_inv(x, y, country="us"):
    L0, P0, P1, P2 = PROJ[country]
    r = math.pi / 180
    f1, f2, f0 = P1 * r, P2 * r, P0 * r
    n = (math.sin(f1) + math.sin(f2)) / 2
    c = math.cos(f1) ** 2 + 2 * n * math.sin(f1)
    rho0 = math.sqrt(c - 2 * n * math.sin(f0)) / n
    x, y = np.asarray(x, float), np.asarray(y, float)
    rho = np.hypot(x, rho0 - y)
    th = np.arctan2(x, rho0 - y)
    lon = L0 + th / n / r
    lat = np.arcsin(np.clip((c - (rho * n) ** 2) / (2 * n), -1, 1)) / r
    return lon, lat


# ---------- web mercator tiles ----------
def _gpx(lon, lat, z):
    """Global pixel coordinates (256-px tiles) of lon/lat at zoom z."""
    s = 256 * 2 ** z
    lat = np.clip(np.asarray(lat, float), -85.05, 85.05)
    gx = (np.asarray(lon, float) + 180) / 360 * s
    gy = (1 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2 * s
    return gx, gy


def num2deg(x, y, z):
    n = 2 ** z
    return x / n * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))


def _path(z, x, y) -> Path:
    return TILES / str(z) / str(x) / f"{y}.png"


_HAVE: set = set()   # tiles known to be on disk (the library is a network volume: every stat costs ~10 ms)


def fetch(z, x, y, tries=4) -> bool:
    if (z, x, y) in _HAVE:
        return True
    p = _path(z, x, y)
    if p.exists() and p.stat().st_size > 0:
        _HAVE.add((z, x, y))
        return True
    p.parent.mkdir(parents=True, exist_ok=True)
    for i in range(tries):
        try:
            req = urllib.request.Request(URL.format(z=z, x=x, y=y), headers={"User-Agent": "iwla-river terrain (research)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            tmp = p.with_suffix(".part")
            tmp.write_bytes(data)
            os.replace(tmp, p)
            _HAVE.add((z, x, y))
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            time.sleep(1.5 * (i + 1))
        except Exception:
            time.sleep(1.5 * (i + 1))
    return False


def fetch_many(tiles, threads=4, label=""):
    todo = []
    for t in set(tiles) - _HAVE:
        if _path(*t).exists():
            _HAVE.add(t)
        else:
            todo.append(t)
    if not todo:
        return
    t0 = time.time()
    with ThreadPoolExecutor(threads) as ex:
        for i, _ in enumerate(ex.map(lambda t: fetch(*t), todo)):
            if (i + 1) % 200 == 0:
                print(f"  {label} {i + 1}/{len(todo)} tiles  {time.time() - t0:.0f}s", flush=True)


_MEM: OrderedDict = OrderedDict()


def _despike(a, lim=600.0):
    """Terrarium has rare one-pixel spikes (e.g. 3,375 m in the Adirondacks at z10); replace any pixel
    more than `lim` metres from its 3x3 median by that median."""
    p = np.pad(a, 1, mode="edge")
    nb = np.stack([p[1 + dy:257 + dy, 1 + dx:257 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    med = np.median(nb, axis=0)
    bad = np.abs(a - med) > lim
    return np.where(bad, med, a).astype(np.float32) if bad.any() else a.astype(np.float32)


def tile(z, x, y) -> np.ndarray:
    k = (z, x, y)
    if k in _MEM:
        _MEM.move_to_end(k)
        return _MEM[k]
    from PIL import Image
    n = 2 ** z
    x %= n
    if not (0 <= y < n):
        a = np.zeros((256, 256), np.float32)
    else:
        p = _path(z, x, y)
        if (z, x, y) not in _HAVE:
            fetch(z, x, y)
        try:
            im = np.asarray(Image.open(p).convert("RGB"), np.float32)
            a = _despike(im[..., 0] * 256 + im[..., 1] + im[..., 2] / 256 - 32768)
        except Exception:
            a = np.zeros((256, 256), np.float32)
    _MEM[k] = a
    if len(_MEM) > 1500:   # ~400 MB of decoded tiles
        _MEM.popitem(last=False)
    return a


def _gather(z, ix, iy):
    """Elevation at integer global pixels (arrays)."""
    ix, iy = np.asarray(ix, np.int64), np.asarray(iy, np.int64)
    out = np.zeros(ix.shape, np.float32)
    tx, ty = ix >> 8, iy >> 8
    key = tx * (1 << 22) + ty
    order = np.argsort(key, kind="stable")
    ks = key[order]
    cuts = np.flatnonzero(np.diff(ks)) + 1
    for grp in np.split(order, cuts):
        if not len(grp):
            continue
        a = tile(z, int(tx[grp[0]]), int(ty[grp[0]]))
        out[grp] = a[iy[grp] & 255, ix[grp] & 255]
    return out


def tiles_for(points, z, pad=True):
    pts = np.asarray(points, float).reshape(-1, 2)
    gx, gy = _gpx(pts[:, 0], pts[:, 1], z)
    s = set()
    for dx in ((-0.5, 0.5) if pad else (0,)):
        for dy in ((-0.5, 0.5) if pad else (0,)):
            s.update(zip(((gx + dx) // 256).astype(int).tolist(), ((gy + dy) // 256).astype(int).tolist()))
    return [(z, x, y) for x, y in s]


def heights(points, z=11, prefetch=True):
    """Bilinear DEM heights (m) for [[lon, lat], ...]."""
    pts = np.asarray(points, float).reshape(-1, 2)
    if not len(pts):
        return np.zeros(0)
    if prefetch:
        fetch_many(tiles_for(pts, z))
    gx, gy = _gpx(pts[:, 0], pts[:, 1], z)
    gx, gy = gx - 0.5, gy - 0.5
    x0, y0 = np.floor(gx), np.floor(gy)
    fx, fy = gx - x0, gy - y0
    x0, y0 = x0.astype(np.int64), y0.astype(np.int64)
    v00, v10 = _gather(z, x0, y0), _gather(z, x0 + 1, y0)
    v01, v11 = _gather(z, x0, y0 + 1), _gather(z, x0 + 1, y0 + 1)
    return (v00 * (1 - fx) * (1 - fy) + v10 * fx * (1 - fy) + v01 * (1 - fx) * fy + v11 * fx * fy).astype(float)


def height(lon, lat, z=11):
    return float(heights([[lon, lat]], z)[0])


def summit(points, z=12):
    """Highest DEM pixel within one pixel of each point (OSM peak nodes sit a few tens of metres off)."""
    pts = np.asarray(points, float).reshape(-1, 2)
    fetch_many(tiles_for(pts, z))
    gx, gy = _gpx(pts[:, 0], pts[:, 1], z)
    ix, iy = np.floor(gx).astype(np.int64), np.floor(gy).astype(np.int64)
    best = np.full(len(pts), -1e9)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            best = np.maximum(best, _gather(z, ix + dx, iy + dy))
    return best


# ---------- rivers ----------
def _km(a, b):
    la = math.radians((a[1] + b[1]) / 2)
    return math.hypot((b[0] - a[0]) * math.cos(la), b[1] - a[1]) * 111.195


def _chain(paths, start=None, end=None):
    """Order a river's pieces from source to mouth: greedy nearest-endpoint chaining from the source."""
    pieces = [list(map(tuple, p)) for p in paths if len(p) > 1]
    if not pieces:
        return []
    if start is None:
        cur = max(pieces, key=lambda p: sum(_km(a, b) for a, b in zip(p, p[1:])))
        pieces.remove(cur)
        line = list(cur)
    else:
        line = [tuple(start)]
    while pieces:
        e = line[-1]
        best, bd, rev = None, 1e18, False
        for p in pieces:
            d0, d1 = _km(e, p[0]), _km(e, p[-1])
            if d0 < bd:
                best, bd, rev = p, d0, False
            if d1 < bd:
                best, bd, rev = p, d1, True
        if end is not None and _km(e, tuple(end)) < bd and bd > 1:
            break   # the mouth is closer than any piece left: the rest are side channels
        pieces.remove(best)
        line.extend(best[::-1] if rev else best)
    if end is not None and _km(line[-1], tuple(end)) > 0.3:
        line.append(tuple(end))
    return line


def _resample(line, n):
    cum = [0.0]
    for a, b in zip(line, line[1:]):
        cum.append(cum[-1] + _km(a, b))
    cum = np.array(cum)
    t = np.linspace(0, cum[-1], n)
    lon = np.interp(t, cum, [p[0] for p in line])
    lat = np.interp(t, cum, [p[1] for p in line])
    return t, np.column_stack([lon, lat])


def profile(path_lonlat, n=40, z=11):
    """[[km_from_start, metres], ...] along a polyline drawn downstream (start = upstream).
    Heights are made non-increasing downstream (water does not climb), which removes DEM spikes
    where the line crosses a bank or a bridge."""
    line = [tuple(p) for p in path_lonlat]
    if len(line) < 2:
        return []
    t, pts = _resample(line, n)
    h = heights(pts, z)
    h = np.maximum(np.minimum.accumulate(h), 0)   # tidal reaches read a metre or two below sea level
    return [[round(float(a), 1), int(round(float(b)))] for a, b in zip(t, h)]


MEMO = C.DATA / "cache" / "terrain_points.json"


def _pkey(z, q):
    return f"{z}/{float(q[0]):.5f}/{float(q[1]):.5f}"


def _load_memo():
    try:
        return json.load(open(MEMO))
    except Exception:
        return {}


def _save_memo(memo):
    tmp = MEMO.with_suffix(".part")
    tmp.write_text(json.dumps(memo, separators=(",", ":")))
    os.replace(tmp, MEMO)


def fill_rivers(rivers, n=32, z=11, min_km=5):
    """Fill missing source/mouth heights (se/me) from the DEM and add `pf`, a height profile
    [[km, m], ...] (km 1 dp, m int) for rivers at least `min_km` long. Rows use the build's
    packed keys (n, L, s, se, m, me, p). Where a profile is made, se/me are set from its ends so
    labels and profile agree. Rivers whose pieces here chain to under half (or over twice) their
    length L get no pf. Returns the same list, changed in place."""
    def zoom(r):   # long rivers sit in wide valleys; a coarser grid keeps the tile count sane (3,000+ national rivers)
        L = r.get("L") or 0
        return min(z, 11 if L < 40 else 10 if L < 150 else 9)

    jobs = []
    for r in rivers:
        line = None
        if (r.get("L") or 0) >= min_km and r.get("p"):
            line = _chain(r["p"], r.get("s"), r.get("m"))
            if len(line) > 1:
                t, pts = _resample(line, n)
                L = r["L"]
                line = (t, pts) if t[-1] > 0 and 0.5 <= L / t[-1] <= 2 else None   # too little of the river here to draw it honestly
            else:
                line = None
        jobs.append((r, line, zoom(r)))
    # Every height needed, as (zoom, lon, lat); answered from a local memo, the rest in one batch per zoom
    # (each DEM tile is then read once: the tile library sits on a network share, ~60 ms a tile).
    want = {}
    for r, line, zr in jobs:
        for k in ("s", "m"):
            if r.get(k):
                want[_pkey(zr, r[k])] = (zr, r[k])
        if line:
            for q in line[1]:
                want[_pkey(zr, q)] = (zr, q)
    memo = _load_memo()
    todo = {k: v for k, v in want.items() if k not in memo}
    if todo:
        fetch_many({t for zr, q in todo.values() for t in tiles_for([q], zr)}, label="rivers")
        for zr in {v[0] for v in todo.values()}:
            ks = [k for k, v in todo.items() if v[0] == zr]
            g = [_gpx(todo[k][1][0], todo[k][1][1], zr) for k in ks]
            ks = [k for _, k in sorted(zip(((int(x // 2048), int(y // 2048)) for x, y in g), ks))]   # 8x8-tile blocks
            for i in range(0, len(ks), 4000):   # chunks small enough that their tiles stay decoded
                part = ks[i:i + 4000]
                for k, v in zip(part, heights([todo[k][1] for k in part], zr, prefetch=False)):
                    memo[k] = round(float(v), 1)
        _save_memo(memo)
    for r, line, zr in jobs:
        for k, ek in (("s", "se"), ("m", "me")):
            if r.get(k) and r.get(ek) is None:
                r[ek] = max(0, int(round(memo[_pkey(zr, r[k])])))
        if line:
            t, pts = line
            h = np.maximum(np.minimum.accumulate([memo[_pkey(zr, q)] for q in pts]), 0)
            f = float(r["L"] / t[-1])   # stretch the chained length to the river's own length
            r["pf"] = [[round(float(a) * f, 1), int(round(float(v)))] for a, v in zip(t, h)]
            r["se"], r["me"] = r["pf"][0][1], r["pf"][-1][1]   # keep the end labels and the profile in step
    return rivers


# ---------- shaded relief ----------
def _tint(e):
    xs = [a for a, _ in RAMP]
    return np.stack([np.interp(e, xs, [c[i] for _, c in RAMP]) for i in range(3)], -1)


def _mask(rings_list, country, bbox, w, h):
    from PIL import Image, ImageChops, ImageDraw  # noqa
    x0, y0, x1, y1 = bbox
    m = Image.new("L", (w, h), 0)
    for ring in rings_list:
        if len(ring) < 3:
            continue
        a = np.asarray(ring, float)
        px, py = albers(a[:, 1], a[:, 0], country)
        u = (px - x0) / (x1 - x0) * w
        v = (y1 - py) / (y1 - y0) * h
        one = Image.new("L", (w, h), 0)
        ImageDraw.Draw(one).polygon(list(zip(u.tolist(), v.tolist())), fill=255)
        m = ImageChops.lighter(m, one)
    return np.asarray(m) > 0


def relief(key, bbox, country, width, z, mask_rings=None, colors=48):
    """Render one shaded-relief PNG covering projected bbox [x0, y0, x1, y1]."""
    from PIL import Image
    x0, y0, x1, y1 = bbox
    asp = (y1 - y0) / (x1 - x0)
    w = int(width if asp <= 1 else max(200, width / asp))   # `width` is the longer side
    h = max(1, int(round(w * asp)))
    xs = x0 + (np.arange(w) + 0.5) / w * (x1 - x0)
    ys = y1 - (np.arange(h) + 0.5) / h * (y1 - y0)
    X, Y = np.meshgrid(xs, ys)
    lon, lat = albers_inv(X.ravel(), Y.ravel(), country)
    pts = np.column_stack([lon, lat])
    fetch_many(tiles_for(pts[:: max(1, len(pts) // 200000)], z) + tiles_for(_edge(lon, lat, w, h), z), label=key)
    e = heights(pts, z, prefetch=False).reshape(h, w)
    land = e > -5 if mask_rings is None else _mask(mask_rings, country, bbox, w, h)
    e = np.where(land, np.maximum(e, 0), 0)
    # hillshade: sun from the north-west, 45 degrees up
    pix = (x1 - x0) / w * R_EARTH
    zf = max(1.0, (pix / 90) ** 0.45)          # coarse images need more relief to show any
    dzdx = np.gradient(e, axis=1) / pix * zf
    dzdn = -np.gradient(e, axis=0) / pix * zf  # rows run south
    alt, az = math.radians(45), math.radians(315)
    L = np.array([math.cos(alt) * math.sin(az), math.cos(alt) * math.cos(az), math.sin(alt)])
    nrm = np.sqrt(dzdx ** 2 + dzdn ** 2 + 1)
    shade = np.clip((-dzdx * L[0] - dzdn * L[1] + L[2]) / nrm, 0, 1) / L[2]
    rgb = _tint(e) * (0.55 + 0.45 * np.clip(shade, 0, 1.35))[..., None]
    rgba = np.dstack([np.clip(rgb, 0, 255), np.where(land, 255, 0)]).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA").quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / f"{key}.png", optimize=True)
    lv = e[land] if land.any() else np.zeros(1)
    return {"bbox": [round(v, 6) for v in bbox], "country": country, "z": z, "px": [w, h],
            "min": int(lv.min()), "max": int(lv.max())}


def _edge(lon, lat, w, h):
    a = np.column_stack([lon, lat]).reshape(h, w, 2)
    return np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])


def _bbox(rings_list, country, margin=0.03):
    a = np.concatenate([np.asarray(r, float) for r in rings_list if len(r)])
    px, py = albers(a[:, 1], a[:, 0], country)
    x0, x1, y0, y1 = px.min(), px.max(), py.min(), py.max()
    mx, my = (x1 - x0) * margin, (y1 - y0) * margin
    return [x0 - mx, y0 - my, x1 + mx, y1 + my]


def _rings(v):
    """Flatten polygon / multipolygon nesting to a list of rings [[lon, lat], ...]."""
    if not v:
        return []
    if isinstance(v[0][0], (int, float)):
        return [v]
    return [r for x in v for r in _rings(x)]


def _outline(path):
    """A country's outline file holds open border arcs; stitch them into land polygons (exterior rings)."""
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union
    arcs = [LineString(r) for r in json.load(open(path))["border"] if len(r) > 1]
    return [[list(c) for c in p.exterior.coords] for p in polygonize(unary_union(arcs))]


def units():
    """Every image to make: key -> (country, rings for extent, mask rings, width, zoom)."""
    us = _outline(DOCS / "lower48.json")
    india = _outline(DOCS / "in" / "outline.json")
    out = {"us": ("us", us, us, 1600, 7), "in": ("in", india, india, 1400, 7)}
    reg = {}
    for f in sorted((DOCS / "rivers").glob("*.json")):
        h = f.stem[:4]
        r2 = reg.setdefault(h[:2], json.load(open(DOCS / "geo" / f"r{h[:2]}.json")))
        if h in r2:
            out[h] = ("us", _rings(r2[h]), us + _rings(r2[h]), 900, 10)   # land = the country plus the basin (some cross into Canada)
    for f in sorted((DOCS / "in" / "geo").glob("rI?.json")):
        g = f.stem[1:]
        rings = [r for v in json.load(open(f)).values() for r in _rings(v)]
        out[g] = ("in", rings, india + rings, 900, 8)   # basins run on into Nepal, Tibet and Bangladesh
    return out


def stage_relief(only=None):
    idx = {}
    p = OUT / "index.json"
    if p.exists():
        idx = json.load(open(p))
    for key, (country, rings, mask, width, z) in units().items():
        if only and key not in only:
            continue
        t0 = time.time()
        idx[key] = relief(key, _bbox(rings, country, 0.03 if key not in ("us", "in") else 0.01), country, width, z, mask)
        print(f"{key}: {idx[key]['px']} z{z} {idx[key]['min']}-{idx[key]['max']} m "
              f"{(OUT / f'{key}.png').stat().st_size // 1024} KB {time.time() - t0:.0f}s", flush=True)
        OUT.joinpath("index.json").write_text(json.dumps(idx, separators=(",", ":")))
    return idx


def stage_tiles():
    """Prefetch every DEM tile the relief images need."""
    for key, (country, rings, mask, width, z) in units().items():
        x0, y0, x1, y1 = _bbox(rings, country)
        n = 60
        X, Y = np.meshgrid(np.linspace(x0, x1, n), np.linspace(y0, y1, n))
        lon, lat = albers_inv(X.ravel(), Y.ravel(), country)
        lo, la = (lon.min(), lon.max()), (lat.min(), lat.max())
        gx0, gy1 = _gpx(lo[0], la[0], z)
        gx1, gy0 = _gpx(lo[1], la[1], z)
        ts = [(z, x, y) for x in range(int(gx0 // 256), int(gx1 // 256) + 1) for y in range(int(gy0 // 256), int(gy1 // 256) + 1)]
        print(f"{key}: {len(ts)} tiles z{z}", flush=True)
        fetch_many(ts, label=key)


# ---------- peaks from the OpenStreetMap vector tiles ----------
_R = None


def _open_maps(prefix):
    global _R
    from pmtiles.reader import Reader
    _R = []
    for p in sorted(PMTILES.glob("*.pmtiles")):
        if p.name.startswith("world") or (prefix == "in") != p.name.startswith("in_"):
            continue
        try:
            f = open(p, "rb")
            r = Reader(lambda off, n, f=f: (f.seek(off), f.read(n))[1])
            h = r.header()
        except Exception:
            continue
        _R.append((r, (h["min_lon_e7"] / 1e7, h["min_lat_e7"] / 1e7, h["max_lon_e7"] / 1e7, h["max_lat_e7"] / 1e7)))


def _tile_lat(yf, z):
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yf / 2 ** z))))


def _peaks_in(job):
    import mapbox_vector_tile as mvt
    z, x, ys = job
    out = []
    for y in ys:
        lon0, lat1 = num2deg(x, y, z)
        lon1, lat0 = num2deg(x + 1, y + 1, z)
        cx, cy = (lon0 + lon1) / 2, (lat0 + lat1) / 2
        for r, (a, b, c, d) in _R:
            if not (a - 0.3 <= cx <= c + 0.3 and b - 0.3 <= cy <= d + 0.3):
                continue
            try:
                data = r.get(z, x, y)
            except Exception:
                continue
            if not data:
                continue
            if data[:2] == b"\x1f\x8b":
                data = gzip.decompress(data)
            layer = mvt.decode(data, default_options={"y_coord_down": True}).get("pois")
            if layer:
                ext = layer.get("extent", 4096)
                for ft in layer["features"]:
                    pr, g = ft["properties"], ft["geometry"]
                    if pr.get("kind") not in ("peak", "volcano") or not pr.get("name") or g["type"] != "Point":
                        continue
                    px, py = g["coordinates"]
                    out.append((pr["name"], round(lon0 + px / ext * (lon1 - lon0), 5), round(_tile_lat(y + py / ext, z), 5)))
            break
    return out


def scan_peaks(bbox, z, prefix="us", procs=6):
    lo0, la0, lo1, la1 = bbox
    gx0, gy1 = _gpx(lo0, la0, z)
    gx1, gy0 = _gpx(lo1, la1, z)
    xs = range(int(gx0 // 256), int(gx1 // 256) + 1)
    ys = list(range(int(gy0 // 256), int(gy1 // 256) + 1))
    jobs = [(z, x, ys) for x in xs]
    with Pool(procs, initializer=_open_maps, initargs=(prefix,)) as pool:
        found = [p for part in pool.imap_unordered(_peaks_in, jobs) for p in part]
    seen, out = set(), []
    for nm, lo, la in found:
        k = (nm, round(lo, 3), round(la, 3))
        if k not in seen:
            seen.add(k)
            out.append((nm, lo, la))
    return out


def _inside(peaks, rings_list):
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep
    polys = []
    for r in rings_list:
        if len(r) >= 3:
            p = Polygon(r)
            polys.append(p if p.is_valid else p.buffer(0))
    shp = prep(unary_union(polys))
    return [p for p in peaks if shp.contains(Point(p[1], p[2]))]


def _rank(peaks, keep, coarse_z, fine_z=12, cand=None):
    """Coarse DEM heights pick candidates, then the 30 m grid gives each summit its height."""
    if not peaks:
        return []
    h0 = heights([[p[1], p[2]] for p in peaks], coarse_z)
    order = np.argsort(-h0)[: cand or keep * 3]
    top = [peaks[i] for i in order]
    h = summit([[p[1], p[2]] for p in top], fine_z)
    rows = sorted(([p[0], round(p[1], 4), round(p[2], 4), int(round(v))] for p, v in zip(top, h)), key=lambda r: -r[3])
    out, names = [], set()
    for r in rows:   # one entry per summit name nearby (OSM sometimes has duplicates)
        k = (r[0], round(r[1], 1), round(r[2], 1))
        if k in names:
            continue
        names.add(k)
        out.append(r)
    return out[:keep]


def stage_peaks():
    U = units()
    res = {}
    # US: each HUC4 at z13 (z12 holds only ~5 named summits per HUC4) inside its own boundary
    union = []
    for key, (country, rings, mask, width, z) in U.items():
        if country != "us" or key == "us":
            continue
        a = np.concatenate([np.asarray(r, float) for r in rings])
        bb = (a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max())
        t0 = time.time()
        pk = _inside(scan_peaks(bb, 13, "us"), rings)
        res[key] = _rank(pk, 25, 10)
        union += pk
        print(f"{key}: {len(pk)} named peaks, top {res[key][:1]} {time.time() - t0:.0f}s", flush=True)
    # US national: z11 carries the prominent summits; plus the HUC4 peaks
    t0 = time.time()
    us = U["us"][1]
    nat = _inside(scan_peaks((-125, 24.3, -66.8, 49.5), 11, "us"), us)
    print(f"us: {len(nat)} named peaks at z11 {time.time() - t0:.0f}s", flush=True)
    seen = {(p[0], round(p[1], 3), round(p[2], 3)) for p in nat}
    nat += [p for p in union if (p[0], round(p[1], 3), round(p[2], 3)) not in seen]
    res["us"] = _rank(nat, 60, 8, cand=400)
    # India: one z13 scan (z11/z12 hold only ~40/60 named summits), then the country and each level-2 group
    t0 = time.time()
    ib = np.concatenate([np.asarray(r, float) for r in U["in"][1]])
    allin = scan_peaks((ib[:, 0].min() - 2, ib[:, 1].min(), ib[:, 0].max() + 2, ib[:, 1].max() + 1), 13, "in")
    print(f"india: {len(allin)} named peaks at z13 {time.time() - t0:.0f}s", flush=True)
    res["in"] = _rank(_inside(allin, U["in"][1]), 60, 8, cand=300)
    for key, (country, rings, *_rest) in U.items():
        if country == "in" and key != "in":
            res[key] = _rank(_inside(allin, rings), 25, 8)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "peaks.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")))
    for k in ("us", "in"):
        print(k, res[k][:5])
    return res


def _packed(r):
    """Raw cache row (name, len_km, source, mouth, paths) -> the build's packed keys."""
    return {"n": r.get("name"), "L": r.get("len_km"), "s": r.get("source"), "se": None,
            "m": r.get("mouth"), "me": None, "p": r.get("paths") or []}


def stage_rivers():
    """Run fill_rivers over every cached river (results thrown away) so the DEM tiles are downloaded and
    every sampled height sits in the local memo (data/cache/terrain_points.json): the site build then
    fills rivers in seconds instead of reading thousands of tiles over the network share."""
    cache = C.DATA / "cache"
    rows = []
    for f in sorted((cache / "rivers_osm").glob("*.json")):
        rows += json.load(open(f)).get("rivers", [])
    nat = cache / "rivers_national.json"
    if nat.exists():
        rows += json.load(open(nat)).get("rivers", [])
    ind = cache / "india" / "rivers.json"
    if ind.exists():
        rows += json.load(open(ind))
    t0 = time.time()
    fill_rivers([_packed(r) for r in rows])
    print(f"rivers: {len(rows)} prefetched {time.time() - t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", choices=["tiles", "relief", "peaks", "rivers", "all"], default="all")
    ap.add_argument("--only", nargs="*", help="relief: only these keys")
    a = ap.parse_args()
    print("DEM tiles in", TILES)
    if a.stage in ("tiles", "all"):
        stage_tiles()
    if a.stage in ("relief", "all"):
        stage_relief(a.only)
    if a.stage in ("peaks", "all"):
        stage_peaks()
    if a.stage in ("rivers", "all"):
        stage_rivers()


if __name__ == "__main__":
    main()
