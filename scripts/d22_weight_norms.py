"""Weight-norm trajectory across a lane set's checkpoints (D22 read 3, DESIGN §12;
adapted 2026-08-12 for D23's R0-9 control curves).

    python scripts/d22_weight_norms.py [--runs-root runs] [--out results/d22]

Defaults reproduce the D22 50M read EXACTLY (lanes 35/36/37 of
showdown_sp_struct50m_s*, every ckpt_*.pt, drift measured from the 500k
checkpoint, Adam state read at 50M). The lane set, step set, run-name prefix
and output file are now CLI arguments, mirroring d22_dormant_rank.py.

Loads each ckpt_*.pt, computes global and per-block parameter L2 norms for
actor and critic, plus L2 drift from the FIRST loaded checkpoint (500k on the
50M lanes — the earliest on-disk proxy for init; the column keeps its D22 name
`drift_from_500k` when that is the reference step and is named
`drift_from_<step>` otherwise). Juliani & Ash: plasticity loss under on-policy
domain shift correlates with growing norms.

Also reads Adam's exp_avg_sq out of the --adam-step checkpoint's optimizer
state to localize which block carries the gradient magnitude (the s37 grad-norm
blowup question). Optimizer group 0 is the actor, group 1 the critic
(rl/agents/ppo.py); within a group, state index i is the i-th state_dict entry
— asserted below.

THETA0 MODE (--theta0), added for D23's R0-9 control read
(configs/showdown_sp_l2init12m.yaml, MANIPULATION CHECK):

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/d22_weight_norms.py --lanes 26,27,28 \
        --run-prefix showdown_sp_struct12m_s \
        --steps 400000,3000000,6000000,9000000,12000000 \
        --anchors 400000,3000000,6000000,9000000,12000000 \
        --theta0 --out results/d23 --out-name control_norms.csv

theta0 is RECONSTRUCTED, not read off disk: the header's claim is that init is
deterministic given (seed, config), so we call rl.common.seeding.set_seed(seed)
with the seed from the checkpoint's OWN config snapshot and then build the
agent exactly the way rl/train.py does (make_agent over faked Showdown spaces,
as rl.train._frozen_checkpoint_pool already does — a real env here would open
websockets just to read shapes). Assumption, stated: nothing between
train()'s set_seed and its make_agent call consumes the TORCH RNG (env
construction draws from Python's `random` for poke-env usernames and from
NumPy for gymnasium spaces). Cross-check available without any run-dir
artifact: the embedding tables are std-0.02 normal draws, so
||theta0(species_emb)|| ~= 0.02*sqrt(152*64) = 1.972 analytically, and the
reconstruction is asserted against that (--theta0-tol, default 2%).

Extra columns in theta0 mode (default output is byte-identical without it):
`r_<block>`   = ||theta_block|| / ||theta0_block||  (NaN where theta0 is
                exactly zero — slot_bias is zero-init, so its ratio is
                undefined by construction and `d_slot_bias` carries the read),
`d_<block>`   = ||theta_block - theta0_block||       (the l2init/anchor_dist_*
                statistic the treatment lanes log online),
`r_lnfree`    = sqrt(sum ||theta_b||^2) / sqrt(sum ||theta0_b||^2) over the
                LN-FREE blocks only (species_emb, move_emb, ctx_net, scorer,
                slot_bias, head) — the header retires the global-norm version
                as ~half gauge-inert, and this is the OVERBOUND statistic,
`d_lnfree`, `d_global` = the same drift aggregated.
"""

import argparse
import json
import re
from pathlib import Path

import pandas as pd
import torch

from rl.common.checkpoint import load_checkpoint

LANES = (35, 36, 37)
RUN_PREFIX = "showdown_sp_struct50m_s"
ANCHORS = (500_000, 12_000_000, 25_000_000, 50_000_000)
ADAM_STEP = 50_000_000
BLOCKS = ("slot_bias", "species_emb", "move_emb", "mon_net", "move_net",
          "field_net", "ctx_net", "scorer", "head")
# The approximately-scale-invariant blocks are exactly those built by _subnet
# (Linear-ReLU-Linear-LayerNorm): mon_net, move_net, field_net. Everything else
# carries no LayerNorm, so its norm is functionally meaningful — this is the
# set every D23 functional read uses (config header, COVERAGE).
LN_FREE = ("species_emb", "move_emb", "ctx_net", "scorer", "slot_bias", "head")
SPECIES_EMB_THETA0 = 0.02 * (152 * 64) ** 0.5  # 1.9718... — analytic cross-check


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


def block_sq(sd: dict) -> dict:
    """Per-block SQUARED norms (aggregating subsets needs squares, not norms)."""
    out = {}
    for name, t in sd.items():
        out[block_of(name)] = out.get(block_of(name), 0.0) + float(t.pow(2).sum())
    return out


def drift(sd: dict, ref: dict) -> float:
    return sum(float((sd[k] - ref[k]).pow(2).sum()) for k in sd) ** 0.5


def drift_by_block(sd: dict, ref: dict) -> dict:
    """Per-block SQUARED ||theta - theta0||."""
    out = {}
    for k, t in sd.items():
        out[block_of(k)] = out.get(block_of(k), 0.0) + float((t - ref[k]).pow(2).sum())
    return out


def reconstruct_theta0(ckpt_config: dict, tol: float) -> dict:
    """Rebuild a run's initialization from (seed, config) — see module docstring.

    Returns {"actor": state_dict, "critic": state_dict} of detached clones,
    taken BEFORE any optimizer step, i.e. after init_head() and .to(device),
    which is the theta0 the D23 lever anchors on.
    """
    from types import SimpleNamespace

    import gymnasium as gym
    import numpy as np

    from rl.common.config import Config
    from rl.common.seeding import set_seed
    from rl.envs.showdown import OBS_DIM
    from rl.train import make_agent

    cfg = Config(**ckpt_config)
    set_seed(cfg.seed)
    spaces = SimpleNamespace(
        observation_space=gym.spaces.Box(-1.0, 4.0, (OBS_DIM,), np.float32),
        action_space=gym.spaces.Discrete(10),
    )
    agent = make_agent(cfg, spaces)
    t0 = {part: {k: v.detach().clone()
                 for k, v in getattr(agent, part).state_dict().items()}
          for part in ("actor", "critic")}
    got = float(t0["actor"]["species_emb.weight"].pow(2).sum().sqrt())
    if abs(got - SPECIES_EMB_THETA0) / SPECIES_EMB_THETA0 > tol:
        raise SystemExit(
            f"theta0 reconstruction failed the analytic cross-check: actor "
            f"species_emb ||theta0|| = {got:.4f}, expected "
            f"{SPECIES_EMB_THETA0:.4f} +/- {tol:.0%} (0.02*sqrt(152*64)). "
            "Either the init recipe changed or the config snapshot is wrong."
        )
    return t0


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
    ap.add_argument("--out-name", default="weight_norms.csv")
    ap.add_argument("--lanes", default=",".join(str(s) for s in LANES),
                    help="comma-separated seeds")
    ap.add_argument("--run-prefix", default=RUN_PREFIX,
                    help="run dir name is <prefix><seed>")
    ap.add_argument("--steps", default="",
                    help="comma-separated checkpoint steps; empty = every ckpt_*.pt")
    ap.add_argument("--anchors", default=",".join(str(s) for s in ANCHORS),
                    help="steps quoted in the printed summary (missing ones print n/a)")
    ap.add_argument("--adam-step", type=int, default=ADAM_STEP,
                    help="step whose Adam exp_avg_sq is dumped per lane; -1 disables")
    ap.add_argument("--theta0", action="store_true",
                    help="add ||theta||/||theta0|| and ||theta-theta0|| columns, "
                         "theta0 reconstructed from the checkpoint's (seed, config)")
    ap.add_argument("--theta0-tol", type=float, default=0.02,
                    help="tolerance on the analytic species_emb ||theta0|| cross-check")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lanes = tuple(int(s) for s in args.lanes.split(","))
    want_steps = tuple(int(s) for s in args.steps.split(",")) if args.steps else None
    anchors = tuple(int(s) for s in args.anchors.split(","))

    rows = []
    drift_col = None
    for seed in lanes:
        rd = Path(args.runs_root) / f"{args.run_prefix}{seed}"
        ckpts = sorted(rd.glob("ckpt_*.pt"),
                       key=lambda p: int(re.search(r"(\d+)", p.name).group(1)))
        if want_steps is not None:
            by_step = {int(re.search(r"(\d+)", p.name).group(1)): p for p in ckpts}
            missing = [s for s in want_steps if s not in by_step]
            if missing:
                raise SystemExit(f"s{seed}: no checkpoint for steps {missing} in {rd}")
            ckpts = [by_step[s] for s in want_steps]
        if not ckpts:
            raise SystemExit(f"s{seed}: no ckpt_*.pt under {rd}")
        ref = None
        t0 = None
        t0_cfg = None
        for p in ckpts:
            c = load_checkpoint(p)
            step = int(re.search(r"(\d+)", p.name).group(1))
            if ref is None:
                ref = {part: {k: v.clone() for k, v in c["agent"][part].items()}
                       for part in ("actor", "critic")}
                drift_col = ("drift_from_500k" if step == 500_000
                             else f"drift_from_{step}")
            if args.theta0 and t0 is None:
                t0_cfg = json.dumps(c["config"], sort_keys=True, default=str)
                if int(c["config"]["seed"]) != seed:
                    print(f"  NOTE s{seed}: config snapshot says seed="
                          f"{c['config']['seed']} — reconstructing at THAT seed")
                t0 = reconstruct_theta0(c["config"], args.theta0_tol)
                t0sq = {part: block_sq(t0[part]) for part in ("actor", "critic")}
            if args.theta0:
                now = json.dumps(c["config"], sort_keys=True, default=str)
                if now != t0_cfg:
                    raise SystemExit(
                        f"s{seed} ckpt_{step:09d}: config snapshot differs from the "
                        "lane's first checkpoint — theta0 is (seed, config)-specific"
                    )
            for part in ("actor", "critic"):
                sd = c["agent"][part]
                row = {"seed": seed, "step": step, "part": part}
                row.update(norms(sd))
                row[drift_col] = drift(sd, ref[part])
                if args.theta0:
                    if set(sd.keys()) != set(t0[part].keys()):
                        raise SystemExit(
                            f"s{seed} ckpt_{step:09d} {part}: state_dict keys differ "
                            "from the reconstructed init (R0-2b would also catch this)"
                        )
                    sq, dsq = block_sq(sd), drift_by_block(sd, t0[part])
                    for b, v0 in t0sq[part].items():
                        row[f"r_{b}"] = (sq[b] / v0) ** 0.5 if v0 > 0 else float("nan")
                        row[f"d_{b}"] = dsq[b] ** 0.5
                    lnf = [b for b in LN_FREE if b in sq]
                    row["r_lnfree"] = (sum(sq[b] for b in lnf)
                                       / sum(t0sq[part][b] for b in lnf)) ** 0.5
                    row["d_lnfree"] = sum(dsq[b] for b in lnf) ** 0.5
                    row["d_global"] = sum(dsq.values()) ** 0.5
                rows.append(row)
            if args.adam_step >= 0 and step == args.adam_step and "optimizer" in c["agent"]:
                gs = grad_scale_by_block(c["agent"])
                gs.insert(0, "seed", seed)
                gs.to_csv(out / f"adam_grad_scale_s{seed}.csv", index=False)
        print(f"s{seed}: {len(ckpts)} ckpts done")

    df = pd.DataFrame(rows)
    df.to_csv(out / args.out_name, index=False)

    lo, hi = anchors[0], anchors[-1]
    for part in ("actor", "critic"):
        print(f"\n=== {part} global L2 norm ("
              f"{' / '.join(f'{a/1e6:g}M' for a in anchors)}, growth x, drift@"
              f"{hi/1e6:g}M) ===")
        for seed in lanes:
            d = df[(df.seed == seed) & (df.part == part)].set_index("step")
            g = d["global"]
            vals = " / ".join("n/a" if g.get(a) is None else f"{g.get(a):.1f}"
                              for a in anchors)
            grow = (f"x{g.get(hi)/g.get(lo):.2f}"
                    if g.get(lo) is not None and g.get(hi) is not None else "x n/a")
            dr = d[drift_col].get(hi)
            print(f"  s{seed}: {vals}   {grow}   "
                  f"drift {'n/a' if dr is None else f'{dr:.1f}'}")

    print(f"\n=== per-block growth x ({lo/1e6:g}M -> {hi/1e6:g}M), actor ===")
    for seed in lanes:
        d = df[(df.seed == seed) & (df.part == "actor")].set_index("step")
        parts = []
        for b in BLOCKS:
            if b in d.columns and not d[b].isna().all():
                num, den = d[b].get(hi), d[b].get(lo)
                if num is not None and den is not None:
                    parts.append(f"{b} x{num/den:.2f}")
        print(f"  s{seed}: " + ", ".join(parts))

    if args.theta0:
        print("\n=== ||theta||/||theta0|| by block (theta0 RECONSTRUCTED from "
              "(seed, config)) ===")
        for part in ("actor", "critic"):
            for seed in lanes:
                d = df[(df.seed == seed) & (df.part == part)].set_index("step")
                cols = [f"r_{b}" for b in LN_FREE if f"r_{b}" in d.columns
                        and not d[f"r_{b}"].isna().all()]
                print(f"  s{seed} {part:6s} @{hi/1e6:g}M: " + ", ".join(
                    f"{c[2:]} x{d[c].get(hi):.2f}" for c in cols)
                    + f", LN-free aggregate x{d['r_lnfree'].get(hi):.2f}")
        print("\n=== actor species_emb ||theta||/||theta0|| trajectory "
              "(MANIPULATION-CHECK control) ===")
        for seed in lanes:
            d = df[(df.seed == seed) & (df.part == "actor")].set_index("step")
            print(f"  s{seed}: " + " -> ".join(
                f"{a/1e6:g}M x{d['r_species_emb'].get(a):.2f}" for a in anchors
                if d['r_species_emb'].get(a) is not None))
        fin = df[(df.step == hi) & (df.part == "actor")]["r_species_emb"]
        print(f"  control MEAN at {hi/1e6:g}M: x{fin.mean():.3f}  "
              f"(0.75x -> BOUND at {0.75*fin.mean():.3f}; "
              f"0.92x -> VOID at {0.92*fin.mean():.3f})")
        print("  NOTE: slot_bias is zero-init, so r_slot_bias is undefined (NaN) "
              "by construction; d_slot_bias carries that block's read.")

    if args.adam_step >= 0:
        files = {s: out / f"adam_grad_scale_s{s}.csv" for s in lanes}
        if all(p.exists() for p in files.values()):
            print(f"\n=== Adam sqrt(exp_avg_sq) per block at "
                  f"{args.adam_step/1e6:g}M (gradient localization) ===")
            for seed in lanes:
                gs = pd.read_csv(files[seed])
                top = gs.sort_values("rms_grad", ascending=False).head(4)
                print(f"  s{seed}: " + ", ".join(
                    f"{r.part}/{r.block} rms {r.rms_grad:.2e}" for r in top.itertuples()))

    print(f"\nwrote {out / args.out_name}")


if __name__ == "__main__":
    main()
