#!/usr/bin/env python
"""Is the type-multiplier feature actually populated at live decision time?

WHY THIS EXISTS. `scripts/probe_type_multiplier.py` showed the policy reads
`vec[o+4]` (a move's damage multiplier vs the current foe) decisively: on a
held-fixed observation, P(pick) runs 0.000 / 0.002 / 0.239 / 0.998 / 1.000
across x0 / x0.5 / x1 / x2 / x4, and it never picks an immune move. But on the
ladder it picked a 0x move six times, three of them with a strictly better
move the same mon had already used that battle.

Probe and behaviour contradict. Either the probe's synthetic observation is too
far off-distribution to mean anything, or THE FEATURE IS NOT WHAT WE THINK AT
DECISION TIME. `_fill_move` fills the multiplier only `if foe is not None`, and
`_move_slots_aliased` deliberately zeroes every move block on gen-1 placeholder
turns (sleep / freeze / recharge / partial trap). If either fires in live play,
every legal move reads x0 and the policy is choosing blind — and nothing in the
JSONL or the replays would show it.

WHAT THIS DOES. Plays locally against SimpleHeuristicsPlayer with the SAME
encoder flags and the SAME checkpoint as the ladder, and at every decision
records what the observation actually holds: whether the move blocks are live,
what multiplier each legal move carries, and whether the chosen move was
dominated by a legal alternative. Local server only — the live ladder run is
never touched.
"""
import argparse, os, sys, json, collections
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", default="configs/eval/ladder_r1.yaml")
    ap.add_argument("--lane", default="s62")
    ap.add_argument("--battles", type=int, default=20)
    ap.add_argument("--seed", type=int, default=909,
                    help="MUST NOT collide with any live lane: poke-env "
                         "derives usernames from the global random seed")
    ap.add_argument("--out", default="results/diag/encoder_live.json")
    args = ap.parse_args()

    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")

    import numpy as np, torch, yaml
    from eval_checkpoint import _load_showdown_agent
    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config
    from rl.common.masking import masked_logits
    from rl.common.seeding import set_seed
    from rl.envs.make import make_env
    import rl.envs.showdown as sd

    prereg = yaml.safe_load(open(args.prereg))
    torch.set_num_threads(1)
    set_seed(args.seed)
    ck = load_checkpoint(prereg["checkpoints"][args.lane]["path"])
    agent = _load_showdown_agent(ck, Config(**ck["config"]))

    MOVE0 = sd.GLOBAL_DIM + 6 * sd.MON_DIM + sd.ACTIVE_DIM   # our 4 move blocks
    env = make_env("Showdown-v0", args.seed,
                   env_kwargs={"opponent": "heuristics"})

    stat = collections.Counter()
    dominated = []
    for b in range(args.battles):
        obs, info = env.reset()
        done = False
        while not done:
            mask = info["action_mask"]
            legal_moves = [j for j in range(4) if mask[6 + j]]
            if legal_moves:
                stat["decisions_with_a_move"] += 1
                blocks = {j: obs[MOVE0 + j * sd.MOVE_DIM:
                                MOVE0 + (j + 1) * sd.MOVE_DIM]
                          for j in legal_moves}
                known = {j: float(v[0]) for j, v in blocks.items()}
                mult = {j: float(v[4]) for j, v in blocks.items()}
                aliased = float(obs[5]) > 0.5
                if aliased:
                    stat["turns_move_slots_ALIASED"] += 1
                if all(k == 0.0 for k in known.values()):
                    stat["all_legal_moves_flagged_UNKNOWN"] += 1
                if all(m == 0.0 for m in mult.values()):
                    stat["all_legal_multipliers_ZERO"] += 1
            with torch.no_grad():
                o_t = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
                m_t = torch.as_tensor(mask, dtype=torch.bool)
                a = int(masked_logits(agent.actor(o_t), m_t).argmax(-1).item())
            if legal_moves and a >= 6 and (a - 6) in mult:
                chosen, best = mult[a - 6], max(mult.values())
                if chosen == 0.0 and best > 0.0:
                    stat["CHOSE_A_ZERO_x_MOVE_with_a_better_one_legal"] += 1
                    dominated.append({"battle": b, "chosen_mult": chosen,
                                      "best_legal_mult": best,
                                      "n_legal": len(legal_moves)})
                elif best > 0 and chosen < best / 2:
                    stat["chose_a_move_under_half_the_best_multiplier"] += 1
            obs, r, term, trunc, info = env.step(a)
            done = term or trunc
        stat["battles"] += 1
    env.close()

    out = {"lane": args.lane, "battles": args.battles, "seed": args.seed,
           "obs_dim": int(sd.OBS_DIM), "counts": dict(stat),
           "dominated_examples": dominated[:20]}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    n = max(stat["decisions_with_a_move"], 1)
    print(json.dumps(out["counts"], indent=2))
    print(f"\n  decisions with >=1 legal move : {n}")
    for k in ("all_legal_multipliers_ZERO", "all_legal_moves_flagged_UNKNOWN",
              "turns_move_slots_ALIASED",
              "CHOSE_A_ZERO_x_MOVE_with_a_better_one_legal"):
        print(f"  {k:<48} {stat[k]:>5}  = {stat[k]/n:6.2%}")
    print(f"\n  -> {args.out}")


if __name__ == "__main__":
    main()
