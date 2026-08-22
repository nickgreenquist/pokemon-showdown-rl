"""CH3 R1 bridge tests: stat formula pins, volatile-map integrity, the
determinizer's containment law, and the end-to-end stub -> State ->
generate_instructions pipeline. Offline: no server, no checkpoints."""

from types import SimpleNamespace

import numpy as np
import pytest
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.move import Move as PEMove

from rl.search.bridge import (
    EFFECT_VOLATILE_MAP,
    GEN1_ENGINE_VOLATILES,
    BridgeCounters,
    battle_to_state,
    gen1_stat,
    is_locked_turn,
)
from rl.search.determinize import sample_determinization


def test_gen1_stat_pinned_vectors():
    # Tauros L100, max DV/statexp: the two classic RBY numbers
    assert gen1_stat(75, 100, hp=True) == 353
    assert gen1_stat(110, 100) == 318
    # level scaling: Tauros at randbats level 68
    assert gen1_stat(110, 68) == 217


def test_volatile_map_within_engine_enum():
    assert set(EFFECT_VOLATILE_MAP.values()) <= GEN1_ENGINE_VOLATILES


def _mon(species, moves, level=68, hp_frac=1.0, active=False, stats=None):
    base_stats = {"hp": 75, "atk": 100, "def": 95, "spa": 70, "spd": 70, "spe": 110}
    return SimpleNamespace(
        species=species,
        level=level,
        current_hp=int(300 * hp_frac),
        max_hp=300,
        current_hp_fraction=hp_frac,
        fainted=hp_frac == 0.0,
        status=None,
        status_counter=0,
        base_stats=base_stats,
        stats=stats or {"atk": 200, "def": 190, "spa": 150, "spd": 150, "spe": 220},
        types=[PokemonType.NORMAL],
        type_1=PokemonType.NORMAL,
        type_2=None,
        boosts=dict.fromkeys(("accuracy", "atk", "def", "evasion", "spa", "spd", "spe"), 0),
        effects={},
        preparing=False,
        must_recharge=False,
        moves={m: PEMove(m, gen=1) for m in moves},
    )


def _battle():
    ours = _mon("tauros", ["bodyslam", "blizzard", "earthquake", "hyperbeam"])
    theirs = _mon("chansey", ["softboiled"], level=76)
    return SimpleNamespace(
        active_pokemon=ours,
        opponent_active_pokemon=theirs,
        team={"p1: Tauros": ours},
        opponent_team={"p2: Chansey": theirs},
        turn=5,
        force_switch=False,
        trapped=False,
        available_moves=list(ours.moves.values()),
    )


def test_determinizer_containment_and_determinism():
    b = _battle()
    d1 = sample_determinization(b, np.random.default_rng(42))
    d2 = sample_determinization(b, np.random.default_rng(42))
    # same key -> identical determinization (determinism clause D2)
    assert {s: spec["moves"] for s, spec in d1["opponents"].items()} == {
        s: spec["moves"] for s, spec in d2["opponents"].items()
    }
    # the active's slots are the encoder's four (containment, MF-5b):
    # softboiled revealed must be among them
    assert "softboiled" in d1["opponents"]["chansey"]["moves"]
    # a full team: 6 opponents, 5 sampled from the pool, no duplicates
    assert len(d1["opponents"]) == 6
    assert len(set(d1["opponents"])) == 6


def test_bridge_end_to_end_generates_instructions():
    from poke_engine import generate_instructions

    b = _battle()
    det = sample_determinization(b, np.random.default_rng(7))
    counters = BridgeCounters()
    state = battle_to_state(b, det, counters)
    # our side exact: real stats, real hp
    us = state.side_one.pokemon[0]
    assert us.id == "tauros" and us.hp == 300 and us.speed == 220
    # opponent active determinized at its randbats level with formula stats
    them = state.side_two.pokemon[0]
    assert them.id == "chansey"
    # joint transition: branch percentages sum to ~100
    branches = generate_instructions(state, "bodyslam", "softboiled")
    total = sum(br.percentage for br in branches)
    assert branches and abs(total - 100.0) < 1e-3


def test_locked_turn_detection():
    b = _battle()
    assert not is_locked_turn(b)
    b.available_moves = [PEMove("struggle", gen=1)]
    assert not is_locked_turn(b)  # struggle is a real move, not a lock
    fight = SimpleNamespace(id="fight")
    b.available_moves = [fight]
    assert is_locked_turn(b)


def test_unmapped_effects_are_counted_not_dropped():
    b = _battle()
    class _FakeEffect:
        name = "SOME_NEW_EFFECT"

    b.active_pokemon.effects = {_FakeEffect(): 1}
    det = sample_determinization(b, np.random.default_rng(3))
    counters = BridgeCounters()
    battle_to_state(b, det, counters)
    assert counters.unmapped_effects.get("SOME_NEW_EFFECT") == 1


def test_shadow_battle_round_trip_parity():
    """Synthetic FG-6 at exact-information grade: a fully-revealed battle
    bridged to a State and shadowed back must embed CLOSE to the original.
    Exact parity is not expected pre-FG-6 (stats source, PP, HP grain
    differ by construction); this pins the pipeline and counts the
    differing dims so regressions are visible."""
    import numpy as np
    from rl.envs.showdown import ShowdownSingles
    from rl.search.shadow_battle import shadow_battle

    env = ShowdownSingles(start_listening=False)
    b = _battle()
    det = sample_determinization(b, np.random.default_rng(11))
    state = battle_to_state(b, det, BridgeCounters())
    sb = shadow_battle(state, turn=b.turn)
    v_live = env.embed_battle(b)
    v_shadow = env.embed_battle(sb)
    assert v_shadow.shape == v_live.shape
    diff = np.flatnonzero(np.abs(v_live - v_shadow) > 1e-6)
    # our active + our moves must round-trip essentially exactly; the
    # opponent side may differ (determinized bench, formula stats). The
    # loose bound below is a tripwire, not a parity claim — FG-6 measures
    # the real budget on live harvest data.
    assert len(diff) < v_live.shape[0] * 0.25, (
        f"{len(diff)} dims differ — bridge/shadow regression"
    )


def test_shadow_available_moves_synthesized():
    import numpy as np
    from rl.search.shadow_battle import shadow_battle

    b = _battle()
    det = sample_determinization(b, np.random.default_rng(5))
    state = battle_to_state(b, det, BridgeCounters())
    sb = shadow_battle(state, turn=1)
    ids = {m.id for m in sb.available_moves}
    assert ids == {"bodyslam", "blizzard", "earthquake", "hyperbeam"}
    assert all(m.current_pp > 0 for m in sb.available_moves)


def test_freeze_rehydrate_embed_parity():
    """Harvest contract: embed_battle(rehydrate(freeze(b))) is bit-identical
    to embed_battle(b), and the rehydrated battle still feeds the
    determinizer (identity of the opponent active survives)."""
    from rl.envs.showdown import ShowdownSingles
    from rl.search.harvest import freeze_battle, rehydrate_battle

    env = ShowdownSingles(start_listening=False)
    b = _battle()
    b.active_pokemon.boosts["atk"] = 2
    b.active_pokemon.status_counter = 3
    r = rehydrate_battle(freeze_battle(b))
    assert np.array_equal(env.embed_battle(b), env.embed_battle(r))
    assert r.opponent_active_pokemon is list(r.opponent_team.values())[0]
    det = sample_determinization(r, np.random.default_rng(9))
    state = battle_to_state(r, det, BridgeCounters())
    assert state.side_one.pokemon[0].id == "tauros"
    assert state.side_one.attack_boost == 2


def test_bench_sampler_enforces_generator_caps():
    """Cap-of-2 rejection (design §3): every determinized team must satisfy
    the vendored generator's team caps — <=2 mons per type, <=2 weak per
    spammable type, <=1 level-100 — and never carry ditto when our own team
    does (one Ditto per battle)."""
    from rl.search.determinize import _TeamCaps, _species_caps

    b = _battle()
    b.team["p1: Ditto"] = _mon("ditto", ["transform"])
    for seed in range(30):
        det = sample_determinization(b, np.random.default_rng(seed))
        assert "ditto" not in det["opponents"]
        caps = _TeamCaps()
        for sp in det["opponents"]:
            caps.admit(sp)
        assert all(v <= 2 for v in caps.type_count.values()), (seed, caps.type_count)
        assert all(v <= 2 for v in caps.weak_count.values()), (seed, caps.weak_count)
        assert caps.max_level <= 1, seed
    # the weakness rule matches PS semantics on known cases: chansey is not
    # weak to psychic; golem is weak to water/ice/ground... and immune to
    # electric despite ground's SE never applying to it
    assert "psychic" not in _species_caps("chansey")[1]
    assert {"water", "ice"} <= _species_caps("golem")[1]
    assert "electric" not in _species_caps("golem")[1]


def test_engine_accepts_every_mapped_status():
    """LANDMINE PIN (2026-08-22): the engine accepts any status string at
    Pokemon construction and only parses it inside generate_instructions —
    the 3-letter poke-env forms ("par") panic there, and .status READBACK
    returns the raw string unparsed so constructed states look clean. Every
    poke-env status must therefore survive an actual generate_instructions
    call through the bridge's map."""
    from poke_env.battle.status import Status
    from poke_engine import generate_instructions

    from rl.search.bridge import _STATUS_MAP

    for name in _STATUS_MAP:
        if name == "FNT":
            continue
        b = _battle()
        b.opponent_active_pokemon.status = Status[name]
        det = sample_determinization(b, np.random.default_rng(1))
        state = battle_to_state(b, det, BridgeCounters())
        branches = generate_instructions(state, "bodyslam", "softboiled")
        assert branches, f"engine rejected mapped status for {name}"


def test_status_round_trips_through_shadow():
    """A paralyzed opponent must survive bridge -> engine -> shadow -> the
    encoder's status one-hot (it silently vanished before the status-name
    fix: shadow's reverse map keyed the 3-letter forms)."""
    from poke_env.battle.status import Status

    from rl.search.shadow_battle import shadow_battle

    b = _battle()
    b.opponent_active_pokemon.status = Status.PAR
    det = sample_determinization(b, np.random.default_rng(2))
    state = battle_to_state(b, det, BridgeCounters())
    sb = shadow_battle(state, turn=b.turn)
    assert sb.opponent_active_pokemon.status is Status.PAR


def test_leaf_volatiles_survive_shadow_readback():
    """LANDMINE PIN (2026-08-22): the engine UPPERCASES volatile_statuses on
    applied-state readback (same family as mon-id uppercasing) — before the
    .lower() fix every leaf silently lost its volatiles at the shadow
    boundary, and the FG-2 comparison misread MUSTRECHARGE as absent."""
    from poke_engine import generate_instructions

    from rl.search.shadow_battle import shadow_battle

    b = _battle()
    b.opponent_active_pokemon.moves = {"hyperbeam": PEMove("hyperbeam", gen=1)}
    det = sample_determinization(b, np.random.default_rng(4))
    state = battle_to_state(b, det, BridgeCounters())
    branches = generate_instructions(state, "bodyslam", "hyperbeam")
    hit = next(
        (state.apply_instructions(br) for br in branches
         if any("mustrecharge" == v.lower() for v in
                state.apply_instructions(br).side_two.volatile_statuses)),
        None,
    )
    assert hit is not None, "no branch left the opponent recharging"
    sb = shadow_battle(hit, turn=2)
    assert sb.opponent_active_pokemon.must_recharge


def test_faint_leaf_carries_force_switch():
    """A leaf where our active fainted must embed as a force-switch state —
    the family the critic trained on (FG-6 dim-3 finding)."""
    from rl.search.shadow_battle import shadow_battle

    b = _battle()
    det = sample_determinization(b, np.random.default_rng(6))
    state = battle_to_state(b, det, BridgeCounters())
    sb = shadow_battle(state, turn=2)
    assert not sb.force_switch
    b.active_pokemon.current_hp = 0
    b.active_pokemon.current_hp_fraction = 0.0
    b.active_pokemon.fainted = True
    state = battle_to_state(b, det, BridgeCounters())
    sb = shadow_battle(state, turn=2)
    assert sb.force_switch
