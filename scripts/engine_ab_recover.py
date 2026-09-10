#!/usr/bin/env python
"""Rebuild an A/B result JSON from the queue log when the summary step crashed.

WHY THIS EXISTS. On 2026-09-10 `engine_ab_speed.py` ran all four arms of
variant 1 correctly and then died on the last line of `main()` with
`NameError: name 'math' is not defined` — an import I never added, on a branch
only reached when there is more than one replicate to take an sd over. The
RUNS were fine; only the summary and the JSON write were lost. Since each arm
prints its wall clock as it finishes, the headline ratio is fully recoverable
from the log, and re-running 90 minutes of training to recover a division would
be absurd.

WHAT IS NOT RECOVERABLE: `speedup_steady_state`. That is computed from each run
dir's history.csv, and consecutive variants reuse the same run-dir names, so a
later variant deletes the earlier one's. The wall-clock ratio — the headline —
is unaffected.

    python scripts/engine_ab_recover.py --variant 1 --engine-k 256 \\
        --out results/engine_a1/ab_speed_k256.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import statistics as st
import time

LOG = pathlib.Path("logs/post_lane_queue.log")


def parse(variant: int, log: pathlib.Path) -> dict[str, list]:
    lines = log.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if f"A/B variant {variant}" in l)
    try:
        end = next(i for i, l in enumerate(lines) if f"variant {variant} rc=" in l)
    except StopIteration:
        end = len(lines)
    arms: dict[str, list] = {"node": [], "engine": []}
    cur = None
    for l in lines[start:end]:
        m = re.search(r"\[(\d)/\d\]\s+(node|engine)\s+rep\s+(\d)", l)
        if m:
            cur = (m.group(2), int(m.group(1)), int(m.group(3)))
            continue
        m2 = re.search(r"rc=(\d+)\s+wall=([\d.]+)s\s+([\d.]+) steps/s", l)
        if m2 and cur:
            arms[cur[0]].append({
                "arm": cur[0], "slot": cur[1], "replicate": cur[2],
                "rc": int(m2.group(1)), "wall_seconds": float(m2.group(2)),
                "steps_per_sec": float(m2.group(3)), "steady_state": None,
            })
            cur = None
    return arms


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--variant", type=int, required=True)
    ap.add_argument("--engine-k", type=int, required=True)
    ap.add_argument("--steps", type=int, default=1_000_000)
    ap.add_argument("--width", type=int, default=1)
    ap.add_argument("--order", default="ABBA")
    ap.add_argument("--log", type=pathlib.Path, default=LOG)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    args = ap.parse_args(argv)

    arms = parse(args.variant, args.log)
    nw = [r["wall_seconds"] for r in arms["node"] if r["rc"] == 0]
    ew = [r["wall_seconds"] for r in arms["engine"] if r["rc"] == 0]
    if not (nw and ew):
        raise SystemExit(f"variant {args.variant}: no completed arms found in {args.log}")
    pairs = [n / e for n, e in zip(nw, ew)]

    out = {
        "question": "wall-clock seconds to train the SAME dose, old way vs new way",
        "dose_steps": args.steps, "width": args.width,
        "engine_k": args.engine_k, "matched_concurrency": args.engine_k == 8,
        "arms": arms, "order": args.order,
        "replicates": {a: len(arms[a]) for a in arms},
        "per_pair_speedup": pairs,
        "speedup_wall_clock": st.fmean(pairs),
        "speedup_sd": st.stdev(pairs) if len(pairs) > 1 else None,
        "speedup_se": (st.stdev(pairs) / len(pairs) ** 0.5) if len(pairs) > 1 else None,
        "speedup_steady_state": None,
        "showdown_simulator_workers": 4,
        "recovered": True,
        "recovery_note":
            "REBUILT FROM THE QUEUE LOG. All four arms ran to completion; the "
            "harness then died on the last line of main() with a missing "
            "`math` import, losing only the summary and the JSON write. Wall "
            "clocks are the harness's own per-arm prints, so the headline "
            "ratio is exactly what it would have written. "
            "`speedup_steady_state` is NULL and unrecoverable: it reads each "
            "run dir's history.csv, and the next variant reuses those dir "
            "names and deleted them.",
        "disclosures": [
            f"ONE LANE each, width {args.width}. This is not a fleet number."
            if args.width == 1 else
            f"WIDTH {args.width}: wall is first launch to last exit.",
            f"ALTERNATED {args.order} with {len(nw)}/{len(ew)} completed "
            "replicates; the ratio is the mean of PER-PAIR ratios, so a "
            "monotone drift in the box cancels rather than landing on "
            "whichever arm ran second. The sd is across pairs and is an "
            "empirical error bar, not an assumption.",
            f"engine k={args.engine_k}; "
            + ("MATCHED to the Node arm's concurrency 8, so the COLLECTOR is "
               "the only delta" if args.engine_k == 8 else
               "the production setting, so this is old-way vs new-way and NOT "
               "a controlled test of the collector alone"),
            "evals OFF in both arms; the locked protocol stays on the server "
            "either way, so including it would add the same constant to both",
            "the Showdown server ran with simulator: 4 (CLAUDE.md rule 5), "
            "checked at launch by the harness that produced these runs",
            "ONLY the wall-clock ratio survived the harness crash; the "
            "steady-state ratio, which excludes startup, is not available for "
            "this variant.",
        ],
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"variant {args.variant}: {out['speedup_wall_clock']:.3f}x  "
          + "per-pair " + ", ".join(f"{p:.3f}" for p in pairs)
          + (f"  sd {out['speedup_sd']:.4f}" if out["speedup_sd"] else ""))
    print(f"  node {st.fmean(nw)/60:.1f} min/run   engine {st.fmean(ew)/60:.1f} min/run")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
