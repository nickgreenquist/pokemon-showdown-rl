"""Resume-from-checkpoint (2026-08-23, the 24h run-loss bar).

Covers the three layers separately and end to end:
- SnapshotPool.state_dict/load_state_dict round-trips members, generator
  streams, PFSP stats and push ids;
- save_checkpoint extras land in the payload and old checkpoints without
  them still load;
- a vectorized self-play run KILLED mid-flight (simulated at an eval
  boundary after a save) resumes from its own dir, continues to
  total_steps, restores the pool from pool.pt, and appends a resume
  stamp to meta.yaml without losing the original one.
"""

import copy

import numpy as np
import pytest
import torch
import yaml

import rl.train as train_mod
from rl.common.checkpoint import load_checkpoint, save_checkpoint
from rl.common.config import Config
from rl.selfplay.pool import SnapshotPool
from rl.train import train

PPO_AGENT = {
    "algo": "ppo",
    "hidden_sizes": [16],
    "lr": 2.5e-4,
    "gamma": 1.0,
    "gae_lambda": 0.95,
    "rollout_steps": 16,
    "epochs": 1,
    "minibatches": 2,
    "clip_eps": 0.2,
    "entropy_coef": 0.01,
    "value_coef": 0.5,
    "max_grad_norm": 0.5,
}


class _TinyAgent:
    """Just enough for AgentOpponent: actor/critic modules + device."""

    def __init__(self, seed=0):
        g = torch.Generator().manual_seed(seed)
        self.actor = torch.nn.Linear(4, 3)
        self.critic = torch.nn.Linear(4, 1)
        with torch.no_grad():
            for p in list(self.actor.parameters()) + list(self.critic.parameters()):
                p.copy_(torch.rand(p.shape, generator=g))
        self.device = "cpu"


def test_pool_state_roundtrip():
    pool = SnapshotPool(pool_size=3, latest_prob=0.8, pfsp_power=1.0)
    for i in range(4):  # 4 pushes into size 3 -> one eviction exercised
        pool.push(_TinyAgent(seed=i))
    pool.stats[0][:] = [2.0, 4]
    pool.stats[-1][:] = [1.0, 2]
    pool.refresh()
    # consume some generator draws so restored streams differ from fresh
    rng = np.random.default_rng(0)
    obs, mask = np.zeros(4, dtype=np.float32), np.ones(3, dtype=bool)
    for _ in range(3):
        pool.select(rng).move(obs, mask, rng)

    state = pool.state_dict()
    restored = SnapshotPool(pool_size=3, latest_prob=0.8, pfsp_power=1.0)
    restored.load_state_dict(copy.deepcopy(state), agent_factory=_TinyAgent)

    assert restored.push_ids == pool.push_ids
    assert restored.pushes == pool.pushes
    assert [list(s) for s in restored.stats] == [list(s) for s in pool.stats]
    for a, b in zip(pool.members, restored.members):
        for pa, pb in zip(a.agent.actor.parameters(), b.agent.actor.parameters()):
            assert torch.equal(pa, pb)
        assert torch.equal(a.generator.get_state(), b.generator.get_state())
        assert not any(p.requires_grad for p in b.agent.actor.parameters())
    # identical draw streams -> identical next moves
    r1, r2 = np.random.default_rng(7), np.random.default_rng(7)
    assert pool.select(r1).move(obs, mask, r1) == restored.select(r2).move(obs, mask, r2)


def test_pool_config_mismatch_refused():
    pool = SnapshotPool(pool_size=2, latest_prob=0.8)
    pool.push(_TinyAgent())
    other = SnapshotPool(pool_size=3, latest_prob=0.8)
    with pytest.raises(AssertionError):
        other.load_state_dict(pool.state_dict(), agent_factory=_TinyAgent)


def test_checkpoint_extras_roundtrip(tmp_path):
    class _A:
        def state_dict(self):
            return {"w": torch.zeros(1)}

    cfg = Config(env_id="CartPole-v1", seed=0, total_steps=1, eval_every=1,
                 eval_episodes=1, run_name="x", agent={"algo": "ppo"})
    p = tmp_path / "c.pt"
    save_checkpoint(p, _A(), 5, cfg, extras={"loop": {"best_eval": 1.5, "updates_done": 3}})
    ckpt = load_checkpoint(p)
    assert ckpt["loop"] == {"best_eval": 1.5, "updates_done": 3}
    save_checkpoint(p, _A(), 5, cfg)  # no extras: key absent, .get() contract
    assert "loop" not in load_checkpoint(p)


def _selfplay_config(tmp_path, monkeypatch, total_steps):
    monkeypatch.chdir(tmp_path)  # runs/ lands under tmp
    return Config(
        env_id="Connect4-v0",
        seed=0,
        total_steps=total_steps,
        eval_every=128,
        eval_episodes=2,
        checkpoint_every=0,
        run_name="test_resume_c4",
        logger="tensorboard",
        num_envs=4,
        selfplay={"opponent": "self", "eval_opponent": "heuristic",
                  "pool_size": 3, "push_every_updates": 1, "latest_prob": 0.8},
        eval_win_rate=True,
        agent=dict(PPO_AGENT),
    )


def test_killed_selfplay_run_resumes_to_completion(tmp_path, monkeypatch, capsys):
    cfg = _selfplay_config(tmp_path, monkeypatch, total_steps=384)

    real_evaluate = train_mod.evaluate
    calls = {"n": 0}

    def killing_evaluate(*a, **k):
        calls["n"] += 1
        if calls["n"] >= 2:  # first eval+save completes; the kill lands later
            raise KeyboardInterrupt("simulated kill")
        return real_evaluate(*a, **k)

    monkeypatch.setattr(train_mod, "evaluate", killing_evaluate)
    with pytest.raises(KeyboardInterrupt):
        train(cfg)
    monkeypatch.setattr(train_mod, "evaluate", real_evaluate)

    run = tmp_path / "runs" / "test_resume_c4"
    ckpt = load_checkpoint(run / "checkpoint.pt")
    assert 0 < ckpt["step"] < 384
    assert (run / "pool.pt").exists()
    assert "loop" in ckpt

    cfg2 = Config(**yaml.safe_load((run / "config.yaml").read_text()))
    train(cfg2, resume_dir=run)
    out = capsys.readouterr().out
    assert "RESUME: test_resume_c4 from step" in out
    assert "no pool.pt" not in out  # the pool restored, not reseeded

    final = load_checkpoint(run / "checkpoint.pt")
    assert final["step"] >= 384
    meta = yaml.safe_load((run / "meta.yaml").read_text())
    assert len(meta["resumes"]) == 1
    assert meta["resumes"][0]["from_step"] == ckpt["step"]
    assert "started_at" in meta  # the original stamp survived the seam


def test_resume_refuses_config_drift(tmp_path, monkeypatch):
    cfg = _selfplay_config(tmp_path, monkeypatch, total_steps=128)
    train(cfg)
    run = tmp_path / "runs" / "test_resume_c4"
    drifted = yaml.safe_load((run / "config.yaml").read_text())
    drifted["agent"]["lr"] = 1e-3
    with pytest.raises(AssertionError, match="must not silently change"):
        train(Config(**drifted), resume_dir=run)
