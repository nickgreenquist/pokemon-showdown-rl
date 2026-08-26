#!/usr/bin/env python
"""Is the critic worse in the endgame, and does it reward stalling?

MOTIVATION. The replay audit found two things move choice cannot explain:
heal loops (Recover at >=99% HP, 13/147 for us vs 0/111 for humans), and an
endgame conversion failure (an HP lead is worth 82% of the next exchange at
4v4 but only 55% at 2v2). Both are value-function shaped, so measure the value
function rather than guessing at a lever.

TWO READS, both inference-only, both on the LOCAL server so a live ladder run
is untouched:

  A. CALIBRATION BY MATERIAL. Record V(s) at every decision plus the episode's
     eventual outcome, then bucket by how many mons are left. If the critic
     degrades in the endgame, its ability to rank winning states above losing
     ones falls with material. Reported as AUC (P(V higher in a state from a
     won episode than from a lost one)), which is scale-free and therefore
     immune to the discounting that makes raw V vs +/-1 incomparable.

  B. THE STALL GRADIENT. Within a battle, regress V on our own HP fraction and
     on PROGRESS (their fainted count). If V tracks our HP but is flat in
     progress, "heal forever" looks good to the critic and the loops follow.
"""
import argparse, os, sys, json, collections, statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def auc(pos, neg):
    """P(a random pos scores above a random neg); 0.5 = no signal."""
    if not pos or not neg:
        return None
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n: wins += 1
            elif p == n: ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", default="configs/eval/ladder_r1.yaml")
    ap.add_argument("--lane", default="s62")
    ap.add_argument("--battles", type=int, default=40)
    ap.add_argument("--seed", type=int, default=777,
                    help="must not collide with a live lane (username derivation)")
    ap.add_argument("--opponent", default="heuristics",
                    help="'heuristics' (SH-like) or a checkpoint path. The "
                         "SH-like default is the whole caveat on the first "
                         "run of this probe: a critic well calibrated on "
                         "SH-like play and miscalibrated on human play would "
                         "look identical. A checkpoint opponent samples (pool "
                         "contract) -- fine for measuring OUR calibration, "
                         "NOT fine for rating that opponent (the A1 lesson).")
    ap.add_argument("--out", default="results/diag/value_head.json")
    args = ap.parse_args()
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")

    import numpy as np, torch, yaml
    from rl.common.seeding import set_seed
    from rl.common.masking import masked_logits
    from rl.envs.make import make_env
    import rl.envs.showdown as sd
    from eval_checkpoint import _load_showdown_agent
    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config

    set_seed(args.seed); torch.set_num_threads(1)
    prereg = yaml.safe_load(open(args.prereg))
    ck = load_checkpoint(prereg["checkpoints"][args.lane]["path"])
    cfg = Config(**ck["config"])
    agent = _load_showdown_agent(ck, cfg)
    print(f"lane {args.lane}  gamma={getattr(cfg,'gamma',None)}  "
          f"gae_lambda={getattr(cfg,'gae_lambda',None)}")

    if args.opponent.endswith(".pt"):
        from eval_checkpoint import _opponent_from_checkpoint
        opp = _opponent_from_checkpoint(args.opponent, args.seed)
        print(f"opponent: checkpoint {args.opponent} (SAMPLING, pool contract)")
    else:
        opp = args.opponent
        print(f"opponent: {opp}")
    env = make_env("Showdown-v0", args.seed, env_kwargs={"opponent": opp})
    recs = []
    for b in range(args.battles):
        obs, info = env.reset(); done = False; ep = []
        while not done:
            mask = info["action_mask"]
            o_t = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                v = float(agent.critic(o_t).squeeze())
                a = int(masked_logits(agent.actor(o_t),
                                      torch.as_tensor(mask, dtype=torch.bool)).argmax(-1))
            # vec[1] and vec[2] are fainted fractions (ours, theirs) out of 6
            ours_dead = round(float(obs[1]) * 6)
            theirs_dead = round(float(obs[2]) * 6)
            # our team HP mass from the six mon blocks (hp is the first field)
            hp = [float(obs[sd.GLOBAL_DIM + i * sd.MON_DIM]) for i in range(6)]
            ep.append(dict(v=v, ours_alive=6 - ours_dead, theirs_alive=6 - theirs_dead,
                           hp_mass=sum(hp) / 6.0, progress=theirs_dead))
            obs, r, term, trunc, info = env.step(a); done = term or trunc
        out = info.get("outcome")
        if out is None:
            out = 1 if r > 0 else (-1 if r < 0 else 0)
        for e in ep: e["outcome"] = out
        recs.extend(ep)
        if (b + 1) % 10 == 0:
            print(f"  {b+1}/{args.battles} battles, {len(recs)} states")
    env.close()

    print(f"\nA. VALUE CALIBRATION BY MATERIAL  (AUC; 0.5 = the critic cannot "
          f"rank a won state above a lost one)\n")
    print(f"  {'material (ours alive)':<26}{'n':>7}{'AUC':>8}{'mean V(win)':>13}"
          f"{'mean V(loss)':>14}")
    rows = {}
    for k in (6, 5, 4, 3, 2, 1):
        sel = [e for e in recs if e["ours_alive"] == k]
        pos = [e["v"] for e in sel if e["outcome"] > 0]
        neg = [e["v"] for e in sel if e["outcome"] < 0]
        a = auc(pos, neg)
        rows[k] = dict(n=len(sel), auc=a,
                       vw=statistics.mean(pos) if pos else None,
                       vl=statistics.mean(neg) if neg else None)
        if a is not None:
            print(f"  {k} left{'':<19}{len(sel):>7}{a:>8.3f}"
                  f"{statistics.mean(pos):>13.3f}{statistics.mean(neg):>14.3f}")

    print(f"\nB. THE STALL GRADIENT  (does V track our HP but ignore progress?)\n")
    print(f"  {'':<22}{'corr(V, our HP mass)':>24}{'corr(V, their faints)':>24}")
    def corr(xs, ys):
        if len(xs) < 10: return None
        mx, my = statistics.mean(xs), statistics.mean(ys)
        num = sum((a-mx)*(b-my) for a, b in zip(xs, ys))
        dx = sum((a-mx)**2 for a in xs) ** .5
        dy = sum((b-my)**2 for b in ys) ** .5
        return num/(dx*dy) if dx and dy else None
    for lbl, sel in [("all states", recs),
                     ("our HP mass > 0.7", [e for e in recs if e["hp_mass"] > 0.7]),
                     ("<=2 mons left", [e for e in recs if e["ours_alive"] <= 2])]:
        if len(sel) < 10: continue
        c1 = corr([e["hp_mass"] for e in sel], [e["v"] for e in sel])
        c2 = corr([e["progress"] for e in sel], [e["v"] for e in sel])
        f = lambda x: f"{x:>24.3f}" if x is not None else f"{'--':>24}"
        print(f"  {lbl:<22}{f(c1)}{f(c2)}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(
        dict(lane=args.lane, battles=args.battles, states=len(recs),
             by_material={str(k): v for k, v in rows.items()}), indent=2))
    print(f"\n  -> {args.out}")


if __name__ == "__main__":
    main()
