"""Resume-from-checkpoint (2026-08-23, the 24h run-loss bar).

Covers the three layers separately and end to end:
- SnapshotPool.state_dict/load_state_dict round-trips members, generator
  streams, PFSP stats and push ids;
- save_checkpoint extras land in the payload and old checkpoints without
  them still load;
- a vectorized self-play run KILLED mid-flight (simulated at an eval
  boundary after a save) resumes from its own dir, continues to
  total_steps, restores the pool from the checkpoint payload, and appends
  a resume stamp to meta.yaml without losing the original one;
- F-05 (2026-09-03): checkpoint.pt is the ONE resume artifact — the pool
  rides inside it stamped with the step it pairs with, written every
  SAVE_LATEST_EVERY_UPDATES update boundaries rather than at evals; a
  pre-F-05 run dir (checkpoint.pt without a pool key + pool.pt — the live
  100M fleet's format) still resumes exactly as before, with a disclosure;
  a torn stamp is refused.
"""

import copy
from pathlib import Path

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
    pool = SnapshotPool(pool_size=3, latest_prob=0.8)
    for i in range(4):  # 4 pushes into size 3 -> one eviction exercised
        pool.push(_TinyAgent(seed=i))
    pool.stats[0][:] = [2.0, 4]
    pool.stats[-1][:] = [1.0, 2]
    # consume some generator draws so restored streams differ from fresh
    rng = np.random.default_rng(0)
    obs, mask = np.zeros(4, dtype=np.float32), np.ones(3, dtype=bool)
    for _ in range(3):
        pool.select(rng).move(obs, mask, rng)

    state = pool.state_dict()
    restored = SnapshotPool(pool_size=3, latest_prob=0.8)
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


def _run_and_kill_at_second_eval(cfg, monkeypatch) -> Path:
    """A 384-step self-play run killed at its SECOND eval. Updates land every
    64 steps (4 envs x 16 rollout_steps); the first eval (step 128) completes,
    the update-cadence save at update 4 (step 256) completes, then the eval
    at 256 raises — so the dir holds a mid-run checkpoint.pt at step 256 and
    nothing past it. Returns the run dir."""
    real_evaluate = train_mod.evaluate
    calls = {"n": 0}

    def killing_evaluate(*a, **k):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise KeyboardInterrupt("simulated kill")
        return real_evaluate(*a, **k)

    monkeypatch.setattr(train_mod, "evaluate", killing_evaluate)
    with pytest.raises(KeyboardInterrupt):
        train(cfg)
    monkeypatch.setattr(train_mod, "evaluate", real_evaluate)
    return Path.cwd() / "runs" / cfg.run_name


def _resume(run: Path) -> None:
    cfg2 = Config(**yaml.safe_load((run / "config.yaml").read_text()))
    train(cfg2, resume_dir=run)


def test_killed_selfplay_run_resumes_to_completion(tmp_path, monkeypatch, capsys):
    cfg = _selfplay_config(tmp_path, monkeypatch, total_steps=384)
    run = _run_and_kill_at_second_eval(cfg, monkeypatch)

    ckpt = load_checkpoint(run / "checkpoint.pt")
    assert 0 < ckpt["step"] < 384
    assert "loop" in ckpt
    # F-05: the pool rides INSIDE the payload, stamped with the step it pairs
    # with, and the second file is gone — one rename, one atomic pair.
    assert ckpt["pool"]["step"] == ckpt["step"]
    assert ckpt["pool"]["state"]["pushes"] == 1 + 4  # step-0 push + one per update
    assert not (run / "pool.pt").exists()

    _resume(run)
    out = capsys.readouterr().out
    assert "RESUME: test_resume_c4 from step" in out
    assert "no pool.pt" not in out  # the pool restored, not reseeded
    assert "legacy pool.pt" not in out  # ...and from the payload, not a fallback

    final = load_checkpoint(run / "checkpoint.pt")
    assert final["step"] >= 384
    assert final["pool"]["step"] == final["step"]
    meta = yaml.safe_load((run / "meta.yaml").read_text())
    assert len(meta["resumes"]) == 1
    assert meta["resumes"][0]["from_step"] == ckpt["step"]
    assert meta["resumes"][0]["pool_source"] == "checkpoint.pt"
    assert "started_at" in meta  # the original stamp survived the seam


def test_legacy_pool_pt_run_dir_resumes_with_disclosure(tmp_path, monkeypatch, capsys):
    """The live fleet's format — checkpoint.pt WITHOUT a pool key beside a
    pool.pt — must resume exactly as it did before F-05: pool restored (not
    reseeded), the unverifiable pairing disclosed, the source recorded."""
    cfg = _selfplay_config(tmp_path, monkeypatch, total_steps=384)
    run = _run_and_kill_at_second_eval(cfg, monkeypatch)
    # Rewrite the dir into the pre-F-05 layout.
    ckpt = load_checkpoint(run / "checkpoint.pt")
    legacy_pool = ckpt.pop("pool")["state"]
    torch.save(ckpt, run / "checkpoint.pt")
    torch.save(legacy_pool, run / "pool.pt")
    capsys.readouterr()  # drop the killed run's output

    _resume(run)
    out = capsys.readouterr().out
    assert ("RESUME: legacy pool.pt (pre-F-05 run dir) — pool/checkpoint "
            "pairing not verifiable") in out
    assert "no pool.pt" not in out
    meta = yaml.safe_load((run / "meta.yaml").read_text())
    assert meta["resumes"][0]["pool_source"] == "pool.pt"
    # Restored, not reseeded: the lifetime push counter continues from the
    # legacy snapshot through the two remaining updates (push_every 1); a
    # reseed would have restarted it at 1. The step-0 anchor is still there.
    final = load_checkpoint(run / "checkpoint.pt")
    assert final["pool"]["state"]["pushes"] == legacy_pool["pushes"] + 2
    assert final["pool"]["state"]["push_ids"][0] == legacy_pool["push_ids"][0] == 0


def test_torn_pool_stamp_refuses_to_resume(tmp_path, monkeypatch):
    """The pair check: a pool stamped with another step than the learner's
    is exactly the silent mismatch F-05 exists to rule out."""
    cfg = _selfplay_config(tmp_path, monkeypatch, total_steps=384)
    run = _run_and_kill_at_second_eval(cfg, monkeypatch)
    ckpt = load_checkpoint(run / "checkpoint.pt")
    ckpt["pool"]["step"] = ckpt["step"] - 64  # a pool from the previous boundary
    torch.save(ckpt, run / "checkpoint.pt")

    with pytest.raises(AssertionError, match="pool/checkpoint pair is torn"):
        _resume(run)
    # A refused resume leaves no trace of a resume that never happened.
    meta = yaml.safe_load((run / "meta.yaml").read_text())
    assert "resumes" not in meta


def test_checkpoint_rides_update_boundaries_not_evals(tmp_path, monkeypatch):
    """F-05 cadence: checkpoint.pt is written every SAVE_LATEST_EVERY_UPDATES
    update boundaries (64 steps each here) plus once at the end, and never
    from the eval block — with eval_every at 8 updates the first save lands
    strictly between evals, which the old eval-coupled cadence could not do."""
    cfg = _selfplay_config(tmp_path, monkeypatch, total_steps=512)
    cfg.eval_every = 512
    real_save = train_mod.save_checkpoint
    saves: list[tuple[str, int]] = []

    def recording_save(path, agent, step, *a, **k):
        saves.append((Path(path).name, step))
        return real_save(path, agent, step, *a, **k)

    monkeypatch.setattr(train_mod, "save_checkpoint", recording_save)
    train(cfg)

    per_update = cfg.num_envs * cfg.agent["rollout_steps"]
    k = train_mod.SAVE_LATEST_EVERY_UPDATES
    latest = [step for name, step in saves if name == "checkpoint.pt"]
    assert latest == [k * per_update, 2 * k * per_update, 512]  # cadence x2, then end
    names = [name for name, _ in saves]
    assert names.index("checkpoint.pt") < names.index("best_checkpoint.pt")
    assert not (Path.cwd() / "runs" / cfg.run_name / "pool.pt").exists()


def test_resume_refuses_config_drift(tmp_path, monkeypatch):
    cfg = _selfplay_config(tmp_path, monkeypatch, total_steps=128)
    train(cfg)
    run = tmp_path / "runs" / "test_resume_c4"
    drifted = yaml.safe_load((run / "config.yaml").read_text())
    drifted["agent"]["lr"] = 1e-3
    with pytest.raises(AssertionError, match="must not silently change"):
        train(Config(**drifted), resume_dir=run)
