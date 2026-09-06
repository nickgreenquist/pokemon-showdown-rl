"""gen4_wang50m IN-RUN METRIC GATES — the AGENT-owned half of GATE OWNERSHIP
(configs/gen4_wang50m.yaml: "the AGENT owns every METRIC gate (R0-1..6, H1,
K6, T2, T3, D-A, D-B, D-C, D-D) by reading each lane's offline wandb
history"). One lane per call; every band is the header's, restated here
with its evidence; nothing DECIDES — a STOP/KILL line is what the babysitter
acts on (exit 2), everything else is PASS / RECORD / INVESTIGATE / n/a.

    python scripts/gen4_wang50m_gates.py runs/gen4_wang50m_s200 --extract
    python scripts/gen4_wang50m_gates.py runs/gen4_wang50m_s200 --history runs/gen4_wang50m_s200/history_merged.csv

--extract runs scripts/extract_history.py first (a resume SPLITS the history:
merge to history_merged.csv and pass --history; this script refuses a
non-monotone _step). D-A loads the rungs nearest >= 5M / 25M / 50M and checks
the STORED optimizer lr against the closed form x = ((u - 1) * rollout *
num_envs) / lr_anneal_steps, lr0 * (a x + 1)^-b, to 1e-12 relative (the
u * ... form is off by one update and would STOP every lane). D-B is the
REALIZED dStep/dWall over >= 30-min windows post-1M (RECORD < 173,
STOP-AND-INVESTIGATE < 102 in 2 consecutive windows; expected 203, band
[173, 234] — PROVISIONAL, re-based from the fleet's first conforming windows).
Windows overlapping a named non-conforming interval (--nonconforming
START,END in epoch seconds; the clone chain) are marked and excluded.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable

BANDS = {
    "r0_1_entropy": (1.3, 2.1), "r0_steps": 250_000,
    "r0_3_ratio": (0.7, 1.3), "r0_3_lag_max": 2, "r0_3_dropped_frac": 0.01,
    "k6_entropy_floor": 0.15, "k6_before_step": 25_000_000,
    "t2_clip_frac": 0.90, "t3_kl": 0.5,
    "d_a_rel_tol": 1e-12, "d_a_grid": (5_000_000, 25_000_000, 50_000_000),
    "d_b_expected": 203, "d_b_record_below": 173, "d_b_stop_below": 102,
    "r0_5_first_rung_min": 60,
}

LINES: list[tuple[str, str, str]] = []  # (gate, verdict, evidence)
def gate(name: str, verdict: str, evidence: str) -> None:
    LINES.append((name, verdict, evidence))
    print(f"{name:<6} {verdict:<12} {evidence}")


def load_history(run: Path, history: Path | None, extract: bool) -> pd.DataFrame:
    if extract:
        subprocess.run([PY, str(REPO / "scripts/extract_history.py"), str(run)], check=True,
                       stdout=subprocess.DEVNULL)
    path = history or run / "history.csv"
    df = pd.read_csv(path)
    if "_step" not in df or "_timestamp" not in df:
        raise SystemExit(f"{path}: no _step/_timestamp columns")
    df = df.sort_values("_timestamp", kind="stable").reset_index(drop=True)
    steps = df["_step"].to_numpy()
    if np.any(np.diff(steps) < 0):
        raise SystemExit(f"{path}: _step is not monotone — a resume split the history; merge to history_merged.csv first")
    return df


def consecutive(mask: np.ndarray, k: int) -> bool:
    run = 0
    for m in mask:
        run = run + 1 if m else 0
        if run >= k:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run", type=Path)
    ap.add_argument("--history", type=Path)
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--wave-log", type=Path, default=REPO / "logs/gen4_wang50m_wave.log")
    ap.add_argument("--db-min-step", type=float, default=1e6, help="D-B reads post-1M only")
    ap.add_argument("--db-window-min", type=float, default=30.0)
    ap.add_argument("--nonconforming", action="append", default=[],
                    help="START,END epoch seconds of a non-conforming interval (repeatable)")
    ap.add_argument("--gap-sec", type=float, default=300.0,
                    help="a gap between consecutive update rows longer than this marks the windows containing it non-conforming (a resume's downtime)")
    ap.add_argument("--da-checkpoint", type=Path, action="append", default=[],
                    help="also run the D-A closed-form check on this checkpoint (e.g. the live checkpoint.pt; repeatable)")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    run = args.run
    df = load_history(run, args.history, args.extract)
    upd = df[df["loss/entropy"].notna()].reset_index(drop=True) if "loss/entropy" in df else df.iloc[0:0]
    print(f"lane {run.name}: {len(df)} history rows, {len(upd)} update rows, last _step {int(df['_step'].max())}")

    # ---- R0-1 entropy band on the first 250k --------------------------------
    early = upd[upd["_step"] <= BANDS["r0_steps"]]
    if len(early):
        lo, hi = early["loss/entropy"].min(), early["loss/entropy"].max()
        ok = BANDS["r0_1_entropy"][0] <= lo and hi <= BANDS["r0_1_entropy"][1]
        gate("R0-1", "PASS" if ok else "INVESTIGATE",
             f"entropy on <=250k: min {lo:.3f} max {hi:.3f} band {BANDS['r0_1_entropy']} ({len(early)} updates)")
    else:
        gate("R0-1", "n/a", "no update rows <= 250k yet")

    # ---- R0-2 clip_frac > 0 on every update -----------------------------------
    if len(upd):
        zero = int((upd["loss/clip_frac"] <= 0.0).sum())
        gate("R0-2", "PASS" if zero == 0 else "KILL",
             f"clip_frac == 0 on {zero}/{len(upd)} updates (first-250k band {early['loss/clip_frac'].min():.3f}–{early['loss/clip_frac'].max():.3f})"
             if len(early) else f"clip_frac == 0 on {zero}/{len(upd)} updates")

    # ---- R0-3 / H1 harvest health ---------------------------------------------
    hk = ["harvest/rows_this_update", "harvest/seat1_rows", "harvest/version_lag_max",
          "harvest/rows_dropped", "harvest/rows", "harvest/discarded", "harvest/empty", "harvest/episodes"]
    if len(upd) > 1 and all(k in upd for k in hk):
        h = upd.iloc[1:]
        absent = int(h["harvest/rows_this_update"].isna().sum())
        ratio = (h["harvest/rows_this_update"] / h["harvest/seat1_rows"]).to_numpy()
        lag = h["harvest/version_lag_max"].to_numpy()
        dropped = (h["harvest/rows_dropped"] / h["harvest/rows"].replace(0, np.nan)).fillna(0).to_numpy()
        disc = h["harvest/discarded"].fillna(0).to_numpy()
        empty_frac = float(h["harvest/empty"].fillna(0).sum() / max(h["harvest/episodes"].fillna(0).sum(), 1))
        breach = (~((ratio >= BANDS["r0_3_ratio"][0]) & (ratio <= BANDS["r0_3_ratio"][1]))
                  | (lag > BANDS["r0_3_lag_max"]) | (dropped >= BANDS["r0_3_dropped_frac"]) | (disc != 0))
        breach = np.where(np.isnan(ratio), True, breach)
        nb = int(breach.sum())
        v = "KILL" if (absent or nb) else "PASS"
        gate("R0-3", v, f"harvest keys absent {absent}; ratio min {np.nanmin(ratio):.3f} max {np.nanmax(ratio):.3f} "
                        f"band {BANDS['r0_3_ratio']}; version_lag_max max {int(np.nanmax(lag))} (<= 2); dropped max "
                        f"{np.nanmax(dropped)*100:.2f}% (< 1%); discarded sum {int(np.nansum(disc))} (== 0); "
                        f"empty {empty_frac*100:.2f}% of episodes (RECORD; investigate > 1%); breaches {nb}/{len(h)}")
        # H1: 3 consecutive rungs (500k buckets) with any breach -> STOP
        buckets = (h["_step"].to_numpy() // 500_000).astype(int)
        per_bucket = [bool(breach[buckets == b].any()) for b in np.unique(buckets)]
        h1 = consecutive(np.array(per_bucket, dtype=bool), 3)
        gate("H1", "STOP" if h1 else ("RECORD" if any(per_bucket) else "PASS"),
             f"rung buckets breached {sum(per_bucket)}/{len(per_bucket)}; 3 consecutive -> STOP")
    else:
        gate("R0-3", "n/a", "fewer than 2 update rows or harvest keys missing")

    # ---- R0-4 / D-C eval -------------------------------------------------------
    ev = df[df["eval/win_rate"].notna()] if "eval/win_rate" in df else df.iloc[0:0]
    if len(ev):
        first = float(ev["eval/win_rate"].iloc[0])
        gate("R0-4", "PASS" if 0.0 <= first < 1.0 else "INVESTIGATE", f"first eval/win_rate {first:.3f} at step {int(ev['_step'].iloc[0])}")
        tail = ", ".join(f"{w:.2f}@{int(s)/1e6:.1f}M" for s, w in zip(ev["_step"].tail(5), ev["eval/win_rate"].tail(5)))
        gate("D-C", "RECORD", f"{len(ev)} in-loop evals (n=100, NOT ACTIONABLE); last 5: {tail}")
    else:
        gate("R0-4", "n/a", "no eval yet")

    # ---- R0-5 first rung within 60 min of launch (wave log) ---------------------
    rungs = sorted(run.glob("ckpt_*.pt"))
    launched = None
    if args.wave_log.exists():
        seed = run.name.rsplit("_s", 1)[-1]
        for line in args.wave_log.read_text().splitlines():
            if f"lane s{seed}: launched" in line:
                launched = pd.Timestamp(line[1:line.index("]")])
    if launched is not None and rungs:
        first_rung = min(rungs, key=lambda p: p.stat().st_mtime)
        mins = (first_rung.stat().st_mtime - launched.timestamp()) / 60
        gate("R0-5", "PASS" if mins <= BANDS["r0_5_first_rung_min"] else "RECORD",
             f"first rung {first_rung.name} {mins:.0f} min after the (last) launch line (<= 60)")
    elif launched is not None:
        mins = (pd.Timestamp.utcnow().timestamp() - launched.timestamp()) / 60
        gate("R0-5", "PASS" if mins <= BANDS["r0_5_first_rung_min"] else "KILL",
             f"no rung yet, {mins:.0f} min since launch (deadline 60)")
    else:
        gate("R0-5", "n/a", "no launch line in the wave log")

    # ---- R0-6 / T3 non-finite loss -------------------------------------------
    loss_cols = [c for c in upd.columns if c.startswith("loss/")]
    if len(upd):
        nonfinite = int((~np.isfinite(upd[loss_cols].to_numpy(dtype=float))).sum())
        gate("R0-6", "PASS" if nonfinite == 0 else "KILL", f"non-finite loss/* readings: {nonfinite}")

    # ---- K6 / T2 / T3 -------------------------------------------------------------
    if len(upd):
        pre = upd[upd["_step"] < BANDS["k6_before_step"]]
        k6 = consecutive((pre["loss/entropy"] < BANDS["k6_entropy_floor"]).to_numpy(), 2)
        gate("K6", "STOP" if k6 else "PASS", f"entropy min {upd['loss/entropy'].min():.3f} (floor 0.15 x2 before 25M; PROVISIONAL)")
        t2 = consecutive((upd["loss/clip_frac"] >= BANDS["t2_clip_frac"]).to_numpy(), 3)
        gate("T2", "STOP" if t2 else "PASS", f"clip_frac max {upd['loss/clip_frac'].max():.3f} (>= 0.90 x3 -> STOP); last {upd['loss/clip_frac'].iloc[-1]:.3f}")
        t3 = consecutive((upd["loss/approx_kl"] >= BANDS["t3_kl"]).to_numpy(), 3)
        gate("T3", "STOP" if t3 else "PASS", f"approx_kl max {upd['loss/approx_kl'].max():.4f} (>= 0.5 x3 -> STOP)")

    # ---- D-A anneal liveness from the stored optimizer lr ----------------------
    try:
        import torch
        targets = []
        for g in BANDS["d_a_grid"]:
            cands = [p for p in rungs if int(p.stem.split("_")[1]) >= g]
            if not cands:
                gate("D-A", "n/a", f"no rung >= {g/1e6:.0f}M yet")
                continue
            targets.append(min(cands, key=lambda q: int(q.stem.split("_")[1])))
        targets += list(args.da_checkpoint)
        for p in targets:
            ck = torch.load(p, map_location="cpu", weights_only=False)
            cfg = ck["config"]; a = cfg["agent"]
            u = int(ck["agent"]["updates"])
            rows = int(a["rollout_steps"]) * int(cfg["num_envs"])
            x = min(1.0, (u - 1) * rows / float(a["lr_anneal_steps"]))
            frac = (float(a["lr_power_a"]) * x + 1.0) ** (-float(a["lr_power_b"]))
            exp_actor = float(a["lr"]) * float(a.get("actor_lr_scale", 1.0)) * frac
            exp_critic = float(a["lr"]) * frac
            groups = ck["agent"]["optimizer"]["param_groups"]
            got_a, got_c = float(groups[0]["lr"]), float(groups[1]["lr"])
            ok = (math.isclose(got_a, exp_actor, rel_tol=BANDS["d_a_rel_tol"])
                  and math.isclose(got_c, exp_critic, rel_tol=BANDS["d_a_rel_tol"]))
            gate("D-A", "PASS" if ok else "STOP",
                 f"{p.name}: u={u} x={x:.6f} stored lr actor {got_a:.6e} critic {got_c:.6e} vs closed form {exp_actor:.6e}/{exp_critic:.6e} (1e-12 rel)")
    except Exception as exc:  # a checkpoint that will not load is itself a finding
        gate("D-A", "INVESTIGATE", f"could not read a rung: {exc!r}")

    # ---- D-B realized throughput over >= 30-min windows post-1M --------------------
    post = upd[upd["_step"] >= args.db_min_step]
    if len(post) >= 2:
        t = post["_timestamp"].to_numpy(dtype=float); s = post["_step"].to_numpy(dtype=float)
        nc = []
        for spec in args.nonconforming:
            a_, b_ = (float(v) for v in spec.split(","))
            nc.append((a_, b_))
        w = args.db_window_min * 60.0
        # A resume leaves a wall-clock GAP with no rows (the dead process, the
        # room wait, the restart): any window containing a gap > --gap-sec is
        # NON-CONFORMING by construction (dStep/dWall would read the downtime
        # as slowness). Gaps are found between consecutive update rows.
        gaps = [(float(t[k]), float(t[k + 1])) for k in range(len(t) - 1) if t[k + 1] - t[k] > args.gap_sec]
        nc = nc + gaps
        rates, flags = [], []
        t0 = t[0]
        while t0 + w <= t[-1]:
            i = int(np.searchsorted(t, t0)); j = int(np.searchsorted(t, t0 + w, side="right")) - 1
            if j > i and t[j] > t[i]:
                r = (s[j] - s[i]) / (t[j] - t[i])
                bad = any(not (t[j] < a_ or t[i] > b_) for a_, b_ in nc)
                rates.append(r); flags.append(bad)
            t0 += w
        conf = [r for r, bad in zip(rates, flags) if not bad]
        whole = (s[-1] - s[0]) / (t[-1] - t[0])
        if conf:
            below_stop = [r < BANDS["d_b_stop_below"] for r in conf]
            stop = consecutive(np.array(below_stop), 2)
            record = any(r < BANDS["d_b_record_below"] for r in conf)
            v = "STOP" if stop else ("RECORD" if record else "PASS")
            gate("D-B", v, f"{len(conf)} conforming {args.db_window_min:.0f}-min windows (of {len(rates)}; {sum(flags)} non-conforming excluded, {len(gaps)} resume gap(s) > {args.gap_sec:.0f} s): "
                          f"min {min(conf):.0f} median {float(np.median(conf)):.0f} last {conf[-1]:.0f} steps/s; whole post-{args.db_min_step/1e6:.0f}M {whole:.0f}; "
                          f"expected {BANDS['d_b_expected']}, RECORD < 173, STOP < 102 x2 (PROVISIONAL band)")
        else:
            gate("D-B", "n/a", f"no full {args.db_window_min:.0f}-min window post-{args.db_min_step/1e6:.0f}M yet (whole-span rate {whole:.0f} steps/s over {(t[-1]-t[0])/60:.0f} min)")
    else:
        gate("D-B", "n/a", f"fewer than 2 update rows past step {args.db_min_step:.0f}")

    # ---- D-D record-only ----------------------------------------------------------
    if "selfplay/winrate_latest" in df and df["selfplay/winrate_latest"].notna().any():
        w = df["selfplay/winrate_latest"].dropna()
        gate("D-D", "RECORD", f"selfplay/winrate_latest mean {w.mean():.3f} over {len(w)} readings (~0.5 by construction at pool_size 1; no forgetting detector on this arm)")

    verdicts = {v for _, v, _ in LINES}
    worst = "STOP" if verdicts & {"STOP", "KILL"} else ("INVESTIGATE" if "INVESTIGATE" in verdicts else ("RECORD" if "RECORD" in verdicts else "PASS"))
    print(f"SUMMARY {run.name}: {worst}")
    if args.json:
        args.json.write_text(json.dumps({"lane": run.name, "worst": worst,
                                         "gates": [{"gate": g, "verdict": v, "evidence": e} for g, v, e in LINES]}, indent=1) + "\n")
    return 2 if worst == "STOP" else 0


if __name__ == "__main__":
    sys.exit(main())
