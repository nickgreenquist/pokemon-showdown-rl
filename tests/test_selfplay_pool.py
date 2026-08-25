"""AgentOpponent + SnapshotPool probes (Phase 4 chunk 2).

The probes SESSION_LOGS_PREDECESSOR.md mandates for the frozen-opponent machinery: the snapshot's
action distribution must be bit-identical after the learner's weights move,
and no snapshot parameter may appear in the LEARNER's optimizer — asserting
against the snapshot's own optimizer passes vacuously, because deepcopy
carries one. Everything else here pins the locked pool mechanics: the 80/20
draw, second-oldest eviction, the pool_size-1 naive arm replacing rather
than retaining, freeze-at-push, and the own-generator replay contract.
"""

import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent
from rl.common.masking import masked_logits
from rl.envs.connect4 import Connect4Env
from rl.envs.make import make_env, make_vec_env
from rl.selfplay.opponents import HeuristicOpponent, RandomOpponent
from rl.selfplay.pool import AgentOpponent, SnapshotPool

HPARAMS = dict(
    lr=2.5e-4, gamma=1.0, gae_lambda=0.95, rollout_steps=8, epochs=1,
    minibatches=2, clip_eps=0.2, entropy_coef=0.01, value_coef=0.5,
    max_grad_norm=0.5, hidden_sizes=[16],
)

EMPTY_OBS = np.zeros((2, 6, 7), dtype=bool)
ALL_LEGAL = np.ones(7, dtype=bool)


def fresh_agent(seed=0):
    """A real conv-trunk PPO agent on the Connect 4 spaces — the snapshots
    must exercise the exact nets the pool will hold in training."""
    torch.manual_seed(seed)
    env = make_env("Connect4-v0", seed=0)
    agent = PPOAgent(
        env.observation_space, env.action_space, num_envs=1, device="cpu", **HPARAMS
    )
    env.close()
    return agent


def probs(actor, obs, mask):
    obs_t = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
    mask_t = torch.as_tensor(mask, dtype=torch.bool)
    with torch.no_grad():
        return torch.softmax(masked_logits(actor(obs_t), mask_t), dim=-1)


# ------------------------------------------------------------ AgentOpponent

def test_snapshot_shares_no_storage_with_the_learner():
    """The deepcopy-at-construction contract. state_dict() aliases the live
    training tensors (probe-confirmed, SESSION_LOGS_PREDECESSOR.md), so storage identity is the
    thing to assert, not value equality."""
    agent = fresh_agent()
    pool = SnapshotPool(4, 0.8)
    pool.push(agent)
    member = pool.members[0]
    member_params = list(member.agent.actor.parameters()) + list(
        member.agent.critic.parameters()
    )
    assert member_params
    learner_ptrs = {p.data_ptr() for p in agent.params}
    assert all(p.data_ptr() not in learner_ptrs for p in member_params)
    # No snapshot parameter in the LEARNER's optimizer.
    optimizer_ids = {
        id(p) for group in agent.optimizer.param_groups for p in group["params"]
    }
    assert all(id(p) not in optimizer_ids for p in member_params)


def test_snapshot_distribution_is_bit_identical_after_the_learner_moves():
    agent = fresh_agent()
    pool = SnapshotPool(4, 0.8)
    pool.push(agent)
    member = pool.members[0]
    learner_before = probs(agent.actor, EMPTY_OBS, ALL_LEGAL)
    member_before = probs(member.agent.actor, EMPTY_OBS, ALL_LEGAL)
    with torch.no_grad():
        for p in agent.params:
            p.add_(1.0)
    # The control first: the perturbation really moved the learner — without
    # this, a no-op perturbation would pass the snapshot assertion vacuously.
    assert not torch.equal(learner_before, probs(agent.actor, EMPTY_OBS, ALL_LEGAL))
    assert torch.equal(member_before, probs(member.agent.actor, EMPTY_OBS, ALL_LEGAL))


def test_push_freezes_the_snapshot_and_leaves_the_learner_trainable():
    agent = fresh_agent()
    pool = SnapshotPool(4, 0.8)
    pool.push(agent)
    member = pool.members[0]
    assert not member.agent.actor.training and not member.agent.critic.training
    assert all(not p.requires_grad for p in member.agent.actor.parameters())
    assert all(not p.requires_grad for p in member.agent.critic.parameters())
    # freeze() must have acted on the copy, never the source.
    assert all(p.requires_grad for p in agent.params)


def test_agent_opponent_samples_rather_than_argmaxes():
    """The locked choice: stochastic play on both sides, because a
    deterministic opponent collapses an eval set to a couple of distinct
    games. A near-uniform init policy sampling 200 times spans many columns;
    argmax would emit exactly one."""
    opponent = AgentOpponent(fresh_agent(), seed=0)
    opponent.freeze()
    rng = np.random.default_rng(0)
    moves = {opponent.move(EMPTY_OBS, ALL_LEGAL, rng) for _ in range(200)}
    assert len(moves) >= 3


def test_agent_opponent_respects_the_mask():
    opponent = AgentOpponent(fresh_agent(), seed=0)
    opponent.freeze()
    mask = np.zeros(7, dtype=bool)
    mask[[2, 5]] = True
    rng = np.random.default_rng(0)
    assert {opponent.move(EMPTY_OBS, mask, rng) for _ in range(100)} <= {2, 5}


def test_agent_opponent_replays_from_its_own_generator():
    """Same generator seed => the same move sequence, even with the global
    torch stream perturbed between draws — the isolation the chunk-3
    tournament needs to replay a matchup."""
    agent = fresh_agent()

    def sequence(seed):
        opponent = AgentOpponent(agent, seed=seed)
        opponent.freeze()
        rng = np.random.default_rng(0)
        out = []
        for _ in range(50):
            torch.rand(11)  # global-stream noise must not reach the opponent
            out.append(opponent.move(EMPTY_OBS, ALL_LEGAL, rng))
        return out

    assert sequence(7) == sequence(7)
    assert sequence(7) != sequence(8)


# ------------------------------------------------------------- SnapshotPool

def test_select_honors_the_80_20_split():
    """latest_prob on the newest member, uniform over the rest — and every
    historical member reachable, which is what the per-member band checks."""
    pool = SnapshotPool(8, 0.8)
    for seed in range(5):
        pool.push(fresh_agent(seed))
    rng = np.random.default_rng(0)
    counts = np.zeros(5)
    draws = 5000
    for _ in range(draws):
        counts[pool.members.index(pool.select(rng))] += 1
    fractions = counts / draws
    assert 0.78 <= fractions[-1] <= 0.82
    assert all(0.035 <= f <= 0.065 for f in fractions[:-1])


def test_pool_size_one_is_the_naive_arm_and_replaces_on_push():
    """pool_size 1 must hold the LATEST snapshot: the naive arm is a lagged
    copy of the learner, and the general evict-second-oldest rule would pin
    it to its random init forever."""
    pool = SnapshotPool(1, 0.8)
    first, second = fresh_agent(0), fresh_agent(1)
    pool.push(first)
    original = pool.members[0]
    rng = np.random.default_rng(0)
    assert pool.select(rng) is original
    pool.push(second)
    assert len(pool) == 1
    assert pool.members[0] is not original
    head = second.actor.head.weight
    assert torch.equal(pool.members[0].agent.actor.head.weight, head)


def test_member_id_reports_the_push_id_and_survives_eviction():
    """D25 §6: the manipulation check's oracle floor A3 must be evaluated on
    the member that actually generated each label — under a real pool
    (latest_prob 0.8, per-member E[H] spanning 0.17-0.43) a legitimate head
    otherwise reads a gap closure of 1.08 and trips the "g > 1.0 is a bug"
    hard fail on a correct run.

    Push ids, not list indices: an index shifts under eviction while a push id
    names the same checkpoint for the run's whole life."""
    pool = SnapshotPool(2, 0.8)
    members = []
    for seed in range(3):
        pool.push(fresh_agent(seed))
        members.append(pool.members[-1])
    assert pool.push_ids == [0, 2]  # the step-0 anchor is never evicted
    assert pool.member_id(members[0]) == 0
    assert pool.member_id(members[2]) == 2
    # Not a member: evicted mid-episode, or a fixed anchor. Never a fake id.
    assert pool.member_id(members[1]) == -1
    assert pool.member_id(RandomOpponent()) == -1


def test_eviction_is_span_preserving_and_keeps_the_anchor():
    """Span-preserving thinning (fixed 2026-08-06): the step-0 snapshot
    anchors the pool, the newest member is never evicted at push time, and
    the retained push ids stay ~uniform over [0, latest] — a plain recency
    deque is the published-worst design (Bansal et al., SESSION_LOGS_PREDECESSOR.md). The old
    rule deleted index 1 every time, which degenerated to anchor + recency
    window ({0,3,4} here) and flushed pre-seeded pools."""
    pool = SnapshotPool(3, 0.8)
    pushed = []
    for seed in range(5):
        pool.push(fresh_agent(seed))
        pushed.append(pool.members[-1])
    # ids [0,1,2] -> push 3 evicts 1 (tie, oldest) -> push 4 evicts 3.
    assert pool.push_ids == [0, 2, 4]
    assert pool.members == [pushed[0], pushed[2], pushed[4]]
    assert len(pool) == 3 and pool.pushes == 5


def test_a_preseeded_pool_is_not_flushed_by_later_pushes():
    """Regression for the recovered predecessor bug: seed pool_size 4 with
    four diverse anchors, then push 8 more snapshots. The old index-1 rule
    left {0,9,10,11} — every seed except the anchor gone, retention a pure
    recency window. Thinning keeps the retained ids spread across the whole
    push history instead."""
    pool = SnapshotPool(4, 0.8)
    for seed in range(12):
        pool.push(fresh_agent(seed))
    assert pool.push_ids == [0, 4, 7, 11]
    assert pool.push_ids != [0, 9, 10, 11]  # the failure mode, spelled out
    # Span coverage: largest gap between retained ids stays well under the
    # recency window's 9.
    gaps = [b - a for a, b in zip(pool.push_ids, pool.push_ids[1:])]
    assert max(gaps) <= 4


def test_select_on_an_empty_pool_raises():
    with pytest.raises(IndexError, match="empty pool"):
        SnapshotPool(4, 0.8).select(np.random.default_rng(0))


def test_the_pool_itself_never_plays():
    pool = SnapshotPool(4, 0.8)
    pool.push(fresh_agent())
    with pytest.raises(TypeError, match="never plays"):
        pool.move(EMPTY_OBS, ALL_LEGAL, np.random.default_rng(0))


def test_pool_rejects_degenerate_parameters():
    with pytest.raises(ValueError, match="pool_size"):
        SnapshotPool(0, 0.8)
    with pytest.raises(ValueError, match="latest_prob"):
        SnapshotPool(4, 1.5)
    with pytest.raises(ValueError, match="pfsp_power"):
        SnapshotPool(4, 0.8, pfsp_power=-1.0)
    with pytest.raises(ValueError, match="fixed_mix"):
        SnapshotPool(4, 0.8, fixed_mix=1.5)


# ------------------------------------------------- probe levers (chunk 4)

def test_defaults_consume_the_pre_lever_rng_stream():
    """The one-key-diff contract extends to the seeded stream: at
    pfsp_power 0 and fixed_mix 0 every select() must draw from the env's
    rng EXACTLY as the pre-lever pool did, or every existing seeded pool
    run changes under the new code. This deliberately asserts exact stream
    consumption — the thing the C5 control says tests must not do for
    DISTRIBUTIONAL properties — because here the stream itself is the
    documented compatibility contract, not an implementation detail."""
    pool = SnapshotPool(8, 0.8)
    for seed in range(5):
        pool.push(fresh_agent(seed))

    def pre_lever_select(rng):
        if rng.random() < pool.latest_prob:
            return pool.members[-1]
        return pool.members[int(rng.integers(len(pool.members) - 1))]

    live, twin = np.random.default_rng(3), np.random.default_rng(3)
    assert all(pool.select(live) is pre_lever_select(twin) for _ in range(300))


def test_pfsp_weights_favor_the_members_still_winning():
    """f_hard(x) = (1-x)^p over the learner's win rate x per member: a
    fully-beaten member (x=1) is never drawn, a never-beaten one (x=0)
    dominates, an unplayed one sits at the 0.5 prior. With p=2 the
    weights are (0, 1, 0.25) -> fractions (0, 0.8, 0.2)."""
    pool = SnapshotPool(8, 0.0, pfsp_power=2.0)  # latest_prob 0: all draws historical
    for seed in range(4):
        pool.push(fresh_agent(seed))
    beaten, unbeaten, unplayed = pool.members[0], pool.members[1], pool.members[2]
    for _ in range(10):
        pool.report(beaten, 1)     # learner always wins  -> x = 1
        pool.report(unbeaten, -1)  # learner always loses -> x = 0
    pool.refresh()
    rng = np.random.default_rng(0)
    counts = {id(m): 0 for m in pool.members}
    for _ in range(5000):
        counts[id(pool.select(rng))] += 1
    assert counts[id(beaten)] == 0
    assert 0.77 <= counts[id(unbeaten)] / 5000 <= 0.83
    assert 0.17 <= counts[id(unplayed)] / 5000 <= 0.23


def test_pfsp_all_beaten_falls_back_to_uniform():
    """Every historical member at x=1 collapses every weight to 0; the
    draw must fall back to uniform rather than divide by zero."""
    pool = SnapshotPool(8, 0.0, pfsp_power=2.0)
    for seed in range(4):
        pool.push(fresh_agent(seed))
    for member in pool.members[:-1]:
        for _ in range(5):
            pool.report(member, 1)
    pool.refresh()
    rng = np.random.default_rng(0)
    counts = {id(m): 0 for m in pool.members[:-1]}
    for _ in range(3000):
        counts[id(pool.select(rng))] += 1
    assert all(0.28 <= c / 3000 <= 0.39 for c in counts.values())


def test_pfsp_weights_are_fixed_until_the_next_refresh():
    """The rollout-boundary invariant: counts reported after a refresh()
    must not move the draw until the NEXT refresh — within a rollout the
    opponent distribution is fixed, which is what PPO's importance ratios
    require (the same invariant that pins the push cadence)."""
    pool = SnapshotPool(8, 0.0, pfsp_power=2.0)
    for seed in range(3):
        pool.push(fresh_agent(seed))
    dormant, active = pool.members[0], pool.members[1]
    for _ in range(10):
        pool.report(dormant, 1)   # x = 1 -> weight 0
        pool.report(active, -1)   # x = 0 -> weight 1
    pool.refresh()
    rng = np.random.default_rng(0)
    for _ in range(300):
        assert pool.select(rng) is active
    # New results arrive mid-rollout: the learner starts losing to the
    # dormant member. Until refresh(), the draw must not notice.
    for _ in range(30):
        pool.report(dormant, -1)
    for _ in range(300):
        assert pool.select(rng) is active
    pool.refresh()  # the next rollout boundary
    draws = sum(pool.select(rng) is dormant for _ in range(500))
    assert draws > 50


def test_fixed_mix_routes_its_fraction_to_the_anchors():
    pool = SnapshotPool(8, 0.8, fixed_mix=0.2)
    for seed in range(3):
        pool.push(fresh_agent(seed))
    rng = np.random.default_rng(0)
    picks = [pool.select(rng) for _ in range(5000)]
    fixed = [p for p in picks if isinstance(p, (RandomOpponent, HeuristicOpponent))]
    assert 0.17 <= len(fixed) / 5000 <= 0.23
    randoms = sum(isinstance(p, RandomOpponent) for p in fixed)
    assert 0.35 <= randoms / len(fixed) <= 0.65  # 50/50 between the two anchors


def test_report_ignores_opponents_that_are_not_members():
    pool = SnapshotPool(4, 0.8)
    pool.push(fresh_agent())
    pool.report(RandomOpponent(), 1)
    pool.report(HeuristicOpponent(), -1)
    assert pool.stats == [[0.0, 0]]


def test_env_reports_every_terminal_outcome_to_the_pool():
    """The feedback channel end-to-end: after N completed episodes the
    pool's counts must total N games, and the score sum must equal the sum
    of (outcome+1)/2 over the outcomes the env itself emitted — a flipped
    sign or a dropped report() call cannot balance that ledger."""
    pool = SnapshotPool(4, 0.8)
    pool.push(fresh_agent(0))
    pool.push(fresh_agent(1))
    env = Connect4Env(opponent=pool)
    rng = np.random.default_rng(0)
    outcomes = []
    for episode in range(12):
        obs, info = env.reset(seed=episode)
        done = False
        while not done:
            legal = np.flatnonzero(info["action_mask"])
            obs, _, done, _, info = env.step(int(rng.choice(legal)))
        outcomes.append(info["outcome"])
    assert sum(stat[1] for stat in pool.stats) == len(outcomes)
    expected = sum((o + 1) / 2 for o in outcomes)
    assert sum(stat[0] for stat in pool.stats) == pytest.approx(expected)
    assert expected != len(outcomes) / 2  # the ledger must be sign-sensitive


def test_pool_with_levers_plays_full_games_through_the_env():
    """Both levers on at once, driven through the real env: fixed-mix
    episodes hand the board to a rule-based anchor whose fallback draws
    from the env stream, PFSP draws consult the snapshot weights — and
    every episode must still complete with a legal game and an outcome."""
    pool = SnapshotPool(4, 0.5, pfsp_power=2.0, fixed_mix=0.3)
    pool.push(fresh_agent(0))
    pool.push(fresh_agent(1))
    pool.refresh()
    env = Connect4Env(opponent=pool)
    rng = np.random.default_rng(0)
    for episode in range(15):
        obs, info = env.reset(seed=episode)
        done = False
        while not done:
            legal = np.flatnonzero(info["action_mask"])
            obs, _, done, _, info = env.step(int(rng.choice(legal)))
        assert info["outcome"] in (-1, 0, 1)


# ------------------------------------------------------- through the env

def test_one_pool_is_shared_by_every_sub_env_and_pushes_are_visible():
    """The env_kwargs seam end-to-end with the real pool object: caller
    kwargs preserve identity across sub-envs, so a push lands in all of
    them at once."""
    pool = SnapshotPool(4, 0.8)
    pool.push(fresh_agent())
    vec = make_vec_env("Connect4-v0", 0, 3, env_kwargs={"opponent": pool})
    assert all(env.unwrapped.opponent_source is pool for env in vec.envs)
    vec.reset(seed=0)
    pool.push(fresh_agent(1))
    assert all(len(env.unwrapped.opponent_source) == 2 for env in vec.envs)
    vec.close()


def test_pool_members_play_full_games_through_the_env():
    """The env raises on any illegal opponent column, so completing episodes
    is most of the assertion; the rest is that terminals carry an outcome."""
    pool = SnapshotPool(4, 0.8)
    pool.push(fresh_agent(0))
    pool.push(fresh_agent(1))
    env = Connect4Env(opponent=pool)
    rng = np.random.default_rng(0)
    for episode in range(10):
        obs, info = env.reset(seed=episode)
        done = False
        while not done:
            legal = np.flatnonzero(info["action_mask"])
            obs, _, done, _, info = env.step(int(rng.choice(legal)))
        assert info["outcome"] in (-1, 0, 1)


def test_installing_an_empty_pool_is_fine_but_resetting_is_not():
    """Construction must work with an empty pool (train() builds the env
    before the agent exists), and the first reset without a push must fail
    loudly — this is the IndexError the pre-loop push exists to prevent."""
    env = Connect4Env(opponent=SnapshotPool(4, 0.8))  # install-time freeze() no-op
    with pytest.raises(IndexError, match="empty pool"):
        env.reset(seed=0)
