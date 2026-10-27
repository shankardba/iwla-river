"""Tests for the phase 2 statistics."""

import numpy as np

from iwla_river import analysis as A


def test_seasonal_kendall_finds_a_steady_rise():
    years = np.repeat(np.arange(2005, 2025), 2).astype(float)
    season = np.tile(["Spring", "Summer"], 20)
    x = (years - 2005) * 0.5 + np.where(season == "Spring", 3.0, 0.0)
    r = A.seasonal_kendall(years, x, season)
    assert r["S"] > 0 and r["p"] < 0.001
    assert abs(r["slope_per_year"] - 0.5) < 1e-9
    assert r["pairs"] == 2 * (20 * 19 // 2)


def test_seasonal_kendall_ignores_season_differences():
    # Spring always higher than summer, no change over the years: no trend.
    years = np.repeat(np.arange(2005, 2025), 2).astype(float)
    season = np.tile(["Spring", "Summer"], 20)
    rng = np.random.default_rng(1)
    x = np.where(season == "Spring", 20.0, 12.0) + rng.normal(0, 0.5, 40)
    assert A.seasonal_kendall(years, x, season)["p"] > 0.1


def test_mean_shift_finds_a_step():
    x = np.r_[np.full(12, 10.0), np.full(12, 16.0)] + np.random.default_rng(2).normal(0, 1, 24)
    r = A.mean_shift(x)
    assert r["k"] == 12 and r["p"] < 0.01


def test_mean_shift_on_noise_is_not_significant():
    x = np.random.default_rng(3).normal(0, 1, 24)
    assert A.mean_shift(x)["p"] > 0.05


def test_jaccard_and_shannon():
    assert A.jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert abs(A.shannon([10, 10]) - np.log(2)) < 1e-12
    assert np.isnan(A.shannon([0, None]))


def test_point_in_polygon_with_a_hole():
    from iwla_river.enrich import _inside
    outer = [[0, 0], [10, 0], [10, 10], [0, 10]]
    hole = [[4, 4], [6, 4], [6, 6], [4, 6]]
    assert _inside(2, 2, [outer, hole])
    assert not _inside(5, 5, [outer, hole])      # inside the hole
    assert not _inside(12, 5, [outer, hole])


def test_watersheds_skip_without_codes(tmp_path):
    import duckdb
    from iwla_river import watersheds
    db = tmp_path / "x.duckdb"
    duckdb.connect(str(db)).close()
    assert watersheds.run(db) == 0
