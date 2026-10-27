"""Phase 3: the expected-score model and observed-minus-expected.

For every usable biological survey, predict what it should find given its season, survey form,
watershed (land cover, soils, climate), recent rain, water temperature, flow and team. The model
never sees the year, so change over time stays in the gap between observed and expected.

Validation is grouped by site: each survey's expected value comes from a model that never saw any
survey from that site. That is how the chapter is judged by what the rest of the country predicts.

Targets
  sensitive_share  share of animal groups found that are pollution-sensitive (comparable across forms)
  score_pct        the survey score as a percentile within its own form (0 to 100)

Adds tables: expected, model_metrics, model_importance, model_dependence, residual_trends.

Usage: python -m iwla_river.model
"""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

from . import config as C
from .analysis import seasonal_kendall, MIN_PAIRS

TARGETS = {
    "sensitive_share": "Share of groups found that are pollution-sensitive",
    "score_pct": "Score percentile within its survey form",
}
FLOW = {"Negligible": -2, "Low": -1, "Below Average": -1, "Normal": 0, "Average": 0,
        "High": 1, "Above Average": 1}
GROUPS = {  # feature groups for importance, in words people use
    "Season": ["doy_sin", "doy_cos"],
    "Survey form": ["form"],
    "Watershed land cover": ["ws_impervious_pct", "ws_urban_pct", "ws_forest_pct", "ws_crop_pct",
                             "ws_hay_pct", "ws_wetland_pct", "ws_road_crossings", "ws_pop_density"],
    "Watershed setting (soil, elevation, climate)": ["ws_elev_m", "ws_precip_mm", "ws_mean_temp_c",
                                                     "ws_clay_pct", "ws_sand_pct"],
    "Location": ["lat", "lon"],
    "Recent rain and heat": ["rain_1d_mm", "rain_3d_mm", "rain_7d_mm", "air_tmax_7d_c"],
    "Water temperature and flow": ["water_temp_c", "flow"],
    "Team": ["group_size", "certified"],
}
FEATURES = [f for g in GROUPS.values() for f in g]
N_FOLDS = 5
BAND = (0.1, 0.9)  # expected range = 10th to 90th percentile of held-out errors


def load(con) -> pd.DataFrame:
    has_wx = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'survey_weather'").fetchall()[0][0]
    wx = ("LEFT JOIN survey_weather w USING (survey_uid)" if has_wx else "")
    wx_cols = ("w.rain_1d_mm, w.rain_3d_mm, w.rain_7d_mm, w.air_tmax_7d_c" if has_wx else
               "NULL AS rain_1d_mm, NULL AS rain_3d_mm, NULL AS rain_7d_mm, NULL AS air_tmax_7d_c")
    df = con.execute(f"""
        SELECT f.*, c.* EXCLUDE (site_id, comid), {wx_cols}
        FROM features f LEFT JOIN site_context c USING (site_id) {wx}""").df()
    d = pd.to_datetime(df.survey_date)
    doy = d.dt.day_of_year
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    df["form"] = df.protocol.map({"sos_bio": 0, "va_rocky": 1, "va_muddy": 2}).astype(float)
    df["flow"] = df.flow_rate.map(FLOW).astype(float)
    df["certified"] = df.certified.astype(float)
    df["score_pct"] = 100 * df.groupby("protocol").score.rank(pct=True)
    for col in FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    return df


def usable_features(df: pd.DataFrame) -> list[str]:
    """Inputs filled for at least 5% of surveys (rain is absent until it has been fetched)."""
    return [f for f in FEATURES if df[f].notna().mean() >= 0.05]


def make_model(feats: list[str]) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=500, learning_rate=0.04, max_leaf_nodes=15, min_samples_leaf=40,
        l2_regularization=1.0, categorical_features=[feats.index("form")], random_state=0)


def out_of_fold(df: pd.DataFrame, target: str, feats: list[str]) -> tuple[np.ndarray, list]:
    """Expected values from models that never saw the survey's site, plus fold indices."""
    pred = np.full(len(df), np.nan)
    folds = []
    for tr, te in GroupKFold(n_splits=N_FOLDS).split(df, groups=df.site_id):
        m = make_model(feats).fit(df.iloc[tr][feats], df.iloc[tr][target])
        pred[te] = m.predict(df.iloc[te][feats])
        folds.append((m, te))
    return pred, folds


def r2(y, p) -> float:
    return float(1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum())


def grouped_importance(df, target, folds, feats, seed=0) -> list[dict]:
    """Drop in held-out R² when a whole group of inputs is shuffled."""
    rng = np.random.default_rng(seed)
    groups = {g: [c for c in cols if c in feats] for g, cols in GROUPS.items()}
    groups = {g: c for g, c in groups.items() if c}
    out = {g: [] for g in groups}
    for m, te in folds:
        X, y = df.iloc[te][feats].copy(), df.iloc[te][target].to_numpy()
        base = r2(y, m.predict(X))
        for g, cols in groups.items():
            Xp = X.copy()
            idx = rng.permutation(len(Xp))
            Xp[cols] = Xp[cols].to_numpy()[idx]
            out[g].append(base - r2(y, m.predict(Xp)))
    return [{"target": target, "group": g, "r2_drop": float(np.mean(v))} for g, v in out.items()]


def dependence(df, target, model, feats, feature="ws_impervious_pct") -> list[dict]:
    """Average prediction as one input is set to each value on a grid (partial dependence)."""
    grid = np.linspace(0, float(np.nanpercentile(df[feature], 98)), 25)
    sample = df.sample(min(len(df), 2000), random_state=0)[feats].copy()
    rows = []
    for v in grid:
        sample[feature] = v
        rows.append({"target": target, "feature": feature, "value": float(v),
                     "expected": float(model.predict(sample).mean())})
    return rows


def run(db_path=C.DB_PATH) -> dict:
    con = duckdb.connect(str(db_path))
    df = load(con)
    expected, metrics, importance, dep, trends = [], [], [], [], []
    for target, label in TARGETS.items():
        d = df[df[target].notna() & df.site_id.notna()].reset_index(drop=True)
        y = d[target].to_numpy(float)
        feats = usable_features(d)
        pred, folds = out_of_fold(d, target, feats)
        resid = y - pred
        lo, hi = np.quantile(resid, BAND)
        # Baseline: form and season only, also grouped by site.
        base = np.full(len(d), np.nan)
        for tr, te in GroupKFold(n_splits=N_FOLDS).split(d, groups=d.site_id):
            means = d.iloc[tr].groupby(["protocol", "season"])[target].mean()
            base[te] = [means.get((p, s), d.iloc[tr][target].mean()) for p, s in zip(d.protocol.iloc[te], d.season.iloc[te])]
        metrics.append({"target": target, "label": label, "surveys": len(d), "sites": int(d.site_id.nunique()),
                        "r2": r2(y, pred), "mae": float(np.abs(resid).mean()),
                        "baseline_r2": r2(y, base), "baseline_mae": float(np.abs(y - base).mean()),
                        "band_lo": float(lo), "band_hi": float(hi),
                        "rain_coverage": float(d.rain_7d_mm.notna().mean())})
        importance += grouped_importance(d, target, folds, feats)
        full = make_model(feats).fit(d[feats], d[target])
        dep += dependence(d, target, full, feats)
        e = d[["survey_uid", "site_id", "protocol", "survey_date", "year", "season", "is_chapter_site",
               "km_from_chapter"]].copy()
        e["target"], e["observed"], e["expected"] = target, y, pred
        e["resid"] = resid
        e["exp_lo"], e["exp_hi"] = pred + lo, pred + hi
        e["outside"] = np.where(resid < lo, "below", np.where(resid > hi, "above", "within"))
        expected.append(e)
        # Does observed-minus-expected change over time? Same seasonal Kendall test as phase 2.
        near = e[e.is_chapter_site | (e.km_from_chapter <= C.NEIGHBOUR_KM)]
        for (site, proto), g in near.groupby(["site_id", "protocol"]):
            if len(g) < C.TREND_MIN_SURVEYS or g.year.max() - g.year.min() < C.TREND_MIN_YEARS:
                continue
            sy = g.groupby(["season", "year"], as_index=False).resid.median()
            r = seasonal_kendall(sy.year.to_numpy(float), sy.resid.to_numpy(float), sy.season.to_numpy())
            verdict = ("too few repeat seasons" if r["pairs"] < MIN_PAIRS else "no clear trend" if r["p"] >= 0.1
                       else "improving" if r["S"] > 0 else "declining")
            trends.append({"target": target, "site_id": int(site), "protocol": proto,
                           "is_chapter_site": bool(g.is_chapter_site.iloc[0]), "km": float(g.km_from_chapter.iloc[0]),
                           "n": len(g), "mean_resid": float(g.resid.mean()), "p": r["p"], "pairs": r["pairs"],
                           "slope_per_decade": 10 * r["slope_per_year"] if r["pairs"] >= MIN_PAIRS else float("nan"),
                           "verdict": verdict})
    tables = {"expected": pd.concat(expected), "model_metrics": pd.DataFrame(metrics),
              "model_importance": pd.DataFrame(importance), "model_dependence": pd.DataFrame(dep),
              "residual_trends": pd.DataFrame(trends)}
    for name, t in tables.items():
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.register("df", t)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
        con.unregister("df")
    con.close()
    out = {m["target"]: {k: round(v, 3) if isinstance(v, float) else v for k, v in m.items() if k != "label"} for m in metrics}
    print(out)
    return out


if __name__ == "__main__":
    run()
