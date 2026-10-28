"""Ocean, bays and lakes for the Explore map, from the OpenStreetMap maps NOMAD keeps on the mini.

One file per map view, matching the terrain views: "us" for the country and regions (zoom 5) and one per
subregion (HUC4) that has a terrain image (zoom 8, over the subregion and a margin around it, so rivers
can be followed out to the bay or the sea). Polygons are clipped to each tile and simplified; names of
bays, seas and large lakes come from the map's label points.

Writes docs/data/water/<key>.json: {"poly": [[ring, ...], ...], "names": [[name, lon, lat, kind], ...]}.
Usage: python -m iwla_river.water
"""

from __future__ import annotations

import gzip
import json

import mapbox_vector_tile as mvt

from . import config as C
from .rivers_osm import Maps, num2deg, simplify, tile_lat, tiles_over

OUT = C.ROOT / "docs" / "data" / "water"
POLY_KINDS = {"ocean", "water", "lake", "reservoir", "bay", "river", "riverbank"}
NAME_KINDS = {"ocean", "sea", "bay", "strait", "lake", "reservoir", "water", "sound", "gulf"}


def view(maps, bbox, z, tol, min_area):
    polys, names = [], {}
    for (_, x, y) in sorted(tiles_over(bbox, z)):
        lon0, lat1 = num2deg(x, y, z)
        lon1, _ = num2deg(x + 1, y + 1, z)
        for _, r, _ in maps.files:
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
            conv = lambda p: (round(lon0 + min(max(p[0], 0), ext) / ext * (lon1 - lon0), 4), round(tile_lat(y + min(max(p[1], 0), ext) / ext, z), 4))
            for ft in layer["features"]:
                pr, g = ft["properties"], ft["geometry"]
                kind = pr.get("kind")
                if g["type"] == "Point" and (pr.get("name:en") or pr.get("name")) and kind in NAME_KINDS:
                    pr["name"] = pr.get("name:en") or pr["name"]
                    lo, la = conv(g["coordinates"])
                    names.setdefault(pr["name"], [pr["name"], lo, la, kind])
                if "Polygon" not in g["type"] or kind not in POLY_KINDS:
                    continue
                for poly in [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]:
                    rings = []
                    for ring in poly:
                        pts = simplify([conv(p) for p in ring], tol)
                        if len(pts) >= 4:
                            rings.append([list(p) for p in pts])
                    if rings and area(rings[0]) >= min_area:
                        polys.append(rings)
            break
    return polys, list(names.values())


def area(ring):
    return abs(sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1))) / 2


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    maps = Maps()
    keys = json.loads((C.ROOT / "docs" / "data" / "terrain" / "index.json").read_text())
    w4 = json.loads((C.DATA / "cache" / "wbd_4.json").read_text())
    jobs = {"us": ((-126, 23.5, -65.5, 50), 5, 0.02, 0.01)}
    for key, meta in keys.items():
        if meta.get("country") == "us" and key in w4:
            xs = [p[0] for r in w4[key] for p in r]
            ys = [p[1] for r in w4[key] for p in r]
            mx, my = (max(xs) - min(xs)) * 0.35, (max(ys) - min(ys)) * 0.35
            jobs[key] = ((min(xs) - mx, min(ys) - my, max(xs) + mx, max(ys) + my), 8, 0.003, 0.0005)
    for key, (bbox, z, tol, min_area) in jobs.items():
        polys, names = view(maps, bbox, z, tol, min_area)
        (OUT / f"{key}.json").write_text(json.dumps({"poly": polys, "names": names}, separators=(",", ":")))
        print(key, len(polys), "water areas", len(names), "names", flush=True)


if __name__ == "__main__":
    run()
