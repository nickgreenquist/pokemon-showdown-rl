#!/usr/bin/env python
"""Render the A/B speed result as the ONE quotable speedup for this port.

WHY THIS EXISTS AS A SCRIPT AND NOT A PARAGRAPH SOMEONE TYPES. The port has
produced several speed numbers today and only one of them is an A/B. The
others are real measurements of real things and every one of them is a trap if
quoted as "the speedup":

  * 2.62x — divides an engine rate measured today by a Node rate banked
    2026-09-01. Different day, different box state, different neighbours. It is
    two measurements subtracted, not a comparison. NOT QUOTABLE.
  * 6,056 battles/s, 22,318 steps/s at K=256 (T-1 a/b) — COLLECTION ONLY, with
    no update in the denominator. `scripts/showdown_throughput.py`'s own
    docstring puts that overstatement at ~7x.
  * 1502 steps/s/lane at 3-wide (T-1 d) — an engine number with no Node arm
    beside it on the same box, same hour.

So this reads the A/B's JSON and prints the number with its scope attached,
and every disclosure the harness recorded travels with it. If someone quotes a
speedup for this port, it should be this output.

    python scripts/engine_speed_readout.py
    python scripts/engine_speed_readout.py --write docs/engine_port/SPEEDUP.md
"""

from __future__ import annotations

import argparse
import json
import pathlib

K256 = pathlib.Path("results/engine_a1/ab_speed_k256.json")
K8 = pathlib.Path("results/engine_a1/ab_speed_k8.json")


def _row(d: dict) -> dict:
    import statistics as st
    nw = [r["wall_seconds"] for r in d["arms"]["node"] if r["rc"] == 0]
    ew = [r["wall_seconds"] for r in d["arms"]["engine"] if r["rc"] == 0]
    return {
        "k": d["engine_k"],
        "matched": d["matched_concurrency"],
        "dose": d["dose_steps"],
        "reps": f"{len(nw)}/{len(ew)}",
        "node_min": st.fmean(nw) / 60 if nw else None,
        "engine_min": st.fmean(ew) / 60 if ew else None,
        "speedup": d.get("speedup_wall_clock"),
        "pairs": d.get("per_pair_speedup", []),
        "sd": d.get("speedup_sd"),
        "se": d.get("speedup_se"),
        "steady": d.get("speedup_steady_state"),
        "order": d.get("order"),
        "workers": d.get("showdown_simulator_workers"),
        "disclosures": d.get("disclosures", []),
        "measured_at": d.get("measured_at"),
    }


def render(rows: dict[str, dict]) -> str:
    L = []
    A = L.append
    A("# The pkmn/engine collector port — the measured speedup\n")
    A("**The question this answers:** how long does it take to train the same "
      "number of steps the old way (Node/Showdown server, poke-env, async "
      "collector) against the new way (in-process pkmn/engine)? Same dose, "
      "same box, back to back, one lane each.\n")

    any_row = next(iter(rows.values()))
    A(f"Alternated **{any_row['order']}** — replicates, not one run each. The "
      "ratio's statistical se is already ~0.6% at 1M steps, so sample size was "
      "never the binding constraint; drift was. ABBA gives both arms the same "
      "mean run position, so a linear trend in the box (thermal, background "
      "creep) cancels out of the per-pair ratios instead of landing on "
      "whichever arm ran second. The reported sd is across pairs and is an "
      "EMPIRICAL error bar, not an assumption.\n")

    A("| variant | dose | reps n/e | node | engine | **speedup** | sd | steady-state |")
    A("|---|---|---|---|---|---|---|---|")
    for name, r in rows.items():
        sd = f"{r['sd']:.3f}" if r["sd"] is not None else "—"
        st_ = f"{r['steady']:.2f}x" if r["steady"] is not None else "—"
        A(f"| {name} | {r['dose']:,} | {r['reps']} | "
          f"{r['node_min']:.1f} min | {r['engine_min']:.1f} min | "
          f"**{r['speedup']:.2f}x** | {sd} | {st_} |")
    A("")

    for name, r in rows.items():
        if r["pairs"]:
            A(f"- {name} per-pair ratios: "
              + ", ".join(f"{p:.2f}x" for p in r["pairs"]))
    A("")

    A("## Which number to quote\n")
    prod = rows.get("production (engine k=256)")
    matched = rows.get("matched concurrency (engine k=8)")
    if prod:
        A(f"**{prod['speedup']:.2f}x is the headline** — old way against new way, "
          "each collector at the width you would actually train it at. It "
          "BUNDLES the concurrency change with the collector change, because "
          "running the engine at k=8 in production would be leaving the port's "
          "main advantage on the table. Name the dose and the width when you "
          "quote it.\n")
    if matched:
        A(f"**{matched['speedup']:.2f}x is the controlled number** — engine k=8 "
          "against the Node arm's concurrency 8, so the COLLECTOR is the only "
          "delta. This is the apples-to-apples read and the one to use for any "
          "claim about the collector itself rather than about the pipeline.\n")

    mx = pathlib.Path("results/engine_a1/maxout.json")
    if mx.exists():
        m = json.loads(mx.read_text())
        cells = [c for c in m["cells"] if c["ok"] and c["fleet_realized"]]
        base = next((c for c in cells if c["k"] == 8 and c["width"] == 3), None)
        A("## And if you MAX IT OUT: k x fleet width\n")
        A("The A/B above is ONE LANE at each collector's production width. This "
          "is the other axis — what the engine does when the box is pushed. "
          "Idle box, 200,000 steps per lane per cell, realized steps/s from "
          "each lane's own series with the startup window dropped.\n")
        A("| k | lanes | per-lane | fleet | peak RSS |")
        A("|---|---|---|---|---|")
        for c in cells:
            mark = "  <- today" if base and c is base else ""
            A(f"| {c['k']} | {c['width']} | {c['per_lane_realized_median']:,.0f} "
              f"| {c['fleet_realized']:,.0f} | {c['peak_rss_gb']:.2f} GB{mark} |")
        A("")
        if base:
            bf = max(cells, key=lambda c: c["fleet_realized"])
            bl = max(cells, key=lambda c: c["per_lane_realized_median"])
            A(f"**Best fleet throughput: k={bf['k']} at width {bf['width']} — "
              f"{bf['fleet_realized']:,.0f} steps/s, {bf['fleet_realized']/base['fleet_realized']:.2f}x "
              f"today's setting**, on {bf['peak_rss_gb']:.1f} GB of 24. Width "
              f"{bf['width']} is not the ceiling.\n")
            A(f"**Best per-lane rate: k={bl['k']} at width {bl['width']} — "
              f"{bl['per_lane_realized_median']:,.0f} steps/s, "
              f"{bl['per_lane_realized_median']/base['per_lane_realized_median']:.2f}x.** "
              "This is the only one of the two that shortens a SINGLE run.\n")
        A("**These two answer different questions and must not be multiplied "
          "together or added to the A/B.** A lane is a SEED, not a shard of one "
          "run: width buys seeds per hour and never a shorter run. And k costs "
          "0.11 GB for 248 extra battle slots, so k and width are independent "
          "axes rather than substitutes.\n")
        A("**Neither is free.** Raising k changes the staleness profile (stale "
          "rows go 0.40% at k=8 to 12.6% at k=256) and needs its own pre-reg. "
          "Width does not change learning at all — a lane is an independent "
          "seed — so it is the one lever here that can be taken on merit.\n")

    A("## What the speedup is actually made of\n")
    A("**A large share of this number is INFERENCE BATCHING, not the engine.** "
      "The Node collector calls the policy one decision at a time — "
      "`rl/envs/showdown_async.py:118-123` passes `obs[None, :]`, and the "
      "opponent seat does the same at `rl/envs/showdown.py:1227`. A forward "
      "pass costs ~230 us almost regardless of how many rows are in it (fit "
      "across the k sweep, cross-checked at 352 us/batch-1-forward against a "
      "banked Node lane's own `inference_seconds / seam_requests`). So the "
      "Node path's measured knee of 1240 learner-decisions/s = 806 us each is "
      "**~85% two batch-1 forwards** — not a server limit and not an I/O "
      "limit. The engine path batches 8 learner rows into one forward, i.e. "
      "44 us/row against 352.\n")
    A("That batching is a genuine property of the port — an in-process "
      "collector can hold k battles at a decision point simultaneously and a "
      "websocket-per-battle collector cannot — so it belongs in the number. "
      "But it is NOT the Rust engine being fast, and someone could in "
      "principle have batched the Node path's forwards without any of this "
      "work. Quote the speedup as the pipeline's, never as the engine's.\n")
    A("## What this is not\n")
    A("- **Not a fleet number.** One lane each, width 1. The fleet-width read "
      "is T-1(d), and it says something different and independently useful: "
      "the Showdown server drops to **0.043 cores** while three engine lanes "
      "train, against 1.08 cores per lane on the Node path.")
    A("- **Not a collection-throughput number.** T-1(a)/(b) measure collection "
      "with no update in the denominator; that overstates by ~7x and is not "
      "comparable to anything here.")
    A("- **Not 2.62x.** That figure divides today's engine rate by a Node rate "
      "banked on 2026-09-01 — two measurements subtracted, on different days. "
      "It is recorded in NOTES with that caveat and must not be quoted as the "
      "speedup.")
    A("- **Not a licence to switch collectors.** Speed is not the gate; A-1 is, "
      "and A-1's band is unresolved. A faster collector that trains a "
      "different agent is worth nothing.\n")

    A("## Disclosures carried from the harness\n")
    seen = set()
    for r in rows.values():
        for d in r["disclosures"]:
            key = d[:60]
            if key in seen:
                continue
            seen.add(key)
            A(f"- {d}")
    A("")
    A(f"Showdown server ran with `simulator: {any_row['workers']}` "
      "(CLAUDE.md rule 5, checked at launch, not assumed).")
    A(f"\nMeasured {', '.join(sorted({r['measured_at'] for r in rows.values()}))}"
      f" by `scripts/engine_ab_speed.py`; raw JSON under `results/engine_a1/`.")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--k256", type=pathlib.Path, default=K256)
    ap.add_argument("--k8", type=pathlib.Path, default=K8)
    ap.add_argument("--write", type=pathlib.Path)
    args = ap.parse_args(argv)

    rows = {}
    for name, p in (("production (engine k=256)", args.k256),
                    ("matched concurrency (engine k=8)", args.k8)):
        if p.exists():
            rows[name] = _row(json.loads(p.read_text()))
        else:
            print(f"(missing: {p} — that variant is not in this readout)")
    if not rows:
        raise SystemExit("no A/B results found; run scripts/engine_ab_speed.py first")

    text = render(rows)
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text)
        print(f"written: {args.write}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
