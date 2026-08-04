"""Loop-split timers: collect / update / eval, on both train-loop paths.

Motivating measurement (2026-08-04): `simulator: 4` bought ~29% collection-side
but +3.7% end-to-end, so the Showdown loop is update-and-encode bound rather
than collection bound. `time/steps_per_sec` cannot distinguish those; these
three keys can. Env-agnostic by construction — nothing here knows about
Showdown, and CartPole is the pin.

The load-bearing assertion is the wall-clock bound: an accumulator that is
never reset, or one that double-counts a step, produces a per-flush total
larger than the entire run took, and no other test would catch it.
"""

import time

from rl.common.config import Config
from rl.common.logging import Logger
from rl.train import train

SPLIT_KEYS = ("time/collect_sec", "time/update_sec")


class Capture(Logger):
    """Records every logged dict, keyed by nothing — order is not asserted."""

    def __init__(self):
        self.records: list[dict] = []

    def log(self, metrics, step):
        self.records.append(dict(metrics))

    def close(self):
        pass


def _run(cfg, monkeypatch, tmp_path):
    capture = Capture()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("rl.train.make_logger", lambda cfg: capture)
    started = time.perf_counter()
    train(cfg)
    return capture.records, time.perf_counter() - started


def _assert_split_contract(records, wall):
    """Every invariant that holds on both paths."""
    splits = [r for r in records if SPLIT_KEYS[0] in r]
    assert splits, "no rollout/episode boundary logged the collect/update split"
    for record in splits:
        for key in SPLIT_KEYS:
            assert key in record, f"{key} missing from a flush that logged the other"
            assert record[key] >= 0.0, f"{key} negative: {record[key]}"
        # Per flush, and summed over the run: the two phases are disjoint
        # slices of the loop, so neither can exceed the wall clock. Catches a
        # missing reset (totals grow without bound) and double counting.
        assert record[SPLIT_KEYS[0]] + record[SPLIT_KEYS[1]] <= wall
    total = sum(r[k] for r in splits for k in SPLIT_KEYS)
    assert total <= wall, f"accumulated {total:.3f}s over a {wall:.3f}s run — reset is broken"

    evals = [r for r in records if "eval/return_mean" in r]
    assert evals, "no eval pass logged"
    for record in evals:
        assert "time/eval_sec" in record, "eval metrics logged without time/eval_sec"
        assert 0.0 <= record["time/eval_sec"] <= wall

    # The no-op pin: the pre-existing keys still arrive, unchanged.
    assert any("time/steps_per_sec" in r for r in records)
    assert any("rollout/episode_return" in r for r in records)
    assert any("rollout/episode_length" in r for r in records)


def test_scalar_loop_logs_the_split(tmp_path, monkeypatch):
    """DQN on CartPole: per-step updates, flushed at the episode boundary."""
    cfg = Config(
        env_id="CartPole-v1",
        seed=0,
        total_steps=300,
        eval_every=150,
        eval_episodes=2,
        run_name="test_timers_dqn",
        logger="tensorboard",
        agent={
            "algo": "dqn",
            "hidden_sizes": [],
            "lr": 1.0e-3,
            "gamma": 0.99,
            "buffer_capacity": 1000,
            "batch_size": 32,
            "learning_starts": 100,
            "target_update_every": 100,
            "epsilon_start": 1.0,
            "epsilon_end": 0.05,
            "epsilon_decay_steps": 200,
        },
    )
    records, wall = _run(cfg, monkeypatch, tmp_path)
    _assert_split_contract(records, wall)


def test_vector_loop_logs_the_split(tmp_path, monkeypatch):
    """PPO on CartPole: the flush rides the rollout boundary, so the split
    lands on exactly the records that carry loss/*."""
    cfg = Config(
        env_id="CartPole-v1",
        seed=0,
        total_steps=320,
        eval_every=160,
        eval_episodes=2,
        run_name="test_timers_ppo",
        logger="tensorboard",
        num_envs=2,
        agent={
            "algo": "ppo", "hidden_sizes": [16], "lr": 3.0e-4, "gamma": 0.99,
            "gae_lambda": 0.95, "rollout_steps": 32, "epochs": 2, "minibatches": 2,
            "clip_eps": 0.2, "entropy_coef": 0.0, "value_coef": 0.5, "max_grad_norm": 0.5,
        },
    )
    records, wall = _run(cfg, monkeypatch, tmp_path)
    _assert_split_contract(records, wall)

    # Rollout-boundary flush: the split rides the same record as the losses,
    # so it is one log call per rollout, not a second series at its own cadence.
    splits = [r for r in records if SPLIT_KEYS[0] in r]
    assert all(any(k.startswith("loss/") for k in r) for r in splits)
    # PPO's update dominates a CartPole rollout only sometimes, but the drain
    # must at least register: a zero here means the timer wraps the wrong call.
    assert any(r["time/update_sec"] > 0.0 for r in splits)
