import json
from pathlib import Path

import pytest

import india_regions as ir

HERE = Path(__file__).parent
CASES = json.loads((HERE / "cases.json").read_text("utf-8"))
GOLDEN = json.loads((HERE / "golden.json").read_text("utf-8"))


@pytest.mark.parametrize("name,want", CASES["normalize_state"])
def test_normalize_state(name, want):
    assert ir.normalize_state(name) == want


@pytest.mark.parametrize("name,want", CASES["match_state"])
def test_match_state(name, want):
    m = ir.match_state(name)
    assert (m.id if m else None) == want


@pytest.mark.parametrize("sid,year,want", CASES["resolve_state_for_year"])
def test_resolve(sid, year, want):
    assert ir.resolve_state_for_year(sid, year) == want


def test_resolve_non_strict_returns_input():
    assert ir.resolve_state_for_year("bombay", 1975, strict=False) == "bombay"


@pytest.mark.parametrize("sid,want", CASES["origin_state"])
def test_origin(sid, want):
    assert ir.origin_state(sid) == want


@pytest.mark.parametrize("sid,year,want", CASES["era_state_id"])
def test_era(sid, year, want):
    assert ir.era_state_id(sid, year) == want


@pytest.mark.parametrize("sid,year,want", CASES["merge_group"])
def test_merge(sid, year, want):
    assert ir.merge_group(sid, year) == want


@pytest.mark.parametrize("name,year,want", CASES["normalize_region"])
def test_normalize_region(name, year, want):
    assert ir.normalize_region(name, year) == want


@pytest.mark.parametrize("name,state,year,want", CASES["match_district"])
def test_match_district(name, state, year, want):
    m = ir.match_district(name, state, year)
    assert (m.id if m else None) == want


def test_match_district_reports_the_old_id():
    m = ir.match_district("Gurgaon", "Haryana", 2020)
    assert m.via == "gurgaon-district" and m.in_year


@pytest.mark.parametrize("did,year,want", CASES["district_for_year"])
def test_district_for_year(did, year, want):
    assert ir.district_for_year(did, year) == want


@pytest.mark.parametrize("code,want", CASES["district_by_lgd"])
def test_lgd(code, want):
    rec = ir.district_by_lgd(code)
    assert (rec["id"] if rec else None) == want


@pytest.mark.parametrize("code,want", CASES["district_by_census2011"])
def test_census(code, want):
    rec = ir.district_by_census2011(code)
    assert (rec["id"] if rec else None) == want


@pytest.mark.parametrize("a,b", CASES["similarity_zero"])
def test_direction_guard(a, b):
    assert ir.similarity(a, b) == 0.0


def test_counts():
    assert len(ir.states_in_year(2026)) == CASES["counts"]["states_in_2026"]
    assert len(ir.states_in_year(1950)) >= CASES["counts"]["states_in_1950_min"]


def test_every_present_state_resolves_back_to_1947():
    for s in ir.STATES:
        if s["last_year"] is None:
            for y in range(1947, 2031):
                got = ir.resolve_state_for_year(s["id"], y)
                assert got and ir.is_valid_in_year(got, y), (s["id"], y, got)


def test_every_district_reference_points_somewhere():
    ids = {p["id"] for p in ir.DISTRICTS}
    for p in ir.DISTRICTS:
        assert ir.get_state(p["state"]), p
        for parent in p["parents"]:
            assert parent in ids, p
    for old, new in ir.DISTRICT_ALIASES.items():
        assert new in ids


def test_golden_matches_python():
    """golden.json is generated from this package (scripts/make_golden.py) and
    replayed by the JS tests; it must still describe the Python behaviour."""
    for (sid, year), want in zip(GOLDEN["resolve_keys"], GOLDEN["resolve"]):
        assert ir.resolve_state_for_year(sid, year) == want
    for row in GOLDEN["match"]:
        m = ir.match_district(row["name"], row["state"], row["year"])
        got = [m.id, m.score, m.method, m.via] if m else None
        assert got == row["want"], row
    for row in GOLDEN["similarity"]:
        assert ir.similarity(row[0], row[1]) == row[2]
