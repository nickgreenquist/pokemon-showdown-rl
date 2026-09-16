#!/usr/bin/env python
"""mech200m stage 1: the LOGGED half of [RWL-3]'s mechanism co-primary.

    python scripts/mech200m_history.py [--out results/mech200m]

Reads each monster lane's `history.csv` (written by scripts/extract_history.py
from the offline wandb run) and reports, at the matched rungs of
`configs/eval/mech200m.yaml`, the four logged quantities the PRIMARY names:
`loss/explained_variance`, `loss/adv_std`, every `l2init/anchor_dist_*` key,
and -- because a rung mean over one update is noise -- a WINDOW mean around
each rung plus a last-5%-of-updates tail mean.

WHY IT STREAMS. Each history.csv is ~740 MB and ~6.4M rows, because wandb
writes a row per LOG CALL and the collector logs far more often than PPO's
update does: in the first 200k rows exactly 196 carry `loss/adv_std` and 24
carry an `l2init/*` key. So the file is read in chunks, every row without the
metric of interest is dropped immediately, and what survives (a few thousand
rows per lane) is what gets summarised. Reading these files whole is a
multi-GB mistake.

NO RESUME SPLIT HERE, checked rather than assumed: the fleet finished with
RESUMES=0, so each lane has exactly one offline wandb run and
`extract_history.py` did not hit the overlapping-step hard failure that a
resume produces (docs/landmines.md). If a future lane resumes, that failure is
loud and this script never sees the file.
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "configs/eval/mech200m.yaml"
METRICS = ["loss/explained_variance", "loss/adv_std"]
L2_PREFIX = "l2init/anchor_dist_"


def lane_frame(run_dir: Path) -> pd.DataFrame:
    """Every row of history.csv that carries at least one PPO-update metric."""
    path = run_dir / "history.csv"
    head = pd.read_csv(path, nrows=0)
    cols = (["_step"] + [c for c in METRICS if c in head.columns]
            + [c for c in head.columns if c.startswith(L2_PREFIX)])
    keep = []
    for chunk in pd.read_csv(path, usecols=cols, chunksize=500_000):
        sub = chunk.dropna(subset=[c for c in cols if c != "_step"], how="all")
        if len(sub):
            keep.append(sub)
    df = pd.concat(keep, ignore_index=True).sort_values("_step")
    return df


def window(df: pd.DataFrame, col: str, centre: int, frac: float = 0.02) -> dict:
    """Mean/std of `col` over steps within +/- frac*centre of `centre`."""
    s = df[["_step", col]].dropna()
    if s.empty:
        return {}
    lo, hi = centre * (1 - frac), centre * (1 + frac)
    w = s[(s._step >= lo) & (s._step <= hi)]
    if w.empty:                       # rung outside this lane's logging cadence
        idx = (s._step - centre).abs().idxmin()
        w = s.loc[[idx]]
    return {"mean": float(w[col].mean()), "std": float(w[col].std()),
            "n": int(len(w)), "step_lo": int(w._step.min()), "step_hi": int(w._step.max())}


def tail(df: pd.DataFrame, col: str, frac: float = 0.05) -> dict:
    s = df[["_step", col]].dropna()
    if s.empty:
        return {}
    cut = s._step.max() * (1 - frac)
    w = s[s._step >= cut]
    return {"mean": float(w[col].mean()), "std": float(w[col].std()),
            "n": int(len(w)), "step_lo": int(w._step.min()), "step_hi": int(w._step.max())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/mech200m")
    ap.add_argument("--plan", default=str(PLAN))
    args = ap.parse_args()
    plan = yaml.safe_load(open(args.plan))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rungs = plan["rungs"]["targets"]

    rows, tails = [], []
    for arm, spec in plan["lanes"].items():
        for seed in spec["seeds"]:
            rd = REPO / "runs" / f"{spec['prefix']}{seed}"
            if not (rd / "history.csv").exists():
                print(f"SKIP {rd.name}: no history.csv "
                      f"(run scripts/extract_history.py {rd})")
                continue
            df = lane_frame(rd)
            cols = [c for c in df.columns if c != "_step"]
            print(f"{rd.name}: {len(df)} metric rows, max step {int(df._step.max()):,}")
            # A rung BEYOND a lane's horizon is not a rung: window() falls back
            # to the nearest logged step, which for the 100M lanes would silently
            # report their 100M final under a "150M" / "200M" label. Filter first.
            max_step = int(df._step.max())
            for col in cols:
                for r in [x for x in rungs if x <= max_step * 1.01]:
                    w = window(df, col, r)
                    if w:
                        rows.append(dict(arm=arm, seed=seed, metric=col, rung=r, **w))
                t = tail(df, col)
                if t:
                    tails.append(dict(arm=arm, seed=seed, metric=col, **t))
    rung_df, tail_df = pd.DataFrame(rows), pd.DataFrame(tails)
    rung_df.to_csv(out / "history_rungs.csv", index=False)
    tail_df.to_csv(out / "history_tail.csv", index=False)
    print(f"\nwrote {out/'history_rungs.csv'} and {out/'history_tail.csv'}")

    for metric in METRICS + sorted({m for m in tail_df.metric if m.startswith(L2_PREFIX)}):
        print(f"\n=== {metric} — tail mean (last 5% of updates) ===")
        for arm in ("w", "l2lam", "h100"):
            t = tail_df[(tail_df.arm == arm) & (tail_df.metric == metric)]
            if t.empty:
                continue
            per = ", ".join(f"s{int(r.seed)} {r['mean']:.4f}" for _, r in t.iterrows())
            print(f"  {arm:6s} {per}   trio mean {t['mean'].mean():.4f} "
                  f"(across-lane sd {t['mean'].std():.4f})")


if __name__ == "__main__":
    main()
