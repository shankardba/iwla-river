"""Turn a raw snapshot into tidy tables in data/river.duckdb.

Tables
  sites          one row per monitoring site (location, stream, state)
  surveys        one row per survey, every protocol (date, flow, weather, temperature, flags)
  taxa           one row per species group counted in a survey (long format)
  bio_scores     the scores each biological protocol computes
  chemistry      one row per chemical reading (long format)
  habitat        one row per habitat or land-use item ticked or measured (long format)
  survey_notes   free-text fields, kept apart because they can hold names

Usage: python -m iwla_river.clean [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd

from . import config as C

META_FIELDS = {
    "id", "site_id", "survey_date", "survey_start_time", "survey_end_time", "flow_rate",
    "weather_conditions_today", "weather_conditions_yesterday",
    "weather_conditions_day_before_yesterday", "weather_last_72_hours", "water_temperature",
    "number_of_people_in_group", "certified_monitor", "has_been_deleted", "has_been_archived",
    "is_admin_archive", "is_flagged", "is_approved", "is_public", "created_on", "modified_on",
    "sample_type", "status", "status_is_shared", "water_source", "most_recent_rainfall",
    "percipitation_24_hours", "sample_number", "kit_lot_number", "kit_expiration_date", "huc_8",
}
SCORE_FIELDS = {
    "sensitive_score", "less_sensitive_score", "tolerant_score", "multi_metric_score",
    "ecological_conditions", "total_organisms", "total_other_subsurface_organisms",
    "total_score", "metric_1", "metric_2", "metric_3", "metric_4", "metric_5", "metric_6",
}
SOS_GROUPS = ("less_sensitive_", "sensitive_", "tolerant_")  # longest prefix first


# ---------- small helpers ----------

def latest_snapshot() -> Path:
    snaps = sorted(p for p in C.RAW.iterdir() if p.is_dir() and (p / "manifest.json").exists())
    if not snaps:
        raise SystemExit("No snapshot in data/raw. Run python -m iwla_river.pull first.")
    return snaps[-1]


def read_jsonl(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def num(v):
    """Float or None; the API sends numbers, numeric strings, '' and None."""
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None  # drop NaN


def text(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in {"none", "null", "nan"} else None


def date_of(v):
    s = text(v)
    return s[:10] if s and len(s) >= 10 and s[4] == "-" else None


def water_temp_c(raw):
    """Return (celsius, rule). The Hub has no unit field and volunteers mix C and F.

    <= 32: Celsius. >= 41: Fahrenheit, converted. 32-41: ambiguous (cold F or hot C).
    Below -1 C or above 38 C after conversion: implausible.
    """
    x = num(raw)
    if x is None:
        return None, "missing"
    if x <= 32:
        c, rule = x, "celsius"
    elif x >= 41:
        c, rule = (x - 32) * 5 / 9, "fahrenheit_converted"
    else:
        return None, "ambiguous"
    if c < -1 or c > 38:
        return None, "implausible"
    return round(c, 2), rule


def load_taxa_map() -> dict[str, dict]:
    with open(C.TAXA_MAP, newline="") as f:
        return {r["source_field"]: r for r in csv.DictReader(f)}


# ---------- per-record split ----------

def split_record(proto: str, rec: dict, taxa_map: dict, out: dict) -> None:
    short = C.SHORT[proto]
    uid = f"{short}:{rec['id']}"

    temp_c, temp_rule = water_temp_c(rec.get("water_temperature"))
    certified = text(rec.get("certified_monitor"))
    out["surveys"].append({
        "survey_uid": uid,
        "protocol": short,
        "record_id": rec["id"],
        "site_id": rec.get("site_id"),
        "survey_date": date_of(rec.get("survey_date")) or date_of(rec.get("survey_start_time")),
        "start_time": text(rec.get("survey_start_time")),
        "end_time": text(rec.get("survey_end_time")),
        "flow_rate": text(rec.get("flow_rate")),
        "weather_today": text(rec.get("weather_conditions_today")),
        "weather_yesterday": text(rec.get("weather_conditions_yesterday")),
        "weather_2_days_ago": text(rec.get("weather_conditions_day_before_yesterday")),
        "weather_72h": text(rec.get("weather_last_72_hours")),
        "recent_rainfall": text(rec.get("most_recent_rainfall")),
        "water_source": text(rec.get("water_source")),
        "sample_type": text(rec.get("sample_type")),
        "water_temp_raw": num(rec.get("water_temperature")),
        "water_temp_c": temp_c,
        "temp_rule": temp_rule,
        "group_size": (num(rec.get("number_of_people_in_group")) or None),
        "certified": None if certified is None else certified.lower() not in {"false", "no", "0"},
        "is_deleted": rec.get("has_been_deleted") is True,
        "is_archived": rec.get("has_been_archived") is True,
        "is_admin_archive": rec.get("is_admin_archive") is True,
        "is_flagged": rec.get("is_flagged") is True,
        "is_approved": rec.get("is_approved") is True,
        "is_public": rec.get("is_public") is not False,
        "created_on": text(rec.get("created_on")),
        "modified_on": text(rec.get("modified_on")),
    })

    # Site, from the copy embedded in each record.
    site = rec.get("site")
    if isinstance(site, dict) and site.get("id") is not None:
        sp = site.get("properties") or {}
        coords = (site.get("geometry") or {}).get("coordinates") or [None, None]
        out["sites"][site["id"]] = {
            "site_id": site["id"],
            "site_name": text(sp.get("site_name")),
            "stream": text(sp.get("name_of_stream")),
            "city": text(sp.get("city")),
            "state": text(sp.get("state")),
            "lon": num(coords[0]),
            "lat": num(coords[1]),
            "water_source": text(sp.get("water_source")),
            "is_public": sp.get("is_public") is not False,
            "description": text(sp.get("description")),
        }

    scores = {"survey_uid": uid, "protocol": short}
    taxa_seen = set()
    for key, val in rec.items():
        if key in C.DROP_FIELDS or key in META_FIELDS or key == "water_temperature":
            continue
        if key in C.NOTE_FIELDS:
            t = text(val)
            if t:
                out["notes"].append({"survey_uid": uid, "field": key, "text": t})
            continue
        if key in SCORE_FIELDS:
            scores[key] = num(val) if key != "ecological_conditions" else text(val)
            continue
        if key in C.CHEM_FIELDS:
            x = num(val)
            if x is not None:
                out["chemistry"].append({"survey_uid": uid, "protocol": short, "parameter": key,
                                         "value": x, "unit": C.CHEM_FIELDS[key]})
            continue

        # Species groups. SOS biological: <group>_<taxon> and <group>_<taxon>_is_present.
        base = key.removesuffix("_is_present")
        stem = base
        for g in SOS_GROUPS:
            if base.startswith(g) and proto == "biological":
                stem = base[len(g):]
                break
        if stem in taxa_map and (proto in ("biological",) or proto.startswith("protocol_vasos")):
            if stem in taxa_seen:
                continue
            taxa_seen.add(stem)
            prefix = base[: len(base) - len(stem)]
            count = num(rec.get(prefix + stem))
            present = rec.get(prefix + stem + "_is_present")
            present = bool(present) if present is not None else (count or 0) > 0
            m = taxa_map[stem]
            out["taxa"].append({
                "survey_uid": uid, "protocol": short, "source_field": stem,
                "taxon": m["taxon"], "taxon_group": m["taxon_group"], "tolerance": m["tolerance"],
                "count": count, "present": present or (count or 0) > 0,
            })
            continue

        # Everything else is habitat or land use: ticked boxes, percentages, measures, words.
        item = key.removesuffix("_is_checked")
        if isinstance(val, bool):
            if val:
                out["habitat"].append({"survey_uid": uid, "item": item, "value_num": 1.0, "value_text": None})
        elif num(val) is not None:
            out["habitat"].append({"survey_uid": uid, "item": item, "value_num": num(val), "value_text": None})
        elif text(val):
            out["habitat"].append({"survey_uid": uid, "item": item, "value_num": None, "value_text": text(val)})

    if len(scores) > 2:
        out["bio_scores"].append(scores)


# ---------- duplicates ----------

def mark_duplicates(surveys: pd.DataFrame, taxa: pd.DataFrame, chem: pd.DataFrame) -> pd.DataFrame:
    """Same protocol, site and date with identical counts or readings = duplicate of the lowest id."""
    sig_parts = []
    if not taxa.empty:
        t = taxa.sort_values(["survey_uid", "source_field"])
        sig_parts.append(t.assign(s=t.source_field + "=" + t["count"].map(repr))
                         .groupby("survey_uid").s.agg("|".join))
    if not chem.empty:
        c = chem.sort_values(["survey_uid", "parameter"])
        sig_parts.append(c.assign(s=c.parameter + "=" + c.value.map(repr))
                         .groupby("survey_uid").s.agg("|".join))
    sig = pd.concat(sig_parts).groupby(level=0).agg("|".join) if sig_parts else pd.Series(dtype=str)
    s = surveys.copy()
    s["content_sig"] = s.survey_uid.map(sig).fillna("")
    s["content_sig"] = s.content_sig.map(lambda x: hashlib.sha1(x.encode()).hexdigest()[:12] if x else None)
    s["duplicate_of"] = None
    keyed = s[s.survey_date.notna() & s.content_sig.notna() & ~s.is_deleted]
    for _, grp in keyed.groupby(["protocol", "site_id", "survey_date", "content_sig"]):
        if len(grp) > 1:
            keep = grp.sort_values("record_id").survey_uid.iloc[0]
            s.loc[grp.index[grp.survey_uid != keep], "duplicate_of"] = keep
    return s


# ---------- build ----------

def build(snapshot: Path, db_path: Path = C.DB_PATH) -> dict:
    taxa_map = load_taxa_map()
    out = {k: [] for k in ("surveys", "taxa", "bio_scores", "chemistry", "habitat", "notes")}
    out["sites"] = {}
    for proto in C.SHORT:
        f = snapshot / f"{proto}.jsonl.gz"
        if not f.exists():
            print(f"{proto}: not in snapshot, skipped")
            continue
        for rec in read_jsonl(f):
            split_record(proto, rec, taxa_map, out)

    # Fixed columns so a table exists (empty) even when a protocol is missing.
    cols = {
        "taxa": ["survey_uid", "protocol", "source_field", "taxon", "taxon_group", "tolerance", "count", "present"],
        "bio_scores": ["survey_uid", "protocol", *sorted(SCORE_FIELDS)],
        "chemistry": ["survey_uid", "protocol", "parameter", "value", "unit"],
        "habitat": ["survey_uid", "item", "value_num", "value_text"],
        "survey_notes": ["survey_uid", "field", "text"],
    }
    frames = {
        "sites": pd.DataFrame(list(out["sites"].values())),
        "surveys": pd.DataFrame(out["surveys"]),
        "taxa": pd.DataFrame(out["taxa"], columns=cols["taxa"]),
        "bio_scores": pd.DataFrame(out["bio_scores"], columns=cols["bio_scores"]),
        "chemistry": pd.DataFrame(out["chemistry"], columns=cols["chemistry"]).astype({"value": "float64"}),
        "habitat": pd.DataFrame(out["habitat"], columns=cols["habitat"]),
        "survey_notes": pd.DataFrame(out["notes"], columns=cols["survey_notes"]),
    }
    frames["surveys"] = mark_duplicates(frames["surveys"], frames["taxa"], frames["chemistry"])
    s = frames["surveys"]
    # Dates before the program began (1969) or after the snapshot are typing errors.
    parsed = pd.to_datetime(s.survey_date, errors="coerce", format="%Y-%m-%d")
    s["date_invalid"] = s.survey_date.notna() & (
        parsed.isna() | (parsed < "1969-01-01") | (parsed > pd.Timestamp(snapshot.name))
    )
    s["survey_date"] = parsed.where(~s.date_invalid).dt.date
    s["usable"] = s.survey_date.notna() & ~s.is_deleted & ~s.is_archived & s.duplicate_of.isna()
    s["site_id"] = s.site_id.astype("Int64")
    s["is_chapter_site"] = s.site_id.isin(list(C.CHAPTER_SITES))
    frames["sites"]["site_id"] = frames["sites"].site_id.astype("Int64")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    for name, df in frames.items():
        con.register("df", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
        con.unregister("df")
    con.execute(f"CREATE TABLE snapshot AS SELECT '{snapshot.name}' AS snapshot_date, now() AS built_at")
    con.execute("""
        CREATE VIEW usable_surveys AS
        SELECT s.*, st.site_name, st.stream, st.state, st.lat, st.lon
        FROM surveys s LEFT JOIN sites st USING (site_id) WHERE s.usable
    """)
    C.CLEAN.mkdir(parents=True, exist_ok=True)
    for name in frames:
        con.execute(f"COPY {name} TO '{C.CLEAN / (name + '.parquet')}' (FORMAT parquet)")
    con.close()
    tmp.replace(db_path)
    counts = {k: len(v) for k, v in frames.items()}
    print(json.dumps({"snapshot": snapshot.name, **counts}, indent=1))
    return counts


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="snapshot folder (default: latest)")
    args = ap.parse_args(argv)
    build(C.RAW / args.date if args.date else latest_snapshot())


if __name__ == "__main__":
    main()
