"""Showdown env plumbing (Phase 5): the harness-contract seams.

Everything above the websocket is unit-tested offline: outcome mapping,
terminal-only reward, the baseline encoder, the opponent-spec factory, and
the gen-1 action-space size. The full stack (mask lifted into info, an
episode completing under strict action conversion, info["outcome"] at the
end) needs a live local server, so it runs as one integration test that
skips when nothing listens on localhost:8000 — start it with:
cd showdown && node pokemon-showdown start --no-security.

strict=True (poke-env's default, kept) is what makes the integration test a
masking proof: every action is drawn from info["action_mask"], and poke-env
raises on any converted order the server would refuse, so a wrong mask
cannot pass silently.
"""

import socket
from types import SimpleNamespace

import numpy as np
import pytest
from gymnasium import spaces

from poke_env.battle.effect import Effect
from poke_env.battle.move import Move
from poke_env.battle.pokemon import Pokemon
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.status import Status
from poke_env.environment import SinglesEnv
from poke_env.player import MaxBasePowerPlayer, RandomPlayer, SimpleHeuristicsPlayer

from rl.envs.make import make_env
from rl.envs.showdown import (
    ACTIVE_DIM,
    GEN1_TYPES,
    GLOBAL_DIM,
    MON_DIM,
    MOVE_DIM,
    OBS_DIM,
    OPPONENT_PLAYERS,
    MixturePlayer,
    PoolPlayer,
    ShowdownEnv,
    ShowdownSingles,
    battle_outcome,
    opponent_player,
)
from rl.selfplay.pool import SnapshotPool


@pytest.fixture(scope="module")
def offline_env():
    # start_listening=False: no server, no websocket — the ctor still builds
    # spaces and the type chart, which is all these tests touch.
    return ShowdownSingles(start_listening=False)


def _battle(won, mine=(), theirs=()):
    """A finished battle stub. `mine`/`theirs` are the two sides' fainted
    flags — empty by default, which is all the reward/outcome tests need and
    still enough for the terminal step to count faints for info["faints"]."""
    lost = None if won is None else not won
    return SimpleNamespace(
        won=won,
        lost=lost,
        team={i: SimpleNamespace(fainted=f) for i, f in enumerate(mine)},
        opponent_team={i: SimpleNamespace(fainted=f) for i, f in enumerate(theirs)},
        # Explicit per the stub rule (read directly, never getattr-defaulted).
        # Note this stub stays unhashable (SimpleNamespace defines __eq__),
        # so it can only travel the shaping-off path — which is the point of
        # the tests that use it.
        _replay_data=[],
        player_role="p1",
    )


def test_outcome_mapping_is_won_lost_tie():
    assert battle_outcome(_battle(True)) == 1
    assert battle_outcome(_battle(False)) == -1
    # A tie leaves battle.won None even though the battle is finished.
    assert battle_outcome(_battle(None)) == 0


def test_reward_is_terminal_only_and_equals_outcome(offline_env):
    assert offline_env.calc_reward(_battle(None)) == 0.0  # in progress / tie
    assert offline_env.calc_reward(_battle(True)) == 1.0
    assert offline_env.calc_reward(_battle(False)) == -1.0


def test_gen1_action_space_is_10(offline_env):
    # 6 switches + 4 moves, no gimmick actions in gen 1. The mask and the
    # obs-space rewrite must agree on this width.
    for agent in offline_env.possible_agents:
        assert offline_env.action_spaces[agent] == spaces.Discrete(10)
        mask_space = offline_env.observation_spaces[agent]["action_mask"]
        assert mask_space.shape == (10,)


# --- encoder --------------------------------------------------------------
#
# Block offsets, from the layout constants (see rl/envs/showdown.py):
_OUR_TEAM = GLOBAL_DIM
_OUR_ACTIVE = _OUR_TEAM + 6 * MON_DIM
_OUR_MOVES = _OUR_ACTIVE + ACTIVE_DIM
_OPP_TEAM = _OUR_MOVES + 4 * MOVE_DIM
_OPP_ACTIVE = _OPP_TEAM + 6 * (MON_DIM + 1)


def _stub_battle(**kwargs):
    base = dict(
        active_pokemon=None, opponent_active_pokemon=None, team={},
        opponent_team={}, turn=0, force_switch=False, trapped=False,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _stub_mon(**kwargs):
    """A mon exposing exactly the attributes the encoder reads, defaulting
    to an all-zero encoding (except NORMAL typing)."""
    base = dict(
        current_hp_fraction=0.0, fainted=False, status=None, level=0,
        base_stats={"hp": 0, "atk": 0, "def": 0, "spa": 0, "spe": 0},
        types=[PokemonType.NORMAL], type_1=PokemonType.NORMAL, type_2=None,
        boosts=dict.fromkeys(("accuracy", "atk", "def", "evasion", "spa", "spd", "spe"), 0),
        effects={}, status_counter=0, preparing=False, moves={},
        must_recharge=False,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_embed_battle_empty_battle_is_zeros(offline_env):
    vec = offline_env.embed_battle(_stub_battle())
    assert vec.shape == (OBS_DIM,) and vec.dtype == np.float32
    assert not vec.any()


def test_global_block(offline_env):
    dead = _stub_mon(fainted=True, status=Status.FNT)
    battle = _stub_battle(
        turn=10, force_switch=True, trapped=True,
        team={"a": dead, "b": dead, "c": _stub_mon()},
        opponent_team={"d": dead},
    )
    vec = offline_env.embed_battle(battle)
    assert vec[0] == pytest.approx(10 / 50)
    assert vec[1] == pytest.approx(2 / 6)
    assert vec[2] == pytest.approx(1 / 6)
    assert vec[3] == 1.0 and vec[4] == 1.0
    # FNT is carried by the fainted flag, never the status one-hot.
    assert not vec[_OUR_TEAM + 3 : _OUR_TEAM + 9].any()
    assert offline_env.embed_battle(_stub_battle(turn=500))[0] == 1.0  # capped


def test_mon_block_features_and_switch_slot_order(offline_env):
    zapdos = Pokemon(gen=1, species="zapdos")  # electric/flying
    snorlax = Pokemon(gen=1, species="snorlax")  # normal
    gyarados = Pokemon(gen=1, species="gyarados")  # water/flying
    battle = _stub_battle(
        active_pokemon=zapdos,
        opponent_active_pokemon=gyarados,
        team={"a": zapdos, "b": snorlax},
        opponent_team={"g": gyarados},
    )
    vec = offline_env.embed_battle(battle)
    o = _OUR_TEAM  # slot 0 = first of team.values() = zapdos, the active
    assert vec[o + 2] == 1.0  # is-active
    assert vec[o + 9] == 1.0  # level 100
    assert vec[o + 10] == pytest.approx(zapdos.base_stats["hp"] / 255)
    types = vec[o + 15 : o + 30]
    assert types[GEN1_TYPES.index(PokemonType.ELECTRIC)] == 1.0
    assert types[GEN1_TYPES.index(PokemonType.FLYING)] == 1.0
    assert types.sum() == 2.0
    assert vec[o + 30] == 4.0  # electric vs water/flying
    assert vec[o + 31] == 1.0  # gyarados's best type vs zapdos: water, x1
    # Slot 1 follows team.values() order — the switch-action alignment.
    o1 = o + MON_DIM
    assert vec[o1 + 2] == 0.0  # not active
    assert vec[o1 + 15 + GEN1_TYPES.index(PokemonType.NORMAL)] == 1.0
    # Opponent block 0: revealed flag, then gyarados as THEIR active.
    assert vec[_OPP_TEAM] == 1.0
    assert vec[_OPP_TEAM + 1 + 2] == 1.0
    # Unrevealed opponent slots stay all-zero, revealed flag included.
    assert not vec[_OPP_TEAM + (MON_DIM + 1) : _OPP_TEAM + 6 * (MON_DIM + 1)].any()
    raw_space = offline_env.observation_spaces[offline_env.possible_agents[0]]
    assert raw_space["observation"].contains(vec)


def test_active_extras_block(offline_env):
    active = _stub_mon(
        boosts={"accuracy": 0, "atk": 2, "def": 0, "evasion": 0, "spa": -1,
                "spd": -1, "spe": 0},
        effects={Effect.SUBSTITUTE: 1},
        status_counter=4,
        preparing=True,
    )
    battle = _stub_battle(active_pokemon=active, team={"a": active})
    vec = offline_env.embed_battle(battle)
    o = _OUR_ACTIVE  # boosts in sorted-key order
    assert vec[o + 1] == pytest.approx(2 / 6)  # atk
    assert vec[o + 4] == pytest.approx(-1 / 6)  # spa
    volatiles = vec[o + 7 : o + 14]  # (confusion, focus energy, leech seed,
    assert volatiles[6] == 1.0  # ..., must recharge, wrap, reflect, SUBSTITUTE)
    assert volatiles.sum() == 1.0
    assert vec[o + 14] == pytest.approx(4 / 16)
    assert vec[o + 15] == 1.0


def test_must_recharge_reads_the_bool_not_the_effect(offline_env):
    # Stage-0 fix (D13a): poke-env routes |-mustrecharge| to the bool
    # `pokemon.must_recharge` and never starts Effect.MUST_RECHARGE, so the
    # slot fires from the bool — and ONLY the bool, the Effect stays inert.
    recharging = _stub_mon(must_recharge=True)
    battle = _stub_battle(active_pokemon=recharging, team={"a": recharging})
    vec = offline_env.embed_battle(battle)
    volatiles = vec[_OUR_ACTIVE + 7 : _OUR_ACTIVE + 14]
    assert volatiles[3] == 1.0 and volatiles.sum() == 1.0
    phantom = _stub_mon(effects={Effect.MUST_RECHARGE: 1})
    vec = offline_env.embed_battle(
        _stub_battle(active_pokemon=phantom, team={"a": phantom})
    )
    assert not vec[_OUR_ACTIVE + 7 : _OUR_ACTIVE + 14].any()
    # The opponent's active extras block gets the same fix. A real Pokemon
    # here, not a stub: the opponent path also walks the set prior by species.
    snorlax = Pokemon(gen=1, species="snorlax")  # the Hyper Beam case
    snorlax.must_recharge = True
    vec = offline_env.embed_battle(
        _stub_battle(opponent_active_pokemon=snorlax, opponent_team={"s": snorlax})
    )
    assert vec[_OPP_ACTIVE + 7 + 3] == 1.0


def test_global_aliased_flag(offline_env):
    # Stage-0 fix (D13a): vec[5] says the move blocks are zeroed because the
    # only legal move-action is a poke-env SPECIAL_MOVE (fight/struggle/
    # recharge) — the one dim that distinguishes a recharge/trap placeholder
    # turn from an ordinary state, since battle.trapped stays False there.
    aliased = _stub_battle(
        available_moves=[SimpleNamespace(id="recharge")],
    )
    assert offline_env.embed_battle(aliased)[5] == 1.0
    two_real = _stub_battle(
        available_moves=[SimpleNamespace(id="tackle"), SimpleNamespace(id="rest")],
    )
    assert offline_env.embed_battle(two_real)[5] == 0.0
    # One remaining REAL move is not aliasing — slot i still means move i.
    one_real = _stub_battle(available_moves=[SimpleNamespace(id="tackle")])
    assert offline_env.embed_battle(one_real)[5] == 0.0


def test_move_block_features(offline_env):
    moves = {
        "thunderbolt": Move("thunderbolt", gen=1),
        "recover": Move("recover", gen=1),
        "quickattack": Move("quickattack", gen=1),
    }
    moves["thunderbolt"].use()  # burn one PP: fraction dips below 1
    active = _stub_mon(moves=moves)
    gyarados = Pokemon(gen=1, species="gyarados")  # water/flying: electric x4
    battle = _stub_battle(
        active_pokemon=active,
        opponent_active_pokemon=gyarados,
        team={"a": active},
        opponent_team={"g": gyarados},
    )
    vec = offline_env.embed_battle(battle)
    o = _OUR_MOVES  # slot 0 = thunderbolt, moves.values() order
    assert vec[o] == 1.0
    assert vec[o + 1] == pytest.approx(0.95)  # base power 95 / 100
    assert vec[o + 2] == 1.0  # accuracy
    assert vec[o + 3] == pytest.approx(23 / 24)  # PP after one use
    assert vec[o + 4] == 4.0
    assert vec[o + 5] == 0.0 and vec[o + 6] == 0.0  # special: neither flag
    assert vec[o + 8 + GEN1_TYPES.index(PokemonType.ELECTRIC)] == 1.0
    o1 = o + MOVE_DIM  # recover: a status move
    assert vec[o1 + 1] == 0.0 and vec[o1 + 6] == 1.0
    o2 = o + 2 * MOVE_DIM  # quick attack: physical, priority +1
    assert vec[o2 + 5] == 1.0 and vec[o2 + 7] == pytest.approx(1 / 5)
    o3 = o + 3 * MOVE_DIM  # fourth slot unknown
    assert not vec[o3 : o3 + MOVE_DIM].any()
    # The opponent's move blocks are filled from the vendored randbats SET
    # PRIOR, not from revealed moves alone. Gyarados has revealed nothing, but
    # its set pool is public and enumerable, so the encoder supplies the four
    # most likely moves with slot 0 carrying P(the mon has this move).
    #
    # This replaces an earlier contract ("unrevealed => all zeros"), which
    # discarded the single largest input the search teacher conditions on.
    # Reusing the existing `known` flag as a probability costs zero extra dims.
    opp = _OPP_ACTIVE + ACTIVE_DIM
    assert vec[opp : opp + 4 * MOVE_DIM].any(), "set prior did not populate"
    probs = [float(vec[opp + i * MOVE_DIM]) for i in range(4)]
    assert probs[0] == pytest.approx(1.0)  # bodyslam is in every gyarados set
    assert all(0.0 < q <= 1.0 for q in probs), probs
    assert probs == sorted(probs, reverse=True), "slots must be most-likely first"
    # A fully-determined species leaves no uncertainty at all.
    tauros = Pokemon(gen=1, species="tauros")
    vec_t = offline_env.embed_battle(
        _stub_battle(
            active_pokemon=active,
            opponent_active_pokemon=tauros,
            team={"a": active},
            opponent_team={"t": tauros},
        )
    )
    assert all(
        float(vec_t[opp + i * MOVE_DIM]) == pytest.approx(1.0) for i in range(4)
    ), "tauros has exactly one possible set; all four slots should be certain"


def test_move_slots_not_aliased_on_placeholder(offline_env):
    """On a gen1 placeholder turn our own move blocks must be inert.

    Showdown replaces the move list with a single `Fight` when the active is
    asleep/frozen/partially trapped, and poke-env re-bases move actions onto
    `available_moves` -- so slot 0 stops meaning "the mon's first move". Filling
    the blocks with the four real moves would teach the network a contradictory
    input->label mapping on those turns. Struggle and Recharge alias the same
    way.
    """
    moves = {
        "thunderbolt": Move("thunderbolt", gen=1),
        "recover": Move("recover", gen=1),
    }
    active = _stub_mon(moves=moves)
    gyarados = Pokemon(gen=1, species="gyarados")
    battle = _stub_battle(
        active_pokemon=active,
        opponent_active_pokemon=gyarados,
        team={"a": active},
        opponent_team={"g": gyarados},
    )
    battle.available_moves = [Move("fight", gen=1)]
    vec = offline_env.embed_battle(battle)
    ours = _OUR_MOVES
    assert not vec[ours : ours + 4 * MOVE_DIM].any(), (
        "our move blocks must be zeroed on a placeholder turn"
    )
    # ...while the rest of the state is still described.
    assert vec[_OPP_ACTIVE + ACTIVE_DIM : _OPP_ACTIVE + ACTIVE_DIM + MOVE_DIM].any()


def test_save_replays_reaches_both_seats():
    # The watch.py replay path: the flag must land on poke-env's players,
    # which write one replay HTML per battle per seat on battle finish.
    env = ShowdownSingles(start_listening=False, save_replays="replay_dir")
    assert env.agent1._save_replays == "replay_dir"
    assert env.agent2._save_replays == "replay_dir"


def test_eval_env_extras_cannot_override_config_opponent():
    # extra_env_kwargs is for eval-site extras (replay saving); the opponent
    # is config-derived and overriding it would defeat make_eval_env's
    # whole purpose. The guard fires before any env is constructed.
    cfg = SimpleNamespace(
        env_id="Showdown-v0", seed=0, selfplay={"eval_opponent": "max_power"},
        env_kwargs={},
    )
    from rl.envs.make import make_eval_env

    with pytest.raises(AssertionError, match="may not override"):
        make_eval_env(cfg, extra_env_kwargs={"opponent": "random"})


def test_opponent_spec_factory():
    fmt = "gen1randombattle"
    assert isinstance(opponent_player("random", fmt), RandomPlayer)
    assert isinstance(opponent_player("max_power", fmt), MaxBasePowerPlayer)
    assert isinstance(opponent_player("heuristics", fmt), SimpleHeuristicsPlayer)
    live = RandomPlayer(battle_format=fmt, start_listening=False)
    assert opponent_player(live, fmt) is live  # instances pass through
    with pytest.raises(ValueError, match="unknown opponent"):
        opponent_player("alphabeta4", fmt)
    assert sorted(OPPONENT_PLAYERS) == ["heuristics", "max_power", "random"]


# --- MixturePlayer (training-distribution lever) ---------------------------


def _mix_player(spec="mix:heuristics=0.7,max_power=0.2,random=0.1"):
    return opponent_player(spec, "gen1randombattle")


def test_mix_spec_parses_and_normalizes():
    player = _mix_player("mix:heuristics=7,max_power=2,random=1")  # unnormalized
    assert isinstance(player, MixturePlayer)
    assert player._names == ["heuristics", "max_power", "random"]
    assert player._weights == pytest.approx([0.7, 0.2, 0.1])


def test_mix_spec_rejects_bad_input():
    with pytest.raises(ValueError, match="unknown opponent|non-empty"):
        _mix_player("mix:alphabeta=1.0")
    with pytest.raises(ValueError, match="positive"):
        _mix_player("mix:heuristics=0,random=1")
    with pytest.raises(ValueError, match="malformed"):
        _mix_player("mix:heuristics")


def test_mix_assignment_is_sticky_within_a_battle():
    # One battle must be driven by ONE sub-player end to end — a mid-game
    # opponent swap would make battles chimeras no bot distribution emits.
    player = _mix_player()
    calls = []
    player._players = {
        name: SimpleNamespace(choose_move=lambda b, n=name: calls.append(n) or n)
        for name in player._names
    }
    b1 = SimpleNamespace(battle_tag="battle-gen1randombattle-1")
    b2 = SimpleNamespace(battle_tag="battle-gen1randombattle-2")
    first = player.choose_move(b1)
    assert all(player.choose_move(b1) == first for _ in range(10))
    player.choose_move(b2)  # new battle: fresh sample, then sticky again
    second = calls[-1]
    assert all(player.choose_move(b2) == second for _ in range(10))
    assert set(calls) <= set(player._names)


def test_mix_sampling_matches_weights_across_battles():
    player = _mix_player()
    player._players = {
        name: SimpleNamespace(choose_move=lambda b, n=name: n)
        for name in player._names
    }
    n = 3000
    picks = [
        player.choose_move(SimpleNamespace(battle_tag=f"battle-x-{i}"))
        for i in range(n)
    ]
    freq = {name: picks.count(name) / n for name in player._names}
    assert freq["heuristics"] == pytest.approx(0.7, abs=0.03)
    assert freq["max_power"] == pytest.approx(0.2, abs=0.03)
    assert freq["random"] == pytest.approx(0.1, abs=0.03)


# --- ShowdownEnv.step adapter logic, offline against a scripted stub -------
#
# The stub mimics the two attributes step() reads from the poke-env stack:
# SingleAgentWrapper.step's 5-tuple and PokeEnv's agent1_to_move/battle1.
# Each script entry is (reward, terminated, truncated, to_move_after) —
# to_move_after False means the RETURNED state is a wait state (poke-env
# would silently discard the next action).


def _obs_dict():
    return {
        "observation": np.zeros(OBS_DIM, np.float32),
        "action_mask": np.array([1] + [0] * 9, np.int64),
    }


class _StubStack:
    def __init__(self, script, battle=None):
        self.env = SimpleNamespace(agent1_to_move=True, battle1=battle)
        self.script = list(script)
        self.actions = []

    def step(self, action):
        self.actions.append(action)
        reward, terminated, truncated, to_move = self.script.pop(0)
        self.env.agent1_to_move = to_move
        return _obs_dict(), reward, terminated, truncated, {}


def _adapter(stub, pool_player=None) -> ShowdownEnv:
    env = ShowdownEnv.__new__(ShowdownEnv)  # step()/waits count only
    env._env = stub
    env._pool_player = pool_player
    env._privileged = False
    env._opp_action = pool_player is not None
    env.waits_absorbed = 0
    return env


def test_step_pumps_wait_states_and_accumulates_reward():
    # Real action -> wait, wait -> wait, wait -> real decision point.
    stub = _StubStack([(0.0, False, False, False), (0.0, False, False, False),
                       (0.0, False, False, True)])
    env = _adapter(stub)
    obs, reward, terminated, truncated, info = env.step(5)
    assert env.waits_absorbed == 2
    assert not terminated and not truncated
    # The learner's action goes through once; the pump's two dummies are
    # discarded by poke-env, so their VALUE is deliberately unpinned here
    # (see the C1 control in scripts/mutations/phase5_env.py).
    assert int(stub.actions[0]) == 5 and len(stub.actions) == 3
    assert all(isinstance(a, np.int64) for a in stub.actions)


def test_step_asserts_on_silent_discard():
    stub = _StubStack([(0.0, False, False, True)])
    stub.env.agent1_to_move = False  # poke-env would drop the action
    env = _adapter(stub)
    with pytest.raises(AssertionError, match="silently discarded"):
        env.step(3)


def test_decided_truncation_is_remapped_to_terminal():
    # A forfeit/timer loss: poke-env reports truncated=True, but the game is
    # decided (won=False) — the learner must see terminal, no bootstrap.
    battle = _battle(False)
    stub = _StubStack([(-1.0, False, True, False)], battle=battle)
    env = _adapter(stub)
    obs, reward, terminated, truncated, info = env.step(0)
    assert terminated and not truncated
    assert info["outcome"] == -1 and reward == -1.0


def test_terminal_step_reports_faint_counts():
    """info["faints"] = (ours, theirs) at the terminal step — the data behind
    Arm B's loss-conditioned secondary, emitted whether or not shaping is on
    so the arm and the control produce the same number."""
    battle = _battle(False, mine=(True,) * 6, theirs=(True, True, False))
    stub = _StubStack([(-1.0, True, False, False)], battle=battle)
    obs, reward, terminated, truncated, info = _adapter(stub).step(0)
    assert info["faints"] == (6, 2)


def test_tie_is_terminal_with_outcome_zero():
    battle = _battle(None)
    stub = _StubStack([(0.0, False, True, False)], battle=battle)
    env = _adapter(stub)
    obs, reward, terminated, truncated, info = env.step(0)
    assert terminated and not truncated
    assert info["outcome"] == 0 and reward == 0.0


def test_reward_accumulates_across_pump():
    # A wait step that carries the terminal reward (opponent's replacement
    # act finishes the game) must not lose it.
    battle = _battle(True)
    stub = _StubStack([(0.0, False, False, False), (1.0, True, False, False)],
                      battle=battle)
    env = _adapter(stub)
    obs, reward, terminated, truncated, info = env.step(2)
    assert reward == 1.0 and terminated and info["outcome"] == 1
    assert env.waits_absorbed == 1


# --- PoolPlayer (milestone 3: the seat-2 pool adapter) ----------------------
#
# Unit tests fake the pool (the SnapshotPool contract itself is pinned in
# tests/test_selfplay_pool.py) and patch the encode/mask/convert trio, which
# needs a real battle object — what these tests pin is the PoolPlayer's OWN
# logic: one member per battle, report-to-the-member-that-played, the wait
# guard, and the sync signature the wrapper asserts.


class _FakeMember:
    def __init__(self, action=0):
        self.action = action

    def move(self, obs, mask, rng):
        return self.action


class _FakePool:
    """Records the PoolPlayer contract calls; select() round-robins."""

    def __init__(self, members):
        self.members = members
        self.selects = 0
        self.reports = []
        self.frozen = 0

    def freeze(self):
        self.frozen += 1

    def select(self, rng):
        member = self.members[self.selects % len(self.members)]
        self.selects += 1
        return member

    def report(self, member, outcome):
        self.reports.append((member, outcome))


def _pool_player(pool):
    return PoolPlayer(pool, battle_format="gen1randombattle", start_listening=False)


def _patch_trio(monkeypatch):
    monkeypatch.setattr(
        "rl.envs.showdown.embed_battle", lambda b, tc: np.zeros(OBS_DIM, np.float32)
    )
    monkeypatch.setattr(
        "rl.envs.showdown.SinglesEnv.get_action_mask",
        staticmethod(lambda b: np.ones(10, np.int64)),
    )
    monkeypatch.setattr(
        "rl.envs.showdown.SinglesEnv.action_to_order",
        staticmethod(lambda a, b: int(a)),
    )


def test_pool_player_selects_one_member_per_battle(monkeypatch):
    # The per-episode swap boundary: one draw drives a battle end to end
    # (the MixturePlayer stickiness contract), a NEW battle draws fresh.
    _patch_trio(monkeypatch)
    pool = _FakePool([_FakeMember(3), _FakeMember(7)])
    player = _pool_player(pool)
    assert pool.frozen == 1  # installer contract: every installer freezes
    b1 = SimpleNamespace(battle_tag="battle-gen1randombattle-1", wait=False)
    b2 = SimpleNamespace(battle_tag="battle-gen1randombattle-2", wait=False)
    assert [player.choose_move(b1) for _ in range(5)] == [3] * 5
    assert pool.selects == 1
    assert player.choose_move(b2) == 7
    assert pool.selects == 2


def test_pool_player_reports_the_member_that_played(monkeypatch):
    # PFSP stats feed: the outcome lands on the member whose battle just
    # ended — report fires before the next battle's choose_move re-selects,
    # so a stale-member mis-credit cannot happen in this call order.
    _patch_trio(monkeypatch)
    members = [_FakeMember(0), _FakeMember(1)]
    pool = _FakePool(members)
    player = _pool_player(pool)
    player.choose_move(SimpleNamespace(battle_tag="b-1", wait=False))
    player.report_outcome(1)
    player.choose_move(SimpleNamespace(battle_tag="b-2", wait=False))
    player.report_outcome(-1)
    assert pool.reports == [(members[0], 1), (members[1], -1)]


def test_pool_player_rejects_wait_states(monkeypatch):
    # SingleAgentWrapper's battle2.wait bypass means a wait state must never
    # reach the pool opponent; if one does, fail loudly instead of advancing
    # the member's generator on a decision poke-env then discards.
    _patch_trio(monkeypatch)
    player = _pool_player(_FakePool([_FakeMember()]))
    with pytest.raises(AssertionError, match="wait state"):
        player.choose_move(SimpleNamespace(battle_tag="b-1", wait=True))


def test_pool_player_choose_move_is_sync():
    # SingleAgentWrapper.step calls choose_move on the caller thread and
    # asserts the result is not awaitable — SeamPlayer's async signature is
    # the precedent for the encode/mask/convert trio only, never for this.
    import inspect

    assert not inspect.iscoroutinefunction(PoolPlayer.choose_move)


def test_pool_player_rng_reseeds_deterministically():
    player = _pool_player(_FakePool([_FakeMember()]))
    player.seed_rng(7)
    first = [player._rng.integers(100) for _ in range(5)]
    player.seed_rng(7)
    assert [player._rng.integers(100) for _ in range(5)] == first


def test_opponent_player_resolves_a_pool_to_a_pool_player():
    # The `opponent: self` seam: rl/train.py substitutes the pool OBJECT,
    # and resolution must wrap it rather than reject it. Empty pool is fine
    # here — selection happens per battle, never at construction.
    pool = SnapshotPool(pool_size=1, latest_prob=1.0)
    player = opponent_player(pool, "gen1randombattle")
    assert isinstance(player, PoolPlayer)


def test_env_terminal_step_reports_to_the_pool_player():
    # The adapter seam: ShowdownEnv.step forwards the learner-perspective
    # outcome at the terminal step.
    stub = _StubStack([(1.0, True, False, False)], battle=_battle(True))
    env = _adapter(stub)
    outcomes = []
    env._pool_player = SimpleNamespace(report_outcome=outcomes.append)
    env.step(0)
    assert outcomes == [1]


def test_reset_seed_latches_into_the_pool_player_rng():
    # The vector loop seeds sub-env i exactly once (first reset, seed + i);
    # later resets pass None and must not reseed.
    class _ResetStub:
        def __init__(self):
            self.env = SimpleNamespace(agent1_to_move=True, battle1=None)

        def reset(self, *, seed=None, options=None):
            return _obs_dict(), {}

    env = ShowdownEnv.__new__(ShowdownEnv)
    env._env = _ResetStub()
    env._privileged = False
    env.waits_absorbed = 0
    seeds = []
    env._pool_player = SimpleNamespace(seed_rng=seeds.append)
    env.reset(seed=123)
    env.reset()
    assert seeds == [123]


def _server_up() -> bool:
    try:
        socket.create_connection(("127.0.0.1", 8000), timeout=0.5).close()
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _server_up(), reason="no local Showdown server on :8000")
def test_full_episode_contract_against_live_server():
    env = make_env("Showdown-v0", seed=0, env_kwargs={"opponent": "random"})
    obs, info = env.reset(seed=0)
    rng = np.random.default_rng(0)
    ret = 0.0
    for _ in range(1000):
        assert obs.shape == (OBS_DIM,) and obs.dtype == np.float32
        mask = info["action_mask"]
        assert mask.dtype == np.bool_ and mask.shape == (10,) and mask.any()
        assert "outcome" not in info
        obs, reward, terminated, truncated, info = env.step(
            int(rng.choice(np.flatnonzero(mask)))
        )
        ret += reward
        if terminated or truncated:
            break
    else:
        pytest.fail("episode did not finish in 1000 steps")
    assert info["outcome"] in (-1, 0, 1)
    assert ret == info["outcome"]  # terminal-only reward equals the outcome
    assert info["action_mask"].shape == (10,)
    assert terminated and not truncated  # every finish is terminal post-remap
    env.close()


# --- Arm B: terminal-cancelled faint shaping -------------------------------
#
# The lever's whole safety argument is that the shaping telescopes to ZERO
# over an episode, so these tests are the R0 shaping-correctness gate
# (DESIGN.md §5) in unit form: the live-server version below runs the same
# assertion on real battles, and this version runs it on scripted faint
# sequences that can't be produced on demand from a server.

class _ShapingBattle:
    """A battle stub carrying only what the potential reads: the two teams'
    fainted counts, the outcome flags, and `finished`.

    MUTATED in place across steps, because that is what poke-env does — one
    Battle object per seat, updated as the protocol arrives, handed to
    calc_reward again every step. A test that built a fresh object per step
    would silently exercise a different contract from the one that ships.

    A plain class, not SimpleNamespace, because the potential dict is keyed
    by the battle OBJECT and SimpleNamespace defines __eq__ (so it is
    unhashable). poke-env's Battle defines neither __eq__ nor __hash__ and
    hashes by identity, which is what this reproduces.
    """

    def __init__(self, mine=0, theirs=0):
        self.team = {i: SimpleNamespace(fainted=False) for i in range(6)}
        self.opponent_team = {i: SimpleNamespace(fainted=False) for i in range(6)}
        self.won = self.lost = None
        self.finished = False
        # Read directly by the hl_shaping path, never getattr-defaulted
        # (the HISTORY_FEATURES stub rule): the protocol event log and this
        # seat's role, exactly as poke-env exposes them.
        self._replay_data = []
        self.player_role = "p1"
        self.faint(mine, theirs)

    def faint(self, mine, theirs):
        """Set the two sides' fainted counts (monotone in a real battle)."""
        for i, mon in self.team.items():
            mon.fainted = i < mine
        for i, mon in self.opponent_team.items():
            mon.fainted = i < theirs
        return self

    def finish(self, won):
        self.won, self.lost = won, None if won is None else not won
        self.finished = True
        return self


def test_faint_shaping_is_off_by_default():
    """Every config before Arm B must take the identical code path — the
    stub battles the offline reward tests build carry no teams at all, so a
    default that touched them would fail loudly here."""
    env = ShowdownSingles(start_listening=False)
    assert env.faint_shaping == 0.0
    assert env.calc_reward(_battle(True)) == 1.0
    assert env.calc_reward(_battle(None)) == 0.0


@pytest.mark.parametrize("won,outcome", [(True, 1.0), (False, -1.0), (None, 0.0)])
def test_shaped_episode_return_is_exactly_the_terminal_outcome(won, outcome):
    """The R0 gate. A scripted episode: we lose two, they lose four, in an
    interleaved order, and the sum over the whole episode must come back to
    the bare ±1. Without the terminal cancellation this sums to outcome +
    0.1*(4-2) = outcome + 0.2 — exactly the failure the cancellation exists
    to remove, and invisible in any single step's reward."""
    env = ShowdownSingles(start_listening=False, faint_shaping=0.1)
    battle = _ShapingBattle()
    total = 0.0
    for mine, theirs in [(0, 0), (0, 1), (1, 1), (1, 2), (1, 3), (2, 3), (2, 4)]:
        total += env.calc_reward(battle.faint(mine, theirs))
    # The intermediate steps DID carry signal — otherwise this proves nothing.
    assert total == pytest.approx(0.1 * (4 - 2))
    total += env.calc_reward(battle.finish(won))
    assert total == pytest.approx(outcome)
    assert not env._faint_potential  # the finished battle left no state behind


def test_faint_shaping_is_signed_and_symmetric():
    env = ShowdownSingles(start_listening=False, faint_shaping=0.1)
    battle = _ShapingBattle()
    assert env.calc_reward(battle) == pytest.approx(0.0)
    # Their faint pays +0.1; ours costs -0.1. Same magnitude, opposite sign.
    assert env.calc_reward(battle.faint(0, 1)) == pytest.approx(0.1)
    assert env.calc_reward(battle.faint(1, 1)) == pytest.approx(-0.1)
    # A step with no faint on either side pays nothing at all.
    assert env.calc_reward(battle) == pytest.approx(0.0)
    # A double faint in one step nets to zero, not to a doubled payout.
    assert env.calc_reward(battle.faint(2, 2)) == pytest.approx(0.0)


def test_faint_potentials_do_not_fuse_across_the_two_seats():
    """calc_reward is called once per step for EACH seat's own battle object,
    and the two share a battle_tag — so any key derived from the tag would
    difference one seat's potential against the other's and emit garbage on
    every step of every battle."""
    env = ShowdownSingles(start_listening=False, faint_shaping=0.1)
    p1 = _ShapingBattle(mine=0, theirs=3)  # p1 is three faints up
    p2 = _ShapingBattle(mine=3, theirs=0)  # the same game from p2's seat
    assert env.calc_reward(p1) == pytest.approx(0.3)
    assert env.calc_reward(p2) == pytest.approx(-0.3)
    assert len(env._faint_potential) == 2
    # Second step, nothing fainted: both seats must now pay exactly zero.
    assert env.calc_reward(p1) == pytest.approx(0.0)
    assert env.calc_reward(p2) == pytest.approx(0.0)


def test_reset_clears_potentials_so_they_cannot_leak_into_the_next_battle(monkeypatch):
    env = ShowdownSingles(start_listening=False, faint_shaping=0.1)
    env.calc_reward(_ShapingBattle(theirs=2))
    assert env._faint_potential
    # poke-env's own reset opens a challenge and needs a live server; stub it
    # out so this stays an offline test of OUR override.
    sentinel = ("obs", {})
    monkeypatch.setattr(SinglesEnv, "reset", lambda self, seed=None, options=None: sentinel)
    assert env.reset() == sentinel  # the super() call still happens
    assert not env._faint_potential


def test_env_kwargs_reach_the_inner_env_through_the_factory():
    """The config seam: `env_kwargs` in the run YAML must arrive at
    ShowdownSingles, or Arm B (or Rung 1) would launch, train and report as
    the control with nothing looking wrong."""
    env = ShowdownEnv(opponent="random", faint_shaping=0.1, hl_shaping=1.0)
    assert env._env.env.faint_shaping == 0.1
    assert env._env.env.hl_shaping == 1.0
    env.close()


# --- Rung 1: H&L 5-term zero-sum event shaping -----------------------------
#
# Constants and attribution rule from metagrok expts/01.json /
# reward_shaper.py::NewRewardShaper (see _HL_WEIGHTS in rl/envs/showdown.py).
# These unit tests plus tests/test_hl_shaping_tapes.py (real recorded
# protocol, both seats) are R0-2(a) of configs/showdown_sp_signal12m.yaml;
# R0-2(b) is the live smoke.


def _ev(tag, ident):
    """One _replay_data entry: a poke-env split message."""
    return ["", tag, ident]


def test_hl_shaping_is_off_by_default():
    env = ShowdownSingles(start_listening=False)
    assert env.hl_shaping == 0.0
    # Bit-for-bit the control reward path; stub carries no events to read.
    assert env.calc_reward(_battle(True)) == 1.0


def test_hl_event_attribution_signs_and_magnitudes():
    """The exact table from the Rung 1 pre-registration, from p1's seat:
    named side gets w, the other side -w. Includes the |-fail| quirk —
    Showdown names the Pokemon the failed action was AIMED AT, so our
    failed status move (line names THEM) pays US +0.005, reproduced
    verbatim on purpose."""
    env = ShowdownSingles(start_listening=False, hl_shaping=1.0)
    battle = _ShapingBattle()
    for tag, ident, expected in [
        ("faint", "p1a: Snorlax", -0.0125),
        ("faint", "p2a: Tauros", 0.0125),
        ("-fail", "p2a: Slowbro", 0.005),
        ("-fail", "p1a: Chansey", -0.005),
        ("-supereffective", "p1a: Rhydon", -0.0025),
        ("-supereffective", "p2a: Zapdos", 0.0025),
        ("-resisted", "p1a: Starmie", 0.0025),
        ("-resisted", "p2a: Gengar", -0.0025),
        ("-immune", "p1a: Gengar", 0.005),
        ("-immune", "p2a: Golem", -0.005),
    ]:
        battle._replay_data.append(_ev(tag, ident))
        assert env.calc_reward(battle) == expected, (tag, ident)
    # Non-scoring protocol noise pays nothing, including the short win/tie
    # entries poke-env also appends to _replay_data.
    battle._replay_data += [["", "tie"], ["", "win", "somename"], _ev("move", "p1a: Snorlax")]
    assert env.calc_reward(battle) == 0.0


def test_hl_events_are_consumed_exactly_once():
    """The cursor rule that survives the wait pump: however many events
    arrive between calc_reward calls, each is paid exactly once, and a call
    with nothing new pays exactly zero."""
    env = ShowdownSingles(start_listening=False, hl_shaping=1.0)
    battle = _ShapingBattle()
    battle._replay_data += [_ev("faint", "p2a: Tauros"), _ev("-supereffective", "p2a: Tauros")]
    assert env.calc_reward(battle) == pytest.approx(0.015)
    assert env.calc_reward(battle) == 0.0
    battle._replay_data.append(_ev("faint", "p1a: Snorlax"))
    assert env.calc_reward(battle) == -0.0125


def test_hl_two_seats_negate_exactly():
    """The safety argument in unit form: the same event sequence read from
    the two seats sums to EXACTLY 0.0 — not approximately. IEEE negation
    and addition are sign-symmetric, so seat 2's partial sums are the exact
    negatives of seat 1's; R0-2 gates on == 0.0 and so does this test."""
    env = ShowdownSingles(start_listening=False, hl_shaping=1.0)
    events = [
        _ev("faint", "p1a: Snorlax"), _ev("-supereffective", "p2a: Tauros"),
        _ev("-fail", "p2a: Slowbro"), _ev("-resisted", "p1a: Starmie"),
        _ev("-immune", "p2a: Golem"), _ev("faint", "p2a: Tauros"),
        _ev("-fail", "p1a: Chansey"),
    ]
    seat1, seat2 = _ShapingBattle(), _ShapingBattle()
    seat2.player_role = "p2"
    seat1._replay_data = list(events)
    seat2._replay_data = list(events)
    r1, r2 = env.calc_reward(seat1), env.calc_reward(seat2)
    assert r1 != 0.0  # the events did carry signal
    assert r1 + r2 == 0.0  # exact


def test_hl_scale_and_terminal_composition():
    """hl_shaping is a SCALE on the table, and the terminal frame's events
    (the deciding faint) ride on top of the ±1 outcome."""
    env = ShowdownSingles(start_listening=False, hl_shaping=0.5)
    battle = _ShapingBattle()
    battle._replay_data.append(_ev("faint", "p2a: Tauros"))
    assert env.calc_reward(battle) == pytest.approx(0.00625)
    battle._replay_data.append(_ev("faint", "p1a: Snorlax"))
    battle.finish(True)
    assert env.calc_reward(battle) == pytest.approx(1.0 - 0.00625)


def test_hl_composes_with_faint_shaping_through_the_shared_tail():
    """No ratified config sets both levers, but the code composes them and
    the restructured reward tail must be right: the potential differences
    against `reward` (outcome + hl term), and the terminal cancellation
    still removes exactly the accumulated potential."""
    env = ShowdownSingles(start_listening=False, faint_shaping=0.1, hl_shaping=1.0)
    battle = _ShapingBattle()
    battle._replay_data.append(_ev("faint", "p2a: Tauros"))
    assert env.calc_reward(battle.faint(0, 1)) == pytest.approx(0.0125 + 0.1)
    assert env.calc_reward(battle.finish(True)) == pytest.approx(1.0 - 0.1)


def test_hl_cursor_cleared_on_reset(monkeypatch):
    env = ShowdownSingles(start_listening=False, hl_shaping=1.0)
    battle = _ShapingBattle()
    battle._replay_data.append(_ev("faint", "p2a: Tauros"))
    env.calc_reward(battle)
    assert env._event_cursor
    sentinel = ("obs", {})
    monkeypatch.setattr(SinglesEnv, "reset", lambda self, seed=None, options=None: sentinel)
    assert env.reset() == sentinel
    assert not env._event_cursor


@pytest.mark.skipif(not _server_up(), reason="no local Showdown server on :8000")
def test_shaped_return_equals_the_outcome_on_live_battles():
    """The R0 gate on real battles, random policy: per-episode shaped return
    must equal the terminal ±1 exactly, and the shaping must actually have
    fired (a silently-zero potential would pass the first assertion by doing
    nothing at all)."""
    env = make_env(
        "Showdown-v0", seed=0,
        env_kwargs={"opponent": "random", "faint_shaping": 0.1},
    )
    rng = np.random.default_rng(0)
    fired = False
    for _ in range(3):
        obs, info = env.reset()
        terminated = truncated = False
        ret = 0.0
        while not (terminated or truncated):
            action = int(rng.choice(np.flatnonzero(info["action_mask"])))
            obs, reward, terminated, truncated, info = env.step(action)
            ret += reward
            if not (terminated or truncated) and reward != 0.0:
                fired = True  # an intermediate faint paid out
        assert ret == pytest.approx(float(info["outcome"]), abs=1e-9)
    assert fired, "no intermediate faint reward in 3 battles — shaping is inert"
    env.close()


@pytest.mark.skipif(not _server_up(), reason="no local Showdown server on :8000")
def test_wait_states_are_absorbed_over_many_battles():
    # Wait states (opponent faint-replacements) occur in ~6.4% of raw steps
    # vs max_power; 15 battles make hitting at least one near-certain. The
    # in-step assert would fire on any leaked one, so completing the batch
    # with a nonzero pump count is the phantom-row regression proof.
    env = ShowdownEnv(opponent="max_power")
    rng = np.random.default_rng(0)
    for _ in range(15):
        obs, info = env.reset()
        terminated = truncated = False
        while not (terminated or truncated):
            action = int(rng.choice(np.flatnonzero(info["action_mask"])))
            obs, reward, terminated, truncated, info = env.step(action)
        assert terminated and not truncated
        assert info["outcome"] in (-1, 0, 1)
    assert env.waits_absorbed > 0
    env.close()
