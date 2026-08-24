"""CH4 R1 BI-8 — recomputed self-play switch-rate baseline for E-b.

The banked R5b D-9 rates (0.143/0.197/0.152/0.173) include force-switch
rows — 100%-switch rows that inflate the rate by a definitional ~+0.09
(review 1 MA-2). PINNED FILTER: all non-smoke chunks of
results/ch3_r5b/collect (both mirror seats — the two seats are the same
policy in a mirror), column policy_argmax, rows where ANY move (action
6-9) is legal (mask[:,6:].any(axis=1)); switch actions are 0-5.
Committed BEFORE the archaeology is graded (this file + its output).
"""
import glob
import json

import numpy as np

out = {}
for lane in ("s62", "s63", "s64", "s65"):
    files = sorted(f for f in glob.glob(f"results/ch3_r5b/collect/{lane}.chunk*.npz")
                   if "smoke" not in f)
    tot = kept = sw = banked_sw = 0
    for f in files:
        d = np.load(f)
        mask, pa = d["mask"], d["policy_argmax"]
        free = mask[:, 6:].any(axis=1)          # a move is legal -> a real choice
        tot += len(pa)
        kept += int(free.sum())
        sw += int((pa[free] < 6).sum())
        banked_sw += int((pa < 6).sum())
    out[lane] = {
        "chunks": len(files), "rows_total": tot, "rows_kept": kept,
        "force_switch_rows": tot - kept,
        "policy_argmax_switch_rate": sw / kept,
        "banked_style_rate_all_rows": banked_sw / tot,
    }
rates = [v["policy_argmax_switch_rate"] for v in out.values()]
out["_band"] = {"min": min(rates), "max": max(rates),
                "note": "LOOSE reference (search-play state distribution); "
                        "E-b band = FG sw_us within +/-0.06 of [min,max]"}
with open("results/ch4_r1_offsh/sp_baseline.json", "w") as f:
    json.dump(out, f, indent=2)
print(json.dumps(out, indent=2))
