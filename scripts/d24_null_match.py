"""Matched-distance grading of a rank de-collapse claim against the geometric null.

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/d24_null_match.py --out results/d24_null

For every TREATMENT lane, this asks the only question that separates restored
learning dynamics from proximity-to-init: at the treatment's OWN distance from
init, what rank does a control checkpoint reach by interpolation alone?

    alpha*  solves  ||theta_c(alpha*) - theta_0||_LN-free  =  d_lnfree(treatment)

(exactly linear in alpha, so alpha* = d_T / d_C, then re-MEASURED at alpha*,
not read off a curve). The reported margin is

    margin = srank99(treatment) / srank99(null at alpha*)

against the MOST FAVOURABLE-TO-THE-NULL control lane (the max).

ASYMMETRY — READ THIS BEFORE QUOTING A MARGIN (corrected 2026-08-13 by the
ratification red team). Taking the max null is adversarial, and therefore the
right choice, only when ESTABLISHING an effect: clearing it means the effect
survives the most generous null available. It is ANTI-CONSERVATIVE when
RETIRING a claim — a margin at or below 1.0 against the max null does NOT mean
"the claim is geometry", it means the most generous null happened to beat it.
Retiring a claim needs the MEDIAN null (printed alongside). D23's actor read is
the worked example: max-null margins 1.26/0.94/0.63 read as "2 of 3 lanes at or
below geometry", but median-null gives 1.57/1.18/0.74 — one of three — so the
honest verdict there is INCONCLUSIVE, not refuted.

Defaults grade D23 (treatment 44/45/46 vs the Rung-2 controls 26/27/28 at 12M),
which is the re-grade the 2026-08-13 design cycle called for. See
scripts/d24_interp_null.py for the null itself.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from d22_dormant_rank import build, probe  # noqa: E402
from d22_weight_norms import reconstruct_theta0  # noqa: E402
from d24_interp_null import covered_names, interpolate, ln_free_dist  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", default="runs")
    ap.add_argument("--out", default="results/d24_null")
    ap.add_argument("--tapes", default="results/d23")
    ap.add_argument("--treatment-lanes", default="44,45,46")
    ap.add_argument("--treatment-prefix", default="showdown_sp_l2init12m_s")
    ap.add_argument("--treatment-ranks", default="results/d23/effective_rank.csv")
    ap.add_argument("--control-lanes", default="26,27,28")
    ap.add_argument("--control-prefix", default="showdown_sp_struct12m_s")
    ap.add_argument("--control-norms", default="results/d23/control_norms.csv")
    ap.add_argument("--treatment-norms", default="results/d23/treatment_norms.csv")
    ap.add_argument("--step", type=int, default=12_000_000)
    ap.add_argument("--theta0-tol", type=float, default=0.02)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"null_match{'_' + args.tag if args.tag else ''}.csv"
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path} — pass --tag <name>.")

    t_lanes = [int(s) for s in args.treatment_lanes.split(",")]
    c_lanes = [int(s) for s in args.control_lanes.split(",")]
    t_norms = pd.read_csv(args.treatment_norms)
    t_ranks = pd.read_csv(args.treatment_ranks)

    def d_lnfree_of(df: pd.DataFrame, seed: int, part: str) -> float:
        r = df[(df.seed == seed) & (df.step == args.step) & (df.part == part)]
        return float(r.d_lnfree.iloc[0])

    def srank_of(seed: int, part: str) -> int:
        r = t_ranks[(t_ranks.seed == seed) & (t_ranks.step == args.step)
                    & (t_ranks.part == part)]
        return int(r.srank99_ctx.iloc[0])

    # Control checkpoints, their theta0, and their own tapes — loaded once.
    controls = {}
    for seed in c_lanes:
        ck = load_checkpoint(
            Path(args.runs_root) / f"{args.control_prefix}{seed}"
            / f"ckpt_{args.step:09d}.pt")
        controls[seed] = {
            "ckpt": ck,
            "t0": reconstruct_theta0(ck["config"], args.theta0_tol),
            "obs": torch.from_numpy(
                np.load(Path(args.tapes) / f"obs_s{seed}.npz")["obs"]),
        }
        print(f"loaded control s{seed}")

    rows = []
    for part in ("actor", "critic"):
        for t_seed in t_lanes:
            d_t = d_lnfree_of(t_norms, t_seed, part)
            srank_t = srank_of(t_seed, part)
            for c_seed in c_lanes:
                c = controls[c_seed]
                sd = c["ckpt"]["agent"][part]
                ref = c["t0"][part]
                names = covered_names(part, c["ckpt"]["config"]["agent"]["trunk_kwargs"])
                d_c = ln_free_dist(sd, ref)
                alpha = d_t / d_c
                theta = interpolate(sd, ref, names, alpha)
                net = build(part, c["ckpt"]["config"]["agent"]["trunk_kwargs"])
                net.load_state_dict(theta)
                net.eval()
                dormant, ranks = probe(
                    net, c["obs"], f"null s{c_seed} alpha={alpha:.4f} {part}")
                rows.append({
                    "part": part, "treatment_seed": t_seed, "control_seed": c_seed,
                    "d_lnfree_treatment": d_t, "d_lnfree_control": d_c,
                    "alpha_star": alpha,
                    "d_lnfree_null": ln_free_dist(theta, ref),
                    "srank99_treatment": srank_t,
                    "srank99_null": ranks["srank99_ctx"],
                    "margin": srank_t / ranks["srank99_ctx"],
                    "dormant_null_tau025": dormant["ctx_net.1"]["tau025"],
                })
            print(f"  {part} t{t_seed} done")

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    print(f"\nwrote {path}\n")

    for part in ("actor", "critic"):
        p = df[df.part == part]
        print(f"=== {part} ctx srank99 vs the geometric null at matched distance ===")
        for t_seed in t_lanes:
            q = p[p.treatment_seed == t_seed]
            worst = q.loc[q.srank99_null.idxmax()]  # most favourable to the null
            nulls = ", ".join(
                f"s{int(r.control_seed)} {int(r.srank99_null)}@a={r.alpha_star:.2f}"
                for _, r in q.iterrows())
            print(f"  s{t_seed}: treatment {int(worst.srank99_treatment):>3d}   "
                  f"null [{nulls}]   ADVERSARIAL MARGIN "
                  f"{worst.srank99_treatment / worst.srank99_null:.2f}x")
        print()


if __name__ == "__main__":
    main()
