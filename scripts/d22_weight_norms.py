"""D22 read 3 (DESIGN §12): weight-norm trajectory across the 50M checkpoints.

    python scripts/d22_weight_norms.py [--runs-root runs] [--out results/d22]

Loads every ckpt_*.pt for lanes s35/s36/s37, computes global and per-block
parameter L2 norms for actor and critic, plus L2 drift from each lane's first
checkpoint (500k — the earliest on-disk proxy for init). Juliani & Ash:
plasticity loss under on-policy domain shift correlates with growing norms.

Also reads Adam's exp_avg_sq out of the FINAL checkpoint's optimizer state to
localize which block carries the gradient magnitude (the s37 grad-norm blowup
question). Optimizer group 0 is the actor, group 1 the critic (rl/agents/ppo.py);
within a group, state index i is the i-th state_dict entry — asserted below.
"""

import argparse
import re
from pathlib import Path

import pandas as pd
import torch

from rl.common.checkpoint import load_checkpoint

LANES = (35, 36, 37)
BLOCKS = ("slot_bias", "species_emb", "move_emb", "mon_net", "move_net",
          "field_net", "ctx_net", "scorer", "head")


def block_of(name: str) -> str:
    for b in BLOCKS:
        if name.startswith(b):
            return b
    raise ValueError(f"unblocked param {name}")


def norms(sd: dict) -> dict:
    out = {}
    for name, t in sd.items():
        b = block_of(name)
        out[b] = out.get(b, 0.0) + float(t.pow(2).sum())
    out["global"] = sum(out.values())
    return {k: v ** 0.5 for k, v in out.items()}


def drift(sd: dict, ref: dict) -> float:
    return sum(float((sd[k] - ref[k]).pow(2).sum()) for k in sd) ** 0.5


def grad_scale_by_block(agent_state: dict) -> pd.DataFrame:
    """Per-block RMS of sqrt(exp_avg_sq) from the final ckpt's Adam state."""
    rows = []
    opt = agent_state["optimizer"]
    for gi, part in ((0, "actor"), (1, "critic")):
        names = list(agent_state[part].keys())
        idxs = opt["param_groups"][gi]["params"]
        assert len(names) == len(idxs), (part, len(names), len(idxs))
        acc: dict[str, list] = {}
        for name, idx in zip(names, idxs):
            st = opt["state"].get(idx)
            if st is None:
                continue
            acc.setdefault(block_of(name), []).append(st["exp_avg_sq"].sqrt().flatten())
        for b, ts in acc.items():
            v = torch.cat(ts)
            rows.append({"part": part, "block": b,
                         "rms_grad": float(v.pow(2).mean().sqrt()), "max_grad": float(v.max())})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", default="runs")
    ap.add_argument("--out", default="results/d22")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for seed in LANES:
        rd = Path(args.runs_root) / f"showdown_sp_struct50m_s{seed}"
        ckpts = sorted(rd.glob("ckpt_*.pt"),
                       key=lambda p: int(re.search(r"(\d+)", p.name).group(1)))
        ref = None
        for p in ckpts:
            c = load_checkpoint(p)
            step = int(re.search(r"(\d+)", p.name).group(1))
            if ref is None:
                ref = {part: {k: v.clone() for k, v in c["agent"][part].items()}
                       for part in ("actor", "critic")}
            for part in ("actor", "critic"):
                row = {"seed": seed, "step": step, "part": part}
                row.update(norms(c["agent"][part]))
                row["drift_from_500k"] = drift(c["agent"][part], ref[part])
                rows.append(row)
            if step == 50_000_000:
                gs = grad_scale_by_block(c["agent"])
                gs.insert(0, "seed", seed)
                gs.to_csv(out / f"adam_grad_scale_s{seed}.csv", index=False)
        print(f"s{seed}: {len(ckpts)} ckpts done")

    df = pd.DataFrame(rows)
    df.to_csv(out / "weight_norms.csv", index=False)

    for part in ("actor", "critic"):
        print(f"\n=== {part} global L2 norm (0.5M / 12M / 25M / 50M, growth x, "
              f"drift@50M) ===")
        for seed in LANES:
            d = df[(df.seed == seed) & (df.part == part)].set_index("step")
            g = d["global"]
            print(f"  s{seed}: {g.get(500_000):.1f} / {g.get(12_000_000):.1f} / "
                  f"{g.get(25_000_000):.1f} / {g.get(50_000_000):.1f}   "
                  f"x{g.get(50_000_000)/g.get(500_000):.2f}   "
                  f"drift {d['drift_from_500k'].get(50_000_000):.1f}")

    print("\n=== per-block growth x (500k -> 50M), actor ===")
    for seed in LANES:
        d = df[(df.seed == seed) & (df.part == "actor")].set_index("step")
        parts = []
        for b in BLOCKS:
            if b in d.columns and not d[b].isna().all():
                parts.append(f"{b} x{d[b].get(50_000_000)/d[b].get(500_000):.2f}")
        print(f"  s{seed}: " + ", ".join(parts))

    print("\n=== Adam sqrt(exp_avg_sq) per block at 50M (gradient localization) ===")
    for seed in LANES:
        gs = pd.read_csv(out / f"adam_grad_scale_s{seed}.csv")
        top = gs.sort_values("rms_grad", ascending=False).head(4)
        print(f"  s{seed}: " + ", ".join(
            f"{r.part}/{r.block} rms {r.rms_grad:.2e}" for r in top.itertuples()))


if __name__ == "__main__":
    main()
