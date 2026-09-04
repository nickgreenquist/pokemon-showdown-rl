"""Loop-split timers: collect / update / eval, on both train-loop paths.

Motivating measurement (2026-08-04): `simulator: 4` bought ~29% collection-side
but +3.7% end-to-end, so the Showdown loop is update-and-encode bound rather
than collection bound. `time/steps_per_sec` cannot distinguish those; these
three keys can. Env-agnostic by construction — nothing here knows about
Showdown, and CartPole is the pin.

The load-bearing assertion is the wall-clock bound: an accumulator that is
never reset, or one that double-counts a step, produces a per-flush total
larger than the entire run took, and no other test would catch it.

`time/realized_steps_per_sec` (F-16) is pinned here on the same principle: it
is dStep/dWall over windows that must TILE the run, so the implied wall time of
all windows is bounded by the run's, and a pause has to show up inside one.
"""

import time

import rl.train as train_mod
from rl.common.config import Config
from rl.common.logging import Logger
from rl.train import train

SPLIT_KEYS = ("time/collect_sec", "time/update_sec")


class Capture(Logger):
    """Records every logged dict in call order, and the step it was logged at
    — F-16's windows are a (step, wall) series, so the step is not optional."""

    def __init__(self):
        self.records: list[dict] = []
        self.steps: list[int] = []

    def log(self, metrics, step):
        self.records.append(dict(metrics))
        self.steps.append(step)

    def close(self):
        pass


def _run(cfg, monkeypatch, tmp_path, patch=None):
    capture = Capture()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("rl.train.make_logger", lambda cfg: capture)
    if patch is not None:
        patch(monkeypatch)
    started = time.perf_counter()
    train(cfg)
    return capture, time.perf_counter() - started


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




def _ppo_cfg(**over) -> Config:
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
    for key, value in over.items():
        setattr(cfg, key, value)
    return cfg


def test_vector_loop_logs_the_split(tmp_path, monkeypatch):
    """PPO on CartPole: the flush rides the rollout boundary, so the split
    lands on exactly the records that carry loss/*."""
    capture, wall = _run(_ppo_cfg(), monkeypatch, tmp_path)
    records = capture.records
    _assert_split_contract(records, wall)

    # Rollout-boundary flush: the split rides the same record as the losses,
    # so it is one log call per rollout, not a second series at its own cadence.
    splits = [r for r in records if SPLIT_KEYS[0] in r]
    assert all(any(k.startswith("loss/") for k in r) for r in splits)
    # PPO's update dominates a CartPole rollout only sometimes, but the drain
    # must at least register: a zero here means the timer wraps the wrong call.
    assert any(r["time/update_sec"] > 0.0 for r in splits)


def test_vector_loop_logs_the_realized_rate(tmp_path, monkeypatch):
    """F-16: `time/realized_steps_per_sec` is dStep/dWall between consecutive
    update-boundary logs, with every pause inside a denominator.

    Two things are pinned. (1) The windows TILE the run — their step deltas sum
    to the run's steps and their implied wall times sum to no more than the run
    took, which is what catches a mark updated in the wrong place or not at
    all. (2) A pause really does land in the rate: eval is slowed to 0.25 s, so
    the window straddling it must read far slower than a collection-only one
    and, being the same window, slower than that record's own
    `time/steps_per_sec` — which is the poll/episode-cadence estimator F-16
    exists to sit beside, not replace."""
    def slow_eval(monkeypatch):
        real = train_mod.evaluate

        def evaluate(*a, **k):
            time.sleep(0.25)
            return real(*a, **k)

        monkeypatch.setattr("rl.train.evaluate", evaluate)

    cfg = _ppo_cfg(total_steps=640, eval_every=192)
    capture, wall = _run(cfg, monkeypatch, tmp_path, patch=slow_eval)
    per_update = cfg.num_envs * cfg.agent["rollout_steps"]

    updates = [
        (record, step)
        for record, step in zip(capture.records, capture.steps)
        if "time/realized_steps_per_sec" in record
    ]
    assert len(updates) == cfg.total_steps // per_update
    # Every update-boundary log carries it, and only those do.
    assert all(SPLIT_KEYS[0] in record for record, _ in updates)
    assert sum(1 for r in capture.records if "time/realized_steps_per_sec" in r) == len(updates)

    prev_step, implied = 0, 0.0
    for record, step in updates:
        rate = record["time/realized_steps_per_sec"]
        assert rate > 0.0
        implied += (step - prev_step) / rate
        prev_step = step
    # Tiling: the windows cover the run exactly once, so the wall they imply
    # cannot exceed the run's own (it is short of it only by startup).
    assert prev_step == cfg.total_steps
    assert implied <= wall

    # The slowed eval lands in the FOLLOWING window, which must therefore read
    # far below a collection-only one — and below every reading of the estimator
    # series, which never sees the pause.
    rates = [record["time/realized_steps_per_sec"] for record, _ in updates]
    estimator = [r["time/steps_per_sec"] for r in capture.records if "time/steps_per_sec" in r]
    assert estimator, "the poll/episode-cadence estimator stopped being logged"
    assert min(rates) < max(rates) / 2
    assert min(rates) <= max(estimator)
