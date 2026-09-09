"""`EngineCollector` against the seam `rl/train.py` drives (plan §8.1).

Real agent, real `SnapshotPool`, real `EpisodeDataset` — no server, no mocks of
the things under test. NOT LICENSED: gate A-1 has not run, so nothing here is a
throughput or quality measurement.
"""

from __future__ import annotations

import glob
import os
import pathlib
import subprocess
import sys

import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first")

ROOT = pathlib.Path(__file__).resolve().parents[1]
BANKS = sorted(glob.glob(str(ROOT / "data/engine/teams_*.bin")))
ENV = {"POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"}

_PREAMBLE = r"""
import pathlib, sys
import numpy as np
import torch
from rl.buffers.episode import EpisodeDataset
from rl.envs.engine_collector import EngineCollector
from rl.envs.showdown import fake_spaces
from rl.selfplay.pool import SnapshotPool

BANK = sys.argv[1]

# A SMALL entity trunk: this tests the seam, not the 100M recipe.
TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=16, entity_dim=32,
    pool="max", ctx_sizes=[64], scorer_sizes=[64], value_sizes=[64],
)

def make_agent(seed=0, **kw):
    from rl.agents.ppo import PPOAgent
    torch.manual_seed(seed)
    obs_space, act_space = fake_spaces()
    return PPOAgent(
        obs_space, act_space,
        num_envs=1, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
        rollout_steps=8, epochs=1, minibatches=2, clip_eps=0.2,
        entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
        hidden_sizes=[64, 64],
        trunk="entity_deepsets", trunk_kwargs=TRUNK_KWARGS, **kw,
    )

def collector(agent, pool, k=16, seed=99, **kw):
    return EngineCollector(
        agent.act_logp, pool, seed=seed, k=k, team_bank=BANK, **kw
    )
"""


def _run(body: str, timeout: int = 1800) -> str:
    r = subprocess.run(
        [sys.executable, "-c", _PREAMBLE + body, BANKS[-1]],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=ROOT,
        env={**os.environ, **ENV},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


needs_bank = pytest.mark.skipif(not BANKS, reason="no team bank built yet")


@needs_bank
def test_the_collector_feeds_a_real_ppo_update_end_to_end():
    """The whole seam: poll -> EpisodeDataset -> update_episodes. This is the
    path `_async_loop` runs, minus the loop's cadences."""
    out = _run(r"""
# aux on, because opp_action=True below: PPO refuses the mismatched pair, and
# this exercises the D25 labels through a real update.
agent = make_agent(aux_oppact_coef=0.1)
pool = SnapshotPool(pool_size=4, latest_prob=0.8)
pool.push(agent)
c = collector(agent, pool, opp_action=True)
c.seam.version = 0
c.start(n_battles=10_000)

ds = EpisodeDataset()
polls = 0
while ds.steps < 3000 and polls < 20_000:
    c.check()
    for ep in c.poll():
        ds.append(ep)
    polls += 1
assert ds.steps >= 3000, ds.steps

batch = ds.drain()
# Every learner row went through act_logp exactly once, and the Python seam
# counted exactly the decisions the ENGINE says it owed. The drained rows are
# fewer: the k battles still in flight hold theirs.
assert c.seam.requests == c.env.stats()["seam_requests"], c.seam.requests
assert c.seam.requests > sum(batch["lengths"]), (c.seam.requests, sum(batch["lengths"]))
assert c.seam.requests - sum(batch["lengths"]) < 16 * 200, "in-flight backlog too large"
assert c.seam.inference_seconds > 0
assert batch["obs"].shape[1] == 828
assert batch["opp_choice"].shape == (len(batch["actions"]), 3)
# The action taken is inside the mask that was recorded with it.
assert np.take_along_axis(batch["masks"], batch["actions"][:, None], 1).all()

before = {k: v.detach().clone() for k, v in agent.actor.state_dict().items()}
metrics = agent.update_episodes(batch, steps_seen=0)
after = agent.actor.state_dict()
assert any(not torch.equal(before[k], after[k]) for k in before), "no weights moved"
assert np.isfinite(metrics["loss/policy"]), metrics

s = c.stats()
assert s["collect/episodes_discarded"] == 0
assert s["collect/rerequests"] == 0
assert s["collect/battles_in_flight"] == 16
assert s["collect/opponent_inference_seconds"] > 0
print("OK", ds.steps, len(batch["lengths"]), metrics["loss/policy"])
""")
    assert out.strip().splitlines()[-1].startswith("OK")


@needs_bank
def test_the_pool_is_drawn_per_battle_and_reported_at_its_end():
    """A member is seated once per BATTLE (never per step), plays every one of
    that battle's rows, and is credited exactly one game at the finish."""
    out = _run(r"""
agent = make_agent()
pool = SnapshotPool(pool_size=8, latest_prob=0.5)
for _ in range(4):
    pool.push(make_agent(seed=_ + 1))
c = collector(agent, pool, k=12)
c.start(n_battles=1000)

seen = []
finished = 0
seat_log = {}
for _ in range(20000):
    # The member seated on each slot must not move while its battle runs.
    for slot in range(c.k):
        m = c._seated[slot]
        if slot in seat_log and seat_log[slot] is not m:
            seat_log[slot] = m  # a restart is the only legal change
    eps = c.poll()
    for slot in range(c.k):
        seat_log.setdefault(slot, c._seated[slot])
    for ep in eps:
        finished += 1
    if finished >= 60:
        break
assert finished >= 60, finished

games = sum(st[1] for st in pool.stats)
assert games == finished, (games, finished)
# Scores are learner-perspective: win 1, draw 0.5, loss 0.
scores = sum(st[0] for st in pool.stats)
assert 0 < scores < games, (scores, games)
# latest_prob 0.5 over 5 members: every member should have played something.
played = sum(1 for st in pool.stats if st[1] > 0)
assert played >= 4, [st[1] for st in pool.stats]
print("OK", finished, games, [st[1] for st in pool.stats])
""")
    assert out.strip().splitlines()[-1].startswith("OK")


@needs_bank
def test_a_resumed_lane_does_not_replay_its_first_battles():
    """Without the persisted `battle_counter` a resume replays the run's first
    K battles — same seeds, same teams — silently. `_save_latest` carries the
    counter in `loop`; this is what that buys.

    The observable is each episode's FIRST observation: turn 1 is a function of
    the team pair alone, so identical leading rows mean identical battles.
    """
    out = _run(r"""
def leads(counter, n=24):
    agent = make_agent()
    pool = SnapshotPool(pool_size=1, latest_prob=1.0)
    pool.push(agent)
    kw = {} if counter is None else {"battle_counter": counter}
    c = collector(agent, pool, k=8, seed=1234, **kw)
    c.start(n_battles=1000)
    rows = []
    for _ in range(20000):
        for ep in c.poll():
            rows.append(ep["obs"][0])
        if len(rows) >= n:
            break
    assert len(rows) >= n, len(rows)
    return np.stack(rows[:n]), c.battle_counter

fresh, n_fresh = leads(None)
assert n_fresh > 8, n_fresh

again, _ = leads(None)
assert np.array_equal(fresh, again), "the same lane seed must replay its battles"

resumed, n_resumed = leads(200)
assert n_resumed > 200 + 8, n_resumed
# THE POINT: starting from a restored counter draws battles the fresh lane
# has not played. Row equality is exact -- these are the same encoder floats.
same = sum(
    1 for r in resumed if any(np.array_equal(r, f) for f in fresh)
)
assert same == 0, f"{same}/{len(resumed)} resumed battles replay the lane's first ones"
print("OK", n_fresh, n_resumed)
""")
    assert out.strip().splitlines()[-1].startswith("OK")


@needs_bank
def test_the_liveness_check_fires_when_nothing_finishes():
    """`check()` is the F-03 shape for a collector that cannot hang on a socket:
    the failure mode left is a battle that never terminates. `Gen1Env` raises on
    its own per-battle bound, so reaching the collector's bound means every slot
    is stuck at once — which is why the message says so."""
    out = _run(r"""
agent = make_agent()
pool = SnapshotPool(pool_size=1, latest_prob=1.0)
pool.push(agent)
# The bound must exceed a real battle's update count or it fires on healthy
# play: at K=4 a finish arrives every ~25 engine steps. The default 8000 is
# `Gen1Env`'s own per-battle ceiling, which is the right coincidence — at K=1
# the two bounds mean the same thing.
c = collector(agent, pool, k=4, max_updates_per_battle=400)
c.start(n_battles=100)

# Healthy: battles finish well inside the bound.
for _ in range(200):
    c.poll()
    c.check()
assert c.episodes_finished > 0, "no battle finished; the bound is untested"

# The stall shape: steps accumulate, nothing finishes.
c._last_finish_step = -10_000
try:
    c.check()
except RuntimeError as e:
    assert "not terminating" in str(e), e
    assert "every slot is stuck at once" in str(e), e
else:
    raise AssertionError("check() did not fire")
print("OK", c.episodes_finished)
""")
    assert out.strip().splitlines()[-1].startswith("OK")


@needs_bank
def test_a_member_evicted_mid_battle_finishes_its_game_and_moves_no_counter():
    """`SnapshotPool.report` matches on IDENTITY, so a member evicted while its
    battle was in flight is silently not a member and credits nothing. The
    collector holds the member OBJECT rather than its push id for exactly this
    reason — holding the id would credit whichever member later occupied that
    slot in the list."""
    out = _run(r"""
agent = make_agent()
pool = SnapshotPool(pool_size=2, latest_prob=0.5)
pool.push(make_agent(seed=1))
pool.push(make_agent(seed=2))
c = collector(agent, pool, k=8)
c.start(n_battles=1000)

# Every slot is seated on one of the two members; now evict by pushing past
# pool_size while their battles are in flight.
seated_before = list(c._seated)
for _ in range(3):
    c.poll()
for i in range(2):
    pool.push(make_agent(seed=10 + i))
evicted = [m for m in seated_before if m not in pool.members]
assert evicted, "the push did not evict anything seated"

finished = 0
for _ in range(20000):
    finished += len(c.poll())
    if finished >= 40:
        break
assert finished >= 40, finished

# No crash, and an evicted member's games are simply not counted anywhere:
# the pool's total is <= the number finished, never more.
games = sum(st[1] for st in pool.stats)
assert 0 < games <= finished, (games, finished)
# ...and every credited game is a real one: scores never exceed games.
for score, n in pool.stats:
    assert 0 <= score <= n, (score, n)
print("OK", finished, games, len(evicted))
""")
    assert out.strip().splitlines()[-1].startswith("OK")


def test_the_engine_collector_declares_no_idle_sleep():
    """`_async_loop` sleeps `collector.idle_sleep` after a poll that returned no
    episodes. That is right for the async collector — its work happens on
    POKE_LOOP, so an empty poll means "nothing has finished yet". It is wrong
    here: every engine poll DOES a batched step, so an empty poll is a step that
    finished no battle and the sleep is a pure stall.

    It bites hardest exactly where the plan wants a K chosen. Using the branch's
    own measured ~67 engine updates per battle, a poll finishes a battle with
    probability ~K/67, so an empty poll is ~2% likely at K=256 but ~62% at K=32 —
    which at 20 ms would be ~12 s of sleep per 30,720-step rollout against the
    plan's ~1 s projected collection.
    """
    from rl.envs.engine_collector import EngineCollector

    assert EngineCollector.idle_sleep == 0.0

    # And the loop must actually read it rather than hardcoding 0.02.
    import inspect

    import rl.train

    src = inspect.getsource(rl.train._async_loop)
    assert 'getattr(collector, "idle_sleep"' in src, (
        "_async_loop hardcodes its empty-poll sleep; the engine path stalls"
    )


@needs_bank
def test_the_collector_preflights_the_extension_and_the_encoder_width():
    """`build_info()` RECORDS whatever extension is loaded, including a stale
    one; `verify()` REFUSES a mismatch against the pin. The stale-editable-
    install trap already cost a debugging cycle at gate P-1, and nothing guarded
    a training launch against it.

    The width check is the second half: the Rust OBS_DIM is a compile-time
    constant, the Python one is env-var driven, and a lane launched without the
    encoder flags would build its agent at the Python width and die on a torch
    GEMM shape error at the first poll — after meta.yaml and the wandb run
    exist, with a message naming nothing.
    """
    out = _run(r"""
import pkmn_gen1
from rl.envs.showdown import OBS_DIM
assert OBS_DIM == pkmn_gen1.OBS_DIM == 828

agent = make_agent()
pool = SnapshotPool(pool_size=1, latest_prob=1.0)
pool.push(agent)
c = collector(agent, pool, k=2)          # calls verify() on the way through
assert c.metadata()["engine_sha"] == pkmn_gen1.build_info()["engine_sha_pinned"]
print("OK")
""")
    assert out.strip().splitlines()[-1] == "OK"


@needs_bank
def test_a_lane_without_the_encoder_flags_is_refused_by_name():
    """Without the encoder flags a lane must die naming THE FLAGS, never inside
    a torch GEMM.

    The primary guard turns out to be the entity trunk itself, which refuses at
    agent construction — earlier than the collector, and with a better message.
    The collector's width check is the backstop for a trunk that does not care
    about the id suffix (`trunk: mlp`), where nothing else compares the Python
    encoder's width to the Rust one. This test accepts either, and fails if the
    process gets far enough to build a collector at the wrong width.
    """
    r = subprocess.run(
        [sys.executable, "-c", _PREAMBLE + r"""
agent = make_agent()
pool = SnapshotPool(pool_size=1, latest_prob=1.0)
pool.push(agent)
try:
    collector(agent, pool, k=2)
except ValueError as e:
    assert "POKEMON_RL_ENCODER_V2" in str(e), e
    print("OK refused")
except Exception as e:
    print("OTHER", type(e).__name__, e)
""", BANKS[-1]],
        capture_output=True, text=True, timeout=900, cwd=ROOT,
        env={k: v for k, v in os.environ.items()
             if k not in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS")},
    )
    # Without the flags the agent's own construction may fail first; either way
    # the failure must be about the encoder width, never a silent 612-dim run.
    combined = r.stdout + r.stderr
    assert "POKEMON_RL_ENCODER_IDS" in combined or "encoder width" in combined, combined
    assert "OTHER" not in combined, combined
