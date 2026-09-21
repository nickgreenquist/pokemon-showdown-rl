#!/usr/bin/env python
"""The 4.12 screen's MECHANICAL read (configs/showdown_r6_batch12m.yaml header), so the
GO / FALLBACK decision is computed, not eyeballed, at the moment it is needed.

    python scripts/r6_batch12m_read.py [--screen runs/showdown_r6_batch12m_s204 runs/showdown_r6_batch12m_s212]
        [--w runs/showdown_monster200m_w_s104 ...] [--horizon 12000000] [--json-out ...]

Per 1M-step bin, for the screen lanes and for the W lanes' OWN first 12M (the schedule is
matched by construction: the screen runs the first 12M of the 200M anneal): the median
per-update loss/approx_kl and the means of loss/clip_frac, loss/entropy,
loss/explained_variance, loss/adv_std, time/update_sec, time/collect_sec. Rows without a
loss/approx_kl value (eval / rollout rows) are dropped. A missing history.csv is extracted
with scripts/extract_history.py.

THE PRE-STATED RULE (the screen's header, restated): GO for trio B iff
  (a) approx_kl in [0.005, 0.06] -- the per-bin MEDIAN in every bin after the first 1M, on
      every screen lane (a collapse below 1e-3 is the header's fallback trigger; the band
      is the GO condition);
  (b) entropy still falling -- OPERATIONALIZED 2026-09-21 BEFORE THE SCREEN RAN, after a dry
      run showed the W lanes' own entropy plateaus near 0.70 from ~2M on (a "last bin below
      the 6M bin" test fails the REFERENCE): every screen lane's last-bin entropy is below its
      first-bin entropy (the descent happened) AND within +-0.15 of the W lanes' mean last-bin
      entropy (neither collapsed toward 0 nor stalled high);
  (c) explained variance within 0.05 of the W lanes at the horizon -- the screen lanes'
      mean last-bin EV >= the W lanes' mean last-bin EV - 0.05.
FALLBACK otherwise: configs/showdown_r6_trio_b_fallback.yaml (epochs 4, minibatches 480,
lr 2.5e-4; batch x4 kept, steps per datum matched). time/update_sec vs collect_sec is
REPORTED (the "faster per datum" claim) but is not a GO input, and the window in which the
400k smokes ran beside the screen is disclosed by whoever ran them. NEVER a win rate.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLS = ["loss/approx_kl", "loss/clip_frac", "loss/entropy", "loss/explained_variance",
        "loss/adv_std", "time/update_sec", "time/collect_sec"]
KL_BAND = (0.005, 0.06)
EV_TOL = 0.05
ENT_TOL = 0.15
BIN = 1_000_000


def load_bins(history_csv: str, horizon: int, bin_size: int = BIN,
              chunksize: int = 500_000) -> pd.DataFrame:
    """One row per 1M bin: the median kl and the means of the rest, from a (possibly huge)
    history.csv -- the W lanes' are ~775 MB -- streamed in chunks and cut at the horizon:
    the scan stops at the first chunk whose UNFILTERED max step reaches the horizon."""
    parts = []
    usecols = ["_step"] + COLS
    for chunk in pd.read_csv(history_csv, usecols=lambda c: c in usecols, chunksize=chunksize):
        raw_max = int(chunk["_step"].max()) if len(chunk) else 0
        chunk = chunk[chunk["_step"] <= horizon]
        if "loss/approx_kl" in chunk:
            chunk = chunk[chunk["loss/approx_kl"].notna()]
        if len(chunk):
            parts.append(chunk)
        if raw_max >= horizon:
            break
    if not parts:
        raise SystemExit(f"{history_csv}: no update rows at or below step {horizon}")
    d = pd.concat(parts)
    d["bin"] = (d["_step"] // bin_size).astype(int)
    d = d[d["bin"] < horizon // bin_size]
    agg = {"loss/approx_kl": "median"}
    agg.update({c: "mean" for c in COLS if c != "loss/approx_kl" and c in d})
    out = d.groupby("bin").agg(agg)
    out["n_updates"] = d.groupby("bin").size()
    return out


def ensure_history(run_dir: str) -> str:
    p = os.path.join(run_dir, "history.csv")
    if not os.path.exists(p):
        subprocess.run([sys.executable, os.path.join(REPO, "scripts/extract_history.py"), run_dir],
                       check=True)
    return p


def rule(screen: dict[str, pd.DataFrame], w: dict[str, pd.DataFrame], horizon: int) -> dict:
    """The GO / FALLBACK decision from per-lane bin tables. Pure; tested."""
    last = horizon // BIN - 1
    checks = {}
    kl_ok, kl_detail = True, {}
    for name, t in screen.items():
        bins = [b for b in t.index if 1 <= b <= last]
        vals = t.loc[bins, "loss/approx_kl"]
        bad = [int(b) for b, v in vals.items() if not (KL_BAND[0] <= v <= KL_BAND[1])]
        kl_detail[name] = {"min": float(vals.min()), "max": float(vals.max()), "bins_outside": bad}
        kl_ok &= not bad
    checks["a_kl_in_band"] = {"ok": bool(kl_ok), "band": KL_BAND, "per_lane": kl_detail}
    ent_ok, ent_detail = True, {}
    ent_w = float(np.mean([t.loc[last, "loss/entropy"] for t in w.values()]))
    for name, t in screen.items():
        e0, el = float(t.loc[0, "loss/entropy"]), float(t.loc[last, "loss/entropy"])
        ent_detail[name] = {"entropy_first_bin": e0, "entropy_last_bin": el}
        ent_ok &= (el < e0) and (abs(el - ent_w) <= ENT_TOL)
    checks["b_entropy_falling"] = {"ok": bool(ent_ok), "w_last_bin_entropy": ent_w, "tol": ENT_TOL,
                                   "per_lane": ent_detail}
    ev_s = float(np.mean([t.loc[last, "loss/explained_variance"] for t in screen.values()]))
    ev_w = float(np.mean([t.loc[last, "loss/explained_variance"] for t in w.values()]))
    checks["c_ev_within_tol"] = {"ok": bool(ev_s >= ev_w - EV_TOL), "screen_last_bin_ev": ev_s,
                                 "w_last_bin_ev": ev_w, "tol": EV_TOL}
    verdict = "GO" if all(c["ok"] for c in checks.values()) else "FALLBACK"
    # reported, not a GO input
    upd_s = float(np.mean([t["time/update_sec"].mean() for t in screen.values() if "time/update_sec" in t]))
    upd_w = float(np.mean([t["time/update_sec"].mean() for t in w.values() if "time/update_sec" in t]))
    col_s = float(np.mean([t["time/collect_sec"].mean() for t in screen.values() if "time/collect_sec" in t]))
    col_w = float(np.mean([t["time/collect_sec"].mean() for t in w.values() if "time/collect_sec" in t]))
    return {"verdict": verdict, "checks": checks,
            "time": {"screen_update_sec_per_update": upd_s, "w_update_sec_per_update": upd_w,
                     "screen_collect_sec_per_update": col_s, "w_collect_sec_per_update": col_w,
                     "note": "the screen's update covers 4x the data of a W update; compare per datum"}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen", nargs="+", default=[os.path.join(REPO, f"runs/showdown_r6_batch12m_s{s}") for s in (204, 212)])
    ap.add_argument("--w", nargs="+", default=[os.path.join(REPO, f"runs/showdown_monster200m_w_s{s}") for s in (104, 112, 120)])
    ap.add_argument("--horizon", type=int, default=12_000_000)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    screen = {os.path.basename(r): load_bins(ensure_history(r), args.horizon) for r in args.screen}
    w = {os.path.basename(r): load_bins(ensure_history(r), args.horizon) for r in args.w}
    cols = ["loss/approx_kl", "loss/clip_frac", "loss/entropy", "loss/explained_variance", "loss/adv_std"]
    print(f"4.12 SCREEN READ -- per-1M bins to {args.horizon:,}; screen = mean over {list(screen)}; W = mean over {list(w)}")
    print(f"{'bin':>5} | " + " | ".join(f"{c.split('/')[1][:8]:>8}s {c.split('/')[1][:8]:>8}w" for c in cols))
    for b in range(args.horizon // BIN):
        row = []
        for c in cols:
            vs = np.mean([t.loc[b, c] for t in screen.values() if b in t.index]) if any(b in t.index for t in screen.values()) else float("nan")
            vw = np.mean([t.loc[b, c] for t in w.values() if b in t.index]) if any(b in t.index for t in w.values()) else float("nan")
            row.append(f"{vs:9.4f} {vw:9.4f}")
        print(f"{b:>5} | " + " | ".join(row))
    r = rule(screen, w, args.horizon)
    for k, c in r["checks"].items():
        print(f"  {k}: {'OK' if c['ok'] else 'FAIL'}  {json.dumps({kk: vv for kk, vv in c.items() if kk != 'ok'})}")
    t = r["time"]
    print(f"  time (reported, not a GO input): update_sec/update screen {t['screen_update_sec_per_update']:.2f} vs W {t['w_update_sec_per_update']:.2f}; "
          f"collect_sec/update screen {t['screen_collect_sec_per_update']:.2f} vs W {t['w_collect_sec_per_update']:.2f} -- {t['note']}")
    print(f"VERDICT: {r['verdict']}  ({'trio B launches on configs/showdown_r6_trio_b.yaml' if r['verdict'] == 'GO' else 'trio B launches on configs/showdown_r6_trio_b_fallback.yaml'})")
    if args.json_out:
        os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump({"horizon": args.horizon, "screen": list(screen), "w": list(w), **r}, f, indent=2)
        print(f"-> {args.json_out}")


if __name__ == "__main__":
    main()
