"""DQN-specific tests: the n-step accumulator's episode-boundary math
(the three ways it silently goes wrong: late emission, missing flush,
chaining across a boundary), and a smoke run with every toggle on.
"""

import pytest

from rl.agents.dqn import NStepAccumulator
from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.train import train

GAMMA = 0.5  # keeps hand-computed returns exact


def push_step(acc, t, reward, terminated=False, truncated=False):
    """Feed a transition with recognizable labels: obs f"s{t}" -> f"s{t + 1}",
    masks f"m{t}" (acting) and f"m{t + 1}" (next state) — the accumulator is
    data-agnostic, so the labels expose exactly which mask rides where."""
    return acc.push(f"s{t}", t, reward, f"s{t + 1}", terminated, truncated, f"m{t}", f"m{t + 1}")


def test_nstep_full_window():
    acc = NStepAccumulator(n=2, gamma=GAMMA)
    assert push_step(acc, 0, reward=1.0) == []  # window not full yet
    # Window full: oldest entry emits with 2 real rewards, discount gamma^2,
    # its own acting mask, and the mask of the bootstrap state s2.
    assert push_step(acc, 1, reward=2.0) == [
        ("s0", 0, 1.0 + GAMMA * 2.0, "s2", 0.0, GAMMA**2, "m0", "m2")
    ]
    assert push_step(acc, 2, reward=4.0) == [
        ("s1", 1, 2.0 + GAMMA * 4.0, "s3", 0.0, GAMMA**2, "m1", "m3")
    ]


def test_nstep_termination_flushes_partials():
    acc = NStepAccumulator(n=3, gamma=GAMMA)
    push_step(acc, 0, reward=1.0)
    out = push_step(acc, 1, reward=2.0, terminated=True)
    # Both pending entries flush with terminated=1.0 and their partial
    # returns; discounts are gamma^m for the m steps actually taken
    # (masked away at train time, but stored consistently). Every partial
    # shares the terminal state's next_mask m2 — unused under terminated,
    # but always a correctly-shaped value, never a placeholder.
    assert out == [
        ("s0", 0, 1.0 + GAMMA * 2.0, "s2", 1.0, GAMMA**2, "m0", "m2"),
        ("s1", 1, 2.0, "s2", 1.0, GAMMA**1, "m1", "m2"),
    ]


def test_nstep_truncation_flushes_but_still_bootstraps():
    acc = NStepAccumulator(n=3, gamma=GAMMA)
    push_step(acc, 0, reward=1.0)
    out = push_step(acc, 1, reward=2.0, truncated=True)
    # Same flush shape, but terminated=0.0: a time-limit cut still
    # bootstraps from s2 (with the partial-window discount gamma^m), so
    # here the shared next_mask m2 is load-bearing, not just well-shaped.
    assert out == [
        ("s0", 0, 1.0 + GAMMA * 2.0, "s2", 0.0, GAMMA**2, "m0", "m2"),
        ("s1", 1, 2.0, "s2", 0.0, GAMMA**1, "m1", "m2"),
    ]


def test_nstep_does_not_chain_across_episodes():
    acc = NStepAccumulator(n=2, gamma=GAMMA)
    push_step(acc, 0, reward=1.0, terminated=True)  # episode ends
    # New episode: its first transition must start a fresh window — no
    # leftover state from the old episode.
    assert push_step(acc, 10, reward=8.0) == []
    assert push_step(acc, 11, reward=16.0) == [
        ("s10", 10, 8.0 + GAMMA * 16.0, "s12", 0.0, GAMMA**2, "m10", "m12")
    ]


def test_nstep_1_is_vanilla():
    acc = NStepAccumulator(n=1, gamma=GAMMA)
    assert push_step(acc, 0, reward=3.0) == [("s0", 0, 3.0, "s1", 0.0, GAMMA, "m0", "m1")]


def test_dqn_all_toggles_smoke(tmp_path, monkeypatch):
    """Double + dueling + 3-step through the real train loop."""
    monkeypatch.chdir(tmp_path)
    cfg = Config(
        env_id="CartPole-v1",
        seed=0,
        total_steps=300,
        eval_every=150,
        eval_episodes=2,
        run_name="test_dqn_toggles",
        logger="tensorboard",
        agent={
            "algo": "dqn",
            "hidden_sizes": [16],
            "lr": 1.0e-3,
            "gamma": 0.99,
            "buffer_capacity": 1000,
            "batch_size": 32,
            "learning_starts": 100,
            "target_update_every": 100,
            "epsilon_start": 1.0,
            "epsilon_end": 0.05,
            "epsilon_decay_steps": 200,
            "double": True,
            "dueling": True,
            "n_step": 3,
        },
    )
    train(cfg)
    ckpt = load_checkpoint(tmp_path / "runs" / "test_dqn_toggles" / "checkpoint.pt")
    assert ckpt["step"] == 300
    assert ckpt["agent"]["grad_steps"] > 0


def test_dueling_requires_hidden_layer():
    from rl.networks.mlp import DuelingMLP

    with pytest.raises(ValueError):
        DuelingMLP(4, [], 2)
