"""The GEOMETRIC NULL for rank de-collapse under a toward-init regularizer.

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/d24_interp_null.py --out results/d24_null

THE QUESTION. D23's mechanism story leaned on critic/actor feature rank rising
under the regenerative L2-toward-init lever ("de-collapse"). A toward-init
regularizer moves the weights back toward a full-rank random init, so some of
that rise may be pure geometry — a property of being NEAR THE INIT, not of
restored learning dynamics. This script measures how much.

THE NULL. Take a CONTROL checkpoint theta_c (no lever) and its own
reconstructed theta_0, and form, over exactly the parameters the lever covers
(rl.agents.ppo._l2_init_covered — everything but LayerNorm-owned params):

    theta(alpha) = theta_0 + alpha * (theta_c - theta_0)

No training, no data, pure interpolation. Then read the same statistics the
lever's rung reads. Whatever the null produces at the treatment's own distance
from init is NOT evidence for the lever.

MATCHED-DISTANCE COMPARISON (the point of the exercise). Rank is compared at
equal LN-free anchor distance d_lnfree = ||theta - theta_0|| over the LN-free
blocks, not at equal alpha: alpha* is chosen so the interpolated control sits
at the treatment lane's measured distance. A treatment lane earns a de-collapse
claim only if its rank EXCEEDS the null at that matched distance.

Statistics per alpha: d_lnfree, r_species (||theta||/||theta_0|| of
species_emb), actor/critic ctx srank99 (float64, NaN-hard-failed — see
d22_dormant_rank.srank99), and actor/critic ctx_net.1 dormant fraction, which
is the control read: dormancy is a ratio to the layer mean, so if the null
moves rank but not dormancy, rank is the geometric one.

Written 2026-08-13 for the carry design cycle (results/d24_design/), which
found the null independently in two of four agents and then confirmed it.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from d22_dormant_rank import build, probe  # noqa: E402
from d22_weight_norms import LN_FREE, reconstruct_theta0  # noqa: E402

from rl.agents.ppo import _l2_init_covered  # noqa: E402
from rl.common.checkpoint import load_checkpoint  # noqa: E402

ALPHAS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0)


def covered_names(part: str, trunk_kwargs: dict) -> set[str]:
    """Parameter names the lever touches, from the lever's own predicate."""
    net = build(part, trunk_kwargs)
    return {name for name, _ in _l2_init_covered(net)}


def ln_free_dist(sd: dict, t0: dict) -> float:
    """||theta - theta0|| over the LN-free blocks — the anchor distance the
    D23 lever logs as l2init/anchor_dist_actor_lnfree."""
    tot = 0.0
    for k, v in sd.items():
        if any(k == b or k.startswith(f"{b}.") for b in LN_FREE):
            tot += float((v - t0[k]).pow(2).sum())
    return tot ** 0.5


def interpolate(sd: dict, t0: dict, names: set[str], alpha: float) -> dict:
    """theta0 + alpha*(theta_c - theta0) on covered params; others untouched."""
    return {
        k: (t0[k] + alpha * (v - t0[k])) if k in names else v.clone()
        for k, v in sd.items()
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", default="runs")
    ap.add_argument("--out", default="results/d24_null")
    ap.add_argument("--tapes", default="results/d23",
                    help="directory holding obs_s<seed>.npz for --lanes")
    ap.add_argument("--lanes", default="26,27,28", help="CONTROL seeds")
    ap.add_argument("--run-prefix", default="showdown_sp_struct12m_s")
    ap.add_argument("--step", type=int, default=12_000_000)
    ap.add_argument("--alphas", default=",".join(str(a) for a in ALPHAS))
    ap.add_argument("--theta0-tol", type=float, default=0.02)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.tag}" if args.tag else ""
    path = out / f"interp_null{suffix}.csv"
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path} — pass --tag <name>.")

    alphas = [float(a) for a in args.alphas.split(",")]
    rows = []
    for seed in (int(s) for s in args.lanes.split(",")):
        obs = torch.from_numpy(np.load(Path(args.tapes) / f"obs_s{seed}.npz")["obs"])
        ckpt = load_checkpoint(
            Path(args.runs_root) / f"{args.run_prefix}{seed}" / f"ckpt_{args.step:09d}.pt")
        tk = ckpt["config"]["agent"]["trunk_kwargs"]
        t0 = reconstruct_theta0(ckpt["config"], args.theta0_tol)
        for part in ("actor", "critic"):
            sd, ref = ckpt["agent"][part], t0[part]
            names = covered_names(part, tk)
            for alpha in alphas:
                theta = interpolate(sd, ref, names, alpha)
                net = build(part, tk)
                net.load_state_dict(theta)
                net.eval()
                dormant, ranks = probe(net, obs, f"s{seed} alpha={alpha} {part}")
                r_species = float(
                    theta["species_emb.weight"].pow(2).sum().sqrt()
                    / ref["species_emb.weight"].pow(2).sum().sqrt())
                rows.append({
                    "seed": seed, "part": part, "alpha": alpha,
                    "d_lnfree": ln_free_dist(theta, ref),
                    "r_species": r_species,
                    "srank99_ctx": ranks["srank99_ctx"],
                    "pr_ctx": ranks["pr_ctx"],
                    "dormant_ctx_tau025": dormant["ctx_net.1"]["tau025"],
                })
            print(f"s{seed} {part} done")

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    print(f"\nwrote {path}\n")

    for part in ("actor", "critic"):
        print(f"=== {part}: srank99_ctx by alpha (rows = control lanes) ===")
        p = df[df.part == part]
        print("  alpha   " + "  ".join(f"{a:>5.1f}" for a in alphas))
        for seed in sorted(p.seed.unique()):
            t = p[p.seed == seed].set_index("alpha")
            print(f"  s{seed}    "
                  + "  ".join(f"{int(t.loc[a, 'srank99_ctx']):>5d}" for a in alphas))
        print("  dorm    " + "  ".join(
            f"{p[p.alpha == a].dormant_ctx_tau025.median():>5.2f}" for a in alphas))
        print("  d_lnf   " + "  ".join(
            f"{p[p.alpha == a].d_lnfree.median():>5.1f}" for a in alphas))
        print()


if __name__ == "__main__":
    main()
