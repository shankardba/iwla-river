# iwla-river

An analysis layer over the Izaak Walton League's Save Our Streams data, built to follow how a stream's ecology changes over time. It starts with the Rockville Chapter's sites on Great Seneca Creek (Germantown, MD).

The data comes from the Clean Water Hub's public read-only API (`api.cleanwaterhub.org/v1`). It is not a documented API, so check with IWLA before running scheduled pulls.

## Phase 1: pull and clean

```
python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt
bin/refresh                 # pull + clean + report (about 45 minutes for every protocol)
```

Or one step at a time:

| Step | Command | Output |
| --- | --- | --- |
| Pull | `python -m iwla_river.pull [--only biological]` | `data/raw/<date>/<protocol>.jsonl.gz`, personal fields removed |
| Clean | `python -m iwla_river.clean [--date <date>]` | `data/river.duckdb` and `data/clean/*.parquet` |
| Report | `python -m iwla_river.report` | `reports/data-quality-<date>.md` |
| Test | `python -m pytest -q` | |

### Tables in `data/river.duckdb`

| Table | One row per | Notes |
| --- | --- | --- |
| `sites` | monitoring site | name, stream, state, lat/lon |
| `surveys` | survey, all protocols | date, flow, weather, water temperature in Celsius, team size, certified flag, `usable`, `duplicate_of` |
| `taxa` | species group counted in a survey | harmonized across SOS and Virginia SOS forms via `iwla_river/taxa_map.csv` |
| `bio_scores` | biological survey | SOS sub-scores and total; Virginia multimetric score and metrics |
| `chemistry` | chemical reading | SOS chemical, Salt Watch, Nitrate Watch |
| `habitat` | habitat or land-use item | ticked boxes, percentages, measures |
| `survey_notes` | free-text field | can hold names: stays in `data/`, never committed |
| `usable_surveys` (view) | usable survey | surveys joined to site details |

### Cleaning rules

- **Usable** = has a date, not deleted or archived, not a duplicate.
- **Duplicate** = same protocol, site and date with identical counts or readings; the lowest record id is kept.
- **Water temperature**: the Hub stores no unit. Up to 32 is Celsius, 41 and up is Fahrenheit and converted, 32 to 41 is left blank as ambiguous.
- **People**: emails, phone numbers and login data are dropped at download; the certified-monitor name becomes a yes/no flag; the other-monitors list is dropped.

## Phase 2: trends and species mix

`python -m iwla_river.analysis` (run after clean; `bin/refresh` does it) adds:

| Table | One row per | Method |
| --- | --- | --- |
| `features` | usable biological survey | score, groups found, sensitive share, mayfly/stonefly/caddisfly (EPT) groups, % EPT and Shannon diversity where counts exist, season |
| `site_trends` | site and measure | seasonal Kendall test on season-year medians, seasonal Sen slope; reported only with at least 10 same-season comparisons |
| `turning_points` | site | strongest shift in the season-adjusted mean, permutation test (999 shuffles) |
| `taxa_by_period` | site, 5-year period, animal group | share of surveys finding the group |
| `baseline_drift` | survey | Jaccard similarity of groups found to the groups common in the site's first five years |

Sites tested: the chapter sites plus every site within 30 km with at least 8 usable biological surveys over 5 or more years.

The findings page (`python -m iwla_river.site`) writes `docs/index.html`, served by GitHub Pages at https://shankardba.github.io/iwla-river/.

## Later phases

3. Expected-score model trained on national data; observed minus expected over time.
4. Language layer: tag free-text notes, read scanned data sheets, answer questions.
5. Dashboard, scheduled refresh on the home server, alerts.
