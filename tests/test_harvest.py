"""BI-G4-1 — the both-seat harvest (rl/selfplay/harvest.py; JOURNEY step 4,
Wang's "each game produced two games for the algorithm to learn from").

Offline: the sink's episode semantics, the member's recorded log-prob (same
draw as move(), the harvest never changes play), PPO's union batch (and its
bit-identity when the sink is empty), the refusals, and train.py's config
seam. Live (skips without a server on :8000): seat 2's rows through the real
PoolPlayer on gen 1 and on gen 4 — terminal reward is seat 2's own outcome,
rows are that seat's decisions, log-probs are the member's.
"""

import math
import socket
from types import SimpleNamespace

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent
from rl.common.config import Config
from rl.selfplay.harvest import SeatHarvest
from rl.selfplay.pool import AgentOpponent, SnapshotPool

OBS_D, N_ACT, N_ENVS, HORIZON = 3, 4, 2, 4


def _agent(seed=0, **over):
    kwargs = dict(
        observation_space=gym.spaces.Box(-1.0, 1.0, (OBS_D,), np.float32),
        action_space=gym.spaces.Discrete(N_ACT), num_envs=N_ENVS, device="cpu",
        lr=1e-3, gamma=0.9999, gae_lambda=0.754, rollout_steps=HORIZON, epochs=2,
        minibatches=2, clip_eps=0.0829, entropy_coef=0.0588, value_coef=0.4375,
        max_grad_norm=0.543, hidden_sizes=[8],
    )
    kwargs.update(over)
    torch.manual_seed(seed)
    return PPOAgent(**kwargs)


def _fill(agent, seed):
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    metrics = {}
    for t in range(HORIZON):
        obs = rng.normal(size=(N_ENVS, OBS_D)).astype(np.float32)
        nxt = rng.normal(size=(N_ENVS, OBS_D)).astype(np.float32)
        masks = np.ones((N_ENVS, N_ACT), dtype=bool)
        acts = agent.act(obs, masks)
        rews = rng.normal(size=N_ENVS).astype(np.float32)
        term = np.array([t == HORIZON - 1] * N_ENVS)
        metrics = agent.update((obs, acts, rews, nxt, term, np.zeros(N_ENVS, dtype=bool), masks, masks))
    return metrics


# --- the sink ---------------------------------------------------------------

def test_sink_builds_seat2_episodes_with_its_own_terminal_outcome():
    h = SeatHarvest()
    obs = np.zeros(OBS_D, dtype=np.float32)
    mask = np.ones(N_ACT, dtype=bool)
    for i in range(3):
        h.record("b1", obs + i, mask, i % N_ACT, -0.5 * i, version=7)
    h.record("b2", obs, mask, 1, -1.0, version=6)
    assert h.open_battles == 2 and len(h) == 0
    h.finish("b1", -1)  # learner won -> seat 2 lost
    h.finish("b2", 0)   # tie
    assert h.open_battles == 0 and len(h) == 2 and h.pending_rows == 4
    batch, stats = h.drain()
    assert batch["lengths"].tolist() == [3, 1]
    assert batch["rewards"].tolist() == [0.0, 0.0, -1.0, 0.0]
    assert batch["old_logp"].tolist() == [0.0, -0.5, -1.0, -1.0]
    assert batch["version"].tolist() == [7, 7, 7, 6]
    assert batch["obs"].shape == (4, OBS_D) and batch["obs"].dtype == np.float32
    assert batch["masks"].dtype == np.bool_ and batch["actions"].dtype == np.int64
    assert stats["harvest/episodes"] == 2 and stats["harvest/rows"] == 4
    assert stats["harvest/version_min"] == 6
    assert len(h) == 0 and h.counts["episodes"] == 0  # reset after drain


def test_sink_counts_drops_discards_and_empties():
    h = SeatHarvest()
    mask = np.ones(N_ACT, dtype=bool)
    h.drop_row("b1")                      # mask-desync recovery: no row
    h.finish("b1", 1)                     # nothing recorded -> empty
    h.record("b2", np.zeros(OBS_D), mask, 0, 0.0, 1)
    h.discard("b2")                       # swept finished, no report
    h.discard("never")                    # unknown tag: no-op
    h.record("b3", np.zeros(OBS_D), mask, 0, 0.0, 1)
    h.finish("b3", 1)
    _, stats = h.drain()
    assert stats["harvest/rows_dropped"] == 1 and stats["harvest/empty"] == 1
    assert stats["harvest/discarded"] == 1 and stats["harvest/episodes"] == 1


# --- the member's recorded log-prob ------------------------------------------

def test_move_logp_is_the_same_draw_as_move_with_the_masked_logprob():
    agent = _agent()
    a, b = AgentOpponent(agent, seed=3), AgentOpponent(agent, seed=3)
    rng = np.random.default_rng(0)
    for _ in range(20):
        obs = rng.normal(size=OBS_D).astype(np.float32)
        mask = rng.random(N_ACT) > 0.4
        mask[rng.integers(N_ACT)] = True
        act_a = a.move(obs, mask, rng)
        act_b, logp = b.move_logp(obs, mask, rng)
        assert act_a == act_b and mask[act_b]
        with torch.no_grad():
            from rl.common.masking import masked_logits
            logits = masked_logits(agent.actor(torch.as_tensor(obs).unsqueeze(0)), torch.as_tensor(mask))
            want = torch.log_softmax(logits, dim=-1)[0, act_b].item()
        assert math.isclose(logp, want, rel_tol=1e-5, abs_tol=1e-6) and logp <= 0.0


# --- PPO's union batch --------------------------------------------------------

def _episode(rng, length, version, outcome):
    obs = rng.normal(size=(length, OBS_D)).astype(np.float32)
    masks = np.ones((length, N_ACT), dtype=bool)
    actions = rng.integers(0, N_ACT, size=length)
    return obs, masks, actions, version, outcome


def test_update_trains_on_seat1_plus_harvested_seat2_rows_and_reports():
    agent = _agent()
    h = SeatHarvest()
    agent.attach_harvest(h)
    rng = np.random.default_rng(1)
    for tag, (length, version, outcome) in {"x": (5, 0, +1), "y": (3, 0, -1)}.items():
        obs, masks, actions, ver, out = _episode(rng, length, version, outcome)
        for t in range(length):
            h.record(tag, obs[t], masks[t], int(actions[t]), -math.log(N_ACT), ver)
        h.finish(tag, out)
    metrics = _fill(agent, seed=1)
    assert metrics["harvest/rows_this_update"] == 8.0 and metrics["harvest/seat1_rows"] == 8.0
    assert metrics["harvest/episodes"] == 2.0 and metrics["harvest/rows"] == 8.0
    assert metrics["harvest/version_lag_max"] == 0.0  # updates 0 - version 0
    assert math.isfinite(metrics["loss/policy"]) and math.isfinite(metrics["loss/value"])
    assert len(h) == 0  # drained
    # The next fill has nothing pending: no harvest keys, still trains.
    metrics = _fill(agent, seed=2)
    assert "harvest/rows_this_update" not in metrics and math.isfinite(metrics["loss/policy"])


def test_update_with_an_empty_sink_is_bit_identical_to_no_sink():
    plain, sunk = _agent(seed=4), _agent(seed=4)
    sunk.attach_harvest(SeatHarvest())
    mp, ms = _fill(plain, seed=9), _fill(sunk, seed=9)
    assert mp == ms
    for a, b in zip(plain.actor.parameters(), sunk.actor.parameters()):
        assert torch.equal(a, b)
    for a, b in zip(plain.critic.parameters(), sunk.critic.parameters()):
        assert torch.equal(a, b)


def test_harvest_refusals():
    with pytest.raises(ValueError, match="privileged"):
        _agent(privileged_dim=2).attach_harvest(SeatHarvest())


# --- train.py's seam ------------------------------------------------------------

def _cfg(**over):
    base = dict(
        env_id="Connect4-v0", seed=0, total_steps=64, eval_every=64, eval_episodes=1,
        run_name="h", logger="tensorboard", num_envs=2,
        selfplay={"opponent": "self", "eval_opponent": "heuristic", "pool_size": 1,
                  "latest_prob": 1.0, "push_every_updates": 1, "harvest_both_seats": True},
        agent={"algo": "ppo", "hidden_sizes": [8], "lr": 1e-3, "gamma": 1.0, "gae_lambda": 0.95,
               "rollout_steps": 8, "epochs": 1, "minibatches": 2, "clip_eps": 0.2,
               "entropy_coef": 0.01, "value_coef": 0.5, "max_grad_norm": 0.5},
    )
    base.update(over)
    return Config(**base)


def test_train_seam_refuses_non_showdown_non_self_and_async(tmp_path, monkeypatch):
    from rl.train import _async_collector_mode, train

    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="Showdown-only"):
        train(_cfg())
    sp = {"opponent": "heuristic", "eval_opponent": "heuristic", "harvest_both_seats": True}
    with pytest.raises(ValueError, match="opponent 'self'"):
        train(_cfg(selfplay=sp))
    cfg = _cfg(env_id="Showdown-v0", collector={"mode": "async", "concurrency": 2})
    with pytest.raises(ValueError, match="no seat-2 harvest hook"):
        _async_collector_mode(cfg, vectorized=True)


# --- live: the real PoolPlayer on both generations ----------------------------------

def _server_up() -> bool:
    try:
        socket.create_connection(("127.0.0.1", 8000), timeout=0.5).close()
        return True
    except OSError:
        return False


def _run_live(env_id, fake_spaces, seed):
    from rl.envs.make import make_env

    obs_space, act_space = fake_spaces()
    torch.manual_seed(seed)
    member = PPOAgent(obs_space, act_space, num_envs=1, device="cpu", lr=1e-3, gamma=1.0,
                      gae_lambda=0.95, rollout_steps=4, epochs=1, minibatches=1, clip_eps=0.2,
                      entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[8])
    pool = SnapshotPool(pool_size=1, latest_prob=1.0)
    pool.push(member)
    harvest = SeatHarvest()
    env = make_env(env_id, seed=seed, env_kwargs={"opponent": pool, "harvest": harvest})
    rng = np.random.default_rng(seed)
    outcomes, seat1_steps = [], []
    try:
        for ep in range(2):
            obs, info = env.reset(seed=seed + ep)
            done, steps = False, 0
            while not done:
                legal = np.flatnonzero(info["action_mask"])
                obs, _, term, trunc, info = env.step(int(rng.choice(legal)))
                done = term or trunc
                steps += 1
            outcomes.append(info["outcome"])
            seat1_steps.append(steps)
    finally:
        env.close()
    assert len(harvest) == 2 and harvest.open_battles == 0
    batch, stats = harvest.drain()
    assert stats["harvest/episodes"] == 2 and stats["harvest/discarded"] == 0
    ends = np.cumsum(batch["lengths"]) - 1
    assert batch["rewards"][ends].tolist() == [-o for o in outcomes]
    assert (batch["rewards"][[i for i in range(len(batch["rewards"])) if i not in set(ends)]] == 0).all()
    assert batch["obs"].shape == (int(batch["lengths"].sum()), obs_space.shape[0])
    assert np.isfinite(batch["old_logp"]).all() and (batch["old_logp"] <= 0).all()
    assert (batch["masks"][np.arange(len(batch["actions"])), batch["actions"]]).all()
    assert (batch["version"] == 0).all()
    # Seat 2 decided about as often as seat 1 (forced replacements differ by a few).
    for n2, n1 in zip(batch["lengths"], seat1_steps):
        assert abs(int(n2) - n1) <= max(6, n1 // 2), (n2, n1)
    return batch


@pytest.mark.live_server
@pytest.mark.skipif(not _server_up(), reason="no local Showdown server on :8000")
def test_live_gen1_seat2_rows_are_harvested():
    from rl.envs.showdown import fake_spaces

    _run_live("Showdown-v0", fake_spaces, seed=41)


@pytest.mark.live_server
@pytest.mark.skipif(not _server_up(), reason="no local Showdown server on :8000")
def test_live_gen4_seat2_rows_are_harvested():
    from rl.envs.gen4.env import fake_spaces_gen4

    batch = _run_live("ShowdownGen4-v0", fake_spaces_gen4, seed=43)
    assert batch["obs"].shape[1] == 1448
