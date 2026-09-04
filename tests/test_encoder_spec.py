"""F-08: the per-generation EncoderSpec seam, and the gate that says gen 1
did not move.

`rl/envs/encoder_spec.py` holds the encoder's per-gen tables as data; the
fill helpers in `rl/envs/showdown.py` read a `spec` argument (default GEN1)
and the module names importers pin against are GEN1's. Only gen 1 is
registered — `spec_for_format` refuses every other generation by name, and
that refusal is the seam (gen 4 keeps poke-env's Discrete(10) but loses the
encoder; gen 9 widens the action space to 26).

THE ONE RULE the refactor had to keep: the gen-1 encoding is BIT-IDENTICAL
at every flag combination. The hash gate below replays the six R0-5 tapes
(tests/test_encoder_ids_tapes.py's corpus, through poke-env's own parser)
and sha256s every `embed_battle` vector in a subprocess per flag combo; the
expected lines were captured on the pre-refactor encoder (commit d546228)
and are pinned verbatim. A changed hash is a changed encoding — fix the
code, never the golden. Tapes are local collection artifacts (gitignored);
the gate skips loudly where they are absent.

Two things the hash gate CANNOT see, covered separately below:
  - a helper that ignores its `spec` argument and reads the module literal
    emits identical gen-1 bytes. The `_GEN2_SKETCH` tests are that class's
    cover — one assertion per spec-threaded helper.
  - `ENCODER_FINGERPRINT`, the third invariant of the ONE RULE and the only
    record of WHICH semantics a checkpoint carries, is pinned per flag combo
    in `FINGERPRINTS`.
"""

import ast
import dataclasses
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from gymnasium import spaces
from poke_env.battle.move import Move
from poke_env.battle.pokemon_type import PokemonType
from poke_env.environment import SinglesEnv

from rl.envs import showdown as sd
from rl.envs.encoder_spec import GEN1, spec_for_format

_ROOT = Path(__file__).resolve().parents[1]

# Same corpus as the R0-5 gate (test_encoder_ids_tapes.py): the two
# hl-shaping tapes plus the 6-lane P4 set, 6000 decisions cap.
TAPES = [
    _ROOT / "data/fp_tapes2/run_92564.jsonl",
    _ROOT / "data/fp_tapes/run_90336.jsonl",
    _ROOT / "data/fp_tapes3/run_98827.jsonl",
    _ROOT / "data/fp_tapes_all/run_4106.jsonl",
    _ROOT / "data/fp_tapes_all/run_4115.jsonl",
    _ROOT / "data/fp_tapes_all/run_4121.jsonl",
]

# Captured on the pre-F-08 encoder (commit d546228's rl/envs/showdown.py),
# each in a process with ONLY the named flags set. The first three are the
# F-08 brief's oracle, quoted verbatim; the last two extend it to the fourth
# encoder flag (POKEMON_RL_NO_SET_PRIOR, which changes obs SEMANTICS at
# constant OBS_DIM) and were captured the same way against the same base
# commit, 2026-09-04.
ORACLE = {
    (): "OBS_DIM=612 decisions=6000 sha256=e0217c10dc8678af4fba93adbc5ef76f930e9f5c4b3533d669d22f06328b509d",
    ("POKEMON_RL_ENCODER_V2",): "OBS_DIM=808 decisions=6000 sha256=273cd675b190cb7e4ca2a1253430f92a0474649e96c1da588f805bc97908a13e",
    ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"): "OBS_DIM=828 decisions=6000 sha256=0be192a8711def10cff546a12271156e006c982f7a739d16161da34c4d961ef6",
    ("POKEMON_RL_NO_SET_PRIOR",): "OBS_DIM=612 decisions=6000 sha256=8c2956c4bde8eb89d30c17391b4a86e44aa8e81ea0dc38feaef2d016482eb769",
    ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS", "POKEMON_RL_NO_SET_PRIOR"): "OBS_DIM=828 decisions=6000 sha256=ac57b7f88a54e209229a38ae897e8570271566f3f6619de2414933bf6044daee",
}

# The encoder reads these at import; a child must see exactly the combo
# under test, never the parent's inherited exports.
_ENCODER_VARS = ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS", "POKEMON_RL_NO_SET_PRIOR")

_HASH_CHILD = r"""
import hashlib
import json
import logging
import sys

from poke_env.battle import Battle
from poke_env.data import GenData

from rl.envs.showdown import OBS_DIM, embed_battle

MESSAGES_TO_IGNORE = {"t:", "expire", "uhtmlchange"}
LOGGER = logging.getLogger("tape_replay")
LOGGER.addHandler(logging.NullHandler())
TYPE_CHART = GenData.from_gen(1).type_chart
TARGET = 6000


def iter_events(path):
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def infer_username(path):
    for ev in iter_events(path):
        if ev["k"] != "m":
            continue
        for line in ev["v"].split("\n"):
            parts = line.split("|")
            if len(parts) > 2 and parts[1] == "updateuser" and parts[2].strip():
                name = parts[2].strip()
                if not name.lower().startswith("guest "):
                    return name
    return None


def apply_message(battle, raw, state):
    for line in raw.split("\n")[1:]:
        sm = line.split("|")
        if len(sm) <= 1:
            continue
        tag = sm[1]
        if tag == "":
            battle.parse_message(sm)
        elif tag in MESSAGES_TO_IGNORE:
            continue
        elif tag == "request":
            if len(sm) > 2 and sm[2]:
                req = json.loads(sm[2])
                battle.parse_request(req)
                state["request"] = req
        elif tag == "win":
            battle.won_by(sm[2])
        elif tag == "tie":
            battle.tied()
        elif tag in ("error", "bigerror"):
            continue
        else:
            battle.parse_message(sm)


h = hashlib.sha256()
decisions = 0
for path in sys.argv[1:]:
    username = infer_username(path)
    assert username, path
    battles, states = {}, {}
    for ev in iter_events(path):
        if decisions >= TARGET:
            break
        if ev["k"] == "m":
            head = ev["v"].split("\n", 1)[0]
            if not head.startswith(">battle-"):
                continue
            room = head[1:]
            if room not in battles:
                battles[room] = Battle(room, username, LOGGER, gen=1)
                states[room] = {"request": None}
            try:
                apply_message(battles[room], ev["v"], states[room])
            except Exception:
                states[room]["request"] = None  # poisoned: skip its decisions
            continue
        room = ev["tag"]
        if room not in battles:
            continue
        req = states[room]["request"]
        if req is None or req.get("rqid") != ev.get("rqid"):
            continue
        vec = embed_battle(battles[room], TYPE_CHART)
        assert vec.shape == (OBS_DIM,) and vec.dtype.name == "float32", (vec.shape, vec.dtype)
        h.update(vec.tobytes())
        decisions += 1

print(f"OBS_DIM={OBS_DIM} decisions={decisions} sha256={h.hexdigest()}")
"""

_DIMS_CHILD = r"""
from rl.envs import showdown as sd
print(sd.OBS_DIM, sd.MON_DIM, sd.MOVE_DIM, sd.ID_DIM)
print(sorted(sd.ENCODER_FINGERPRINT.items()))
"""

# The fingerprint each flag combo above must stamp into meta.yaml
# (rl/train.py) and the BC metrics (scripts/train_bc.py). Same keys as ORACLE
# on purpose: the hash gate pins the BYTES a combo emits, this pins the record
# of WHICH semantics those bytes are, and nothing else in the suite asserts
# `set_prior` / `recharge_fix` / the fingerprint's own `obs_dim` at all. An
# edit that dropped or inverted a key would otherwise leave every test green
# and make checkpoints unattributable — the incident the fingerprint's own
# comment in rl/envs/showdown.py cites.
FINGERPRINTS = {
    (): {"obs_dim": 612, "encoder": "v1", "set_prior": True, "recharge_fix": True, "ids": False},
    ("POKEMON_RL_ENCODER_V2",): {"obs_dim": 808, "encoder": "v2", "set_prior": True, "recharge_fix": True, "ids": False},
    ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"): {"obs_dim": 828, "encoder": "v2", "set_prior": True, "recharge_fix": True, "ids": True},
    ("POKEMON_RL_NO_SET_PRIOR",): {"obs_dim": 612, "encoder": "v1", "set_prior": False, "recharge_fix": True, "ids": False},
    ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS", "POKEMON_RL_NO_SET_PRIOR"): {"obs_dim": 828, "encoder": "v2", "set_prior": False, "recharge_fix": True, "ids": True},
}


def _child_env(*flags: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _ENCODER_VARS}
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(_ROOT), env.get("PYTHONPATH", "")) if p
    )
    for flag in flags:
        env[flag] = "1"
    return env


def _run_child(src: str, *args: str, flags: tuple[str, ...] = ()) -> str:
    result = subprocess.run(
        [sys.executable, "-c", src, *args],
        env=_child_env(*flags),
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


# --- (i) the registry is the seam ------------------------------------------


def test_spec_for_format_registers_gen1_only():
    assert spec_for_format("gen1randombattle") is GEN1
    assert spec_for_format("gen1ou") is GEN1  # keyed by generation, not format
    with pytest.raises(NotImplementedError, match=r"no EncoderSpec for gen 4"):
        spec_for_format("gen4randombattle")
    with pytest.raises(NotImplementedError, match=r"gen 9.*26 actions") as err:
        spec_for_format("gen9randombattle")
    # The message names what is missing, so the refusal is a work list.
    for piece in ("type table", "items and abilities", "set prior", "strides"):
        assert piece in str(err.value), piece


# --- (ii) the action space: 10 through gen 5, the gen-9 break ---------------


def test_n_actions_is_poke_envs_and_gen9_widens():
    assert sd.N_ACTIONS == 10 == GEN1.n_actions == SinglesEnv.get_action_space_size(1)
    assert GEN1.n_switches + GEN1.n_moves == GEN1.n_actions  # no gimmick slots
    assert [SinglesEnv.get_action_space_size(g) for g in range(1, 10)] == [
        10, 10, 10, 10, 10, 14, 18, 22, 26
    ]


# --- (iii) the module constants are GEN1's ---------------------------------


def test_module_constants_are_gen1_derived():
    assert sd.GEN1_TYPES is GEN1.types
    assert sd._TYPE_INDEX is GEN1.type_index
    assert sd._STATUS_INDEX is GEN1.status_index
    assert sd._BOOST_KEYS is GEN1.boost_keys
    assert sd._BASE_STAT_KEYS is GEN1.base_stat_keys
    assert sd._VOLATILES is GEN1.volatiles
    assert sd._SPECIAL_MOVE_IDS is GEN1.special_move_ids
    assert sd.GLOBAL_DIM == 6
    assert sd.ACTIVE_DIM == GEN1.active_dim
    assert sd.MON_DIM == GEN1.mon_dim_v1 + (1 if sd._ENCODER_V2 else 0)
    assert sd.MOVE_DIM == GEN1.move_dim_v1 + (sd.EFFECT_DIM if sd._ENCODER_V2 else 0)
    assert sd.OBS_DIM == (
        sd.GLOBAL_DIM + 6 * sd.MON_DIM + sd.ACTIVE_DIM + 4 * sd.MOVE_DIM
        + 6 * (sd.MON_DIM + 1) + sd.ACTIVE_DIM + 4 * sd.MOVE_DIM + sd.ID_DIM
    )


def test_gen1_tables_are_the_literals_they_replaced():
    # The exact pre-F-08 tables, in order: the one-hot layout is the order.
    assert [t.name for t in GEN1.types] == [
        "BUG", "DRAGON", "ELECTRIC", "FIGHTING", "FIRE", "FLYING", "GHOST",
        "GRASS", "GROUND", "ICE", "NORMAL", "POISON", "PSYCHIC", "ROCK", "WATER",
    ]
    assert [s.name for s in GEN1.statuses] == ["BRN", "FRZ", "PAR", "PSN", "SLP", "TOX"]
    assert GEN1.boost_keys == ("accuracy", "atk", "def", "evasion", "spa", "spd", "spe")
    assert GEN1.base_stat_keys == ("hp", "atk", "def", "spa", "spe")
    assert [e.name for e in GEN1.volatiles] == [
        "CONFUSION", "FOCUS_ENERGY", "LEECH_SEED", "MUST_RECHARGE",
        "PARTIALLY_TRAPPED", "REFLECT", "SUBSTITUTE",
    ]
    assert GEN1.special_move_ids == frozenset({"fight", "struggle", "recharge"})
    assert GEN1.species_num_range == (1, 151) and GEN1.move_num_range == (1, 165)
    # The v1 layout the docstrings quote, as numbers.
    assert (GEN1.mon_status_off, GEN1.mon_level_off, GEN1.mon_stats_off,
            GEN1.mon_types_off, GEN1.mon_matchup_off, GEN1.mon_dim_v1) == (3, 9, 10, 15, 30, 32)
    assert (GEN1.active_volatiles_off, GEN1.active_counter_off, GEN1.active_dim) == (7, 14, 16)
    assert (GEN1.move_type_off, GEN1.move_dim_v1) == (8, 23)
    # Frozen, and hashable BY FIELDS (the hash is cached, not identity-based):
    # the id lookups take the spec into an lru_cache key per mon.
    with pytest.raises(dataclasses.FrozenInstanceError):
        GEN1.gen = 4  # type: ignore[misc]
    assert hash(GEN1) == hash(dataclasses.replace(GEN1))
    assert hash(GEN1) != hash(dataclasses.replace(GEN1, gen=2))


def test_bare_process_is_612_v1():
    dims, _ = _run_child(_DIMS_CHILD).splitlines()
    assert dims.split() == ["612", "32", "23", "0"], dims  # OBS/MON/MOVE/ID


@pytest.mark.parametrize(
    "flags", list(FINGERPRINTS),
    ids=["bare", "v2", "v2+ids", "bare+noprior", "v2+ids+noprior"],
)
def test_fingerprint_records_the_semantics_the_hash_gate_pins(flags):
    dims, fingerprint = _run_child(_DIMS_CHILD, flags=flags).splitlines()
    stamped = dict(ast.literal_eval(fingerprint))
    assert stamped == FINGERPRINTS[flags], (flags, stamped)
    assert stamped["obs_dim"] == int(dims.split()[0])  # the stamp is the truth


def test_every_hashed_combo_is_distinguishable():
    # bare vs bare+noprior (and v2+ids vs v2+ids+noprior) share an OBS_DIM and
    # differ only in obs SEMANTICS: different bytes, and — the part nothing
    # asserted before — a different fingerprint, so a checkpoint's meta.yaml
    # says which of the two it trained under.
    assert set(FINGERPRINTS) == set(ORACLE), "a hashed combo with no fingerprint"
    stamps = [tuple(sorted(fp.items())) for fp in FINGERPRINTS.values()]
    assert len(set(stamps)) == len(stamps) == len(set(ORACLE.values()))


# --- (iv) the encoding-hash gate --------------------------------------------


@pytest.mark.skipif(
    not all(t.exists() for t in TAPES),
    reason="local FP tapes absent — the F-08 hash gate must run on the training box",
)
@pytest.mark.parametrize(
    "flags", list(ORACLE),
    ids=["bare", "v2", "v2+ids", "bare+noprior", "v2+ids+noprior"],
)
def test_gen1_encoding_hash_is_pinned(flags):
    out = _run_child(_HASH_CHILD, *[str(t) for t in TAPES], flags=flags)
    assert out == ORACLE[flags], f"encoding changed under {flags or 'no flags'}:\n{out}\n{ORACLE[flags]}"


# --- (v) fake_spaces, the fill helpers, and the embed_battle refusal --------


def test_fake_spaces_shapes():
    obs_space, act_space = sd.fake_spaces()
    assert isinstance(obs_space, spaces.Box) and obs_space.shape == (sd.OBS_DIM,)
    assert obs_space.dtype == np.float32
    assert float(obs_space.low[0]) == -1.0 and float(obs_space.high[0]) == 4.0
    assert isinstance(act_space, spaces.Discrete) and int(act_space.n) == 10
    # eval_checkpoint's shim passes the checkpoint's own width.
    shim_obs, _ = sd.fake_spaces(obs_dim=sd.OBS_DIM - 20)
    assert shim_obs.shape == (sd.OBS_DIM - 20,)
    with pytest.raises(NotImplementedError, match="gen 9"):
        sd.fake_spaces("gen9randombattle")


# A sketch of what a second spec does to the layout — 17 types, a real Special
# Defense, gen-2 id ranges, and two SYNTHETIC boost slots whose only job is to
# push the volatile block off gen 1's offset (poke-env exposes the same seven
# boost keys in every generation, so nothing real moves that block). NOT a
# gen-2 encoder: no items, no gen-2 volatiles, no side-condition block, no
# prior.
#
# WHY IT EXISTS: the tape hash gate above is structurally BLIND to a helper
# that ignores its `spec` argument and reads the module literal instead — at
# gen 1 the two agree bit-for-bit, so the gen-1 digest cannot move. Every
# helper that gained a `spec` parameter therefore gets one assertion here that
# a "kept the gen-1 literal" implementation fails. That silent-wrong-number
# class (e.g. _species_id mapping every gen-2+ species to 0 = unknown) is
# exactly what the gen-4 chapter would hit first.
_GEN2_SKETCH = dataclasses.replace(
    GEN1,
    gen=2,
    types=GEN1.types + (PokemonType.DARK, PokemonType.STEEL),
    base_stat_keys=("hp", "atk", "def", "spa", "spd", "spe"),
    boost_keys=GEN1.boost_keys + ("_probe1", "_probe2"),
    species_num_range=(1, 251),
    move_num_range=(1, 251),
)


def test_fill_mon_offsets_follow_the_spec_not_the_module():
    # One more base stat and two more types push everything after them out.
    assert (_GEN2_SKETCH.mon_stats_off, _GEN2_SKETCH.mon_types_off,
            _GEN2_SKETCH.mon_matchup_off, _GEN2_SKETCH.mon_dim_v1) == (10, 16, 33, 35)
    mon = SimpleNamespace(
        current_hp_fraction=1.0, fainted=False, status=None, level=100,
        base_stats={k: 255 for k in _GEN2_SKETCH.base_stat_keys},
        types=(PokemonType.NORMAL,),
    )
    vec = np.zeros(_GEN2_SKETCH.mon_dim_v1, dtype=np.float32)
    # foe=None skips the matchups, so no type chart is needed here.
    sd._fill_mon(vec, 0, mon, None, None, None, spec=_GEN2_SKETCH)
    normal = _GEN2_SKETCH.type_index[PokemonType.NORMAL]
    assert vec[_GEN2_SKETCH.mon_types_off + normal] == 1.0
    # ... and NOT where gen 1 would have put it (one slot per extra stat).
    assert vec[GEN1.mon_types_off + normal] == 0.0
    # The sixth base stat occupies gen 1's first type slot.
    assert vec[GEN1.mon_types_off] == 1.0 and vec[_GEN2_SKETCH.mon_level_off] == 1.0


def test_fill_active_offsets_follow_the_spec_not_the_module():
    # Two extra boost slots push the volatile block from 7..13 to 9..15 and the
    # counter/preparing pair from 14/15 to 16/17.
    assert (_GEN2_SKETCH.active_volatiles_off, _GEN2_SKETCH.active_counter_off,
            _GEN2_SKETCH.active_dim) == (9, 16, 18)
    mon = SimpleNamespace(
        boosts={k: 6 for k in _GEN2_SKETCH.boost_keys},  # 6/6 -> 1.0 each
        effects={},          # no Effect volatile set...
        must_recharge=True,  # ...but the D13(a) bool is, at volatiles[3]
        status_counter=8,    # /16 (the toxic cap) -> 0.5
        preparing=True,
    )
    vec = np.zeros(_GEN2_SKETCH.active_dim + 2, dtype=np.float32)
    sd._fill_active(vec, 0, mon, spec=_GEN2_SKETCH)
    # A _BOOST_KEYS / _VOLATILES literal writes the boosts at 0..6, this
    # MUST_RECHARGE bit at 10 and the counter/preparing pair at 14/15 — none of
    # which is this vector.
    assert vec.tolist() == [1.0] * 9 + [0, 0, 0, 1.0, 0, 0, 0] + [0.5, 1.0, 0, 0]


def test_fill_move_type_onehot_follows_the_spec_not_the_module():
    crunch = Move("crunch", gen=2)  # DARK — and SPECIAL in gen-2 move data
    vec = np.zeros(_GEN2_SKETCH.move_dim_v1 + sd.EFFECT_DIM, dtype=np.float32)
    sd._fill_move(vec, 0, crunch, None, None, spec=_GEN2_SKETCH)
    dark = _GEN2_SKETCH.type_index[PokemonType.DARK]
    assert (_GEN2_SKETCH.move_type_off, dark, _GEN2_SKETCH.move_dim_v1) == (8, 15, 25)
    # THE DISCRIMINATOR: a `_TYPE_INDEX` literal has no DARK key, so `.get`
    # returns None and the one-hot is never written at all.
    assert vec[8 + dark] == vec[23] == 1.0
    assert not vec[8:23].any()  # gen 1's 15-wide window, empty either way
    # physical/special is per-move from poke-env, never gen 1's type rule.
    assert vec[5] == 0.0 and vec[6] == 0.0


def test_id_lookups_follow_the_spec_not_the_module():
    crunch = Move("crunch", gen=2)
    # The spec supplies BOTH the dex/move table generation and the valid range.
    assert sd._species_id("chikorita", _GEN2_SKETCH) == 152
    assert sd._move_id(crunch, _GEN2_SKETCH) == 242
    # Under the pre-F-08 literals (GenData.from_gen(1); 1..151 / 1..165) both
    # are 0 = unknown — a silent wrong number, not an error.
    assert sd._species_id("chikorita", GEN1) == 0
    assert sd._move_id(crunch, GEN1) == 0
    # ...and gen 1's own ids do not move under the wider range.
    assert sd._species_id("bulbasaur", GEN1) == sd._species_id("bulbasaur", _GEN2_SKETCH) == 1


def test_move_slots_aliased_reads_the_specs_special_moves():
    battle = SimpleNamespace(available_moves=[SimpleNamespace(id="fight")])
    assert sd._move_slots_aliased(battle, spec=GEN1) is True
    # poke-env's SPECIAL_MOVES are per-gen data too: with none declared, the
    # same battle is NOT an aliased turn.
    no_special = dataclasses.replace(_GEN2_SKETCH, special_move_ids=frozenset())
    assert sd._move_slots_aliased(battle, spec=no_special) is False


def test_embed_battle_refuses_a_non_gen1_spec():
    # Refused before any battle attribute is read: the strides and OBS_DIM are
    # module-level GEN1 values, the v2 effect block is gen-1 Move data and the
    # set prior is gen-1 randbats — a second spec is not encodable yet.
    with pytest.raises(NotImplementedError, match="GEN1 spec only"):
        sd.embed_battle(SimpleNamespace(), None, _GEN2_SKETCH)
    # Even a field-equal copy: the module derived its constants from the
    # singleton, so identity is the honest test.
    with pytest.raises(NotImplementedError, match="GEN1 spec only"):
        sd.embed_battle(SimpleNamespace(), None, dataclasses.replace(GEN1))
