"""Pull every Clean Water Hub protocol into a dated raw snapshot.

Each record is written as one JSON line to data/raw/<date>/<protocol>.jsonl.gz.
Personal fields (emails, login history, phone numbers) are removed before
anything is written to disk.

Usage: python -m iwla_river.pull [--only biological,chemical] [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import time
from pathlib import Path

import requests

from .config import RAW

API = "https://api.cleanwaterhub.org/v1/data"
PAGE_SIZE = 500  # the API caps pages at 500 records
PROTOCOLS = [
    "biological",
    "chemical",
    "protocol_vasos_rocky_bottom",
    "protocol_vasos_muddy_bottom",
    "protocol_saltwatch",
    "protocol_nitratewatch",
]

# Keys dropped wherever they appear, at any depth.
PII_KEYS = {
    "created_by",
    "last_modified_by",
    "email",
    "contact_telephone_or_email",
    "legacy_username",
    "current_login_at",
    "last_login_at",
    "login_count",
    "picture",
}


def strip_pii(obj):
    """Return a copy of obj with personal fields removed."""
    if isinstance(obj, dict):
        return {k: strip_pii(v) for k, v in obj.items() if k not in PII_KEYS}
    if isinstance(obj, list):
        return [strip_pii(v) for v in obj]
    return obj


def slim_organizations(orgs):
    """Keep only id and name fields of embedded organizations."""
    out = []
    for o in orgs or []:
        props = o.get("properties", o) if isinstance(o, dict) else {}
        out.append({k: v for k, v in props.items() if k == "id" or "name" in k})
    return out


def flatten(feature: dict) -> dict:
    """One record = the feature's properties plus its geometry, PII removed."""
    rec = dict(feature.get("properties") or {})
    if feature.get("geometry"):
        rec["_geometry"] = feature["geometry"]
    if "organizations" in rec:
        rec["organizations"] = slim_organizations(rec["organizations"])
    site = rec.get("site")
    if isinstance(site, dict) and isinstance(site.get("properties"), dict):
        site["properties"]["organizations"] = slim_organizations(
            site["properties"].get("organizations")
        )
    return strip_pii(rec)


def get_page(session: requests.Session, path: str, page: int, tries: int = 5) -> dict:
    q = json.dumps({"order_by": [{"field": "id", "direction": "asc"}]})
    params = {"results_per_page": PAGE_SIZE, "page": page, "q": q}
    for attempt in range(tries):
        try:
            r = session.get(f"{API}/{path}", params=params, timeout=120)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt * 3)
    raise RuntimeError("unreachable")


def pull_protocol(session, path: str, out_dir: Path) -> dict:
    out = out_dir / f"{path}.jsonl.gz"
    tmp = out.with_suffix(".tmp")
    first = get_page(session, path, 1)
    total, pages = first["properties"]["num_results"], first["properties"]["total_pages"]
    n = 0
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for page in range(1, pages + 1):
            data = first if page == 1 else get_page(session, path, page)
            for feat in data.get("features", []):
                f.write(json.dumps(flatten(feat), ensure_ascii=False) + "\n")
                n += 1
            print(f"  {path}: page {page}/{pages} ({n}/{total})", flush=True)
            time.sleep(0.5)  # be gentle with a volunteer-run service
    tmp.rename(out)
    return {"protocol": path, "reported": total, "written": n}


def pull_parameters(session, out_dir: Path) -> int:
    r = session.get(f"{API}/parameter", params={"results_per_page": 250}, timeout=60)
    r.raise_for_status()
    feats = [strip_pii(f.get("properties", {})) for f in r.json().get("features", [])]
    (out_dir / "parameter.json").write_text(json.dumps(feats, indent=1, ensure_ascii=False))
    return len(feats)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated protocols to pull")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="snapshot folder name")
    args = ap.parse_args(argv)
    protocols = args.only.split(",") if args.only else PROTOCOLS
    out_dir = RAW / args.date
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    with requests.Session() as s:
        s.headers["User-Agent"] = "iwla-river research pull (read-only)"
        manifest["parameters"] = pull_parameters(s, out_dir)
        for p in protocols:
            if (out_dir / f"{p}.jsonl.gz").exists():
                print(f"{p}: already in snapshot, skipped")
                continue
            print(f"{p}: pulling")
            manifest[p] = pull_protocol(s, p, out_dir)
            manifest_path.write_text(json.dumps(manifest, indent=1))
    manifest["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    manifest_path.write_text(json.dumps(manifest, indent=1))
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
