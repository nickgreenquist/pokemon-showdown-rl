"""D18's privileged block on the ENGINE route: the value-parity gate the port
did not have, and the seam end to end.

`tests/test_seat_tag.py::test_the_two_encoders_agree_on_the_privileged_block_
width` pins the WIDTH (408 both sides, one of them at compile time). Nothing
pinned the VALUES. That is the drift `docs/engine_port/NOTES.md:1484-1489` names
as "actually coming" — JOURNEY step 8's encoder rewrite is the next step after
7.5 — and a shifted slice would reach the critic with no error anywhere.

The gate here is exact, not statistical, and it needs no reference
implementation of anything: at a step where BOTH seats owe a decision,
`pending("opponent")` hands back the foe's full 828 vector encoded from
`state(foe, t)`, which is the very vector `step()` slices the privileged block
out of (engine/pkmn_gen1/src/env.rs:295-302, before `battle.update()`). So the
Python `privileged_block` applied to that vector must equal the Rust block
BITWISE, row for row.

The second test is the seam itself: EngineCollector -> EpisodeDataset ->
PPOAgent.update_episodes with design B's evaluator head (`priv_eval_dim=408`,
`priv_eval_coef=0.5`) and D25's aux head on together — and, on the same drained
batch, an A+B agent whose critic IS widened. Both consumers of the block are
exercised; the combination with the aux head is the one the old constructor
guard refused outright.

No server: `BatchEnv` is engine-only. Skips loudly without the built extension
or a team bank.
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
# The SMALLEST bank. These tests want A bank, not the biggest one — the A-1
# bank is 480 MB and every subprocess here would read all of it.
BANKS = sorted(glob.glob(str(ROOT / "data/engine/teams_*.bin")),
               key=lambda p: pathlib.Path(p).stat().st_size)
ENV = {"POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"}

needs_bank = pytest.mark.skipif(not BANKS, reason="no team bank built yet")


def _run(body: str, timeout: int = 1800) -> str:
    r = subprocess.run(
        [sys.executable, "-c", body, BANKS[0]],
        capture_output=True, text=True, timeout=timeout, cwd=ROOT,
        env={**os.environ, **ENV},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


_PARITY = r"""
import pathlib, sys
sys.path.insert(0, "scripts")
import numpy as np
import pkmn_gen1
import engine_team_bank as bank
from rl.envs.engine_tables import build_tables
from rl.envs.showdown import OBS_DIM, PRIV_DIM, privileged_block

assert OBS_DIM == pkmn_gen1.OBS_DIM == 828
assert PRIV_DIM == pkmn_gen1.PRIV_DIM == 408

tables, _fp = build_tables()
_header, payload = bank.read_bank(pathlib.Path(sys.argv[1]))
K = 16
env = pkmn_gen1.BatchEnv(K, 4321, tables, payload, "p1", 0, privileged=True)
rng = np.random.default_rng(11)

# Per slot, one entry per LEARNER ROW recorded so far in the battle currently on
# that slot: the foe's own 828 vector at that step, or None when the foe owed
# only a Pass (mid-turn faint) and `pending` therefore returned nothing.
foe_at_row = {slot: [] for slot in range(K)}

compared = rows = episodes = 0
for _ in range(40000):
    l_idx, l_obs, l_mask, _lm = env.pending("learner")
    o_idx, o_obs, o_mask, _om = env.pending("opponent")
    l_obs = np.asarray(l_obs).reshape(len(l_idx), OBS_DIM)
    o_obs = np.asarray(o_obs).reshape(len(o_idx), OBS_DIM)
    l_mask = np.asarray(l_mask).reshape(len(l_idx), -1)
    o_mask = np.asarray(o_mask).reshape(len(o_idx), -1)
    foe_now = {int(s): o_obs[i] for i, s in enumerate(o_idx)}
    for i, s in enumerate(l_idx):
        foe_at_row[int(s)].append(foe_now.get(int(s)))
    la = np.array([rng.choice(np.flatnonzero(m)) for m in l_mask], dtype=np.int64)
    oa = np.array([rng.choice(np.flatnonzero(m)) for m in o_mask], dtype=np.int64)
    env.step([int(i) for i in l_idx], la.tolist(), [0.0] * len(l_idx), 0,
             [int(i) for i in o_idx], oa.tolist())

    for raw in env.drain_finished():
        slot = int(raw["slot"])
        n = int(raw["length"])
        priv = np.asarray(raw["privileged"], dtype=np.float32)
        seen = foe_at_row[slot]
        foe_at_row[slot] = []
        # ONE BLOCK PER LEARNER ROW, IN LEARNER-ROW ORDER. If this ever slips
        # the comparison below would silently compare the wrong rows.
        assert priv.shape == (n, PRIV_DIM), (priv.shape, n)
        assert len(seen) == n, (len(seen), n, slot)
        obs = np.asarray(raw["obs"], dtype=np.float32)
        assert obs.shape == (n, OBS_DIM), obs.shape
        episodes += 1
        rows += n
        for i, fobs in enumerate(seen):
            if fobs is None:
                continue          # the foe owed a Pass; no vector to compare
            want = privileged_block(np.asarray(fobs, dtype=np.float32))
            assert want.shape == (PRIV_DIM,), want.shape
            # BITWISE. Same floats, same slice, two implementations.
            assert np.array_equal(priv[i], want), (
                slot, i, int(np.argmax(priv[i] != want)),
                priv[i][priv[i] != want][:4], want[priv[i] != want][:4],
            )
            compared += 1
    if episodes >= 30:
        break

assert episodes >= 30, episodes
assert compared > 500, compared
# The block is a real view, not zeros, and it is NOT the learner's own slice.
print("OK", episodes, rows, compared)
"""


_SEAM = r"""
import pathlib, sys
import numpy as np
import torch
from rl.agents.ppo import PPOAgent
from rl.buffers.episode import EpisodeDataset
from rl.envs.engine_collector import EngineCollector
from rl.envs.showdown import OBS_DIM, PRIV_DIM, privileged_block
from rl.selfplay.pool import SnapshotPool

BANK = sys.argv[1]
TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=16, entity_dim=32,
    pool="max", ctx_sizes=[64], scorer_sizes=[64], value_sizes=[64],
)

def make_agent(seed=0, **kw):
    from rl.envs.showdown import fake_spaces
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

# DESIGN B, the shape configs/engine_a1_priveval_smoke.yaml runs: the block is
# emitted and ONLY the evaluator head reads it. Plus D25's aux head, which is
# the combination the old constructor guard refused outright.
agent = make_agent(aux_oppact_coef=0.1, priv_eval_dim=PRIV_DIM, priv_eval_coef=0.5)
control = make_agent(aux_oppact_coef=0.1)
# S-3: the ORDINARY critic is untouched — same width, same params as the
# control's — while the HEAD is the wide one. A wide critic here would mean
# design A leaked in and the block reached the advantage channel.
assert agent.critic.ctx_net[0].weight.shape[1] == 5 * 32
assert agent.critic.param_count == control.critic.param_count
assert agent.priv_eval_head is not None
assert agent.priv_eval_head.ctx_net[0].weight.shape[1] == 8 * 32
assert agent.actor.param_count == control.actor.param_count
assert agent.privileged_block_dim == PRIV_DIM and agent.privileged_dim == 0
# The other consumer, for the same seam: D18's wide critic (design A + B).
wide = make_agent(aux_oppact_coef=0.1, privileged_dim=PRIV_DIM, priv_eval_coef=0.5)
assert wide.critic.ctx_net[0].weight.shape[1] == 8 * 32
assert wide.privileged_block_dim == PRIV_DIM

pool = SnapshotPool(pool_size=4, latest_prob=0.8)
pool.push(agent)
c = EngineCollector(agent.act_logp, pool, seed=99, k=16, team_bank=BANK,
                    opp_action=True, privileged=True)
c.seam.version = 0
c.start(n_battles=10_000)

ds = EpisodeDataset()
polls = 0
while ds.steps < 1500 and polls < 40_000:
    c.check()
    for ep in c.poll():
        assert ep["privileged"].dtype == np.float32
        assert ep["privileged"].shape == (len(ep["actions"]), PRIV_DIM)
        ds.append(ep)
    polls += 1
assert ds.steps >= 1500, ds.steps

batch = ds.drain()
n = len(batch["obs"])
# S-2: shape and alignment.
assert batch["privileged"].shape == (n, PRIV_DIM), batch["privileged"].shape
assert batch["obs"].shape == (n, OBS_DIM)
assert len(batch["actions"]) == len(batch["old_logp"]) == n
assert int(batch["lengths"].sum()) == n
# S-1: NOT ZEROS, and not a constant column block either -- the exact failure
# both lifted refusals named ("the wide critic would train on zeros").
priv = batch["privileged"]
assert np.abs(priv).sum() > 0
assert float(priv.std()) > 0
nonconst = int((priv.std(axis=0) > 0).sum())
assert nonconst > PRIV_DIM // 4, nonconst
# ...and it is the FOE's own side, not ours: our own slice of our own obs is a
# different quantity on essentially every row.
mine = np.stack([privileged_block(row) for row in batch["obs"][:256]])
same = int((np.abs(mine - priv[:256]).max(axis=1) == 0).sum())
assert same < 8, same

before_actor = {k: v.detach().clone() for k, v in agent.actor.state_dict().items()}
before_head = {k: v.detach().clone() for k, v in agent.priv_eval_head.state_dict().items()}
for _ in range(3):
    metrics = agent.update_episodes(batch, steps_seen=0)
assert any(not torch.equal(before_actor[k], v)
           for k, v in agent.actor.state_dict().items()), "no actor weights moved"
assert any(not torch.equal(before_head[k], v)
           for k, v in agent.priv_eval_head.state_dict().items()), "the head took no step"
# The new keys are there, the old ones did not change name, and D25's are intact.
for key in ("loss/priv_eval_value", "priv_eval/explained_variance",
            "loss/value", "loss/explained_variance", "loss/policy",
            "aux/loss", "aux/labelled_frac"):
    assert key in metrics, (key, sorted(metrics))
    assert np.isfinite(metrics[key]), (key, metrics[key])

# The OTHER consumer on the same rows: D18's wide critic reads the block through
# `flat_critic_obs`, which is the half of the seam design B does not exercise.
wide_metrics = wide.update_episodes(batch, steps_seen=0)
assert np.isfinite(wide_metrics["loss/value"]), wide_metrics
assert np.isfinite(wide_metrics["loss/priv_eval_value"]), wide_metrics

# The seam is LOUD BOTH WAYS on this route, the sync path's rule.
try:
    control.update_episodes(batch, steps_seen=0)
    raise SystemExit("a narrow agent accepted a privileged batch")
except ValueError as e:
    assert "privileged mismatch" in str(e), e
blind = {k: v for k, v in batch.items() if k != "privileged"}
try:
    agent.update_episodes(blind, steps_seen=0)
    raise SystemExit("a wide agent accepted a batch with no block")
except ValueError as e:
    assert "privileged mismatch" in str(e), e

# A collector built WITHOUT the flag emits no key at all (the all-or-none rule
# in EpisodeDataset would catch a mixed dataset).
solo = make_agent()
assert solo.privileged_block_dim == 0
c2 = EngineCollector(solo.act_logp, pool, seed=7, k=4, team_bank=BANK)
for _ in range(4000):
    eps = c2.poll()
    if eps:
        assert "privileged" not in eps[0], sorted(eps[0])
        break
else:
    raise SystemExit("no episode finished on the unprivileged collector")

print("OK", n, nonconst, metrics["loss/priv_eval_value"],
      metrics["priv_eval/explained_variance"])
"""


@needs_bank
def test_the_engine_privileged_block_is_the_python_block():
    out = _run(_PARITY)
    print(out.strip().splitlines()[-1])
    assert out.strip().splitlines()[-1].startswith("OK")


@needs_bank
def test_the_privileged_seam_carries_real_rows_into_a_real_update():
    out = _run(_SEAM)
    print(out.strip().splitlines()[-1])
    assert out.strip().splitlines()[-1].startswith("OK")
