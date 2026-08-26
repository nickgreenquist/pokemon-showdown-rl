"""Did we pick a materially worse damaging move when a better one was available?

METHOD. In gen1 randbats a moveset is fixed at team generation, so any move a
mon used at ANY point in a battle was available to it the whole battle. That
gives a lower bound on our own movesets straight from the replay.

DAMAGE MODEL. gen1: dmg ~= ((2L/5 + 2) * BP_eff / 50) + 2, with
BP_eff = basePower * STAB * type-multiplier, then scaled by accuracy.
Fixed-damage moves are special-cased (Seismic Toss / Night Shade = level,
Dragon Rage = 40, Sonic Boom = 20, Psywave ~ 0.5L) because treating Seismic
Toss as basePower 1 produced five false positives on the first pass.

THREE APPROXIMATIONS, disclosed because they set the error bars:
  1. NO PP. A flagged pick whose better move was exhausted is a false
     positive. Hydro Pump and Blizzard have 5 PP, so this is not rare.
  2. NO ATTACK/DEFENSE RATIO. Comparing a physical move to a special one on
     the same mon ignores the stat difference. Same-category comparisons are
     unaffected and are reported separately as the trustworthy subset.
  3. LOWER-BOUND MOVESETS. A better move never used in that battle is
     invisible, so this UNDERCOUNTS.
Net: the same-category count is the defensible number; the total is an upper
bound on one side and a lower bound on the other.
"""
import re, pathlib, collections
from poke_env.data import GenData
from poke_env.battle.pokemon_type import PokemonType

G = GenData.from_gen(1)
TC, DEX, MOVES = G.type_chart, G.pokedex, G.moves
US = "nickgen1rbrlbot"
FIXED = {"seismictoss": "L", "nightshade": "L", "dragonrage": 40,
         "sonicboom": 20, "psywave": "L/2"}

def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())

def types_of(sp):
    e = DEX.get(norm(sp))
    if not e: return None
    ts = [getattr(PokemonType, t.upper()) for t in e["types"]]
    return (ts[0], ts[1] if len(ts) > 1 else None)

def damage(move_name, at, ft, level):
    m = MOVES.get(norm(move_name))
    if not m: return None
    acc = m["accuracy"]; acc = 1.0 if acc is True else acc / 100.0
    fx = FIXED.get(norm(move_name))
    if fx is not None:
        base = level if fx == "L" else (level / 2 if fx == "L/2" else fx)
        return base * acc, 1.0, m["category"]
    if not m["basePower"]: return None
    mt = getattr(PokemonType, m["type"].upper())
    mult = mt.damage_multiplier(*ft, type_chart=TC)
    stab = 1.5 if mt in [t for t in at if t] else 1.0
    bp_eff = m["basePower"] * stab * mult
    return (((2 * level / 5 + 2) * bp_eff / 50) + 2) * acc, mult, m["category"]

MARGIN = 2.0
flags, decisions = [], 0
for p in sorted(pathlib.Path("results/ladder/replays").glob("*.html")):
    bid = re.search(r"gen1randombattle-(\d{9,})", p.name)
    if not bid: continue
    txt = p.read_text(errors="ignore")
    slots = dict(re.findall(r"\|player\|(p[12])\|([^|]*)\|", txt))
    if US not in slots.values(): continue
    us = next(s for s, n in slots.items() if n == US)
    them = "p2" if us == "p1" else "p1"
    lines = [l for l in txt.split("\n") if l.startswith("|")]

    known = collections.defaultdict(set)
    for l in lines:
        m = re.match(rf"\|move\|{us}a: ([^|]+)\|([^|]+)\|", l)
        if m: known[m.group(1)].add(m.group(2))
    lvl = {}
    for m in re.finditer(rf"\|switch\|{us}a: ([^|,]+)[^|]*\|[^|,]+, L(\d+)", txt):
        lvl[m.group(1)] = int(m.group(2))

    ours = foe = None; turn = 0
    for l in lines:
        if l.startswith("|turn|"): turn = int(l.split("|")[2])
        m = re.match(rf"\|switch\|{us}a: ([^|,]+)", l)
        if m: ours = m.group(1)
        m = re.match(rf"\|switch\|{them}a: ([^|,]+)", l)
        if m: foe = m.group(1)
        m = re.match(rf"\|move\|{us}a: ([^|]+)\|([^|]+)\|", l)
        if not (m and ours and foe): continue
        at, ft, L = types_of(ours), types_of(foe), lvl.get(ours, 80)
        if not at or not ft: continue
        got = damage(m.group(2), at, ft, L)
        if got is None: continue
        decisions += 1
        ud, umlt, ucat = got
        best = None
        for alt in known[ours]:
            if alt == m.group(2): continue
            a = damage(alt, at, ft, L)
            if a and (best is None or a[0] > best[0]):
                best = (a[0], a[1], alt, a[2])
        if best and best[0] > max(ud, 1e-9) * MARGIN:
            flags.append((bid.group(1)[-4:], turn, ours, L, foe, m.group(2),
                          ud, umlt, ucat, best[2], best[0], best[1], best[3]))

same = [f for f in flags if f[8] == f[12]]
print(f"our damaging-move decisions judged : {decisions}")
print(f"flagged, a known move >{MARGIN:g}x better : {len(flags)}"
      f"  = {len(flags)/decisions:.1%}")
print(f"  of those, SAME category (no A/D confound) : {len(same)}"
      f"  = {len(same)/decisions:.1%}   <- the defensible number\n")
for b, t, o, L, f, um, ud, umlt, uc, bm, bd, bmlt, bc in flags:
    tag = "" if uc == bc else "   [cross-category: A/D unmodelled]"
    print(f"  ...{b} t{t:<2} L{L} {o} vs {f}")
    print(f"        used {um:<13} x{umlt:<5g} ~{ud:>4.0f} dmg   |"
          f"  had {bm:<13} x{bmlt:<5g} ~{bd:>4.0f}  ({bd/max(ud,1e-9):.1f}x){tag}")
