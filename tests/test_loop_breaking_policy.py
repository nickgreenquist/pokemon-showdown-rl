"""The loop breaker wired as a seat (RESULTS §28): `LoopBreakingPolicy` over a
PPOAgent or an EnsembleAgent is bit-identical to the bare argmax until a
position repeats, escapes the fixed point at the threshold, forgets at the
battle boundary, and delegates everything else to the seat it wraps."""
import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent
from rl.common.loop_breaker import LoopBreakingPolicy
from rl.search.ensemble import EnsembleAgent


class _Member:
    obs_rank = 1
    device = torch.device("cpu")

    def __init__(self, w):
        self._w = torch.tensor(w, dtype=torch.float32)

    def actor(self, t):
        return t @ self._w


def _ppo(seed=0):
    torch.manual_seed(seed)
    return PPOAgent(
        observation_space=gym.spaces.Box(-1.0, 1.0, (12,), np.float32),
        action_space=gym.spaces.Discrete(6), num_envs=1, device="cpu", lr=1e-3,
        gamma=1.0, gae_lambda=0.95, rollout_steps=8, epochs=1, minibatches=1,
        clip_eps=0.2, entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
        hidden_sizes=[16, 16], lr_anneal_steps=100,
    )


def _draw(rng):
    obs = rng.standard_normal(12).astype(np.float32)
    mask = rng.random(6) < 0.7
    if mask.sum() < 2:
        mask[:2] = True
    return obs, mask


def test_bare_argmax_is_bit_identical_for_both_agent_kinds():
    rng = np.random.default_rng(0)
    ens = EnsembleAgent([_Member(rng.standard_normal((12, 6))) for _ in range(3)])
    for agent in (ens, _ppo()):
        wrapped = LoopBreakingPolicy(agent)
        for _ in range(200):
            obs, mask = _draw(rng)
            bare = agent.act(obs, mask, deterministic=True)
            assert wrapped.act(obs, mask, deterministic=True) == bare
            assert int(np.argmax(agent.scores(obs, mask))) == bare
            assert not mask[np.argmin(agent.scores(obs, mask))] or mask.all()
        assert wrapped.counters["loop/fired"] == 0
        assert wrapped.counters["loop/decisions"] == 200


def test_a_fixed_point_is_escaped_at_the_threshold_and_reset_forgets():
    rng = np.random.default_rng(1)
    agent = _ppo(1)
    wrapped = LoopBreakingPolicy(agent, threshold=4)
    obs, mask = _draw(rng)
    a = agent.act(obs, mask, deterministic=True)
    scores = agent.scores(obs, mask)
    legal = np.flatnonzero(mask)
    runner_up = int(legal[np.argsort(-scores[legal], kind="stable")][1])
    plays = [wrapped.act(obs, mask, deterministic=True) for _ in range(6)]
    assert plays[:4] == [a] * 4 and plays[4] == runner_up and plays[5] == runner_up
    assert wrapped.counters["loop/fired"] >= 1
    assert 0.0 < wrapped.counters["loop/fired_rate"] <= 1.0
    wrapped.reset_episode()
    assert wrapped.act(obs, mask, deterministic=True) == a


def test_delegation_and_the_deterministic_contract():
    rng = np.random.default_rng(2)
    ens = EnsembleAgent([_Member(rng.standard_normal((12, 6)))])
    wrapped = LoopBreakingPolicy(ens)
    assert wrapped.members is ens.members and wrapped.obs_rank == 1
    assert wrapped.decisions == 0  # the ensemble's own counter, through the wrapper
    with pytest.raises(AssertionError):
        wrapped.act(np.zeros(12, np.float32), np.ones(6, bool), deterministic=False)
    with pytest.raises(AttributeError):
        wrapped.no_such_attribute
