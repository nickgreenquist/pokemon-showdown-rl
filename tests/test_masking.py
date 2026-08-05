"""The action-masking contract (rl/common/masking.py + the harness seam).

The first test is the regression guard: an all-True mask must leave logits
bitwise untouched — that property is what makes the masking retrofit a
provable no-op on every env without illegal actions (all of Phases 0-3).
"""

import math

import gymnasium as gym
import numpy as np
import pytest
import torch
from torch.distributions import Categorical

from rl.agents.dqn import DQNAgent
from rl.agents.ppo import PPOAgent
from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.common.masking import masked_entropy, masked_logits, masked_sample
from rl.train import train
from tests.envs.masked_dummy import (
    MAX_EP_LEN,
    MIN_EP_LEN,
    N_ACTIONS,
    MaskedDummyEnv,
    register,
)


def test_all_true_mask_is_bitwise_identity():
    torch.manual_seed(0)
    logits = torch.randn(7, 5) * 100
    out = masked_logits(logits, torch.ones(7, 5, dtype=torch.bool))
    assert torch.equal(out, logits)  # bitwise, not allclose


def test_illegal_probabilities_are_exactly_zero():
    logits = torch.zeros(5)
    mask = torch.tensor([True, False, True, False, False])
    probs = Categorical(logits=masked_logits(logits, mask)).probs
    assert (probs[~mask] == 0.0).all()
    assert probs[mask].sum().item() == pytest.approx(1.0)


def test_sampled_and_argmax_actions_are_legal():
    torch.manual_seed(0)
    logits = torch.randn(5)
    mask = torch.tensor([False, True, False, True, False])
    samples = Categorical(logits=masked_logits(logits, mask)).sample((1000,))
    assert mask[samples].all()
    assert mask[masked_logits(logits, mask).argmax()]


def test_masked_entropy_finite_and_bounded():
    # k legal actions bound entropy by log(k). The -inf sentinel would make
    # this NaN (0 * -inf) — the exact silent bug the finite NEG exists for.
    logits = torch.zeros(2, 5)  # uniform over legal -> entropy == log(k)
    mask = torch.tensor(
        [[True, True, False, False, False], [True, True, True, True, False]]
    )
    ent = masked_entropy(logits, mask)
    assert torch.isfinite(ent).all()
    assert ent[0].item() == pytest.approx(math.log(2))
    assert ent[1].item() == pytest.approx(math.log(4))
    sharp = masked_entropy(torch.tensor([[10.0, 0.0, 0.0, 0.0, 0.0]]), mask[:1])
    assert 0 < sharp.item() < math.log(2)


def test_masked_entropy_matches_categorical_when_all_legal():
    torch.manual_seed(0)
    logits = torch.randn(4, 6)
    ref = Categorical(logits=logits).entropy()
    ours = masked_entropy(logits, torch.ones(4, 6, dtype=torch.bool))
    assert torch.allclose(ours, ref)


def test_all_illegal_mask_asserts():
    with pytest.raises(AssertionError):
        masked_logits(torch.zeros(2, 3), torch.zeros(2, 3, dtype=torch.bool))
    with pytest.raises(AssertionError):
        masked_sample(gym.spaces.Discrete(3), np.zeros(3, dtype=bool))


def test_masked_sample_legal_and_stream_identical_when_all_true():
    space = gym.spaces.Discrete(N_ACTIONS)
    space.seed(0)
    mask = np.array([False, True, False, False, True])
    assert all(mask[masked_sample(space, mask)] for _ in range(200))
    # All-True: rejection accepts the first draw, so the RNG stream matches a
    # bare sample() — fixed-seed spine runs reproduce bit-for-bit.
    space.seed(123)
    bare = [space.sample() for _ in range(50)]
    space.seed(123)
    masked = [masked_sample(space, np.ones(N_ACTIONS, dtype=bool)) for _ in range(50)]
    assert bare == masked


def test_dummy_env_contract():
    env = MaskedDummyEnv()
    obs, info = env.reset(seed=0)
    mask = info["action_mask"]
    assert mask.shape == (N_ACTIONS,) and mask.dtype == np.bool_ and mask.any()
    steps, done = 0, False
    while not done:
        obs, reward, terminated, truncated, info = env.step(int(np.flatnonzero(mask)[0]))
        assert reward == 1.0
        mask = info["action_mask"]
        done = terminated or truncated
        steps += 1
    assert MIN_EP_LEN <= steps <= MAX_EP_LEN
    obs, info = env.reset(seed=1)
    illegal = np.flatnonzero(~info["action_mask"])
    assert illegal.size > 0  # seed-pinned: this draw has an illegal action
    with pytest.raises(ValueError):
        env.step(int(illegal[0]))


def test_ppo_first_epoch_ratio_is_one_with_masking_active():
    """pi_old is recomputed at update start and pi_new on the epoch forwards;
    if only one of them were masked, the very first minibatch's ratio drifts
    from 1 and approx_kl/clip_frac leave zero — the silent corruption this
    contract exists to prevent. With consistent masking they are exactly 0
    (up to kernel-order float noise on the two forward shapes)."""
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    agent = PPOAgent(
        observation_space=gym.spaces.Box(-1.0, 1.0, (3,), np.float32),
        action_space=gym.spaces.Discrete(N_ACTIONS),
        num_envs=2,
        device="cpu",
        lr=1.0e-3,
        gamma=0.99,
        gae_lambda=0.95,
        rollout_steps=4,
        epochs=1,
        minibatches=1,
        clip_eps=0.2,
        entropy_coef=0.01,
        value_coef=0.5,
        max_grad_norm=0.5,
        hidden_sizes=[8],
    )
    for t in range(4):
        masks = rng.random((2, N_ACTIONS)) < 0.5
        masks[np.arange(2), rng.integers(N_ACTIONS, size=2)] = True  # >= 1 legal
        actions = np.array([rng.choice(np.flatnonzero(m)) for m in masks])
        metrics = agent.update(
            (
                rng.uniform(-1, 1, (2, 3)).astype(np.float32),
                actions,
                np.ones(2, dtype=np.float32),
                rng.uniform(-1, 1, (2, 3)).astype(np.float32),
                np.zeros(2, dtype=bool),
                np.zeros(2, dtype=bool),
                masks,
                masks,
            )
        )
    assert abs(metrics["loss/approx_kl"]) < 1e-6  # masked-inconsistency drift is ~1e-1
    assert metrics["loss/clip_frac"] == 0.0


def test_random_agent_end_to_end_on_masked_dummy(tmp_path, monkeypatch):
    """Scalar loop + eval on an env that raises on illegal actions: the
    masked_sample path and the scalar mask threading, end to end."""
    register()
    monkeypatch.chdir(tmp_path)
    cfg = Config(
        env_id="MaskedDummy-v0",
        seed=0,
        total_steps=200,
        eval_every=100,
        eval_episodes=2,
        run_name="test_masked_random",
        logger="tensorboard",
        agent={"algo": "random"},
    )
    train(cfg)  # completing without a ValueError is the assertion


def test_ppo_end_to_end_never_selects_illegal(tmp_path, monkeypatch):
    """PPO through the real vector train loop on the masked dummy env:
    batched masked act, stored-mask epochs, the partial-reset mask merge
    (episode lengths vary so sub-envs desynchronize), and masked eval. The
    env raises on any illegal action, so completing is the assertion."""
    register()
    monkeypatch.chdir(tmp_path)
    cfg = Config(
        env_id="MaskedDummy-v0",
        seed=0,
        total_steps=384,
        eval_every=192,
        eval_episodes=2,
        run_name="test_masked_ppo",
        logger="tensorboard",
        num_envs=2,
        agent={
            "algo": "ppo",
            "hidden_sizes": [16],
            "lr": 2.5e-4,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "rollout_steps": 32,
            "epochs": 2,
            "minibatches": 2,
            "clip_eps": 0.2,
            "entropy_coef": 0.01,
            "value_coef": 0.5,
            "max_grad_norm": 0.5,
        },
    )
    train(cfg)
    ckpt = load_checkpoint(tmp_path / "runs" / "test_masked_ppo" / "checkpoint.pt")
    assert ckpt["agent"]["updates"] == 6  # 384/2 rows, rollout fills every 32


def _dqn_agent(n_step=1, next_q=(5.0, 1.0, 2.0)):
    """Linear DQN with all weights zeroed and the target head's bias pinned:
    Q_target(s', ·) == next_q for every s' and Q_online == 0, so the TD
    target is hand-computable and loss/q reads it back through the Huber."""
    torch.manual_seed(0)
    agent = DQNAgent(
        observation_space=gym.spaces.Box(-1.0, 1.0, (3,), np.float32),
        action_space=gym.spaces.Discrete(3),
        device="cpu",
        lr=1.0e-3,
        gamma=0.5,
        epsilon_start=0.0,
        epsilon_end=0.0,
        epsilon_decay_steps=1,
        buffer_capacity=4,
        batch_size=1,
        learning_starts=1,
        target_update_every=10_000,  # never syncs inside a test
        hidden_sizes=[],
        n_step=n_step,
    )
    with torch.no_grad():
        for p in agent.q.parameters():
            p.zero_()
        for p in agent.q_target.parameters():
            p.zero_()
        agent.q_target[0].bias.copy_(torch.tensor(next_q))
    return agent


def test_dqn_target_max_respects_next_mask():
    """§5: the bootstrap max must range over actions legal in s'. Hand case
    where the illegal action holds the highest Q — Q_target(s') = [5, 1, 2],
    gamma 0.5, r 1, Q_online == 0:
    unmasked target 1 + 0.5*5 = 3.5 -> Huber loss 3.0
    masked (action 0 illegal in s') 1 + 0.5*2 = 2.0 -> Huber loss 1.5"""
    all_true = np.ones(3, dtype=bool)
    no_action0 = np.array([False, True, True])
    obs = np.zeros(3, dtype=np.float32)

    def run(next_mask):
        return _dqn_agent().update((obs, 0, 1.0, obs, False, False, all_true, next_mask))

    assert run(all_true)["loss/q"] == pytest.approx(3.0)
    assert run(no_action0)["loss/q"] == pytest.approx(1.5)


def test_dqn_nstep_target_uses_bootstrap_state_mask():
    """The n-step path is distinct from 1-step: next_mask must be the mask of
    the bootstrap state s_{t+n} (the accumulator's flush-time state), not the
    first transition's. n=2, gamma 0.5, rewards 1 then 2: R = 2, discount
    0.25; unmasked 2 + 0.25*5 = 3.25 -> Huber 2.75, masked (action 0 illegal
    in s2) 2 + 0.25*2 = 2.5 -> Huber 2.0."""
    all_true = np.ones(3, dtype=bool)
    no_action0 = np.array([False, True, True])
    obs = np.zeros(3, dtype=np.float32)

    def run(final_next_mask):
        agent = _dqn_agent(n_step=2)
        first = agent.update((obs, 0, 1.0, obs, False, False, all_true, all_true))
        assert first == {}  # window not full: nothing emitted, nothing learned
        return agent.update((obs, 1, 2.0, obs, False, False, all_true, final_next_mask))

    assert run(all_true)["loss/q"] == pytest.approx(2.75)
    assert run(no_action0)["loss/q"] == pytest.approx(2.0)


def test_dqn_end_to_end_never_selects_illegal(tmp_path, monkeypatch):
    """DQN through the scalar loop on the masked dummy env: masked ε-greedy
    (ε=1 early hammers the sampler), masked greedy argmax, masked n-step
    target threading, and masked eval. The env raises on any illegal action,
    so completing is the assertion."""
    register()
    monkeypatch.chdir(tmp_path)
    cfg = Config(
        env_id="MaskedDummy-v0",
        seed=0,
        total_steps=300,
        eval_every=150,
        eval_episodes=2,
        run_name="test_masked_dqn",
        logger="tensorboard",
        agent={
            "algo": "dqn",
            "hidden_sizes": [16],
            "lr": 1.0e-3,
            "gamma": 0.99,
            "buffer_capacity": 500,
            "batch_size": 16,
            "learning_starts": 50,
            "target_update_every": 100,
            "epsilon_start": 1.0,
            "epsilon_end": 0.1,
            "epsilon_decay_steps": 200,
            "n_step": 2,
        },
    )
    train(cfg)  # completing without a ValueError is the assertion
