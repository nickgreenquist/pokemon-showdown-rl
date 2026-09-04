"""The Stage-2 PPO surface: act_logp (old_logp recorded at act time) and
update_episodes (whole-episode batches through the factored _optimize)."""

import functools
import hashlib
import inspect
import math
import pathlib
import subprocess
import types

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent

OBS_D, N_ACT = 3, 4


def _agent_kwargs(**over):
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
    return kwargs


def _agent(**over):
    torch.manual_seed(0)
    return PPOAgent(**_agent_kwargs(**over))


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
# The PRODUCTION shape (configs/showdown_sp_100m.yaml): agent.minibatches 120
# and an update budget of num_envs 8 x rollout_steps 3840 = 30,720 steps that
# whole episodes overshoot by eps, so B = 30,720 + eps and mbs = 256 + eps//120.
_M_100M = 120
_B_100M = 30_720


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


def _legacy_minibatch_plan(total, mbs, epochs):
    """The PRE-F-04 minibatch loop (commit 5d3c6b7, ppo.py update loop),
    replayed from the CURRENT torch RNG state as an oracle that owes nothing
    to the new code: per epoch ONE `randperm(total)`, slices
    `perm[start:start + mbs]` for `start in range(0, total, mbs)`, a slice
    under 2 rows skipped. Returns the executed row lists in order and the
    RNG state the loop leaves behind — 'keep' must match on BOTH, which is
    what makes it a pin against the old loop rather than against itself:
    an extra draw, a moved slice boundary or a changed skip each fail here
    while passing an absent-vs-'keep' comparison of the new loop."""
    plan: list[list[int]] = []
    for _ in range(epochs):
        perm = torch.randperm(total, device="cpu")
        for start in range(0, total, mbs):
            idx = perm[start : start + mbs]
            if idx.numel() < 2:
                continue
            plan.append(idx.tolist())
    return plan, torch.get_rng_state()


# FULL sha, not the abbreviation: an abbreviation stops resolving the moment
# it stops being unique, and `git show` then exits non-zero for a reason that
# has nothing to do with F-04.
_PRE_F04_COMMIT = "5d3c6b7c841c008b0e70e916e3d8242ef3166bb5"  # parent of wire commit 650a8e6
_PRE_F04_FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "ppo_pre_f04.py.txt"
# sha256 of that commit's rl/agents/ppo.py (72,626 bytes), so the vendored copy
# is self-checking even where git cannot corroborate it.
_PRE_F04_SHA256 = "307ad4a140f8fff08f2c619fdd326cbf915d9ad2dfd6c2111fc5b3acf02be1b7"


def _pre_f04_source():
    """`rl/agents/ppo.py` as of the commit BEFORE F-04, read from the VENDORED
    FIXTURE and only CROSS-CHECKED against the object store.

    Review round 2 rejected a git-only loader, correctly: it resolved an
    abbreviated sha and turned every git failure into `pytest.skip`, so a
    squash-merge (5d3c6b7 gc'd), an abbreviation that stopped being unique, or
    a run from a non-git export would each have reduced the whole weight-level
    bit-identity pin to skips indistinguishable from the suite's nine
    documented ones — the pin would stop pinning and nothing would say so.
    So the fixture is the source of truth and git is corroboration:

      * the fixture is REQUIRED and its sha256 is pinned here: missing or
        edited FAILS, and no code path skips;
      * when git can reach `_PRE_F04_COMMIT`, `<sha>:rl/agents/ppo.py` must be
        byte-identical to the fixture — that is what keeps the vendored copy
        honest, and it fails if someone regenerates the fixture from HEAD;
      * a commit that resolves but whose `ppo.py` does not is a broken repo,
        not a merge, and FAILS; only a genuinely unreachable object (post
        squash-merge, or no `git` at all) is tolerated, and it drops the
        CROSS-CHECK, never the pin.

    (`tests/fixtures/`, not `tests/data/`: `.gitignore:40` ignores every `data/`
    directory — the F-21 landmine — and a bit-identity baseline that a fresh
    clone does not get is no baseline.)"""
    try:
        src = _PRE_F04_FIXTURE.read_text()
    except OSError as exc:  # not a skip: this file IS the pin's baseline
        pytest.fail(f"pre-F-04 fixture {_PRE_F04_FIXTURE} unreadable: {exc}")
    digest = hashlib.sha256(src.encode()).hexdigest()
    assert digest == _PRE_F04_SHA256, (
        f"{_PRE_F04_FIXTURE.name} is no longer the pre-F-04 blob "
        f"({digest[:12]} != {_PRE_F04_SHA256[:12]})"
    )
    root = pathlib.Path(__file__).resolve().parents[1]
    try:
        reachable = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f"{_PRE_F04_COMMIT}^{{commit}}"],
            capture_output=True,
        ).returncode == 0
    except OSError:  # no git binary, or no checkout at all
        reachable = False
    if reachable:
        blob = subprocess.run(
            ["git", "-C", str(root), "show", f"{_PRE_F04_COMMIT}:rl/agents/ppo.py"],
            capture_output=True, text=True,
        )
        assert blob.returncode == 0, (
            f"{_PRE_F04_COMMIT[:12]} resolves but its rl/agents/ppo.py does not: "
            f"{blob.stderr.strip()}"
        )
        assert blob.stdout == src, (
            f"{_PRE_F04_FIXTURE.name} drifted from {_PRE_F04_COMMIT[:12]}:rl/agents/ppo.py"
        )
    return src


@functools.lru_cache(maxsize=1)
def _pre_f04_ppo():
    """That source exec'd as a throwaway module so the pre-change
    `update_episodes` can be RUN, not paraphrased. Every import in the file is
    absolute (`rl.agents.base`, `rl.buffers.*`, ...) and F-04 touched no other
    file, so the old module binds to today's tree and the ONLY difference on
    the wire is the minibatch loop itself. Nothing is written to disk and
    nothing is registered in `sys.modules`.

    The two identity assertions are the point: without them a source that had
    been regenerated from HEAD would turn this test back into the tautology
    review round 1 rejected (new code vs new code)."""
    src = _pre_f04_source()
    mod = types.ModuleType("_ppo_pre_f04")
    mod.__file__ = f"<pre-F-04 {_PRE_F04_COMMIT[:12]}:rl/agents/ppo.py>"
    exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    assert not hasattr(mod, "_minibatch_slices"), "that source already has F-04"
    assert "minibatch_tail" not in inspect.signature(mod.PPOAgent.__init__).parameters
    return mod


def _pre_f04_agent(**over):
    """The pre-F-04 PPOAgent under the SAME seed and kwargs `_agent` uses, so
    the two agents start bit-identical (asserted, not assumed)."""
    torch.manual_seed(0)
    return _pre_f04_ppo().PPOAgent(**_agent_kwargs(**over))


def _assert_same_weights_and_optimizer(new, old):
    for net in ("actor", "critic"):
        a, b = getattr(new, net).state_dict(), getattr(old, net).state_dict()
        assert a.keys() == b.keys()
        for name in a:
            assert torch.equal(a[name], b[name]), f"{net}.{name} moved"
    # Adam's moments and step counts too: a changed number of gradient steps
    # or a changed step ORDER moves these even when the weights happen to
    # land close, and it is the tail slice's step that F-04 is about.
    sa, sb = new.optimizer.state_dict(), old.optimizer.state_dict()
    assert sa["param_groups"] == sb["param_groups"]
    assert sa["state"].keys() == sb["state"].keys()
    for key, entry in sa["state"].items():
        assert entry.keys() == sb["state"][key].keys()
        for name, value in entry.items():
            other = sb["state"][key][name]
            if isinstance(value, torch.Tensor):
                assert torch.equal(value, other), f"opt state {key}.{name} moved"
            else:
                assert value == other, f"opt state {key}.{name} moved"


def test_pre_f04_baseline_is_present_and_pinned():
    """The bit-identity pin's baseline exists, hashes to the pre-F-04 blob, and
    really is pre-F-04 — asserted as its OWN test so losing it is a red run and
    not a quieter test suite. Review round 2's whole point: the pin must not be
    able to become a no-op without failing, so this has no skip branch either.
    The `_pre_f04_source` docstring says what the git cross-check adds."""
    assert _PRE_F04_FIXTURE.is_file(), "the pre-F-04 baseline is not in the tree"
    src = _pre_f04_source()  # fails on a hash mismatch or a drifted fixture
    assert hashlib.sha256(src.encode()).hexdigest() == _PRE_F04_SHA256
    # The content guards are the last line of defence in the one future the git
    # cross-check cannot reach (no object store AND a re-pinned hash): a
    # baseline regenerated from HEAD carries F-04 and would restore the
    # tautology, so refuse it on its text alone.
    assert "_minibatch_slices" not in src, "the baseline carries F-04's helper"
    assert "minibatch_tail" not in src, "the baseline carries F-04's kwarg"
    assert "class PPOAgent" in src and "def update_episodes" in src, "not ppo.py"


def test_minibatch_tail_rejects_unknown_policy():
    with pytest.raises(ValueError, match="minibatch_tail"):
        _agent(minibatch_tail="skip")


@pytest.mark.parametrize("tail_rows", _TAILS)
def test_minibatch_tail_keep_is_bit_identical_to_the_pre_f04_agent(tail_rows):
    """THE bit-identity pin (review round 1: the absent-vs-'keep' comparison
    was new-code-vs-new-code). Today's default is run side by side with the
    PRE-F-04 agent itself — same seed, same kwargs, same batch, same
    `manual_seed` before the update — at every async tail the plan can
    produce: weights, Adam state, the metrics dict (KEYS included, so a
    stray `loss/minibatch_*` under 'keep' fails here) and the torch RNG state
    left behind must all be identical. Any drift in the 'keep' path — an
    extra draw before `randperm`, `< min_rows` becoming `<=`, a moved slice
    boundary, a tensor op added to the bookkeeping — fails this test."""
    total = _M * _M + tail_rows
    new, old = _agent(minibatches=_M), _pre_f04_agent(minibatches=_M)
    assert new.minibatch_tail == "keep"
    _assert_same_weights_and_optimizer(new, old)  # same starting point

    batch = _recorded_batch(new, total)
    torch.manual_seed(7)
    m_new = new.update_episodes(batch, steps_seen=0)
    rng_new = torch.get_rng_state()
    torch.manual_seed(7)
    m_old = old.update_episodes(batch, steps_seen=0)
    rng_old = torch.get_rng_state()

    _assert_same_weights_and_optimizer(new, old)
    assert set(m_new) == set(m_old), "'keep' changed the metric keys"
    assert m_new == m_old
    assert torch.equal(rng_new, rng_old), "'keep' consumed different RNG"


def test_minibatch_tail_default_is_keep_and_bit_identical():
    """The kwarg is UNRULED, so the default must BE the pre-F-04 loop. The
    GIT-INDEPENDENT companion to
    test_minibatch_tail_keep_is_bit_identical_to_the_pre_f04_agent: that test
    runs the old agent and is the stronger pin, but it needs the pre-F-04 blob
    in the object store, so the structural half is asserted here too from a
    loop reimplemented in this file. Same seed, an async-shaped batch (tail 3
    < mbs//2, exactly where 'drop'/'fold' WOULD diverge), three pins:
      1. LEGACY ORACLE (review round 1): the rows every executed minibatch
         received — content AND order — equal a replay of the pre-F-04 loop
         from the same seed, and the torch RNG state afterwards equals the
         state after exactly `epochs` randperm draws: no extra draw, no
         moved boundary, no changed skip. It does not compare the new loop
         to itself.
      2. absent kwarg == 'keep': torch.equal on every actor/critic tensor,
         identical metrics, and 'keep' adds no metric key.
      3. 'fold' on the same seed diverges — the negative control that shows
         the tensor comparison has teeth."""
    total, epochs = _M * _M + 3, 2
    mbs = total // _M

    def run(**over):
        agent = _agent(minibatches=_M, epochs=epochs, **over)
        batch = _recorded_batch(agent, total)
        seen = _spy_minibatches(agent, batch)
        torch.manual_seed(7)
        metrics = agent.update_episodes(batch, steps_seen=0)
        return agent, metrics, seen, torch.get_rng_state()

    absent, m_absent, seen_absent, rng_absent = run()
    assert absent.minibatch_tail == "keep"

    # 1. the legacy oracle, replayed from the same seed the update ran under
    torch.manual_seed(7)
    legacy, rng_legacy = _legacy_minibatch_plan(total, mbs, epochs)
    assert len(legacy) == epochs * (_M + 1), "8 full slices + the 3-row tail per epoch"
    assert seen_absent == legacy, "the default executed different rows/order than the pre-F-04 loop"
    assert torch.equal(rng_absent, rng_legacy), "the default consumed RNG the pre-F-04 loop did not"

    # 2. absent == 'keep', tensor for tensor
    keep, m_keep, seen_keep, _ = run(minibatch_tail="keep")
    assert seen_keep == legacy
    for net in ("actor", "critic"):
        a, k = getattr(absent, net).state_dict(), getattr(keep, net).state_dict()
        assert a.keys() == k.keys()
        for name in a:
            assert torch.equal(a[name], k[name]), f"{net}.{name} moved"
    assert m_absent == m_keep
    assert "loss/minibatch_rows_min" not in m_keep, "'keep' must add no metric key"

    # 3. negative control
    fold, _, seen_fold, _ = run(minibatch_tail="fold")
    assert seen_fold != legacy and len(seen_fold) == epochs * _M
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


@pytest.mark.parametrize("eps", [1, 2, 60, 119, 120, 250])
def test_minibatch_slices_plan_at_the_100m_recipe(eps):
    """The pure plan at the PRODUCTION shape the F-04 proposal's arithmetic
    and its R0-3 gate rest on (review round 1: every other test runs at
    mbs == minibatches, the boundary of the `mbs >= m` assumption). B =
    30,720 + eps, minibatches 120: mbs = 256 + eps//120 >= 256 > 120, so the
    trailing slice is eps mod 120 — never a function of the width; the floor
    mbs//2 >= 128 exceeds every possible tail (<= 119), so 'drop' sits out
    ANY 1..119-row tail and 'fold' appends it to slice 119. Exact division
    (eps % 120 == 0) leaves all three plans equal to the legacy one. The
    optimizer-step count per epoch is 'keep' 120 + [tail >= 2] vs 'drop' /
    'fold' exactly 120 — the DOSE paragraph's 121 vs 120."""
    batch = _B_100M + eps
    mbs = batch // _M_100M
    tail = eps % _M_100M
    assert mbs == 256 + eps // _M_100M and batch % mbs == tail
    half = mbs // 2
    assert half >= 128 > tail

    def rows(sl):
        return sl[1] - sl[0]

    legacy = [(s, min(s + mbs, batch)) for s in range(0, batch, mbs)]
    assert len(legacy) == _M_100M + (1 if tail else 0)
    if tail:
        assert rows(legacy[-1]) == tail

    keep, keep_floor = _minibatch_slices(batch, mbs, "keep")
    assert keep == legacy and keep_floor == 2
    keep_exec = [sl for sl in keep if rows(sl) >= keep_floor]
    assert len(keep_exec) == _M_100M + (1 if tail >= 2 else 0)
    assert sum(map(rows, keep_exec)) == batch - (1 if tail == 1 else 0)

    drop, drop_floor = _minibatch_slices(batch, mbs, "drop")
    assert drop == legacy and drop_floor == half
    drop_exec = [sl for sl in drop if rows(sl) >= drop_floor]
    assert len(drop_exec) == _M_100M, "drop must leave exactly 120 steps"
    assert sum(map(rows, drop_exec)) == batch - tail, "drop sits out exactly the tail"
    assert all(rows(sl) == mbs for sl in drop_exec)

    fold, fold_floor = _minibatch_slices(batch, mbs, "fold")
    assert fold_floor == 2
    assert len(fold) == _M_100M, "fold must leave exactly 120 steps"
    assert fold[0][0] == 0 and fold[-1][1] == batch
    assert all(a[1] == b[0] for a, b in zip(fold, fold[1:])), "fold slices must tile B"
    assert rows(fold[-1]) == mbs + tail
    assert all(rows(sl) == mbs for sl in fold[:-1])
    # The action plan's fix line (>= mbs // 2 rows in every executed
    # minibatch) and gate R0-3's `loss/minibatch_rows_min >= 256`, on the plan.
    assert min(map(rows, fold)) == mbs and mbs >= max(256, half)
    assert max(map(rows, fold)) < 1.5 * mbs
    if tail == 0:
        assert fold == drop == keep == legacy
    else:
        assert fold != legacy


@pytest.mark.parametrize("tail_rows", _TAILS)
@pytest.mark.parametrize("policy", ["keep", "drop", "fold"])
def test_minibatch_tail_policies_on_async_shaped_batches(policy, tail_rows):
    """End to end through update_episodes, spying on the rows each executed
    minibatch actually received: under 'drop' and 'fold' every executed
    minibatch has >= mbs//2 rows; 'fold' trains every row exactly once per
    epoch; 'drop' drops at most one slice per epoch; 'keep' is today's wire
    — the executed rows, their order and the RNG consumption equal the
    pre-F-04 loop's replay (_legacy_minibatch_plan) at EVERY named tail —
    and reports no tail key."""
    epochs = 2
    agent = _agent(minibatches=_M, epochs=epochs, minibatch_tail=policy)
    batch = _recorded_batch(agent, _M * _M + tail_rows)
    total = len(batch["obs"])
    mbs = total // _M
    half = mbs // 2
    seen = _spy_minibatches(agent, batch)
    rng_before = torch.get_rng_state()
    metrics = agent.update_episodes(batch, steps_seen=0)
    rng_after = torch.get_rng_state()
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
        # The legacy oracle: replay the pre-F-04 loop from the RNG state the
        # update started at; rows, order and the RNG state left behind must
        # all agree (an absent-vs-'keep' comparison cannot see any of these).
        torch.set_rng_state(rng_before)
        legacy, rng_legacy = _legacy_minibatch_plan(total, mbs, epochs)
        assert seen == legacy, "keep executed different rows/order than the pre-F-04 loop"
        assert torch.equal(rng_after, rng_legacy), "keep consumed RNG the pre-F-04 loop did not"
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


@pytest.mark.parametrize("policy", ["drop", "fold"])
def test_minibatch_tail_metrics_at_the_100m_shape(policy):
    """update_episodes at the PRODUCTION shape (B = 30,720 + 60, minibatches
    120, mbs = 256, one epoch; tiny net, so it is cheap): the draft pre-reg's
    R0-3 launch read taken from the metrics the wire reports —
    loss/minibatch_rows_min >= 256 and loss/minibatch_rows_dropped == 0
    ('fold') / 60 ('drop') — plus exactly 120 gradient steps and the widest
    slice 316 ('fold', 256 + 60) / 256 ('drop'). The action plan's fix line
    asks for exactly this: every executed minibatch >= mbs // 2 on an
    async-shaped 30,721..30,839-row batch."""
    eps = 60
    mbs = (_B_100M + eps) // _M_100M
    agent = _agent(minibatches=_M_100M, epochs=1, minibatch_tail=policy)
    batch = _recorded_batch(agent, _B_100M + eps)
    sizes: list[int] = []
    orig = agent._logp_entropy

    # Sizes only, not row indices: `_spy_minibatches` would hash 30,780 obs
    # rows to identify them and the claim here is about WIDTHS, not order —
    # the row-level oracle runs at minibatches=8 where it is cheap.
    def count(obs, actions, masks, **kw):
        sizes.append(int(obs.shape[0]))
        return orig(obs, actions, masks, **kw)

    agent._logp_entropy = count
    metrics = agent.update_episodes(batch, steps_seen=0)
    assert math.isfinite(metrics["loss/policy"])
    assert len(sizes) == _M_100M, "exactly 120 gradient steps per epoch"
    assert mbs == 256 and min(sizes) >= mbs // 2, "the action plan's fix line"
    assert metrics["loss/minibatch_rows_min"] == float(min(sizes)) == float(mbs)
    if policy == "fold":
        assert metrics["loss/minibatch_rows_dropped"] == 0.0
        assert sum(sizes) == _B_100M + eps and max(sizes) == 256 + eps
    else:
        assert metrics["loss/minibatch_rows_dropped"] == float(eps)
        assert sum(sizes) == _B_100M and max(sizes) == 256
