"""Chloride and stream bugs, both measured by Save Our Streams volunteers.

Asked by the SOS program: is there a link between chloride and the bugs, both the overall SOS score and each kind of animal?
Every pairing below puts a volunteer chloride reading (SOS Chemical kit or Salt Watch strip) beside a volunteer bug survey
at the same site, so both sides are SOS data. Paving, season and state come from the joined public data as controls only.

  pairs        how many bug surveys have a chloride reading at the same site within 7 / 30 days, and in the winter before
  score        Virginia SOS score, sensitive share, % EPT, % tolerant against log chloride: raw, then with paving, season
               and state held, then within a site (the same stream in saltier vs fresher weeks)
  bands        the same outcomes in chloride bands, cut at EPA's chronic (230 mg/L) and acute (860 mg/L) criteria
  threshold    the chloride level where the score drops most (nonparametric change point, bootstrap interval)
  winter       winter (Dec-Mar) chloride at a site against its spring (Mar-Jun) bug survey
  taxa         each of the 19 Virginia rocky-bottom groups: share of organisms and presence against chloride, paving held
  professional EPA NRSA visits, where professionals measured chloride and bugs together: same question, independent data

Writes aggregates only, under "salt_bugs" in iwla_river/web/findings/context_results.json. Needs statsmodels: run with DataLab's environment.

    ~/datalab/.venv/bin/python -m iwla_river.salt_bugs
"""

from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

from . import config as cfg
from .context import OUT, STREAMS, bh, pf, r3

SEED = 20261106
MAXSCORE = {"va_rocky": 12, "sos_bio": 44}
OUTCOMES = {"score_pct": "SOS score, % of the form's maximum", "sensitive_share": "share of sensitive groups",
            "pct_ept": "% mayflies, stoneflies, caddisflies", "pct_tolerant": "% tolerant animals"}
BANDS = [0, 25, 100, 230, 860, 1e9]
BAND_NAMES = ["under 25", "25-100", "100-230", "230-860", "over 860"]


def connect():
    r = duckdb.connect(str(cfg.DB_PATH), read_only=True)
    r.execute(f"ATTACH '{STREAMS}' AS s (READ_ONLY)")
    return r


def chloride(r) -> pd.DataFrame:
    """Volunteer chloride readings. Zeros are dropped (mostly blanks or 'below detection'); readings over 20,000 mg/L
    (beyond seawater's 19,400) are dropped as entry errors."""
    return r.execute("""SELECT u.site_id, u.survey_date AS d, c.protocol, c.value AS cl
        FROM chemistry c JOIN usable_surveys u USING (survey_uid)
        WHERE c.parameter = 'chloride' AND c.value > 0 AND c.value <= 20000""").df()


def bugs(r) -> pd.DataFrame:
    d = r.execute("""SELECT f.survey_uid, f.protocol, f.site_id, f.state, f.survey_date AS d, f.year, f.month, f.season,
            f.score, f.sensitive_share, f.pct_ept, f.pct_tolerant, f.total_organisms,
            sc.impervious_at_survey AS paved, sc.huc12
        FROM features f LEFT JOIN s.survey_context sc USING (survey_uid)
        WHERE f.protocol IN ('va_rocky', 'sos_bio')""").df()
    d["score_pct"] = 100 * d.score / d.protocol.map(MAXSCORE)
    d[["season", "state"]] = d[["season", "state"]].fillna("unknown")
    return d


def pair(b: pd.DataFrame, cl: pd.DataFrame, days: int) -> pd.DataFrame:
    """Each bug survey with the median of its site's chloride readings within +/- days."""
    m = b[["survey_uid", "site_id", "d"]].merge(cl, on="site_id", suffixes=("", "_cl"))
    m = m[(m.d - m.d_cl).abs().dt.days <= days]
    g = m.groupby("survey_uid").agg(cl=("cl", "median"), n_cl=("cl", "size"),
                                    kit=("protocol", lambda p: (p == "sos_chem").any()))
    d = b.merge(g, on="survey_uid")
    d["lcl"] = np.log10(d.cl)
    return d


def _ols(d, y, x="lcl", ctrl=True):
    f = f"{y} ~ {x}" + (" + paved + C(season) + C(state) + C(protocol)" if ctrl else "")
    x_ = d.dropna(subset=[y, x] + (["paved"] if ctrl else []))
    m = smf.ols(f, x_).fit(cov_type="cluster", cov_kwds={"groups": x_.site_id.astype("category").cat.codes})
    lo, hi = m.conf_int().loc[x]
    return {"coef": r3(m.params[x], 4), "lo": r3(lo, 4), "hi": r3(hi, 4), "p": pf(m.pvalues[x]), "n": int(m.nobs),
            "sites": int(x_.site_id.nunique())}


def _within(d, y):
    """Same site, saltier vs fresher visits: demean chloride and the outcome by site (and season), slope of what is left."""
    x = d.dropna(subset=[y, "lcl"])
    x = x[x.groupby("site_id").site_id.transform("size") >= 2].copy()
    for c in (y, "lcl"):
        x[c + "_w"] = x[c] - x.groupby("site_id")[c].transform("mean")
        x[c + "_w"] = x[c + "_w"] - x.groupby("season")[c + "_w"].transform("mean")
    m = sm.OLS(x[y + "_w"], sm.add_constant(x["lcl_w"])).fit(cov_type="cluster", cov_kwds={"groups": x.site_id.astype("category").cat.codes})
    lo, hi = m.conf_int().loc["lcl_w"]
    return {"coef": r3(m.params["lcl_w"], 4), "lo": r3(lo, 4), "hi": r3(hi, 4), "p": pf(m.pvalues["lcl_w"]), "n": int(len(x)),
            "sites": int(x.site_id.nunique()), "cl_sd_within": r3(float(x.lcl_w.std()), 3)}


def score_links(d):
    out = {}
    for y in OUTCOMES:
        if d[y].notna().sum() < 30:
            continue
        rho = stats.spearmanr(d.lcl, d[y], nan_policy="omit")
        out[y] = {"spearman": r3(rho.statistic), "spearman_p": pf(rho.pvalue), "raw": _ols(d, y, ctrl=False),
                  "controlled": _ols(d, y), "within_site": _within(d, y)}
    return out


def bands(d):
    d = d.assign(band=pd.cut(d.cl, BANDS, labels=BAND_NAMES, right=False))
    rows = []
    for b, g in d.groupby("band", observed=False):
        rows.append({"band": str(b), "surveys": int(len(g)), "sites": int(g.site_id.nunique()),
                     **{y: r3(g[y].median()) for y in OUTCOMES}, "paved": r3(g.paved.median()),
                     "va_score": r3(g[g.protocol == "va_rocky"].score.median(), 1), "va_n": int((g.protocol == "va_rocky").sum()),
                     "sos_score": r3(g[g.protocol == "sos_bio"].score.median(), 1), "sos_n": int((g.protocol == "sos_bio").sum())})
    kw = stats.kruskal(*[g.score_pct.dropna() for _, g in d.groupby("band", observed=True) if len(g) >= 5])
    return {"rows": rows, "kruskal_h": r3(kw.statistic, 1), "kruskal_p": pf(kw.pvalue)}


def threshold(d, y="score_pct", boots=500):
    """Nonparametric change point: the chloride split that most reduces deviance in y (King & Richardson 2003)."""
    x = d.dropna(subset=[y, "cl"]).sort_values("cl")
    v, c = x[y].to_numpy(float), x.cl.to_numpy(float)

    def best(v, c):
        n, tot = len(v), ((v - v.mean()) ** 2).sum()
        cs, cs2 = np.cumsum(v), np.cumsum(v ** 2)
        k = np.arange(10, n - 10)
        left = cs2[k - 1] - cs[k - 1] ** 2 / k
        right = (cs2[-1] - cs2[k - 1]) - (cs[-1] - cs[k - 1]) ** 2 / (n - k)
        i = k[np.argmin(left + right)]
        return (c[i - 1] + c[i]) / 2, v[:i].mean(), v[i:].mean(), 1 - (left + right).min() / tot

    cp, below, above, r2 = best(v, c)
    rng, bs = np.random.default_rng(SEED), []
    sites = x.site_id.unique()
    by = {k: g for k, g in x.groupby("site_id")}
    for _ in range(boots):
        s = pd.concat([by[k] for k in rng.choice(sites, len(sites))]).sort_values("cl")
        bs.append(best(s[y].to_numpy(float), s.cl.to_numpy(float))[0])
    lo, hi = np.percentile(bs, [5, 95])
    return {"outcome": y, "change_point_mg_l": r3(cp, 1), "lo90": r3(lo, 1), "hi90": r3(hi, 1),
            "mean_below": r3(below, 2), "mean_above": r3(above, 2), "deviance_explained": r3(r2), "boots": boots}


def sites(b, cl):
    """Chronic exposure: each site's median chloride over all its readings, against its average bug results.
    Sites with at least 3 chloride readings and 2 bug surveys; paving is the site's median at survey time."""
    c = cl.groupby("site_id").agg(cl=("cl", "median"), n_cl=("cl", "size"))
    g = b.groupby(["site_id", "protocol"]).agg(n=("score", "size"), paved=("paved", "median"), state=("state", "first"),
                                               **{y: (y, "mean") for y in OUTCOMES}).reset_index()
    g = g.merge(c, on="site_id")
    g = g[(g.n_cl >= 3) & (g.n >= 2)].copy()
    g["lcl"], g["season"] = np.log10(g.cl), "all"
    out = {"sites": int(len(g)), "median_cl": r3(g.cl.median(), 1)}
    for y in OUTCOMES:
        x = g.dropna(subset=[y, "paved"])
        m = smf.wls(f"{y} ~ lcl + paved + C(protocol)", x, weights=np.sqrt(x.n)).fit(cov_type="HC3")
        lo, hi = m.conf_int().loc["lcl"]
        out[y] = {"spearman": r3(stats.spearmanr(g.lcl, g[y], nan_policy="omit").statistic), "coef": r3(m.params["lcl"], 4),
                  "lo": r3(lo, 4), "hi": r3(hi, 4), "p": pf(m.pvalues["lcl"]), "n": int(m.nobs)}
    return out


def winter(b, cl):
    """Median chloride Dec (year before) - Mar at the site, against that site's Mar-Jun bug survey."""
    w = cl[cl.d.dt.month.isin([12, 1, 2, 3])].copy()
    w["spring"] = w.d.dt.year + (w.d.dt.month == 12)
    w = w.groupby(["site_id", "spring"]).agg(wcl=("cl", "median"), wn=("cl", "size")).reset_index()
    s = b[b.month.between(3, 6)].merge(w, left_on=["site_id", "year"], right_on=["site_id", "spring"])
    s["lcl"] = np.log10(s.wcl)
    return {"surveys": int(len(s)), "sites": int(s.site_id.nunique()), "median_winter_cl": r3(s.wcl.median(), 1),
            **{y: {"spearman": r3(stats.spearmanr(s.lcl, s[y], nan_policy="omit").statistic),
                   "controlled": _ols(s, y)} for y in ("score_pct", "sensitive_share")}}


def taxa(r, d, protocol):
    """Each group's share of the organisms counted, and whether it was found, against log chloride (paving, season held)."""
    t = r.execute("""SELECT survey_uid, taxon, tolerance, count, present FROM taxa WHERE protocol = ?""", [protocol]).df()
    t = t.merge(d[["survey_uid", "site_id", "lcl", "paved", "season", "state", "protocol", "total_organisms"]], on="survey_uid")
    tot = t.groupby("survey_uid")["count"].transform(lambda c: c.fillna(0).sum())   # the original form keeps no total
    t["share"] = 100 * t["count"].fillna(0) / tot.where(tot > 0)
    rows = []
    for (tx, tol), g in t.groupby(["taxon", "tolerance"]):
        g = g.dropna(subset=["paved", "share"])
        if g.present.sum() < 30:
            continue
        ab = _ols(g, "share")
        try:
            m = smf.glm("present ~ lcl + paved + C(season)", g.assign(present=g.present.astype(float)),
                        family=sm.families.Binomial()).fit(cov_type="cluster", cov_kwds={"groups": g.site_id.astype("category").cat.codes})
            # chance of finding it at 25 vs 100 mg/L chloride (both well inside the data), median paving, summer
            base = {"paved": g.paved.median(), "season": "Summer"}
            p_lo, p_hi = m.predict(pd.DataFrame([{**base, "lcl": np.log10(25)}, {**base, "lcl": np.log10(100)}]))
            pres = {"odds_per_10x": r3(float(np.exp(m.params["lcl"])), 3), "p": float(m.pvalues["lcl"]),
                    "found_at_25": r3(float(p_lo)), "found_at_100": r3(float(p_hi))}
        except Exception as e:
            print("presence model failed:", tx, repr(e)[:120])
            pres = {"odds_per_10x": None, "p": None, "found_at_25": None, "found_at_100": None}
        rho = stats.spearmanr(g.lcl, g.share)
        rows.append({"taxon": tx, "tolerance": tol, "surveys": int(len(g)), "found": int(g.present.sum()),
                     "share_median": r3(g.share.median(), 2), "spearman": r3(rho.statistic), "share_per_10x": ab["coef"],
                     "share_lo": ab["lo"], "share_hi": ab["hi"], "share_p": ab["p"], **pres})
    q_ab = bh([x["share_p"] if isinstance(x["share_p"], float) else 1e-12 for x in rows])
    q_pr = bh([x["p"] if x["p"] is not None else 1.0 for x in rows])
    for x, a, b_ in zip(rows, q_ab, q_pr):
        x["share_q"], x["present_q"] = float(f"{a:.4g}"), float(f"{b_:.4g}")
        x["p"] = pf(x["p"]) if x["p"] is not None else None
    return sorted(rows, key=lambda x: x["share_per_10x"] if x["share_per_10x"] is not None else 0)


def professional(r):
    """EPA NRSA: professionals measured chloride and the bug index on the same visit."""
    p = r.execute("""SELECT site_id, state, year, score, chloride_mg_l cl, conductance_us_cm cond, condition
                     FROM s.prof_visits WHERE source = 'nrsa' AND chloride_mg_l > 0 AND score IS NOT NULL""").df()
    p["lcl"] = np.log10(p.cl)
    rho = stats.spearmanr(p.lcl, p.score)
    m = smf.ols("score ~ lcl + C(state)", p).fit(cov_type="cluster", cov_kwds={"groups": p.site_id.astype("category").cat.codes})
    p["band"] = pd.cut(p.cl, BANDS, labels=BAND_NAMES, right=False)
    return {"visits": int(len(p)), "sites": int(p.site_id.nunique()), "spearman": r3(rho.statistic), "spearman_p": pf(rho.pvalue),
            "coef_per_10x": r3(m.params["lcl"], 3), "coef_p": pf(m.pvalues["lcl"]),
            "bands": [{"band": str(k), "visits": int(len(g)), "score_median": r3(g.score.median(), 1),
                       "good_share": r3((g.condition == "Good").mean())} for k, g in p.groupby("band", observed=False)]}


def main():
    r = connect()
    cl, b = chloride(r), bugs(r)
    d7, d30 = pair(b, cl, 7), pair(b, cl, 30)
    res = {
        "pairs": {"bug_surveys": int(len(b)), "within_7d": int(len(d7)), "sites_7d": int(d7.site_id.nunique()),
                  "within_30d": int(len(d30)), "sites_30d": int(d30.site_id.nunique()),
                  "kit_share_7d": r3(d7.kit.mean()), "median_cl_7d": r3(d7.cl.median(), 1),
                  "p90_cl_7d": r3(d7.cl.quantile(.9), 1), "states_7d": d7.state.value_counts().head(5).to_dict(),
                  "paved_cl_rho": r3(stats.spearmanr(d7.paved, d7.lcl, nan_policy="omit").statistic)},
        "forms_7d": d7.protocol.value_counts().to_dict(), "forms_30d": d30.protocol.value_counts().to_dict(),
        "score_7d": score_links(d7),
        "score_by_form_30d": {f: _ols(d30[d30.protocol == f], "score") for f in MAXSCORE},
        "score_30d": score_links(d30),
        "score_7d_kits_only": score_links(d7[d7.kit]),
        "bands_7d": bands(d7),
        "threshold_score": {f: threshold(d30[d30.protocol == f], "score") for f in MAXSCORE},
        "threshold_sensitive": threshold(d30, "sensitive_share"),
        "winter": winter(b, cl),
        "sites": sites(b, cl),
        "taxa_va_30d": taxa(r, d30, "va_rocky"),
        "taxa_sos_30d": taxa(r, d30, "sos_bio"),
        "professional": professional(r),
    }
    res["pairs"]["share_7d"] = r3(len(d7) / len(b))
    allres = json.loads(OUT.read_text()) if OUT.exists() else {}
    allres["salt_bugs"] = res
    OUT.write_text(json.dumps(allres, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
