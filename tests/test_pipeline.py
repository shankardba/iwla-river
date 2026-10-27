"""Tests for the pull and clean steps, on small made-up records (no network)."""

import gzip
import json

import duckdb

from iwla_river import clean, pull, report


def test_strip_pii_removes_nested_personal_fields():
    feature = {
        "geometry": None,
        "properties": {
            "id": 1,
            "created_by": {"properties": {"email": "someone@example.org"}},
            "contact_telephone_or_email": "555-0100",
            "site": {"id": 9, "properties": {"created_by": {"email": "x@example.org"}, "site_name": "A"}},
            "comments": "fine",
        },
    }
    rec = pull.flatten(feature)
    text = json.dumps(rec)
    assert "example.org" not in text and "555-0100" not in text
    assert rec["site"]["properties"]["site_name"] == "A" and rec["comments"] == "fine"


def test_water_temperature_rule():
    assert clean.water_temp_c(18) == (18, "celsius")
    assert clean.water_temp_c(68) == (20.0, "fahrenheit_converted")
    assert clean.water_temp_c(35) == (None, "ambiguous")
    assert clean.water_temp_c(None) == (None, "missing")
    assert clean.water_temp_c(120) == (None, "implausible")


def site(sid):
    return {"id": sid, "geometry": {"coordinates": [-77.2, 39.1]},
            "properties": {"site_name": f"S{sid}", "name_of_stream": "Test Creek", "state": "MD"}}


def write_snapshot(tmp_path):
    snap = tmp_path / "2026-01-01"
    snap.mkdir()
    (snap / "manifest.json").write_text("{}")
    bio = [
        {"id": 1, "site_id": 467, "site": site(467), "survey_date": "2024-05-26T00:00:00",
         "water_temperature": 70, "sensitive_mayflies": 12, "sensitive_mayflies_is_present": True,
         "tolerant_midge_flies": None, "tolerant_midge_flies_is_present": True,
         "less_sensitive_crayfish_is_present": False, "sensitive_score": 3, "tolerant_score": 1,
         "odor_none_is_checked": True, "riffle_composition_cobbles": 40, "comments": "rain yesterday",
         "certified_monitor": "A Person", "has_been_deleted": None},
        # same content, same day: a duplicate of record 1
        {"id": 2, "site_id": 467, "site": site(467), "survey_date": "2024-05-26T00:00:00",
         "sensitive_mayflies": 12, "sensitive_mayflies_is_present": True,
         "tolerant_midge_flies": None, "tolerant_midge_flies_is_present": True,
         "less_sensitive_crayfish_is_present": False},
        # deleted survey
        {"id": 3, "site_id": 468, "site": site(468), "survey_date": "2023-01-01T00:00:00",
         "has_been_deleted": True},
    ]
    va = [{"id": 10, "site_id": 5, "site": site(5), "survey_date": "2020-04-01T00:00:00",
           "mayflies": 30, "worms": 2, "multi_metric_score": 10, "ecological_conditions": "Acceptable",
           "algae_color_hairy_is_checked": True}]
    chem = [{"id": 20, "site_id": 5, "site": site(5), "survey_date": "2020-04-01T00:00:00",
             "ph_units": 7.2, "chloride": 40, "dissolved_oxygen": None}]
    for name, rows in [("biological", bio), ("protocol_vasos_rocky_bottom", va), ("chemical", chem)]:
        with gzip.open(snap / f"{name}.jsonl.gz", "wt") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
    return snap


def test_build_tables(tmp_path):
    snap = write_snapshot(tmp_path)
    db = tmp_path / "river.duckdb"
    counts = clean.build(snap, db)
    assert counts["surveys"] == 5 and counts["sites"] == 3
    con = duckdb.connect(str(db), read_only=True)
    q = lambda sql: con.execute(sql).fetchall()

    assert q("SELECT survey_uid, usable, duplicate_of FROM surveys ORDER BY survey_uid") == [
        ("sos_bio:1", True, None), ("sos_bio:2", False, "sos_bio:1"), ("sos_bio:3", False, None),
        ("sos_chem:20", True, None), ("va_rocky:10", True, None)]
    assert q("SELECT water_temp_c, temp_rule, certified FROM surveys WHERE survey_uid='sos_bio:1'") == [
        (21.11, "fahrenheit_converted", True)]
    # midges present without a count; crayfish absent; VA fields mapped to the same names
    assert q("""SELECT taxon, tolerance, count, present FROM taxa WHERE survey_uid='sos_bio:1'
                ORDER BY taxon""") == [("crayfish", "less_sensitive", None, False),
                                      ("mayflies", "sensitive", 12.0, True),
                                      ("midges", "tolerant", None, True)]
    assert q("SELECT taxon, count FROM taxa WHERE protocol='va_rocky' ORDER BY taxon") == [
        ("aquatic worms", 2.0), ("mayflies", 30.0)]
    assert q("SELECT parameter, value FROM chemistry ORDER BY parameter") == [("chloride", 40.0), ("ph_units", 7.2)]
    assert q("SELECT item FROM habitat WHERE survey_uid='sos_bio:1' ORDER BY item") == [
        ("odor_none",), ("riffle_composition_cobbles",)]
    assert q("SELECT text FROM survey_notes") == [("rain yesterday",)]
    # names never reach the clean tables
    assert "A Person" not in json.dumps(q("SELECT * FROM surveys"), default=str)
    con.close()

    md = report.build_report(db)
    assert "## Chapter sites" in md and "A Person" not in md and "rain yesterday" not in md


def test_site_builds_with_only_phase_1_tables(tmp_path):
    """Findings whose tables are missing are left out; the rest still build."""
    import json as _json
    from iwla_river.web.build import build
    snap = write_snapshot(tmp_path)
    db = tmp_path / "river.duckdb"
    clean.build(snap, db)
    out = build(db, tmp_path / "site", tmp_path / "body")
    index = _json.loads((out / "findings.json").read_text())
    ids = {f["id"] for f in index["findings"]}
    assert "data-quality" in ids and "expected" not in ids
    home = (out / "index.html").read_text()
    assert "How clean the data is" in home and "A Person" not in home and "rain yesterday" not in home
    for f in index["findings"]:
        assert (out / f["url"]).exists()
