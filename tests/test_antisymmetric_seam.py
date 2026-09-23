"""R7 B2 -- the antisymmetric critic's SEAM, end to end on the engine route:
EngineCollector(both_views) -> EpisodeDataset -> PPOAgent.update_episodes with
`antisymmetric_critic=True`, plain and with the privileged block.

What must hold (tests/test_engine_privileged_seam.py's shape, for the second
view):
  * `obs2` arrives (n, 828) float32, one row per learner row, and it IS the
    foe's own view: its own-side slice equals the `privileged` block the same
    rows carry (one vector, two consumers), and it differs from `obs`;
  * the critic's input is [obs | obs2 (| priv | priv2)] with priv2 = OUR own
    side (`privileged_block_rows`), and an update takes real steps with finite
    losses under both forms;
  * the seam is LOUD BOTH WAYS: a plain critic refuses a batch carrying obs2,
    an antisymmetric critic refuses a batch without it, and the rollout-buffer
    path refuses the flag outright;
  * the ordinary value counters are unchanged in name.

No server: `BatchEnv` is engine-only. Skips loudly without the built
extension or a team bank.
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

_SEAM = r"""
import sys
import numpy as np
import torch
from rl.agents.ppo import PPOAgent
from rl.buffers.episode import EpisodeDataset
from rl.envs.engine_collector import EngineCollector
from rl.envs.showdown import OBS_DIM, PRIV_DIM, privileged_block, privileged_block_rows
from rl.selfplay.pool import SnapshotPool

BANK = sys.argv[1]
TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=16, entity_dim=32,
    pool="max", ctx_sizes=[64], scorer_sizes=[64], value_sizes=[64],
)

def make_agent(seed=0, trunk_kwargs=None, **kw):
    from rl.envs.showdown import fake_spaces
    torch.manual_seed(seed)
    obs_space, act_space = fake_spaces()
    return PPOAgent(
        obs_space, act_space,
        num_envs=1, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
        rollout_steps=8, epochs=1, minibatches=2, clip_eps=0.2,
        entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
        hidden_sizes=[64, 64],
        trunk="entity_deepsets", trunk_kwargs=trunk_kwargs or TRUNK_KWARGS, **kw,
    )

anti = make_agent(antisymmetric_critic=True)
control = make_agent()
wide = make_agent(antisymmetric_critic=True, privileged_dim=PRIV_DIM)
# Construction: no new module anywhere, the actor untouched, the critic's
# state_dict the control's (a plain checkpoint loads into it).
assert anti.critic.param_count == control.critic.param_count
assert anti.actor.param_count == control.actor.param_count
assert list(anti.critic.state_dict()) == list(control.critic.state_dict())
anti.critic.load_state_dict(control.critic.state_dict(), strict=True)
assert anti.antisymmetric_critic and not control.antisymmetric_critic
assert anti.privileged_block_dim == 0 and wide.privileged_block_dim == PRIV_DIM
# The flag lives on the agent, never in trunk_kwargs.
try:
    make_agent(trunk_kwargs={**TRUNK_KWARGS, "antisymmetric": True})
    raise SystemExit("trunk_kwargs.antisymmetric was accepted")
except ValueError as e:
    assert "agent.antisymmetric_critic" in str(e)

def collect(privileged, both_views, steps=1200):
    pool = SnapshotPool(pool_size=4, latest_prob=0.8)
    pool.push(anti)
    c = EngineCollector(anti.act_logp, pool, seed=4242, k=16, team_bank=BANK,
                        privileged=privileged, both_views=both_views)
    c.seam.version = 0
    c.start(n_battles=10_000)
    ds = EpisodeDataset()
    polls = 0
    while ds.steps < steps and polls < 40_000:
        c.check()
        for ep in c.poll():
            if both_views:
                assert ep["obs2"].dtype == np.float32
                assert ep["obs2"].shape == (len(ep["actions"]), OBS_DIM), ep["obs2"].shape
            else:
                assert "obs2" not in ep
            ds.append(ep)
        polls += 1
    assert ds.steps >= steps, ds.steps
    c.close()
    return ds.drain()

batch = collect(privileged=True, both_views=True)
n = len(batch["obs"])
assert batch["obs2"].shape == (n, OBS_DIM) and batch["privileged"].shape == (n, PRIV_DIM)
# obs2 IS the foe's own view: its own-side slice is the privileged block, row for row.
assert np.array_equal(privileged_block_rows(batch["obs2"]), batch["privileged"]), "obs2's slice != privileged"
# ...and the batched slice rule is the per-row one.
assert np.array_equal(privileged_block_rows(batch["obs"][:300]),
                      np.stack([privileged_block(r) for r in batch["obs"][:300]]))
# ...and it is a different view from ours on essentially every row.
same = int((np.abs(batch["obs2"] - batch["obs"]).max(axis=1) == 0).sum())
assert same < n // 50, same
assert np.isfinite(batch["obs2"]).all() and float(batch["obs2"].std()) > 0

# The critic input the agent builds, checked against the contract directly.
flat_obs = torch.as_tensor(batch["obs"]); flat_priv = torch.as_tensor(batch["privileged"])
x = wide._critic_input(flat_obs, flat_priv, batch["obs"], batch["obs2"])
assert x.shape == (n, 2 * OBS_DIM + 2 * PRIV_DIM)
assert torch.equal(x[:, :OBS_DIM], flat_obs)
assert torch.equal(x[:, OBS_DIM:2 * OBS_DIM], torch.as_tensor(batch["obs2"]))
assert torch.equal(x[:, 2 * OBS_DIM:2 * OBS_DIM + PRIV_DIM], flat_priv)
assert torch.equal(x[:, 2 * OBS_DIM + PRIV_DIM:], torch.as_tensor(privileged_block_rows(batch["obs"])))
x_plain = anti._critic_input(flat_obs, None, batch["obs"], batch["obs2"])
assert x_plain.shape == (n, 2 * OBS_DIM)
# And the identity holds on REAL rows, bitwise, for both forms.
with torch.no_grad():
    v = wide.critic(x); v_swap = wide.critic(torch.cat([x[:, OBS_DIM:2 * OBS_DIM], x[:, :OBS_DIM],
                                                          x[:, 2 * OBS_DIM + PRIV_DIM:], x[:, 2 * OBS_DIM:2 * OBS_DIM + PRIV_DIM]], 1))
    assert torch.equal(v_swap, -v)
    v = anti.critic(x_plain); v_swap = anti.critic(torch.cat([x_plain[:, OBS_DIM:], x_plain[:, :OBS_DIM]], 1))
    assert torch.equal(v_swap, -v)

# Real updates take real steps with finite losses, both forms.
for agent_, label in ((wide, "wide"), (anti, "plain")):
    before = {k: v_.detach().clone() for k, v_ in agent_.critic.state_dict().items()}
    b = batch if label == "wide" else {k: v_ for k, v_ in batch.items() if k != "privileged"}
    for _ in range(2):
        metrics = agent_.update_episodes(b, steps_seen=0)
    assert any(not torch.equal(before[k], v_) for k, v_ in agent_.critic.state_dict().items()), f"{label}: critic took no step"
    for key in ("loss/value", "loss/explained_variance", "loss/policy"):
        assert key in metrics and np.isfinite(metrics[key]), (label, key, metrics.get(key))

# LOUD BOTH WAYS.
plain_batch = {k: v_ for k, v_ in batch.items() if k not in ("privileged",)}
try:
    control.update_episodes(plain_batch, steps_seen=0)
    raise SystemExit("a plain critic accepted a batch carrying obs2")
except ValueError as e:
    assert "second-view mismatch" in str(e), e
no_view = {k: v_ for k, v_ in batch.items() if k not in ("privileged", "obs2")}
try:
    anti.update_episodes(no_view, steps_seen=0)
    raise SystemExit("an antisymmetric critic accepted a batch without obs2")
except ValueError as e:
    assert "second-view mismatch" in str(e), e
# The rollout-buffer path refuses the flag before touching anything.
try:
    anti.update((np.zeros((8, 1, OBS_DIM), np.float32), np.zeros((8, 1), np.int64), np.zeros((8, 1), np.float32),
                 np.zeros((8, 1, OBS_DIM), np.float32), np.zeros((8, 1), bool), np.zeros((8, 1), bool),
                 np.ones((8, 1, 10), bool), np.ones((8, 1, 10), bool)))
    raise SystemExit("the rollout-buffer path accepted the antisymmetric critic")
except (ValueError, TypeError, AttributeError) as e:
    assert "antisymmetric_critic" in str(e) or "obs2" in str(e), e
# The emitter off: no key, and a plain agent updates as before.
plain_only = collect(privileged=False, both_views=False, steps=400)
assert "obs2" not in plain_only and "privileged" not in plain_only
m = control.update_episodes(plain_only, steps_seen=0)
assert np.isfinite(m["loss/value"])
print(f"OK antisymmetric seam: {n} rows, obs2 is the foe's own view, both forms update, seams loud")
"""


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_the_antisymmetric_seam_carries_the_second_view_into_a_real_update():
    r = subprocess.run(
        [sys.executable, "-c", _SEAM, BANKS[0]],
        capture_output=True, text=True, timeout=1200, cwd=ROOT,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("OK")
