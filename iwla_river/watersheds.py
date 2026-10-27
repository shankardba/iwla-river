"""Metrics for every watershed level (USGS hydrologic units) and every state, for Explore.

Hydrologic unit codes nest: 2 digits = region, 4 = subregion, 6 = basin, 8 = subbasin, 10 = watershed,
12 = subwatershed. Every site with a usable survey has a HUC12 (from enrich --stage huc); a watershed's
metrics pool all sites whose code starts with its own. States are a second way to group the same sites:
each site is placed in its state by a point-in-polygon test (the Hub's own state field is often blank).

Adds tables watershed_metrics, state_metrics, site_state and state_subbasins.
Usage: python -m iwla_river.watersheds
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from . import config as C
from .analysis import MIN_PAIRS, seasonal_kendall
from .enrich import _inside

LEVELS = (2, 4, 6, 8, 10, 12)
STATES = Path(__file__).resolve().parent / "web" / "geo" / "states.json"


def aggregate(sites: pd.DataFrame, exp: pd.DataFrame, chem: pd.DataFrame) -> pd.DataFrame:
    """Metrics per group. Each frame carries a 'code' column naming the group of every row."""
    g = sites.groupby("code")
    base = pd.DataFrame({
        "sites": g.size(), "bio_sites": g.bio.apply(lambda s: int((s > 0).sum())), "bio_surveys": g.bio.sum(),
        "chem_readings": g.chem.sum(), "first_year": g.first_bio.min(), "last_year": g.last_bio.max(),
        "lat": g.lat.mean(), "lon": g.lon.mean(),
        "imperv": g.ws_impervious_pct.mean(), "forest": g.ws_forest_pct.mean()}).reset_index()
    if len(exp):
        ss = exp[exp.target == "sensitive_share"]
        m = ss.groupby("code").agg(sens_obs=("observed", "mean"), sens_exp=("expected", "mean"), gap=("resid", "mean")).reset_index()
        sp = exp[exp.target == "score_pct"].groupby("code")["observed"].mean().rename("score_pct").reset_index()
        trend = []
        for code, grp in ss.groupby("code"):
            if len(grp) < C.TREND_MIN_SURVEYS or grp.year.max() - grp.year.min() < C.TREND_MIN_YEARS:
                continue
            sy = grp.groupby(["season", "year"], as_index=False).resid.median()
            r = seasonal_kendall(sy.year.to_numpy(float), sy.resid.to_numpy(float), sy.season.to_numpy())
            if r["pairs"] < MIN_PAIRS:
                continue
            verdict = "no clear trend" if r["p"] >= 0.1 else "improving" if r["S"] > 0 else "declining"
            trend.append({"code": code, "gap_p": r["p"], "gap_slope": 10 * r["slope_per_year"], "gap_verdict": verdict})
        base = base.merge(m, on="code", how="left").merge(sp, on="code", how="left")
        base = base.merge(pd.DataFrame(trend, columns=["code", "gap_p", "gap_slope", "gap_verdict"]), on="code", how="left")
    cl = chem[chem.parameter == "chloride"].groupby("code").value.agg(cl_median="median", cl_p90=lambda v: v.quantile(0.9), cl_n="size").reset_index()
    no3 = chem[chem.parameter != "chloride"].groupby("code").value.agg(no3_median="median", no3_n="size").reset_index()
    return base.merge(cl, on="code", how="left").merge(no3, on="code", how="left")


def place_in_states(sites: pd.DataFrame) -> pd.Series:
    """State (USPS code) for each site by point-in-polygon, or '' when outside the lower 48."""
    states = json.loads(STATES.read_text())["states"]
    boxes = []
    for abbr, s in states.items():
        xs = [p[0] for r in s["r"] for p in r]
        ys = [p[1] for r in s["r"] for p in r]
        boxes.append((abbr, min(xs), max(xs), min(ys), max(ys), s["r"]))
    out = []
    for la, lo in zip(sites.lat, sites.lon):
        hit = ""
        if la == la and lo == lo:
            for abbr, x0, x1, y0, y1, rings in boxes:
                if x0 <= lo <= x1 and y0 <= la <= y1 and _inside(lo, la, rings):
                    hit = abbr
                    break
        out.append(hit)
    return pd.Series(out, index=sites.index)


def run(db_path=C.DB_PATH) -> int:
    con = duckdb.connect(str(db_path))
    has = lambda t: con.execute(f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{t}'").fetchall()[0][0]
    if not has("site_huc"):
        print("no site_huc table yet: run python -m iwla_river.enrich --stage huc")
        return 0
    sites = con.execute("""
        SELECT u.site_id, any_value(u.lat) AS lat, any_value(u.lon) AS lon, h.huc12,
               count(*) FILTER (WHERE u.protocol IN ('sos_bio', 'va_rocky', 'va_muddy')) AS bio,
               count(*) FILTER (WHERE u.protocol NOT IN ('sos_bio', 'va_rocky', 'va_muddy')) AS chem,
               min(year(u.survey_date)) FILTER (WHERE u.protocol IN ('sos_bio', 'va_rocky', 'va_muddy')) AS first_bio,
               max(year(u.survey_date)) FILTER (WHERE u.protocol IN ('sos_bio', 'va_rocky', 'va_muddy')) AS last_bio
        FROM usable_surveys u JOIN site_huc h USING (site_id) GROUP BY u.site_id, h.huc12""").df()
    ctx = con.execute("SELECT site_id, ws_impervious_pct, ws_forest_pct FROM site_context").df() if has("site_context") \
        else pd.DataFrame(columns=["site_id", "ws_impervious_pct", "ws_forest_pct"])
    sites = sites.merge(ctx, on="site_id", how="left")
    exp = con.execute("""SELECT e.site_id, e.target, e.observed, e.expected, e.resid, e.year, e.season, h.huc12
                         FROM expected e JOIN site_huc h USING (site_id)""").df() if has("expected") else pd.DataFrame(
        columns=["site_id", "target", "observed", "expected", "resid", "year", "season", "huc12"])
    chem = con.execute("""SELECT u.site_id, c.parameter, c.value, h.huc12 FROM chemistry c JOIN usable_surveys u USING (survey_uid)
                          JOIN site_huc h USING (site_id) WHERE c.parameter IN ('chloride', 'nitrate', 'nitrate_n')""").df()
    names = dict(con.execute("SELECT huc, name FROM huc_names").fetchall()) if has("huc_names") else {}

    # Watersheds: every level of the hydrologic unit code.
    out = []
    for d in LEVELS:
        m = aggregate(sites.assign(code=sites.huc12.str[:d]), exp.assign(code=exp.huc12.str[:d]), chem.assign(code=chem.huc12.str[:d]))
        m["digits"] = d
        m["parent"] = m.code.str[:d - 2] if d > 2 else ""
        m["name"] = m.code.map(lambda c: names.get(c, ""))
        out.append(m)
    ws = pd.concat(out, ignore_index=True)

    # States: the same measures, with each site placed in its state.
    sites["state"] = place_in_states(sites)
    st_of = dict(zip(sites.site_id, sites.state))
    s_sites = sites[sites.state != ""]
    st = aggregate(s_sites.assign(code=s_sites.state), exp.assign(code=exp.site_id.map(st_of)).dropna(subset=["code"]),
                   chem.assign(code=chem.site_id.map(st_of)).dropna(subset=["code"]))
    st = st[st.code != ""]
    st["name"] = st.code.map({k: v["n"] for k, v in json.loads(STATES.read_text())["states"].items()})
    # Subbasins (HUC8) with sites in each state, for moving from a state into its watersheds.
    sub = (s_sites.assign(huc8=s_sites.huc12.str[:8]).groupby(["state", "huc8"])
           .agg(sites=("site_id", "size"), bio_surveys=("bio", "sum")).reset_index())

    for name, df in {"watershed_metrics": ws, "state_metrics": st, "site_state": sites[["site_id", "state"]],
                     "state_subbasins": sub}.items():
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.register("df", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
        con.unregister("df")
    con.close()
    print({"watersheds": len(ws), **{f"huc{d}": int((ws.digits == d).sum()) for d in LEVELS},
           "states": len(st), "sites placed in states": int((sites.state != "").sum())})
    return len(ws)


if __name__ == "__main__":
    run()
