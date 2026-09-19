"""C6 (IDEAS 4.6 form (a), 2026-09-19): the fixed-damage move slots. Flag OFF
must be the pinned defect (bit-identical to every banked checkpoint's encoder);
flag ON carries an effective power and an immunity-only type multiplier. The
encoder reads its flags at import, so each combo runs in a child process."""
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ENCODER_VARS = ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS",
                 "POKEMON_RL_NO_SET_PRIOR", "POKEMON_RL_ENCODER_C6")

_CHILD = r"""
import json
from types import SimpleNamespace
import numpy as np
from poke_env.battle.pokemon_type import PokemonType
from poke_env.data import GenData
from rl.envs import showdown as sd

TC = GenData.from_gen(1).type_chart
def foe(t1, t2=None, frac=0.5):
    return SimpleNamespace(type_1=t1, type_2=t2, current_hp_fraction=frac)
def slots(move_id, f):
    vec = np.zeros(sd.MOVE_DIM, dtype=np.float32)
    sd._fill_move(vec, 0, sd._move_obj(move_id), f, TC)
    return [round(float(vec[1]), 4), round(float(vec[4]), 4)]
out = {
    "c6": sd.ENCODER_FINGERPRINT["c6"],
    "seismictoss_vs_normal": slots("seismictoss", foe(PokemonType.NORMAL)),
    "seismictoss_vs_ghost": slots("seismictoss", foe(PokemonType.GHOST, PokemonType.POISON)),
    "seismictoss_vs_psychic": slots("seismictoss", foe(PokemonType.PSYCHIC)),
    "nightshade_vs_normal": slots("nightshade", foe(PokemonType.NORMAL)),
    "superfang_full": slots("superfang", foe(PokemonType.WATER, frac=1.0)),
    "superfang_quarter": slots("superfang", foe(PokemonType.ROCK, PokemonType.GROUND, frac=0.25)),
    "superfang_unknown_foe": slots("superfang", None),
    "counter_vs_normal": slots("counter", foe(PokemonType.NORMAL)),
    "thunderbolt_vs_water": slots("thunderbolt", foe(PokemonType.WATER)),
}
print(json.dumps(out))
"""


def _run(*flags):
    env = {k: v for k, v in os.environ.items() if k not in _ENCODER_VARS}
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(_ROOT), env.get("PYTHONPATH", "")) if p)
    for f in flags:
        env[f] = "1"
    r = subprocess.run([sys.executable, "-c", _CHILD], env=env, cwd=_ROOT,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    import json
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_flag_off_is_the_pinned_defect():
    d = _run("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS")
    assert d["c6"] is False
    assert d["seismictoss_vs_normal"] == [0.01, 2.0]      # basePower 1, spurious 2x
    assert d["superfang_full"] == [0.01, 1.0]
    assert d["counter_vs_normal"] == [0.01, 2.0]
    assert d["thunderbolt_vs_water"] == [0.95, 2.0]


def test_flag_on_carries_effective_power_and_immunity_only_multiplier():
    d = _run("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS", "POKEMON_RL_ENCODER_C6")
    assert d["c6"] is True
    assert d["seismictoss_vs_normal"] == [1.15, 1.0]      # 2x dropped: fixed damage
    assert d["seismictoss_vs_ghost"] == [1.15, 0.0]       # immunity kept
    assert d["seismictoss_vs_psychic"] == [1.15, 1.0]     # 0.5x dropped
    assert d["nightshade_vs_normal"] == [1.15, 0.0]       # Ghost cannot touch Normal
    assert d["superfang_full"] == [2.2, 1.0]
    assert d["superfang_quarter"] == [0.55, 1.0]          # scales with the foe's HP; 0.5x dropped
    assert d["superfang_unknown_foe"][0] == 1.1           # 0.5 when the foe is unknown
    assert d["counter_vs_normal"] == [1.0, 1.0]
    assert d["thunderbolt_vs_water"] == [0.95, 2.0]       # untouched
