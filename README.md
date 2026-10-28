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


## Phase 3: expected-score model

```
python -m iwla_river.enrich     # watershed land cover (USGS NLDI + EPA StreamCat) and 7-day rainfall (Open-Meteo); cached in data/cache
python -m iwla_river.model      # train, validate by site, observed minus expected
```

| Table | One row per | Notes |
| --- | --- | --- |
| `site_context` | site | NHDPlus COMID; watershed % paved, urban, forest, crop, hay, wetland; elevation, soils, 1981–2010 climate, road crossings, population |
| `survey_weather` | survey | rain over 1, 3 and 7 days and mean air maximum over 7 days before the survey |
| `expected` | survey and target | observed, expected (from a model that never saw the site), gap, 80% expected range, below/within/above |
| `model_metrics` | target | held-out R² and error, against season-and-form averages |
| `model_importance` | target and input group | drop in held-out R² when the group is scrambled |
| `residual_trends` | site and target | seasonal Kendall test on observed minus expected |

Targets: share of animal groups found that are pollution-sensitive (comparable across forms) and the score as a percentile within its form. Model: gradient-boosted trees (scikit-learn `HistGradientBoostingRegressor`), five folds grouped by site. The year is never an input, so change over time stays in the gap.

## Watersheds

`python -m iwla_river.enrich --stage huc` places every site in its USGS 12-digit hydrologic unit (Watershed Boundary Dataset): one request per one-degree square fetches the simplified boundaries there, and each site is placed by a point-in-polygon test (cached in `data/cache/huc.json`, names in `huc_names.json`). `python -m iwla_river.watersheds` then computes, for every unit at every level (2, 4, 6, 8, 10 and 12 digits): sites and surveys, sensitive share found against expected, the gap and its seasonal Kendall trend, score percentile, paved and forest share, chloride and nitrate. The site's Watershed explorer page zooms through those levels; `docs/data/watersheds.json` holds regions to subbasins and `docs/data/huc4/<code>.json` the smaller units and sites, fetched as you zoom.

## Rivers

`python -m iwla_river.rivers_osm` names the rivers in every subbasin with biological surveys and finds where each one starts
and ends. It reads the OpenStreetMap vector maps (Protomaps `.pmtiles`) that NOMAD keeps on the M4 mini
(`/Volumes/OricoArray/Daemon/library/maps/pmtiles`), joins each river's pieces, follows it past the subbasin edge to its
source and mouth, gets those two elevations from Open-Meteo, and notes what it flows into and which two rivers form it.
Output: `data/cache/rivers_osm/<huc8>.json`; the site packs these into `docs/data/rivers/<huc4>.json`. It is resumable;
subbasins whose state map is not downloaded yet are skipped until it is. Explore draws the rivers with water moving
downstream, marks each source, lists them in the panel, finds them in search, and shows one animated idea per zoom level
(water cycle, rivers joining, source to mouth, land and runoff, life in the riffle) using that unit's numbers.

## The findings site

`python -m iwla_river.site` builds the site into `docs/`, served by GitHub Pages at https://shankardba.github.io/iwla-river/. It is organised as a tool, with a top menu (a full-screen sheet on phones):

| Menu | Page | What it is |
| --- | --- | --- |
| Explore | `index.html` | The workspace: map of where samples are taken (heat, filter by sample type), watershed rings coloured by a chosen measure, and a panel with each watershed's figures against its parent, what is inside it, and each biological site's survey history. Search with `/`. Every view has its own link (`#w<huc>`, `#s<site>@<huc12>`). |
| Findings | `findings.html`, `<section>.html`, `<section>--<finding>.html` | Every result, by section, each with its evidence and method; finding pages have an "In this section" list. |
| Great Seneca Creek | `chapter.html` | The chapter's own sites. |
| Data | `data--*.html` | Data quality, temperature units, sources and methods, downloads. |
| About | `about.html` | How volunteers sample, how to use the tool, sources and privacy. |

Data files for Explore live in `docs/data/` (`watersheds.json`, `huc4/<code>.json` with sites and site histories, `search.json`, `lower48.json`, `watershed_metrics.csv`).

Code lives in `iwla_river/web/`:

| Path | Role |
| --- | --- |
| `registry.py` | sections, findings and the content blocks a finding returns (`text`, `chart`, `table`, `links`) |
| `findings/*.py` | one module per section; each finding is one decorated function |
| `db.py` | read-only database access and shared lookups |
| `assets/charts.js` | chart library: `time`, `bars`, `stack`, `hbars`, `strip`, `heat`, `dotrank`, drawn from specs |
| `templates/` | page layout (Jinja2) |
| `build.py` | runs every finding and writes the pages |

### Adding a finding

Write one function in the section's module (or a new module under `findings/`; it is picked up automatically):

```python
@finding("chemistry", "chloride-vs-insects", "Salt peaks and sensitive animals", order=30, key=False)
def chloride_vs_insects(db):
    rows = db.rows("SELECT ...")
    if not rows:
        return None                      # left out when its data is missing
    return Page(
        headline="One sentence with the result and its number.",
        status="watch",                  # concern | watch | steady | good | info
        numbers=[("145 mg/L", "winter peak")],
        blocks=[text("..."), chart({"type": "time", ...}, "caption"), table([("Col",), ("Num", 1)], rows),
                links([("road-salt", "why it matters")])])
```

Diagrams: `iwla_river/web/diagrams/` draws static SVG at build time, after Omniscala's figure conventions (shaded forms named by tone, dot-and-leader labels, amber "not to scale" lenses, light and dark palettes in `site.css`). `bugs.py` holds field-guide drawings of the animal groups; `plates.py` holds the diagrams, each built from the data it shows. Add one with `diagram(plates.my_plate(...), "caption")` in a finding's blocks.

It gets its own page, appears in its section, the sidebar tree and `findings.json`, and with `key=True` on the overview. A new section is one `section(...)` call. A new chart type is one function in `assets/charts.js`.

## Later phases

4. Language layer: tag free-text notes, read scanned data sheets, answer questions.
5. Dashboard, scheduled refresh on the home server, alerts.
