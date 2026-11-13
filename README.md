# civic-address-qa

![tests](https://github.com/YaniceZ/civic-address-qa/actions/workflows/ci.yml/badge.svg)

Municipalities publish civic address points in their own schemas. This tool downloads them from public ArcGIS REST services, maps each source onto one standard schema, and runs data quality checks before the output is used.

```
civic-qa run thunder_bay west_kelowna --out data
```

```
thunder_bay: 45,102 rows, all checks passed
  parser matched the source's split fields on 99.95% of rows
west_kelowna: 18,255 rows, all checks passed
```

Each run writes a GeoPackage, a JSON report and a Markdown report per source.

## What it does

1. **Download.** Pages through a FeatureServer layer ordered by object ID, retries failed requests, treats ArcGIS's "HTTP 200 with an error body" as a failure, and checks the row count against the count the server reports. A short download raises instead of returning a partial layer.
2. **Standardize.** A YAML entry per source says how to read it. Some layers already split the address into fields (`mode: components`); others publish one address string that has to be parsed (`mode: parse`). Both end up in the same schema: house number, suffix, unit, street name, street type (Canada Post abbreviations), direction, full address, city, province.
3. **Check.** Missing house numbers or street names, unparsed addresses, street types outside the known list, duplicate addresses, empty geometries and points outside Canada. Each check has a threshold; a source that crosses one is flagged in the report. A layer with no rows is an error, not a check result, because an empty output usually means something upstream failed silently.
4. **Measure the parser.** When a source publishes both a full address and its split fields, the report compares the parser's output with the source's own fields.

## Results on real data

Run on 12 November 2026.

| Source | Rows | Mode | Notes |
| --- | ---: | --- | --- |
| City of Thunder Bay, ON | 45,102 | parse | Parser matches the source's own number, name and type on 99.95% of 45,100 non-blank addresses |
| City of West Kelowna, BC | 18,255 | components | 81 points (0.44%) had street types missing from the first version of the type list |

What the checks turned up while building this:

- **Thunder Bay writes hyphenated addresses as number-unit** (`276-4 CARIBOU CRES` is number 276, unit 4), the opposite of the usual Canada Post order. Each source can now set `hyphen_order`.
- **The remaining 22 parser mismatches are mostly in the source itself.** 14 are records where the full address and the house-number field disagree (for example `122 ALBANY ST` with a house number of 125), and 7 have no house number at all. One is a genuine parser miss.
- **West Kelowna uses `QUAY`, `COVE`, `KEY` and `LANDG`**, which were not in the first street-type list. The unknown-type check listed them, and they are now mapped.
- **Numbers arrive as floats.** The first accuracy run reported 0% on house numbers because `1885.0` was being compared with `1885`. The comparison now normalizes numeric fields.

## Usage

```
python -m venv .venv
.venv\Scripts\activate            # source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"

civic-qa list
civic-qa run thunder_bay --out data
civic-qa run thunder_bay west_kelowna --out data --strict   # exit code 1 if any check is flagged
pytest
```

To add a source, add an entry to `src/civic_qa/sources.yaml`:

```yaml
my_city:
  name: My City civic addresses
  province: BC
  url: https://example.ca/arcgis/rest/services/Addresses/FeatureServer/0
  mode: components
  city: MY CITY
  fields:
    house_number: CIVIC_NUM
    unit: UNIT
    street_name: ST_NAME
    street_type: ST_TYPE
```

## Layout

```
src/civic_qa/
  download.py      paged ArcGIS REST download with retries and a row-count check
  parse.py         rule-based address parser and Canada Post street types
  standardize.py   maps a source onto the standard schema
  qa.py            checks, thresholds and the empty-output guard
  evaluate.py      parser accuracy against a source's own split fields
  pipeline.py      download -> standardize -> check -> write
  cli.py           command line entry point
tests/             unit tests; no network access needed
```

## Limitations

- The parser is rule-based and tuned on the two sources above. Rural route addresses, French street types (`RUE`, `CHEMIN`) and addresses with several units are not handled yet.
- The street-type list is a subset of the Canada Post list.
- Duplicate detection compares the formatted address only. It does not look at distance between points.

## Data

This repository contains code only. Address data is downloaded at run time from each municipality's public service and is not redistributed here. Use of the data is subject to each municipality's open data terms.

## License

MIT
