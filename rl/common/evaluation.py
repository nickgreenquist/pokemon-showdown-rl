"""Eval protocol: fixed seeds, N episodes, deterministic policy, mean ± std.

Runs on a dedicated env passed in by the caller, so eval never disturbs the
training env's RNG or episode state. Episode i always resets with the same
constant seed — independent of the training seed — so scores are comparable
across passes, across training seeds (the multi-seed benchmark protocol),
and across algorithms.
"""

import gymnasium as gym
import numpy as np

from rl.agents.base import Agent

# Fixed base for eval episode seeds; large so they stay disjoint from
# plausible training seeds.
EVAL_SEED_OFFSET = 10_000


def _run_eval_episodes(
    agent: Agent, env: gym.Env, episodes: int, seed_start: int = 0, max_steps: int = 10_000
) -> tuple[list[float], list[int | None], list[tuple[int, int] | None]]:
    """The protocol itself, returning per-episode (returns, outcomes, faints).

    `outcomes` is the env's own `info["outcome"]` at the terminal step, or
    None where the env supplies none (every env before Phase 4) or where the
    episode hit `max_steps`. `faints` is `info["faints"]` under the same
    rule — Showdown-only, None everywhere else. Private so that
    `eval_returns` keeps its exact public signature and return type for the
    analysis scripts.
    """
    returns: list[float] = []
    outcomes: list[int | None] = []
    faints: list[tuple[int, int] | None] = []
    for episode in range(episodes):
        obs, info = env.reset(seed=EVAL_SEED_OFFSET + seed_start + episode)
        mask = info.get("action_mask")  # masking applies at eval time too
        ep_return, done, steps = 0.0, False, 0
        while not done and steps < max_steps:
            obs, reward, terminated, truncated, info = env.step(
                agent.act(obs, mask, deterministic=True)
            )
            mask = info.get("action_mask")
            ep_return += float(reward)
            steps += 1
            done = terminated or truncated
        returns.append(ep_return)
        outcomes.append(info.get("outcome") if done else None)
        faints.append(info.get("faints") if done else None)
    return returns, outcomes, faints


def eval_returns(
    agent: Agent, env: gym.Env, episodes: int, seed_start: int = 0, max_steps: int = 10_000
) -> list[float]:
    """The protocol itself, returning per-episode returns. Analysis scripts
    use the raw list: identical episode seeds across runs make per-episode
    scores directly comparable (paired comparisons between variants).
    `seed_start` shifts the ladder (episode i seeds with
    EVAL_SEED_OFFSET + seed_start + i) so a re-eval can use episodes
    disjoint from the ones training-time eval selected checkpoints on.
    Caveat: MinAtar's sticky-action carry (`last_action`) survives reset,
    so ~1% of episodes are weakly order/policy dependent — negligible on
    means; pairing across runs is approximate, not exact.
    `max_steps` caps a single episode: MinAtar registers no time limit,
    and a strong Seaquest policy can survive indefinitely under greedy
    eval (oxygen is renewable), hanging the protocol — observed in the
    lr-5e-4 diagnostic runs. The cap is ~50x a normal MinAtar episode, so
    it binds only on effectively-immortal policies; the return
    accumulated at the cap is recorded."""
    return _run_eval_episodes(agent, env, episodes, seed_start, max_steps)[0]


def evaluate(
    agent: Agent, env: gym.Env, episodes: int, win_rate: bool = False
) -> dict[str, float]:
    """Mean/std of the eval return, plus `eval/win_rate` when asked for.

    The win rate is the fraction of episodes with `info["outcome"] == 1`,
    read from the ENV. It is deliberately not `return > 0`, which is the
    obvious implementation and is unsafe: the return is computed from the
    very reward a sign bug inverts, so a flipped reward makes that form
    report a win rate of 1.000 and sail through its own detector at the
    ceiling — measured on real training runs, where the "near 0%" signature
    the spec had predicted instead showed up on a policy genuinely winning
    81.3% of its games. Reading an env-supplied outcome breaks that
    circularity: no arithmetic on the reward stream can forge it.

    Draws count as neither wins nor losses, so win_rate + loss_rate need not
    sum to 1.
    """
    returns, outcomes, faints = _run_eval_episodes(agent, env, episodes)
    metrics = {
        "eval/return_mean": float(np.mean(returns)),
        "eval/return_std": float(np.std(returns)),
    }
    # Arm B's pre-registered SECONDARY (DESIGN.md §5), emitted only where the
    # env supplies faint counts — i.e. Showdown, and never on the spine envs.
    # Conditioned on LOSSES because the unconditional differential is
    # mechanically determined by the outcome: a win means they lost more mons
    # than you almost by definition, so the unconditional number measures the
    # win rate a second time. Restricted to decided losses; ties carry no
    # "did the shaping teach trading" signal either way.
    lost = [f for f, o in zip(faints, outcomes) if o == -1 and f is not None]
    if lost:
        differential = [theirs - ours for ours, theirs in lost]
        metrics["eval/loss_faint_diff"] = float(np.mean(differential))
        metrics["eval/loss_faint_lead_frac"] = float(np.mean([d > 0 for d in differential]))
    if win_rate:
        missing = sum(outcome is None for outcome in outcomes)
        if missing:
            # Silently scoring these as non-wins would report a plausible,
            # wrong number — the failure mode this metric exists to avoid.
            raise ValueError(
                f"eval_win_rate is on but {missing}/{len(outcomes)} eval episodes "
                f'supplied no info["outcome"]'
            )
        metrics["eval/win_rate"] = float(np.mean([outcome == 1 for outcome in outcomes]))
    return metrics
