"""Build src/india_regions/data/*.json from a themapsdaily-data checkout.

    python scripts/export_from_tmd.py ../themapsdaily-data

The data repo is the source of truth; this package is downstream of it. Every
run rewrites both JSON files, so re-run it after the data repo changes and
review the diff. Exits 1 when a check fails.

What leaves the data repo:
  states.json     region validity (which state/UT/province existed in which
                  year, 1947 on), the parent chain, renames, merges, codes and
                  every name/typo alias the pipelines learned.
  districts.json  district periods (1961 on) with LGD and Census 2011 codes,
                  start/end events, spelling aliases, and dated change events
                  with their source URL.

What does not: map geometry, cities, internal notes, and the Wikipedia quotes
(CC BY-SA text; the source URL is kept instead).
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "india_regions" / "data"
STATE_HORIZON = 2027      # the data repo's "still exists" year for states
DISTRICT_HORIZON = 2026   # ... and for districts


def load_regions_module(tmd: Path):
    path = tmd / "sources" / "_shared" / "regions.py"
    spec = importlib.util.spec_from_file_location("tmd_regions", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if not next(iter(r.values()), "").startswith("#")]


def open_end(year: int, horizon: int):
    return None if year >= horizon else year


# Units the map table has no row for yet.
FALLBACK_NAMES = {"nefa": "North-East Frontier Agency", "sikkim-kingdom": "Kingdom of Sikkim"}


def build_states(tmd: Path, rg) -> tuple[dict, list[str]]:
    """Windows come from regions.py, the snapshot of the FK table pipelines
    check against. Drift against state_year.csv (the maps) is a warning: it is
    for the data repo to settle, not for this export."""
    problems: list[str] = []
    rows = read_csv(tmd / "regions" / "state" / "state_year.csv")
    years: dict[str, list[int]] = {}
    latest: dict[str, dict] = {}
    for r in rows:
        sid, y = r["st_id"], int(r["year"])
        years.setdefault(sid, []).append(y)
        if sid not in latest or y >= int(latest[sid]["year"]):
            latest[sid] = r

    # state_year.csv (the maps) and regions.py (the FK snapshot) must agree on
    # every window, or one of them is stale.
    for sid, ys in years.items():
        window = (min(ys), max(ys))
        snap = rg.REGION_VALIDITY.get(sid)
        if snap is None:
            problems.append(f"WARN state_year has {sid}, regions.py does not")
        elif snap != window:
            problems.append(f"WARN {sid}: state_year {window}, regions.py {snap}")
        if len(ys) != window[1] - window[0] + 1:
            problems.append(f"WARN {sid}: gap in state_year years")
    for sid in rg.REGION_VALIDITY:
        if sid not in years and sid not in ("india", "british-raj"):
            problems.append(f"WARN regions.py has {sid}, state_year does not")

    states = []
    for sid, (first, last) in sorted(rg.REGION_VALIDITY.items()):
        if sid in ("india", "british-raj"):
            continue
        r = latest.get(sid, {})
        states.append({
            "id": sid,
            "name": r.get("st_nm") or FALLBACK_NAMES.get(sid, ""),
            "type": r.get("region_type", ""),
            "code": r.get("region_code", "") or None,
            "first_year": first,
            "last_year": open_end(last, STATE_HORIZON),
        })

    out = {
        "states": states,
        "parent": dict(sorted(rg.PARENT.items())),
        "parent_before": {k: {"until": v[0], "parent": v[1]} for k, v in rg.PARENT_BEFORE.items()},
        "renamed_from": dict(rg.RENAMED_FROM),
        "merges": [{
            "into": "dnhdd",
            "members": list(rg.DNHDD_MEMBERS),
            "from_year": rg.DNHDD_FROM_YEAR,
            "population_share_2011": {"dnh": round(rg.DNH_POPULATION_SHARE, 6),
                                      "daman-diu": round(1 - rg.DNH_POPULATION_SHARE, 6)},
        }],
        "aliases": dict(sorted(rg.STATE_ALIASES.items())),
    }
    return out, problems


END_RE = re.compile(r"^(rename|absorb|moved)\s*->\s*(.+)$")


def fold(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("&", "and"))


def lineage(tmd: Path, rg) -> callable:
    """Two states hold the same territory when one is on the other's parent
    chain (telangana/andhra-pradesh, keralam/kerala, dnhdd/dnh)."""
    def chain(sid):
        seen = [sid]
        while sid in rg.PARENT:
            sid = rg.PARENT[sid]
            seen.append(sid)
        return seen
    def related(a, b):
        return a == b or a in chain(b) or b in chain(a)
    return related


def build_districts(tmd: Path, state_ids: set[str], rg) -> tuple[dict, list[str]]:
    problems: list[str] = []
    related = lineage(tmd, rg)
    d = tmd / "regions" / "district"
    raw = read_csv(d / "district_validity_all.csv")
    ids = {r["dt_id"] for r in raw}
    alias_rows = read_csv(d / "district_aliases.csv")
    # a parent may be written in a spelling only the alias table knows
    alias_names = {fold(a["old_dt_id"].removesuffix("-district")): a["dt_id"] for a in alias_rows}

    def parent_ids(r) -> list[str]:
        """Parent names -> the ids of the periods alive the year before this one
        opened, in the same territory. A parent that is the district's own
        earlier period (a state move or rename keeps the name) is dropped."""
        if not r["parent"]:
            return []
        out = []
        start = int(r["first_year"])
        for name in r["parent"].split(";"):
            name = name.strip()
            if fold(name) == fold(r["dt_nm"]):
                continue  # its own earlier period (state move / merger), not a parent
            if name in ids:
                out.append(name)
                continue
            want = {fold(name)}
            if fold(name) in alias_names:
                want.add(fold(alias_names[fold(name)].removesuffix("-district")))
            alive = [q for q in raw if related(q["st_id"], r["st_id"])
                     and int(q["first_year"]) <= start - 1 <= int(q["last_year"])]
            hits = [q for q in alive if fold(q["dt_nm"]) in want
                    or fold(q["dt_id"].removesuffix("-district")) in want]
            hit_ids = sorted({q["dt_id"] for q in hits})
            if len(hit_ids) == 1:
                if hit_ids[0] != r["dt_id"]:
                    out.append(hit_ids[0])
            elif r["dt_id"] in hit_ids:
                pass
            else:
                problems.append(f"WARN {r['dt_id']}: parent {name!r} -> {hit_ids or 'no match'}")
        return out

    periods = []
    for r in raw:
        end = None
        if r["end_event"]:
            m = END_RE.match(r["end_event"].strip())
            if not m:
                problems.append(f"{r['dt_id']}: unparsed end_event {r['end_event']!r}")
            else:
                targets = [t.strip() for t in m.group(2).split(";")]
                end = {"kind": m.group(1), "to": targets, "date": r["end_date"] or None}
                for t in targets:
                    ok = t in state_ids if m.group(1) == "moved" else t in ids
                    if not ok:
                        problems.append(f"{r['dt_id']}: end target {t} unknown")
        if r["st_id"] not in state_ids:
            problems.append(f"{r['dt_id']}: unknown state {r['st_id']}")
        periods.append({
            "id": r["dt_id"],
            "name": r["dt_nm"],
            "state": r["st_id"],
            "first_year": int(r["first_year"]),
            "last_year": open_end(int(r["last_year"]), DISTRICT_HORIZON),
            "status": r["status"],
            "event": r["event"] or None,
            "parents": parent_ids(r),
            "date": r["date"] or None,
            "confidence": r["confidence"] or None,
            "end": end,
            "lgd_code": r["lgd_code"] or None,
            "census2011_code": r["census2011_code"] or None,
        })

    aliases = {}
    for r in alias_rows:
        if r["dt_id"] not in ids:
            problems.append(f"alias {r['old_dt_id']} -> unknown {r['dt_id']}")
        aliases[r["old_dt_id"]] = r["dt_id"]

    events = []
    for r in read_csv(d / "district_events.csv"):
        events.append({
            "year": int(r["year"]),
            "date": r["date"] or None,
            "kind": r["kind"],
            "from": r["from_dt_id"] or None,
            "to": r["to_dt_id"] or None,
            "from_state": r["from_st_id"] or None,
            "to_state": r["to_st_id"] or None,
            "source": r["source"] if r["source"].startswith("http") else None,
            "confidence": r["confidence"] or None,
        })
    return {"periods": periods, "aliases": dict(sorted(aliases.items())), "events": events}, problems


def check_parity(rg) -> list[str]:
    """The package must answer exactly as regions.py does, for every state id,
    every year in the data repo's range, and every alias. Run after writing the
    JSON is too late, so this imports the package against the fresh tables."""
    import importlib
    sys.path.insert(0, str(OUT.parent.parent))
    pkg = importlib.import_module("india_regions._core")
    pkg = importlib.reload(pkg)
    out = []
    for sid in rg.REGION_VALIDITY:
        if sid in ("india", "british-raj"):
            continue
        for y in range(1947, STATE_HORIZON + 1):
            a = rg.resolve_region_for_year(sid, y, strict=True)
            b = pkg.resolve_state_for_year(sid, y, strict=True)
            if a != b:
                out.append(f"resolve {sid} {y}: regions.py {a}, package {b}")
        if rg.origin_region(sid) != pkg.origin_state(sid):
            out.append(f"origin {sid}: {rg.origin_region(sid)} vs {pkg.origin_state(sid)}")
    for key, sid in rg.STATE_ALIASES.items():
        if pkg.normalize_state(key) != sid:
            out.append(f"alias {key!r}: {sid} vs {pkg.normalize_state(key)}")
    return out[:40]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    tmd = Path(sys.argv[1]).resolve()
    rg = load_regions_module(tmd)
    internal = rg.check_snapshot_internally_consistent()
    states, p1 = build_states(tmd, rg)
    state_ids = {s["id"] for s in states["states"]}
    districts, p2 = build_districts(tmd, state_ids, rg)
    problems = internal + p1 + p2
    warns = [p for p in problems if p.startswith("WARN")]
    fails = [p for p in problems if not p.startswith("WARN")]
    for line in warns:
        print(line)
    for line in fails:
        print("FAIL", line)
    print(f"{len(warns)} warning(s), {len(fails)} failure(s)")
    if fails:
        return 1
    stamp = {"version": date.today().isoformat(), "source": "https://themapsdaily.com",
             "licence": "CC-BY-4.0"}
    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in (("states.json", states), ("districts.json", districts)):
        (OUT / name).write_text(json.dumps({**stamp, **body}, ensure_ascii=False, indent=1) + "\n",
                                encoding="utf-8")
    parity = check_parity(rg)
    for line in parity:
        print("FAIL parity", line)
    if parity:
        print("JSON written but does not match regions.py; do not commit it")
        return 1
    print("parity with regions.py: OK")
    print(f"states: {len(states['states'])} units, {len(states['aliases'])} aliases")
    print(f"districts: {len(districts['periods'])} periods, "
          f"{len({p['id'] for p in districts['periods']})} ids, {len(districts['events'])} events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
