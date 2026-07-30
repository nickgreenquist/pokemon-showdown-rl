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

from poke_env.battle.move import Move
from poke_env.battle.pokemon import Pokemon
from poke_env.player import MaxBasePowerPlayer, RandomPlayer, SimpleHeuristicsPlayer

from rl.envs.make import make_env
from rl.envs.showdown import (
    OPPONENT_PLAYERS,
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


def test_embed_battle_empty_battle_is_zeros(offline_env):
    battle = SimpleNamespace(
        active_pokemon=None, opponent_active_pokemon=None, team={}, opponent_team={}
    )
    vec = offline_env.embed_battle(battle)
    assert vec.shape == (10,) and vec.dtype == np.float32
    assert not vec.any()


def test_embed_battle_features(offline_env):
    thunderbolt = Move("thunderbolt", gen=1)
    active = SimpleNamespace(moves={"thunderbolt": thunderbolt})
    gyarados = Pokemon(gen=1, species="gyarados")  # water/flying: electric x4
    mon = lambda fainted: SimpleNamespace(fainted=fainted)  # noqa: E731
    battle = SimpleNamespace(
        active_pokemon=active,
        opponent_active_pokemon=gyarados,
        team={"a": mon(True), "b": mon(True), "c": mon(False)},
        opponent_team={"d": mon(True)},
    )
    vec = offline_env.embed_battle(battle)
    assert vec[0] == pytest.approx(0.95)  # base power 95 / 100
    assert vec[4] == 4.0
    assert vec[1] == vec[5] == 0.0  # empty move slots stay zero
    assert vec[8] == pytest.approx(2 / 6)
    assert vec[9] == pytest.approx(1 / 6)
    raw_space = offline_env.observation_spaces[offline_env.possible_agents[0]]
    assert raw_space["observation"].contains(vec)


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
        assert obs.shape == (10,) and obs.dtype == np.float32
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
    env.close()
