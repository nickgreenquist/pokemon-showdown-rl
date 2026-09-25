"""R7 B4b -- the T-op inside the engine collector (`rl/search/top.py`), on the
fleet's critic form (antisymmetric + privileged), in process and in the child
process.

What must hold:
  * every episode carries `search_mask` / `search_pi` / `search_v` aligned to
    its rows; pi' is a masked distribution on searched rows and zero elsewhere;
    the dose lands (searched fraction in a band under frac 0.5), forced rows
    and confident rows (top-1 >= top1_skip) are never searched;
  * PLAY: on searched rows the played action is a legal support point of pi'
    and `old_logp` is EXACTLY float32(log pi'(a)); on unsearched rows it is the
    policy's own log-prob;
  * THE RATIO IDENTITY ON REAL ROWS (B5 (a), collector side): at version 0 the
    learner's epoch-0 ratio is exactly exp(log pi_theta(a) - log pi'(a)) on
    searched rows (bitwise, with log pi'(a) from the STORED pi') and ~1 on the
    rest; under RECORD-ONLY (`play: false`) it is ~1 everywhere while searched
    rows still exist with argmax pi' != argmax pi_theta -- both settings of
    the play-vs-record dial;
  * the counters reach the collector's stats (`search/*`), the dial list is
    the signature (an unknown key fails), and the child-process collector
    carries the same keys and counters.

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
import copy, sys, time
from dataclasses import asdict
from types import SimpleNamespace
import numpy as np
import torch
import rl.agents.ppo as ppo_mod
from rl.buffers.episode import EpisodeDataset
from rl.common.config import Config
from rl.common.masking import masked_logits
from rl.envs.engine_collector import EngineCollector
from rl.envs.engine_collector_proc import ProcCollector
from rl.envs.showdown import OBS_DIM, PRIV_DIM, N_ACTIONS, fake_spaces
from rl.search.top import TOp
from rl.selfplay.pool import SnapshotPool
from rl.train import make_agent

BANK = sys.argv[1]
TRUNK_KWARGS = dict(species_vocab=152, move_vocab=166, embed_dim=16, entity_dim=32, pool="max",
                    ctx_sizes=[64], scorer_sizes=[64], value_sizes=[64])
AGENT = dict(algo="ppo", lr=2.5e-4, gamma=1.0, gae_lambda=0.95, rollout_steps=8, epochs=1, minibatches=1,
             clip_eps=0.2, entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[64, 64],
             trunk="entity_deepsets", trunk_kwargs=TRUNK_KWARGS, antisymmetric_critic=True,
             privileged_dim=PRIV_DIM, search_targets=True, search_policy_coef=0.1)
DIALS = dict(frac=0.5, top1_skip=0.97, cols_k=3, chance_s=2, tau=0.5)
cfg = Config(env_id="ShowdownGen1-v0", seed=11, total_steps=1000, eval_every=10**9, eval_episodes=1,
             run_name="top_test", num_envs=1, agent=AGENT,
             selfplay={"opponent": "self", "pool_size": 4, "latest_prob": 0.8},
             collector={"mode": "engine", "k": 16, "team_bank": BANK, "process": True, "search": DIALS})
obs_space, act_space = fake_spaces()
spaces = SimpleNamespace(observation_space=obs_space, action_space=act_space)
torch.manual_seed(0)
agent = make_agent(cfg, spaces)
pool = SnapshotPool(4, 0.8); pool.push(agent)

# The dial list is the signature.
assert set(TOp.dials()) == {"frac", "top1_skip", "cols_k", "chance_s", "tau", "play"}, TOp.dials()
TOp.check_dials({**DIALS, "play": True})
try:
    TOp.check_dials({"cols": 2, "play": True})
    raise SystemExit("an unknown dial was accepted")
except ValueError as e:
    assert "unknown collector.search key" in str(e), e
# `play` has no default: a spec that drops it is refused, never defaulted to playing.
try:
    TOp.check_dials(DIALS)
    raise SystemExit("a spec without `play` was accepted")
except ValueError as e:
    assert "missing required key(s) ['play']" in str(e), e

def collect(play, steps=1500, seed=4242):
    c = EngineCollector(agent.act_logp, pool, seed=seed, k=16, team_bank=BANK, privileged=True, both_views=True)
    c.searcher = TOp(agent, c.tables, seat="p1", seed=1, play=play, **DIALS)
    c.seam.version = 0
    c.start(10_000)
    ds = EpisodeDataset(); polls = 0
    while ds.steps < steps and polls < 40_000:
        c.check()
        for ep in c.poll():
            n = len(ep["actions"])
            assert ep["search_mask"].shape == (n,) and ep["search_pi"].shape == (n, N_ACTIONS) and ep["search_v"].shape == (n,)
            assert ep["search_mask"].dtype == np.bool_ and ep["search_pi"].dtype == np.float32 and ep["search_v"].dtype == np.float32
            ds.append(ep)
        polls += 1
    st = c.stats()
    c.close()
    return ds.drain(), st

batch, st = collect(play=True)
n = len(batch["obs"]); s = batch["search_mask"]; pi = batch["search_pi"]; a = batch["actions"]; m = batch["masks"]
assert s.sum() > 20, s.sum()
# pi' is a masked distribution on searched rows, zero elsewhere; v' finite.
assert np.allclose(pi[s].sum(1), 1.0, atol=1e-5) and (pi[s][~m[s]] == 0).all()
assert (pi[~s] == 0).all() and (batch["search_v"][~s] == 0).all() and np.isfinite(batch["search_v"]).all()
# Never a forced row, never a confident row.
with torch.no_grad():
    probs = torch.softmax(masked_logits(agent.actor(torch.as_tensor(batch["obs"])), torch.as_tensor(m)), -1).numpy()
assert (m[s].sum(1) > 1).all(), "a forced row was searched"
assert (probs[s].max(1) < DIALS["top1_skip"]).all(), "a confident row was searched"
eligible = (m.sum(1) > 1) & (probs.max(1) < DIALS["top1_skip"])
frac_of_eligible = s.sum() / eligible.sum()
assert 0.3 < frac_of_eligible < 0.7, frac_of_eligible
# PLAY: a legal support point of pi', old_logp EXACTLY float32(log pi'(a)).
assert m[np.flatnonzero(s), a[s]].all() and (pi[np.flatnonzero(s), a[s]] > 0).all()
assert np.array_equal(batch["old_logp"][s], np.log(pi[np.flatnonzero(s), a[s]].astype(np.float64)).astype(np.float32))
# Unsearched rows: the policy's own log-prob.
with torch.no_grad():
    lp = agent._logp_entropy(torch.as_tensor(batch["obs"]), torch.as_tensor(a), torch.as_tensor(m))[0].numpy()
assert np.allclose(lp[~s], batch["old_logp"][~s], atol=1e-5)
# Counters.
for key in ("search/searched_frac", "search/eligible_frac", "search/decisions", "search/kl_prior",
            "search/override", "search/margin", "search/ms", "search/leaves", "search/seconds"):
    assert key in st and np.isfinite(st[key]), (key, st.get(key))
assert st["search/kl_prior"] > 0 and st["search/leaves"] > 0
# The behaviour counter: under play every searched decision played pi'.
assert st["search/played_frac"] == st["search/searched_frac"] > 0, (st["search/played_frac"], st["search/searched_frac"])
print(f"in-process play: {n} rows, {int(s.sum())} searched ({frac_of_eligible:.2f} of eligible), override {st['search/override']:.3f}, "
      f"kl_prior {st['search/kl_prior']:.4f}, {st['search/ms']:.1f} ms/decision")

# ---- the ratio identity on REAL rows, both settings of the dial --------------
def epoch0_ratio(learner, b):
    captured = {}
    orig_loss, orig_perm = ppo_mod.clipped_surrogate_loss, torch.randperm
    def spy(new_logp, old_logp, adv, eps):
        if "ratio" not in captured:
            captured["ratio"] = (new_logp - old_logp).exp().detach().clone(); captured["new"] = new_logp.detach().clone()
        return orig_loss(new_logp, old_logp, adv, eps)
    ppo_mod.clipped_surrogate_loss = spy
    torch.randperm = lambda n_, **kw: torch.arange(n_, device=kw.get("device"))
    try:
        learner.update_episodes(b, steps_seen=0)
    finally:
        ppo_mod.clipped_surrogate_loss, torch.randperm = orig_loss, orig_perm
    return captured["ratio"], captured["new"]

ratio, new_logp = epoch0_ratio(copy.deepcopy(agent), batch)
sm = torch.as_tensor(s); at = torch.as_tensor(a)
logp_prime = torch.log(torch.as_tensor(pi, dtype=torch.float64)[torch.arange(n), at]).to(torch.float32)
assert torch.equal(ratio[sm], (new_logp[sm] - logp_prime[sm]).exp()), "searched rows: ratio != pi_theta(a)/pi'(a)"
assert float((ratio[sm] - 1).abs().max()) > 1e-3
assert torch.allclose(ratio[~sm], torch.ones_like(ratio[~sm]), atol=1e-4), "unsearched rows: ratio != 1"
# RECORD ONLY: the same rows searched, the policy's action played, ratio ~1 everywhere.
rec, st_rec = collect(play=False)
s2 = rec["search_mask"]; pi2 = rec["search_pi"]
assert s2.sum() > 20
with torch.no_grad():
    probs2 = torch.softmax(masked_logits(agent.actor(torch.as_tensor(rec["obs"])), torch.as_tensor(rec["masks"])), -1).numpy()
assert (pi2[s2].argmax(1) != probs2[s2].argmax(1)).sum() > 0, "record-only: no row where the operator disagrees"
ratio2, _ = epoch0_ratio(copy.deepcopy(agent), rec)
assert torch.allclose(ratio2, torch.ones_like(ratio2), atol=1e-4), "record-only: ratio != 1"
# Record-only: searched, never played -- the control's behaviour counter reads 0.
assert st_rec["search/searched_frac"] > 0 and st_rec["search/played_frac"] == 0.0, st_rec
print(f"ratio identity: play -> pi_theta/pi' on {int(s.sum())} searched rows (bitwise), ~1 elsewhere; record-only -> ~1 on all {len(rec['obs'])} rows")

# ---- the child-process collector carries the same keys and counters -----------
pc = ProcCollector(asdict(cfg), agent, pool, seed=4243, k=16, team_bank=BANK, privileged=True, both_views=True,
                   max_steps_ahead=100_000, allow_background_qos=True, search={**DIALS, "play": True})
pc.start(10_000)
eps, t0 = [], time.time()
while sum(len(e["actions"]) for e in eps) < 600 and time.time() - t0 < 600:
    pc.check(); got = pc.poll(); eps += got
    if not got:
        time.sleep(pc.idle_sleep)
assert eps
for e in eps:
    n_ = len(e["actions"])
    assert e["search_mask"].shape == (n_,) and e["search_pi"].shape == (n_, N_ACTIONS) and e["search_v"].shape == (n_,)
    ss = e["search_mask"]
    if ss.any():
        assert np.array_equal(e["old_logp"][ss], np.log(e["search_pi"][np.flatnonzero(ss), e["actions"][ss]].astype(np.float64)).astype(np.float32))
stp = pc.stats()
assert stp["search/decisions"] > 0 and stp["search/searched_frac"] > 0 and "search/kl_prior" in stp
pc.close()
print(f"OK T-op collector: {sum(len(e['actions']) for e in eps)} child rows, searched frac {stp['search/searched_frac']:.2f}")
"""


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_the_t_op_searches_records_and_plays_pi_prime_and_the_learner_reads_it():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD, BANKS[0]],
        capture_output=True, text=True, timeout=1500, cwd=ROOT,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("OK")
