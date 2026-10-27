"""Project settings shared by the pull, clean and report steps."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CLEAN = DATA / "clean"
DB_PATH = DATA / "river.duckdb"
REPORTS = ROOT / "reports"
TAXA_MAP = Path(__file__).resolve().parent / "taxa_map.csv"

# Sites the Rockville Chapter monitors on Great Seneca Creek.
CHAPTER_SITES = {467: "IWLA-R Site 1 (GRESENCRE7.6)", 468: "IWLA-R Site 2 (GRESENCRE7.52)"}

SHORT = {
    "biological": "sos_bio",
    "chemical": "sos_chem",
    "protocol_vasos_rocky_bottom": "va_rocky",
    "protocol_vasos_muddy_bottom": "va_muddy",
    "protocol_saltwatch": "salt",
    "protocol_nitratewatch": "nitrate",
}

# Chemistry fields per protocol, with the unit shown on IWLA's data sheets.
CHEM_FIELDS = {
    "chloride": "mg/L",
    "conductivity": "uS/cm",
    "dissolved_oxygen": "mg/L",
    "dissolved_oxygen_saturation": "%",
    "nitrate_n": "mg/L",
    "nitrate": "mg/L",
    "ph_units": "pH",
    "phosphate": "mg/L",
    "transparency": "cm",
    "quantab_unit_reading": "Quantab units",
    "air_temperature": "raw",
}

# Free-text fields kept apart in survey_notes (they may hold names; never leave data/).
NOTE_FIELDS = [
    "comments", "notes", "sampling_notes", "description", "potential_threats",
    "litter_description", "other_subsurface_organisms_explanation", "status_notes",
    "admin_notes", "ecological_conditions_notes",
]

# Fields dropped from the clean tables (people's names, bookkeeping).
DROP_FIELDS = {
    "other_monitors", "group_name", "name", "creator_id", "last_modified_by_id",
    "site", "organizations", "related_data", "is_read", "image_link", "_geometry",
    "x1", "x2", "y1", "y2",
}
