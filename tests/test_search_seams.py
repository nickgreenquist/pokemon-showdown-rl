"""R7 B5 -- the learner's searched-row seams, ENGINE-FREE (the MLP trunk on the
synthetic episode fixture of tests/test_ppo_episodes.py), so they run in any
env. Plan amendment box 3 item 3 / REPLY BOX 2 §3:

(a) THE IMPORTANCE-RATIO IDENTITY, asserted BITWISE at epoch 0 / minibatch 0
    with the minibatch permutation pinned to the identity: on every UNSEARCHED
    row the learner's ratio is exactly 1.0 (the recompute uses the weights
    that generated the data), and on every SEARCHED row it is exactly
    exp(log pi_theta(a) - log pi'(a)) -- the behaviour correction PPO's ratio
    carries when the collector records log pi'(a) as `old_logp` (plan §4 item
    1). The fixture asserts its own preconditions (rows with argmax pi' !=
    argmax pi_theta; search_mask.sum() > 0), and the identity goes RED under
    "play pi' with pi_theta's logp" -- old_logp = log pi_theta(a) on rows whose
    action came from pi' -- which is the corruption that would otherwise read
    as a healthy ratio of 1.0 on every row.
(c) the counters, each re-derived from the batch directly: value/pred_mean,
    value/realized_mean, value/bias and, with `opp_latest`, value/bias_mirror +
    value/mirror_frac; the search/* reads; loss/search_policy under beta, and
    beta moving the actor toward pi'.
Plus the loud seams (construction, update both ways, the rollout-buffer path,
harvest, the keys travelling together, an unknown dial) and the blend touching
only searched targets.

(b), the aux-head golden, needs the entity critic: tests/test_search_seams_engine.py.
The collector's side of the seam -- sampling from pi' and recording log pi'(a) --
is B4's and is tested there when it lands; here the batch is built the way that
collector will build it.
"""

from __future__ import annotations

import copy
import math

import gymnasium as gym
import numpy as np
import pytest
import torch

import rl.agents.ppo as ppo_mod
from rl.agents.ppo import PPOAgent
from rl.buffers.episode import EpisodeDataset, episode_gae

OBS_D, N_ACT = 12, 6


def _kwargs(**over):
    kwargs = dict(
        observation_space=gym.spaces.Box(-1.0, 1.0, (OBS_D,), np.float32),
        action_space=gym.spaces.Discrete(N_ACT),
        num_envs=2, device="cpu", lr=1e-3, gamma=1.0, gae_lambda=0.95,
        rollout_steps=4, epochs=1, minibatches=1, clip_eps=0.2,
        entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[16],
    )
    kwargs.update(over)
    return kwargs


def _agent(seed=0, **over):
    torch.manual_seed(seed)
    return PPOAgent(**_kwargs(**over))


def _episodes(lengths, seed=0):
    rng = np.random.default_rng(seed)
    total = int(sum(lengths))
    obs = rng.normal(size=(total, OBS_D)).astype(np.float32)
    masks = np.ones((total, N_ACT), dtype=np.bool_)
    masks[:, -1] = rng.random(total) > 0.5
    masks[:, 0] = rng.random(total) > 0.3
    actions = np.array([rng.choice(np.flatnonzero(m)) for m in masks], dtype=np.int64)
    rewards = np.zeros(total, dtype=np.float32)
    ends = np.cumsum(lengths) - 1
    rewards[ends] = rng.choice([-1.0, 1.0], size=len(lengths))
    return {
        "obs": obs, "masks": masks, "actions": actions, "rewards": rewards,
        "old_logp": np.zeros(total, dtype=np.float32),
        "version": np.zeros(total, dtype=np.int64),
        "lengths": np.asarray(lengths, dtype=np.int64),
    }


def _recorded(agent, batch):
    """old_logp from the acting policy, the whole batch in row order -- the
    collector's act-time record."""
    with torch.no_grad():
        return agent._logp_entropy(
            torch.as_tensor(batch["obs"]), torch.as_tensor(batch["actions"]),
            torch.as_tensor(batch["masks"]),
        )[0].numpy().astype(np.float32)


def _searched(agent, batch, frac=0.5, seed=1, logp_from="behaviour"):
    """Make `frac` of the rows SEARCHED, the way B4's T-op will: pi' is a
    sharpened, perturbed pi_theta (masked, normalised; zeros off-mask), the
    played action is RE-SAMPLED from pi', and old_logp is log pi'(a)
    ('behaviour') -- or log pi_theta(a), the corruption ('pi_theta'). v' is a
    random value in [-1, 1] on searched rows. Asserts the preconditions."""
    rng = np.random.default_rng(seed)
    n = len(batch["obs"])
    with torch.no_grad():
        logits = ppo_mod.masked_logits(
            agent.actor(torch.as_tensor(batch["obs"])), torch.as_tensor(batch["masks"])
        ).numpy().astype(np.float64)
    mask = rng.random(n) < frac
    z = np.where(batch["masks"], (logits + rng.normal(scale=3.0, size=logits.shape)) / 0.5, -np.inf)
    p = np.exp(z - z.max(1, keepdims=True))
    p /= p.sum(1, keepdims=True)
    pi = np.zeros((n, N_ACT), np.float32)
    pi[mask] = p[mask].astype(np.float32)
    actions = batch["actions"].copy()
    for i in np.flatnonzero(mask):
        actions[i] = rng.choice(N_ACT, p=p[i])
    out = dict(batch)
    out["actions"] = actions
    out["search_mask"] = mask
    out["search_pi"] = pi
    out["search_v"] = np.where(mask, rng.uniform(-1.0, 1.0, n), 0.0).astype(np.float32)
    old = _recorded(agent, out)  # log pi_theta(a) for the actions actually played
    if logp_from == "behaviour":
        old[mask] = np.log(pi[mask, actions[mask]].astype(np.float64)).astype(np.float32)
    else:
        assert logp_from == "pi_theta"
    out["old_logp"] = old
    # THE PRECONDITIONS (a test that passes on a batch with no searched rows,
    # or none where the operator disagrees, has tested nothing).
    assert mask.sum() > 0
    assert (pi[mask].argmax(1) != logits.argmax(1)[mask]).sum() > 0
    assert np.all(out["masks"][np.arange(n), actions])
    return out


def _ratio_at_epoch0(agent, batch):
    """The learner's OWN per-row ratio on epoch 0 / minibatch 0 (minibatches=1,
    epochs=1) with the permutation pinned to the identity, captured at the
    surrogate; the update then runs to completion."""
    captured = {}
    orig_loss, orig_perm = ppo_mod.clipped_surrogate_loss, torch.randperm

    def spy(new_logp, old_logp, adv, eps):
        if "ratio" not in captured:
            captured["ratio"] = (new_logp - old_logp).exp().detach().clone()
            captured["new_logp"] = new_logp.detach().clone()
        return orig_loss(new_logp, old_logp, adv, eps)

    ppo_mod.clipped_surrogate_loss = spy
    torch.randperm = lambda n, **kw: torch.arange(n, device=kw.get("device"))
    try:
        agent.update_episodes(batch, steps_seen=0)
    finally:
        ppo_mod.clipped_surrogate_loss, torch.randperm = orig_loss, orig_perm
    return captured["ratio"], captured["new_logp"]


def _identity_holds(ratio, new_logp, batch) -> bool:
    """ratio == 1.0 on unsearched rows, == exp(log pi_theta(a) - log pi'(a)) on
    searched rows -- both BITWISE, with log pi'(a) taken from the STORED pi'
    (never from old_logp, which is the thing under test)."""
    mask = torch.as_tensor(batch["search_mask"])
    a = torch.as_tensor(batch["actions"])
    logp_prime = torch.log(torch.as_tensor(batch["search_pi"], dtype=torch.float64)[torch.arange(len(a)), a]).to(torch.float32)
    expected_searched = (new_logp[mask] - logp_prime[mask]).exp()
    unsearched_ok = torch.equal(ratio[~mask], torch.ones_like(ratio[~mask]))
    searched_ok = torch.equal(ratio[mask], expected_searched)
    return unsearched_ok and searched_ok


def test_the_ratio_identity_holds_bitwise_and_goes_red_under_pi_thetas_logp():
    base = _agent(search_targets=True)
    batch = _searched(base, _episodes([7, 9, 6, 10]))
    ratio, new_logp = _ratio_at_epoch0(copy.deepcopy(base), batch)
    assert _identity_holds(ratio, new_logp, batch)
    # And it is not vacuous: searched rows carry a ratio that is NOT 1.
    m = batch["search_mask"]
    assert float((ratio[torch.as_tensor(m)] - 1.0).abs().max()) > 1e-3
    # THE RED RUN: the played action came from pi', old_logp says pi_theta.
    bad = _searched(base, _episodes([7, 9, 6, 10]), logp_from="pi_theta")
    assert np.array_equal(bad["actions"], batch["actions"]) and np.array_equal(bad["search_pi"], batch["search_pi"])
    ratio_bad, new_logp_bad = _ratio_at_epoch0(copy.deepcopy(base), bad)
    assert torch.equal(ratio_bad, torch.ones_like(ratio_bad)), "the corruption reads as a healthy ratio of 1.0"
    assert not _identity_holds(ratio_bad, new_logp_bad, bad)


def test_the_counters_reach_disk_and_match_a_direct_recompute():
    agent = _agent(search_targets=True, search_policy_coef=0.5)
    batch = _searched(agent, _episodes([7, 9, 6, 10]))
    batch["opp_latest"] = np.repeat([True, False, True, False], [7, 9, 6, 10])
    with torch.no_grad():
        values = agent.critic(torch.as_tensor(batch["obs"])).squeeze(-1).numpy()
    realized = episode_gae(batch["rewards"], values, batch["lengths"], 1.0, 1.0) + values
    # gamma 1 with a terminal-only reward: the realized value IS the outcome.
    outcome = np.repeat(batch["rewards"][np.cumsum(batch["lengths"]) - 1], batch["lengths"])
    assert np.allclose(realized, outcome)
    adv = episode_gae(batch["rewards"], values, batch["lengths"], 1.0, 0.95)
    m = agent.update_episodes(batch, steps_seen=0)
    for key in ("value/pred_mean", "value/realized_mean", "value/bias", "value/bias_mirror",
                "value/mirror_frac", "search/rows_frac", "search/rows", "search/kl_update",
                "search/override_update", "search/value_gap", "search/value_gap_critic",
                "search/v_mean", "loss/search_policy"):
        assert key in m and math.isfinite(m[key]), key
    assert "loss/search_value" not in m and "search_value/grad_norm" not in m  # no head
    assert m["value/pred_mean"] == pytest.approx(float(values.mean()), abs=1e-6)
    assert m["value/realized_mean"] == pytest.approx(float(realized.mean()), abs=1e-6)
    assert m["value/bias"] == pytest.approx(float((values - realized).mean()), abs=1e-6)
    mirror = batch["opp_latest"]
    assert m["value/mirror_frac"] == pytest.approx(mirror.mean())
    assert m["value/bias_mirror"] == pytest.approx(float((values[mirror] - realized[mirror]).mean()), abs=1e-6)
    s = batch["search_mask"]
    assert m["search/rows_frac"] == pytest.approx(s.mean()) and m["search/rows"] == s.sum()
    assert m["search/value_gap"] == pytest.approx(float(np.abs(batch["search_v"] - (adv + values))[s].mean()), abs=1e-5)
    assert m["search/value_gap_critic"] == pytest.approx(float(np.abs(batch["search_v"] - values)[s].mean()), abs=1e-5)
    assert m["search/v_mean"] == pytest.approx(float(batch["search_v"][s].mean()), abs=1e-6)
    assert m["search/override_update"] > 0 and m["search/kl_update"] > 0 and m["loss/search_policy"] > 0
    # beta moves the actor toward pi': the update-time KL falls.
    kl0 = m["search/kl_update"]
    for _ in range(12):
        m = agent.update_episodes(batch, steps_seen=0)
    assert m["search/kl_update"] < kl0
    # Without the tag, no mirror keys and nothing else changes.
    plain = {k: v for k, v in batch.items() if k != "opp_latest"}
    m2 = _agent(search_targets=True, search_policy_coef=0.5).update_episodes(plain, steps_seen=0)
    assert "value/bias_mirror" not in m2 and "value/mirror_frac" not in m2 and "value/bias" in m2


def test_the_blend_moves_only_searched_targets_and_zero_leaves_them_untouched():
    def captured_arrays(agent, batch):
        cap = {}
        orig = agent._optimize

        def w(*args, **kw):
            cap["adv"], cap["tgt"] = args[4].numpy().copy(), args[5].numpy().copy()
            return orig(*args, **kw)

        agent._optimize = w
        agent.update_episodes(batch, steps_seen=0)
        return cap["adv"], cap["tgt"]

    ctrl = _agent(search_targets=True)
    batch = _searched(ctrl, _episodes([6, 8, 5]))
    adv_c, tgt_c = captured_arrays(ctrl, batch)
    adv_0, tgt_0 = captured_arrays(_agent(search_targets=True, search_value_blend=0.0), batch)
    assert np.array_equal(adv_c, adv_0) and np.array_equal(tgt_c, tgt_0)
    assert np.array_equal(tgt_c.view(np.uint32), tgt_0.view(np.uint32))
    adv_b, tgt_b = captured_arrays(_agent(search_targets=True, search_value_blend=0.25), batch)
    s = batch["search_mask"]
    assert np.array_equal(adv_b, adv_c), "the blend must not touch advantages"
    assert np.array_equal(tgt_b[~s], tgt_c[~s])
    assert not np.array_equal(tgt_b[s], tgt_c[s])
    assert np.allclose(tgt_b[s], 0.75 * tgt_c[s] + 0.25 * batch["search_v"][s], atol=1e-6)


def test_the_seams_are_loud():
    with pytest.raises(ValueError, match="search_targets=True"):
        _agent(search_policy_coef=0.1)
    with pytest.raises(ValueError, match="search_targets=True"):
        _agent(search_value_blend=0.5)
    with pytest.raises(ValueError, match="search_value_head=False"):
        _agent(search_targets=True, search_value_coef=0.1)
    with pytest.raises(TypeError, match="entity_deepsets"):
        _agent(search_targets=True, search_value_head=True)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        _agent(search_targets=True, search_value_blend=1.5)
    with pytest.raises(ValueError, match=">= 0"):
        _agent(search_targets=True, search_policy_coef=-1.0)
    # An unknown dial is a TypeError at construction -- make_agent passes config
    # keys through **hparams, so the dial list IS the signature (the typed-list
    # landmine).
    with pytest.raises(TypeError):
        _agent(search_tau=1.0)
    plain, expects = _agent(), _agent(search_targets=True)
    base = _episodes([5, 6])
    base["old_logp"] = _recorded(plain, base)
    searched = _searched(expects, _episodes([5, 6]))
    with pytest.raises(ValueError, match="search-target mismatch"):
        plain.update_episodes(searched, steps_seen=0)
    with pytest.raises(ValueError, match="search-target mismatch"):
        expects.update_episodes(base, steps_seen=0)
    # A shape mismatch is named.
    wrong = dict(searched)
    wrong["search_pi"] = searched["search_pi"][:, :-1]
    with pytest.raises(ValueError, match="searched-row shapes"):
        expects.update_episodes(wrong, steps_seen=0)
    # The three keys travel together, per episode.
    ds = EpisodeDataset()
    ep = {k: v[:5] for k, v in searched.items() if k != "lengths"}
    ds.append(dict(ep))
    del ep["search_v"]
    with pytest.raises(AssertionError, match="travel together"):
        ds.append(ep)
    # The rollout-buffer path refuses the flag; so does the harvest.
    T, N = 4, 2
    with pytest.raises(ValueError, match="rollout-buffer path"):
        expects.update((
            np.zeros((T, N, OBS_D), np.float32), np.zeros((T, N), np.int64), np.zeros((T, N), np.float32),
            np.zeros((T, N, OBS_D), np.float32), np.zeros((T, N), bool), np.zeros((T, N), bool),
            np.ones((T, N, N_ACT), bool), np.ones((T, N, N_ACT), bool),
        ))
    with pytest.raises(ValueError, match="searched rows"):
        expects.attach_harvest(object())
    # The counters and coefficients are off by default: no key, no group.
    m = plain.update_episodes(base, steps_seen=0)
    assert not any(k.startswith("search") for k in m)
    assert len(plain.optimizer.param_groups) == 2 and plain.search_value_head is None
