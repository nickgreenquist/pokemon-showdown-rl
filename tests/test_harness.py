"""CartPole sanity test — the known-good path when a reward curve goes flat.

Runs the real train loop end-to-end (env -> rollout -> logging -> eval ->
checkpoint) with a random agent for a few hundred steps and asserts it
completes. Must stay green for the life of the project.
"""

import numpy as np

from rl.agents.random_agent import RandomAgent
from rl.common.masking import masked_sample
from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.train import ALGOS, train


def test_cartpole_harness_completes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # runs/ output lands in the tmp dir
    cfg = Config(
        env_id="CartPole-v1",
        seed=0,
        total_steps=300,
        eval_every=150,
        eval_episodes=2,
        run_name="test_cartpole",
        logger="tensorboard",  # offline backend; keeps tests free of W&B auth
        agent={"algo": "random"},
    )
    train(cfg)
    ckpt = load_checkpoint(tmp_path / "runs" / "test_cartpole" / "checkpoint.pt")
    assert ckpt["step"] == 300
    assert ckpt["config"]["env_id"] == "CartPole-v1"




class _VecRandomAgent(RandomAgent):
    """Minimal agent on the vectorized constructor contract (single sub-env
    spaces + num_envs): keeps the vector collection path tested independently
    of PPO. Batched act() during collection, a single action when eval drives
    its scalar env."""

    vectorized = True

    def __init__(self, observation_space, action_space, num_envs, device):
        super().__init__(action_space)
        self.num_envs = num_envs

    def act(self, obs, action_mask=None, deterministic=False):
        if deterministic:  # eval: one scalar env, one action
            return masked_sample(self.action_space, action_mask)
        return np.array(
            [masked_sample(self.action_space, action_mask[i]) for i in range(self.num_envs)]
        )


def test_vector_path_smoke(tmp_path, monkeypatch):
    """Vector collection path end-to-end before its real consumer exists:
    batched transitions, manual partial resets at episode ends, eval and
    checkpointing on the unchanged scalar protocol."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(ALGOS, "vec_random", _VecRandomAgent)
    cfg = Config(
        env_id="CartPole-v1",
        seed=0,
        total_steps=300,
        eval_every=150,
        eval_episodes=2,
        run_name="test_vector_random",
        logger="tensorboard",
        num_envs=4,
        agent={"algo": "vec_random"},
    )
    train(cfg)
    ckpt = load_checkpoint(tmp_path / "runs" / "test_vector_random" / "checkpoint.pt")
    assert ckpt["step"] == 300  # 4 divides 300: the loop lands exactly
    # Random episodes are ~20 steps, so episode ends (and partial resets)
    # happened many times; the first eval always sets a best.
    assert (tmp_path / "runs" / "test_vector_random" / "best_checkpoint.pt").exists()
