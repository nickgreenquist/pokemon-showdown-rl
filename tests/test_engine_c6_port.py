"""C6 on the RUST encoder (IDEAS 4.6 form (a), ported 2026-09-20): with
`Tables(..., c6=True)` the seven fixed-damage move ids carry an effective power
in [+1] and an immunity-only multiplier in [+4]; every other slot, every other
move and the whole c6=False encoding are untouched.

The contract is CROSS-IMPLEMENTATION and BITWISE: the same move block is filled
by `rl/envs/showdown.py::_fill_move` (the reference, under the same flag) and
by `Tables.encode` over a hand-built observable state, and the 46 floats must
be identical -- the P-1 shape, without tapes. The reference reads its flag at
import, so each flag setting runs in its own child process; the Rust flag is an
explicit kwarg, so a child also asserts on/off differ ONLY in the C6 slots.
Needs the `pkmn_gen1` extension (the pkmn-engine-port env); skipped elsewhere.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first (pkmn-engine-port env)")

_ROOT = Path(__file__).resolve().parents[1]
_ENCODER_VARS = ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS",
                 "POKEMON_RL_NO_SET_PRIOR", "POKEMON_RL_ENCODER_C6")

_CHILD = r"""
import json, os
from types import SimpleNamespace
import numpy as np
import pkmn_gen1
from poke_env.battle.pokemon_type import PokemonType as PT
from poke_env.data import GenData
from rl.envs import showdown as sd
from rl.envs.encoder_spec import GEN1
from rl.envs.engine_tables import build_tables

C6 = bool(os.environ.get("POKEMON_RL_ENCODER_C6"))
assert sd.ENCODER_FINGERPRINT["c6"] is C6 and sd.OBS_DIM == 828
assert pkmn_gen1.ENCODER_C6 is True, "the installed extension predates the port"
TC = GenData.from_gen(1).type_chart
TI = lambda t: -1 if t is None else GEN1.type_index[t]
MOVES = {"seismictoss": 69, "superfang": 162, "counter": 68, "thunderbolt": 85,
         "nightshade": 101, "sonicboom": 49, "dragonrage": 82, "psywave": 149}
OWN_MOVE_OFF = sd.GLOBAL_DIM + 6 * sd.MON_DIM + sd.ACTIVE_DIM

def mon(species, t1, t2, hp, active):
    return {"species": species, "base_stats": [100, 80, 70, 60, 50], "type_1": TI(t1),
            "type_2": TI(t2), "hp": float(hp), "fainted": False, "is_active": active,
            "status": None, "level": 80}
def seat(team, moves):
    return {"team": team, "active_slot": 0, "boosts": [0] * 7, "volatiles": [False] * 7,
            "status_counter": 0, "preparing": False,
            "moves": [{"id": MOVES[m], "prob": 1.0, "pp": int(pkmn_gen1.max_pp(MOVES[m])),
                       "max_pp": int(pkmn_gen1.max_pp(MOVES[m]))} for m in moves]}
def state(own_moves, foe_t1, foe_t2, foe_hp):
    return {"turn": 5, "force_switch": False, "trapped": False, "aliased": False,
            "own": seat([mon(113, PT.NORMAL, None, 1.0, True)], own_moves),
            "opp": seat([mon(94, foe_t1, foe_t2, foe_hp, True)], [])}

def py_block(move_id, foe):
    vec = np.zeros(sd.MOVE_DIM, dtype=np.float32)
    mv = sd._move_obj(move_id)
    sd._fill_move(vec, 0, mv, foe, TC)
    return vec

tables, _ = build_tables(c6=C6)
assert tables.c6 is C6
cases = [  # (own moves, foe types, foe hp)
    (["seismictoss", "superfang", "counter", "thunderbolt"], PT.NORMAL, None, 1.0),
    (["seismictoss", "superfang", "nightshade", "thunderbolt"], PT.GHOST, PT.POISON, 0.25),
    (["sonicboom", "dragonrage", "psywave", "counter"], PT.WATER, None, 0.5),
]
out = {"c6": C6, "mismatch": [], "slots": {}}
for moves, t1, t2, hp in cases:
    obs = np.asarray(tables.encode(state(moves, t1, t2, hp)), dtype=np.float32)
    assert obs.shape == (828,)
    foe = SimpleNamespace(type_1=t1, type_2=t2, current_hp_fraction=hp)
    for j, m in enumerate(moves):
        rust = obs[OWN_MOVE_OFF + j * sd.MOVE_DIM: OWN_MOVE_OFF + (j + 1) * sd.MOVE_DIM]
        ref = py_block(m, foe)
        # own moves: prob 1.0 and full PP on both sides by construction
        if not np.array_equal(rust.view(np.uint32), ref.view(np.uint32)):
            out["mismatch"].append({"move": m, "foe": str(t1), "rust": rust.tolist(), "ref": ref.tolist()})
        out["slots"][f"{m}_vs_{t1.name.lower()}"] = [round(float(rust[1]), 4), round(float(rust[4]), 4)]
# on/off differ ONLY in the C6 slots of C6 moves (an in-process check: the Rust
# flag is a kwarg, so both tables live in one process)
other, _ = build_tables(c6=not C6)
diff_slots = set()
for moves, t1, t2, hp in cases:
    a = np.asarray(tables.encode(state(moves, t1, t2, hp)))
    b = np.asarray(other.encode(state(moves, t1, t2, hp)))
    for k in np.flatnonzero(a != b):
        k = int(k)
        j, r = divmod(k - OWN_MOVE_OFF, sd.MOVE_DIM)
        diff_slots.add((moves[j] if 0 <= j < 4 and 0 <= k - OWN_MOVE_OFF else f"off{k}", r))
out["diff_slots"] = sorted(map(list, diff_slots))
print(json.dumps(out))
"""


def _run(*flags):
    env = {k: v for k, v in os.environ.items() if k not in _ENCODER_VARS}
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(_ROOT), env.get("PYTHONPATH", "")) if p)
    for f in flags:
        env[f] = "1"
    r = subprocess.run([sys.executable, "-c", _CHILD], env=env, cwd=_ROOT,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-4000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_c6_off_is_bitwise_the_reference_and_the_pinned_defect():
    d = _run("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS")
    assert d["c6"] is False and d["mismatch"] == [], d["mismatch"][:1]
    assert d["slots"]["seismictoss_vs_normal"] == [0.01, 2.0]
    assert d["slots"]["superfang_vs_normal"] == [0.01, 1.0]
    assert d["slots"]["thunderbolt_vs_normal"] == [0.95, 1.0]


def test_c6_on_is_bitwise_the_reference_and_touches_only_the_c6_slots():
    d = _run("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS", "POKEMON_RL_ENCODER_C6")
    assert d["c6"] is True and d["mismatch"] == [], d["mismatch"][:1]
    s = d["slots"]
    assert s["seismictoss_vs_normal"] == [1.15, 1.0]      # 2x dropped: fixed damage
    assert s["superfang_vs_normal"] == [2.2, 1.0]
    assert s["counter_vs_normal"] == [1.0, 1.0]
    assert s["thunderbolt_vs_normal"] == [0.95, 1.0]      # untouched
    assert s["seismictoss_vs_ghost"] == [1.15, 0.0]       # immunity kept
    assert s["superfang_vs_ghost"] == [0.55, 0.0]         # scales with HP; Normal cannot touch Ghost
    assert s["nightshade_vs_ghost"] == [1.15, 1.0]        # 2x dropped
    assert s["sonicboom_vs_water"] == [0.26, 1.0]
    assert s["dragonrage_vs_water"] == [0.56, 1.0]
    assert s["psywave_vs_water"] == [0.85, 1.0]
    # every on/off difference sits in [+1] or [+4] of a C6 move
    c6_moves = {"seismictoss", "superfang", "counter", "nightshade", "sonicboom", "dragonrage", "psywave"}
    assert d["diff_slots"], "the flag changed nothing"
    for m, r in d["diff_slots"]:
        assert m in c6_moves and r in (1, 4), (m, r)
