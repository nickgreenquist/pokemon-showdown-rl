"""R0-2(b) of configs/showdown_sp_signal12m.yaml — the LIVE half of the
shaping-correctness gate.

    python scripts/hl_shaping_live_smoke.py --battles 10

Needs the local Showdown server on :8000. Seed 29 is the pre-registered
smoke seed; do not reuse a training lane's seed while lanes are live (the
username landmine).

WHAT IT ASSERTS, per battle, with hl_shaping on and a random policy:

  1. RETURN IDENTITY (seat 1): the wrapper-summed episode return equals
     outcome + in-process shaping sum to <= 1e-9 — the wait pump neither
     dropped nor double-paid an event.
  2. TWO-SEAT ZERO-SUM, IN-PROCESS: poke-env scores BOTH seats' battles
     every step (SingleAgentWrapper merely discards seat 2's number), so a
     spy on calc_reward captures the real seat-2 shaping stream. The two
     accumulated sums must cancel to EXACTLY 0.0. A nonzero residual means
     the two seats consumed different events or batched them differently
     across steps — either is a finding to understand BEFORE training on
     this signal (K3: a farmable shaping voids the arm).
  3. CURSOR COMPLETENESS: each seat's accumulated sum equals a fresh
     full-log recompute over its battle's _replay_data to <= 1e-12.

Also prints the per-term event counts (the first live S1 numbers) and the
per-battle shaping magnitudes.
"""

import argparse
import sys
from collections import defaultdict

import numpy as np

from rl.envs.make import make_env
from rl.envs.showdown import _HL_WEIGHTS, battle_outcome, hl_event_sum


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--battles", type=int, default=10)
    parser.add_argument("--seed", type=int, default=29)
    parser.add_argument("--hl-shaping", type=float, default=1.0)
    args = parser.parse_args()

    env = make_env(
        "Showdown-v0",
        seed=args.seed,
        env_kwargs={"opponent": "random", "hl_shaping": args.hl_shaping},
    )
    singles = env.unwrapped._env.env  # the two-seat ShowdownSingles
    assert singles.hl_shaping == args.hl_shaping

    shaping_sum: dict[object, float] = defaultdict(float)
    orig_calc_reward = singles.calc_reward

    def spy(battle):
        reward = orig_calc_reward(battle)
        outcome = 1.0 if battle.won else -1.0 if battle.lost else 0.0
        shaping_sum[battle] += reward - outcome
        return reward

    singles.calc_reward = spy

    rng = np.random.default_rng(args.seed)
    term_counts = dict.fromkeys(_HL_WEIGHTS, 0)
    magnitudes = []
    failures = []
    for ep in range(args.battles):
        obs, info = env.reset()
        terminated = truncated = False
        ret = 0.0
        while not (terminated or truncated):
            action = int(rng.choice(np.flatnonzero(info["action_mask"])))
            obs, reward, terminated, truncated, info = env.step(action)
            ret += float(reward)
        b1, b2 = singles.battle1, singles.battle2
        s1, s2 = shaping_sum[b1], shaping_sum[b2]
        out1 = float(battle_outcome(b1))
        r1 = args.hl_shaping * hl_event_sum(b1._replay_data, b1.player_role)
        r2 = args.hl_shaping * hl_event_sum(b2._replay_data, b2.player_role)
        checks = [
            ("return-identity", abs(ret - out1 - s1), 1e-9),
            ("two-seat-zero-sum", abs(s1 + s2), 0.0),
            ("cursor-complete-s1", abs(s1 - r1), 1e-12),
            ("cursor-complete-s2", abs(s2 - r2), 1e-12),
        ]
        for name, residual, tol in checks:
            if residual > tol:
                failures.append((ep, name, residual))
        magnitudes.append(s1)
        for entry in b1._replay_data:
            if len(entry) >= 3 and entry[1] in term_counts:
                term_counts[entry[1]] += 1
        print(f"battle {ep}: outcome {out1:+.0f}  shaping s1 {s1:+.6f}  s1+s2 {s1 + s2:+.2e}")
    env.close()

    print("=" * 66)
    print(f"battles checked     : {args.battles}")
    print(f"term counts (seat 1): {term_counts}")
    print(f"|shaping| per battle: min {min(map(abs, magnitudes)):.4f} "
          f"median {sorted(map(abs, magnitudes))[len(magnitudes) // 2]:.4f} "
          f"max {max(map(abs, magnitudes)):.4f}")
    if not any(magnitudes):
        failures.append(("all", "shaping-never-fired", 0.0))
    print("=" * 66)
    if failures:
        for ep, name, residual in failures:
            print(f"FAIL battle {ep}: {name} residual {residual:.3e}")
        print("R0-2(b): FAIL — K3 territory; do not launch on this signal")
        sys.exit(1)
    print("R0-2(b): PASS — zero-sum exact in-process, cursor complete, "
          "return identity holds")


if __name__ == "__main__":
    main()
