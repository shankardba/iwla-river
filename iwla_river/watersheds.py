"""Metrics for every watershed level (USGS hydrologic units), for the watershed explorer.

Hydrologic unit codes nest: 2 digits = region, 4 = subregion, 6 = basin, 8 = subbasin, 10 = watershed,
12 = subwatershed. Every site with a usable survey has a HUC12 (from enrich --stage huc); a watershed's
metrics pool all sites whose code starts with its own.

Adds table watershed_metrics. Usage: python -m iwla_river.watersheds
"""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from . import config as C
from .analysis import MIN_PAIRS, seasonal_kendall

LEVELS = (2, 4, 6, 8, 10, 12)
BIO = ("sos_bio", "va_rocky", "va_muddy")


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
    ctx = con.execute("SELECT site_id, ws_impervious_pct, ws_forest_pct FROM site_context").df() if has("site_context") else pd.DataFrame(columns=["site_id", "ws_impervious_pct", "ws_forest_pct"])
    sites = sites.merge(ctx, on="site_id", how="left")
    exp = con.execute("""SELECT e.target, e.observed, e.expected, e.resid, e.year, e.season, h.huc12
                         FROM expected e JOIN site_huc h USING (site_id)""").df() if has("expected") else pd.DataFrame()
    chem = con.execute("""SELECT c.parameter, c.value, h.huc12 FROM chemistry c JOIN usable_surveys u USING (survey_uid)
                          JOIN site_huc h USING (site_id) WHERE c.parameter IN ('chloride', 'nitrate', 'nitrate_n')""").df()
    names = dict(con.execute("SELECT huc, name FROM huc_names").fetchall()) if has("huc_names") else {}

    out = []
    for d in LEVELS:
        sites["code"] = sites.huc12.str[:d]
        g = sites.groupby("code")
        base = pd.DataFrame({
            "sites": g.size(), "bio_sites": g.bio.apply(lambda s: int((s > 0).sum())), "bio_surveys": g.bio.sum(),
            "chem_readings": g.chem.sum(), "first_year": g.first_bio.min(), "last_year": g.last_bio.max(),
            "lat": g.lat.mean(), "lon": g.lon.mean(),
            "imperv": g.ws_impervious_pct.mean(), "forest": g.ws_forest_pct.mean()}).reset_index()
        if len(exp):
            e = exp.assign(code=exp.huc12.str[:d])
            ss = e[e.target == "sensitive_share"]
            m = ss.groupby("code").agg(sens_obs=("observed", "mean"), sens_exp=("expected", "mean"), gap=("resid", "mean")).reset_index()
            sp = e[e.target == "score_pct"].groupby("code")["observed"].mean().rename("score_pct").reset_index()
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
        ch = chem.assign(code=chem.huc12.str[:d])
        cl = ch[ch.parameter == "chloride"].groupby("code").value.agg(cl_median="median", cl_p90=lambda v: v.quantile(0.9), cl_n="size").reset_index()
        no3 = ch[ch.parameter != "chloride"].groupby("code").value.agg(no3_median="median", no3_n="size").reset_index()
        base = base.merge(cl, on="code", how="left").merge(no3, on="code", how="left")
        base["digits"] = d
        base["parent"] = base.code.str[:d - 2] if d > 2 else ""
        base["name"] = base.code.map(lambda c: names.get(c, ""))
        out.append(base)
    df = pd.concat(out, ignore_index=True)
    con.execute("DROP TABLE IF EXISTS watershed_metrics")
    con.register("df", df)
    con.execute("CREATE TABLE watershed_metrics AS SELECT * FROM df")
    con.close()
    print({"watersheds": len(df), **{f"huc{d}": int((df.digits == d).sum()) for d in LEVELS}})
    return len(df)


if __name__ == "__main__":
    run()
