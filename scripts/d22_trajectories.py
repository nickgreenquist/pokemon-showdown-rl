"""D22 reads 1+2 (DESIGN §12): EV + entropy trajectories from the 50M lanes.

    python scripts/d22_trajectories.py [--runs-root runs] [--out results/d22]

Bins loss/explained_variance and loss/entropy (per-update series, ~48k points)
into 1M-step bins per lane, alongside eval/win_rate (250k cadence) and
selfplay/winrate_latest. Prints the numbers the §12 decision rule consumes:
plateau level, late-run slope, entropy floor, and the win-rate peak-vs-final
gap per lane (the "flat win rate" clause). CSV of the binned series goes to
--out for figures/re-reads.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

LANES = (35, 36, 37)
BIN = 1_000_000
SERIES = ["loss/explained_variance", "loss/entropy", "loss/approx_kl", "loss/grad_norm"]


def binned(df: pd.DataFrame, col: str) -> pd.Series:
    s = df[["_step", col]].dropna()
    return s.groupby(s["_step"] // BIN)[col].mean()


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
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for seed in LANES:
        df = pd.read_csv(Path(args.runs_root) / f"showdown_sp_struct50m_s{seed}" / "history.csv")
        b = {col: binned(df, col) for col in SERIES}
        wr = df[["_step", "eval/win_rate"]].dropna()
        sp = binned(df, "selfplay/winrate_latest")

        ev, ent = b["loss/explained_variance"], b["loss/entropy"]
        wr_final = wr["eval/win_rate"].iloc[-5:].mean()  # last ~1.25M of curve
        wr_smooth = wr["eval/win_rate"].rolling(5, min_periods=5).mean()
        wr_peak = wr_smooth.max()
        peak_at = wr.loc[wr_smooth.idxmax(), "_step"]  # idxmax is a df label, not a position
        print(f"\n=== s{seed} ===")
        print(f"  EV      5M/12M/25M/50M: {ev.get(4, np.nan):.3f} / {ev.get(11, np.nan):.3f} / "
              f"{ev.get(24, np.nan):.3f} / {ev.iloc[-1]:.3f}   "
              f"late slope (>=35M, per 10M): {slope_per_10m(ev, 35):+.4f}")
        print(f"  entropy 5M/12M/25M/50M: {ent.get(4, np.nan):.3f} / {ent.get(11, np.nan):.3f} / "
              f"{ent.get(24, np.nan):.3f} / {ent.iloc[-1]:.3f}   "
              f"late slope (>=35M, per 10M): {slope_per_10m(ent, 35):+.4f}")
        print(f"  eval/win_rate: final(5-pt) {wr_final:.3f}, peak(5-pt) {wr_peak:.3f} "
              f"at {peak_at/1e6:.1f}M, peak-final gap {wr_peak - wr_final:+.3f}")
        print(f"  selfplay wr_latest last-10M mean: {sp[sp.index >= 40].mean():.3f}")
        print(f"  approx_kl 50M: {b['loss/approx_kl'].iloc[-1]:.4f}   "
              f"grad_norm 50M: {b['loss/grad_norm'].iloc[-1]:.3f}")

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
