// node --test tests/  — replays cases.json and golden.json against the JS port.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ir = require("../js/index.js");
const load = (f) => JSON.parse(readFileSync(new URL(f, import.meta.url), "utf8"));
const C = load("./cases.json");
const G = load("./golden.json");

const id = (x) => (x ? x.id : null);

test("normalizeState", () => {
  for (const [name, want] of C.normalize_state) assert.equal(ir.normalizeState(name), want, name);
});
test("matchState", () => {
  for (const [name, want] of C.match_state) assert.equal(id(ir.matchState(name)), want, name);
});
test("resolveStateForYear", () => {
  for (const [sid, y, want] of C.resolve_state_for_year) assert.equal(ir.resolveStateForYear(sid, y), want, `${sid} ${y}`);
  assert.equal(ir.resolveStateForYear("bombay", 1975, { strict: false }), "bombay");
});
test("originState / eraStateId / mergeGroup / normalizeRegion", () => {
  for (const [sid, want] of C.origin_state) assert.equal(ir.originState(sid), want);
  for (const [sid, y, want] of C.era_state_id) assert.equal(ir.eraStateId(sid, y), want);
  for (const [sid, y, want] of C.merge_group) assert.equal(ir.mergeGroup(sid, y), want);
  for (const [n, y, want] of C.normalize_region) assert.equal(ir.normalizeRegion(n, y), want);
});
test("matchDistrict", () => {
  for (const [n, s, y, want] of C.match_district) assert.equal(id(ir.matchDistrict(n, s, y)), want, `${n} ${s} ${y}`);
  const m = ir.matchDistrict("Gurgaon", "Haryana", 2020);
  assert.equal(m.via, "gurgaon-district");
});
test("districtForYear / codes / guard", () => {
  for (const [d, y, want] of C.district_for_year) assert.deepEqual(ir.districtForYear(d, y), want);
  for (const [c, want] of C.district_by_lgd) assert.equal(id(ir.districtByLgd(c)), want);
  for (const [c, want] of C.district_by_census2011) assert.equal(id(ir.districtByCensus2011(c)), want);
  for (const [a, b] of C.similarity_zero) assert.equal(ir.similarity(a, b), 0);
  assert.equal(ir.statesInYear(2026).length, C.counts.states_in_2026);
});
test("golden: same answers as Python", () => {
  G.resolve_keys.forEach(([sid, y], i) => assert.equal(ir.resolveStateForYear(sid, y), G.resolve[i], `${sid} ${y}`));
  for (const row of G.match) {
    const m = ir.matchDistrict(row.name, row.state, row.year);
    assert.deepEqual(m ? [m.id, m.score, m.method, m.via] : null, row.want, JSON.stringify(row));
  }
  for (const [a, b, want] of G.similarity) assert.equal(ir.similarity(a, b), want, `${a} | ${b}`);
});
