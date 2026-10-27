"""Build the findings page (docs/index.html) from data/river.duckdb.

The page is static: data is embedded as JSON and drawn in the browser.
Only counts, scores and public site details go in; no names, no free text.

Usage: python -m iwla_river.site
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from . import config as C

TEMPLATE = Path(__file__).resolve().parent / "templates" / "findings.html"
OUT = C.ROOT / "docs" / "index.html"
LABEL = {467: "Site 1", 468: "Site 2"}


def rows(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, (v.isoformat() if hasattr(v, "isoformat") else v for v in r))) for r in cur.fetchall()]


def collect(db_path=C.DB_PATH) -> dict:
    con = duckdb.connect(str(db_path), read_only=True)
    chapter = ",".join(str(s) for s in C.CHAPTER_SITES)
    data = {
        "snapshot": con.execute("SELECT snapshot_date FROM snapshot").fetchall()[0][0],
        "chapterSites": [
            {"site_id": sid, "label": LABEL.get(sid, str(sid)), "name": name}
            for sid, name in C.CHAPTER_SITES.items()
        ],
        "sos": rows(con, f"""
            SELECT s.site_id, s.survey_date AS date, b.sensitive_score AS sens,
                   b.less_sensitive_score AS less, b.tolerant_score AS tol,
                   b.sensitive_score + b.less_sensitive_score + b.tolerant_score AS total,
                   s.water_temp_c AS temp_c, s.group_size
            FROM usable_surveys s JOIN bio_scores b USING (survey_uid)
            WHERE s.protocol = 'sos_bio' AND s.site_id IN ({chapter})
              AND b.sensitive_score IS NOT NULL ORDER BY date, site_id"""),
        "va": rows(con, f"""
            SELECT s.site_id, s.survey_date AS date, b.multi_metric_score AS mms, b.ecological_conditions AS cond
            FROM usable_surveys s JOIN bio_scores b USING (survey_uid)
            WHERE s.protocol IN ('va_rocky', 'va_muddy') AND s.site_id IN ({chapter}) ORDER BY date"""),
        "protocols": rows(con, """
            SELECT protocol, count(*) AS records, sum(usable::int) AS usable,
                   sum((survey_date IS NULL)::int) AS no_date, sum(date_invalid::int) AS bad_date, sum(is_deleted::int) AS deleted,
                   sum((duplicate_of IS NOT NULL)::int) AS duplicates, count(DISTINCT site_id) AS sites,
                   min(survey_date) FILTER (WHERE usable) AS first, max(survey_date) FILTER (WHERE usable) AS last
            FROM surveys GROUP BY protocol ORDER BY records DESC"""),
        "byYear": rows(con, """
            SELECT year(survey_date) AS year, protocol, count(*) AS n FROM usable_surveys
            WHERE year(survey_date) >= 2000 GROUP BY ALL ORDER BY year, protocol"""),
        "temps": rows(con, """
            SELECT protocol, temp_rule AS rule, count(*) AS n FROM surveys
            WHERE temp_rule <> 'missing' GROUP BY ALL ORDER BY protocol, n DESC"""),
        "chapterTemps": rows(con, f"""
            SELECT survey_date AS date, site_id, water_temp_raw AS raw, temp_rule AS rule, water_temp_c AS c
            FROM usable_surveys WHERE site_id IN ({chapter}) AND water_temp_raw IS NOT NULL ORDER BY date"""),
        "completeness": rows(con, """
            SELECT protocol, count(*) AS usable,
                   round(100 * avg((water_temp_c IS NOT NULL)::int)) AS temp,
                   round(100 * avg((flow_rate IS NOT NULL)::int)) AS flow,
                   round(100 * avg((weather_today IS NOT NULL OR weather_72h IS NOT NULL)::int)) AS weather,
                   round(100 * avg((group_size IS NOT NULL)::int)) AS team
            FROM usable_surveys WHERE protocol IN ('sos_bio', 'va_rocky', 'va_muddy') GROUP BY 1 ORDER BY usable DESC"""),
        "nearby": rows(con, f"""
            WITH c AS (SELECT lat, lon FROM sites WHERE site_id = 467), d AS (
              SELECT s.site_id, s.site_name, s.stream, s.state,
                round(6371 * 2 * asin(sqrt(pow(sin(radians(s.lat - c.lat) / 2), 2) +
                  cos(radians(c.lat)) * cos(radians(s.lat)) * pow(sin(radians(s.lon - c.lon) / 2), 2))), 1) AS km
              FROM sites s, c WHERE s.lat IS NOT NULL AND s.site_id NOT IN ({chapter}))
            SELECT d.*, (SELECT count(*) FROM usable_surveys u WHERE u.site_id = d.site_id) AS surveys,
                   (SELECT max(survey_date) FROM usable_surveys u WHERE u.site_id = d.site_id) AS last
            FROM d WHERE km <= 15 ORDER BY km LIMIT 12"""),
        # ---- phase 2 ----
        "trends": rows(con, f"""
            SELECT site_id, protocol, site_name, stream, state, km, is_chapter_site, n, first, last,
                   measure, label, p, pairs, slope_per_decade, mean, verdict
            FROM site_trends WHERE is_chapter_site OR measure = 'score' ORDER BY is_chapter_site DESC, km"""),
        "turns": rows(con, f"""
            SELECT site_id, protocol, n, split_before, mean_before, mean_after, p FROM turning_points
            WHERE site_id IN ({chapter})"""),
        "taxa": rows(con, f"""
            SELECT taxon, tolerance, period, sum(found)::int AS found, sum(surveys)::int AS surveys
            FROM taxa_by_period WHERE site_id IN ({chapter}) AND protocol = 'sos_bio'
            GROUP BY ALL ORDER BY tolerance, taxon, period"""),
        "drift": rows(con, f"""
            SELECT site_id, baseline_years,
                   round(avg(similarity_to_baseline) FILTER (WHERE year(survey_date) < 2013), 2) AS early,
                   round(avg(similarity_to_baseline) FILTER (WHERE year(survey_date) >= 2013), 2) AS late,
                   round(corr(similarity_to_baseline, year(survey_date)), 2) AS r
            FROM baseline_drift WHERE site_id IN ({chapter}) AND protocol = 'sos_bio' GROUP BY ALL ORDER BY site_id"""),
        "salt": rows(con, f"""
            SELECT s.site_id, s.survey_date AS date, c.parameter, c.value FROM chemistry c
            JOIN usable_surveys s USING (survey_uid)
            WHERE s.site_id IN ({",".join(str(s) for s in C.CHAPTER_CHEM_SITES)})
              AND c.parameter IN ('chloride', 'nitrate') ORDER BY date"""),
        "chemSites": [{"site_id": k, "label": v} for k, v in C.CHAPTER_CHEM_SITES.items()],
        "mdChloride": rows(con, """
            SELECT round(median(c.value)) AS median FROM chemistry c JOIN usable_surveys s USING (survey_uid)
            WHERE c.protocol = 'salt' AND c.parameter = 'chloride' AND s.state = 'MD'""")[0]["median"],
        # ---- phase 3 ----
        "modelMetrics": rows(con, "SELECT * FROM model_metrics"),
        "importance": rows(con, """SELECT target, "group", r2_drop FROM model_importance ORDER BY target, r2_drop DESC"""),
        "expected": rows(con, f"""
            SELECT target, site_id, protocol, survey_date::DATE AS date, observed, expected, exp_lo, exp_hi, resid, outside
            FROM expected WHERE site_id IN ({chapter}) ORDER BY date"""),
        "residTrends": rows(con, """SELECT target, site_id, is_chapter_site, n, mean_resid, p, slope_per_decade, verdict
                                    FROM residual_trends"""),
        "imperv": rows(con, """
            WITH b AS (
              SELECT e.target, e.observed, e.site_id, c.ws_impervious_pct AS imp,
                CASE WHEN imp < 2 THEN 0 WHEN imp < 5 THEN 1 WHEN imp < 10 THEN 2
                     WHEN imp < 15 THEN 3 WHEN imp < 25 THEN 4 ELSE 5 END AS bin
              FROM expected e JOIN site_context c USING (site_id) WHERE c.ws_impervious_pct IS NOT NULL)
            SELECT target, bin, ['0–2%', '2–5%', '5–10%', '10–15%', '15–25%', '25% +'][bin + 1] AS label,
                   count(*) AS surveys, count(DISTINCT site_id) AS sites, avg(observed) AS mean
            FROM b GROUP BY ALL ORDER BY target, bin"""),
        "context": rows(con, f"SELECT * FROM site_context WHERE site_id IN ({chapter}) ORDER BY site_id"),
        "totals": rows(con, """
            SELECT count(*) FILTER (WHERE usable) AS usable_surveys,
                   count(DISTINCT site_id) FILTER (WHERE usable) AS sites_with_data,
                   count(DISTINCT protocol) AS protocols FROM surveys""")[0],
    }
    con.close()
    return data


FRAGMENT = C.REPORTS / "findings.html"  # body-only copy, for hosts that add their own <html> shell
SHELL_HEAD = (
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    "<style>*,*::before,*::after{box-sizing:border-box}body{margin:0}"
    ":root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}</style>\n"
)


def build(db_path=C.DB_PATH, out: Path = OUT) -> Path:
    data = collect(db_path)
    page = TEMPLATE.read_text().replace("__DATA__", json.dumps(data, default=str).replace("</", "<\\/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(SHELL_HEAD + page + "\n</html>\n")
    FRAGMENT.parent.mkdir(parents=True, exist_ok=True)
    FRAGMENT.write_text(page)
    return out


if __name__ == "__main__":
    print(build())
