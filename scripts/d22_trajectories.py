"""EV + entropy trajectories from a lane set's history.csv (D22 reads 1+2,
DESIGN §12; adapted 2026-08-12 so the 12M rungs can reuse it).

    python scripts/d22_trajectories.py [--runs-root runs] [--out results/d22]

Bins loss/explained_variance and loss/entropy (per-update series, ~48k points)
into 1M-step bins per lane, alongside eval/win_rate and
selfplay/winrate_latest. Prints the numbers the §12 decision rule consumes:
plateau level, late-run slope, entropy floor, and the win-rate peak-vs-final
gap per lane (the "flat win rate" clause). CSV of the binned series goes to
--out for figures/re-reads.

Defaults reproduce the D22 50M read exactly (lanes 35/36/37 of
showdown_sp_struct50m_s*, anchor bins 4/11/24 + last, late slope from bin 35,
self-play mean over bins >= 40). Every one of those is now a flag, because the
12M rungs have 12 bins and none of the D22 constants exist there. D23
(configs/showdown_sp_l2init12m.yaml, SECONDARY 4 entropy band + D23-watch):

    python scripts/d22_trajectories.py --lanes 44,45,46 \
        --run-prefix showdown_sp_l2init12m_s --anchor-bins 2,5,8 \
        --slope-from-bin 6 --late-from-bin 8 --watch --out results/d23

--watch adds the D23-WATCH statistic, which is NOT the mean this script bins
elsewhere: per-lane per-1M-bin MEDIAN pre-clip loss/grad_norm, trigger = 3
consecutive bins each >= 3.0x the lane's own bins-0-3 median AND
non-decreasing. Record-only, and 12M-horizon-only (the header notes it also
fires retrospectively on s35/s36's RECOVERING 50M transients, which is why any
50M carry needs a recovery clause written at that pre-registration).
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

LANES = (35, 36, 37)
RUN_PREFIX = "showdown_sp_struct50m_s"
BIN = 1_000_000
ANCHOR_BINS = (4, 11, 24)
SLOPE_FROM_BIN = 35
LATE_FROM_BIN = 40
WATCH_SERIES = "loss/grad_norm"
WATCH_RATIO = 3.0
WATCH_BASE_BINS = 4
WATCH_RUN = 3
SERIES = ["loss/explained_variance", "loss/entropy", "loss/approx_kl", "loss/grad_norm"]


def binned(df: pd.DataFrame, col: str, how: str = "mean") -> pd.Series:
    s = df[["_step", col]].dropna()
    return s.groupby(s["_step"] // BIN)[col].agg(how)


def watch_trigger(med: pd.Series) -> tuple[bool, int | None, list[float]]:
    """D23-watch on a per-1M-bin MEDIAN grad-norm series. Returns
    (fired, first bin of the firing run, the ratio series)."""
    base = float(med.iloc[:WATCH_BASE_BINS].median())
    ratios = (med / base).tolist()
    for i in range(len(ratios) - WATCH_RUN + 1):
        window = ratios[i:i + WATCH_RUN]
        if all(r >= WATCH_RATIO for r in window) and all(
            b >= a for a, b in zip(window, window[1:])
        ):
            return True, int(med.index[i]), ratios
    return False, None, ratios


def slope_per_10m(series: pd.Series, lo_bin: int) -> float:
    """OLS slope over bins >= lo_bin, scaled to per-10M-steps."""
    tail = series[series.index >= lo_bin]
    if len(tail) < 3:
        return float("nan")
    coef = np.polyfit(tail.index.astype(float), tail.values, 1)[0]
    return coef * 10.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", default="runs")
    ap.add_argument("--out", default="results/d22")
    ap.add_argument("--lanes", default=",".join(str(s) for s in LANES),
                    help="comma-separated seeds")
    ap.add_argument("--run-prefix", default=RUN_PREFIX,
                    help="run dir name is <prefix><seed>")
    ap.add_argument("--anchor-bins", default=",".join(str(b) for b in ANCHOR_BINS),
                    help="1M-bin indices quoted in the summary (bin b prints as b+1 M); "
                         "the lane's LAST bin is always appended")
    ap.add_argument("--slope-from-bin", type=int, default=SLOPE_FROM_BIN,
                    help="OLS late-slope is fit over bins >= this")
    ap.add_argument("--late-from-bin", type=int, default=LATE_FROM_BIN,
                    help="selfplay/winrate_latest mean is taken over bins >= this")
    ap.add_argument("--wr-window", type=int, default=5,
                    help="eval/win_rate smoothing/final window, in eval points")
    ap.add_argument("--watch", action="store_true",
                    help="also print the D23-watch median-grad-norm trigger")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lanes = tuple(int(s) for s in args.lanes.split(","))
    anchors = tuple(int(b) for b in args.anchor_bins.split(","))
    w = args.wr_window

    rows = []
    for seed in lanes:
        df = pd.read_csv(Path(args.runs_root) / f"{args.run_prefix}{seed}" / "history.csv")
        b = {col: binned(df, col) for col in SERIES}
        wr = df[["_step", "eval/win_rate"]].dropna()
        sp = binned(df, "selfplay/winrate_latest")

        ev, ent = b["loss/explained_variance"], b["loss/entropy"]
        last = int(ev.index[-1])
        labels = "/".join([f"{a + 1}M" for a in anchors] + [f"{last + 1}M"])
        wr_final = wr["eval/win_rate"].iloc[-w:].mean()
        wr_smooth = wr["eval/win_rate"].rolling(w, min_periods=w).mean()
        wr_peak = wr_smooth.max()
        peak_at = wr.loc[wr_smooth.idxmax(), "_step"]  # idxmax is a df label, not a position

        def traj(s: pd.Series) -> str:
            return " / ".join(f"{s.get(a, np.nan):.3f}" for a in (*anchors, last))

        print(f"\n=== s{seed} ===")
        print(f"  EV      {labels}: {traj(ev)}   "
              f"late slope (>={args.slope_from_bin}M, per 10M): "
              f"{slope_per_10m(ev, args.slope_from_bin):+.4f}")
        print(f"  entropy {labels}: {traj(ent)}   "
              f"late slope (>={args.slope_from_bin}M, per 10M): "
              f"{slope_per_10m(ent, args.slope_from_bin):+.4f}")
        print(f"  eval/win_rate: final({w}-pt) {wr_final:.3f}, peak({w}-pt) {wr_peak:.3f} "
              f"at {peak_at/1e6:.1f}M, peak-final gap {wr_peak - wr_final:+.3f}")
        print(f"  selfplay wr_latest bins >={args.late_from_bin} mean: "
              f"{sp[sp.index >= args.late_from_bin].mean():.3f}")
        print(f"  approx_kl {last + 1}M: {b['loss/approx_kl'].iloc[-1]:.4f}   "
              f"grad_norm {last + 1}M: {b['loss/grad_norm'].iloc[-1]:.3f}")
        if args.watch:
            med = binned(df, WATCH_SERIES, "median")
            fired, at, ratios = watch_trigger(med)
            print(f"  D23-WATCH (median pre-clip grad_norm, bins-0-3 median "
                  f"{float(med.iloc[:WATCH_BASE_BINS].median()):.3f}): "
                  f"max bin ratio {max(ratios):.2f} -> "
                  + (f"FIRES over bins {at}-{at + WATCH_RUN - 1} "
                     f"(ratios {'/'.join(f'{r:.1f}' for r in ratios[at:at + WATCH_RUN])}); "
                     f"the header labels such a fire by its LAST bin, "
                     f"{at + WATCH_RUN - 1}" if fired else "no fire"))

        for col in SERIES + ["selfplay/winrate_latest"]:
            series = sp if col == "selfplay/winrate_latest" else b[col]
            for bin_idx, val in series.items():
                rows.append({"seed": seed, "metric": col, "bin_m": bin_idx, "value": val})
        wr_out = wr.copy()
        wr_out["seed"] = seed
        wr_out.to_csv(out / f"winrate_s{seed}.csv", index=False)

    pd.DataFrame(rows).to_csv(out / "binned_trajectories.csv", index=False)
    print(f"\nwrote {out}/binned_trajectories.csv + per-lane winrate CSVs")


if __name__ == "__main__":
    main()
