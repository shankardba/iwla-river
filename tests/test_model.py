"""Tests for the expected-score model's validation design."""

import numpy as np
import pandas as pd

from iwla_river import model as M


def synthetic(n_sites=120, per_site=8, signal=True, quirk=0.1, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_sites):
        imp = rng.uniform(0, 40)
        site_level = rng.normal(0, quirk)  # each site's own quirk, not predictable from inputs
        for _ in range(per_site):
            row = {f: np.nan for f in M.FEATURES}
            row.update(site_id=s, form=float(rng.integers(0, 2)), ws_impervious_pct=imp,
                       doy_sin=rng.uniform(-1, 1), doy_cos=rng.uniform(-1, 1), lat=rng.uniform(36, 42))
            y = site_level + rng.normal(0, 0.02)
            if signal:
                y += 0.5 - 0.01 * imp
            row["target"] = y
            rows.append(row)
    return pd.DataFrame(rows)


def test_usable_features_skips_empty_inputs():
    d = synthetic(n_sites=10)
    feats = M.usable_features(d)
    assert "ws_impervious_pct" in feats and "rain_7d_mm" not in feats


def test_held_out_sites_cannot_borrow_their_own_quirks():
    # Only per-site quirks, no real signal: a model validated on unseen sites must not look skilful.
    d = synthetic(signal=False)
    feats = M.usable_features(d)
    pred, _ = M.out_of_fold(d, "target", feats)
    assert M.r2(d.target.to_numpy(), pred) < 0.05


def test_real_signal_is_learned():
    d = synthetic(signal=True, quirk=0.02)
    feats = M.usable_features(d)
    pred, folds = M.out_of_fold(d, "target", feats)
    assert M.r2(d.target.to_numpy(), pred) > 0.6
    imp = {r["group"]: r["r2_drop"] for r in M.grouped_importance(d, "target", folds, feats)}
    assert max(imp, key=imp.get) == "Watershed land cover"
