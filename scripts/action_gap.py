#!/usr/bin/env python
"""HOW MUCH IS THERE FOR SEARCH TO WIN? The prize, measured.

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/action_gap.py --battles 150 --rollouts 24

Four search constructions have now read null or negative on this object -- the
one-ply matrix (§22), Foul Play's own evaluator inside it (§23), an honest
minimax second ply (§30), and a real decoupled-UCT tree (§26) -- across many
override rates, two evaluators, two backups and a selection gate (§30). Every one
of those is a NULL, and CLAUDE.md rule 6 is explicit that a null kills nothing:
only a MEASURED MECHANISM CEILING does.

THIS MEASURES THE CEILING. Search over a decision can only ever improve on the
policy by swapping its argmax for a better legal action. So the entire prize is

    P(the policy's top-1 is worse than its top-2) x E[ |Q(a1) - Q(a2)| ]

and both factors are measurable by rollout, with no evaluator and no search
involved. Q is estimated the way §27 estimated the luck ceiling: the SAME
deterministic committee on both seats, `dets` determinizations x `rollouts` each,
so what is measured is the true expected outcome of taking that action here.

WHAT IT DECIDES.
  * If the gap is SMALL relative to the critic's error, no evaluator can rank
    the two actions reliably and search cannot pay AT ANY BUDGET -- a ceiling,
    not a null, and the first thing in this project licensed to close the axis.
  * If the gap is LARGE and the policy is often wrong, the prize is real and the
    four nulls are about our constructions rather than about search.

THE BOUND IS OVER THE TOP TWO ONLY, and that is deliberate: it is what a gated
search actually does (§24/§30 measure override rates of 6-19%, i.e. swapping the
argmax for the runner-up). A search ranging over all legal actions could win
more, so this is a bound on the GATED form and a lower bound on the general one.
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoints", nargs="+", default=[
        "runs/showdown_monster200m_w_s104/ckpt_200000000.pt",
        "runs/showdown_monster200m_w_s112/ckpt_200000012.pt",
        "runs/showdown_monster200m_w_s120/ckpt_200000003.pt"])
    ap.add_argument("--battles", type=int, default=150)
    ap.add_argument("--dets", type=int, default=2)
    ap.add_argument("--rollouts", type=int, default=24,
                    help="per determinization PER ACTION; the gap is a "
                         "difference of two means, so it needs more than §27 did")
    ap.add_argument("--max-stop", type=int, default=36)
    ap.add_argument("--seed", type=int, default=20260919)
    ap.add_argument("--out", default="results/outcome_variance/action_gap.json")
    ap.add_argument("--rows", default="results/outcome_variance/action_gap.rows.jsonl")
    args = ap.parse_args()

    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    import torch
    from poke_engine import generate_instructions
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
    from rl.search.matrix import our_action_str
    from rl.search.shadow_battle import shadow_battle

    ov = __import__("outcome_variance")       # _swap, rollout, _shadow_mask: tested

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

    def top2(sb):
        """The committee's top two LEGAL actions at a shadow battle."""
        mask = ov._shadow_mask(sb)
        if mask.sum() < 2:
            return None
        obs = embed_battle(sb, type_chart)
        t = torch.as_tensor(np.asarray(obs, dtype=np.float32)[None])
        with torch.no_grad():
            lp = torch.stack([
                torch.log_softmax(m.actor(t)[0], dim=-1) for m in members]).mean(0).numpy()
        legal = np.flatnonzero(mask)
        order = legal[np.argsort(-lp[legal])]
        return int(order[0]), int(order[1]), obs

    def q_of(state, action, turn, rng, n):
        """True expected outcome of PLAYING `action` here, by rollout."""
        sb = shadow_battle(state, turn)
        try:
            ours = our_action_str(sb, action)
        except (IndexError, KeyError, AttributeError):
            return None
        theirs, _ = ov._choose(ov._swap(state), agent, type_chart, turn)
        if ours is None or theirs is None:
            return None
        outs = []
        for _ in range(n):
            try:
                brs = generate_instructions(state, ours, theirs)
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException:
                return None
            if not brs:
                return None
            p = np.array([b.percentage for b in brs], dtype=np.float64)
            if p.sum() <= 0:
                return None
            nxt = state.apply_instructions(brs[int(rng.choice(len(brs), p=p / p.sum()))])
            tv = ov._terminal(nxt)
            o = tv if tv is not None else ov.rollout(nxt, agent, type_chart, rng, turn + 1)
            if not np.isnan(o):
                outs.append(float(o))
        return np.array(outs) if len(outs) >= 4 else None

    rows_path = Path(args.rows)
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    rows, done = ov.load_rows(rows_path)
    if rows:
        print(f"RESUME: {len(rows)} positions already measured", flush=True)

    import time
    t0 = time.time()
    for ep in range(args.battles):
        if ep in done:
            continue
        rng = np.random.default_rng([args.seed, ep])
        obs, info = env.reset(seed=EVAL_SEED_OFFSET + 60000 + ep)
        mask = info.get("action_mask")
        stop_at = int(rng.integers(2, max(args.max_stop, 3)))
        fin, step = False, 0
        while not fin and step < 500:
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
                q1s, q2s = [], []
                for st in states:
                    tt = top2(shadow_battle(st, turn))
                    if tt is None:
                        continue
                    a1, a2, _ = tt
                    o1 = q_of(st, a1, turn, rng, args.rollouts)
                    o2 = q_of(st, a2, turn, rng, args.rollouts)
                    if o1 is None or o2 is None:
                        continue
                    q1s.append(float(o1.mean())); q2s.append(float(o2.mean()))
                if len(q1s) >= 1:
                    q1, q2 = float(np.mean(q1s)), float(np.mean(q2s))
                    row = {"ep": ep, "turn": turn, "q_top1": q1, "q_top2": q2,
                           "gap": q1 - q2, "n_det": len(q1s),
                           "rollouts": args.rollouts}
                    rows.append(row)
                    with rows_path.open("a") as f:
                        f.write(json.dumps(row) + "\n")
                    el = time.time() - t0
                    print(f"ep {ep+1}/{args.battles}: {len(rows)} rows, turn {turn}, "
                          f"q1 {q1:+.3f} q2 {q2:+.3f} gap {q1-q2:+.3f}, "
                          f"{el/max(len(rows),1):.1f} s/row", flush=True)
                break
            obs, _, term, trunc, info = env.step(agent.act(obs, mask, deterministic=True))
            mask, fin, step = info.get("action_mask"), term or trunc, step + 1
    env.close()
    if not rows:
        print("no positions"); return

    g = np.array([r["gap"] for r in rows])
    q1 = np.array([r["q_top1"] for r in rows])
    q2 = np.array([r["q_top2"] for r in rows])
    wrong = g < 0
    se_row = 1.0 / math.sqrt(args.rollouts * max(rows[0]["n_det"], 1))

    print("\n" + "=" * 80)
    print("HOW MUCH IS THERE FOR SEARCH TO WIN?")
    print("=" * 80)
    print(f"\n  {len(rows)} positions, {args.dets}x{args.rollouts} rollouts per action")
    print(f"  E[Q(top1)]                         {q1.mean():+.4f}")
    print(f"  E[Q(top2)]                         {q2.mean():+.4f}")
    print(f"  E[gap] = E[Q(top1) - Q(top2)]      {g.mean():+.4f}")
    print(f"  E|gap|                             {np.abs(g).mean():.4f}")
    print(f"  the policy's top-1 is WORSE in     {wrong.mean():.1%} of positions")
    print(f"  E[-gap | top-1 worse]              {(-g[wrong]).mean() if wrong.any() else 0:.4f}")
    print(f"\n  *** CEILING ON A TOP-2 SWAP: "
          f"{(wrong.mean() * ((-g[wrong]).mean() if wrong.any() else 0)) / 2:.4f} "
          f"of win rate ***")
    print("  (a win-rate point is half an outcome point on the -1..+1 scale)")
    print(f"\n  per-position rollout noise on the gap ~ {se_row * math.sqrt(2):.4f},")
    print(f"  so a gap smaller than that is not resolvable HERE either.")
    print("\n  READ: compare the ceiling to the effects these blocks chase (+0.02..0.05).")
    print("  A ceiling BELOW them is a MEASURED MECHANISM CEILING and the first")
    print("  thing in this project licensed to close the search axis (rule 6).")
    print("  A ceiling ABOVE them says the prize is real and the four nulls are")
    print("  about our constructions, not about search.")
    print("\n  SCOPE: the bound is over the TOP TWO actions, which is what a gated")
    print("  search does (§24/§30 override 6-19% of decisions, i.e. argmax ->")
    print("  runner-up). A search ranging over ALL legal actions could win more.")
    print("=" * 80)

    Path(args.out).write_text(json.dumps({
        "positions": len(rows), "dets": args.dets, "rollouts": args.rollouts,
        "mean_q_top1": float(q1.mean()), "mean_q_top2": float(q2.mean()),
        "mean_gap": float(g.mean()), "mean_abs_gap": float(np.abs(g).mean()),
        "frac_top1_worse": float(wrong.mean()),
        "mean_loss_when_wrong": float((-g[wrong]).mean()) if wrong.any() else 0.0,
        "ceiling_win_rate": float(wrong.mean() * ((-g[wrong]).mean() if wrong.any() else 0)) / 2,
        "rollout_noise_on_gap": se_row * math.sqrt(2),
    }, indent=2) + "\n")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
