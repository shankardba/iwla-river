"""Phase 2: per-survey features, trend tests, turning points and species-mix change.

Adds these tables to data/river.duckdb (run after clean):
  features         one row per usable biological survey: score, groups found, sensitive share, EPT, diversity
  site_trends      seasonal Kendall trend + Sen slope per site and measure
  turning_points   the strongest shift in the mean per site, with a permutation p-value
  taxa_by_period   share of surveys finding each animal group, per site and 5-year period
  baseline_drift   per survey: similarity of the groups found to the site's first five years

Usage: python -m iwla_river.analysis
"""

from __future__ import annotations

import math

import duckdb
import numpy as np
import pandas as pd

from . import config as C

BIO = ("sos_bio", "va_rocky", "va_muddy")
EPT = ("Ephemeroptera", "Plecoptera", "Trichoptera")
SEASONS = ("Spring", "Summer", "Fall")
MIN_PAIRS = 10  # same-season comparisons needed before a trend is reported


def season_of(month: int) -> str:
    return "Spring" if 3 <= month <= 6 else "Summer" if 7 <= month <= 9 else "Fall"


# ---------- statistics ----------

def _norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def seasonal_kendall(t_years: np.ndarray, x: np.ndarray, season: np.ndarray) -> dict:
    """Seasonal Kendall test (Hirsch, Slack and Smith 1982) with the seasonal Sen slope.

    Compares each value only with later values from the same season, so a spring-to-summer
    difference never looks like a trend. Returns S, z, two-sided p and slope per year.
    """
    S, var, slopes = 0.0, 0.0, []
    for g in np.unique(season):
        m = season == g
        tg, xg = t_years[m], x[m]
        order = np.argsort(tg, kind="stable")
        tg, xg = tg[order], xg[order]
        n = len(xg)
        if n < 2:
            continue
        for i in range(n - 1):
            dt = tg[i + 1:] - tg[i]
            dx = xg[i + 1:] - xg[i]
            ok = dt > 0
            S += np.sign(dx[ok]).sum()
            slopes.extend((dx[ok] / dt[ok]).tolist())
        _, counts = np.unique(xg, return_counts=True)
        ties = sum(c * (c - 1) * (2 * c + 5) for c in counts if c > 1)
        var += (n * (n - 1) * (2 * n + 5) - ties) / 18
    if var <= 0:
        return {"S": S, "z": 0.0, "p": 1.0, "slope_per_year": float("nan"), "pairs": len(slopes)}
    z = (S - 1) / math.sqrt(var) if S > 0 else (S + 1) / math.sqrt(var) if S < 0 else 0.0
    return {"S": S, "z": z, "p": 2 * _norm_sf(abs(z)),
            "slope_per_year": float(np.median(slopes)) if slopes else float("nan"), "pairs": len(slopes)}


def mean_shift(x: np.ndarray, min_seg: int = 4, n_perm: int = 999, seed: int = 7) -> dict:
    """Strongest single shift in the mean of an ordered series, tested by permutation.

    The statistic is the scaled difference in means either side of each split. Shuffling the
    series 999 times shows how often a split that strong appears by chance.
    """
    n = len(x)
    if n < 2 * min_seg:
        return {"k": None, "stat": float("nan"), "p": float("nan")}

    def best(v):
        cs = np.cumsum(v)
        k = np.arange(min_seg, n - min_seg + 1)
        left = cs[k - 1] / k
        right = (cs[-1] - cs[k - 1]) / (n - k)
        stat = np.abs(left - right) * np.sqrt(k * (n - k) / n)
        i = int(np.argmax(stat))
        return int(k[i]), float(stat[i])

    k, stat = best(x)
    rng = np.random.default_rng(seed)
    hits = sum(best(rng.permutation(x))[1] >= stat for _ in range(n_perm))
    return {"k": k, "stat": stat, "p": (hits + 1) / (n_perm + 1)}


def shannon(counts) -> float:
    c = np.asarray([v for v in counts if v and v > 0], dtype=float)
    if c.sum() == 0:
        return float("nan")
    p = c / c.sum()
    return float(-(p * np.log(p)).sum())


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else float("nan")


# ---------- features ----------

def build_features(con) -> pd.DataFrame:
    s = con.execute(f"""
        SELECT u.survey_uid, u.protocol, u.site_id, u.site_name, u.stream, u.state, u.lat, u.lon,
               u.survey_date, u.water_temp_c, u.flow_rate, u.group_size, u.certified, u.is_chapter_site,
               b.sensitive_score + b.less_sensitive_score + b.tolerant_score AS sos_total,
               b.multi_metric_score AS va_score, b.total_organisms
        FROM usable_surveys u JOIN bio_scores b USING (survey_uid)
        WHERE u.protocol IN {BIO}""").df()
    t = con.execute(f"""SELECT t.* FROM taxa t JOIN usable_surveys u USING (survey_uid)
                        WHERE u.protocol IN {BIO}""").df()
    agg = t.groupby("survey_uid").apply(lambda g: pd.Series({
        "groups_found": int(g.present.sum()),
        "sensitive_found": int((g.present & (g.tolerance == "sensitive")).sum()),
        "tolerant_found": int((g.present & (g.tolerance == "tolerant")).sum()),
        "ept_found": int((g.present & g.taxon_group.isin(EPT)).sum()),
        "counted": float(g["count"].fillna(0).sum()),
        "ept_count": float(g.loc[g.taxon_group.isin(EPT), "count"].fillna(0).sum()),
        "tolerant_count": float(g.loc[g.tolerance == "tolerant", "count"].fillna(0).sum()),
        "shannon": shannon(g["count"].fillna(0)),
    }), include_groups=False).reset_index()
    f = s.merge(agg, on="survey_uid", how="left")
    d = pd.to_datetime(f.survey_date)
    f["year"] = d.dt.year
    f["month"] = d.dt.month
    f["t_years"] = d.dt.year + (d.dt.day_of_year - 1) / 365.25
    f["season"] = f.month.map(season_of)
    # One headline score per survey: SOS total, or the Virginia multimetric score.
    f["score"] = np.where(f.protocol == "sos_bio", f.sos_total, f.va_score)
    f["sensitive_share"] = f.sensitive_found / f.groups_found.replace(0, np.nan)
    has_counts = f.counted > 0
    f["pct_ept"] = np.where(has_counts, 100 * f.ept_count / f.counted.where(has_counts), np.nan)
    f["pct_tolerant"] = np.where(has_counts, 100 * f.tolerant_count / f.counted.where(has_counts), np.nan)
    c = con.execute("SELECT lat, lon FROM sites WHERE site_id = 467").fetchall()[0]
    la, lo = np.radians(c[0]), np.radians(c[1])
    lat, lon = np.radians(f.lat), np.radians(f.lon)
    f["km_from_chapter"] = 6371 * 2 * np.arcsin(np.sqrt(
        np.sin((lat - la) / 2) ** 2 + np.cos(la) * np.cos(lat) * np.sin((lon - lo) / 2) ** 2))
    return f.drop(columns=["counted", "ept_count", "tolerant_count"])


# ---------- per-site tests ----------

MEASURES = {  # measure: (column, label for people, higher is better?)
    "score": ("score", "Survey score", True),
    "sensitive_share": ("sensitive_share", "Share of groups found that are pollution-sensitive", True),
    "ept_found": ("ept_found", "Mayfly, stonefly and caddisfly groups found", True),
}


def site_tests(f: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    trends, turns = [], []
    near = f[(f.km_from_chapter <= C.NEIGHBOUR_KM) | f.is_chapter_site]
    for (site, proto), g in near.groupby(["site_id", "protocol"]):
        g = g.sort_values("survey_date")
        span = g.year.max() - g.year.min()
        if len(g) < C.TREND_MIN_SURVEYS or span < C.TREND_MIN_YEARS:
            continue
        base = {"site_id": int(site), "protocol": proto, "site_name": g.site_name.iloc[0],
                "stream": g.stream.iloc[0], "state": g.state.iloc[0],
                "km": round(float(g.km_from_chapter.iloc[0]), 1), "is_chapter_site": bool(g.is_chapter_site.iloc[0]),
                "n": len(g), "first": g.survey_date.min(), "last": g.survey_date.max()}
        for key, (col, label, up_good) in MEASURES.items():
            v = g[[col, "year", "season"]].dropna()
            if len(v) < C.TREND_MIN_SURVEYS:
                continue
            # One value per season and year (the median), compared across whole years,
            # so two surveys a few days apart cannot produce an extreme slope.
            sy = v.groupby(["season", "year"], as_index=False)[col].median()
            r = seasonal_kendall(sy.year.to_numpy(float), sy[col].to_numpy(float), sy.season.to_numpy())
            sd = float(v[col].std()) or float("nan")
            verdict = ("too few repeat seasons" if r["pairs"] < MIN_PAIRS else
                       "no clear trend" if r["p"] >= 0.1 else
                       ("improving" if (r["S"] > 0) == up_good else "declining"))
            trends.append({**base, "measure": key, "label": label, "S": r["S"], "z": r["z"], "p": r["p"],
                           "pairs": r["pairs"], "seasons_years": len(sy),
                           "slope_per_decade": 10 * r["slope_per_year"] if r["pairs"] >= MIN_PAIRS else float("nan"), "mean": float(v[col].mean()),
                           "sd": sd, "verdict": verdict})
        # Turning point on the season-adjusted score.
        v = g[["score", "season", "survey_date"]].dropna().copy()
        if len(v) >= 8:
            v["adj"] = v.score - v.groupby("season").score.transform("mean")
            r = mean_shift(v.adj.to_numpy(float))
            if r["k"] is not None:
                k = r["k"]
                turns.append({**base, "split_after": v.survey_date.iloc[k - 1], "split_before": v.survey_date.iloc[k],
                              "mean_before": float(v.score.iloc[:k].mean()), "mean_after": float(v.score.iloc[k:].mean()),
                              "stat": r["stat"], "p": r["p"]})
    return pd.DataFrame(trends), pd.DataFrame(turns)


# ---------- species mix ----------

def species_mix(con, f: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sites = f[f.is_chapter_site | (f.km_from_chapter <= C.NEIGHBOUR_KM)]
    keep = sites.groupby(["site_id", "protocol"]).survey_uid.transform("size") >= C.TREND_MIN_SURVEYS
    sites = sites[keep]
    uids = tuple(sites.survey_uid) or ("",)
    t = con.execute(f"SELECT survey_uid, taxon, tolerance, present FROM taxa WHERE survey_uid IN {uids}").df()
    t = t.merge(sites[["survey_uid", "site_id", "protocol", "year", "survey_date"]], on="survey_uid")
    t["period"] = (t.year // 5 * 5).astype(str) + "–" + (t.year // 5 * 5 + 4).astype(str)
    by_period = (t.groupby(["site_id", "protocol", "period", "taxon", "tolerance"])
                 .agg(found=("present", "sum"), surveys=("survey_uid", "nunique")).reset_index())
    by_period["share_found"] = by_period.found / by_period.surveys

    drift = []
    for (site, proto), g in t.groupby(["site_id", "protocol"]):
        sets = g[g.present].groupby("survey_uid").taxon.agg(set)
        dates = g.drop_duplicates("survey_uid").set_index("survey_uid").survey_date
        first_year = int(g.year.min())
        base_uids = g[g.year < first_year + 5].survey_uid.unique()
        counts = pd.Series([x for u in base_uids for x in sets.get(u, set())]).value_counts()
        baseline = set(counts[counts >= len(base_uids) / 2].index)
        for u, d in dates.items():
            drift.append({"site_id": int(site), "protocol": proto, "survey_uid": u, "survey_date": d,
                          "baseline_years": f"{first_year}–{first_year + 4}",
                          "similarity_to_baseline": jaccard(sets.get(u, set()), baseline),
                          "groups_found": len(sets.get(u, set()))})
    return by_period, pd.DataFrame(drift)


def run(db_path=C.DB_PATH) -> dict:
    con = duckdb.connect(str(db_path))
    f = build_features(con)
    trends, turns = site_tests(f)
    by_period, drift = species_mix(con, f)
    for name, df in {"features": f, "site_trends": trends, "turning_points": turns,
                     "taxa_by_period": by_period, "baseline_drift": drift}.items():
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.register("df", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
        con.unregister("df")
    con.close()
    out = {"features": len(f), "site_trends": len(trends), "turning_points": len(turns),
           "taxa_by_period": len(by_period), "baseline_drift": len(drift)}
    print(out)
    return out


if __name__ == "__main__":
    run()
