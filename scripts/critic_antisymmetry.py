#!/usr/bin/env python
"""Is the critic ANTISYMMETRIC? The decisive test §27.1 could not run.

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/critic_antisymmetry.py --battles 300

RESULTS §27.1 measured the critic reading **+0.0416 optimistic (z 2.74)** against
the rollout oracle, and named TWO causes it could not separate:

  (a) a SEAT BIAS -- the collector runs `learner_seat: p1`, so the critic has
      only ever been fit from one side of a symmetric game;
  (b) the DETERMINIZATION SAMPLER -- the oracle is E[outcome | obs] under the
      sampler's belief about the hidden team, while the critic was fit against
      real outcomes, so a sampler drawing opponents stronger than the true
      posterior makes the critic read optimistic WITHOUT BEING WRONG.

THIS SEPARATES THEM, AND IT USES NO ROLLOUTS AT ALL. Gen 1 is zero-sum, so for
any position s:

        V(s)  +  V(swap(s))  ==  0        for a calibrated critic

Both terms come from the SAME determinization and the SAME encoder; no outcome,
no oracle, no sampler enters. **A non-zero sum is therefore a property of the
critic alone** -- "whoever I am looking at is doing well" -- and it is exactly
what a seat bias is. If the measured asymmetry is ~2x §27.1's +0.0416, (a)
explains that finding and (b) is exonerated. If it is ~0, the +0.0416 is NOT a
perspective bias and the sampler is the live suspect.

WHY IT IS CHEAP: two critic forwards per determinization and no rollouts, so the
cost is position collection and nothing else -- minutes rather than the hour
§27 took.

WHAT IT CANNOT SAY. It measures the critic's SELF-CONSISTENCY, not its accuracy.
A critic can be perfectly antisymmetric and badly wrong, and §27.1's ranking gap
(88% of the distance to the ceiling) is untouched by this either way.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).parent))
REPO = Path(__file__).resolve().parents[1]
BUCKETS = ((2, 8), (9, 15), (16, 22), (23, 10**9))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoints", nargs="+", default=[
        "runs/showdown_monster200m_w_s104/ckpt_200000000.pt",
        "runs/showdown_monster200m_w_s112/ckpt_200000012.pt",
        "runs/showdown_monster200m_w_s120/ckpt_200000003.pt"])
    ap.add_argument("--battles", type=int, default=300)
    ap.add_argument("--dets", type=int, default=4)
    ap.add_argument("--max-stop", type=int, default=36)
    ap.add_argument("--seed", type=int, default=20260919)
    ap.add_argument("--out", default="results/outcome_variance/antisymmetry.json")
    args = ap.parse_args()

    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    import torch
    from poke_env.data import GenData

    from eval_checkpoint import _load_showdown_agent, _opponent_from_checkpoint
    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config
    from rl.common.evaluation import EVAL_SEED_OFFSET
    from rl.envs.make import make_env
    from rl.envs.showdown import embed_battle
    from rl.search.bridge import BridgeCounters, battle_to_state
    from rl.search.determinize import sample_determinization
    from rl.search.ensemble import EnsembleAgent
    from rl.search.shadow_battle import shadow_battle

    ov = __import__("outcome_variance")          # reuse its _swap, tested

    type_chart = GenData.from_format("gen1randombattle").type_chart
    members = []
    for p in args.checkpoints:
        c = load_checkpoint(p)
        members.append(_load_showdown_agent(c, Config(**c["config"])))
    agent = EnsembleAgent(members) if len(members) > 1 else members[0]
    print(f"object: committee of {len(members)}", flush=True)

    c0 = load_checkpoint(args.checkpoints[0])
    cfg0 = Config(**c0["config"])
    opponent, _ = _opponent_from_checkpoint(args.checkpoints[0], cfg0.seed)
    env = make_env(cfg0.env_id, cfg0.seed, env_kwargs={"opponent": opponent})
    counters = BridgeCounters()

    def value(state, turn):
        obs = embed_battle(shadow_battle(state, turn), type_chart)
        t = torch.as_tensor(np.asarray(obs, dtype=np.float32)[None])
        with torch.no_grad():
            return float(np.mean([float(m.critic(t).reshape(-1)[0]) for m in members]))

    rows = []
    for ep in range(args.battles):
        rng = np.random.default_rng([args.seed, ep])
        obs, info = env.reset(seed=EVAL_SEED_OFFSET + 90000 + ep)
        mask = info.get("action_mask")
        stop_at = int(rng.integers(2, max(args.max_stop, 3)))
        done, step = False, 0
        while not done and step < 500:
            inner = getattr(getattr(env.unwrapped, "_env", None), "env", None)
            battle = getattr(inner, "battle1", None) if inner is not None else None
            if step >= stop_at and battle is not None and not battle.finished:
                turn = int(battle.turn)
                try:
                    states = [battle_to_state(battle, sample_determinization(battle, rng),
                                              counters) for _ in range(args.dets)]
                except (KeyboardInterrupt, SystemExit):
                    raise
                except BaseException:
                    break
                for st in states:
                    try:
                        vu, vt = value(st, turn), value(ov._swap(st), turn)
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except BaseException:
                        continue
                    rows.append({"ep": ep, "turn": turn, "v_us": vu, "v_them": vt,
                                 "sum": vu + vt})
                break
            obs, _, term, trunc, info = env.step(agent.act(obs, mask, deterministic=True))
            mask, done, step = info.get("action_mask"), term or trunc, step + 1
        if (ep + 1) % 50 == 0:
            print(f"  {ep + 1}/{args.battles} battles, {len(rows)} evaluations", flush=True)
    env.close()
    if not rows:
        print("no positions"); return

    s = np.array([r["sum"] for r in rows])
    t = np.array([r["turn"] for r in rows])
    # cluster by POSITION: the `dets` evaluations of one position are not
    # independent draws, and treating them as such would shrink the se by 2x.
    by_ep: dict[int, list[float]] = {}
    for r in rows:
        by_ep.setdefault(r["ep"], []).append(r["sum"])
    clustered = np.array([np.mean(v) for v in by_ep.values()])
    mean = float(clustered.mean())
    se = float(clustered.std(ddof=1) / math.sqrt(clustered.size))

    print("\n" + "=" * 78)
    print("IS THE CRITIC ANTISYMMETRIC?   V(s) + V(swap(s)) must be 0 in a zero-sum game")
    print("=" * 78)
    print(f"\n  {len(rows)} evaluations over {len(by_ep)} positions "
          f"({args.dets} determinizations each)")
    print(f"  mean V(s) + V(swap(s))      {mean:+.4f}   se {se:.4f}  "
          f"z {mean / se if se else float('nan'):.2f}   (position-clustered)")
    print(f"  implied PER-SIDE bias       {mean / 2:+.4f}")
    print(f"  §27.1 measured against the rollout oracle:  +0.0416")
    print(f"\n  {'turns':>8} {'evals':>6} {'mean sum':>10} {'per-side':>10}")
    for lo, hi in BUCKETS:
        sel = (t >= lo) & (t <= hi)
        if sel.sum() < 10:
            continue
        print(f"  {f'{lo}-' + ('+' if hi > 999 else str(hi)):>8} {int(sel.sum()):>6} "
              f"{s[sel].mean():>+10.4f} {s[sel].mean() / 2:>+10.4f}")

    print("\n  HOW TO READ IT:")
    print("   * per-side bias ~ +0.042  -> §27.1 IS a perspective/seat bias, the")
    print("     sampler is exonerated, and IDEAS 4.1 gets its measured defect.")
    print("   * per-side bias ~ 0       -> the critic is self-consistent, so the")
    print("     +0.0416 is NOT a perspective bias and the DETERMINIZATION SAMPLER")
    print("     is the live suspect (audit rl/search/determinize.py).")
    print("   * anything between        -> both contribute; report the split.")
    print("\n  It measures SELF-CONSISTENCY, never accuracy. §27.1's ranking gap")
    print("  (88% of the distance to the ceiling) is untouched either way.")
    print("=" * 78)

    out = {"evaluations": len(rows), "positions": len(by_ep), "dets": args.dets,
           "mean_sum": mean, "se_clustered": se, "per_side_bias": mean / 2,
           "rows": rows[:2000]}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
