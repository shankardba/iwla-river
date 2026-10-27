"""Phase 3 inputs: watershed land cover and rainfall for every biological survey.

Stages (each cached in data/cache/, so a rerun only fetches what is new):
  comid      USGS NLDI: the NHDPlus stream segment (COMID) each site sits on
  streamcat  EPA StreamCat: land cover, soils, climate and roads for the watershed above each segment
  rain       Open-Meteo archive: daily rainfall and air temperature for the 7 days up to each survey

Writes tables site_context and survey_weather into data/river.duckdb.

Usage: python -m iwla_river.enrich [--stage comid,streamcat,rain]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import duckdb
import pandas as pd
import requests

from . import config as C

CACHE = C.DATA / "cache"
NLDI = "https://api.water.usgs.gov/nldi/linked-data/comid/position"
STREAMCAT = "https://api.epa.gov/StreamCat/streams/metrics"
METEO = "https://archive-api.open-meteo.com/v1/archive"
WBD = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer"
HUC_LAYERS = {2: 1, 4: 2, 6: 3, 8: 4, 10: 5, 12: 6}  # digits -> WBD map layer
UA = {"User-Agent": "iwla-river research (read-only)"}

# Watershed metrics (NLCD 2019 land cover, soils, 1981-2010 climate, road crossings, population).
SC_METRICS = [
    "pcturbhi2019", "pcturbmd2019", "pcturblo2019", "pcturbop2019", "pctimp2019",
    "pctdecid2019", "pctconif2019", "pctmxfst2019", "pctcrop2019", "pcthay2019", "pctwdwet2019",
    "elev", "rdcrs", "precip8110", "tmean8110", "clay", "sand", "popden2010",
]
METEO_PER_HOUR = 4500  # stay under Open-Meteo's free limit of 5,000 calls an hour


def _load(name: str) -> dict:
    p = CACHE / name
    return json.loads(p.read_text()) if p.exists() else {}


def _save(name: str, data: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = CACHE / (name + ".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(CACHE / name)


def bio_sites(con) -> pd.DataFrame:
    return con.execute("""
        SELECT DISTINCT site_id, lat, lon FROM features WHERE lat IS NOT NULL AND lon IS NOT NULL""").df()


def stage_comid(sites: pd.DataFrame) -> None:
    cache = _load("comid.json")
    todo = [r for r in sites.itertuples() if str(r.site_id) not in cache]
    print(f"comid: {len(todo)} sites to look up ({len(cache)} cached)")
    with requests.Session() as s:
        s.headers.update(UA)
        for i, r in enumerate(todo, 1):
            try:
                resp = s.get(NLDI, params={"coords": f"POINT({r.lon} {r.lat})"}, timeout=60)
                feats = resp.json().get("features", []) if resp.ok else []
                cache[str(r.site_id)] = feats[0]["properties"]["comid"] if feats else None
            except (requests.RequestException, ValueError, KeyError):
                continue  # left uncached, retried next run
            if i % 50 == 0:
                _save("comid.json", cache)
                print(f"  comid {i}/{len(todo)}", flush=True)
            time.sleep(0.2)
    _save("comid.json", cache)


def stage_streamcat() -> None:
    comids = sorted({c for c in _load("comid.json").values() if c})
    cache = _load("streamcat.json")
    todo = [c for c in comids if str(c) not in cache]
    print(f"streamcat: {len(todo)} segments to fetch ({len(cache)} cached)")
    with requests.Session() as s:
        s.headers.update(UA)
        for i in range(0, len(todo), 100):
            batch = todo[i:i + 100]
            params = {"name": ",".join(SC_METRICS), "aoi": "ws", "comid": ",".join(map(str, batch))}
            resp = s.get(STREAMCAT, params=params, timeout=180)
            resp.raise_for_status()
            for item in resp.json().get("items", []):
                cache[str(item.pop("comid"))] = item
            for c in batch:  # segments StreamCat has no data for
                cache.setdefault(str(c), {})
            _save("streamcat.json", cache)
            print(f"  streamcat {min(i + 100, len(todo))}/{len(todo)}", flush=True)
            time.sleep(1)


def rain_key(lat, lon, date) -> str:
    """Surveys on the same ~10 km grid cell and day share one weather request."""
    return f"{round(lat, 1)}|{round(lon, 1)}|{str(date)[:10]}"


def stage_rain(rows, workers: int = 4) -> None:
    keys = {rain_key(la, lo, d) for la, lo, d in rows}
    cache = _load("rain.json")
    todo = sorted(k for k in keys if k not in cache)
    print(f"rain: {len(todo)} grid-cell days to fetch ({len(cache)} cached)", flush=True)
    gap = 3600 / METEO_PER_HOUR  # seconds between request starts, across all workers
    lock = threading.Lock()
    next_slot = [time.monotonic()]

    def wait_turn():
        with lock:
            now = time.monotonic()
            slot = max(now, next_slot[0])
            next_slot[0] = slot + gap
        time.sleep(max(0.0, slot - now))

    def fetch(k):
        la, lo, d = k.split("|")
        end = dt.date.fromisoformat(d)
        params = {"latitude": la, "longitude": lo, "start_date": (end - dt.timedelta(days=6)).isoformat(),
                  "end_date": d, "daily": "precipitation_sum,temperature_2m_max", "timezone": "auto"}
        for attempt in range(5):
            wait_turn()
            try:
                resp = requests.get(METEO, params=params, timeout=60, headers=UA)
            except requests.RequestException:
                continue
            if resp.status_code == 429:  # limit reached: back off, then retry
                time.sleep(60 * (attempt + 1))
                continue
            if resp.ok:
                daily = resp.json().get("daily", {})
                return k, {"rain": daily.get("precipitation_sum"), "tmax": daily.get("temperature_2m_max")}
            return k, None
        return k, None

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for k, val in pool.map(fetch, todo):
            if val is not None:
                cache[k] = val
            done += 1
            if done % 200 == 0:
                _save("rain.json", cache)
                print(f"  rain {done}/{len(todo)} at {dt.datetime.now():%H:%M}", flush=True)
    _save("rain.json", cache)


def _inside(x, y, rings) -> bool:
    """Even-odd ray test against all rings of an ESRI polygon (holes handled by the parity)."""
    hit = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / ((y2 - y1) or 1e-12):
                hit = not hit
    return hit


def stage_huc(points, workers: int = 3) -> None:
    """USGS Watershed Boundary Dataset: the 12-digit hydrologic unit (HUC12) each site sits in.

    One request per 1-degree square that holds sites fetches every HUC12 boundary there (simplified);
    each site is then placed by a point-in-polygon test. Sites left over get a single-point lookup.
    """
    cache = _load("huc.json")
    todo = [(sid, la, lo) for sid, la, lo in points if str(sid) not in cache]
    cells = {}
    for sid, la, lo in todo:
        cells.setdefault((math.floor(la), math.floor(lo)), []).append((sid, la, lo))
    print(f"huc: {len(todo)} sites in {len(cells)} one-degree squares ({len(cache)} cached)", flush=True)

    def get(url, params, tries=5):
        for attempt in range(tries):
            try:
                r = requests.get(url, params=params, timeout=120, headers=UA)
                if r.ok:
                    return r.json()
            except (requests.RequestException, ValueError):
                pass
            time.sleep(4 * (attempt + 1))
        return None

    def fetch_cell(item):
        (la, lo), pts_ = item
        data = get(f"{WBD}/6/query", {"geometry": f"{lo},{la},{lo + 1},{la + 1}", "geometryType": "esriGeometryEnvelope",
                                      "inSR": 4326, "outSR": 4326, "spatialRel": "esriSpatialRelIntersects",
                                      "outFields": "huc12", "returnGeometry": "true", "maxAllowableOffset": 0.0008, "f": "json"})
        found = {}
        if data is None:
            return found, pts_
        polys = []
        for f in data.get("features", []):
            rings = f.get("geometry", {}).get("rings") or []
            xs = [p[0] for r in rings for p in r]
            ys = [p[1] for r in rings for p in r]
            if xs:
                polys.append((f["attributes"]["huc12"], min(xs), max(xs), min(ys), max(ys), rings))
        left = []
        for sid, y, x in pts_:
            code = next((c for c, x0, x1, y0, y1, rings in polys if x0 <= x <= x1 and y0 <= y <= y1 and _inside(x, y, rings)), None)
            if code:
                found[str(sid)] = code
            else:
                left.append((sid, y, x))
        return found, left

    leftovers, done = [], 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for found, left in pool.map(fetch_cell, sorted(cells.items())):
            cache.update(found)
            leftovers += left
            done += 1
            if done % 25 == 0:
                _save("huc.json", cache)
                print(f"  huc squares {done}/{len(cells)}, {len(cache)} sites placed at {dt.datetime.now():%H:%M}", flush=True)
    _save("huc.json", cache)
    print(f"huc: {len(leftovers)} sites need a single-point lookup", flush=True)
    for i, (sid, la, lo) in enumerate(leftovers, 1):
        data = get(f"{WBD}/6/query", {"geometry": f"{lo},{la}", "geometryType": "esriGeometryPoint", "inSR": 4326,
                                      "spatialRel": "esriSpatialRelIntersects", "outFields": "huc12", "returnGeometry": "false", "f": "json"}, 3)
        if data is not None:
            feats = data.get("features", [])
            cache[str(sid)] = feats[0]["attributes"]["huc12"] if feats else ""
        if i % 100 == 0:
            _save("huc.json", cache)
    _save("huc.json", cache)

    # Names for every level of each unit found.
    names = _load("huc_names.json")
    codes = {k: v for k, v in cache.items() if v}
    with requests.Session() as s:
        s.headers.update(UA)
        for digits, layer in HUC_LAYERS.items():
            want = sorted({c[:digits] for c in codes.values()} - set(names))
            for i in range(0, len(want), 80):
                chunk = want[i:i + 80]
                where = f"huc{digits} IN ({','.join(repr(c) for c in chunk)})"
                for attempt in range(4):  # this service takes GET only, and is sometimes slow
                    try:
                        r = s.get(f"{WBD}/{layer}/query", params={"where": where, "outFields": f"huc{digits},name",
                                                                  "returnGeometry": "false", "f": "json"}, timeout=120)
                        feats = r.json().get("features", [])
                        break
                    except (requests.RequestException, ValueError):
                        feats = []
                        time.sleep(5 * (attempt + 1))
                for f in feats:
                    a = f["attributes"]
                    names[a[f"huc{digits}"]] = a["name"]
            _save("huc_names.json", names)
            print(f"  names: level {digits}, {len(want)} looked up", flush=True)


# Simplification per level (degrees): coarse for regions, fine for small subwatersheds.
WBD_OFFSET = {2: 0.03, 4: 0.012, 6: 0.006, 8: 0.003, 10: 0.0015, 12: 0.0008}
WBD_CHUNK = {2: 4, 4: 20, 6: 30, 8: 40, 10: 60, 12: 80}


def stage_wbdgeo(codes_by_level: dict) -> None:
    """Simplified boundary of every watershed that has samples, from the USGS Watershed Boundary Dataset."""
    for digits, layer in HUC_LAYERS.items():
        name = f"wbd_{digits}.json"
        cache = _load(name)
        todo = sorted(set(codes_by_level.get(digits, [])) - set(cache))
        print(f"wbd geo level {digits}: {len(todo)} to fetch ({len(cache)} cached)", flush=True)
        for i in range(0, len(todo), WBD_CHUNK[digits]):
            chunk = todo[i:i + WBD_CHUNK[digits]]
            params = {"where": f"huc{digits} IN ({','.join(repr(c) for c in chunk)})", "outFields": f"huc{digits}",
                      "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": WBD_OFFSET[digits],
                      "geometryPrecision": 4, "f": "json"}
            for attempt in range(4):
                try:
                    r = requests.get(f"{WBD}/{layer}/query", params=params, timeout=180, headers=UA)
                    feats = r.json().get("features")
                    if feats is not None:
                        break
                except (requests.RequestException, ValueError):
                    pass
                time.sleep(5 * (attempt + 1))
            else:
                continue
            for f in feats:
                cache[f["attributes"][f"huc{digits}"]] = f["geometry"]["rings"]
            _save(name, cache)
        print(f"  level {digits}: {len(cache)} boundaries", flush=True)


def write_huc(con) -> None:
    huc = _load("huc.json")
    names = _load("huc_names.json")
    rows = [{"site_id": int(k), "huc12": v, **{f"huc{d}": v[:d] for d in (2, 4, 6, 8, 10)}} for k, v in huc.items() if v]
    nm = [{"huc": k, "digits": len(k), "name": v} for k, v in names.items()]
    for name, df in {"site_huc": pd.DataFrame(rows), "huc_names": pd.DataFrame(nm)}.items():
        if df.empty:
            continue
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.register("df", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
        con.unregister("df")
    print({"site_huc": len(rows), "huc_names": len(nm)})


def write_tables(con) -> None:
    comid = _load("comid.json")
    sc = _load("streamcat.json")
    site_rows = []
    for site_id, c in comid.items():
        m = sc.get(str(c), {}) if c else {}
        forest = sum(m.get(f"pct{k}2019ws") or 0 for k in ("decid", "conif", "mxfst")) if m else None
        urban = sum(m.get(f"pcturb{k}2019ws") or 0 for k in ("hi", "md", "lo", "op")) if m else None
        site_rows.append({
            "site_id": int(site_id), "comid": c,
            "ws_impervious_pct": m.get("pctimp2019ws"), "ws_urban_pct": urban, "ws_forest_pct": forest,
            "ws_crop_pct": m.get("pctcrop2019ws"), "ws_hay_pct": m.get("pcthay2019ws"),
            "ws_wetland_pct": m.get("pctwdwet2019ws"), "ws_elev_m": m.get("elevws"),
            "ws_road_crossings": m.get("rdcrsws"), "ws_precip_mm": m.get("precip8110ws"),
            "ws_mean_temp_c": m.get("tmean8110ws"), "ws_clay_pct": m.get("clayws"),
            "ws_sand_pct": m.get("sandws"), "ws_pop_density": m.get("popden2010ws"),
        })
    site_ctx = pd.DataFrame(site_rows)

    rain = _load("rain.json")
    surveys = con.execute("SELECT survey_uid, lat, lon, survey_date FROM features WHERE lat IS NOT NULL").df()
    wx = []
    for r in surveys.itertuples():
        w = rain.get(rain_key(r.lat, r.lon, r.survey_date))
        if not w or not w.get("rain"):
            continue
        p = [v if v is not None else 0.0 for v in w["rain"]]
        tm = [v for v in (w.get("tmax") or []) if v is not None]
        wx.append({"survey_uid": r.survey_uid, "rain_1d_mm": sum(p[-2:]), "rain_3d_mm": sum(p[-3:]),
                   "rain_7d_mm": sum(p), "air_tmax_7d_c": sum(tm) / len(tm) if tm else None})
    weather = pd.DataFrame(wx, columns=["survey_uid", "rain_1d_mm", "rain_3d_mm", "rain_7d_mm", "air_tmax_7d_c"])

    for name, df in {"site_context": site_ctx, "survey_weather": weather}.items():
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.register("df", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
        con.unregister("df")
    print({"site_context": len(site_ctx), "with_landcover": int(site_ctx.ws_impervious_pct.notna().sum()) if len(site_ctx) else 0,
           "survey_weather": len(weather), "surveys": len(surveys)})


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", default="comid,streamcat,rain,huc")
    args = ap.parse_args(argv)
    stages = args.stage.split(",")
    # Read what the fetches need, then close: fetching can take an hour and must not lock the database.
    with duckdb.connect(str(C.DB_PATH), read_only=True) as con:
        sites = bio_sites(con)
        rows = con.execute("""SELECT DISTINCT lat, lon, survey_date FROM features
                              WHERE lat IS NOT NULL AND survey_date >= DATE '1950-01-01'""").fetchall()
        points = con.execute("""SELECT DISTINCT site_id, lat, lon FROM usable_surveys
                                WHERE lat IS NOT NULL AND lon IS NOT NULL""").fetchall()
    if "comid" in stages:
        stage_comid(sites)
    if "streamcat" in stages:
        stage_streamcat()
    if "rain" in stages:
        stage_rain(rows)
    if "huc" in stages:
        stage_huc(points)
    if "wbdgeo" in stages:
        with duckdb.connect(str(C.DB_PATH), read_only=True) as con:
            rows = con.execute("SELECT digits, code FROM watershed_metrics").fetchall()
        by = {}
        for d, c in rows:
            by.setdefault(d, []).append(c)
        stage_wbdgeo(by)
        return
    for attempt in range(10):  # another step may hold the database for a moment
        try:
            with duckdb.connect(str(C.DB_PATH)) as con:
                if stages != ["huc"]:
                    write_tables(con)
                write_huc(con)
            break
        except duckdb.IOException:
            time.sleep(15)


if __name__ == "__main__":
    main()
