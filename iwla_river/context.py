"""Volunteer data in context: IWLA surveys checked against public USGS, EPA, state and Census data.

Recomputes every number shown on the site's "In context" pages from two local databases:
  - data/river.duckdb (this project's cleaned Clean Water Hub snapshot), and
  - DataLab's `streams` dataset (IWLA joined with USGS gauges, Water Quality Portal chloride, EPA ECHO, ATTAINS,
    Annual NLCD, Census ACS, EPA NRSA, Maryland MBSS and Stream Waders, restoration project records), built by
    the private DataLab project. Set DATALAB_STREAMS to its data.duckdb.

Writes iwla_river/web/findings/context_results.json: aggregate statistics only (counts, medians, coefficients,
p-values, intervals). No site location or name leaves this script. Every test is named next to its result.

    python -m iwla_river.context
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import cohen_kappa_score

from . import config as C
from .analysis import mean_shift, seasonal_kendall

STREAMS = Path(os.environ.get("DATALAB_STREAMS", Path.home() / "datalab/datasets/streams/data.duckdb"))
OUT = Path(__file__).parent / "web" / "findings" / "context_results.json"
RNG = np.random.default_rng(20261028)
BOOT = 2000
CLASSES = {"Poor": 0, "Fair": 1, "Good": 2}


def pf(p):
    """p-values to two significant figures, never rounded to zero."""
    return None if p is None or not math.isfinite(p) else float(f"{p:.2g}")


def r3(x, d=3):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), d)


def boot_ci(groups: np.ndarray, fn, reps=BOOT):
    """95% percentile interval, resampling whole clusters (watersheds, projects) so repeat visits don't count twice."""
    ug = np.unique(groups)
    idx = {g: np.flatnonzero(groups == g) for g in ug}
    vals = []
    for _ in range(reps):
        pick = np.concatenate([idx[g] for g in RNG.choice(ug, len(ug), replace=True)])
        v = fn(pick)
        if v is not None and math.isfinite(v):
            vals.append(v)
    return [r3(np.percentile(vals, 2.5)), r3(np.percentile(vals, 97.5))] if vals else [None, None]


def bh(p):
    """Benjamini–Hochberg q-values."""
    p = np.asarray(p, float)
    n = len(p)
    o = np.argsort(p)
    q = np.empty(n)
    q[o] = np.minimum.accumulate((p[o] * n / np.arange(1, n + 1))[::-1])[::-1]
    return np.minimum(q, 1)


def ols(y, X, cluster=None):
    """Least squares with heteroskedasticity-robust (HC1) or cluster-robust standard errors; returns coef, se, p."""
    X = np.column_stack([np.ones(len(y)), X]) if cluster is None else np.asarray(X, float)
    n, k = X.shape
    XtX = np.linalg.pinv(X.T @ X)
    b = XtX @ X.T @ y
    e = y - X @ b
    if cluster is None:
        meat = (X * e[:, None]).T @ (X * e[:, None]) * n / (n - k)
        df = n - k
    else:
        meat = np.zeros((k, k))
        g = pd.Series(range(n)).groupby(np.asarray(cluster)).indices
        for ix in g.values():
            s = X[ix].T @ e[ix]
            meat += np.outer(s, s)
        G = len(g)
        meat *= G / (G - 1) * (n - 1) / (n - k)
        df = G - 1
    se = np.sqrt(np.diag(XtX @ meat @ XtX))
    p = 2 * stats.t.sf(np.abs(b / se), df)
    return b, se, p


# ---------- 1. volunteer chloride vs agency laboratory chloride ----------
def chloride_validation(s):
    d = s.sql("""SELECT protocol, site_id, huc12, volunteer_mg_l v, agency_median_mg_l a, winter FROM chloride_pairs
                 WHERE NOT zero_reading AND NOT implausible AND volunteer_mg_l > 0 AND agency_median_mg_l > 0""").df()
    out = {}
    for proto, g in d.groupby("protocol"):
        lv, la = np.log10(g.v.to_numpy()), np.log10(g.a.to_numpy())
        hu = g.huc12.to_numpy()
        ratio = g.v / g.a
        w = g[g.winter]
        out[proto] = {
            "pairs": len(g), "sites": int(g.site_id.nunique()), "watersheds": int(g.huc12.nunique()),
            "log_r": r3(stats.pearsonr(lv, la)[0]), "log_r_ci": boot_ci(hu, lambda i: stats.pearsonr(lv[i], la[i])[0]),
            "rho": r3(stats.spearmanr(g.v, g.a)[0]),
            "median_ratio": r3(ratio.median()), "within_factor_2": r3((ratio.between(0.5, 2)).mean()),
            "winter_pairs": len(w), "winter_vol_median": r3(w.v.median(), 1), "winter_agency_median": r3(w.a.median(), 1),
            "winter_wilcoxon_p": pf(stats.wilcoxon(np.log10(w.v), np.log10(w.a)).pvalue) if len(w) > 10 else None}
    return out


# ---------- 2. chloride across all IWLA sites over time ----------
def chloride_trend(r):
    d = r.sql("""SELECT s.site_id, s.survey_date::DATE AS date, c.value FROM chemistry c JOIN usable_surveys s USING (survey_uid)
                 WHERE c.parameter = 'chloride' AND c.value IS NOT NULL""").df()
    zeros, implausible = int((d.value == 0).sum()), int((d.value > 20000).sum())
    d = d[(d.value > 0) & (d.value <= 20000)].copy()
    d["date"] = pd.to_datetime(d.date)
    d["lv"] = np.log10(d.value)
    n_site = d.groupby("site_id").lv.transform("size")
    d = d[n_site >= 3].copy()
    d["c"] = d.lv - d.groupby("site_id").lv.transform("median")      # each reading relative to its own site
    m = d.groupby(d.date.dt.to_period("M")).agg(c=("c", "median"), n=("c", "size"), sites=("site_id", "nunique"))
    m = m[m.n >= 3]
    t = np.array([p.year + (p.month - 0.5) / 12 for p in m.index])
    sk = seasonal_kendall(t, m.c.to_numpy(), np.array([(p.month - 1) // 3 for p in m.index]))
    ms = mean_shift(m.c.to_numpy(), min_seg=12)
    shift_at = str(m.index[ms["k"]]) if ms["k"] is not None else None
    before, after = (m.c.iloc[:ms["k"]].median(), m.c.iloc[ms["k"]:].median()) if ms["k"] else (None, None)
    # site by site: sites with 8+ readings over 4+ years
    rows = []
    for sid, g in d.groupby("site_id"):
        yrs = g.date.dt.year
        if len(g) >= 8 and yrs.max() - yrs.min() >= 4:
            tt = (g.date.dt.year + (g.date.dt.day_of_year - 0.5) / 366).to_numpy()
            k = seasonal_kendall(tt, g.lv.to_numpy(), ((g.date.dt.month - 1) // 3).to_numpy())
            rows.append((k["p"], k["slope_per_year"]))
    p = np.array([x[0] for x in rows])
    sl = np.array([x[1] for x in rows])
    q = bh(p) if len(p) else p
    return {"readings": int(len(d)), "sites": int(d.site_id.nunique()), "months": int(len(m)),
            "first": str(m.index[0]), "last": str(m.index[-1]),
            "zero_readings": zeros, "implausible_readings": implausible, "max_reading": r3(r.sql(
                "SELECT max(value) FROM chemistry WHERE parameter = 'chloride'").fetchall()[0][0], 0),
            "sk_p": pf(sk["p"]), "sk_z": r3(sk["z"]), "pct_per_year": r3((10 ** sk["slope_per_year"] - 1) * 100, 2),
            "pct_per_decade": r3((10 ** (10 * sk["slope_per_year"]) - 1) * 100, 1),
            "shift_at": shift_at, "shift_p": pf(ms["p"]),
            "shift_change_pct": r3((10 ** (after - before) - 1) * 100, 1) if before is not None else None,
            "site_tests": int(len(rows)), "sites_rising_q05": int(((q < 0.05) & (sl > 0)).sum()),
            "sites_falling_q05": int(((q < 0.05) & (sl < 0)).sum()),
            "site_median_pct_per_year": r3((10 ** np.nanmedian(sl) - 1) * 100, 2) if len(sl) else None,
            "rising_median_pct_per_year": r3((10 ** np.median(sl[(q < 0.05) & (sl > 0)]) - 1) * 100, 1) if len(sl) else None}


# ---------- 3. development vs winter road salt as explanations of spring bug scores ----------
def scores_with_huc(r, s):
    f = r.sql("""SELECT f.survey_uid, f.site_id, f.protocol, f.year, f.month, f.sos_total, f.va_score, h.huc12
                 FROM features f JOIN site_huc h USING (site_id)""").df()
    f["score"] = np.where(f.protocol == "sos_bio", f.sos_total, f.va_score)
    f = f[f.score.notna()].copy()
    f["family"] = np.where(f.protocol == "sos_bio", "sos", "va")
    f["z"] = f.groupby("family").score.transform(lambda x: (x - x.mean()) / x.std())   # one scale for both forms
    return f


def development_vs_salt(r, s, f):
    sp = f[f.month.between(3, 5)].groupby(["huc12", "year"]).z.mean().rename("score").reset_index()
    w = s.sql("SELECT * FROM winter_salt").df()
    for col in ("agency_chloride_mg_l", "gauge_conductance_us_cm", "volunteer_chloride_mg_l"):
        v = np.log10(w[col].where(w[col] > 0))
        w[col + "_z"] = (v - v.mean()) / v.std()
    w["salt"] = w[[c for c in w.columns if c.endswith("_z")]].mean(axis=1)
    w = w[w.salt.notna()][["huc12", "spring_year", "salt"]].rename(columns={"spring_year": "year"})
    imp = s.sql("SELECT * FROM watershed_impervious").df().set_index("huc12")
    yrs = np.arange(1985, 2026, 5)
    d = sp.merge(w, on=["huc12", "year"])
    d = d[d.huc12.isin(imp.index)].copy()
    d["imperv"] = [np.interp(y, yrs, imp.loc[h, [f"impervious_{x}" for x in yrs]].to_numpy(float)) for h, y in zip(d.huc12, d.year)]
    d = d.dropna()
    # between watersheds: watershed means
    b = d.groupby("huc12")[["score", "imperv", "salt"]].mean()
    coef, se, p = ols(b.score.to_numpy(), b[["imperv", "salt"]].to_numpy())
    c1, _, p1 = ols(b.score.to_numpy(), b[["salt"]].to_numpy())
    # within watersheds: remove watershed and year effects (two-way demeaning), cluster by watershed
    wi = d[d.groupby("huc12").year.transform("size") >= 2].copy()
    for col in ("score", "salt"):
        x = wi[col].to_numpy(float).copy()
        for _ in range(50):
            x = x - wi.assign(v=x).groupby("huc12").v.transform("mean").to_numpy()
            x = x - wi.assign(v=x).groupby("year").v.transform("mean").to_numpy()
        wi[col + "_w"] = x
    cw, sew, pw = ols(wi.score_w.to_numpy(), wi[["salt_w"]].to_numpy(), cluster=wi.huc12.to_numpy())
    return {"watershed_years": int(len(d)), "watersheds": int(d.huc12.nunique()),
            "between_imperv_coef": r3(coef[1]), "between_imperv_p": pf(p[1]),
            "between_salt_coef": r3(coef[2]), "between_salt_p": pf(p[2]),
            "salt_alone_coef": r3(c1[1]), "salt_alone_p": pf(p1[1]),
            "corr_imperv_salt": r3(np.corrcoef(b.imperv, b.salt)[0, 1]),
            "within_watersheds": int(wi.huc12.nunique()), "within_rows": int(len(wi)),
            "within_salt_coef": r3(cw[0]), "within_salt_se": r3(sew[0]), "within_salt_p": pf(pw[0])}


# ---------- 4. state-listed impaired biology vs volunteer and professional scores ----------
def impaired_biology(s, f):
    wp = s.sql("SELECT huc12, biota_impaired FROM watershed_pressures").df()
    site = f.groupby(["site_id", "family", "huc12"]).score.median().reset_index().merge(wp, on="huc12")
    out = {}
    for fam, g in site.groupby("family"):
        a, b = g[g.biota_impaired].score, g[~g.biota_impaired].score
        if len(a) >= 5:
            out[fam] = {"impaired_sites": len(a), "other_sites": len(b), "impaired_median": r3(a.median(), 2),
                        "other_median": r3(b.median(), 2), "p": float(f"{stats.mannwhitneyu(a, b).pvalue:.2g}")}
    pro = s.sql("""SELECT p.source, p.state, p.site_id, median(p.score) score, any_value(w.biota_impaired) imp
                   FROM prof_visits p JOIN watershed_pressures w USING (huc12) WHERE p.score IS NOT NULL
                   GROUP BY ALL""").df()
    for (src, st), g in pro.groupby(["source", "state"]):
        if (src, st) not in (("nrsa", "VA"), ("mbss", "MD")):
            continue
        a, b = g[g.imp == True].score, g[g.imp != True].score   # noqa: E712
        if len(a) >= 5:
            out[f"{src}_{st}"] = {"impaired_sites": len(a), "other_sites": len(b), "impaired_median": r3(a.median(), 2),
                                  "other_median": r3(b.median(), 2), "p": float(f"{stats.mannwhitneyu(a, b).pvalue:.2g}")}
    return out


# ---------- 5. volunteer vs professional bug surveys ----------
def agreement(x, y, cx=None, cy=None):
    o = {"pairs": int(len(x)), "rho": r3(stats.spearmanr(x, y)[0]), "rho_p": float(f"{stats.spearmanr(x, y)[1]:.2g}")}
    if cx is not None:
        m = cx.notna() & cy.notna()
        a, b = cx[m].map(CLASSES), cy[m].map(CLASSES)
        o.update(same_class=r3((a == b).mean(), 2), kappa_w=r3(cohen_kappa_score(a, b, weights="linear"), 2),
                 vol_good=int((a == 2).sum()), vol_good_pro_fair_or_poor=int(((a == 2) & (b < 2)).sum()),
                 vol_higher=int((a > b).sum()), vol_lower=int((a < b).sum()))
    return o


def volunteer_vs_professional(s):
    p = s.sql("SELECT * FROM pro_pairs").df()
    out = {}
    for (src, proto, match), g in p.groupby(["source", "protocol", "match"]):
        if len(g) >= 6:
            o = agreement(g.vol_score, g.pro_score, g.vol_condition, g.pro_condition)
            o["sites"] = int(g.site_id.nunique())
            out[f"{proto}|{src}|{match}"] = o
    md = s.sql("SELECT * FROM md_volunteer_pairs WHERE km <= 1").df()
    out["stream_waders|mbss|within 1 km"] = agreement(md.volunteer_ibi, md.mbss_ibi, md.volunteer_condition, md.mbss_condition)
    return out


# ---------- 6. where the monitoring is, and where it isn't ----------
def monitoring_gaps(s):
    g = s.sql("SELECT * FROM monitoring_gaps").df()
    hi = g[g.need_score >= 5]
    cov = g.assign(band=pd.cut(g.need_score, [-1, 1, 3, 5, 9], labels=["0–1", "2–3", "4–5", "6–9"])) \
        .groupby("band", observed=True).agg(n=("huc12", "size"), monitored=("unmonitored", lambda x: (~x).sum()))
    mon_hi, un_hi = hi[~hi.unmonitored], hi[hi.unmonitored]
    near = g[g.km_to_active_iwla_site <= 25]
    nh = near[near.need_score >= 5]
    pinc = lambda a, b: float(f"{stats.mannwhitneyu(a.dropna(), b.dropna()).pvalue:.2g}")
    return {"watersheds": len(g), "basins": None, "with_active_bug_site": int((~g.unmonitored).sum()),
            "high_need": len(hi), "high_need_unmonitored": len(un_hi),
            "high_need_unmonitored_within_25km": int((un_hi.km_to_active_iwla_site <= 25).sum()),
            "coverage_by_need": {str(k): [int(v.n), int(v.monitored)] for k, v in cov.iterrows()},
            "income_monitored_high_need": r3(mon_hi.median_income.median(), 0),
            "income_unmonitored_high_need": r3(un_hi.median_income.median(), 0), "income_p": pinc(mon_hi.median_income, un_hi.median_income),
            "income_near_monitored": r3(nh[~nh.unmonitored].median_income.median(), 0),
            "income_near_unmonitored": r3(nh[nh.unmonitored].median_income.median(), 0),
            "income_near_p": pinc(nh[~nh.unmonitored].median_income, nh[nh.unmonitored].median_income),
            "top_recruitable": [[x.watershed, x.nearest_site_state, r3(x.km_to_active_iwla_site, 0), int(x.need_score)]
                                for x in un_hi[un_hi.km_to_active_iwla_site <= 25].sort_values(
                                    ["need_score", "km_to_active_iwla_site"], ascending=[False, True]).head(10).itertuples()]}


# ---------- 7. stream restoration: before and after, against controls and a placebo ----------
def restoration(r, s):
    ev = s.sql("""SELECT project_id, year, lat, lon, state FROM restoration_events
                  WHERE kind = 'stream restoration' AND lat IS NOT NULL AND year BETWEEN 1995 AND 2022""").df()
    allev = s.sql("SELECT lat, lon FROM restoration_events WHERE lat IS NOT NULL").df()
    sv = r.sql("""SELECT site_id, any_value(lat) lat, any_value(lon) lon, any_value(state) state FROM features
                  WHERE protocol IN ('va_rocky', 'va_muddy') AND va_score IS NOT NULL GROUP BY site_id""").df()
    sc = r.sql("SELECT site_id, year, va_score FROM features WHERE protocol IN ('va_rocky', 'va_muddy') AND va_score IS NOT NULL").df()

    def km(la1, lo1, la2, lo2):
        la1, lo1, la2, lo2 = map(np.radians, (la1, lo1, la2, lo2))
        h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
        return 6371 * 2 * np.arcsin(np.sqrt(h))

    near_any = np.array([km(a, b, allev.lat.values, allev.lon.values).min() <= 5 for a, b in zip(sv.lat, sv.lon)])
    controls_pool = sv[~near_any]
    by_site = sc.groupby("site_id")

    def change(site_ids, y):
        out = []
        for sid in site_ids:
            g = by_site.get_group(sid)
            pre, post = g[(g.year >= y - 5) & (g.year <= y - 1)].va_score, g[(g.year >= y + 1) & (g.year <= y + 5)].va_score
            if len(pre) >= 2 and len(post) >= 2:
                out.append((post.mean() - pre.mean(), pre.mean()))
        return out

    def run(shift):
        rows = []
        for e in ev.itertuples():
            y = e.year - shift
            treated = sv[km(e.lat, e.lon, sv.lat.values, sv.lon.values) <= 5].site_id
            t = change(treated, y)
            if not t:
                continue
            c = change(controls_pool[controls_pool.state == e.state].site_id, y)
            if len(c) < 5:
                continue
            rows.append((e.project_id, np.mean([x[0] for x in t]), np.mean([x[0] for x in c]),
                         np.mean([x[1] for x in t]), np.mean([x[1] for x in c])))
        return pd.DataFrame(rows, columns=["project", "treated", "control", "treated_start", "control_start"])

    real, placebo = run(0), run(5)
    out = {}
    for name, d in (("real", real), ("placebo", placebo)):
        if len(d) < 5:
            out[name] = {"projects": len(d)}
            continue
        did = (d.treated - d.control).to_numpy()
        out[name] = {"projects": len(d), "did_mean": r3(did.mean(), 2),
                     "did_ci": boot_ci(np.arange(len(did)), lambda i: did[i].mean()),
                     "treated_change": r3(d.treated.mean(), 2), "control_change": r3(d.control.mean(), 2),
                     "treated_start": r3(d.treated_start.mean(), 2), "control_start": r3(d.control_start.mean(), 2)}
    return out


# ---------- 8. paving over time (Annual NLCD, every downloaded year) ----------
def development_trend(s, f):
    y = s.sql("SELECT huc12, year, impervious_pct FROM impervious_yearly").df()
    iwla = set(f.huc12.dropna())
    y["iwla"] = y.huc12.isin(iwla)
    years = sorted(int(v) for v in y.year.unique())
    med = y.groupby(["iwla", "year"]).impervious_pct.median().unstack(0)
    first, last = years[0], years[-1]
    w = y.pivot_table(index="huc12", columns="year", values="impervious_pct")
    gain = (w[last] - w[first]).dropna()
    gi = gain[gain.index.isin(iwla)]
    # within watersheds: does a watershed's spring score fall as it paves? watershed and year effects removed
    sp = f[f.month.between(3, 5)].groupby(["huc12", "year"]).z.mean().rename("score").reset_index()
    yy = np.array(years)
    sp = sp[sp.huc12.isin(w.index)].copy()
    sp["imperv"] = [np.interp(t, yy, w.loc[h, years].to_numpy(float)) for h, t in zip(sp.huc12, sp.year)]
    sp = sp.dropna()
    wi = sp[sp.groupby("huc12").year.transform("size") >= 3].copy()
    for col in ("score", "imperv"):
        x = wi[col].to_numpy(float).copy()
        for _ in range(50):
            x = x - wi.assign(v=x).groupby("huc12").v.transform("mean").to_numpy()
            x = x - wi.assign(v=x).groupby("year").v.transform("mean").to_numpy()
        wi[col + "_w"] = x
    cw, sew, pw = ols(wi.score_w.to_numpy(), wi[["imperv_w"]].to_numpy(), cluster=wi.huc12.to_numpy())
    return {"years": years, "n_years": len(years),
            "median_iwla": {int(k): r3(v, 2) for k, v in med[True].items()},
            "median_other": {int(k): r3(v, 2) for k, v in med[False].items()},
            "iwla_watersheds": int(len(gi)), "other_watersheds": int(len(gain) - len(gi)),
            "iwla_gain_median": r3(gi.median(), 2), "other_gain_median": r3(gain[~gain.index.isin(iwla)].median(), 2),
            "iwla_gain5_share": r3((gi >= 5).mean()), "iwla_gain10_share": r3((gi >= 10).mean()),
            "within_watersheds": int(wi.huc12.nunique()), "within_rows": int(len(wi)),
            "within_imperv_coef": r3(cw[0]), "within_imperv_se": r3(sew[0]), "within_imperv_p": pf(pw[0])}


# ---------- 9. storms before a survey (USGS gauge flow) ----------
def storm_timing(s, f):
    c = s.sql("SELECT survey_uid, storm_in_week, high_flow_day, flow_pct FROM survey_conditions WHERE flow_pct IS NOT NULL").df()
    d = f.merge(c, on="survey_uid")
    d = d[d.groupby("site_id").storm_in_week.transform("nunique") == 2].copy()   # sites surveyed both with and without a storm
    out = {"surveys": int(len(d)), "sites": int(d.site_id.nunique()), "storm_share": r3(d.storm_in_week.mean())}
    x = d.z.to_numpy(float).copy()
    st = d.storm_in_week.astype(float).to_numpy().copy()
    for _ in range(50):
        x = x - d.assign(v=x).groupby("site_id").v.transform("mean").to_numpy()
        x = x - d.assign(v=x).groupby("year").v.transform("mean").to_numpy()
        st = st - d.assign(v=st).groupby("site_id").v.transform("mean").to_numpy()
        st = st - d.assign(v=st).groupby("year").v.transform("mean").to_numpy()
    cw, sew, pw = ols(x, st[:, None], cluster=d.site_id.to_numpy())
    raw = d.groupby("storm_in_week").z.mean()
    out.update({"within_storm_coef": r3(cw[0]), "within_storm_ci": [r3(cw[0] - 1.96 * sew[0]), r3(cw[0] + 1.96 * sew[0])],
                "within_storm_p": pf(pw[0]), "raw_storm_z": r3(raw.get(True)), "raw_calm_z": r3(raw.get(False))})
    return out


# ---------- 10. what each public dataset added ----------
def enrichment(s, f):
    q = lambda sql: s.sql(sql).fetchall()[0][0]
    return {"sites": int(q("SELECT count(*) FROM site_spine")), "sites_public": int(q("SELECT count(*) FILTER (WHERE is_public) FROM site_spine")),
            "watersheds_with_sites": int(q("SELECT count(DISTINCT huc12) FROM site_spine WHERE huc12 IS NOT NULL")),
            "usgs_gauges": int(q("SELECT count(*) FROM usgs_gauges")),
            "surveys_with_flow": int(q("SELECT count(flow_pct) FROM survey_conditions")),
            "wqp_stations": int(q("SELECT count(*) FROM wqp_stations")), "chloride_pairs": int(q("SELECT count(*) FROM chloride_pairs")),
            "streamcat_catchments": int(q("SELECT count(*) FROM streamcat")),
            "nlcd_years": int(q("SELECT count(DISTINCT year) FROM impervious_yearly")),
            "nlcd_watersheds": int(q("SELECT count(DISTINCT huc12) FROM impervious_yearly")),
            "prof_visits": int(q("SELECT count(*) FROM prof_visits")),
            "restoration_events": int(q("SELECT count(*) FROM restoration_events")),
            "epa319_projects": int(q("SELECT count(*) FROM epa319_projects")),
            "gap_watersheds": int(q("SELECT count(*) FROM monitoring_gaps"))}


def main():
    r = duckdb.connect(str(C.DB_PATH), read_only=True)
    s = duckdb.connect(str(STREAMS), read_only=True, config={"enable_external_access": False})
    f = scores_with_huc(r, s)
    res = {
        "generated": dt.date.today().isoformat(),
        "inputs": {"clean_water_hub_snapshot": r.sql("SELECT max(snapshot_date) FROM snapshot").fetchall()[0][0],
                   "streams_dataset": dt.datetime.fromtimestamp(STREAMS.stat().st_mtime).date().isoformat()},
        "chloride_validation": chloride_validation(s),
        "chloride_trend": chloride_trend(r),
        "development_vs_salt": development_vs_salt(r, s, f),
        "impaired_biology": impaired_biology(s, f),
        "volunteer_vs_professional": volunteer_vs_professional(s),
        "monitoring_gaps": monitoring_gaps(s),
        "restoration": restoration(r, s),
        "development_trend": development_trend(s, f),
        "storm_timing": storm_timing(s, f),
        "enrichment": enrichment(s, f),
    }
    OUT.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
