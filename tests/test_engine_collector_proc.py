"""R7 B4a -- the two-core lane's collector (`rl/envs/engine_collector_proc.py`).

What must hold:
  * EQUIVALENCE: at a fixed version, the child-process collector produces the
    SAME episodes as the in-process `EngineCollector` from the same lane seed,
    pool state and weights -- bitwise on every key (obs, masks, actions,
    rewards, old_logp, version, opp_latest) and in the same order. The seeds
    are the lane's alone (REPLY BOX 2 §4).
  * WEIGHTS TRAVEL WITH THE VERSION: after `ship_weights(agent, 1)` later rows
    are stamped 1, a row's version never decreases within an episode, and the
    child's decisions change (it really plays the new weights).
  * BACKPRESSURE: with `max_steps_ahead` small and nothing drained, the child
    idles at the bound (rows unconsumed stay near it, idle fraction high) and
    resumes on a drain -- the plan's "bound of one update".
  * The pool RPCs (push / pool_state / pool_stats), battle_counter, metadata,
    `pause_on_update`, the refusals (background QoS without the flag,
    `run_in_loop`), and a clean close.

No server. Skips loudly without the built extension or a team bank. The test
itself runs niced beside a fleet, so the child is built with
`allow_background_qos=True` and the refusal is asserted separately.
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
BANKS = sorted(glob.glob(str(ROOT / "data/engine/teams_*.bin")),
               key=lambda p: pathlib.Path(p).stat().st_size)

_CHILD = r"""
import sys, time
from dataclasses import asdict
from types import SimpleNamespace
import numpy as np
import torch
from rl.common.config import Config
from rl.common.seeding import set_seed
from rl.envs.engine_collector import EngineCollector
from rl.envs.engine_collector_proc import ProcCollector, qos_is_background
from rl.envs.showdown import fake_spaces
from rl.selfplay.pool import SnapshotPool
from rl.train import make_agent

BANK = sys.argv[1]
AGENT = dict(algo="ppo", lr=2.5e-4, gamma=1.0, gae_lambda=0.95, rollout_steps=8, epochs=1, minibatches=2,
             clip_eps=0.2, entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[64, 64],
             trunk="entity_deepsets",
             trunk_kwargs=dict(species_vocab=152, move_vocab=166, embed_dim=16, entity_dim=32, pool="max",
                               ctx_sizes=[64], scorer_sizes=[64], value_sizes=[64]))
cfg = Config(env_id="ShowdownGen1-v0", seed=5, total_steps=1000, eval_every=1000, eval_episodes=1,
             run_name="proc_test", num_envs=1, agent=AGENT,
             selfplay={"opponent": "self", "pool_size": 4, "latest_prob": 0.8},
             collector={"mode": "engine", "k": 16, "team_bank": BANK, "process": True})
obs_space, act_space = fake_spaces()
spaces = SimpleNamespace(observation_space=obs_space, action_space=act_space)
torch.manual_seed(0)
agent = make_agent(cfg, spaces)
pool = SnapshotPool(4, 0.8)
pool.push(agent)
N_EPS = 30

def fresh_pool():
    p = SnapshotPool(4, 0.8)
    p.load_state_dict(pool.state_dict(), agent_factory=lambda: make_agent(cfg, spaces))
    return p

def run_inproc(n):
    c = EngineCollector(agent.act_logp, fresh_pool(), seed=cfg.seed, k=16, team_bank=BANK)
    c.seam.version = 0
    set_seed(cfg.seed)          # the child seeds its streams at the same point
    c.start(10_000)
    eps = []
    while len(eps) < n:
        c.check(); eps += c.poll()
    c.close()
    return eps[:n]

def drain(pc, n, timeout=600):
    eps, t0 = [], time.time()
    while len(eps) < n and time.time() - t0 < timeout:
        pc.check()
        got = pc.poll()
        eps += got
        if not got:
            time.sleep(pc.idle_sleep)
    assert len(eps) >= n, f"only {len(eps)} episodes in {timeout}s"
    return eps

# ---- the refusals first (cheap) --------------------------------------------
if qos_is_background():
    try:
        ProcCollector(asdict(cfg), agent, pool, seed=cfg.seed, k=16, team_bank=BANK, max_steps_ahead=100)
        raise SystemExit("a background QoS was accepted without the flag")
    except RuntimeError as e:
        assert "BACKGROUND QoS" in str(e), e
    print("refusal: background QoS refused without the flag")
else:
    print("refusal: (not background here; the QoS refusal is untested in this run)")

# ---- equivalence -------------------------------------------------------------
ref = run_inproc(N_EPS)
pc = ProcCollector(asdict(cfg), agent, pool, seed=cfg.seed, k=16, team_bank=BANK, max_steps_ahead=100_000,
                   allow_background_qos=True)
assert pc.tables_fingerprint and pc.build_info and pc.child_pid > 0
try:
    pc.run_in_loop(lambda: 1)
    raise SystemExit("run_in_loop was accepted")
except TypeError:
    pass
pc.start(10_000)
got = drain(pc, N_EPS)[:N_EPS]
for i, (a, b) in enumerate(zip(ref, got)):
    assert set(a) == set(b), (i, set(a) ^ set(b))
    for key in a:
        assert a[key].dtype == b[key].dtype and a[key].shape == b[key].shape, (i, key)
        assert np.array_equal(a[key], b[key]), f"episode {i} key {key} differs"
    assert (a["version"] == 0).all()
rows_ref = sum(len(e["actions"]) for e in ref)
print(f"equivalence: {N_EPS} episodes / {rows_ref} rows bitwise identical to the in-process collector")

# ---- weights travel with the version -------------------------------------------
with torch.no_grad():
    for p in agent.actor.parameters():
        p.add_(torch.randn_like(p) * 0.5)
pc.ship_weights(agent, 1)
pc.resume(version=1)                      # same version: allowed, a no-op
try:
    pc.resume(version=2)
    raise SystemExit("resume() bumped the version without weights")
except RuntimeError as e:
    assert "ship_weights" in str(e), e
later = drain(pc, 40)
versions = np.concatenate([e["version"] for e in later])
assert set(np.unique(versions).tolist()) <= {0, 1}, np.unique(versions)
assert any((e["version"] == 1).all() for e in later), "no episode fully under the new weights"
for e in later:
    assert (np.diff(e["version"]) >= 0).all(), "a row's version decreased within an episode"
# The new weights are really played: the child's decisions on the SAME states
# would differ -- checked on the rows the parent's new actor would score
# differently (a different argmax on most rows is the signature of noise 0.5).
from rl.common.masking import masked_logits
e1 = next(e for e in later if (e["version"] == 1).all())
with torch.no_grad():
    new_greedy = masked_logits(agent.actor(torch.as_tensor(e1["obs"])), torch.as_tensor(e1["masks"])).argmax(-1).numpy()
    new_logp = torch.log_softmax(masked_logits(agent.actor(torch.as_tensor(e1["obs"])), torch.as_tensor(e1["masks"])), -1)
    new_logp = new_logp[torch.arange(len(e1["actions"])), torch.as_tensor(e1["actions"])].numpy()
assert np.allclose(new_logp, e1["old_logp"], atol=1e-4), "old_logp on version-1 rows is not the shipped actor's log-prob"
st = pc.stats()
assert st["collect/child_version"] == 1.0 and st["collect/child_polls"] > 0
print(f"weights: {len(later)} later episodes, versions {sorted(set(versions.tolist()))}, old_logp matches the shipped actor")

# ---- pool RPCs, counters, metadata ---------------------------------------------
assert pc.push(agent) == 2
s0, s_last, n_pool = pc.pool_stats()
assert n_pool == 2 and len(s0) == 2 and len(s_last) == 2
state = pc.pool_state()
assert len(state["members"]) == 2 and state["pool_size"] == 4
assert isinstance(pc.battle_counter, int) and pc.battle_counter >= N_EPS
md = pc.metadata()
assert isinstance(md, dict) and md
pc.close()
assert not pc._proc.is_alive()
print("rpcs: push -> 2 members, pool_state/pool_stats/battle_counter/metadata answer, close joins the child")

# ---- backpressure ---------------------------------------------------------------
pc2 = ProcCollector(asdict(cfg), agent, pool, seed=cfg.seed + 1, k=16, team_bank=BANK, max_steps_ahead=100,
                    allow_background_qos=True)
pc2.start(10_000)
time.sleep(6.0)                           # no poll: the child must stall at the bound
st = pc2.stats()
unconsumed = st["collect/child_steps_unconsumed"]
assert 100 <= unconsumed <= 100 + 16 * 400, unconsumed   # the bound plus at most one step's finishes
assert st["collect/child_idle_frac"] > 0.5, st
# The drain releases it. mp.Queue hands items over through a feeder thread, so
# one non-blocking poll may see a prefix of what the child enqueued; the rest
# arrives on later polls (the loop polls continuously).
got = pc2.poll()
assert got, "nothing drained after the stall"
time.sleep(2.0)
st2 = pc2.stats()
assert st2["collect/child_polls"] > 0, st2   # it stepped again after the drain
pc2.close()
print(f"backpressure: {unconsumed:.0f} rows held at bound 100 (idle frac {st['collect/child_idle_frac']:.2f}), released on drain")

# ---- pause_on_update ------------------------------------------------------------
pc3 = ProcCollector(asdict(cfg), agent, pool, seed=cfg.seed + 2, k=16, team_bank=BANK, max_steps_ahead=100_000,
                    allow_background_qos=True, pause_on_update=True)
pc3.start(10_000)
drain(pc3, 5)
pc3.pause(); time.sleep(0.5); pc3.stats()
time.sleep(2.0)
st = pc3.stats()
assert st["collect/child_polls"] == 0, st    # paused: no engine step
pc3.ship_weights(agent, 0)                   # same version: resumes only
time.sleep(1.0)
assert pc3.stats()["collect/child_polls"] > 0
pc3.close()
print("OK proc collector: equivalence, weights/version, rpcs, backpressure, pause_on_update")
"""


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_the_process_collector_matches_the_in_process_one_and_bounds_its_lead():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD, BANKS[0]],
        capture_output=True, text=True, timeout=1500, cwd=ROOT,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("OK")
