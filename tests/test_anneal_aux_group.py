"""D26 R0-B — the LR anneal x auxiliary-head path, which has NEVER EXECUTED.

`rl/agents/ppo.py`'s anneal writes `param_groups[2]["lr"]` when an aux head
exists, and its own comment records that this is "Inert at D25's
lr_anneal_steps: 0". Every config with a live aux head pins `lr_anneal_steps: 0`
and every config with a live anneal has no aux head, so no run and no test has
ever taken that branch. `tests/test_ppo.py`'s agent builds no aux head, so its
two-tuple unpack of `param_groups` never sees a third group either. D26 would be
the first thing to execute it; this is its blocking gate.

These tests drive a REAL `update()` to a full rollout fill and read the lr back
off the optimizer, following `tests/test_ppo.py::_lr_after_fill`. They
deliberately do NOT re-implement the schedule and compare against themselves —
that would assert the formula rather than the code path that has never run.
"""

import os
import subprocess
import sys
from pathlib import Path

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent

# `rl.envs.showdown` freezes ID_DIM from the process env at IMPORT time, so
# setting the flags at construction is too late once any earlier test in the
# session has imported it. The in-process tests therefore SKIP unless the flags
# were set before pytest started; `test_r0b_gate_runs_under_the_encoder_flags`
# below re-runs this whole file in a subprocess that has them, so the gate is
# still executed by a bare `pytest tests/` (the pattern at
# tests/test_privileged_block.py:69-77).
_FLAGS_SET = (os.environ.get("POKEMON_RL_ENCODER_V2") == "1"
              and os.environ.get("POKEMON_RL_ENCODER_IDS") == "1")
_needs_flags = pytest.mark.skipif(
    not _FLAGS_SET,
    reason="entity trunk needs POKEMON_RL_ENCODER_V2/IDS set before import; "
           "the subprocess test in this file covers it",
)


def test_r0b_gate_runs_under_the_encoder_flags():
    """R0-B in a child process that HAS the encoder flags.

    This is the assertion that makes the gate real under a plain `pytest
    tests/`: without it the in-process tests would silently skip and R0-B would
    read as satisfied while never having executed.
    """
    if _FLAGS_SET:
        pytest.skip("already running with the flags; the in-process tests ran")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(Path(__file__).resolve()), "-q"],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1",
             "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]

OBS_DIM, N_ACTS, ROLL, ENVS = 828, 10, 128, 8
STEPS_PER_UPDATE = ROLL * ENVS          # 1024, the anneal's own arithmetic
ANNEAL = 12_000_000
BASE_LR = 2.5e-4

TRUNK_KWARGS = dict(species_vocab=152, move_vocab=166, embed_dim=64,
                    entity_dim=128, pool="max", ctx_sizes=[384, 384],
                    scorer_sizes=[256], value_sizes=[384, 384])


def _agent(anneal_steps: int) -> PPOAgent:
    """D25's arm, with the anneal switched on. epochs/minibatches are shrunk to
    1: the SCHEDULE is under test, not the optimisation.

    The entity tokenizer reads the encoder flags from the process env at
    construction and both are required for the 828 layout, so they are set for
    the construction only and restored — no other test inherits them
    (tests/test_d25_placebo.py's pattern).
    """
    saved = {k: os.environ.get(k)
             for k in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS")}
    os.environ["POKEMON_RL_ENCODER_V2"] = "1"
    os.environ["POKEMON_RL_ENCODER_IDS"] = "1"
    try:
        return _build(anneal_steps)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _build(anneal_steps: int) -> PPOAgent:
    torch.manual_seed(0)
    return PPOAgent(
        observation_space=gym.spaces.Box(-1.0, 1.0, (OBS_DIM,), np.float32),
        action_space=gym.spaces.Discrete(N_ACTS),
        num_envs=ENVS,
        device="cpu",
        lr=BASE_LR,
        gamma=1.0,
        gae_lambda=0.95,
        rollout_steps=ROLL,
        epochs=1,
        minibatches=1,
        clip_eps=0.2,
        entropy_coef=0.01,
        value_coef=0.5,
        max_grad_norm=0.5,
        hidden_sizes=[512, 512],
        lr_anneal_steps=anneal_steps,
        trunk="entity_deepsets",
        trunk_kwargs=dict(TRUNK_KWARGS),
        aux_oppact_coef=0.1,
        aux_scorer_sizes=[96],
        aux_head_gain=0.01,
    )


def _row():
    """One batched transition as the vector loop hands it over, WITH the D25
    opp_choice seam. flags=1 marks a real, non-aliased decision; kind=1 with
    ident=0 canonicalises to OTHER_MOVE, which is always legal, so the rows are
    VALID and the aux loss is live rather than a masked-out zero."""
    obs = np.zeros((ENVS, OBS_DIM), dtype=np.float32)
    masks = np.ones((ENVS, N_ACTS), dtype=bool)
    return (
        obs,
        np.zeros(ENVS, dtype=np.int64),
        np.zeros(ENVS, dtype=np.float32),
        obs.copy(),
        np.zeros(ENVS, dtype=bool),
        np.zeros(ENVS, dtype=bool),
        masks,
        masks.copy(),
        None,                                            # privs
        None,                                            # next_privs
        np.tile(np.array([1, 0, 1], np.int32), (ENVS, 1)),   # opp_choice
    )


def _lr_after_fill(agent: PPOAgent, updates: int) -> list[float]:
    """Pin the counter, drive one full rollout, read back every group's lr."""
    agent.updates = updates
    for _ in range(agent.buffer.horizon):
        agent.update(_row())
    return [g["lr"] for g in agent.optimizer.param_groups]


def _expected(u_pre: int) -> float:
    return BASE_LR * max(0.0, 1.0 - u_pre * STEPS_PER_UPDATE / ANNEAL)


@_needs_flags
def test_third_group_exists_and_is_exactly_the_aux_head():
    """(a) Three groups, and group 2 is the aux head's params BY ID.

    Ordering is load-bearing: the anneal writes groups by index, and D25's
    header records that appending aux params to group 0 would silently hand
    them the critic's Adam moments.
    """
    agent = _agent(ANNEAL)
    groups = agent.optimizer.param_groups
    assert len(groups) == 3, f"expected [actor, critic, aux], got {len(groups)}"
    assert {id(p) for p in groups[2]["params"]} == {
        id(p) for p in agent.aux_head.parameters()
    }


@_needs_flags
@pytest.mark.parametrize("u_pre", [0, 5859, 11718, 11719])
def test_all_three_groups_follow_the_schedule(u_pre):
    """(b) All three groups anneal together, through a real update.

    u = 11718 is NOT the clamped case (frac = 6.4e-5 > 0); 11719 is the first
    clamped counter. Both boundaries are asserted rather than assumed.
    """
    lrs = _lr_after_fill(_agent(ANNEAL), u_pre)
    want = _expected(u_pre)
    for i, lr in enumerate(lrs):
        assert lr == pytest.approx(want, rel=1e-12, abs=1e-18), (
            f"group {i} lr {lr!r} != {want!r} at pre-increment u={u_pre}"
        )
    if u_pre == 11718:
        assert want > 0.0, "u=11718 must still be strictly positive"
    if u_pre == 11719:
        assert want == 0.0, "u=11719 is the first clamped counter"


@_needs_flags
def test_actor_critic_and_aux_share_one_lr_at_default_scale():
    """(c) At actor_lr_scale 1.0 the three groups are EQUAL.

    This is what makes the anneal a PURE GLOBAL step-size schedule: the
    aux:policy gradient RATIO is untouched, so D25's coefficient 0.1 remains
    the operative coefficient throughout the run.
    """
    for u_pre in (0, 5000):
        lrs = _lr_after_fill(_agent(ANNEAL), u_pre)
        assert lrs[0] == lrs[1] == lrs[2], f"groups diverged at u={u_pre}: {lrs}"


@_needs_flags
def test_anneal_off_is_an_exact_no_op_including_the_aux_group():
    """(d) With lr_anneal_steps: 0 no group's lr is ever written.

    D25 and D25-P ran in exactly this configuration, so this is the guard that
    the newly-live code path cannot retroactively perturb the banked arms.
    """
    agent = _agent(0)
    before = [g["lr"] for g in agent.optimizer.param_groups]
    for u_pre in (0, 5000):
        assert _lr_after_fill(agent, u_pre) == before


@_needs_flags
def test_realised_schedule_pins_BOTH_counter_conventions():
    """D26's Q3 table and R0-C's assertion, with the off-by-one pinned.

    THIS TEST EXISTS BECAUSE THE TWO GATES USE THE SAME LETTER FOR DIFFERENT
    QUANTITIES, and an unlabelled mismatch would fail a correct run:

      * R0-B / this file: `u` is the PRE-increment counter, which is what
        `ppo.py:990` reads before `ppo.py:1121` does `self.updates += 1`.
        lr = base * max(0, 1 - u * 1024 / 12e6).
      * R0-C / Q3's table: `updates` is the POST-increment counter as stored in
        the CHECKPOINT, so the lr that ran is one step older:
        lr = base * max(0, 1 - (updates - 1) * 1024 / 12e6).

    Q3's row "200,000 / u=195 / 2.4586e-04" is the CHECKPOINT convention. Read
    as pre-increment it is 2.45840e-04, and a gate that mixed the two would
    reject a correct anneal. Both are asserted here against a real update.
    """
    # Asserted at the precision Q3 actually prints (5 s.f.). Earlier drafts of
    # this test invented trailing digits and failed against a CORRECT anneal —
    # the same transcription hazard the two conventions above create.
    for ckpt_updates, want in ((195, 2.4586e-04), (1953, 2.0836e-04),
                               (5859, 1.2503e-04)):
        got = _lr_after_fill(_agent(ANNEAL), ckpt_updates - 1)[0]
        assert got == pytest.approx(want, rel=1e-4), (
            f"checkpoint counter {ckpt_updates}: {got!r} != {want!r}"
        )
    # ...and the pre-increment reading of the SAME row is a different number,
    # which is the whole point: 2.45840e-04, not Q3's 2.4586e-04.
    assert _lr_after_fill(_agent(ANNEAL), 195)[0] == pytest.approx(2.45840e-04, rel=1e-5)
    assert _lr_after_fill(_agent(ANNEAL), 195)[0] != pytest.approx(2.4586e-04, rel=1e-6)


@_needs_flags
def test_r0e_smoke_acceptance_lr_is_the_100k_value():
    """R0-E's acceptance number, which the draft header had wrong.

    `step` advances by num_envs (rl/train.py), so 100k steps is 12,500
    iterations = 97 completed updates, and the lr the last one ran under comes
    from the pre-increment counter 96. The draft's 2.4586e-04 was Q3's 200,000
    row and would have FAILED A CORRECT RUN.
    """
    smoke_updates = (100_000 // ENVS) // ROLL
    assert smoke_updates == 97
    assert _lr_after_fill(_agent(ANNEAL), smoke_updates - 1)[0] == pytest.approx(
        2.479520e-04, rel=1e-6
    )
