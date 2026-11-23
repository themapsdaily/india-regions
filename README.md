# india-regions

Indian data is full of state and district names that don't line up. "Orissa" in one table and "Odisha" in the next. "Gurgaon" in 2014 and "Gurugram" in 2020. "Telengana", "Chattisgarh", "Ladakh @", "Delhi (NCT)". Telangana figures that were part of Andhra Pradesh until 2014. A district called "Aurangabad" in two different states.

`india-regions` sorts this out in Python and JavaScript, with no dependencies:

- **Which state or district existed in which year.** States and UTs from 1947, including princely states and provinces. Districts from 1961.
- **Names to ids.** A label from any source, including the typos publishers really make, becomes one stable id.
- **The right unit for any year.** "Uttarakhand" in 1995 becomes Uttar Pradesh. "Allahabad" in 2020 becomes Prayagraj.
- **Codes.** LGD and Census 2011 district codes, plus short state codes such as `UP`, `TN` and `OD`.

```
pip install india-regions
npm install india-regions
```

## States

```python
from india_regions import normalize_state, normalize_region, resolve_state_for_year, match_state

normalize_state("ODISHA #")             # 'odisha'   (footnote marks dropped)
normalize_state("Telengana")            # 'telangana' (known typo)
normalize_state("UP")                   # 'uttar-pradesh'

normalize_region("Orissa", 1998)        # 'orissa'    the id that year
normalize_region("Uttarakhand", 1995)   # 'uttar-pradesh' (two hops: Uttaranchal, then UP)
resolve_state_for_year("telangana", 1950)  # 'hyderabad-state'
resolve_state_for_year("dnh", 2021)        # 'dnhdd'   (merged in 2020)

match_state("Utter Pradesh")            # Match(id='uttar-pradesh', score=0.9091, method='fuzzy', ...)
```

Normalising answers *which territory is this?* Historical spellings map to today's id, so "Orissa" gives `odisha`. Resolving answers *what was it called in year Y?* and walks back to `orissa` for 1998. Because the two steps are separate, one table works for data from any year.

Other helpers:
- `origin_state("telangana")` gives `andhra-pradesh`: the state it was carved out of.
- `era_state_id("keralam", 2018)` gives `kerala`: renames only, it never folds a split back into its parent.
- `merge_group("dnh", 2021)` gives `dnhdd`: tells you two values must be combined into one. Whether you sum them or weight them is up to you.

## Districts

```python
from india_regions import match_district, district_candidates, district_for_year, district_by_lgd

match_district("Gurgaon", "Haryana", 2020)
# Match(id='gurugram-district', name='Gurugram', score=1.0, method='exact', state='haryana', in_year=True, via='gurgaon-district')

match_district("East Medinipur", "WB")      # 'purba-medinipur-district' (Purba = East)
match_district("Thoothukudi", "Tamil Nadu") # 'thoothukkudi-district'   (LGD spelling)
match_district("Mahabubnagar", "Telangana", 2012)  # found under Andhra Pradesh, where it was in 2012

match_district("Aurangabad")                # None: there's one in Bihar and one in Maharashtra
district_candidates("Aurangabad")           # both, ranked

district_for_year("hapur-district", 2005)   # ['ghaziabad-district'] (Hapur was carved out of it in 2011)
district_by_lgd(501)                        # Adilabad's record
```

How matching works:
1. Folding: ASCII only, no brackets, no "district". Uttar/Dakshin/Purba/Paschim count as North/South/East/West.
2. Exact match against every name and old id a district has had.
3. Spelling fold: aa/a, ee/i, oo/u, w/v, doubled letters.
4. Fuzzy score, 0.85 cutoff by default.

A guard stops the classic false matches. "Garo Hills" never matches "West Garo Hills", and "Bangalore Urban" never matches "Bangalore Rural". When two districts fit equally well, `match_district` returns `None` rather than guessing.

JavaScript uses the same names in camelCase (`matchDistrict`, `resolveStateForYear`, ...). It reads the same data and gives the same answers, fuzzy scores included. CI checks this on every change.

## Data

| File | What's in it |
|---|---|
| `states.json` | 83 states, UTs, provinces and princely units with the years they existed, the parent chain, renames, merges and 87 name aliases |
| `districts.json` | 959 districts across 1,149 periods (a district that moved state or was renamed has one period per spell), with LGD and Census 2011 codes, where each period came from and how it ended, and 809 dated change events with source links |

Rules the data follows:
- A change counts from the calendar year it takes effect.
- A rename gets a new id (`orissa` becomes `odisha`, `gurgaon-district` becomes `gurugram-district`).
- In a split, the parent keeps its id.
- A district that changes state keeps its id.

`last_year: null` means the unit still exists.

The data comes from TheMapsDaily's region tables, built from Census reports, LGD, state gazettes and the dated sources listed for each event. It's rebuilt with `scripts/export_from_tmd.py`, which refuses to write if any check fails.

**Not included:** map boundaries. Bring your own, and check how a boundary file draws India's border before you publish a map.

## Licence

Code: MIT. Data: CC BY 4.0. Credit "TheMapsDaily (themapsdaily.com)" when you publish anything made with it. See `DATA_LICENSE.md`.

Found a district we've got wrong, or a spelling we don't catch? Open an issue with the source.
