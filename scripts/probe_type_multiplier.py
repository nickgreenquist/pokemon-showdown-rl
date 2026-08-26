#!/usr/bin/env python
"""Does the policy actually USE the type-multiplier feature?

THE QUESTION. `_fill_move` hands the network each move's damage multiplier vs
the current foe as one scalar (`vec[o+4]`), but it never hands it the PRODUCT
that matters: expected damage = power x multiplier x STAB x accuracy. There is
no STAB feature at all. So "4x beats 2x" has to be learned as a multiplicative
interaction between features a linear layer combines additively. Two live
observations motivated this:

  * four of six 0x moves on the ladder were Thunderbolt into a Ground type;
  * Blizzard (bp 120, acc 0.90, x2, no STAB) and Hydro Pump (bp 120, acc 0.80,
    x4, STAB) differ in the encoder ONLY in the multiplier — and every other
    feature FAVOURS Blizzard.

THE INTERVENTION. Hold one observation fixed. Give the active mon four
identical, interchangeable moves. Sweep slot 0's multiplier across the gen-1
lattice (0, 0.25, 0.5, 1, 2, 4) while the other three stay at 1.0, and read
how much probability the policy puts on slot 0. A policy that reads the
feature should move sharply; one that ignores it should sit near 1/4.

WHAT THIS IS NOT. A synthetic observation is not a battle: it shows whether the
feature is WIRED IN and how strongly, not how the agent behaves in a real
position. It is a controlled intervention, and that is exactly why it isolates
the one feature. Read it alongside the replay audit, which is behavioural but
confounded by PP and unrevealed movesets.
"""
import argparse, os, sys, hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def _flags():
    # Must match the ladder's encoder exactly, and must be set before the
    # first rl.envs.showdown import (the flags are read at import time).
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")


def build_obs(sd, mult0, others=1.0, bp=1.20, acc=0.90):
    """One active mon, four interchangeable moves, slot 0's multiplier varied.

    Slot alignment is load-bearing (see embed_battle): move action 6+j reads
    move block j, so probability on action 6 IS probability on slot 0.
    """
    import numpy as np
    vec = np.zeros(sd.OBS_DIM, dtype=np.float32)
    vec[0] = 0.2                                  # turn 10/50
    o = sd.GLOBAL_DIM
    # our six team slots: slot 0 alive and active, rest alive on the bench
    for i in range(6):
        b = o + i * sd.MON_DIM
        vec[b] = 1.0                              # hp
        vec[b + 2] = 1.0 if i == 0 else 0.0       # is-active
    o += 6 * sd.MON_DIM
    o += sd.ACTIVE_DIM                            # boosts/volatiles all zero
    for j in range(4):
        b = o + j * sd.MOVE_DIM
        vec[b] = 1.0                              # known
        vec[b + 1] = bp                           # base power / 100
        vec[b + 2] = acc
        vec[b + 3] = 1.0                          # full PP
        vec[b + 4] = mult0 if j == 0 else others  # <-- THE INTERVENTION
        vec[b + 5] = 1.0                          # physical
    return vec


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", default="configs/eval/ladder_r1.yaml")
    ap.add_argument("--lanes", default="s62,s63,s64,s65")
    args = ap.parse_args()
    _flags()

    import numpy as np, torch, yaml
    from eval_checkpoint import _load_showdown_agent
    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config
    import rl.envs.showdown as sd

    prereg = yaml.safe_load(open(args.prereg))
    torch.set_num_threads(1)

    LATTICE = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
    # legal: 4 moves, no switches -- isolates the move choice
    mask = np.zeros(6 + 4, dtype=bool); mask[6:10] = True

    print(f"OBS_DIM {sd.OBS_DIM}  MOVE_DIM {sd.MOVE_DIM}  "
          f"(v2={os.environ['POKEMON_RL_ENCODER_V2']} "
          f"ids={os.environ['POKEMON_RL_ENCODER_IDS']})")
    print("\nP(pick slot 0) as its type multiplier is swept, other three at 1.0.")
    print("A policy that ignores the feature sits at 0.250 throughout.\n")
    print(f"  {'lane':<6}" + "".join(f"{f'x{m:g}':>9}" for m in LATTICE)
          + f"{'x4/x0':>9}")

    rows = []
    for lane in args.lanes.split(","):
        spec = prereg["checkpoints"][lane]
        h = hashlib.sha256()
        with open(spec["path"], "rb") as fh:
            for blk in iter(lambda: fh.read(1 << 20), b""):
                h.update(blk)
        assert h.hexdigest() == spec["sha256"], f"sha256 mismatch on {lane}"
        agent = _load_showdown_agent(load_checkpoint(spec["path"]),
                                     Config(**load_checkpoint(spec["path"])["config"]))
        ps = []
        for m in LATTICE:
            obs = build_obs(sd, m)
            # Same path act() takes -- actor -> masked_logits -- so the probe
            # reads the deployed policy, not a reimplementation of it.
            from rl.common.masking import masked_logits
            obs_t = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
            mask_t = torch.as_tensor(mask, dtype=torch.bool)
            with torch.no_grad():
                logits = masked_logits(agent.actor(obs_t), mask_t)
            probs = torch.softmax(logits, -1)[0].numpy()
            ps.append(float(probs[6]))
        rows.append(ps)
        print(f"  {lane:<6}" + "".join(f"{p:>9.3f}" for p in ps)
              + f"{ps[-1]/max(ps[0],1e-9):>9.1f}")

    mean = np.mean(rows, axis=0)
    print(f"  {'mean':<6}" + "".join(f"{p:>9.3f}" for p in mean)
          + f"{mean[-1]/max(mean[0],1e-9):>9.1f}")
    print(f"\n  spread over the lattice: {mean.max() - mean.min():.3f}"
          f"   (0.000 = feature unused; 0.750 = feature dominant)")


if __name__ == "__main__":
    main()
