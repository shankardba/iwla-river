"""Write a data-quality report for the current database to reports/.

Only counts and ranges go in the report: no names, no free text.

Usage: python -m iwla_river.report
"""

from __future__ import annotations

import duckdb

from . import config as C

PLAUSIBLE = {  # parameter: (low, high) outside which a reading is flagged
    "ph_units": (2, 12),
    "dissolved_oxygen": (0, 20),
    "dissolved_oxygen_saturation": (0, 200),
    "chloride": (0, 20000),
    "nitrate_n": (0, 100),
    "nitrate": (0, 100),
    "phosphate": (0, 20),
    "transparency": (0, 200),
    "conductivity": (0, 30000),
}


def md_table(rel) -> str:
    cols = [d[0] for d in rel.description]
    rows = rel.fetchall()
    plain = {"year", "site_id"}  # identifiers: no thousands separator

    def fmt(v, col):
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:,.2f}".rstrip("0").rstrip(".")
        if isinstance(v, int):
            return str(v) if col in plain else f"{v:,}"
        return str(v)

    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    lines += ["| " + " | ".join(fmt(v, c) for v, c in zip(r, cols)) + " |" for r in rows]
    return "\n".join(lines)


def build_report(db_path=C.DB_PATH) -> str:
    con = duckdb.connect(str(db_path), read_only=True)
    q = con.execute  # each call is fetched in full before the next
    snap = con.execute("SELECT snapshot_date FROM snapshot").fetchall()[0][0]
    chapter = ", ".join(str(s) for s in C.CHAPTER_SITES)
    out = [f"# Data-quality report, snapshot {snap}", ""]
    out += ["Source: Clean Water Hub public API. Personal fields were removed at download.", ""]

    out += ["## Records by protocol", "",
            "A survey is usable when it has a date, is not deleted or archived, and is not a duplicate.", "",
            md_table(q("""
                SELECT protocol, count(*) AS records, sum(usable::int) AS usable,
                       sum((survey_date IS NULL)::int) AS no_date, sum(is_deleted::int) AS deleted,
                       sum(is_archived::int) AS archived, sum((duplicate_of IS NOT NULL)::int) AS duplicates,
                       count(DISTINCT site_id) AS sites,
                       min(survey_date) FILTER (WHERE usable)::varchar AS first,
                       max(survey_date) FILTER (WHERE usable)::varchar AS last
                FROM surveys GROUP BY protocol ORDER BY records DESC""")), ""]

    out += ["## Usable surveys by state (top 12)", "", md_table(q("""
        SELECT coalesce(state, '(none)') AS state, count(*) AS surveys, count(DISTINCT site_id) AS sites
        FROM usable_surveys GROUP BY 1 ORDER BY surveys DESC LIMIT 12""")), ""]

    out += ["## Usable surveys by year", "", md_table(q("""
        PIVOT (SELECT year(survey_date) AS year, protocol FROM usable_surveys)
        ON protocol USING count(*) GROUP BY year ORDER BY year""")), ""]

    out += ["## Water temperature units", "",
            "The Hub stores no unit. Readings up to 32 are taken as Celsius, 41 and up as Fahrenheit (converted); "
            "32 to 41 is ambiguous and left blank.", "",
            md_table(q("""SELECT protocol, temp_rule, count(*) AS readings FROM surveys
                          WHERE temp_rule <> 'missing' GROUP BY ALL ORDER BY protocol, readings DESC""")), ""]

    checks = " UNION ALL ".join(
        f"SELECT '{p}' AS parameter, {lo} AS lo, {hi} AS hi" for p, (lo, hi) in PLAUSIBLE.items())
    out += ["## Chemistry readings", "", "Out of range = outside the plausible band shown.", "", md_table(q(f"""
        WITH b AS ({checks})
        SELECT c.protocol, c.parameter, any_value(c.unit) AS unit, count(*) AS readings,
               round(median(c.value), 2) AS median, round(quantile_cont(c.value, 0.95), 2) AS p95,
               sum((c.value < b.lo OR c.value > b.hi)::int) AS out_of_range
        FROM chemistry c JOIN surveys s USING (survey_uid) LEFT JOIN b USING (parameter)
        WHERE s.usable GROUP BY ALL ORDER BY c.protocol, readings DESC""")), ""]

    out += ["## Species-group fields", "", md_table(q("""
        SELECT t.protocol, t.tolerance, count(DISTINCT t.source_field) AS fields,
               sum(t.present::int) AS times_present,
               round(avg(t.count) FILTER (WHERE t.count > 0), 1) AS mean_count_when_found
        FROM taxa t JOIN surveys s USING (survey_uid) WHERE s.usable GROUP BY ALL ORDER BY 1, 2""")), ""]

    out += ["## Field completeness, biological surveys", "", md_table(q("""
        SELECT protocol, count(*) AS usable,
               round(100 * avg((water_temp_c IS NOT NULL)::int)) AS pct_temp,
               round(100 * avg((flow_rate IS NOT NULL)::int)) AS pct_flow,
               round(100 * avg((weather_today IS NOT NULL OR weather_72h IS NOT NULL)::int)) AS pct_weather,
               round(100 * avg((group_size IS NOT NULL)::int)) AS pct_group_size,
               round(100 * avg((certified IS NOT NULL)::int)) AS pct_certified_field
        FROM usable_surveys WHERE protocol IN ('sos_bio', 'va_rocky', 'va_muddy') GROUP BY 1""")), ""]

    out += [f"## Chapter sites ({chapter})", "", md_table(q(f"""
        SELECT s.site_id, s.protocol, count(*) AS records, sum(s.usable::int) AS usable,
               sum((s.survey_date IS NULL)::int) AS no_date,
               sum((s.duplicate_of IS NOT NULL)::int) AS duplicates,
               min(s.survey_date) FILTER (WHERE s.usable)::varchar AS first,
               max(s.survey_date) FILTER (WHERE s.usable)::varchar AS last
        FROM surveys s WHERE s.is_chapter_site GROUP BY ALL ORDER BY 1, 2""")), ""]
    out += ["Years with no usable chapter survey: " + (con.execute(f"""
        SELECT string_agg(y::varchar, ', ' ORDER BY y) FROM range(
            (SELECT min(year(survey_date)) FROM usable_surveys WHERE is_chapter_site),
            (SELECT max(year(survey_date)) + 1 FROM usable_surveys WHERE is_chapter_site)) t(y)
        WHERE y NOT IN (SELECT year(survey_date) FROM usable_surveys WHERE is_chapter_site)""").fetchall()[0][0] or "none"), ""]

    out += ["## Sites nearest the chapter sites (within 25 km)", "",
            "Candidates for upstream and downstream comparison in phase 2.", "", md_table(q("""
        WITH c AS (SELECT lat, lon FROM sites WHERE site_id = 467), d AS (
        SELECT s.site_id, s.site_name, s.stream, s.state,
               round(6371 * 2 * asin(sqrt(pow(sin(radians(s.lat - c.lat) / 2), 2) +
                     cos(radians(c.lat)) * cos(radians(s.lat)) * pow(sin(radians(s.lon - c.lon) / 2), 2))), 1) AS km,
               (SELECT count(*) FROM usable_surveys u WHERE u.site_id = s.site_id) AS usable_surveys
        FROM sites s, c WHERE s.lat IS NOT NULL AND s.site_id NOT IN (467, 468))
        SELECT * FROM d WHERE km <= 25 ORDER BY km LIMIT 15""")), ""]
    con.close()
    return "\n".join(out)


def main() -> None:
    con = duckdb.connect(str(C.DB_PATH), read_only=True)
    snap = con.execute("SELECT snapshot_date FROM snapshot").fetchall()[0][0]
    con.close()
    C.REPORTS.mkdir(exist_ok=True)
    path = C.REPORTS / f"data-quality-{snap}.md"
    path.write_text(build_report())
    print(path)


if __name__ == "__main__":
    main()
