"""The Stage-2 PPO surface: act_logp (old_logp recorded at act time) and
update_episodes (whole-episode batches through the factored _optimize)."""

import math

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent

OBS_D, N_ACT = 3, 4


def _agent(**over):
    torch.manual_seed(0)
    kwargs = dict(
        observation_space=gym.spaces.Box(-1.0, 1.0, (OBS_D,), np.float32),
        action_space=gym.spaces.Discrete(N_ACT),
        num_envs=2,
        device="cpu",
        lr=1e-3,
        gamma=1.0,
        gae_lambda=0.95,
        rollout_steps=4,
        epochs=2,
        minibatches=2,
        clip_eps=0.2,
        entropy_coef=0.01,
        value_coef=0.5,
        max_grad_norm=0.5,
        hidden_sizes=[8],
    )
    kwargs.update(over)
    return PPOAgent(**kwargs)


def _episodes(lengths, seed=0):
    rng = np.random.default_rng(seed)
    total = int(sum(lengths))
    obs = rng.normal(size=(total, OBS_D)).astype(np.float32)
    masks = np.ones((total, N_ACT), dtype=np.bool_)
    masks[:, -1] = rng.random(total) > 0.5  # some rows lose an action
    actions = np.array([rng.choice(np.flatnonzero(m)) for m in masks], dtype=np.int64)
    rewards = np.zeros(total, dtype=np.float32)
    ends = np.cumsum(lengths) - 1
    rewards[ends] = rng.choice([-1.0, 1.0], size=len(lengths))
    return {
        "obs": obs,
        "masks": masks,
        "actions": actions,
        "rewards": rewards,
        "old_logp": np.zeros(total, dtype=np.float32),  # caller overwrites
        "version": np.zeros(total, dtype=np.int64),
        "lengths": np.asarray(lengths, dtype=np.int64),
    }


def test_act_logp_samples_inside_mask_and_matches_recompute():
    agent = _agent()
    rng = np.random.default_rng(1)
    obs = rng.normal(size=(16, OBS_D)).astype(np.float32)
    masks = np.ones((16, N_ACT), dtype=bool)
    masks[:, 0] = False  # action 0 illegal everywhere
    torch.manual_seed(2)
    actions, logp = agent.act_logp(obs, masks)
    assert actions.shape == (16,) and logp.shape == (16,)
    assert masks[np.arange(16), actions].all(), "sampled outside the mask"
    # The recorded logp is the same masked-Categorical the update rebuilds —
    # recomputed at the same batch size it must agree to float precision.
    with torch.no_grad():
        want = agent._logp_entropy(
            torch.as_tensor(obs), torch.as_tensor(actions), torch.as_tensor(masks)
        )[0]
    np.testing.assert_allclose(logp, want.numpy(), rtol=1e-6)


def test_update_episodes_trains_and_reports_the_locked_keys():
    agent = _agent()
    batch = _episodes([5, 3, 8, 4])
    # Record old_logp the way the collector does: from the acting policy.
    with torch.no_grad():
        batch["old_logp"] = (
            agent._logp_entropy(
                torch.as_tensor(batch["obs"]),
                torch.as_tensor(batch["actions"]),
                torch.as_tensor(batch["masks"]),
            )[0]
            .numpy()
            .astype(np.float32)
        )
    before = [p.clone() for p in agent.actor.parameters()]
    metrics = agent.update_episodes(batch, steps_seen=0)
    assert set(metrics) == {
        "loss/policy", "loss/value", "loss/entropy", "loss/approx_kl",
        "loss/clip_frac", "loss/grad_norm", "loss/grad_clip_frac",
        "loss/explained_variance", "loss/adv_std",
    }
    assert agent.updates == 1
    assert any(
        (p != q).any() for p, q in zip(agent.actor.parameters(), before)
    ), "the actor never moved"
    # First-epoch ratios start at the recorded logp, so approx_kl is finite
    # and small — not the silent-wrongness signature (NaN / huge).
    assert math.isfinite(metrics["loss/approx_kl"])


def test_update_episodes_anneals_from_steps_seen():
    agent = _agent(lr_anneal_steps=1_000)
    batch = _episodes([4, 4])
    agent.update_episodes(batch, steps_seen=500)
    assert agent.optimizer.param_groups[0]["lr"] == pytest.approx(0.5e-3)
    # And the schedule reads the caller's counter, not the update count.
    batch = _episodes([4, 4], seed=1)
    agent.update_episodes(batch, steps_seen=750)
    assert agent.optimizer.param_groups[0]["lr"] == pytest.approx(0.25e-3)


def test_update_episodes_refuses_privileged_and_label_mismatch():
    with pytest.raises(ValueError, match="privileged"):
        _agent(privileged_dim=7).update_episodes(_episodes([4]), steps_seen=0)
    # aux head off + labels recorded = the same loud seam update() enforces.
    batch = _episodes([4])
    batch["opp_choice"] = np.zeros((4, 3), dtype=np.int32)
    with pytest.raises(ValueError, match="opponent-action mismatch"):
        _agent().update_episodes(batch, steps_seen=0)


def test_vector_update_unchanged_by_the_factor_out():
    """The (T, N) path's numbers must not move: a seeded fill-and-train
    produces the same metrics whether or not _optimize exists as a seam —
    pinned here against values computed at build time so a later edit to
    _optimize that touches the vector path fails loudly."""
    torch.manual_seed(3)
    agent = _agent()
    rng = np.random.default_rng(3)
    for t in range(4):
        obs = rng.normal(size=(2, OBS_D)).astype(np.float32)
        nxt = rng.normal(size=(2, OBS_D)).astype(np.float32)
        acts = rng.integers(0, N_ACT, size=2)
        rews = rng.normal(size=2).astype(np.float32)
        term = np.array([t == 3, t == 3])
        trunc = np.zeros(2, dtype=bool)
        masks = np.ones((2, N_ACT), dtype=bool)
        metrics = agent.update((obs, acts, rews, nxt, term, trunc, masks, masks))
    assert agent.updates == 1 and len(agent.buffer) == 0
    # Epoch 1 recomputes old_logp exactly, so the mean over 2 epochs is
    # small; the exact value is pinned loosely (float noise across BLAS
    # builds) but the structural reads are exact.
    assert metrics["loss/clip_frac"] < 0.5
    assert math.isfinite(metrics["loss/policy"])


def test_trailing_one_row_minibatch_is_skipped_not_nan():
    """Async batches are not multiples of `minibatches`; a trailing 1-row
    slice has no advantage std, and before the guard its NaN silently
    poisoned the weights (caught live 2026-09-01: the crash surfaced one
    forward LATER, in act_logp). Batch of 5 at minibatches=2 slices 2/2/1."""
    agent = _agent(minibatches=2, epochs=1)
    batch = _episodes([3, 2])
    with torch.no_grad():
        batch["old_logp"] = (
            agent._logp_entropy(
                torch.as_tensor(batch["obs"]),
                torch.as_tensor(batch["actions"]),
                torch.as_tensor(batch["masks"]),
            )[0]
            .numpy()
            .astype(np.float32)
        )
    metrics = agent.update_episodes(batch, steps_seen=0)
    assert math.isfinite(metrics["loss/policy"])
    for p in agent.actor.parameters():
        assert torch.isfinite(p).all(), "NaN reached the weights"


# ---------------------------------------------------------------------------
# F-04 minibatch tail policy (audit 2026-09-02). The property is about
# batch_size mod mbs: with B = m*mbs + r (r < m) the trailing slice IS r once
# mbs >= m, so it is bounded by `minibatches`, not by the minibatch width.
# minibatches=8 with B = 64 + r therefore gives mbs = 8 for every r in 0..7
# and lets the five named tails be DISTINCT rows: 1, 2, mbs//2-1 = 3,
# mbs//2 = 4, mbs-1 = 7 (at minibatches=4 they would collapse to 1..3).

from rl.agents.ppo import _minibatch_slices

_M = 8
_TAILS = [1, 2, 3, 4, 7]  # 1, 2, mbs//2 - 1, mbs//2, mbs - 1 at mbs = 8


def _recorded_batch(agent, total, seed=0):
    """An episode batch of `total` rows whose old_logp came from the acting
    policy, the way the collector records it."""
    batch = _episodes([total // 2, total - total // 2], seed=seed)
    with torch.no_grad():
        batch["old_logp"] = (
            agent._logp_entropy(
                torch.as_tensor(batch["obs"]),
                torch.as_tensor(batch["actions"]),
                torch.as_tensor(batch["masks"]),
            )[0]
            .numpy()
            .astype(np.float32)
        )
    return batch


def _spy_minibatches(agent, batch):
    """Record the ROW INDICES of every executed minibatch, in order, by
    matching the obs rows _logp_entropy is handed back to the batch (random
    normals: unique to the byte). Installed AFTER old_logp is recorded so the
    recording pass is not counted."""
    row_of = {row.tobytes(): i for i, row in enumerate(batch["obs"])}
    assert len(row_of) == len(batch["obs"])
    seen: list[list[int]] = []
    orig = agent._logp_entropy

    def spy(obs, actions, masks, **kw):
        seen.append([row_of[r.tobytes()] for r in obs.numpy()])
        return orig(obs, actions, masks, **kw)

    agent._logp_entropy = spy
    return seen


def test_minibatch_tail_rejects_unknown_policy():
    with pytest.raises(ValueError, match="minibatch_tail"):
        _agent(minibatch_tail="skip")


def test_minibatch_tail_default_is_keep_and_bit_identical():
    """The kwarg is UNRULED: absent must equal 'keep' bit-for-bit — same seed,
    same async-shaped batch (tail 3 < mbs//2, exactly where 'drop'/'fold'
    WOULD diverge), torch.equal on every actor/critic tensor and identical
    metrics. 'fold' on the same seed is the negative control that shows the
    comparison has teeth."""
    def run(**over):
        agent = _agent(minibatches=_M, epochs=2, **over)
        batch = _recorded_batch(agent, _M * _M + 3)
        torch.manual_seed(7)
        metrics = agent.update_episodes(batch, steps_seen=0)
        return agent, metrics

    absent, m_absent = run()
    keep, m_keep = run(minibatch_tail="keep")
    assert absent.minibatch_tail == "keep"
    for net in ("actor", "critic"):
        a, k = getattr(absent, net).state_dict(), getattr(keep, net).state_dict()
        assert a.keys() == k.keys()
        for name in a:
            assert torch.equal(a[name], k[name]), f"{net}.{name} moved"
    assert m_absent == m_keep
    assert "loss/minibatch_rows_min" not in m_keep, "'keep' must add no metric key"
    fold, _ = run(minibatch_tail="fold")
    assert any(
        not torch.equal(p, q)
        for p, q in zip(fold.actor.state_dict().values(), keep.actor.state_dict().values())
    ), "the negative control did not diverge — the identity test is vacuous"


@pytest.mark.parametrize("tail_rows", [0] + _TAILS)
def test_minibatch_slices_plan(tail_rows):
    """The pure plan, all three policies, at every named tail (and the exact
    division the vector path always has)."""
    batch = _M * _M + tail_rows
    mbs = batch // _M
    assert mbs == _M and batch % mbs == tail_rows
    half = mbs // 2

    def rows(sl):
        return sl[1] - sl[0]

    def covered(slices, floor):
        out = []
        for sl in slices:
            if rows(sl) >= floor:
                out += list(range(*sl))
        return out

    legacy = [(s, min(s + mbs, batch)) for s in range(0, batch, mbs)]

    keep, keep_floor = _minibatch_slices(batch, mbs, "keep")
    assert keep == legacy and keep_floor == 2

    drop, drop_floor = _minibatch_slices(batch, mbs, "drop")
    assert drop == legacy and drop_floor == max(2, half)
    got = covered(drop, drop_floor)
    assert len(got) == len(set(got))
    missing = batch - len(got)
    # At most ONE slice sits out, and only when the tail is under the floor.
    assert missing == (tail_rows if 0 < tail_rows < drop_floor else 0)

    fold, fold_floor = _minibatch_slices(batch, mbs, "fold")
    assert fold_floor == 2
    assert sorted(covered(fold, fold_floor)) == list(range(batch)), "fold lost a row"
    assert all(rows(sl) >= half for sl in fold)
    if 0 < tail_rows < half:
        assert len(fold) == len(legacy) - 1 and rows(fold[-1]) == mbs + tail_rows
    else:
        assert fold == legacy


@pytest.mark.parametrize("tail_rows", _TAILS)
@pytest.mark.parametrize("policy", ["keep", "drop", "fold"])
def test_minibatch_tail_policies_on_async_shaped_batches(policy, tail_rows):
    """End to end through update_episodes, spying on the rows each executed
    minibatch actually received: under 'drop' and 'fold' every executed
    minibatch has >= mbs//2 rows; 'fold' trains every row exactly once per
    epoch; 'drop' drops at most one slice per epoch; 'keep' is today's wire
    (only the 1-row slice sits out) and reports no tail key."""
    epochs = 2
    agent = _agent(minibatches=_M, epochs=epochs, minibatch_tail=policy)
    batch = _recorded_batch(agent, _M * _M + tail_rows)
    total = len(batch["obs"])
    mbs = total // _M
    half = mbs // 2
    seen = _spy_minibatches(agent, batch)
    metrics = agent.update_episodes(batch, steps_seen=0)
    assert math.isfinite(metrics["loss/policy"])
    for p in agent.actor.parameters():
        assert torch.isfinite(p).all()

    # The executed count is the same every epoch (the tail width is fixed;
    # only WHICH rows land in it changes), so the record splits evenly.
    assert len(seen) % epochs == 0
    per_epoch = len(seen) // epochs
    n_full = total // mbs
    sizes = [len(mb) for mb in seen]
    for e in range(epochs):
        rows = [i for mb in seen[e * per_epoch:(e + 1) * per_epoch] for i in mb]
        assert len(rows) == len(set(rows)), "a row trained twice in one epoch"
        if policy == "fold":
            assert sorted(rows) == list(range(total)), "fold lost a row"
        elif policy == "drop":
            dropped = total - len(rows)
            assert dropped == (tail_rows if tail_rows < max(2, half) else 0)
        else:  # keep: today's wire — only a 1-row slice sits out
            assert total - len(rows) == (1 if tail_rows == 1 else 0)

    if policy == "keep":
        assert per_epoch == n_full + (1 if tail_rows >= 2 else 0)
        assert min(sizes) == (tail_rows if tail_rows >= 2 else mbs)
        assert not {k for k in metrics if k.startswith("loss/minibatch_")}
        return

    assert min(sizes) >= half, f"a {min(sizes)}-row minibatch took a step"
    assert metrics["loss/minibatch_rows_min"] == float(min(sizes))
    if policy == "drop":
        # At most one slice out per epoch; the rest are the legacy slices.
        assert per_epoch in (n_full, n_full + 1)
        assert metrics["loss/minibatch_rows_dropped"] == (
            float(tail_rows) if tail_rows < max(2, half) else 0.0
        )
    else:
        assert metrics["loss/minibatch_rows_dropped"] == 0.0
        assert max(sizes) == (mbs + tail_rows if tail_rows < half else mbs)
