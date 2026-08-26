"""Replay -> turn-by-turn decision records, for both sides.

Both sides on purpose: every rate this produces is meaningless without the
human baseline from the same battles, on the same parser, with the same bugs.
"""
import re, json, pathlib, collections
import sys, pathlib as _pl
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

from poke_env.data import GenData
from poke_env.battle.pokemon_type import PokemonType

G = GenData.from_gen(1)
TC, DEX, MOVES = G.type_chart, G.pokedex, G.moves
SETS = json.load(open("rl/envs/data/gen1_randbats_sets.json"))
US = "nickgen1rbrlbot"
FIXED = {"seismictoss": "L", "nightshade": "L", "dragonrage": 40,
         "sonicboom": 20, "psywave": "L/2"}

def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def types_of(sp):
    e = DEX.get(norm(sp))
    if not e: return None
    t = [getattr(PokemonType, x.upper()) for x in e["types"]]
    return (t[0], t[1] if len(t) > 1 else None)

_MOVESET_CACHE = {}

def moveset_dist(sp, draws=4000):
    """(always, p_by_move) by ENUMERATING Showdown's own gen1 randomSet.

    Doing this by hand is what I got wrong first: `moves` is not filler, it is
    sampleNoReplace over the REMAINING slots, so when len(moves) + 1 exclusive
    fills the 4-move cap every entry in `moves` is taken with probability 1.
    That is why Raichu ALWAYS has Surf and Electabuzz ALWAYS has Psychic --
    which is what makes their 0x Electric moves indefensible rather than
    forced. Sampling the real generator removes the need to reason about it.
    """
    import random as _r, collections as _c
    key = norm(sp)
    if key in _MOVESET_CACHE: return _MOVESET_CACHE[key]
    s = SETS.get(key)
    if not s: return set(), {}
    from rl.envs.randbats_prior import _sample_set
    rng = _r.Random(12345)
    cnt = _c.Counter()
    for _ in range(draws):
        for m in _sample_set(s, rng): cnt[m] += 1
    p = {m: c / draws for m, c in cnt.items()}
    always = {m for m, q in p.items() if q > 0.999}
    _MOVESET_CACHE[key] = (always, p)
    return always, p

def guaranteed_moves(sp):
    always, p = moveset_dist(sp)
    return always, {m for m in p if m not in always}

def dmg(move_name, at, ft, level):
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
    bp = m["basePower"] * stab * mult
    return (((2 * level / 5 + 2) * bp / 50) + 2) * acc, mult, m["category"]

def parse(path):
    """-> (us_slot, decisions). A decision is one player's action on one turn,
    with the state as it stood BEFORE the action resolved."""
    txt = path.read_text(errors="ignore")
    slots = dict(re.findall(r"\|player\|(p[12])\|([^|]*)\|", txt))
    if US not in slots.values(): return None, None, None
    us = next(s for s, n in slots.items() if n == US)
    lines = [l for l in txt.split("\n") if l.startswith("|")]

    active = {"p1": None, "p2": None}
    hp = collections.defaultdict(lambda: 100.0)      # (side, species) -> %
    status = {}                                       # (side, species) -> str
    level = {}
    seen_moves = collections.defaultdict(set)         # (side, species) -> moves
    vol = collections.defaultdict(set)                # (side, species) -> volatiles
    decisions, turn = [], 0

    for i, l in enumerate(lines):
        f = l.split("|")[1:]
        if not f: continue
        tag = f[0]
        if tag == "turn":
            turn = int(f[1]); continue
        if tag == "switch" or tag == "drag":
            side = f[1][:2]; sp = f[1].split(": ", 1)[-1]
            m = re.search(r"L(\d+)", f[2])
            level[(side, sp)] = int(m.group(1)) if m else 80
            if len(f) > 3 and "/" in f[3]:
                a, b = f[3].split(" ")[0].split("/")
                hp[(side, sp)] = 100.0 * float(a) / float(b) if float(b) else 0.0
            active[side] = sp
            vol[(side, sp)] = set()
            if tag == "switch" and turn > 0:
                decisions.append(dict(turn=turn, side=side, kind="switch",
                                      actor=sp, foe=active["p2" if side == "p1" else "p1"],
                                      hp=hp[(side, sp)], action=f"switch->{sp}"))
            continue
        if tag == "move":
            side = f[1][:2]; sp = f[1].split(": ", 1)[-1]; mv = f[2]
            seen_moves[(side, sp)].add(mv)
            foe_side = "p2" if side == "p1" else "p1"
            foe = active[foe_side]
            decisions.append(dict(
                turn=turn, side=side, kind="move", actor=sp, foe=foe,
                action=mv, level=level.get((side, sp), 80),
                hp=hp[(side, sp)], foe_hp=hp[(foe_side, foe)] if foe else None,
                status=status.get((side, sp)), foe_status=status.get((foe_side, foe)),
                foe_vol=set(vol[(foe_side, foe)]) if foe else set(),
                self_vol=set(vol[(side, sp)]),
                line_idx=i))
            continue
        if tag in ("-damage", "-heal") and len(f) > 2 and "/" in f[2]:
            side = f[1][:2]; sp = f[1].split(": ", 1)[-1]
            part = f[2].split(" ")[0]
            if "/" in part:
                a, b = part.split("/")
                hp[(side, sp)] = 100.0 * float(a) / float(b) if float(b) else 0.0
        if tag == "-status":
            status[(f[1][:2], f[1].split(": ", 1)[-1])] = f[2]
        if tag == "-curestatus":
            status.pop((f[1][:2], f[1].split(": ", 1)[-1]), None)
        if tag == "faint":
            hp[(f[1][:2], f[1].split(": ", 1)[-1])] = 0.0
        if tag == "-start":
            vol[(f[1][:2], f[1].split(": ", 1)[-1])].add(f[2])
        if tag == "-end":
            vol[(f[1][:2], f[1].split(": ", 1)[-1])].discard(f[2])
    return us, decisions, lines

def replays():
    for p in sorted(pathlib.Path("results/ladder/replays").glob("*.html")):
        if re.search(r"gen1randombattle-\d{9,}", p.name):
            yield p
