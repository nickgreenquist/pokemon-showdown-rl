"""D26 R0-B — the LR anneal x auxiliary-head path, which has NEVER EXECUTED.

`rl/agents/ppo.py`'s anneal writes `param_groups[2]["lr"]` when an aux head
exists, and its own comment records that this is "Inert at D25's
lr_anneal_steps: 0". Every config with a live aux head pins `lr_anneal_steps: 0`
and every config with a live anneal has no aux head, so no run and no test has
ever taken this branch. `tests/test_ppo.py`'s agent builds no aux head, so its
two-tuple unpack of `param_groups` never sees a third group either.

D26 would be the first thing to execute it. This is its blocking gate.
"""

import pytest
import torch

from rl.agents.ppo import PPOAgent

OBS, ACTS, ROLL, ENVS = 828, 10, 128, 8
STEPS_PER_UPDATE = ROLL * ENVS          # 1024
ANNEAL = 12_000_000
BASE_LR = 2.5e-4

TRUNK_KWARGS = dict(species_vocab=152, move_vocab=166, embed_dim=64,
                    entity_dim=128, pool="max", ctx_sizes=[384, 384],
                    scorer_sizes=[256], value_sizes=[384, 384])


def _agent(anneal: int) -> PPOAgent:
    return PPOAgent(
        obs_dim=OBS, n_actions=ACTS, hidden_sizes=[512, 512],
        trunk="entity_deepsets", trunk_kwargs=dict(TRUNK_KWARGS),
        lr=BASE_LR, lr_anneal_steps=anneal,
        rollout_steps=ROLL, num_envs=ENVS,
        aux_oppact_coef=0.1, aux_scorer_sizes=[96], aux_head_gain=0.01,
        seed=0,
    )


def _expected_lr(u_pre: int) -> float:
    """The lr written at the TOP of update() from the PRE-increment counter."""
    return BASE_LR * max(0.0, 1.0 - u_pre * STEPS_PER_UPDATE / ANNEAL)


def test_third_group_exists_and_is_exactly_the_aux_head():
    """(a) Three groups, and group 2 is the aux head's params BY ID.

    Ordering is load-bearing: the anneal writes groups by index, and D25's own
    header notes that appending aux params to group 0 would silently hand them
    the critic's Adam moments.
    """
    agent = _agent(ANNEAL)
    groups = agent.optimizer.param_groups
    assert len(groups) == 3, f"expected [actor, critic, aux], got {len(groups)}"
    assert {id(p) for p in groups[2]["params"]} == {
        id(p) for p in agent.aux_head.parameters()
    }


@pytest.mark.parametrize("u_pre", [0, 1, 1000, 5859, 11717, 11718, 11719, 20000])
def test_all_three_groups_follow_the_schedule(u_pre):
    """(b) All three groups anneal together, including the clamp.

    u = 11718 is NOT the clamped case (frac = 6.4e-5 > 0); 11719 is the first
    clamped counter. Both boundaries are asserted rather than assumed.
    """
    agent = _agent(ANNEAL)
    agent.updates = u_pre
    agent._anneal_lr()
    want = _expected_lr(u_pre)
    for i, g in enumerate(agent.optimizer.param_groups):
        assert g["lr"] == pytest.approx(want, rel=1e-12, abs=1e-18), (
            f"group {i} lr {g['lr']!r} != {want!r} at pre-increment u={u_pre}"
        )
    if u_pre >= 11719:
        assert want == 0.0, "expected the clamped-to-zero regime"
    if u_pre == 11718:
        assert want > 0.0, "u=11718 must still be strictly positive"


def test_actor_critic_and_aux_share_one_lr_at_default_scale():
    """(c) At actor_lr_scale 1.0 the three groups are EQUAL at every u.

    This is what makes the anneal a PURE GLOBAL step-size schedule: the
    aux:policy gradient RATIO is untouched, so D25's coefficient 0.1 remains
    the operative coefficient throughout.
    """
    agent = _agent(ANNEAL)
    for u_pre in (0, 500, 5000, 11000):
        agent.updates = u_pre
        agent._anneal_lr()
        lrs = [g["lr"] for g in agent.optimizer.param_groups]
        assert lrs[0] == lrs[1] == lrs[2], f"groups diverged at u={u_pre}: {lrs}"


def test_anneal_off_is_an_exact_no_op_including_the_aux_group():
    """(d) With lr_anneal_steps: 0 no group's lr is ever written.

    D25 and D25-P ran in exactly this configuration, so this is the guard that
    the new code path cannot retroactively perturb the banked arms.
    """
    agent = _agent(0)
    before = [g["lr"] for g in agent.optimizer.param_groups]
    for u_pre in (0, 1, 5000, 20000):
        agent.updates = u_pre
        agent._anneal_lr()
    assert [g["lr"] for g in agent.optimizer.param_groups] == before


def test_schedule_matches_the_header_table():
    """The realised-schedule table pre-registered in D26's Q3, to 1e-9."""
    for step, u_pre, want in ((200_000, 195, 2.458613e-04),
                              (2_000_000, 1953, 2.083584e-04),
                              (6_000_000, 5859, 1.250325e-04)):
        assert _expected_lr(u_pre) == pytest.approx(want, rel=1e-6), step


def test_smoke_acceptance_lr_is_the_100k_value_not_the_200k_row():
    """R0-E's acceptance number. `step` advances by num_envs, so 100k steps is
    12,500 iterations = 97 completed updates, and the lr written at the last of
    them comes from the pre-increment counter 96."""
    updates = (100_000 // ENVS) // ROLL
    assert updates == 97
    assert _expected_lr(updates - 1) == pytest.approx(2.479520e-04, rel=1e-6)
