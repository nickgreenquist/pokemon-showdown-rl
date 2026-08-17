"""D25 offline gates — configs/showdown_sp_actpred12m.yaml (ratified r2).

The label canonicaliser and the head are pure torch and run in-process: R0-5(c)
(the oracle identity — the single best test in the cycle, it catches label,
ordering and timing bugs at once), R0-5(d) (canonicalisation, legality and the
anti-leak replay assertion), and the head's own arithmetic.

Everything touching the real trunk needs the 828-dim encoder, whose flags are
read at module import, so those gates run in a SUBPROCESS with both env vars
set (test_entity_deepsets's pattern): R0-2 (param accounting), R0-2b (the eval
path and the state_dict guard), R0-2c (third-group ordering), R0-3 (exact no-op
and init isolation), R0-7 (the aux head is never called at eval) and R0-9 (the
decoupled clip).

R0-5(a) label TIMING and R0-5(b) aliasing live in tests/test_showdown_env.py,
next to the env stub that can drive a two-seat step.
"""

import os
import subprocess
import sys

import pytest
import torch
from types import SimpleNamespace

from rl.envs.showdown import OPP_CHOICE_ALIASED, OPP_CHOICE_DIM, OPP_CHOICE_PRESENT
from rl.networks.opp_action import (
    CHOICE_DIM,
    N_CLASSES,
    OTHER_MOVE,
    SWITCH,
    OppActionHead,
    aux_cross_entropy,
    canonicalise,
)

# The real layout at OBS_DIM 828, duck-typed: canonicalise takes the net's own
# EntityTokenizer precisely so it needs no encoder import of its own.
OBS_W = 828
ID_OFF = SimpleNamespace(id_off=808, opp_mon_off=404, mon_dim=33)
PRESENT, ALIASED = OPP_CHOICE_PRESENT, OPP_CHOICE_PRESENT | OPP_CHOICE_ALIASED


def test_the_class_order_is_the_pre_registered_one():
    """§1 writes the space as "{ slot 0,1,2,3 | OTHER_MOVE | SWITCH }" and pins
    it numerically: its realised s26 frequencies are 43.6/27.3/13.6/5.2/3.0/
    **7.2**%, and s26's measured tape switch fraction is 0.0719 — so the LAST
    class is SWITCH. The design cycle's own probe code (`y12_to_y6` in
    results/d25/scripts/gate_r012.py) uses the same order.

    Nothing cross-references these indices between the head and the probe, so
    the ordering is not load-bearing for the loss. It is load-bearing for the
    READOUT: a head whose class 4 is SWITCH, read against a header whose class
    4 is OTHER_MOVE, is a silent mis-attribution. Pinned here so it cannot
    drift back."""
    assert (OTHER_MOVE, SWITCH) == (4, 5)
    # And the head's entity list must agree with the constants: the null token
    # scores OTHER_MOVE, the bench pool scores SWITCH.
    torch.manual_seed(0)
    head = OppActionHead(ctx_dim=4, entity_dim=3, sizes=[8])
    head.init_head(1.0)
    ctx = torch.randn(2, 4)
    moves = torch.randn(2, 4, 3)
    bench = torch.randn(2, 3)
    logits = head(ctx, moves, bench)
    null = head.null_token.detach().expand(2, 1, -1)
    assert torch.allclose(
        logits[:, OTHER_MOVE], head(ctx, null.expand(-1, 4, -1), bench)[:, 0], atol=1e-6
    )
    assert torch.allclose(
        logits[:, SWITCH], head(ctx, bench.unsqueeze(1).expand(-1, 4, -1), bench)[:, 0],
        atol=1e-6,
    )


def test_the_two_seam_widths_agree():
    """The env writes [kind, id, flags]; the agent side reads it without
    importing poke_env, so the two constants are asserted equal here."""
    assert CHOICE_DIM == OPP_CHOICE_DIM == 3


def _obs(slot_ids=(0, 0, 0, 0), opp_faints=0, n=1, active_alive=True):
    """A minimal obs row carrying only what canonicalise reads: the global
    block's opponent faint count, the id suffix's opponent-move block, and the
    opponent active's revealed/fainted/is-active bits."""
    obs = torch.zeros(n, OBS_W)
    obs[:, 2] = opp_faints / 6.0
    for j, move_id in enumerate(slot_ids):
        obs[:, ID_OFF.id_off + 16 + j] = move_id / 256.0
    base = ID_OFF.opp_mon_off  # opponent mon block 0 = their active
    obs[:, base + 0] = 1.0  # revealed
    obs[:, base + 3] = 1.0  # is-active
    obs[:, base + 2] = 0.0 if active_alive else 1.0  # fainted
    return obs


def _choice(kind, ident, flags=PRESENT, n=1):
    return torch.tensor([[kind, ident, flags]] * n, dtype=torch.int32)


# --- R0-5(d): canonicalisation, legality, anti-leak -------------------------


def test_a_slotted_move_canonicalises_to_its_own_slot():
    obs = _obs(slot_ids=(33, 94, 0, 0))
    for slot, move_id in enumerate((33, 94)):
        target, _, valid, _ = canonicalise(obs, _choice(1, move_id), ID_OFF)
        assert int(target[0]) == slot and bool(valid[0])


def test_any_switch_canonicalises_to_switch_and_names_no_target():
    """L6 does not sub-decompose the switch: R0-L's 12-class alternative had to
    beat it by >= 0.05 nats at BOTH named lanes and cleared 0 of 2."""
    obs = _obs(slot_ids=(33, 94, 0, 0), opp_faints=2)
    for species in (121, 143, 0):
        target, _, valid, _ = canonicalise(obs, _choice(0, species), ID_OFF)
        assert int(target[0]) == SWITCH and bool(valid[0])


def test_unslotted_moves_id_zero_and_struggle_all_reach_other_move():
    obs = _obs(slot_ids=(33, 94, 0, 0))
    for ident in (57, 0, 165):  # an unrevealed move, recharge's id 0, Struggle
        target, _, valid, _ = canonicalise(obs, _choice(1, ident), ID_OFF)
        assert int(target[0]) == OTHER_MOVE and bool(valid[0])


def test_legality_is_obs_derived_and_other_move_is_always_legal():
    obs = _obs(slot_ids=(33, 94, 0, 0), opp_faints=1)
    _, allow, _, _ = canonicalise(obs, _choice(1, 33), ID_OFF)
    assert allow[0].tolist() == [True, True, False, False, True, True]
    # SWITCH is legal iff a LIVE NON-ACTIVE mon exists. With the active alive
    # that is "at most 4 fainted"; the faint count is public, which is why this
    # needs no privileged read.
    for faints, switch_legal in ((0, True), (4, True), (5, False)):
        _, allow, _, _ = canonicalise(
            _obs(slot_ids=(33, 0, 0, 0), opp_faints=faints), _choice(1, 33), ID_OFF
        )
        assert bool(allow[0, SWITCH]) is switch_legal
        assert bool(allow[0, OTHER_MOVE]) is True  # never masked — see B11


def test_a_forced_post_faint_replacement_can_still_switch():
    """THE BUG THE FROZEN TAPES COULD NOT CATCH, found by running the real
    launch path: "6 - 1 - faints" assumes the opponent's ACTIVE IS ALIVE. On a
    forced post-faint replacement it is not, so with 5 fainted the one survivor
    sits on the BENCH and is switchable. The old rule called that label illegal
    and dropped it, at a measured 0.12% of live decisions — a rate that would
    have hard-failed R0-5(d) at read time.

    Whether forced replacements belong in the loss at all is C10 and is still
    open; this fixes only their LEGALITY."""
    for faints, switch_legal in ((4, True), (5, True)):
        obs = _obs(slot_ids=(33, 0, 0, 0), opp_faints=faints, active_alive=False)
        target, allow, valid, stats = canonicalise(obs, _choice(0, 121), ID_OFF)
        assert int(target[0]) == SWITCH
        assert bool(allow[0, SWITCH]) is switch_legal
        assert bool(valid[0]) is switch_legal
        assert stats["aux/illegal_label_frac"] == 0.0
    # A fainted active with the whole team down is still illegal — the battle is
    # over, and the rule must not become "SWITCH is always legal".
    obs = _obs(slot_ids=(33, 0, 0, 0), opp_faints=6, active_alive=False)
    _, allow, _, _ = canonicalise(obs, _choice(0, 121), ID_OFF)
    assert not bool(allow[0, SWITCH])


def test_an_illegal_label_is_dropped_and_counted_never_scored():
    """One occurrence would otherwise put the label on a -1e8 logit and produce
    a ~1e8 CE term. Measured rate is 0.0000 on all five tapes and on the frozen
    s36 reference, so this path should never execute — which is exactly why it
    needs a test rather than a comment."""
    obs = _obs(slot_ids=(33, 0, 0, 0), opp_faints=5)  # no live bench
    target, allow, valid, stats = canonicalise(obs, _choice(0, 121), ID_OFF)
    assert int(target[0]) == SWITCH and not bool(allow[0, SWITCH])
    assert not bool(valid[0])
    assert stats["aux/illegal_label_frac"] == 1.0


def test_a_frame_collision_is_dropped_and_counted():
    """The injectivity argument is incomplete — `_species_id` returns 0 for
    out-of-dex species and unrevealed slots are also 0 — so the ambiguous case
    is dropped rather than argued away."""
    obs = _obs(slot_ids=(33, 33, 0, 0))
    _, _, valid, stats = canonicalise(obs, _choice(1, 33), ID_OFF)
    assert not bool(valid[0]) and stats["aux/frame_collision_frac"] == 1.0


def test_absent_and_aliased_rows_are_dropped_not_zero_filled():
    obs = _obs(slot_ids=(33, 94, 0, 0), n=3)
    choice = torch.tensor(
        [[1, 33, PRESENT], [-1, -1, 0], [1, 33, ALIASED]], dtype=torch.int32
    )
    _, _, valid, stats = canonicalise(obs, choice, ID_OFF)
    assert valid.tolist() == [True, False, False]
    assert stats["aux/label_present_frac"] == pytest.approx(2 / 3)
    assert stats["aux/labelled_frac"] == pytest.approx(1 / 3)
    assert stats["aux/aliased_frac"] == pytest.approx(0.5)


def _random_rows(n, generator):
    """n rows with distinct nonzero slot ids (some slots empty) and a random
    public faint count — the shape a real tape has."""
    obs = torch.zeros(n, OBS_W)
    faints = torch.randint(0, 6, (n,), generator=generator)
    obs[:, 2] = faints / 6.0
    obs[:, ID_OFF.opp_mon_off + 0] = 1.0   # their active: revealed,
    obs[:, ID_OFF.opp_mon_off + 3] = 1.0   # is-active, and alive
    slot_ids = torch.zeros(n, 4, dtype=torch.long)
    for i in range(n):
        filled = int(torch.randint(1, 5, (1,), generator=generator))
        ids = torch.randperm(165, generator=generator)[:filled] + 1
        slot_ids[i, :filled] = ids
    obs[:, ID_OFF.id_off + 16 : ID_OFF.id_off + 20] = slot_ids.float() / 256.0
    return obs, slot_ids


def test_anti_leak_a_label_never_names_an_entity_absent_from_its_own_row():
    """R0-5(d)'s replay assertion, and it is what makes the anti-leak property
    STRUCTURAL rather than argued (B4): the frame is the BUFFERED OBS ROW'S OWN
    id suffix, so a switch-in the env only learns about after the step cannot
    become a nameable class. Asserted, not commented."""
    generator = torch.Generator().manual_seed(0)
    obs, slot_ids = _random_rows(400, generator)
    idents = torch.randint(0, 166, (400,), generator=generator)
    kinds = torch.randint(0, 2, (400,), generator=generator)
    choice = torch.stack([kinds, idents, torch.full_like(kinds, PRESENT)], -1).int()
    target, _, _, _ = canonicalise(obs, choice, ID_OFF)
    slot_rows = target < 4
    named = slot_ids[slot_rows].gather(1, target[slot_rows, None]).squeeze(-1)
    assert (named == idents[slot_rows]).all()  # the named move IS in this row
    assert (named != 0).all()  # ...and it is a real slot, not padding
    # Every move whose id is absent from its row's slots falls to OTHER_MOVE.
    absent = (kinds == 1) & ~(slot_ids == idents[:, None]).any(-1)
    assert (target[absent] == OTHER_MOVE).all()


# --- R0-5(c): THE ORACLE IDENTITY -------------------------------------------


def _oracle_tape(n=20_000, seed=0, aliased_frac=0.0):
    """A synthetic tape whose label-generating distribution is known exactly.

    Labels are drawn from `oracle` (masked to the legal classes) and then
    written back out in the ENV's own [kind, id, flags] encoding, so the round
    trip exercises the real canonicaliser rather than a reimplementation of it.

    On aliased rows the label is drawn UNIFORMLY over the legal classes — the
    offline analogue of poke-env re-basing the opponent's move list, where the
    slot the label lands in has nothing to do with the slot the observation
    describes. Scoring those rows under the oracle INFLATES the cross entropy,
    which is the direction the real tapes measured (+0.66 nats unfiltered).
    """
    generator = torch.Generator().manual_seed(seed)
    obs, slot_ids = _random_rows(n, generator)
    _, allow, _, _ = canonicalise(obs, _choice(1, 0, n=n), ID_OFF)
    logits = torch.randn(n, N_CLASSES, generator=generator) * 1.5
    oracle = torch.softmax(logits.masked_fill(~allow, -1e8), dim=-1)
    aliased = torch.rand(n, generator=generator) < aliased_frac
    rebased = allow.float() / allow.sum(-1, keepdim=True)
    drawn = torch.where(aliased[:, None], rebased, oracle)
    labels = torch.multinomial(drawn, 1, generator=generator).squeeze(-1)

    kind = torch.where(labels == SWITCH, 0, 1)
    ident = torch.where(
        labels < 4,
        slot_ids.gather(1, labels.clamp(max=3)[:, None]).squeeze(-1),
        torch.where(labels == SWITCH, torch.full_like(labels, 121), torch.zeros_like(labels)),
    )
    flags = torch.where(aliased, torch.full_like(labels, ALIASED), torch.full_like(labels, PRESENT))
    choice = torch.stack([kind, ident, flags], dim=-1).int()
    return obs, choice, labels, oracle, allow


def test_r05c_the_oracle_s_ce_against_realised_labels_equals_its_own_entropy():
    """THE test of the cycle. The labels ARE draws from the oracle, so scoring
    the oracle against them must return the oracle's own entropy — any label,
    ordering or timing bug breaks the identity at once. Measured on the real
    tapes: +0.008 / +0.015 nats filtered, +0.66 unfiltered."""
    obs, choice, labels, oracle, _ = _oracle_tape()
    target, allow, valid, _ = canonicalise(obs, choice, ID_OFF)
    assert (target == labels).all()  # the env round trip is lossless
    assert bool(valid.all())

    log_oracle = torch.log(oracle.clamp_min(1e-30))
    entropy = -(oracle * log_oracle).sum(-1).mean()
    cross_entropy = aux_cross_entropy(log_oracle, target, allow, valid)
    se = (-log_oracle.gather(1, target[:, None])).std() / len(target) ** 0.5
    assert abs(float(cross_entropy - entropy)) < 3 * float(se)


def test_r05c_the_identity_breaks_if_aliased_rows_are_not_dropped():
    """The aliasing fix is what makes every number in the pre-registration
    trustworthy, so the test asserts it BUYS something: keep the aliased rows
    and the identity fails by a wide margin."""
    obs, choice, _, oracle, _ = _oracle_tape(aliased_frac=0.10)
    target, allow, valid, stats = canonicalise(obs, choice, ID_OFF)
    assert 0.05 < stats["aux/aliased_frac"] < 0.15
    log_oracle = torch.log(oracle.clamp_min(1e-30))
    entropy = -(oracle * log_oracle).sum(-1).mean()
    filtered = aux_cross_entropy(log_oracle, target, allow, valid)
    unfiltered = aux_cross_entropy(log_oracle, target, allow, torch.ones_like(valid))
    assert abs(float(filtered - entropy)) < 0.02
    assert float(unfiltered - entropy) > 0.05  # the identity fails, upward


# --- the head's own arithmetic (B7) -----------------------------------------


def test_head_param_counts_are_the_pre_registered_ones():
    """B7's live arithmetic, at the ratified trunk_kwargs. The scorer is
    Linear(384+128, w) + Linear(w, 1) = 514w + 1, plus 6 slot biases, plus the
    DECLARED learned 128-d null token."""
    for width, expected in ((32, 16_583), (64, 33_031), (96, 49_479), (128, 65_927), (256, 131_719)):
        head = OppActionHead(ctx_dim=384, entity_dim=128, sizes=[width])
        assert sum(p.numel() for p in head.parameters()) == expected, width
    # The constant-null-token variant is NOT taken; recorded so the r1 numbers
    # stay traceable: it would be 128 fewer at every width.
    assert 49_479 - 128 == 49_351


def test_head_init_follows_the_net_s_own_convention():
    head = OppActionHead(ctx_dim=384, entity_dim=128, sizes=[96])
    head.init_head(0.01)
    with torch.no_grad():
        assert float(head.slot_bias.abs().sum()) == 0.0  # zero, and NOT scaled
        assert float(head.scorer[-1].weight.abs().max()) < 0.01  # final layer only
        assert 0.01 < float(head.null_token.std()) < 0.03  # entity-space token
        # Off zero on purpose: an empty bench pools to the all-zero vector, and
        # OTHER_MOVE must not be the same scorer input as an empty-bench SWITCH.
        assert float(head.null_token.abs().sum()) > 0.0


def test_head_is_scorer_shaped_so_slot_identity_survives():
    """A plain Linear(ctx -> 6) would be ill-posed and that is measured, not
    argued: ctx is ctx_net over MAX-POOLED team features, so opponent slot
    identity is destroyed before ctx exists. Permuting the move tokens must
    permute the logits — the property a ctx-only head cannot have."""
    torch.manual_seed(0)
    head = OppActionHead(ctx_dim=8, entity_dim=4, sizes=[16])
    head.init_head(1.0)
    ctx, moves, bench = torch.randn(2, 8), torch.randn(2, 4, 4), torch.randn(2, 4)
    base = head(ctx, moves, bench)
    swapped = head(ctx, moves[:, [1, 0, 2, 3]], bench)
    assert torch.allclose(base[:, [1, 0, 2, 3]], swapped[:, :4], atol=1e-6)
    assert torch.allclose(base[:, 4:], swapped[:, 4:], atol=1e-6)


def test_the_head_can_learn_the_task_it_is_asked_to_learn():
    """The manipulation check's machinery, end to end: a head fit on a fixed
    batch must beat the mask-renormalised marginal by a wide margin. If this
    cannot happen offline, a VOID at 12M would be unreadable."""
    torch.manual_seed(0)
    n = 256
    ctx = torch.randn(n, 32)
    moves, bench = torch.randn(n, 4, 16), torch.randn(n, 16)
    allow = torch.ones(n, N_CLASSES, dtype=torch.bool)
    valid = torch.ones(n, dtype=torch.bool)
    # A learnable target: the slot whose token is most aligned with ctx's head.
    target = (moves @ ctx[:, :16, None]).squeeze(-1).argmax(-1)
    head = OppActionHead(ctx_dim=32, entity_dim=16, sizes=[64])
    head.init_head(0.01)
    optimizer = torch.optim.Adam(head.parameters(), lr=3e-3)
    first = None
    for _ in range(400):
        loss = aux_cross_entropy(head(ctx, moves, bench), target, allow, valid)
        first = first if first is not None else float(loss.detach())
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    marginal = -torch.log(torch.bincount(target, minlength=N_CLASSES) / n)
    assert first > 1.5  # starts near log 6 = 1.79
    assert float(loss.detach()) < 0.5 * float((marginal[target]).mean())


# --- the trunk-side gates, in a subprocess at the 828 encoder ----------------

_CHILD = r"""
import numpy as np
import torch
import gymnasium as gym

from rl.agents.ppo import PPOAgent
from rl.networks.entity_deepsets import ACTOR_PARAM_CEILING
from rl.envs.showdown import OBS_DIM

assert OBS_DIM == 828, OBS_DIM

TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
    pool="max", ctx_sizes=[384, 384], scorer_sizes=[256], value_sizes=[384, 384],
)
PPO_KWARGS = dict(
    num_envs=2, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
    rollout_steps=2, epochs=1, minibatches=1, clip_eps=0.2,
    entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[512, 512],
)


def mk(seed=0, **overrides):
    torch.manual_seed(seed)
    return PPOAgent(
        gym.spaces.Box(-1.0, 4.0, (828,), np.float32),
        gym.spaces.Discrete(10),
        trunk="entity_deepsets", trunk_kwargs=TRUNK_KWARGS,
        **PPO_KWARGS, **overrides,
    )


rng = np.random.default_rng(0)

def obs_batch(n):
    x = rng.random((n, 828), dtype=np.float32) * 0.5
    # A plausible id suffix: real ids in [1, 151] / [1, 165], scaled by 256.
    x[:, 808:820] = rng.integers(1, 152, (n, 12)) / 256.0
    x[:, 820:828] = rng.integers(1, 166, (n, 8)) / 256.0
    return x


def rows(count, aux=True, seed=7):
    # Paired batches: the aux-on and aux-off variants must be the SAME data, so
    # the labels are drawn from their own stream rather than advancing the one
    # the observations come from.
    global rng
    rng = np.random.default_rng(seed)
    n = PPO_KWARGS["num_envs"]
    out = []
    for _ in range(count):
        base = (
            obs_batch(n), rng.integers(0, 10, n), rng.random(n).astype(np.float32),
            obs_batch(n), np.zeros(n, bool), np.zeros(n, bool),
            np.ones((n, 10), bool), np.ones((n, 10), bool), None, None,
        )
        out.append(base)
    if not aux:
        return out
    labels = np.random.default_rng(seed + 1000)
    return [
        (*base, np.stack([
            np.ones(n, np.int32),                          # kind: a move
            labels.integers(1, 166, n).astype(np.int32),   # its id
            np.full(n, 1, np.int32),                       # present, not aliased
        ], axis=-1))
        for base in out
    ]


def row(t, aux=True):
    return rows(1, aux=aux, seed=100 + t)[0]


# --- R0-2: PARAM ACCOUNTING (a POLICY here, not a code gate: the net's own
# assert walks EntityDeepSetsNet.parameters(), so an agent-owned head is
# invisible to it and no aux width can hard-fail at launch).
agent = mk(aux_oppact_coef=0.1, aux_scorer_sizes=[96])
actor_n = sum(p.numel() for p in agent.actor.parameters())
aux_n = sum(p.numel() for p in agent.aux_head.parameters())
assert actor_n == 626_059, actor_n
assert sum(p.numel() for p in agent.critic.parameters()) == 494_849
assert aux_n == 49_479, aux_n
assert actor_n + aux_n == 675_538
assert ACTOR_PARAM_CEILING == 681_994
assert ACTOR_PARAM_CEILING - (actor_n + aux_n) == 6_456
for width, total in ((128, 691_986), (256, 757_778)):
    wide = mk(aux_oppact_coef=0.1, aux_scorer_sizes=[width])
    n = actor_n + sum(p.numel() for p in wide.aux_head.parameters())
    assert n == total, (width, n)
    assert n > ACTOR_PARAM_CEILING  # fails the strict actor+aux accounting

# --- R0-3(a): aux_oppact_coef = 0.0 is an EXACT no-op, RNG stream included.
torch.manual_seed(0); off = PPOAgent(
    gym.spaces.Box(-1.0, 4.0, (828,), np.float32), gym.spaces.Discrete(10),
    trunk="entity_deepsets", trunk_kwargs=TRUNK_KWARGS, **PPO_KWARGS)
after_off = torch.randn(4)
torch.manual_seed(0); zero = PPOAgent(
    gym.spaces.Box(-1.0, 4.0, (828,), np.float32), gym.spaces.Discrete(10),
    trunk="entity_deepsets", trunk_kwargs=TRUNK_KWARGS,
    aux_oppact_coef=0.0, **PPO_KWARGS)
assert torch.equal(after_off, torch.randn(4))
assert zero.aux_head is None and len(zero.optimizer.param_groups) == 2
assert zero.buffer.opp_choice is None
for key, value in off.actor.state_dict().items():
    assert torch.equal(value, zero.actor.state_dict()[key]), key

# --- R0-3(b): INIT ISOLATION. With the lever ON, the actor and critic are
# BIT-IDENTICAL to the lever-off build at the same seed, because the head is
# constructed LAST. Fails immediately if anyone moves that construction.
on = mk(aux_oppact_coef=0.1)
control = mk()
for name in ("actor", "critic"):
    a = getattr(on, name).state_dict()
    b = getattr(control, name).state_dict()
    assert a.keys() == b.keys(), name
    for key in a:
        assert torch.equal(a[key], b[key]), (name, key)

# --- R0-2b: the EVAL PATH. actor.state_dict() is unchanged, so a D25
# checkpoint scores identically to a control checkpoint of the same weights
# and every eval script runs unmodified.
control.actor.load_state_dict(on.actor.state_dict())
eval_obs, eval_mask = obs_batch(4), np.ones((4, 10), bool)
assert (on.act(eval_obs, eval_mask, deterministic=True)
        == control.act(eval_obs, eval_mask, deterministic=True)).all()
assert "aux_head" in on.state_dict() and "aux_head" not in control.state_dict()
try:
    control.load_state_dict(on.state_dict())
except ValueError as err:
    assert "aux_oppact_coef = 0" in str(err), err
else:
    raise AssertionError("an aux checkpoint loaded into an aux-off agent silently")

# --- R0-2c: THIRD-GROUP ORDERING. Load a 2-group control checkpoint into a
# D25 agent and assert every critic param receives a shape-matching exp_avg.
# This is the test that fails on the group-0 append.
donor = mk()
for param in donor.params:
    param.grad = torch.zeros_like(param)
donor.optimizer.step()
grafted = mk(aux_oppact_coef=0.1)
grafted.load_state_dict(donor.state_dict())
for param in grafted.critic_params:
    state = grafted.optimizer.state[param]
    assert "exp_avg" in state and state["exp_avg"].shape == param.shape
for param in grafted.aux_params:
    assert not grafted.optimizer.state.get(param)  # simply gets none
flat = [p for group in grafted.optimizer.param_groups for p in group["params"]]
order = [*grafted.actor_params, *grafted.critic_params, *grafted.aux_params]
assert len(flat) == len(order) and all(a is b for a, b in zip(flat, order))

# --- R0-7: the aux head is NEVER called in act() or at eval, and the
# opponent-move-token pass does not run either (move_net is called once per
# forward, not twice).
calls = {"aux": 0, "move": 0}
on.aux_head.register_forward_hook(lambda *_: calls.__setitem__("aux", calls["aux"] + 1))
on.actor.move_net.register_forward_hook(lambda *_: calls.__setitem__("move", calls["move"] + 1))
for _ in range(5):
    on.act(eval_obs, eval_mask, deterministic=True)
    on.act(eval_obs, eval_mask)
assert calls == {"aux": 0, "move": 10}, calls

# --- R0-9: THE DECOUPLED CLIP. On a fixed batch loss/grad_norm and
# loss/grad_clip_frac are numerically identical lever-on and lever-off. One
# grad step per update (epochs 1, minibatches 1), so the comparison is of the
# same weights under the same permutation.
rows_on, rows_off = rows(2, aux=True), rows(2, aux=False)
for on_row, off_row in zip(rows_on, rows_off):
    assert (on_row[0] == off_row[0]).all()  # the batches really are identical
lever_on, lever_off = mk(aux_oppact_coef=0.1), mk()
torch.manual_seed(99)
for r in rows_on:
    metrics_on = lever_on.update(r)
torch.manual_seed(99)
for r in rows_off:
    metrics_off = lever_off.update(r)
for key in ("loss/grad_norm", "loss/grad_clip_frac", "loss/policy", "loss/value"):
    assert metrics_on[key] == metrics_off[key], (key, metrics_on[key], metrics_off[key])
assert np.isfinite(metrics_on["aux/loss"]) and metrics_on["aux/loss"] > 0
assert metrics_on["aux/labelled_frac"] == 1.0
assert metrics_on["aux/illegal_label_frac"] == 0.0
assert metrics_on["aux/frame_collision_frac"] == 0.0
assert "aux/loss" not in metrics_off

# ...and the aux contribution to the step is bounded by aux_max_grad_norm.
bounded = mk(aux_oppact_coef=50.0, aux_max_grad_norm=0.5)
logits, *feats = bounded.actor(
    torch.as_tensor(obs_batch(8)), return_features=True
)
target = torch.zeros(8, dtype=torch.long)
allow = torch.ones(8, 6, dtype=torch.bool)
valid = torch.ones(8, dtype=torch.bool)
for param in (*bounded.actor_params, *bounded.critic_params, *bounded.aux_params):
    param.grad = None
loss, norm, trunk, delivered, scale = bounded._aux_gradient(
    tuple(feats), target, allow, valid
)
assert abs(delivered - trunk * scale) < 1e-9, (delivered, trunk, scale)
assert 0.0 < scale <= 1.0, scale
applied = torch.norm(torch.stack([
    p.grad.norm() for p in (*bounded.actor_params, *bounded.aux_params)
    if p.grad is not None
]))
assert norm > 0.5, norm  # the raw gradient really did need clipping
assert float(applied) <= 0.5 + 1e-5, float(applied)
# The trunk slice is a strict subset of the whole aux gradient, and nonzero:
# it is the numerator R0-10b's ratio is read from, live.
assert 0.0 < trunk <= norm, (trunk, norm)

# WHERE THE AUX GRADIENT MAY GO, asserted rather than argued (B6b): the
# shared trunk — ctx_net, mon_net, move_net, field_net and both embedding
# tables — and the head. NEVER the policy scorer or slot_bias (those are the
# acting readout, and a lever that moved them would not be one lever), and
# NEVER the critic, which this rung leaves untouched.
touched = {
    name for name, param in bounded.actor.named_parameters() if param.grad is not None
}
assert all(not n.startswith(("scorer.", "slot_bias")) for n in touched), sorted(touched)
assert any(n.startswith("ctx_net.") for n in touched)
assert any(n.startswith("move_net.") for n in touched)   # B6a's new pathway
assert any(n.startswith("move_emb") for n in touched)
assert all(p.grad is None for p in bounded.critic_params)

# --- the loud seams: env flag and agent hparam must be set together.
try:
    mk(aux_oppact_coef=0.1).update(row(0, aux=False))
except ValueError as err:
    assert "opponent-action mismatch" in str(err), err
else:
    raise AssertionError("a lever-on agent accepted a batch with no labels")
try:
    mk().update(row(0))
except ValueError as err:
    assert "opponent-action mismatch" in str(err), err
else:
    raise AssertionError("a lever-off agent accepted opponent-action labels")

print("OK")
"""


def test_d25_trunk_gates_r02_r02b_r02c_r03_r07_r09():
    result = subprocess.run(
        [sys.executable, "-c", _CHILD],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_the_lever_refuses_the_configurations_it_was_not_ratified_for():
    """The label space is not a free choice: L6 is R0-L's pre-stated fallback,
    executed because the 12-class adopt-rule FAILED at both named lanes. And
    D18's plumbing must not ride along — R0-1's fingerprint requires
    privileged_dim and env_kwargs.privileged ABSENT."""
    import gymnasium as gym
    import numpy as np

    from rl.agents.ppo import PPOAgent

    kwargs = dict(
        observation_space=gym.spaces.Box(-1.0, 1.0, (8,), np.float32),
        action_space=gym.spaces.Discrete(4),
        num_envs=2, device="cpu", lr=1e-3, gamma=0.99, gae_lambda=0.95,
        rollout_steps=4, epochs=1, minibatches=1, clip_eps=0.2,
        entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[8],
    )
    with pytest.raises(TypeError, match="entity_deepsets"):
        PPOAgent(aux_oppact_coef=0.1, **kwargs)
    with pytest.raises(ValueError, match="aux_oppact_coef must be"):
        PPOAgent(aux_oppact_coef=-1.0, **kwargs)
