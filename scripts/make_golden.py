"""Write tests/golden.json from the Python package: the JS port must reproduce
every answer exactly, fuzzy scores included.

    PYTHONPATH=src python scripts/make_golden.py
"""

import json
import random
from pathlib import Path

import india_regions as ir

OUT = Path(__file__).resolve().parent.parent / "tests" / "golden.json"
rng = random.Random(7)

resolve_keys = [(s["id"], y) for s in ir.STATES for y in range(1945, 2031, 3)]

# District labels as publishers write them: real names, dropped/added letters,
# swapped vowels, old spellings, wrong-ish states, other years.
def mangle(name: str) -> str:
    s = list(name)
    op = rng.choice(["drop", "dup", "swap", "case", "none"])
    i = rng.randrange(len(s)) if s else 0
    if op == "drop" and len(s) > 4:
        del s[i]
    elif op == "dup":
        s.insert(i, s[i])
    elif op == "swap" and i + 1 < len(s):
        s[i], s[i + 1] = s[i + 1], s[i]
    elif op == "case":
        return name.upper()
    return "".join(s)


periods = rng.sample(ir.DISTRICTS, 300)
match = []
for p in periods:
    state = rng.choice([p["state"], ir.get_state(p["state"])["name"], None])
    year = rng.choice([None, p["first_year"], 2011, 2026, 1981])
    for name in (p["name"], mangle(p["name"])):
        m = ir.match_district(name, state, year)
        match.append({"name": name, "state": state, "year": year,
                      "want": [m.id, m.score, m.method, m.via] if m else None})

names = [p["name"] for p in rng.sample(ir.DISTRICTS, 120)]
similarity = [[a, mangle(b), ir.similarity(a, mangle(b))] for a, b in zip(names, rng.sample(names, len(names)))]
similarity += [[n, mangle(n), None] for n in names]
for row in similarity:
    row[2] = ir.similarity(row[0], row[1])

OUT.write_text(json.dumps({
    "data_version": ir.DATA_VERSION,
    "resolve_keys": resolve_keys,
    "resolve": [ir.resolve_state_for_year(s, y) for s, y in resolve_keys],
    "match": match,
    "similarity": similarity,
}, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{len(resolve_keys)} resolves, {len(match)} matches, {len(similarity)} similarities -> {OUT}")
