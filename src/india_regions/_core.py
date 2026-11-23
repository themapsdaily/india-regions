"""India's states and districts through time: names, codes, validity, matching.

Two jobs, kept apart on purpose:

  normalisation   a source label  -> a territory id   ("Orissa" -> "odisha")
  resolution      id + year       -> the id that existed that year
                                     ("odisha", 1998 -> "orissa")

Historical spellings normalise to the present-day id; resolution walks back to
the unit that held the territory in the year asked. One table then serves data
of any vintage.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from importlib import resources
from typing import Iterable, Mapping, Optional, Union

Year = Union[int, str, None]

# --------------------------------------------------------------------------- data


def _load(name: str) -> dict:
    return json.loads(resources.files(__package__).joinpath("data", name).read_text("utf-8"))


_S = _load("states.json")
_D = _load("districts.json")

DATA_VERSION: str = _S["version"]
STATES: list[dict] = _S["states"]
_STATE = {s["id"]: s for s in STATES}
PARENT: dict[str, str] = _S["parent"]
PARENT_BEFORE: dict[str, tuple[int, str]] = {
    k: (v["until"], v["parent"]) for k, v in _S["parent_before"].items()
}
RENAMED_FROM: dict[str, str] = _S["renamed_from"]
MERGES: list[dict] = _S["merges"]
STATE_ALIASES: dict[str, str] = _S["aliases"]

DISTRICTS: list[dict] = _D["periods"]
DISTRICT_ALIASES: dict[str, str] = _D["aliases"]
DISTRICT_EVENTS: list[dict] = _D["events"]

_OPEN = 9999
# short codes of units that exist today ("UP", "TN", "OD"); folded like names
_CODES = {s["code"].lower(): s["id"] for s in STATES if s.get("code") and s["last_year"] is None}  # last_year null = still exists


def _window(rec: dict) -> tuple[int, int]:
    return rec["first_year"], rec["last_year"] if rec["last_year"] is not None else _OPEN


def _coerce_year(year: Year) -> Optional[int]:
    """Accept 2020, '2020' or '2020-21' (a financial year counts as its first year)."""
    if year is None or isinstance(year, bool):
        return None
    if isinstance(year, int):
        return year
    head = str(year).strip().split("-", 1)[0].strip()
    try:
        return int(head)
    except ValueError:
        return None


# ------------------------------------------------------------------------- states


def get_state(state_id: str) -> Optional[dict]:
    """The record for a state id: name, type, short code, first/last year."""
    return _STATE.get(state_id)


def states_in_year(year: Year) -> list[dict]:
    """Every state, UT, province or princely unit that existed in `year`."""
    y = _coerce_year(year)
    if y is None:
        return []
    return [s for s in STATES if _window(s)[0] <= y <= _window(s)[1]]


def is_valid_in_year(state_id: str, year: Year) -> bool:
    rec = _STATE.get(state_id)
    y = _coerce_year(year)
    if rec is None or y is None:
        return False
    first, last = _window(rec)
    return first <= y <= last


def _derive_successors() -> dict[str, str]:
    # A successor is the unique child whose window opens the year its parent's
    # closes, so uttar-pradesh is never read as succeeded by uttaranchal.
    cands: dict[str, list[str]] = {}
    for child, parent in PARENT.items():
        if child in _STATE and parent in _STATE and _STATE[parent]["last_year"] is not None:
            if _STATE[child]["first_year"] == _STATE[parent]["last_year"] + 1:
                cands.setdefault(parent, []).append(child)
    out = {p: kids[0] for p, kids in cands.items() if len(kids) == 1}
    for m in MERGES:
        out.update({member: m["into"] for member in m["members"]})
    return out


SUCCESSOR: dict[str, str] = _derive_successors()


def resolve_state_for_year(state_id: str, year: Year, *, strict: bool = True) -> Optional[str]:
    """The id that held this territory in `year`.

    >>> resolve_state_for_year("odisha", 1998)
    'orissa'
    >>> resolve_state_for_year("uttarakhand", 1995)
    'uttar-pradesh'
    >>> resolve_state_for_year("telangana", 1950)
    'hyderabad-state'
    >>> resolve_state_for_year("dnh", 2021)
    'dnhdd'

    Walks back through PARENT when the unit did not exist yet and forward
    through SUCCESSOR when it had been superseded. With strict=True (default) a
    pair with no answer gives None; strict=False gives the input back.
    """
    miss = None if strict else state_id
    y = _coerce_year(year)
    if not state_id or y is None or state_id not in _STATE:
        return miss
    if is_valid_in_year(state_id, y):
        return state_id
    current = state_id
    if y < _STATE[state_id]["first_year"]:
        for _ in range(len(PARENT) + 1):
            override = PARENT_BEFORE.get(current)
            if override and y <= override[0]:
                current = override[1]
            elif current in PARENT:
                current = PARENT[current]
            else:
                break
            if is_valid_in_year(current, y):
                return current
        return miss
    for _ in range(len(SUCCESSOR) + 1):
        if current not in SUCCESSOR:
            break
        current = SUCCESSOR[current]
        if is_valid_in_year(current, y):
            return current
    return miss


def origin_state(state_id: str) -> str:
    """The state this one was carved out of, stepping over pure renames.

    >>> origin_state("uttarakhand")
    'uttar-pradesh'
    >>> origin_state("telangana")
    'andhra-pradesh'
    >>> origin_state("odisha")      # never carved out: its earliest name
    'orissa'
    """
    current = state_id
    for _ in range(len(PARENT) + 1):
        parent = PARENT.get(current)
        if parent is None or current not in _STATE or parent not in _STATE:
            return current
        if _STATE[parent]["last_year"] is None or \
                _STATE[parent]["last_year"] + 1 != _STATE[current]["first_year"]:
            return parent
        current = parent
    return current


def era_state_id(state_id: str, year: Year) -> str:
    """The id a renamed state carried in `year`; splits are never folded.

    >>> era_state_id("keralam", 2018)
    'kerala'
    >>> era_state_id("chhattisgarh", 1998)
    'chhattisgarh'
    """
    old = RENAMED_FROM.get(state_id)
    y = _coerce_year(year)
    if old is None or y is None:
        return state_id
    return old if y < _STATE[state_id]["first_year"] else state_id


def merge_group(state_id: str, year: Year) -> Optional[str]:
    """The merged unit a value must be combined into, or None.

    >>> merge_group("dnh", 2021)
    'dnhdd'

    Relabelling is not enough when two units became one: sum counts,
    population-weight rates. That choice is the caller's.
    """
    y = _coerce_year(year)
    if y is None:
        return None
    for m in MERGES:
        if state_id in m["members"] and y >= m["from_year"]:
            return m["into"]
    return None


def same_territory(a: str, b: str) -> bool:
    """True when one state is on the other's lineage (keralam/kerala,
    telangana/andhra-pradesh, dnhdd/daman-diu)."""
    if a == b:
        return True
    la, lb = _lineage(a), _lineage(b)
    return a in lb or b in la


@lru_cache(maxsize=None)
def _lineage(state_id: str) -> frozenset:
    seen = {state_id}
    stack = [state_id]
    while stack:
        cur = stack.pop()
        nxt = [PARENT.get(cur)] + [m["into"] for m in MERGES if cur in m["members"]] \
            + [mem for m in MERGES if m["into"] == cur for mem in m["members"]]
        override = PARENT_BEFORE.get(cur)
        if override:
            nxt.append(override[1])
        for n in nxt:
            if n and n not in seen:
                seen.add(n)
                stack.append(n)
    return frozenset(seen)


# ------------------------------------------------------------------ name folding

_FOOTNOTE_RE = re.compile(r"[\s*@#+]+$")
_UT_NCT_RE = re.compile(r"\(\s*(?:ut|nct)\s*\)", re.IGNORECASE)


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def normalize_state_key(name: Optional[str]) -> str:
    """Fold a label to a comparison key: lowercase, & -> and, no punctuation,
    no trailing footnote marks (`Ladakh @`, `Odisha #`), no `(UT)` / `(NCT)`."""
    if not name:
        return ""
    key = _ascii(str(name)).lower()
    while True:
        stripped = _FOOTNOTE_RE.sub("", _UT_NCT_RE.sub(" ", key))
        if stripped == key:
            break
        key = stripped
    key = key.replace("&", " and ")
    for ch in ".,()'’":
        key = key.replace(ch, " ")
    key = key.replace("-", " ").replace("_", " ").replace("/", " ")
    return " ".join(key.split())


DIRECTION_WORDS = frozenset(
    {"north", "south", "east", "west", "upper", "lower", "central", "middle", "greater", "new",
     "rural", "urban", "city", "metro", "metropolitan", "old"}
)
# Same direction in Hindi/Bengali/Odia names: Uttar Dinajpur = North Dinajpur.
_DIRECTION_SYNONYMS = {
    "uttar": "north", "uttara": "north", "dakshin": "south", "dakshina": "south",
    "purba": "east", "purbi": "east", "purv": "east", "purva": "east",
    "paschim": "west", "pashchim": "west", "paschimi": "west", "madhya": "central",
}


def _phonetic(compact: str) -> str:
    """Spelling-variant fold used before fuzzy scoring: the transliteration
    drift seen across Indian publishers (aa/a, ee/i, oo/u, w/v, doubled letters)."""
    s = compact
    for x, z in (("aa", "a"), ("ee", "i"), ("oo", "u"), ("w", "v")):
        s = s.replace(x, z)
    return re.sub(r"(.)\1+", r"\1", s)


def _directions(key: str) -> frozenset:
    return frozenset(key.split()) & DIRECTION_WORDS


def similarity(a: str, b: str) -> float:
    """0..1 score between two place names after folding.

    0 when one has a direction word the other lacks: "Garo Hills" never matches
    "West Garo Hills", however close the letters are.
    """
    if _district_key(a) == _district_key(b):
        return 1.0
    ka, kb = _raw_key(a), _raw_key(b)
    if _directions(ka) != _directions(kb):
        return 0.0
    pa, pb = _phonetic(ka.replace(" ", "")), _phonetic(kb.replace(" ", ""))
    if not pa or not pb:
        return 0.0
    if pa == pb:
        return 1.0
    return SequenceMatcher(None, pa, pb).ratio()


@dataclass(frozen=True)
class Match:
    id: str
    name: str
    score: float
    method: str            # exact | alias | spelling | fuzzy
    state: Optional[str] = None
    in_year: bool = True   # False when the match only exists in another year
    via: Optional[str] = None  # the id the label named, when it was resolved to another year's id


# ----------------------------------------------------------- state normalisation


def normalize_state(name: Optional[str], extra: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """A state label to its id, or None. Exact and alias matches only (incl.
    known typos: Telengana, Chattisgarh, Maharastra, Andaman & Nicober).

    `extra` adds labels of your own, folded the same way.
    """
    key = normalize_state_key(name)
    if not key:
        return None
    if extra:
        folded = {normalize_state_key(k): v for k, v in extra.items()}
        if key in folded:
            return folded[key]
    if key in STATE_ALIASES:
        return STATE_ALIASES[key]
    if key in _CODES:
        return _CODES[key]
    compact = key.replace(" ", "")
    for k, v in STATE_ALIASES.items():
        if k.replace(" ", "") == compact:
            return v
    return None


def match_state(name: Optional[str], *, cutoff: float = 0.85) -> Optional[Match]:
    """Like normalize_state, plus a fuzzy pass for spellings nobody listed yet.

    >>> match_state("Chhatisgarh").id
    'chhattisgarh'
    >>> match_state("Utter Pradesh").method
    'fuzzy'
    """
    key = normalize_state_key(name)
    if not key:
        return None
    exact = normalize_state(name)
    if exact:
        rec = _STATE.get(exact)
        method = "exact" if rec and normalize_state_key(rec["name"]) == key else "alias"
        return Match(exact, rec["name"] if rec else exact, 1.0, method, exact)
    best: Optional[Match] = None
    for alias, sid in STATE_ALIASES.items():
        score = similarity(key, alias)
        if score >= cutoff and (best is None or score > best.score):
            rec = _STATE.get(sid)
            best = Match(sid, rec["name"] if rec else sid, round(score, 4),
                         "spelling" if score == 1.0 else "fuzzy", sid)
    return best


def normalize_region(name: Optional[str], year: Year = None, *, strict: bool = True) -> Optional[str]:
    """normalize_state + resolve_state_for_year: label and year in, the id of
    that year out.

    >>> normalize_region("Orissa", 1998)
    'orissa'
    >>> normalize_region("Uttarakhand", 1995)
    'uttar-pradesh'
    """
    sid = normalize_state(name)
    if not sid:
        return None
    if year is None:
        return sid
    return resolve_state_for_year(sid, year, strict=strict)


# --------------------------------------------------------------------- districts

_PARENS_RE = re.compile(r"\([^)]*\)")
_DISTRICT_WORD_RE = re.compile(r"\b(district|dist|zila|zilla|jilla)\b")


def _raw_key(name: str) -> str:
    s = _ascii(str(name)).lower().replace("&", " and ")
    s = _PARENS_RE.sub(" ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = _DISTRICT_WORD_RE.sub(" ", s)
    s = re.sub(r"^the\s+", "", s.strip())
    return " ".join(s.split())


def _district_key(name: str) -> str:
    """Comparison key; Indian-language direction words read as English so
    'Purba Medinipur' and 'East Medinipur' share one key."""
    return " ".join(_DIRECTION_SYNONYMS.get(w, w) for w in _raw_key(name).split())


def normalize_district_key(name: Optional[str]) -> str:
    """Fold a district label: ascii, lowercase, no brackets, no 'district'."""
    return _district_key(name).replace(" ", "") if name else ""


_BY_ID: dict[str, list[dict]] = {}
for _p in DISTRICTS:
    _BY_ID.setdefault(_p["id"], []).append(_p)
for _ps in _BY_ID.values():
    _ps.sort(key=lambda p: p["first_year"])


def _derive_district_successors() -> dict[str, list[str]]:
    """Where a district's territory went when it ended: renames and absorptions.

    Read from both ends, because the data records a rename either as the old
    period's `end` or only as the new period's `event` + `parents`. A split is
    not a successor: the parent carries on under its own id.
    """
    out: dict[str, list[str]] = {}
    for did, periods in _BY_ID.items():
        last = periods[-1]
        if last["end"] and last["end"]["kind"] in ("rename", "absorb"):
            out[did] = [t for t in last["end"]["to"] if t != did]
    for did, periods in _BY_ID.items():
        first = periods[0]
        if first["event"] in ("rename", "renamed", "absorb") and first["parents"]:
            for parent in first["parents"]:
                pp = _BY_ID.get(parent)
                if pp and pp[-1]["last_year"] == first["first_year"] - 1:
                    lst = out.setdefault(parent, [])
                    if did not in lst:
                        lst.append(did)
    return out


def _period_alive(p: dict, y: int) -> bool:
    first, last = _window(p)
    return first <= y <= last


def get_district(district_id: str, year: Year = None) -> Optional[dict]:
    """The district's period for `year`, or its latest period when no year."""
    district_id = DISTRICT_ALIASES.get(district_id, district_id)
    periods = _BY_ID.get(district_id)
    if not periods:
        return None
    y = _coerce_year(year)
    if y is None:
        return periods[-1]
    return next((p for p in periods if _period_alive(p, y)), None)


def district_periods(district_id: str) -> list[dict]:
    """Every period of a district: one per state it belonged to or name it kept."""
    return list(_BY_ID.get(DISTRICT_ALIASES.get(district_id, district_id), []))


def districts_in_year(year: Year, state: Optional[str] = None, *,
                      official_only: bool = True) -> list[dict]:
    """Districts that existed in `year`, optionally in one state (id or name)."""
    y = _coerce_year(year)
    if y is None:
        return []
    sid = (normalize_state(state) or state) if state else None
    return [p for p in DISTRICTS if _period_alive(p, y)
            and (not official_only or p["status"] == "official")
            and (sid is None or p["state"] == sid)]


def _index(field: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in DISTRICTS:
        if p[field] and (p[field] not in out or p["first_year"] > out[p[field]]["first_year"]):
            out[p[field]] = p
    return out


DISTRICT_SUCCESSOR: dict[str, list[str]] = _derive_district_successors()
_BY_LGD = _index("lgd_code")
_BY_CENSUS = _index("census2011_code")


def district_by_lgd(code: Union[str, int]) -> Optional[dict]:
    """Latest period carrying this LGD district code."""
    return _BY_LGD.get(str(code).strip())


def district_by_census2011(code: Union[str, int]) -> Optional[dict]:
    """Latest period carrying this Census 2011 district code."""
    return _BY_CENSUS.get(str(int(str(code).strip()))) if str(code).strip().isdigit() else None


def district_for_year(district_id: str, year: Year) -> list[str]:
    """The district id(s) that held this district's territory in `year`.

    Before it existed: the district(s) it was carved from. After it ended: what
    it was renamed to or absorbed into (a split into several gives several).
    Empty when there is no answer in the data.
    """
    y = _coerce_year(year)
    district_id = DISTRICT_ALIASES.get(district_id, district_id)
    periods = _BY_ID.get(district_id)
    if not periods or y is None:
        return []
    if any(_period_alive(p, y) for p in periods):
        return [district_id]
    out: list[str] = []
    if y < periods[0]["first_year"]:
        for parent in periods[0]["parents"]:
            for r in district_for_year(parent, y):
                if r not in out:
                    out.append(r)
        return out
    for nxt in DISTRICT_SUCCESSOR.get(district_id, []):
        for r in district_for_year(nxt, y):
            if r not in out:
                out.append(r)
    return out


@lru_cache(maxsize=1)
def _district_keys() -> list[tuple[str, str, dict]]:
    """(key, method, period) for every name a period answers to."""
    rows: list[tuple[str, str, dict]] = []
    names_by_id: dict[str, set[str]] = {}
    for p in DISTRICTS:
        names_by_id.setdefault(p["id"], set()).add(p["name"])
    old_ids: dict[str, list[str]] = {}
    for old, new in DISTRICT_ALIASES.items():
        old_ids.setdefault(new, []).append(old)
    for p in DISTRICTS:
        own = _district_key(p["name"])
        rows.append((own, "exact", p))
        seen = {own}
        for other in [p["id"].removesuffix("-district")] + sorted(names_by_id[p["id"]]) + \
                [o.removesuffix("-district") for o in old_ids.get(p["id"], [])]:
            k = _district_key(other)
            if k and k not in seen:
                seen.add(k)
                rows.append((k, "alias", p))
    return rows


def district_candidates(name: Optional[str], state: Optional[str] = None, year: Year = None,
                        *, cutoff: float = 0.85, limit: int = 5) -> list[Match]:
    """Ranked district matches for a label, best first, one per district id.

    `state` (id or label) limits the search to that territory, including its
    earlier and later forms (a 2011 Andhra Pradesh district is found under
    Telangana). `year` prefers districts that existed then; matches that only
    exist in other years come after, with in_year=False.
    """
    key = _district_key(name) if name else ""
    if not key:
        return []
    sid = None
    if state:
        sid = normalize_state(state) or (state if state in _STATE else None)
        if sid is None:
            return []
    y = _coerce_year(year)
    best: dict[str, Match] = {}
    for k, method, p in _district_keys():
        if sid and not same_territory(p["state"], sid):
            continue
        if k == key:
            score, how = 1.0, method
        else:
            score = similarity(key, k)
            if score < cutoff:
                continue
            how = "spelling" if score == 1.0 else "fuzzy"
        in_year = y is None or _period_alive(p, y)
        m = Match(p["id"], p["name"], round(score, 4), how, p["state"], in_year)
        cur = best.get(p["id"])
        # in the year asked > closer score > in the very state named > newest period
        rank = (m.in_year, m.score, sid is None or p["state"] == sid, p["first_year"],
                m.method == "exact")
        if cur is None or rank > cur[0]:
            best[p["id"]] = (rank, m)
    best = {k: v[1] for k, v in best.items()}
    ranked = sorted(best.values(), key=lambda m: (not m.in_year, -m.score, m.method != "exact", m.id))
    return ranked[:limit]


def match_district(name: Optional[str], state: Optional[str] = None, year: Year = None,
                   *, cutoff: float = 0.85) -> Optional[Match]:
    """The one district a label means, or None when nothing or more than one fits.

    >>> match_district("Gurgaon", "Haryana", 2020).id   # renamed 2016
    'gurugram-district'
    >>> match_district("Thoothukudi", "Tamil Nadu").id
    'thoothukkudi-district'
    >>> match_district("Allahabad", "UP", 2020).id     # renamed 2018
    'prayagraj-district'

    Without a year the label's own unit comes back ("Gurgaon" -> gurgaon-district).
    When the unit did not exist in `year` and has no single successor (a split),
    the match comes back with in_year=False.

    Ambiguity returns None rather than a guess: "Aurangabad" without a state
    is two districts (Bihar and Maharashtra). Use district_candidates to see them.
    """
    ranked = district_candidates(name, state, year, cutoff=cutoff, limit=2)
    if not ranked:
        return None
    if len(ranked) == 2 and ranked[1].in_year == ranked[0].in_year \
            and ranked[1].score == ranked[0].score:
        return None
    top = ranked[0]
    if top.in_year:
        return top
    # the label is an old (or newer) name: answer with that year's district
    now = district_for_year(top.id, year)
    if len(now) != 1:
        return top
    rec = get_district(now[0], year)
    return Match(now[0], rec["name"], top.score, top.method, rec["state"], True, via=top.id)


def match_districts(names: Iterable[str], state: Optional[str] = None,
                    year: Year = None, *, cutoff: float = 0.85) -> dict[str, Optional[Match]]:
    """match_district over many labels, e.g. a column of a table."""
    return {n: match_district(n, state, year, cutoff=cutoff) for n in names}
