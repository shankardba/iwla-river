"""Where stream chloride comes from, and how paving reaches the bugs. Four checks, volunteer chloride throughout.

  seasons   each site's winter (Dec-Mar, road-salt season) and summer (Jun-Sep, no road salt) median chloride: how high
            summer chloride stays, and which of the two tracks the site's bugs better (paving held equal)
  sources   site summer and winter chloride against paving and road density, then whether septic systems, wastewater
            plants, discharge permits, housing and population add anything once paving is held equal
  flow      the same site on low- vs high-water days (USGS gauge flow percentile on the sampling day), by season:
            a steady source is diluted at high water; a salt pulse rises with melt and runoff
  paving    paving -> chloride -> bugs: how much of paving's link to the bugs runs through chloride, and how much does not
            (runoff, heat, sediment, lost habitat), with a bootstrap over sites

Stream and river sites only (pipes, ponds, lakes and drinking-water samples left out). Zeros and readings over
20,000 mg/L dropped. Writes aggregates only, under "chloride_sources" in iwla_river/web/findings/context_results.json.

    DATALAB_STREAMS=<streams dataset> ~/datalab/.venv/bin/python -m iwla_river.chloride_sources
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

from .context import OUT, bh, pf, r3
from .salt_bugs import SEED, bugs, connect, pair

STREAMS_ONLY = ("small stream/creek", "river", "stream/creek")


def readings(r) -> pd.DataFrame:
    d = r.execute("""SELECT u.survey_uid, u.site_id, u.survey_date AS d, c.protocol, c.value AS cl, lower(st.water_source) AS src,
                            h.huc12, sc.flow_pct
        FROM chemistry c JOIN usable_surveys u USING (survey_uid) JOIN sites st ON st.site_id = u.site_id
        LEFT JOIN site_huc h ON h.site_id = u.site_id LEFT JOIN s.survey_conditions sc ON sc.survey_uid = u.survey_uid
        WHERE c.parameter = 'chloride' AND c.value > 0 AND c.value <= 20000""").df()
    d = d[d.src.isin(STREAMS_ONLY)].copy()
    d["m"] = d.d.dt.month
    d["season"] = np.where(d.m.isin([12, 1, 2, 3]), "winter", np.where(d.m.isin([6, 7, 8, 9]), "summer", "other"))
    d["lcl"] = np.log10(d.cl)
    return d


def site_seasons(cl: pd.DataFrame, min_n=2) -> pd.DataFrame:
    g = cl[cl.season != "other"].groupby(["site_id", "season"]).agg(cl=("cl", "median"), n=("cl", "size")).reset_index()
    g = g[g.n >= min_n].pivot(index="site_id", columns="season", values="cl").dropna()
    g.columns = [f"cl_{c}" for c in g.columns]
    return g.reset_index()


def paving(r) -> pd.DataFrame:
    return r.execute("""SELECT h.site_id, w.impervious_2025 AS paved FROM site_huc h JOIN s.watershed_impervious w USING (huc12)""").df()


def seasons(r, cl, b):
    base = site_seasons(cl)
    ss = base.merge(paving(r), on="site_id", how="left")
    ratio = ss.cl_summer / ss.cl_winter
    out = {"sites": int(len(ss)), "winter_median": r3(ss.cl_winter.median(), 1), "summer_median": r3(ss.cl_summer.median(), 1),
           "summer_over_winter_median": r3(ratio.median(), 2), "summer_ge_winter_share": r3((ratio >= 1).mean()),
           "summer_over_50": r3((ss.cl_summer > 50).mean()), "summer_over_100": r3((ss.cl_summer > 100).mean()),
           "summer_over_230": r3((ss.cl_summer > 230).mean()),
           "rho_summer_winter": r3(stats.spearmanr(ss.cl_summer, ss.cl_winter).statistic)}
    # bugs: each site's average against its winter and its summer chloride (paving held equal)
    bb = b.groupby(["site_id", "protocol"]).agg(n=("score", "size"), sensitive_share=("sensitive_share", "mean"),
                                                pct_tolerant=("pct_tolerant", "mean"), score_pct=("score_pct", "mean")).reset_index()
    x = bb.merge(ss, on="site_id").dropna(subset=["paved"])
    x["lw"], x["ls"] = np.log10(x.cl_winter), np.log10(x.cl_summer)
    res = {"sites": int(x.site_id.nunique())}
    for y in ("sensitive_share", "pct_tolerant", "score_pct"):
        row = {}
        for nm, v in (("winter", "lw"), ("summer", "ls")):
            m = smf.wls(f"{y} ~ {v} + paved + C(protocol)", x, weights=np.sqrt(x.n)).fit(cov_type="HC3")
            lo, hi = m.conf_int().loc[v]
            row[nm] = {"rho": r3(stats.spearmanr(x[v], x[y], nan_policy="omit").statistic), "coef": r3(m.params[v], 4),
                       "lo": r3(lo, 4), "hi": r3(hi, 4), "p": pf(m.pvalues[v]), "r2": r3(m.rsquared)}
        both = smf.wls(f"{y} ~ lw + ls + paved + C(protocol)", x, weights=np.sqrt(x.n)).fit(cov_type="HC3")
        row["both"] = {"winter_coef": r3(both.params["lw"], 4), "winter_p": pf(both.pvalues["lw"]),
                       "summer_coef": r3(both.params["ls"], 4), "summer_p": pf(both.pvalues["ls"])}
        res[y] = row
    out["bugs"] = res
    return out, base


def sources(r, ss):
    """Site summer and winter chloride against what is upstream."""
    w = r.execute("""SELECT h.site_id, w.impervious_2025 AS paved, p.npdes_permits, p.npdes_major, g.population, g.area_sqkm,
                            g.median_income
        FROM site_huc h JOIN s.watershed_impervious w USING (huc12) LEFT JOIN s.watershed_pressures p USING (huc12)
        LEFT JOIN s.monitoring_gaps g USING (huc12)""").df()
    w["pop_density"] = w.population / w.area_sqkm
    sc = r.execute("""SELECT site_id, rddensws AS road_density, septicws AS septic, wwtpalldensws AS wwtp, huden2010ws AS housing,
                             npdesdensws AS npdes_density, pctimp2019ws AS paved_catchment, bfiws AS baseflow_index
                      FROM s.site_pressures""").df()
    out = {}
    x = ss.merge(w, on="site_id")
    for c in ("npdes_permits", "pop_density"):
        x["l_" + c] = np.log10(1 + x[c])
    for season in ("winter", "summer"):
        x["y"] = np.log10(x[f"cl_{season}"])
        row = {"sites": int(len(x))}
        base = smf.ols("y ~ paved", x).fit(cov_type="HC3")
        row["paved_only"] = {"coef10": r3(10 * base.params["paved"], 3), "p": pf(base.pvalues["paved"]), "r2": r3(base.rsquared)}
        for c in ("l_npdes_permits", "l_pop_density"):
            xx = x.dropna(subset=[c])
            m = smf.ols(f"y ~ paved + {c}", xx).fit(cov_type="HC3")
            row[c] = {"coef": r3(m.params[c], 3), "p": pf(m.pvalues[c]), "r2": r3(m.rsquared), "n": int(m.nobs)}
        out[f"huc12_{season}"] = row
    # StreamCat: only public stream sites on a mapped segment
    y = ss.merge(sc, on="site_id")
    for c in ("road_density", "septic", "wwtp", "housing", "npdes_density"):
        y["l_" + c] = np.log10(1e-3 + y[c])
    for season in ("winter", "summer"):
        y["y"] = np.log10(y[f"cl_{season}"])
        row = {"sites": int(len(y))}
        base = smf.ols("y ~ paved_catchment", y).fit(cov_type="HC3")
        row["paved_only"] = {"coef10": r3(10 * base.params["paved_catchment"], 3), "p": pf(base.pvalues["paved_catchment"]), "r2": r3(base.rsquared)}
        ps = []
        for c in ("l_road_density", "l_septic", "l_wwtp", "l_housing", "l_npdes_density", "baseflow_index"):
            m = smf.ols(f"y ~ paved_catchment + {c}", y).fit(cov_type="HC3")
            row[c] = {"coef": r3(m.params[c], 3), "p": pf(m.pvalues[c]), "r2": r3(m.rsquared),
                      "rho": r3(stats.spearmanr(y[c], y.y).statistic), "rho_paved": r3(stats.spearmanr(y[c], y.paved_catchment).statistic)}
            ps.append(m.pvalues[c])
        for c, q in zip(("l_road_density", "l_septic", "l_wwtp", "l_housing", "l_npdes_density", "baseflow_index"), bh(ps)):
            row[c]["q"] = float(f"{q:.4g}")
        out[f"streamcat_{season}"] = row
    return out


def flow(cl):
    """Same site, different days: log chloride against the gauge flow percentile, site means removed, by season."""
    out = {}
    for season in ("winter", "summer", "other"):
        x = cl[(cl.season == season) & cl.flow_pct.notna()].copy()
        x = x[x.groupby("site_id").site_id.transform("size") >= 4]
        for c in ("lcl", "flow_pct"):
            x[c + "_w"] = x[c] - x.groupby("site_id")[c].transform("mean")
        m = sm.OLS(x.lcl_w, sm.add_constant(x.flow_pct_w)).fit(cov_type="cluster", cov_kwds={"groups": x.site_id.astype("category").cat.codes})
        lo, hi = m.conf_int().loc["flow_pct_w"]
        # low (bottom quarter) vs high (top quarter) water at the same site
        x["band"] = pd.cut(x.flow_pct, [-1, 0.25, 0.75, 1.01], labels=["low", "mid", "high"])
        lohi = x.groupby("band", observed=True).lcl_w.mean().to_dict()
        out[season] = {"readings": int(len(x)), "sites": int(x.site_id.nunique()), "coef": r3(m.params["flow_pct_w"], 3),
                       "lo": r3(lo, 3), "hi": r3(hi, 3), "p": pf(m.pvalues["flow_pct_w"]),
                       "ratio_low_vs_high": r3(10 ** (lohi.get("low", np.nan) - lohi.get("high", np.nan)), 2)}
    return out


def mediation(d, boots=1000):
    """On surveys paired with chloride: total link of paving to the bugs, the part that runs through chloride
    (paving -> chloride x chloride -> bugs, paving held) and the rest. Bootstrap over sites."""
    d = d.dropna(subset=["paved", "lcl"]).copy()

    def fit(x, y):
        a = smf.ols("lcl ~ paved + C(protocol) + C(season)", x).fit().params["paved"]
        full = smf.ols(f"{y} ~ paved + lcl + C(protocol) + C(season)", x).fit().params
        tot = smf.ols(f"{y} ~ paved + C(protocol) + C(season)", x).fit().params["paved"]
        return tot, full["paved"], a * full["lcl"], a

    out = {"surveys": int(len(d)), "sites": int(d.site_id.nunique())}
    rng, sites = np.random.default_rng(SEED), d.site_id.unique()
    by = {k: g for k, g in d.groupby("site_id")}
    for y in ("sensitive_share", "pct_tolerant", "score_pct"):
        x = d.dropna(subset=[y])
        tot, direct, ind, a = fit(x, y)
        bs = []
        for _ in range(boots):
            s = pd.concat([by[k] for k in rng.choice(sites, len(sites))]).dropna(subset=[y])
            try:
                bs.append(fit(s, y))
            except Exception:
                continue
        bs = np.array(bs)
        share = bs[:, 2] / bs[:, 0]
        out[y] = {"total_per10": r3(10 * tot, 4), "direct_per10": r3(10 * direct, 4), "via_chloride_per10": r3(10 * ind, 4),
                  "share_via_chloride": r3(ind / tot), "share_lo": r3(np.percentile(share, 2.5)), "share_hi": r3(np.percentile(share, 97.5)),
                  "total_lo": r3(10 * np.percentile(bs[:, 0], 2.5), 4), "total_hi": r3(10 * np.percentile(bs[:, 0], 97.5), 4),
                  "direct_lo": r3(10 * np.percentile(bs[:, 1], 2.5), 4), "direct_hi": r3(10 * np.percentile(bs[:, 1], 97.5), 4),
                  "via_lo": r3(10 * np.percentile(bs[:, 2], 2.5), 4), "via_hi": r3(10 * np.percentile(bs[:, 2], 97.5), 4),
                  "boots": int(len(bs))}
    out["paving_to_chloride_per10"] = r3(10 * a, 4)   # log10 mg/L per 10 points of paving
    out["paving_to_chloride_factor_per10"] = r3(10 ** (10 * a), 3)
    return out


def main():
    r = connect()
    cl, b = readings(r), bugs(r)
    sea, ss = seasons(r, cl, b)
    d30 = pair(b, cl.rename(columns={})[["site_id", "d", "protocol", "cl"]], 30)
    res = {"readings": int(len(cl)), "sites": int(cl.site_id.nunique()), "seasons": sea, "sources": sources(r, ss),
           "flow": flow(cl), "mediation": mediation(d30)}
    allres = json.loads(OUT.read_text()) if OUT.exists() else {}
    allres["chloride_sources"] = res
    OUT.write_text(json.dumps(allres, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
