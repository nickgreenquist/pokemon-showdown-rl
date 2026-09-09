#!/usr/bin/env python
"""Grade gate A-1 against configs/engine_a1.yaml. Reads only committed files.

The pre-reg's arithmetic, executed — so the verdict is not retyped by hand from
a header. Every constant here is the header's, and the header is the authority:
if the two disagree, the header wins and this file is the bug.

    python scripts/engine_a1_grade.py results/engine_a1/rung12m_s*.json \
        --out results/engine_a1/primary.json

WHAT IT WILL NOT DO. It will not grade a fleet with fewer than three lanes at
the rung (cell A1-VOID-K), it will not accept an eval whose cross-checks
disagree, and it will not promote P-AUC to co-primary unless the sidecar records
a ruling on RW-8. A "PASS" it prints without those is not a pass.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import statistics
import sys

import yaml

# --- the banked baseline, BY PROVENANCE (configs/engine_a1.yaml §B) -----------
BASE_END = 0.67211            # equal-weight mean of 0.6593333/0.6836667/0.6733333
BASE_AUC = 0.64597            # equal-weight mean of the three lane AUCs
BAND = 0.025                  # JOURNEY 7.5, verbatim
SIGMA_REF = 0.01454           # annealed family, 7 df (results/engine_a1/sigma.json)
SIGMA_CI_HI = 0.0296
N_LANES = 3
RUNG = 12_000_000
UPDATE = 30_720               # one update; the A1-RUNG tolerance
EVAL_INTERVAL = 250_000       # beyond this it is a different dose, not an overshoot
N_RUNGS = 48


def _auc(run_dir: pathlib.Path) -> tuple[float, int, str]:
    """Mean eval/win_rate over the in-loop rungs at 250k..12.0M.

    A resumed lane has NO history.csv — extract_history.py hard-fails on a split
    history — so history_merged.csv is read instead, and the row count is
    checked against the banked lanes' 48 before the number is used at all.
    """
    merged, plain = run_dir / "history_merged.csv", run_dir / "history.csv"
    path = merged if merged.exists() else plain
    if not path.exists():
        raise SystemExit(
            f"{run_dir}: no history.csv and no history_merged.csv. A resumed "
            "lane splits the wandb history and extract_history.py HARD-FAILS; "
            "run scripts/merge_history.py first (docs/landmines.md:268-283).")
    pts = {}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            w = r.get("eval/win_rate", "")
            if w in ("", None):
                continue
            try:
                step, val = int(float(r["_step"])), float(w)
            except (TypeError, ValueError):
                continue
            if step <= RUNG + EVAL_INTERVAL:
                pts[step] = val          # a resume overlaps steps; last wins
    vals = [pts[k] for k in sorted(pts)][:N_RUNGS]
    return (statistics.fmean(vals) if vals else float("nan"), len(vals), path.name)


def _load(paths: list[pathlib.Path]) -> list[dict]:
    lanes = []
    for p in sorted(paths):
        d = json.loads(p.read_text())
        wr, wfr = d["eval/win_rate"], d.get("wins_from_returns")
        # eval/win_rate is env-supplied outcome; wins_from_returns exists only
        # as the cross-check and the two must agree.
        if wfr is None or abs(wr - wfr) > 1e-9:
            raise SystemExit(f"{p}: eval/win_rate {wr} != wins_from_returns "
                             f"{wfr} — the cross-check disagrees; do not grade")
        if d.get("mask_desyncs", 0) != 0:
            raise SystemExit(f"{p}: mask_desyncs={d['mask_desyncs']} != 0")
        if d.get("episodes") != 3000:
            raise SystemExit(f"{p}: episodes={d.get('episodes')}, locked protocol is 3000")
        if "eval/no_outcome" in d:
            raise SystemExit(
                f"{p}: eval/no_outcome present ({d['eval/no_outcome']}). The "
                "banked evals ran under the all-or-nothing guard, so their "
                "missing==0 is proven; an arm-E eval that scores any episode "
                "as a non-win by default is not symmetric with them.")
        run = d.get("run_name", p.stem)
        lanes.append({"file": str(p), "run": run, "step": int(d["step"]),
                      "win_rate": float(wr),
                      "run_dir": pathlib.Path("runs") / run})
    return lanes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("evals", nargs="+", type=pathlib.Path)
    ap.add_argument("--prereg", type=pathlib.Path,
                    default=pathlib.Path("configs/engine_a1.prereg.yaml"))
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/primary.json"))
    args = ap.parse_args(argv)

    lanes = _load(args.evals)
    res: dict = {"lanes": lanes, "band": BAND, "baseline_endpoint": BASE_END,
                 "baseline_auc": BASE_AUC}

    # --- cell A1-VOID-K / A1-RUNG --------------------------------------------
    off = [l for l in lanes if abs(l["step"] - RUNG) > EVAL_INTERVAL]
    if len(lanes) < N_LANES or off:
        res.update({"cell": "A1-VOID-K", "pass": False,
                    "why": (f"{len(lanes)} lane(s) at the rung"
                            + (f"; off-dose lanes {[l['run'] for l in off]}" if off else "")
                            + " — DESCRIPTIVE ONLY; A-1 does not decide the switch")})
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(res, indent=2) + "\n")
        print(json.dumps(res, indent=2))
        return 1
    res["rung_overshoot"] = {l["run"]: l["step"] - RUNG for l in lanes}
    res["rung_note"] = ("graded at realized steps; "
                        + ("all within one update" if all(abs(l["step"] - RUNG) <= UPDATE for l in lanes)
                           else "A1-RUNG: a lane is >1 update off; realized step disclosed"))

    # --- P-END ----------------------------------------------------------------
    per_seed = [l["win_rate"] for l in lanes]
    pooled = statistics.fmean(per_seed)
    d_end = pooled - BASE_END
    sd_e = statistics.stdev(per_seed)
    # se_diff for the DISCLOSED POWER only — the pass rule is a fixed magnitude.
    # Larger of the pooled-binomial and the seed-clustered form.
    se_binom = math.sqrt(2 * pooled * (1 - pooled) / (3 * 3000))
    se_seed = math.sqrt((sd_e ** 2 + 0.01221 ** 2) / 2) * math.sqrt(2 / 3)
    se_diff = max(se_binom, se_seed)
    res["P_END"] = {"per_seed": {l["run"]: l["win_rate"] for l in lanes},
                    "pooled": pooled, "signed_delta": d_end, "seed_sd": sd_e,
                    "se_diff_binomial": se_binom, "se_diff_seed_clustered": se_seed,
                    "se_diff_quoted": se_diff, "delta_in_se": d_end / se_diff,
                    "inside_band": abs(d_end) < BAND}

    # --- P-AUC ----------------------------------------------------------------
    aucs, counts, srcs = [], {}, {}
    for l in lanes:
        a, n, src = _auc(l["run_dir"])
        aucs.append(a); counts[l["run"]] = n; srcs[l["run"]] = src
    auc = statistics.fmean(aucs)
    d_auc = auc - BASE_AUC
    bad = {r: n for r, n in counts.items() if n != N_RUNGS}
    res["P_AUC"] = {"per_lane": {l["run"]: a for l, a in zip(lanes, aucs)},
                    "arm_auc": auc, "signed_delta": d_auc,
                    "rung_counts": counts, "sources": srcs,
                    "inside_band": abs(d_auc) < BAND,
                    "denominator_ok": not bad,
                    "note": (f"rung count != {N_RUNGS} for {bad} — REPORTED and "
                             "re-extracted; never graded on a different "
                             "denominator" if bad else "")}

    # --- RW-8 gates whether P-AUC can fail the run ----------------------------
    side = yaml.safe_load(args.prereg.read_text()) if args.prereg.exists() else {}
    rw8 = (side.get("ratified_decisions") or {}).get("RW-8")
    co_primary = str(rw8).lower().startswith("co-primary") if rw8 else False
    res["P_AUC"]["role"] = "CO-PRIMARY" if co_primary else "SECONDARY-DESCRIPTIVE (RW-8 unanswered)"

    if co_primary:
        if res["P_END"]["inside_band"] and res["P_AUC"]["inside_band"]:
            cell = "A1-PASS"
        elif res["P_END"]["inside_band"] != res["P_AUC"]["inside_band"]:
            cell = "A1-SPLIT"
        else:
            cell = "A1-FAIL"
    else:
        cell = "A1-PASS" if res["P_END"]["inside_band"] else "A1-FAIL"
    res["cell"] = cell
    res["pass"] = cell == "A1-PASS" and (not co_primary or res["P_AUC"]["denominator_ok"])

    res["disclosures_that_travel"] = [
        f"A-1 SIGNED delta {d_end:+.5f} (endpoint) and {d_auc:+.5f} (AUC) — these "
        "ride every gen-1 credit sentence produced on the engine path, forever (N-ENG)",
        "A-1 is a gross-breakage SCREEN, not an equivalence test; no TOST was run",
        f"at sigma {SIGMA_CI_HI} (the reference class's own CI upper bound) this "
        "screen fails a truly-equivalent arm 30.1% of the time",
        "the band cannot distinguish 'matches async' from 'matches sync': an arm "
        "reproducing the sync fleet exactly lands at |D|=0.02322 and PASSES",
        "the credit line does NOT apply — A-1 asks whether a difference is absent",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2) + "\n")

    print(f"A-1 {cell}")
    print(f"  P-END  pooled {pooled:.5f} vs banked {BASE_END} -> {d_end:+.5f} "
          f"({d_end/se_diff:+.2f} se_diff, band {BAND}) "
          f"{'INSIDE' if res['P_END']['inside_band'] else 'OUTSIDE'}")
    print(f"  P-AUC  arm {auc:.5f} vs banked {BASE_AUC} -> {d_auc:+.5f} "
          f"{'INSIDE' if res['P_AUC']['inside_band'] else 'OUTSIDE'} "
          f"[{res['P_AUC']['role']}]")
    print(f"  written: {args.out}")
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
