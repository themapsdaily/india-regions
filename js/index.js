"use strict";
// india-regions: India's states and districts through time.
// A line-for-line port of src/india_regions/_core.py over the same JSON data;
// tests/golden.json (generated from Python) holds the two to the same answers.

const S = require("../src/india_regions/data/states.json");
const D = require("../src/india_regions/data/districts.json");

const DATA_VERSION = S.version;
const STATES = S.states;
const STATE = new Map(STATES.map((s) => [s.id, s]));
const PARENT = S.parent;
const PARENT_BEFORE = Object.fromEntries(
  Object.entries(S.parent_before).map(([k, v]) => [k, [v.until, v.parent]])
);
const RENAMED_FROM = S.renamed_from;
const MERGES = S.merges;
const STATE_ALIASES = S.aliases;
const DISTRICTS = D.periods;
const DISTRICT_ALIASES = D.aliases;
const DISTRICT_EVENTS = D.events;

const OPEN = 9999;
const CODES = new Map(
  STATES.filter((s) => s.code && s.last_year === null).map((s) => [s.code.toLowerCase(), s.id])
);
const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

function window_(rec) {
  return [rec.first_year, rec.last_year !== null ? rec.last_year : OPEN];
}

function coerceYear(year) {
  if (year === null || year === undefined || typeof year === "boolean") return null;
  if (typeof year === "number" && Number.isInteger(year)) return year;
  const head = String(year).trim().split("-", 1)[0].trim();
  return /^[+]?\d+$/.test(head) ? parseInt(head, 10) : null;
}

// ------------------------------------------------------------------ states

function getState(id) {
  return STATE.get(id) || null;
}

function statesInYear(year) {
  const y = coerceYear(year);
  if (y === null) return [];
  return STATES.filter((s) => window_(s)[0] <= y && y <= window_(s)[1]);
}

function isValidInYear(id, year) {
  const rec = STATE.get(id);
  const y = coerceYear(year);
  if (!rec || y === null) return false;
  const [first, last] = window_(rec);
  return first <= y && y <= last;
}

function deriveSuccessors() {
  const cands = {};
  for (const [child, parent] of Object.entries(PARENT)) {
    const c = STATE.get(child), p = STATE.get(parent);
    if (c && p && p.last_year !== null && c.first_year === p.last_year + 1) {
      (cands[parent] = cands[parent] || []).push(child);
    }
  }
  const out = {};
  for (const [p, kids] of Object.entries(cands)) if (kids.length === 1) out[p] = kids[0];
  for (const m of MERGES) for (const member of m.members) out[member] = m.into;
  return out;
}
const SUCCESSOR = deriveSuccessors();

function resolveStateForYear(id, year, { strict = true } = {}) {
  const miss = strict ? null : id;
  const y = coerceYear(year);
  if (!id || y === null || !STATE.has(id)) return miss;
  if (isValidInYear(id, y)) return id;
  let current = id;
  if (y < STATE.get(id).first_year) {
    for (let i = 0; i <= Object.keys(PARENT).length; i++) {
      const override = PARENT_BEFORE[current];
      if (override && y <= override[0]) current = override[1];
      else if (has(PARENT, current)) current = PARENT[current];
      else break;
      if (isValidInYear(current, y)) return current;
    }
    return miss;
  }
  for (let i = 0; i <= Object.keys(SUCCESSOR).length; i++) {
    if (!has(SUCCESSOR, current)) break;
    current = SUCCESSOR[current];
    if (isValidInYear(current, y)) return current;
  }
  return miss;
}

function originState(id) {
  let current = id;
  for (let i = 0; i <= Object.keys(PARENT).length; i++) {
    const parent = PARENT[current];
    if (parent === undefined || !STATE.has(current) || !STATE.has(parent)) return current;
    const p = STATE.get(parent);
    if (p.last_year === null || p.last_year + 1 !== STATE.get(current).first_year) return parent;
    current = parent;
  }
  return current;
}

function eraStateId(id, year) {
  const old = RENAMED_FROM[id];
  const y = coerceYear(year);
  if (old === undefined || y === null) return id;
  return y < STATE.get(id).first_year ? old : id;
}

function mergeGroup(id, year) {
  const y = coerceYear(year);
  if (y === null) return null;
  for (const m of MERGES) if (m.members.includes(id) && y >= m.from_year) return m.into;
  return null;
}

const lineageCache = new Map();
function lineage(id) {
  if (lineageCache.has(id)) return lineageCache.get(id);
  const seen = new Set([id]);
  const stack = [id];
  while (stack.length) {
    const cur = stack.pop();
    const nxt = [PARENT[cur]];
    for (const m of MERGES) {
      if (m.members.includes(cur)) nxt.push(m.into);
      if (m.into === cur) nxt.push(...m.members);
    }
    if (PARENT_BEFORE[cur]) nxt.push(PARENT_BEFORE[cur][1]);
    for (const n of nxt) if (n && !seen.has(n)) { seen.add(n); stack.push(n); }
  }
  lineageCache.set(id, seen);
  return seen;
}

function sameTerritory(a, b) {
  return a === b || lineage(b).has(a) || lineage(a).has(b);
}

// ------------------------------------------------------------ name folding

const asciiOnly = (t) => String(t).normalize("NFKD").replace(/[^\x00-\x7f]/g, "");
const FOOTNOTE_RE = /[\s*@#+]+$/;
const UT_NCT_RE = /\(\s*(?:ut|nct)\s*\)/gi;

function normalizeStateKey(name) {
  if (!name) return "";
  let key = asciiOnly(name).toLowerCase();
  for (;;) {
    const stripped = key.replace(UT_NCT_RE, " ").replace(FOOTNOTE_RE, "");
    if (stripped === key) break;
    key = stripped;
  }
  key = key.replace(/&/g, " and ");
  for (const ch of ".,()'’") key = key.split(ch).join(" ");
  key = key.replace(/[-_/]/g, " ");
  return key.split(/\s+/).filter(Boolean).join(" ");
}

const DIRECTION_WORDS = new Set([
  "north", "south", "east", "west", "upper", "lower", "central", "middle", "greater", "new",
  "rural", "urban", "city", "metro", "metropolitan", "old",
]);
const DIRECTION_SYNONYMS = {
  uttar: "north", uttara: "north", dakshin: "south", dakshina: "south",
  purba: "east", purbi: "east", purv: "east", purva: "east",
  paschim: "west", pashchim: "west", paschimi: "west", madhya: "central",
};

function phonetic(compact) {
  let s = compact;
  for (const [x, z] of [["aa", "a"], ["ee", "i"], ["oo", "u"], ["w", "v"]]) s = s.split(x).join(z);
  return s.replace(/(.)\1+/g, "$1");
}

function directions(key) {
  return new Set(key.split(" ").filter((w) => DIRECTION_WORDS.has(w)));
}
const setEq = (a, b) => a.size === b.size && [...a].every((x) => b.has(x));

function rawKey(name) {
  let s = asciiOnly(name).toLowerCase().replace(/&/g, " and ");
  s = s.replace(/\([^)]*\)/g, " ");
  s = s.replace(/[^a-z0-9]+/g, " ");
  s = s.replace(/\b(district|dist|zila|zilla|jilla)\b/g, " ");
  s = s.trim().replace(/^the\s+/, "");
  return s.split(/\s+/).filter(Boolean).join(" ");
}

function districtKey(name) {
  return rawKey(name).split(" ").filter(Boolean).map((w) => DIRECTION_SYNONYMS[w] || w).join(" ");
}

// Python's difflib.SequenceMatcher(None, a, b).ratio(), for strings under 200
// characters (no autojunk), so scores match the Python package exactly.
function sequenceRatio(a, b) {
  const b2j = new Map();
  for (let j = 0; j < b.length; j++) {
    if (!b2j.has(b[j])) b2j.set(b[j], []);
    b2j.get(b[j]).push(j);
  }
  function longest(alo, ahi, blo, bhi) {
    let besti = alo, bestj = blo, bestsize = 0;
    let j2len = new Map();
    for (let i = alo; i < ahi; i++) {
      const newj2len = new Map();
      for (const j of b2j.get(a[i]) || []) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const k = (j2len.get(j - 1) || 0) + 1;
        newj2len.set(j, k);
        if (k > bestsize) { besti = i - k + 1; bestj = j - k + 1; bestsize = k; }
      }
      j2len = newj2len;
    }
    return [besti, bestj, bestsize];
  }
  let matches = 0;
  const queue = [[0, a.length, 0, b.length]];
  while (queue.length) {
    const [alo, ahi, blo, bhi] = queue.pop();
    const [i, j, k] = longest(alo, ahi, blo, bhi);
    if (k) {
      matches += k;
      if (alo < i && blo < j) queue.push([alo, i, blo, j]);
      if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
    }
  }
  const total = a.length + b.length;
  return total ? (2 * matches) / total : 1;
}

// Python's round(x, 4): exact halves go to the even neighbour.
function round4(x) {
  const v = x * 1e4;
  const f = Math.floor(v);
  const diff = v - f;
  const r = diff > 0.5 ? f + 1 : diff < 0.5 ? f : (f % 2 === 0 ? f : f + 1);
  return r / 1e4;
}

function similarity(a, b) {
  if (districtKey(a) === districtKey(b)) return 1.0;
  const ka = rawKey(a), kb = rawKey(b);
  if (!setEq(directions(ka), directions(kb))) return 0.0;
  const pa = phonetic(ka.split(" ").join("")), pb = phonetic(kb.split(" ").join(""));
  if (!pa || !pb) return 0.0;
  if (pa === pb) return 1.0;
  return sequenceRatio(pa, pb);
}

function makeMatch(id, name, score, method, state = null, inYear = true, via = null) {
  return { id, name, score, method, state, inYear, via };
}

// ---------------------------------------------------- state normalisation

function normalizeState(name, extra) {
  const key = normalizeStateKey(name);
  if (!key) return null;
  if (extra) {
    for (const [k, v] of Object.entries(extra)) if (normalizeStateKey(k) === key) return v;
  }
  if (has(STATE_ALIASES, key)) return STATE_ALIASES[key];
  if (CODES.has(key)) return CODES.get(key);
  const compact = key.split(" ").join("");
  for (const [k, v] of Object.entries(STATE_ALIASES)) if (k.split(" ").join("") === compact) return v;
  return null;
}

function matchState(name, { cutoff = 0.85 } = {}) {
  const key = normalizeStateKey(name);
  if (!key) return null;
  const exact = normalizeState(name);
  if (exact) {
    const rec = STATE.get(exact);
    const method = rec && normalizeStateKey(rec.name) === key ? "exact" : "alias";
    return makeMatch(exact, rec ? rec.name : exact, 1.0, method, exact);
  }
  let best = null;
  for (const [alias, sid] of Object.entries(STATE_ALIASES)) {
    const score = similarity(key, alias);
    if (score >= cutoff && (best === null || score > best.score)) {
      const rec = STATE.get(sid);
      best = makeMatch(sid, rec ? rec.name : sid, round4(score), score === 1.0 ? "spelling" : "fuzzy", sid);
    }
  }
  return best;
}

function normalizeRegion(name, year = null, { strict = true } = {}) {
  const sid = normalizeState(name);
  if (!sid) return null;
  if (year === null || year === undefined) return sid;
  return resolveStateForYear(sid, year, { strict });
}

// --------------------------------------------------------------- districts

function normalizeDistrictKey(name) {
  return name ? districtKey(name).split(" ").join("") : "";
}

const BY_ID = new Map();
for (const p of DISTRICTS) {
  if (!BY_ID.has(p.id)) BY_ID.set(p.id, []);
  BY_ID.get(p.id).push(p);
}
for (const ps of BY_ID.values()) ps.sort((x, y) => x.first_year - y.first_year);

function deriveDistrictSuccessors() {
  const out = {};
  for (const [did, periods] of BY_ID) {
    const last = periods[periods.length - 1];
    if (last.end && (last.end.kind === "rename" || last.end.kind === "absorb")) {
      out[did] = last.end.to.filter((t) => t !== did);
    }
  }
  for (const [did, periods] of BY_ID) {
    const first = periods[0];
    if (["rename", "renamed", "absorb"].includes(first.event) && first.parents.length) {
      for (const parent of first.parents) {
        const pp = BY_ID.get(parent);
        if (pp && pp[pp.length - 1].last_year === first.first_year - 1) {
          const lst = (out[parent] = out[parent] || []);
          if (!lst.includes(did)) lst.push(did);
        }
      }
    }
  }
  return out;
}
const DISTRICT_SUCCESSOR = deriveDistrictSuccessors();

function periodAlive(p, y) {
  const [first, last] = window_(p);
  return first <= y && y <= last;
}

const canonicalDistrict = (id) => (has(DISTRICT_ALIASES, id) ? DISTRICT_ALIASES[id] : id);

function getDistrict(id, year = null) {
  const periods = BY_ID.get(canonicalDistrict(id));
  if (!periods) return null;
  const y = coerceYear(year);
  if (y === null) return periods[periods.length - 1];
  return periods.find((p) => periodAlive(p, y)) || null;
}

function districtPeriods(id) {
  return [...(BY_ID.get(canonicalDistrict(id)) || [])];
}

function districtsInYear(year, state = null, { officialOnly = true } = {}) {
  const y = coerceYear(year);
  if (y === null) return [];
  const sid = state ? normalizeState(state) || state : null;
  return DISTRICTS.filter((p) => periodAlive(p, y)
    && (!officialOnly || p.status === "official")
    && (sid === null || p.state === sid));
}

function index(field) {
  const out = new Map();
  for (const p of DISTRICTS) {
    if (p[field] && (!out.has(p[field]) || p.first_year > out.get(p[field]).first_year)) out.set(p[field], p);
  }
  return out;
}
const BY_LGD = index("lgd_code");
const BY_CENSUS = index("census2011_code");

function districtByLgd(code) {
  return BY_LGD.get(String(code).trim()) || null;
}

function districtByCensus2011(code) {
  const t = String(code).trim();
  return /^\d+$/.test(t) ? BY_CENSUS.get(String(parseInt(t, 10))) || null : null;
}

function districtForYear(id, year) {
  const y = coerceYear(year);
  id = canonicalDistrict(id);
  const periods = BY_ID.get(id);
  if (!periods || y === null) return [];
  if (periods.some((p) => periodAlive(p, y))) return [id];
  const out = [];
  const add = (xs) => { for (const r of xs) if (!out.includes(r)) out.push(r); };
  if (y < periods[0].first_year) {
    for (const parent of periods[0].parents) add(districtForYear(parent, y));
    return out;
  }
  for (const nxt of DISTRICT_SUCCESSOR[id] || []) add(districtForYear(nxt, y));
  return out;
}

let keysCache = null;
function districtKeys() {
  if (keysCache) return keysCache;
  const rows = [];
  const namesById = new Map();
  for (const p of DISTRICTS) {
    if (!namesById.has(p.id)) namesById.set(p.id, new Set());
    namesById.get(p.id).add(p.name);
  }
  const oldIds = {};
  for (const [old, nu] of Object.entries(DISTRICT_ALIASES)) (oldIds[nu] = oldIds[nu] || []).push(old);
  const strip = (s) => (s.endsWith("-district") ? s.slice(0, -"-district".length) : s);
  for (const p of DISTRICTS) {
    const own = districtKey(p.name);
    rows.push([own, "exact", p]);
    const seen = new Set([own]);
    const others = [strip(p.id), ...[...namesById.get(p.id)].sort(), ...(oldIds[p.id] || []).map(strip)];
    for (const other of others) {
      const k = districtKey(other);
      if (k && !seen.has(k)) { seen.add(k); rows.push([k, "alias", p]); }
    }
  }
  keysCache = rows;
  return rows;
}

function tupleGt(a, b) {
  for (let i = 0; i < a.length; i++) {
    const x = typeof a[i] === "boolean" ? +a[i] : a[i];
    const y = typeof b[i] === "boolean" ? +b[i] : b[i];
    if (x > y) return true;
    if (x < y) return false;
  }
  return false;
}

function districtCandidates(name, state = null, year = null, { cutoff = 0.85, limit = 5 } = {}) {
  const key = name ? districtKey(name) : "";
  if (!key) return [];
  let sid = null;
  if (state) {
    sid = normalizeState(state) || (STATE.has(state) ? state : null);
    if (sid === null) return [];
  }
  const y = coerceYear(year);
  const best = new Map();
  for (const [k, method, p] of districtKeys()) {
    if (sid && !sameTerritory(p.state, sid)) continue;
    let score, how;
    if (k === key) { score = 1.0; how = method; } else {
      score = similarity(key, k);
      if (score < cutoff) continue;
      how = score === 1.0 ? "spelling" : "fuzzy";
    }
    const inYear = y === null || periodAlive(p, y);
    const m = makeMatch(p.id, p.name, round4(score), how, p.state, inYear);
    const rank = [m.inYear, m.score, sid === null || p.state === sid, p.first_year, m.method === "exact"];
    const cur = best.get(p.id);
    if (!cur || tupleGt(rank, cur[0])) best.set(p.id, [rank, m]);
  }
  const ranked = [...best.values()].map((v) => v[1]);
  ranked.sort((a, b) => {
    const ka = [!a.inYear, -a.score, a.method !== "exact"], kb = [!b.inYear, -b.score, b.method !== "exact"];
    if (tupleGt(ka, kb)) return 1;
    if (tupleGt(kb, ka)) return -1;
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });
  return ranked.slice(0, limit);
}

function matchDistrict(name, state = null, year = null, { cutoff = 0.85 } = {}) {
  const ranked = districtCandidates(name, state, year, { cutoff, limit: 2 });
  if (!ranked.length) return null;
  if (ranked.length === 2 && ranked[1].inYear === ranked[0].inYear && ranked[1].score === ranked[0].score) {
    return null;
  }
  const top = ranked[0];
  if (top.inYear) return top;
  const now = districtForYear(top.id, year);
  if (now.length !== 1) return top;
  const rec = getDistrict(now[0], year);
  return makeMatch(now[0], rec.name, top.score, top.method, rec.state, true, top.id);
}

function matchDistricts(names, state = null, year = null, opts = {}) {
  const out = {};
  for (const n of names) out[n] = matchDistrict(n, state, year, opts);
  return out;
}

module.exports = {
  DATA_VERSION, STATES, PARENT, PARENT_BEFORE, RENAMED_FROM, MERGES, STATE_ALIASES, SUCCESSOR,
  DISTRICTS, DISTRICT_ALIASES, DISTRICT_EVENTS, DISTRICT_SUCCESSOR, DIRECTION_WORDS,
  getState, statesInYear, isValidInYear, resolveStateForYear, originState, eraStateId,
  mergeGroup, sameTerritory, normalizeStateKey, normalizeState, matchState, normalizeRegion,
  similarity, normalizeDistrictKey, getDistrict, districtPeriods, districtsInYear,
  districtByLgd, districtByCensus2011, districtForYear, districtCandidates, matchDistrict,
  matchDistricts,
};
