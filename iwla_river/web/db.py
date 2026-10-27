"""Read-only access to data/river.duckdb for the findings, with shared lookups cached."""

from __future__ import annotations

import datetime as dt

import duckdb

from .. import config as C

LABEL = {467: "Site 1", 468: "Site 2"}
PROTO = {"sos_bio": "SOS Biological", "va_rocky": "VA SOS rocky bottom", "va_muddy": "VA SOS muddy bottom",
         "sos_chem": "SOS Chemical", "salt": "Salt Watch", "nitrate": "Nitrate Watch"}
CHAPTER = ",".join(str(s) for s in C.CHAPTER_SITES)
CHEM = ",".join(str(s) for s in C.CHAPTER_CHEM_SITES)


def _plain(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()[:10]
    if hasattr(v, "item"):  # numpy scalars
        return v.item()
    return v


class DB:
    def __init__(self, path=C.DB_PATH):
        self.con = duckdb.connect(str(path), read_only=True)
        self._memo = {}

    def rows(self, sql: str) -> list[dict]:
        cur = self.con.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, map(_plain, r))) for r in cur.fetchall()]

    def one(self, sql: str):
        r = self.con.execute(sql).fetchall()
        return _plain(r[0][0]) if r else None

    def has(self, table: str) -> bool:
        return bool(self.one(f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{table}'"))

    def memo(self, key: str, fn):
        if key not in self._memo:
            self._memo[key] = fn()
        return self._memo[key]

    # ---- shared lookups ----
    def snapshot(self) -> str:
        return self.memo("snapshot", lambda: self.one("SELECT snapshot_date FROM snapshot"))

    def sos(self) -> list[dict]:
        """Chapter SOS Biological surveys with sub-scores."""
        return self.memo("sos", lambda: self.rows(f"""
            SELECT s.site_id, s.survey_date AS date, b.sensitive_score AS sens,
                   coalesce(b.less_sensitive_score, 0) AS less, coalesce(b.tolerant_score, 0) AS tol,
                   b.sensitive_score + coalesce(b.less_sensitive_score, 0) + coalesce(b.tolerant_score, 0) AS total
            FROM usable_surveys s JOIN bio_scores b USING (survey_uid)
            WHERE s.protocol = 'sos_bio' AND s.site_id IN ({CHAPTER}) AND b.sensitive_score IS NOT NULL
            ORDER BY date, site_id"""))

    def va(self) -> list[dict]:
        return self.memo("va", lambda: self.rows(f"""
            SELECT s.site_id, s.survey_date AS date, b.multi_metric_score AS mms, b.ecological_conditions AS cond
            FROM usable_surveys s JOIN bio_scores b USING (survey_uid)
            WHERE s.protocol IN ('va_rocky', 'va_muddy') AND s.site_id IN ({CHAPTER}) ORDER BY date"""))

    def trends(self) -> list[dict]:
        return self.memo("trends", lambda: self.rows("SELECT * FROM site_trends") if self.has("site_trends") else [])

    def resid_trends(self) -> list[dict]:
        return self.memo("rt", lambda: self.rows("SELECT * FROM residual_trends") if self.has("residual_trends") else [])

    def context(self, site_id: int) -> dict:
        r = self.rows(f"SELECT * FROM site_context WHERE site_id = {site_id}") if self.has("site_context") else []
        return r[0] if r else {}


# ---------- formatting ----------

def fmt(n) -> str:
    return "" if n is None else f"{n:,.0f}" if isinstance(n, (int, float)) else str(n)


def pct(v) -> str:
    return f"{round(100 * v)}%"


def pfmt(p) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}" if p < 0.1 else f"p = {p:.2f}"


def mean(a) -> float:
    a = list(a)
    return sum(a) / len(a) if a else float("nan")


def year(d: str) -> int:
    return int(str(d)[:4])


def season(d: str) -> str:
    m = int(str(d)[5:7])
    return "Spring" if 3 <= m <= 6 else "Summer" if 7 <= m <= 9 else "Fall"


def verdict_pill(v: str) -> dict:
    return {"pill": "good" if v == "improving" else "bad" if v == "declining" else "neutral", "text": v}
