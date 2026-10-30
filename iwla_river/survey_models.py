"""Three program-design questions about the bug surveys, answered with models scored on sites they never saw.

  site_reliability   How much of the variation in the sensitive-animal share is the site itself, and so how many
                     visits it takes to know a site (linear mixed model, random intercept per site; Spearman-Brown).
  mapped_vs_local    How much of the difference between sites mapped land and pollution data can predict, and how
                     much is local (LightGBM, 5 repeats of 5-fold cross-validation grouped by site).
  watershed_types    Kinds of small watershed by their pressures alone, and how their streams compare (k-means on
                     robust-scaled HUC12 medians, k by silhouette, stability from 30 re-clusterings of 80%).

Reads DataLab's `streams` dataset (survey_context: one row per bug survey with its watershed's pressures, gauge flow
and weather). Writes aggregates only into iwla_river/web/findings/context_results.json, beside python -m iwla_river.context.
Needs statsmodels and lightgbm: run with DataLab's environment.

    ~/datalab/.venv/bin/python -m iwla_river.survey_models
"""

from __future__ import annotations

import itertools
import json

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, r2_score, silhouette_score
from sklearn.model_selection import GroupKFold

from .context import OUT, STREAMS, bh, pf, r3

SEED = 20261030
FEATS = ["impervious_at_survey", "impervious_change_1985_2025", "road_density", "npdes_permits", "npdes_major",
         "npdes_significant_noncompliance", "mine_features", "impaired_waters", "salt_impaired", "nutrient_impaired",
         "sediment_impaired", "septic_upstream", "fertilizer_upstream", "manure_upstream", "flow_pct", "storm_in_week",
         "rain_7d_mm", "air_tmax_7d_c", "season", "state"]
PRESSURES = ["impervious_at_survey", "road_density", "npdes_permits", "mine_features", "impaired_waters",
             "septic_upstream", "fertilizer_upstream", "manure_upstream"]


def load() -> pd.DataFrame:
    s = duckdb.connect(str(STREAMS), read_only=True, config={"enable_external_access": False})
    cols = ", ".join(dict.fromkeys(["site_id", "huc12", "sensitive_share"] + FEATS))
    d = s.sql(f"SELECT {cols} FROM survey_context WHERE sensitive_share IS NOT NULL").df()
    d["storm_in_week"] = d.storm_in_week.astype("float")
    for c in ("season", "state"):
        d[c] = d[c].fillna("unknown").astype("category")
    return d


def states(d: pd.DataFrame) -> list:
    v = d.groupby("state", observed=True).site_id.size().sort_values(ascending=False)
    return [[k, int(n), r3(n / len(d))] for k, n in v.head(5).items()]


def site_reliability(d: pd.DataFrame) -> dict:
    """Random intercept per site, season as a fixed effect. ICC = between-site / (between + within) variance."""
    x = d.dropna(subset=["site_id"]).copy()
    m = smf.mixedlm("sensitive_share ~ C(season)", x, groups=x.site_id.astype(str)).fit(reml=True)
    between, within = float(m.cov_re.iloc[0, 0]), float(m.scale)
    icc = between / (between + within)
    # 95% interval: resample whole sites (200 rounds)
    rng, sites, boot = np.random.default_rng(SEED), x.site_id.unique(), []
    by = {k: g for k, g in x.groupby("site_id")}
    for _ in range(200):
        pick = rng.choice(sites, size=len(sites), replace=True)
        b = pd.concat([by[k].assign(site_id=f"{i}") for i, k in enumerate(pick)])
        try:
            mb = smf.mixedlm("sensitive_share ~ C(season)", b, groups=b.site_id).fit(reml=True)
            boot.append(float(mb.cov_re.iloc[0, 0]) / (float(mb.cov_re.iloc[0, 0]) + float(mb.scale)))
        except Exception:
            continue
    lo, hi = np.percentile(boot, [2.5, 97.5])
    visits = x.groupby("site_id").size()
    sb = lambda k, r: k * r / (1 + (k - 1) * r)  # Spearman-Brown: reliability of the mean of k visits
    return {"surveys": int(len(x)), "sites": int(x.site_id.nunique()), "states": states(x),
            "between_var": r3(between, 5), "within_var": r3(within, 5), "icc": r3(icc), "icc_lo": r3(lo), "icc_hi": r3(hi),
            "boot_rounds": len(boot),
            "reliability": {str(k): [r3(sb(k, icc)), r3(sb(k, lo)), r3(sb(k, hi))] for k in (1, 2, 3, 4, 6, 10)},
            "visits_for_0_8": int(np.ceil(0.8 * (1 - icc) / (icc * 0.2))), "visits_for_0_9": int(np.ceil(0.9 * (1 - icc) / (icc * 0.1))),
            "median_visits_per_site": float(visits.median()), "sites_with_1_visit": int((visits == 1).sum()),
            "sites_with_3_plus": int((visits >= 3).sum())}


def _cv(d: pd.DataFrame, feats: list[str], repeats: int = 5) -> dict:
    """Held-out predictions with every site's surveys kept together; R² per survey and per site mean."""
    X, y, g = d[feats], d.sensitive_share.to_numpy(), d.site_id.to_numpy()
    r2s, site_r2s = [], []
    for rep in range(repeats):
        pred = np.zeros(len(d))
        for tr, te in GroupKFold(n_splits=5, shuffle=True, random_state=SEED + rep).split(X, y, g):
            m = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=20,
                                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=SEED + rep, verbose=-1)
            m.fit(X.iloc[tr], y[tr])
            pred[te] = m.predict(X.iloc[te])
        r2s.append(r2_score(y, pred))
        sm = pd.DataFrame({"s": g, "y": y, "p": pred}).groupby("s").filter(lambda t: len(t) >= 3).groupby("s")[["y", "p"]].mean()
        site_r2s.append(r2_score(sm.y, sm.p))
    return {"r2": r3(np.mean(r2s)), "r2_lo": r3(min(r2s)), "r2_hi": r3(max(r2s)),
            "site_r2": r3(np.mean(site_r2s)), "site_r2_lo": r3(min(site_r2s)), "site_r2_hi": r3(max(site_r2s))}


def mapped_vs_local(d: pd.DataFrame) -> dict:
    x = d.dropna(subset=["site_id"]).copy()
    allf = _cv(x, FEATS)
    land = [f for f in FEATS if f not in ("flow_pct", "storm_in_week", "rain_7d_mm", "air_tmax_7d_c", "season")]
    road, paved = _cv(x, ["road_density"]), _cv(x, ["impervious_at_survey"])
    rho = stats.spearmanr(x.road_density, x.impervious_at_survey, nan_policy="omit")
    sites3 = int((x.groupby("site_id").size() >= 3).sum())
    return {"surveys": int(len(x)), "sites": int(x.site_id.nunique()), "sites_3_plus": sites3, "inputs": len(FEATS),
            "all": allf, "land_only": _cv(x, land), "road_only": road, "paved_only": paved,
            "road_paved_rho": r3(rho.statistic), "repeats": 5, "folds": 5}


def watershed_types(d: pd.DataFrame) -> dict:
    h = d.groupby("huc12").agg(**{c: (c, "median") for c in PRESSURES}, share=("sensitive_share", "median"),
                               n=("sensitive_share", "size"), sites=("site_id", "nunique"),
                               state=("state", lambda s: s.astype(str).mode().iat[0]))
    h = h[h.n >= 3].copy()
    F = h[PRESSURES].fillna(h[PRESSURES].median())
    Z = ((F - F.median()) / (F.quantile(0.75) - F.quantile(0.25)).replace(0, 1)).clip(-5, 5).to_numpy()
    sil = {k: float(silhouette_score(Z, KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(Z), random_state=0)) for k in range(2, 10)}
    k = max(sil, key=sil.get)
    lab = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(Z)
    rng, ids, aris, jac = np.random.default_rng(SEED), np.arange(len(Z)), [], {c: [] for c in range(k)}
    for _ in range(30):
        sub = np.sort(rng.choice(ids, size=int(0.8 * len(ids)), replace=False))
        lab2 = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(Z[sub])
        aris.append(adjusted_rand_score(lab[sub], lab2))
        for c in range(k):
            mem = set(sub[lab[sub] == c])
            jac[c].append(max(len(mem & set(sub[lab2 == e])) / max(1, len(mem | set(sub[lab2 == e]))) for e in range(k)))
    h["cl"] = lab
    prof = h.groupby("cl")[PRESSURES].median()
    # Name each type by what sets it apart: the most paved, the most fertiliser, the most manure; the rest low-pressure.
    names, left = {}, set(range(k))
    for col, nm in (("impervious_at_survey", "urban"), ("fertilizer_upstream", "cropland"), ("manure_upstream", "livestock"),
                    ("mine_features", "mining")):
        if len(left) <= 1:
            break
        c = int(prof.loc[sorted(left)][col].idxmax()); names[c] = nm; left.discard(c)
    for c in left:
        names[c] = "low-pressure" if len(left) == 1 else f"type {c + 1}"
    types = []
    for c in range(k):
        t = h[h.cl == c]
        st = t.state.value_counts()
        types.append({"name": names[c], "watersheds": int(len(t)), "sites": int(t.sites.sum()), "surveys": int(t.n.sum()),
                      "share_median": r3(t.share.median()), "stability": r3(np.mean(jac[c])),
                      "states": [[s, int(n)] for s, n in st.head(3).items()], "top_state_share": r3(st.iat[0] / len(t)),
                      "profile": {p: r3(v, 2) for p, v in prof.loc[c].items()}})
    kw = stats.kruskal(*[h[h.cl == c].share for c in range(k)])
    pairs = [(names[a], names[b], stats.mannwhitneyu(h[h.cl == a].share, h[h.cl == b].share).pvalue) for a, b in itertools.combinations(range(k), 2)]
    qs = bh([p for *_, p in pairs])
    return {"watersheds": int(len(h)), "min_surveys": 3, "k": k, "silhouette": {str(a): r3(b) for a, b in sil.items()},
            "ari_mean": r3(np.mean(aris)), "rounds": 30, "types": types, "kruskal_h": r3(kw.statistic, 1), "kruskal_p": pf(kw.pvalue),
            "pairs": [[a, b, float(f"{p:.4g}"), float(f"{q:.4g}")] for (a, b, p), q in zip(pairs, qs)]}


def main():
    d = load()
    res = json.loads(OUT.read_text()) if OUT.exists() else {}
    res["site_reliability"] = site_reliability(d)
    res["mapped_vs_local"] = mapped_vs_local(d)
    res["watershed_types"] = watershed_types(d)
    OUT.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("site_reliability", "mapped_vs_local", "watershed_types")}, indent=1, default=str)[:7000])


if __name__ == "__main__":
    main()
