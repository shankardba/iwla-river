"""Findings for every watershed: what the data show in the unit you pick on the Explore map.

For each USGS hydrologic unit (region HUC2 down to subwatershed HUC12) with enough data:
  - trend in pollution-sensitive animals and in the survey score, relative to each site's usual level
    (seasonal Kendall on season-year medians, Sen slope; Benjamini–Hochberg across units of the same level);
  - chloride: long-record sites rising vs falling (seasonal Kendall per site, Benjamini–Hochberg across all sites);
  - paved and roofed area 1985 vs 2025 (Annual NLCD, area-weighted over the unit's HUC12s);
  - state impairment listings, dischargers in significant noncompliance, and volunteer coverage (EPA ATTAINS, ECHO);
  - for regions down to subbasins with 40+ biological sites: what predicts the sensitive share there
    (LightGBM, five repeats of five folds grouped by site, TreeSHAP on held-out surveys).
Each result is written as a plain sentence with the keys of the sources it rests on (iwla_river/web/refs.py).

Inputs: data/river.duckdb (or RIVER_DB) and DataLab's streams dataset (DATALAB_STREAMS). Heavy enough to run on the
M4 mini:  python -m iwla_river.watershed_findings [--out DIR] [--only 02]
Output: <out>/<huc4>.json (and <huc2>.json for the region itself) = {code: {"items": [{"t": text, "s": status, "r": [ref keys]}], "n": surveys}}, plus
<out>/meta.json. Aggregates only: no site name or location is written.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from .analysis import seasonal_kendall

ROOT = Path(__file__).resolve().parent.parent
RIVER = Path(os.environ.get("RIVER_DB", ROOT / "data" / "river.duckdb"))
STREAMS = Path(os.environ.get("DATALAB_STREAMS", Path.home() / "datalab/datasets/streams/data.duckdb"))
OUT = Path(__file__).parent / "web" / "wsf"
LEVELS = (2, 4, 6, 8, 10, 12)
LEVEL_WORD = {2: "region", 4: "subregion", 6: "basin", 8: "subbasin", 10: "watershed", 12: "subwatershed"}
FEATURES = {"ws_impervious_pct": "paved and roofed area", "ws_urban_pct": "developed land", "ws_forest_pct": "forest",
            "ws_crop_pct": "cropland", "ws_hay_pct": "hay and pasture", "ws_wetland_pct": "wetland", "ws_elev_m": "elevation",
            "ws_road_crossings": "road crossings", "ws_precip_mm": "rainfall", "ws_mean_temp_c": "air temperature",
            "ws_clay_pct": "clay soil", "ws_sand_pct": "sandy soil", "ws_pop_density": "population density",
            "month": "time of year", "va_form": "survey form"}
TREND_REFS = ["cwh", "sos", "mann", "hirsch1982", "sen1968", "bh1995"]


def fmt(n):
    return f"{n:,.0f}"


def bh(p):
    p = np.asarray(p, float)
    n = len(p)
    if not n:
        return p
    o = np.argsort(p)
    q = np.empty(n)
    q[o] = np.minimum.accumulate((p[o] * n / np.arange(1, n + 1))[::-1])[::-1]
    return np.minimum(q, 1)


def qtxt(q):
    return "q < 0.001" if q < 0.001 else f"q = {q:.2g}" if q < 0.01 else f"q = {q:.3f}" if q < 0.1 else f"q = {q:.2f}"


# ---------- data ----------
def load():
    r = duckdb.connect(str(RIVER), read_only=True)
    f = r.sql("""SELECT f.survey_uid, f.site_id, f.protocol, f.year, f.month, f.sos_total, f.va_score,
                        f.groups_found, f.sensitive_found, h.huc12
                 FROM features f JOIN site_huc h USING (site_id) WHERE h.huc12 IS NOT NULL""").df()
    f["score"] = np.where(f.protocol == "sos_bio", f.sos_total, f.va_score)
    f["va_form"] = (f.protocol != "sos_bio").astype(int)
    f["share"] = np.where(f.groups_found > 0, f.sensitive_found / f.groups_found.where(f.groups_found > 0), np.nan)
    fam = np.where(f.va_form == 1, "va", "sos")
    f["z"] = f.groupby(fam).score.transform(lambda x: (x - x.mean()) / x.std())
    for col in ("z", "share"):
        f[col + "_c"] = f[col] - f.groupby("site_id")[col].transform("median")   # relative to the site's usual level
    f["season"] = (f.month - 1) // 3
    ctx = r.sql("SELECT * FROM site_context").df().drop(columns=["comid"])
    cl = r.sql("""SELECT s.site_id, s.survey_date::DATE AS date, c.value, h.huc12 FROM chemistry c
                  JOIN usable_surveys s USING (survey_uid) JOIN site_huc h ON h.site_id = s.site_id
                  WHERE c.parameter = 'chloride' AND c.value > 0 AND c.value <= 20000""").df()
    snap = r.sql("SELECT max(snapshot_date) FROM snapshot").fetchall()[0][0]
    s = duckdb.connect(str(STREAMS), read_only=True, config={"enable_external_access": False})
    g = s.sql("""SELECT g.huc12, g.area_sqkm, g.biota_impaired, g.salt_impaired, g.impaired_waters,
                        g.npdes_significant_noncompliance AS snc, g.need_score, g.unmonitored, g.iwla_bug_sites_active,
                        i.impervious_1985, i.impervious_2025
                 FROM monitoring_gaps g LEFT JOIN watershed_impervious i USING (huc12)""").df()
    return f, ctx, cl, g, snap


# ---------- tests ----------
def unit_trend(d, col):
    """Seasonal Kendall on season-year means of the site-relative value. Needs 8+ years, 3+ sites, 30+ surveys."""
    d = d[d[col].notna()]
    if len(d) < 30 or d.site_id.nunique() < 3 or d.year.nunique() < 8:
        return None
    m = d.groupby(["year", "season"])[col].mean().reset_index()
    k = seasonal_kendall((m.year + (m.season + 0.5) / 4).to_numpy(float), m[col].to_numpy(float), m.season.to_numpy())
    if not math.isfinite(k["slope_per_year"]):
        return None
    return {"p": k["p"], "slope": k["slope_per_year"], "first": int(d.year.min()), "last": int(d.year.max()),
            "surveys": int(len(d)), "sites": int(d.site_id.nunique())}


def chloride_sites(cl):
    rows = []
    for sid, g in cl.groupby("site_id"):
        yrs = g.date.dt.year
        if len(g) >= 8 and yrs.max() - yrs.min() >= 4:
            t = (yrs + (g.date.dt.day_of_year - 0.5) / 366).to_numpy(float)
            k = seasonal_kendall(t, np.log10(g.value.to_numpy(float)), ((g.date.dt.month - 1) // 3).to_numpy())
            rows.append((sid, g.huc12.iloc[0], k["p"], k["slope_per_year"]))
    d = pd.DataFrame(rows, columns=["site_id", "huc12", "p", "slope"])
    d["q"] = bh(d.p.fillna(1).to_numpy())
    d["dir"] = np.where(d.q < 0.05, np.sign(d.slope), 0)
    return d


def drivers_one(args):
    """LightGBM on the sensitive share for one unit. Five repeats of five folds grouped by site (no site is ever in both
    training and test), TreeSHAP on the held-out surveys; reports held-out R² and how often each top driver recurs."""
    code, d = args
    import lightgbm as lgb
    from sklearn.model_selection import GroupKFold
    cols = list(FEATURES)
    d = d.dropna(subset=["share"])
    X, y, groups = d[cols].to_numpy(float), d.share.to_numpy(float), d.site_id.to_numpy()
    r2s, imps, rhos = [], [], []
    for rep in range(5):
        pred, shap = np.full(len(y), np.nan), np.full((len(y), len(cols)), np.nan)
        for tr, te in GroupKFold(n_splits=5, shuffle=True, random_state=rep).split(X, y, groups):
            m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.04, num_leaves=15, min_child_samples=30, subsample=0.8,
                                  subsample_freq=1, colsample_bytree=0.8, n_jobs=1, verbose=-1, random_state=rep)
            m.fit(X[tr], y[tr])
            pred[te] = m.predict(X[te])
            shap[te] = m.predict(X[te], pred_contrib=True)[:, :-1]
        r2s.append(1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2))
        imps.append(np.mean(np.abs(shap), axis=0))
        rhos.append([pd.Series(X[:, j]).corr(pd.Series(shap[:, j]), method="spearman") for j in range(len(cols))])
    imp, rho = np.mean(imps, axis=0), np.nanmean(np.array(rhos, float), axis=0)
    tops = [set(np.argsort(i)[::-1][:3]) for i in imps]
    top = [(cols[j], float(imp[j]), float(rho[j]), sum(j in t for t in tops)) for j in np.argsort(imp)[::-1][:3]]
    return code, {"r2": float(np.mean(r2s)), "r2_range": [float(min(r2s)), float(max(r2s))], "top": top,
                  "surveys": int(len(y)), "sites": int(d.site_id.nunique())}


# ---------- sentences ----------
def items_for(code, f_u, cl_u, g_u, tr_share, tr_z, drv):
    it, word = [], LEVEL_WORD[len(code)]
    if tr_share:
        pp = 100 * tr_share["slope"] * 10
        base = (f"{fmt(tr_share['surveys'])} surveys at {fmt(tr_share['sites'])} sites, {tr_share['first']}–{tr_share['last']}; "
                f"{qtxt(tr_share['q'])}")
        z = tr_z or {}
        agree = ""
        if z.get("q") is not None and z["q"] < 0.05:
            zdir = "rising" if z["slope"] > 0 else "falling"
            if tr_share["q"] < 0.05:
                agree = (" The survey score moves the same way" if np.sign(z["slope"]) == np.sign(tr_share["slope"])
                         else " The survey score, though, is " + zdir) + f" ({qtxt(z['q'])})."
            else:
                agree = f" The overall survey score, though, is {zdir} ({qtxt(z['q'])})."
        if tr_share["q"] < 0.05:
            up = pp > 0
            it.append({"t": f"Pollution-sensitive animals are {'increasing' if up else 'declining'} in this {word}: "
                            f"{pp:+.1f} percentage points of the animal groups found per decade, relative to each site's usual "
                            f"level ({base}).{agree}", "s": "good" if up else "concern", "r": TREND_REFS})
        else:
            it.append({"t": f"No clear trend in pollution-sensitive animals in this {word} ({pp:+.1f} points per decade; {base}).{agree}",
                       "s": "steady", "r": TREND_REFS})
    if len(cl_u):
        up, dn = int((cl_u.dir > 0).sum()), int((cl_u.dir < 0).sum())
        n = len(cl_u)
        s = "concern" if up > dn and up >= 2 else "good" if dn > up else "info"
        how = f"seasonal Kendall per site, false discovery rate 5% across all {fmt(CL_TESTS)} sites tested"
        it.append({"t": (f"Chloride: none of the {n} site{'s' if n > 1 else ''} with long records here shows a clear rise or fall ({how})."
                         if up == dn == 0 else
                         f"Chloride: of {n} site{'s' if n > 1 else ''} with long records here, {up} {'is' if up == 1 else 'are'} rising and "
                         f"{dn} falling ({how})."),
                   "s": s, "r": ["cwh", "hirsch1982", "sen1968", "bh1995", "kaushal2018"]})
    if len(g_u) and len(code) == 12:
        x = g_u.iloc[0]
        if pd.notna(x.impervious_1985) and pd.notna(x.impervious_2025):
            it.append({"t": f"Paved and roofed area here went from {x.impervious_1985:.1f}% in 1985 to {x.impervious_2025:.1f}% in 2025.",
                       "s": "concern" if x.impervious_2025 - x.impervious_1985 >= 2 else "info", "r": ["annual-nlcd", "wbd", "walsh2005"]})
        listed = [w for w, v in (("aquatic life", x.biota_impaired), ("salt or chloride", x.salt_impaired)) if v]
        it.append({"t": (f"The state lists water here as impaired for {' and for '.join(listed)}." if listed else
                         "No water here is listed as impaired for aquatic life or salt." if x.impaired_waters == 0 else
                         "Water here is listed as impaired, but not for aquatic life or salt.")
                        + (" A discharge permit holder here is in significant noncompliance." if x.snc > 0 else ""),
                   "s": "concern" if x.biota_impaired else "info", "r": ["attains", "echo", "wbd"]})
        it.append({"t": "A volunteer bug site here has been surveyed since 2021." if not x.unmonitored else
                        f"No volunteer bug site here has been surveyed since 2021{'; it is a high-need subwatershed' if x.need_score >= 5 else ''}.",
                   "s": "concern" if x.unmonitored and x.need_score >= 5 else "info", "r": ["cwh", "wbd", "attains", "echo", "annual-nlcd", "usmin"]})
    elif len(g_u):
        a = g_u.dropna(subset=["impervious_1985", "impervious_2025"])
        n12 = len(g_u)
        scope = "" if len(code) >= 8 else " in the river basins where IWLA volunteers work"
        if len(a) and a.area_sqkm.sum() > 0:
            w = a.area_sqkm
            i85, i25 = np.average(a.impervious_1985, weights=w), np.average(a.impervious_2025, weights=w)
            it.append({"t": f"Paved and roofed area went from {i85:.1f}% in 1985 to {i25:.1f}% in 2025 across {fmt(len(a))} "
                            f"small watersheds{scope} (area-weighted).",
                       "s": "concern" if i25 - i85 >= 2 else "info", "r": ["annual-nlcd", "wbd", "walsh2005"]})
        bio, salt, snc = int(g_u.biota_impaired.sum()), int(g_u.salt_impaired.sum()), int((g_u.snc > 0).sum())
        it.append({"t": f"{fmt(bio)} of {fmt(n12)} small watersheds{scope} have water the state lists as impaired for aquatic life"
                        f"{f', {fmt(salt)} for salt or chloride' if salt else ''}; {fmt(snc)} {'has' if snc == 1 else 'have'} a "
                        f"discharge permit holder in significant noncompliance.",
                   "s": "concern" if bio and bio / n12 >= 0.2 else "info", "r": ["attains", "echo", "wbd"]})
        act, hi = int((~g_u.unmonitored).sum()), g_u[g_u.need_score >= 5]
        it.append({"t": f"{fmt(act)} of {fmt(n12)} small watersheds{scope} have a volunteer bug site surveyed since 2021"
                        + (f"; {fmt(int(hi.unmonitored.sum()))} of {fmt(len(hi))} high-need ones have none." if len(hi) else "."),
                   "s": "concern" if len(hi) and hi.unmonitored.mean() > 0.8 else "info", "r": ["cwh", "wbd", "attains", "echo", "annual-nlcd", "usmin"]})
    if drv:
        if drv["r2"] >= 0.1:
            parts = [f"{FEATURES[c]} ({'higher' if rho > 0.1 else 'lower' if rho < -0.1 else 'mixed'} share where it is higher"
                     f"{'' if k == 5 else f'; top three in {k} of 5 repeats'})"
                     if c not in ("month", "va_form") else FEATURES[c] for c, _, rho, k in drv["top"]]
            it.append({"t": f"What best predicts the sensitive share in this {word}: {', '.join(parts)}. The model explains "
                            f"{round(100 * drv['r2'])}% of the variation at sites it never saw (range {round(100 * drv['r2_range'][0])}–"
                            f"{round(100 * drv['r2_range'][1])}% over 5 repeats; {fmt(drv['surveys'])} surveys at "
                            f"{fmt(drv['sites'])} sites).",
                       "s": "info", "r": ["cwh", "streamcat", "nlcd2019", "lightgbm", "treeshap"]})
        else:
            it.append({"t": f"Watershed traits do not reliably predict the sensitive share in this {word} (held-out R² "
                            f"{drv['r2']:.2f}, {fmt(drv['sites'])} sites).", "s": "info", "r": ["cwh", "streamcat", "lightgbm"]})
    return it


CL_TESTS = 0


def main(argv=None):
    global CL_TESTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--only", help="a region code (HUC2) to run alone, for testing")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    f, ctx, cl, g, snap = load()
    if a.only:
        f, cl, g = f[f.huc12.str.startswith(a.only)], cl[cl.huc12.str.startswith(a.only)], g[g.huc12.str.startswith(a.only)]
    cls = chloride_sites(cl)
    CL_TESTS = len(cls)
    for L in LEVELS:
        f[f"u{L}"], cls[f"u{L}"], g[f"u{L}"] = f.huc12.str[:L], cls.huc12.str[:L], g.huc12.str[:L]
    # trends, with Benjamini–Hochberg across the units of each level
    trends = {}
    for col in ("share_c", "z_c"):
        for L in LEVELS:
            res = {u: t for u, d in f.groupby(f"u{L}") if (t := unit_trend(d, col))}
            q = bh([t["p"] for t in res.values()])
            for (u, t), qq in zip(res.items(), q):
                t["q"] = float(qq)
                trends[(col, u)] = t
    # drivers for regions down to subbasins with 40+ biological sites
    fm = f.merge(ctx, on="site_id", how="left")
    jobs = [(u, d) for L in (2, 4, 6, 8) for u, d in fm.groupby(f"u{L}") if d.site_id.nunique() >= 40 and d.share.notna().sum() >= 300]
    with ProcessPoolExecutor(a.workers) as ex:
        drivers = dict(ex.map(drivers_one, jobs))
    # sentences per unit, one file per region
    units = sorted(set().union(*[set(f[f"u{L}"]) | set(g[f"u{L}"]) for L in LEVELS]))
    out = {}
    for u in units:
        L = len(u)
        it = items_for(u, f[f[f"u{L}"] == u], cls[cls[f"u{L}"] == u], g[g[f"u{L}"] == u],
                       trends.get(("share_c", u)), trends.get(("z_c", u)), drivers.get(u))
        if it:
            out.setdefault(u if L < 4 else u[:4], {})[u] = {"items": it, "n": int((f[f"u{L}"] == u).sum())}   # one file per subregion
    a.out.mkdir(parents=True, exist_ok=True)
    for old in a.out.glob("*.json"):
        old.unlink()
    for key, d in out.items():
        (a.out / f"{key}.json").write_text(json.dumps(d, separators=(",", ":")))
    meta = {"generated": dt.date.today().isoformat(), "clean_water_hub_snapshot": snap,
            "streams_dataset": dt.datetime.fromtimestamp(STREAMS.stat().st_mtime).date().isoformat(),
            "units": sum(len(d) for d in out.values()), "trend_units": len(trends), "driver_units": len(drivers),
            "chloride_sites_tested": CL_TESTS,
            "significant": {col: int(sum(1 for (c, _), t in trends.items() if c == col and t["q"] < 0.05)) for col in ("share_c", "z_c")}}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
