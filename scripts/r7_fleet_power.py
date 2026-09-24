#!/usr/bin/env python
"""R7 FLEET POWER -- the power statement of the fleet pre-reg (scripts/derive_r7_fleet.py's header), computed
from disk so the header quotes a traced number, never a typed one (CLAUDE.md, "a number typed from memory").

Inputs: five banked 3-lane trio READS of per-lane FP@20 greedy finals at n 3000 (the reads protocol the fleet's
primary uses) -- FOUR distinct trios: the 100M finals were read in two sessions, so the pooled df double-count
their lane term (their binomial terms are independent draws). Each read's across-lane sd is pooled (2 df each) and
split into its binomial part (the mean p(1-p)/n over the lanes) and the rest -- the TRUE lane sd, which is what a
searched/control lane pair differs by besides the lever.

The simulation applies the pre-reg's rule EXACTLY: delta = the equal-weight mean of the searched finals minus
the equal-weight mean of the control finals; se_diff = the LARGER of the pooled-binomial se_diff and the
seed-clustered se_diff (the per-arm across-lane sd / sqrt(k), 2 df per arm, 1 df for a two-lane control); the
strict boundary (a delta EXACTLY +0.025 or EXACTLY 2*se_diff reads as NOT met). The lane pairs share a donor
(PAIRED BY FINAL), so the true lane variance is split into a donor part (shared by a pair) and a training part
(each lane's own); the split is unknown, so both ends are printed. Cells (the header's partition):
  X-POS   delta > +0.025 and delta > 2*se_diff
  X-GAIN  0 < delta <= +0.025 and delta > 2*se_diff      (a RESOLVED gain below the floor)
  X-COST  -0.025 <= delta < 0 and |delta| > 2*se_diff   (a RESOLVED cost below the floor)
  X-NEG   delta < -0.025 and |delta| > 2*se_diff
  X-FLAT  everything else

    python scripts/r7_fleet_power.py --out <main>/results/r7_fleet/power.json
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import pathlib

import numpy as np

MAIN = pathlib.Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")
TRIOS = {  # name -> the per-lane FP@20 greedy finals (n 3000 each), as banked
    "W 200M finals (R5 reads)": "results/monster_reads_offfp/gw1*f.json",
    "L2LAM 200M finals (R5 reads)": "results/monster_reads_offfp/gl1*f.json",
    "100M finals (R5 reads session)": "results/monster_reads_offfp/g1*r.json",
    "100M finals (ch5 session)": "results/ch5_100m/t1*.json",
    "R2 batch 50M finals": "results/ch5_r2_offsh/t*.json",
}
FLOOR = 0.025


def lane_finals(main: pathlib.Path) -> dict[str, list[tuple[str, int, int]]]:
    out = {}
    for name, pat in TRIOS.items():
        rows = []
        for f in sorted(glob.glob(str(main / pat))):
            if f.endswith(".runner.json"):
                continue
            d = json.loads(pathlib.Path(f).read_text())
            if d.get("battles_finished") is None or d.get("our_wins") is None:
                continue
            rows.append((str(pathlib.Path(f).relative_to(main)), int(d["our_wins"]), int(d["battles_finished"])))
        if len(rows) != 3:
            raise SystemExit(f"{name}: expected 3 lane finals under {pat}, found {len(rows)}")
        out[name] = rows
    return out


def spread(trios: dict) -> dict:
    var, binv, per = [], [], {}
    for name, rows in trios.items():
        p = np.array([w / n for _, w, n in rows])
        v = float(p.var(ddof=1))
        b = float(np.mean([pi * (1 - pi) / n for pi, (_, _, n) in zip(p, rows)]))
        var.append(v); binv.append(b)
        per[name] = {"finals": [round(float(x), 4) for x in p], "sd": math.sqrt(v), "files": [r[0] for r in rows]}
    pooled = float(np.mean(var)); b = float(np.mean(binv))
    return {"per_trio": per, "pooled_sd": math.sqrt(pooled), "binomial_sd": math.sqrt(b),
            "true_lane_sd": math.sqrt(max(pooled - b, 0.0)), "df": 2 * len(var)}


def simulate(delta: float, k_c: int, n: int, lane_sd: float, donor_share: float, sims: int, rng) -> dict:
    """One cell of the power table: the probability of each branch at a TRUE delta."""
    base = 0.5
    donor = rng.normal(0.0, lane_sd * math.sqrt(donor_share), (sims, 3))
    train_sd = lane_sd * math.sqrt(1.0 - donor_share)
    p_s = np.clip(base + delta / 2 + donor + rng.normal(0.0, train_sd, (sims, 3)), 0.01, 0.99)
    p_c = np.clip(base - delta / 2 + donor[:, :k_c] + rng.normal(0.0, train_sd, (sims, k_c)), 0.01, 0.99)
    s = rng.binomial(n, p_s) / n
    c = rng.binomial(n, p_c) / n
    d = s.mean(1) - c.mean(1)
    ps, pc = s.mean(1), c.mean(1)
    se_bin = np.sqrt(ps * (1 - ps) / (3 * n) + pc * (1 - pc) / (k_c * n))
    se_clu = np.sqrt(s.var(1, ddof=1) / 3 + c.var(1, ddof=1) / k_c)
    se = np.maximum(se_bin, se_clu)
    pos = (d > FLOOR) & (d > 2 * se)
    gain = (d > 0) & (d <= FLOOR) & (d > 2 * se)
    neg = (d < -FLOOR) & (-d > 2 * se)
    cost = (d >= -FLOOR) & (d < 0) & (-d > 2 * se)
    return {"X-POS": float(pos.mean()), "X-GAIN": float(gain.mean()), "X-NEG": float(neg.mean()),
            "X-COST": float(cost.mean()), "X-FLAT": float(1.0 - pos.mean() - gain.mean() - neg.mean() - cost.mean()),
            "se_diff_median": float(np.median(se)), "se_bin_median": float(np.median(se_bin)),
            "se_clustered_p05_p95": [float(np.quantile(se_clu, 0.05)), float(np.quantile(se_clu, 0.95))]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--main", default=str(MAIN))
    ap.add_argument("--out", required=True)
    ap.add_argument("--sims", type=int, default=200_000)
    ap.add_argument("--seed", type=int, default=20260924)
    args = ap.parse_args()
    main_ = pathlib.Path(args.main)
    sp = spread(lane_finals(main_))
    rng = np.random.default_rng(args.seed)
    deltas = (-0.030, -0.020, 0.0, 0.020, 0.025, 0.030, 0.035, 0.040)
    table = []
    for width, k_c in (("3+3", 3), ("3+2", 2)):
        for n in (3000, 6000):
            for share in (0.0, 0.5):
                for dl in deltas:
                    cell = simulate(dl, k_c, n, sp["true_lane_sd"], share, args.sims, rng)
                    table.append({"width": width, "n": n, "donor_share": share, "delta": dl, **cell})
    out = {"version": "r7_fleet_power/2", "sims": args.sims, "seed": args.seed, "floor": FLOOR, **sp, "table": table}
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    print(f"pooled per-lane sd {sp['pooled_sd']:.4f} over {sp['df']} df; binomial {sp['binomial_sd']:.4f}; "
          f"true lane sd {sp['true_lane_sd']:.4f}")
    for name, t in sp["per_trio"].items():
        print(f"  {name}: {t['finals']} sd {t['sd']:.4f}")
    print("width   n     donor  " + "  ".join(f"{d:+.3f}" for d in deltas) + "   (P(X-POS); se_diff median at +0.030)")
    for width in ("3+3", "3+2"):
        for n in (3000, 6000):
            for share in (0.0, 0.5):
                cells = [r for r in table if r["width"] == width and r["n"] == n and r["donor_share"] == share]
                se30 = next(r["se_diff_median"] for r in cells if r["delta"] == 0.030)
                print(f"{width}  {n}  {share:.1f}    " + "  ".join(f"{r['X-POS']:.3f} " for r in cells) + f"  {se30:.4f}")
    for width in ("3+3", "3+2"):
        for dl in (-0.020, 0.020):
            r = next(r for r in table if r["width"] == width and r["n"] == 3000 and r["donor_share"] == 0.0 and r["delta"] == dl)
            print(f"{width} n 3000 at a true {dl:+.3f}: " + ", ".join(f"{k} {r[k]:.3f}" for k in ("X-POS", "X-GAIN", "X-FLAT", "X-COST", "X-NEG")))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
