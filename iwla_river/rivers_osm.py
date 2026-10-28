"""Named rivers in each subbasin (HUC8), with where each one starts and where it ends, from OpenStreetMap.

Reads the Protomaps vector map files (OpenStreetMap data) that NOMAD keeps on the M4 mini, so no web
service is needed. For every subbasin with biological surveys it:
  1. reads the map tiles over the subbasin and keeps named lines in the water layer (rivers and creeks);
  2. joins each river's pieces across tile edges (OSM draws rivers in the direction they flow);
  3. follows a river past the subbasin edge, tile by tile, until it reaches its true source and mouth;
  4. asks Open-Meteo for the elevation of the source and mouth, notes what the river flows into and,
     when two named rivers meet at its source, which two;
  5. records how far it runs through each watershed and subwatershed (HUC10, HUC12).

Writes data/cache/rivers_osm/<huc8>.json (data/ is not committed). Public geography only.
Usage: python -m iwla_river.rivers_osm [--only 02070008] [--zoom 12]
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import duckdb
import mapbox_vector_tile as mvt
from pmtiles.reader import Reader

from . import config as C
from .enrich import _inside

MAPS = Path("/Volumes/OricoArray/Daemon/library/maps/pmtiles")
OUT = C.DATA / "cache" / "rivers_osm"
CACHE = C.DATA / "cache"
KINDS = {"river", "stream", "canal"}
GAP_M = 700           # gaps in the map up to this long are bridged
SNAP_M = 60            # pieces whose ends are this close are the same river
MAX_FOLLOW = 900       # tiles read while following one subbasin's rivers outside it


# ---------- tiles ----------
class Maps:
    """All state map files, read tile by tile. Tiles are the same in every file that holds them."""

    def __init__(self, folder=MAPS):
        self.files = []
        for p in sorted(folder.glob("*.pmtiles")):
            if p.name.startswith("world"):
                continue
            try:
                f = open(p, "rb")   # a download may rename or remove its file at any moment
            except OSError:
                continue
            src = lambda off, n, f=f: (f.seek(off), f.read(n))[1]
            r = Reader(src)
            try:
                h = r.header()      # a file still downloading has no header yet
            except Exception:
                continue
            self.files.append((p.stem, r, (h["min_lon_e7"] / 1e7, h["min_lat_e7"] / 1e7, h["max_lon_e7"] / 1e7, h["max_lat_e7"] / 1e7)))
        self.memo = {}

    def lines(self, z, x, y):
        """Named water lines in one tile as (kind, name, [(lon, lat), ...]), clipped to the tile itself."""
        key = (z, x, y)
        if key in self.memo:
            return self.memo[key]
        lon0, lat1 = num2deg(x, y, z)
        lon1, lat0 = num2deg(x + 1, y + 1, z)
        cx, cy = (lon0 + lon1) / 2, (lat0 + lat1) / 2
        out = []
        for _, r, (a, b, c, d) in self.files:
            if not (a - 0.5 <= cx <= c + 0.5 and b - 0.5 <= cy <= d + 0.5):
                continue
            try:
                data = r.get(z, x, y)
            except Exception:
                continue
            if not data:
                continue
            if data[:2] == b"\x1f\x8b":
                data = gzip.decompress(data)
            layer = mvt.decode(data, default_options={"y_coord_down": True}).get("water")
            if not layer:
                break
            ext = layer.get("extent", 4096)
            for ft in layer["features"]:
                pr, g = ft["properties"], ft["geometry"]
                if pr.get("kind") not in KINDS or not pr.get("name") or "LineString" not in g["type"]:
                    continue
                parts = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
                for part in parts:
                    for run in clip_run(part, ext):
                        pts = [(lon0 + px / ext * (lon1 - lon0), tile_lat(y + py / ext, z)) for px, py in run]
                        if len(pts) > 1:
                            out.append((pr["kind"], pr["name"], pts))
            break
        self.memo[key] = out
        return out


def deg2num(lat, lon, z):
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def num2deg(x, y, z):
    n = 2 ** z
    return x / n * 360 - 180, tile_lat(y, z)


def tile_lat(yf, z):
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yf / 2 ** z))))


def clip_run(part, ext):
    """Split a line into the runs that lie inside the tile (tiles carry a buffer we must drop)."""
    runs, cur = [], []
    inside = lambda p: -1 <= p[0] <= ext + 1 and -1 <= p[1] <= ext + 1
    for i, p in enumerate(part):
        if inside(p):
            if not cur and i > 0:
                cur.append(edge_point(part[i - 1], p, ext))
            cur.append(p)
        elif cur:
            cur.append(edge_point(p, cur[-1], ext))
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


def edge_point(outp, inp, ext):
    """Where the segment from an outside point to an inside point crosses the tile edge."""
    t = 1.0
    for k in (0, 1):
        if outp[k] < 0:
            t = min(t, (inp[k] - 0) / (inp[k] - outp[k]))
        elif outp[k] > ext:
            t = min(t, (ext - inp[k]) / (outp[k] - inp[k]))
    t = max(0.0, min(1.0, t))
    return (inp[0] + (outp[0] - inp[0]) * t, inp[1] + (outp[1] - inp[1]) * t)


# ---------- geometry ----------
def metres(a, b):
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * k, a[1] - b[1]) * 111_195


def length_km(pts):
    return sum(metres(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) / 1000


def simplify(pts, tol):
    """Douglas-Peucker in degrees."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = pts[i], pts[j]
        dx, dy = x2 - x1, y2 - y1
        L = dx * dx + dy * dy or 1e-18
        best, bk = -1, -1
        for k in range(i + 1, j):
            x, y = pts[k]
            t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / L))
            d = (x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2
            if d > best:
                best, bk = d, k
        if best > tol * tol:
            keep[bk] = True
            stack += [(i, bk), (bk, j)]
    return [p for p, k in zip(pts, keep) if k]


class Grid:
    """Point lookup by ~SNAP_M cells."""

    def __init__(self, cell=0.0008):
        self.cell, self.g = cell, defaultdict(list)

    def key(self, p):
        return int(p[0] // self.cell), int(p[1] // self.cell)

    def add(self, p, v):
        self.g[self.key(p)].append((p, v))

    def near(self, p, m=SNAP_M):
        kx, ky = self.key(p)
        return [v for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q, v in self.g.get((kx + dx, ky + dy), []) if metres(p, q) <= m]


# ---------- rivers ----------
def components(pieces):
    """Group same-name pieces into separate rivers (two creeks can share a name)."""
    by_name = defaultdict(list)
    for i, (kind, name, pts) in enumerate(pieces):
        by_name[name].append(i)
    out = []
    for name, idx in by_name.items():
        parent = {i: i for i in idx}

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        g = Grid()
        for i in idx:
            pts = pieces[i][2]
            for p in (pts[0], pts[-1]):
                for j in g.near(p):
                    parent[find(i)] = find(j)
            g.add(pts[0], i)
            g.add(pts[-1], i)
        # Bridge small gaps in the map: a piece that ends near where another starts is the same river.
        heads = Grid(0.005)
        for i in idx:
            heads.add(pieces[i][2][0], i)
        for i in idx:
            for j in heads.near(pieces[i][2][-1], GAP_M):
                parent[find(i)] = find(j)
        groups = defaultdict(list)
        for i in idx:
            groups[find(i)].append(i)
        out += [(name, ids) for ids in groups.values()]
    return out


def open_ends(pieces, ids):
    """Starts with nothing flowing in, and ends with nothing flowing out, within one river."""
    starts, ends = Grid(), Grid()
    for i in ids:
        starts.add(pieces[i][2][0], i)
        ends.add(pieces[i][2][-1], i)
    heads = [pieces[i][2][0] for i in ids if not ends.near(pieces[i][2][0])]
    tails = [pieces[i][2][-1] for i in ids if not starts.near(pieces[i][2][-1])]
    return heads, tails


def tiles_over(bbox, z):
    x0, y1 = deg2num(bbox[1], bbox[0], z)
    x1, y0 = deg2num(bbox[3], bbox[2], z)
    return {(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


def collect(maps, tiles):
    return [ln for t in sorted(tiles) for ln in maps.lines(*t)]


def elevations(points):
    """Elevation in metres from Open-Meteo (Copernicus 90 m DEM), 100 points a call."""
    out = []
    for i in range(0, len(points), 100):
        chunk = points[i:i + 100]
        url = ("https://api.open-meteo.com/v1/elevation?latitude=" + ",".join(f"{p[1]:.5f}" for p in chunk) +
               "&longitude=" + ",".join(f"{p[0]:.5f}" for p in chunk))
        for attempt in range(4):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    out += json.load(r)["elevation"]
                break
            except Exception:
                time.sleep(5 * (attempt + 1))
        else:
            out += [None] * len(chunk)
        time.sleep(0.3)
    return out


def subbasin(maps, huc8, rings, z, units):
    """Every named river in one subbasin."""
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    home = tiles_over(bbox, z)
    tiles = set(home)
    pieces = collect(maps, tiles)
    inside = lambda p: bbox[0] <= p[0] <= bbox[2] and bbox[1] <= p[1] <= bbox[3] and _inside(p[0], p[1], rings)
    # Rivers that touch the subbasin itself.
    names = {name for name, ids in components(pieces) for i in ids
             if any(inside(q) for q in pieces[i][2][:: max(1, len(pieces[i][2]) // 6)])}
    # Follow open ends that sit on the edge of what we have read, until each river is whole.
    read = 0
    for _ in range(60):
        frontier = set()
        for name, ids in components([p for p in pieces if p[1] in names] or [("", "", [(0, 0), (0, 0)])]):
            if name not in names:
                continue
            sub = [p for p in pieces if p[1] == name]
            heads, tails = open_ends(sub, [i for i in range(len(sub))])
            for p in heads + tails:
                tx, ty = deg2num(p[1], p[0], z)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        t = (z, tx + dx, ty + dy)
                        if t not in tiles:
                            frontier.add(t)
        if not frontier or read > MAX_FOLLOW:
            break
        read += len(frontier)
        tiles |= frontier
        pieces += collect(maps, frontier)
    pieces = [p for p in pieces if p[1] in names]
    rivers = []
    for name, ids in components(pieces):
        km_in = sum(length_km(pieces[i][2]) for i in ids if inside(pieces[i][2][len(pieces[i][2]) // 2]))
        if km_in < 0.5:
            continue
        heads, tails = open_ends(pieces, ids)
        total = sum(length_km(pieces[i][2]) for i in ids)
        # Through which watersheds and subwatersheds it runs.
        u = defaultdict(float)
        for i in ids:
            pts = pieces[i][2]
            for a, b in zip(pts, pts[1:]):
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                for code, rr, bx in units:
                    if bx[0] <= m[0] <= bx[2] and bx[1] <= m[1] <= bx[3] and _inside(m[0], m[1], rr):
                        u[code] += metres(a, b) / 1000
        paths = [simplify(pieces[i][2], 0.0004) for i in ids if inside(pieces[i][2][len(pieces[i][2]) // 2])]
        rivers.append({"name": name, "kind": max((pieces[i][0] for i in ids), key=lambda k: k == "river"),
                       "len_km": round(total, 1), "len_in_km": round(km_in, 1), "heads": heads, "tails": tails,
                       "u": {k: round(v, 2) for k, v in u.items() if v >= 0.2},
                       "paths": [[[round(x, 4), round(y, 4)] for x, y in p] for p in paths if len(p) > 1]})
    # Elevations of every open end; the source is the highest start, the mouth the lowest end.
    ends = [p for r in rivers for p in r["heads"] + r["tails"]]
    el = dict(zip(ends, elevations(ends)))
    all_pieces = collect(maps, tiles)
    joins = Grid(0.002)
    for kind, name, pts in all_pieces:
        if kind == "canal":
            continue
        for q in pts[:: max(1, len(pts) // 40)] + [pts[-1]]:
            joins.add(q, name)
    for r in rivers:
        hs = [h for h in r["heads"] if el.get(h) is not None] or r["heads"]
        ts = [t for t in r["tails"] if el.get(t) is not None] or r["tails"]
        src = max(hs, key=lambda p: el.get(p) or -1e9) if hs else None
        mouth = min(ts, key=lambda p: el.get(p) if el.get(p) is not None else 1e9) if ts else None
        r["source"] = [round(src[0], 5), round(src[1], 5)] if src else None
        r["source_elev_m"] = el.get(src) if src else None
        r["mouth"] = [round(mouth[0], 5), round(mouth[1], 5)] if mouth else None
        r["mouth_elev_m"] = el.get(mouth) if mouth else None
        r["source_in_unit"] = bool(src and inside(src))
        r["mouth_in_unit"] = bool(mouth and inside(mouth))
        others = lambda p, m: sorted({n for n in joins.near(p, m) if n != r["name"]})
        r["flows_into"] = (others(mouth, 150) or [None])[0] if mouth else None
        r["tidal"] = bool(r["mouth_elev_m"] is not None and r["mouth_elev_m"] <= 2)
        if r["tidal"]:
            r["flows_into"] = None
        r["formed_by"] = others(src, 250)[:2] if src else []
        del r["heads"], r["tails"]
    rivers.sort(key=lambda r: -r["len_in_km"])
    return {"huc8": huc8, "source": "OpenStreetMap via Protomaps (NOMAD), elevations Open-Meteo", "zoom": z,
            "tiles_read": len(tiles), "rivers": rivers}


def run(only=None, z=12):
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(C.DB_PATH), read_only=True)
    codes = [r[0] for r in con.execute("SELECT code FROM watershed_metrics WHERE digits = 8 AND bio_surveys > 0 ORDER BY code").fetchall()]
    con.close()
    if only:
        codes = [c for c in codes if c in only] or list(only)
    w8 = json.loads((CACHE / "wbd_8.json").read_text())
    units = []
    for lvl in (10, 12):
        for code, rr in json.loads((CACHE / f"wbd_{lvl}.json").read_text()).items():
            xs = [p[0] for r in rr for p in r]
            ys = [p[1] for r in rr for p in r]
            units.append((code, rr, (min(xs), min(ys), max(xs), max(ys))))
    maps = Maps()
    done = 0
    for code in codes:
        path = OUT / f"{code}.json"
        if path.exists() and not only:
            continue
        rings = w8.get(code)
        if not rings:
            print(code, "no outline")
            continue
        t0 = time.time()
        mine = [u for u in units if u[0].startswith(code)]
        res = subbasin(maps, code, rings, z, mine)
        if not res["rivers"]:
            print(code, "no rivers yet (its state map is not downloaded?)", flush=True)
            continue
        path.write_text(json.dumps(res, separators=(",", ":")))
        done += 1
        print(code, len(res["rivers"]), "rivers", res["tiles_read"], "tiles", f"{time.time() - t0:.0f}s", flush=True)
        maps.memo.clear()
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--zoom", type=int, default=12)
    a = ap.parse_args()
    run(a.only, a.zoom)
