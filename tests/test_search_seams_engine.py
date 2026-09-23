"""R7 B5 -- the learner's searched-row seams on the FLEET'S OWN CRITIC FORM
(antisymmetric + privileged EntityDeepSetsNet) over a real engine batch, the
pattern of tests/test_antisymmetric_seam.py. Plan amendment box 3 item 3 /
REPLY BOX 2 §3:

(b) THE AUX-HEAD GOLDEN. Three agents at one seed on one real batch:
    (i) head absent, (ii) `search_value_head` at coef 0, (iii) at coef > 0.
    The ADVANTAGES and RETURNS arrays the optimizer receives are bitwise
    identical across all three (asserted on the arrays, never a downstream
    metric); (i) vs (ii) leave bitwise-identical actor AND critic after the
    update; the actor is bitwise identical across all three after it (the
    head's gradient never reaches the actor); only (iii)'s critic and head
    move; `loss/grad_norm` is identical across the three (the post-clip
    placement); ACTOR_PARAM_CEILING is pinned and the actor's count unchanged.
(a) the ratio identity, re-run on this critic form (tests/test_search_seams.py
    has the engine-free version and the RED run).
(c) `opp_latest` is emitted by the engine collector as one tag per episode
    and is MIXED under a two-member pool; `value/bias_mirror` re-derived from
    the batch; and the free antisymmetry bonus, V(swap(s)) == -V(s) bitwise.
Plus the checkpoint rider (a head-on checkpoint refuses a head-off agent; the
reverse warm-starts with the head at init) and the blend/priv_eval refusal.

No server. Skips loudly without the built extension or a team bank.
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
import copy, sys
import numpy as np
import torch
import rl.agents.ppo as ppo_mod
from rl.agents.ppo import PPOAgent
from rl.buffers.episode import EpisodeDataset, episode_gae
from rl.envs.engine_collector import EngineCollector
from rl.envs.showdown import OBS_DIM, PRIV_DIM, N_ACTIONS, fake_spaces
from rl.networks.entity_deepsets import ACTOR_PARAM_CEILING
from rl.selfplay.pool import SnapshotPool

BANK = sys.argv[1]
assert ACTOR_PARAM_CEILING == 681_994, ACTOR_PARAM_CEILING  # K2's pin, unchanged by B5
TRUNK_KWARGS = dict(species_vocab=152, move_vocab=166, embed_dim=16, entity_dim=32,
                    pool="max", ctx_sizes=[64], scorer_sizes=[64], value_sizes=[64])

def make_agent(seed=0, minibatches=2, **kw):
    torch.manual_seed(seed)
    obs_space, act_space = fake_spaces()
    return PPOAgent(obs_space, act_space, num_envs=1, device="cpu", lr=2.5e-4, gamma=1.0,
                    gae_lambda=0.95, rollout_steps=8, epochs=1, minibatches=minibatches,
                    clip_eps=0.2, entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
                    hidden_sizes=[64, 64], trunk="entity_deepsets", trunk_kwargs=TRUNK_KWARGS,
                    antisymmetric_critic=True, privileged_dim=PRIV_DIM, search_targets=True, **kw)

# ---- one real batch, the fleet's critic form, a two-member pool -------------
seed_agent = make_agent()
pool = SnapshotPool(pool_size=4, latest_prob=0.7)
pool.push(seed_agent); pool.push(seed_agent)
c = EngineCollector(seed_agent.act_logp, pool, seed=4242, k=16, team_bank=BANK,
                    privileged=True, both_views=True)
c.seam.version = 0
c.start(n_battles=10_000)
ds = EpisodeDataset(); polls = 0; n_eps = 0; n_latest = 0
while ds.steps < 1500 and polls < 40_000:
    c.check()
    for ep in c.poll():
        tag = ep["opp_latest"]
        assert tag.dtype == np.bool_ and tag.shape == (len(ep["actions"]),)
        assert tag.all() or not tag.any(), "one tag per episode"
        n_eps += 1; n_latest += int(tag[0])
        ds.append(ep)
    polls += 1
c.close()
raw = ds.drain(); n = len(raw["obs"])
assert n_eps >= 20 and 0 < n_latest < n_eps, (n_eps, n_latest)  # mixed under latest_prob 0.7

# ---- searched rows, the way B4's T-op will build them -----------------------
def searched(agent, batch, frac=0.4, seed=1, logp_from="behaviour"):
    rng = np.random.default_rng(seed)
    n = len(batch["obs"])
    with torch.no_grad():
        logits = ppo_mod.masked_logits(agent.actor(torch.as_tensor(batch["obs"])),
                                       torch.as_tensor(batch["masks"])).numpy().astype(np.float64)
    mask = rng.random(n) < frac
    z = np.where(batch["masks"], (logits + rng.normal(scale=3.0, size=logits.shape)) / 0.5, -np.inf)
    p = np.exp(z - z.max(1, keepdims=True)); p /= p.sum(1, keepdims=True)
    pi = np.zeros((n, N_ACTIONS), np.float32); pi[mask] = p[mask].astype(np.float32)
    actions = batch["actions"].copy()
    for i in np.flatnonzero(mask):
        actions[i] = rng.choice(N_ACTIONS, p=p[i])
    out = dict(batch); out["actions"] = actions
    out["search_mask"] = mask; out["search_pi"] = pi
    out["search_v"] = np.where(mask, rng.uniform(-1.0, 1.0, n), 0.0).astype(np.float32)
    with torch.no_grad():
        old = agent._logp_entropy(torch.as_tensor(out["obs"]), torch.as_tensor(actions),
                                  torch.as_tensor(out["masks"]))[0].numpy().astype(np.float32)
    if logp_from == "behaviour":
        old[mask] = np.log(pi[mask, actions[mask]].astype(np.float64)).astype(np.float32)
    out["old_logp"] = old
    assert mask.sum() > 0 and (pi[mask].argmax(1) != logits.argmax(1)[mask]).sum() > 0
    assert np.all(out["masks"][np.arange(n), actions])
    return out

batch = searched(seed_agent, raw)

# ---- (b) the aux-head golden ------------------------------------------------
# ONE gradient step (minibatches=1, epochs=1): the head's gradient reaches the
# critic trunk and the head only, so the actor after the step is bitwise the
# head-absent actor's. (Two minibatches: see the coupling block below.)
agents = {"absent": make_agent(minibatches=1), "coef0": make_agent(minibatches=1, search_value_head=True),
          "coef": make_agent(minibatches=1, search_value_head=True, search_value_coef=0.5)}
def nets(a):
    return {f"actor.{k}": v.clone() for k, v in a.actor.state_dict().items()} | \
           {f"critic.{k}": v.clone() for k, v in a.critic.state_dict().items()}
init = {k: nets(a) for k, a in agents.items()}
for k in ("coef0", "coef"):
    assert all(torch.equal(init["absent"][name], init[k][name]) for name in init["absent"]), k
assert agents["absent"].search_value_head is None
assert agents["coef0"].search_value_head is not None and agents["coef"].search_value_head is not None
assert torch.equal(agents["coef0"].search_value_head.weight, agents["coef"].search_value_head.weight)
assert len(agents["absent"].optimizer.param_groups) + 1 == len(agents["coef0"].optimizer.param_groups)
assert all(a.actor.param_count == agents["absent"].actor.param_count <= ACTOR_PARAM_CEILING for a in agents.values())
head0 = agents["coef0"].search_value_head.weight.clone(); head1 = agents["coef"].search_value_head.weight.clone()

arrays, metrics = {}, {}
for k, a in agents.items():
    orig = a._optimize
    def w(*args, _orig=orig, _k=k, **kw):
        arrays[_k] = (args[4].numpy().copy(), args[5].numpy().copy())
        return _orig(*args, **kw)
    a._optimize = w
    torch.manual_seed(11)
    metrics[k] = a.update_episodes(batch, steps_seen=0)
for k in ("coef0", "coef"):
    for i in range(2):
        assert np.array_equal(arrays["absent"][i].view(np.uint32), arrays[k][i].view(np.uint32)), (k, i)
after = {k: nets(a) for k, a in agents.items()}
actor_keys = [name for name in after["absent"] if name.startswith("actor.")]
critic_keys = [name for name in after["absent"] if name.startswith("critic.")]
assert any(not torch.equal(init["absent"][name], after["absent"][name]) for name in actor_keys), "no step"
for k in ("coef0", "coef"):
    assert all(torch.equal(after["absent"][name], after[k][name]) for name in actor_keys), f"{k}: the actor moved differently"
assert all(torch.equal(after["absent"][name], after["coef0"][name]) for name in critic_keys), "coef 0 moved the critic"
assert any(not torch.equal(after["absent"][name], after["coef"][name]) for name in critic_keys), "the aux gradient never reached the critic trunk"
assert torch.equal(agents["coef0"].search_value_head.weight, head0), "coef 0 moved the head"
assert not torch.equal(agents["coef"].search_value_head.weight, head1), "coef > 0 left the head still"
assert "loss/search_value" not in metrics["absent"]
assert metrics["coef0"]["loss/search_value"] > 0 and "search_value/grad_norm" not in metrics["coef0"]
assert metrics["coef"]["loss/search_value"] > 0 and metrics["coef"]["search_value/grad_norm"] > 0
assert metrics["absent"]["loss/grad_norm"] == metrics["coef0"]["loss/grad_norm"] == metrics["coef"]["loss/grad_norm"]
assert metrics["absent"]["loss/policy"] == metrics["coef0"]["loss/policy"] == metrics["coef"]["loss/policy"]
for key in ("search/kl_update", "search/override_update", "search/value_gap", "value/bias_mirror", "value/mirror_frac"):
    assert metrics["absent"][key] == metrics["coef0"][key] == metrics["coef"][key], key

# At TWO minibatches the pre-update arrays are still bitwise identical, but the
# actor is NOT from the second step on: `clip_grad_norm_` is ONE norm over the
# actor+critic union and (iii)'s critic moved after step 1, so step 2's clip
# factor differs -- the coupling every critic-side lever in rl/agents/ppo.py
# shares (the outcome head's placement comment). Pinned here so nobody reads
# it as the head's gradient leaking into the policy.
two = {"absent": make_agent(minibatches=2),
       "coef": make_agent(minibatches=2, search_value_head=True, search_value_coef=0.5)}
arrays2 = {}
for k, a in two.items():
    orig = a._optimize
    def w2(*args, _orig=orig, _k=k, **kw):
        arrays2[_k] = (args[4].numpy().copy(), args[5].numpy().copy())
        return _orig(*args, **kw)
    a._optimize = w2
    torch.manual_seed(11)
    a.update_episodes(batch, steps_seen=0)
for i in range(2):
    assert np.array_equal(arrays2["absent"][i].view(np.uint32), arrays2["coef"][i].view(np.uint32)), i
after2 = {k: nets(a) for k, a in two.items()}
assert any(not torch.equal(after2["absent"][name], after2["coef"][name]) for name in actor_keys), \
    "two minibatches: the shared clip's coupling vanished -- re-read the placement comment"

# ---- the checkpoint rider ---------------------------------------------------
state = agents["coef"].state_dict()
assert "search_value_head" in state and "search_value_head" not in agents["absent"].state_dict()
try:
    make_agent().load_state_dict(state)
    raise SystemExit("a head-on checkpoint loaded into a head-off agent")
except ValueError as e:
    assert "search-value head" in str(e), e
warm = make_agent(search_value_head=True)
warm.load_state_dict(agents["absent"].state_dict())  # a warm start; the head stays at init
assert torch.equal(warm.search_value_head.weight, head0)
reload = make_agent(search_value_head=True, search_value_coef=0.5)
reload.load_state_dict(state)
assert torch.equal(reload.search_value_head.weight, agents["coef"].search_value_head.weight)

# ---- (a) the ratio identity on this critic form ----------------------------
ident = make_agent(minibatches=1)
b1 = searched(ident, raw, seed=2)
captured = {}
orig_loss, orig_perm = ppo_mod.clipped_surrogate_loss, torch.randperm
def spy(new_logp, old_logp, adv, eps):
    if "ratio" not in captured:
        captured["ratio"] = (new_logp - old_logp).exp().detach().clone(); captured["new"] = new_logp.detach().clone()
    return orig_loss(new_logp, old_logp, adv, eps)
ppo_mod.clipped_surrogate_loss = spy
torch.randperm = lambda n, **kw: torch.arange(n, device=kw.get("device"))
try:
    copy.deepcopy(ident).update_episodes(b1, steps_seen=0)
finally:
    ppo_mod.clipped_surrogate_loss, torch.randperm = orig_loss, orig_perm
ratio, new_logp = captured["ratio"], captured["new"]
m = torch.as_tensor(b1["search_mask"]); a = torch.as_tensor(b1["actions"])
logp_prime = torch.log(torch.as_tensor(b1["search_pi"], dtype=torch.float64)[torch.arange(len(a)), a]).to(torch.float32)
assert torch.equal(ratio[~m], torch.ones_like(ratio[~m])), "unsearched rows: ratio != 1 at epoch 0"
assert torch.equal(ratio[m], (new_logp[m] - logp_prime[m]).exp()), "searched rows: ratio != pi_theta(a)/pi'(a)"
assert float((ratio[m] - 1).abs().max()) > 1e-3

# ---- (c) bias_mirror from the real tag; the antisymmetry bonus -------------
agent = make_agent()
with torch.no_grad():
    x = agent._critic_input(torch.as_tensor(batch["obs"]), torch.as_tensor(batch["privileged"]), batch["obs"], batch["obs2"])
    values = agent.critic(x).squeeze(-1)
    swap = torch.cat([x[:, OBS_DIM:2 * OBS_DIM], x[:, :OBS_DIM], x[:, 2 * OBS_DIM + PRIV_DIM:], x[:, 2 * OBS_DIM:2 * OBS_DIM + PRIV_DIM]], 1)
    assert torch.equal(agent.critic(swap).squeeze(-1), -values), "V(swap(s)) != -V(s)"
realized = episode_gae(batch["rewards"], values.numpy(), batch["lengths"], 1.0, 1.0) + values.numpy()
mirror = batch["opp_latest"]
mm = agent.update_episodes(batch, steps_seen=0)
assert abs(mm["value/bias"] - float((values.numpy() - realized).mean())) < 1e-6
assert abs(mm["value/bias_mirror"] - float((values.numpy()[mirror] - realized[mirror]).mean())) < 1e-6
assert abs(mm["value/mirror_frac"] - float(mirror.mean())) < 1e-6  # a float32 mean vs numpy's float64

# ---- the blend / design-B refusal -------------------------------------------
try:
    make_agent(search_value_blend=0.5, priv_eval_coef=0.1, priv_eval_dim=PRIV_DIM)
    raise SystemExit("blend + priv_eval was accepted")
except ValueError as e:
    assert "identity" in str(e), e
print(f"OK search seams (engine): {n} rows, {n_eps} episodes ({n_latest} vs latest), "
      f"{int(batch['search_mask'].sum())} searched; golden arrays bitwise across absent/coef0/coef")
"""


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_the_search_seams_hold_on_the_fleets_critic_form_over_a_real_batch():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD, BANKS[0]],
        capture_output=True, text=True, timeout=1500, cwd=ROOT,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("OK")
