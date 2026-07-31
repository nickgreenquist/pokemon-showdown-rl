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
    ShowdownEnv,
    ShowdownSingles,
    battle_outcome,
    opponent_player,
)


@pytest.fixture(scope="module")
def offline_env():
    # start_listening=False: no server, no websocket — the ctor still builds
    # spaces and the type chart, which is all these tests touch.
    return ShowdownSingles(start_listening=False)


def _battle(won):
    lost = None if won is None else not won
    return SimpleNamespace(won=won, lost=lost)


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
    # The same move features appear for the opponent's REVEALED moves only:
    # gyarados has revealed nothing, so its move blocks are all zero.
    assert not vec[_OPP_ACTIVE + ACTIVE_DIM : OBS_DIM].any()


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
        env_id="Showdown-v0", seed=0, selfplay={"eval_opponent": "max_power"}
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


def _adapter(stub) -> ShowdownEnv:
    env = ShowdownEnv.__new__(ShowdownEnv)  # step()/waits count only
    env._env = stub
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
    battle = SimpleNamespace(won=False, lost=True)
    stub = _StubStack([(-1.0, False, True, False)], battle=battle)
    env = _adapter(stub)
    obs, reward, terminated, truncated, info = env.step(0)
    assert terminated and not truncated
    assert info["outcome"] == -1 and reward == -1.0


def test_tie_is_terminal_with_outcome_zero():
    battle = SimpleNamespace(won=None, lost=None)
    stub = _StubStack([(0.0, False, True, False)], battle=battle)
    env = _adapter(stub)
    obs, reward, terminated, truncated, info = env.step(0)
    assert terminated and not truncated
    assert info["outcome"] == 0 and reward == 0.0


def test_reward_accumulates_across_pump():
    # A wait step that carries the terminal reward (opponent's replacement
    # act finishes the game) must not lose it.
    battle = SimpleNamespace(won=True, lost=False)
    stub = _StubStack([(0.0, False, False, False), (1.0, True, False, False)],
                      battle=battle)
    env = _adapter(stub)
    obs, reward, terminated, truncated, info = env.step(2)
    assert reward == 1.0 and terminated and info["outcome"] == 1
    assert env.waits_absorbed == 1


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
