#!/usr/bin/env python
"""A-1's sigma_seed measurement, from named files — the provenance behind the
power table in `configs/engine_a1.yaml`.

WHY THIS SCRIPT EXISTS. The A-1 header pins its baseline "BY PROVENANCE, NEVER
BY A REMEMBERED NUMBER" and then quoted a sigma that appeared nowhere else in
the repo (review 1, M-11). This re-derives it from run dirs and eval JSONs so
the number the band is ratified on can be looked up and recomputed, exactly the
way the baseline block can.

THE QUESTION. IDEAS_POST_100M §1 carries sigma_seed ~= 0.0617, which is measured
at the 50M dose (RESULTS.md:1177, off Foul Play @20, n=1000/lane). A-1 reads at
12M. Seeds diverge with dose, so the 50M constant is the wrong instrument for a
12M gate; this measures the 12M one and splits it by LR schedule, which turns
out to be the covariate that matters.

READ-ONLY. Points at the main tree by absolute path and writes only its own
JSON. Run it from the worktree.

    python scripts/engine_a1_sigma.py --out results/engine_a1/sigma.json
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import statistics
import sys

import yaml

MAIN = pathlib.Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")
RUNG_LO, RUNG_HI = 11_900_000, 12_100_000
LOCKED_N = 3000


def _fleet_of(run_name: str) -> str:
    """Strip the trailing _s<seed> so lanes group into their fleet."""
    return re.sub(r"_s\d+(_.*)?$", "", run_name)


def _qualifies(d: dict) -> tuple[bool, str]:
    """Is this eval JSON a locked-protocol vs-SH read AT THE 12M RUNG?

    Three filters, and the middle one is the one that matters. Several fleets
    keep their reads under results/ as `best_s<seed>.json` — a BEST-checkpoint
    read, which for `d18` lands at step 7,000,000 and for `d23` at 5,000,000.
    Those are neither the locked protocol's FINAL checkpoint nor the 12M rung,
    and pooling them into a 12M sigma would mix doses and inflate it. They are
    excluded by the step window, not by their filename.
    """
    if not isinstance(d, dict) or "eval/win_rate" not in d:
        return False, "no eval/win_rate"
    if d.get("episodes") != LOCKED_N:
        return False, f"n={d.get('episodes')} != {LOCKED_N}"
    step = d.get("step")
    if not isinstance(step, (int, float)):
        return False, "no step"
    if not (RUNG_LO <= step <= RUNG_HI):
        return False, f"step {int(step)} outside the 12M rung window"
    opp = str(d.get("opponent", "heuristics")).lower()
    if "heur" not in opp and opp not in ("", "none"):
        return False, f"opponent {opp!r} is not the locked denominator"
    return True, ""


def collect(main: pathlib.Path) -> dict:
    """Every lane with a locked-protocol vs-SH read at the 12M rung.

    Scans BOTH the run dirs and results/, because fleets differ in where they
    parked their finals, and a sigma computed over only one location silently
    drops fleets (review 1, M-11).
    """
    lanes = []
    seen: set[str] = set()
    rejected: list[dict] = []

    # results/**: attributed back to a run via the JSON's own run_name.
    cfg_cache: dict[str, dict] = {}
    for js in sorted((main / "results").glob("**/*.json")):
        try:
            d = json.loads(js.read_text())
        except Exception:
            continue
        ok, why = _qualifies(d) if isinstance(d, dict) else (False, "")
        run_name = d.get("run_name") if isinstance(d, dict) else None
        if not run_name:
            continue
        if not ok:
            if isinstance(d, dict) and "eval/win_rate" in d and d.get("episodes") == LOCKED_N:
                rejected.append({"file": str(js.relative_to(main)),
                                 "run": run_name, "why": why})
            continue
        if run_name in seen:
            continue
        cfg_path = main / "runs" / run_name / "config.yaml"
        if not cfg_path.exists():
            continue
        if run_name not in cfg_cache:
            try:
                cfg_cache[run_name] = yaml.safe_load(cfg_path.read_text()) or {}
            except Exception:
                continue
        cfg = cfg_cache[run_name]
        anneal = (cfg.get("agent") or {}).get("lr_anneal_steps", 0) or 0
        seen.add(run_name)
        lanes.append({
            "run": run_name, "fleet": _fleet_of(run_name), "seed": cfg.get("seed"),
            "eval_json": str(js.relative_to(main)), "step": int(d["step"]),
            "win_rate": float(d["eval/win_rate"]), "total_steps": cfg.get("total_steps"),
            "lr_anneal_steps": anneal,
            "schedule": "annealed" if anneal and anneal > 0 else "flat",
            "anneal_frac_at_rung": (RUNG_LO / anneal) if anneal else 0.0,
        })

    for cfg_path in sorted((main / "runs").glob("*/config.yaml")):
        run = cfg_path.parent
        try:
            cfg = yaml.safe_load(cfg_path.read_text()) or {}
        except Exception:
            continue
        agent = cfg.get("agent") or {}
        total = cfg.get("total_steps")
        anneal = agent.get("lr_anneal_steps", 0) or 0
        if run.name in seen:
            continue
        for js in sorted(run.glob("**/*.json")):
            try:
                d = json.loads(js.read_text())
            except Exception:
                continue
            ok, why = _qualifies(d) if isinstance(d, dict) else (False, "")
            if not ok:
                if isinstance(d, dict) and "eval/win_rate" in d and d.get("episodes") == LOCKED_N:
                    rejected.append({"file": str(js.relative_to(main)),
                                     "run": run.name, "why": why})
                continue
            step = d["step"]
            seen.add(run.name)
            lanes.append({
                "run": run.name,
                "fleet": _fleet_of(run.name),
                "seed": cfg.get("seed"),
                "eval_json": str(js.relative_to(main)),
                "step": int(step),
                "win_rate": float(d["eval/win_rate"]),
                "total_steps": total,
                "lr_anneal_steps": anneal,
                "schedule": "annealed" if anneal and anneal > 0 else "flat",
                "anneal_frac_at_rung": (RUNG_LO / anneal) if anneal else 0.0,
            })
            break   # one locked read per lane
    return lanes, rejected


def pool(fleets: dict) -> dict:
    """Pooled within-fleet across-seed sd: sqrt(sum (k-1) s^2 / sum (k-1))."""
    num = den = 0.0
    used = []
    for name, rows in sorted(fleets.items()):
        if len(rows) < 2:
            continue
        s = statistics.stdev([r["win_rate"] for r in rows])
        num += (len(rows) - 1) * s * s
        den += len(rows) - 1
        used.append({"fleet": name, "k": len(rows), "sd": s,
                     "schedule": rows[0]["schedule"],
                     "per_seed": {str(r["seed"]): r["win_rate"] for r in rows},
                     "eval_jsons": [r["eval_json"] for r in rows]})
    return {"sigma": math.sqrt(num / den) if den else None, "df": int(den),
            "n_fleets": len(used), "fleets": used}


def ci95(s: float, df: int) -> list[float] | None:
    """chi-square 95% CI for an sd on df degrees of freedom (table, no scipy)."""
    lo = {2: 7.378, 4: 11.143, 7: 16.013, 10: 20.483, 24: 39.364, 31: 48.232}
    hi = {2: 0.0506, 4: 0.4844, 7: 1.690, 10: 3.247, 24: 12.401, 31: 17.539}
    if df not in lo:
        return None
    return [s * math.sqrt(df / lo[df]), s * math.sqrt(df / hi[df])]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--main", type=pathlib.Path, default=MAIN)
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/sigma.json"))
    args = ap.parse_args(argv)

    lanes, rejected = collect(args.main)
    if not lanes:
        raise SystemExit("no locked-protocol 12M reads found — check --main")
    by_fleet: dict[str, list] = {}
    for r in lanes:
        by_fleet.setdefault(r["fleet"], []).append(r)

    allp = pool(by_fleet)
    ann = pool({k: v for k, v in by_fleet.items() if v[0]["schedule"] == "annealed"})
    # REGIME-MATCHED is stricter than "annealed" (review 2, M6). A-1's arms
    # anneal over 50M and are KILLED at 12M, so ~76% of the base LR is still
    # live at the read. showdown_sp_recipe12m anneals over 12M and is fully
    # decayed at the same rung — annealed, but a different regime, and it is
    # the only annealed fleet that is not one of A-1's own two arms.
    regime = pool({k: v for k, v in by_fleet.items()
                   if 0.0 < v[0]["anneal_frac_at_rung"] < 0.5})
    flat = pool({k: v for k, v in by_fleet.items() if v[0]["schedule"] == "flat"})

    # Binomial floor at the locked n, for the "is this real seed variation"
    # question: at p~0.65, n=3000.
    binom = math.sqrt(0.65 * 0.35 / LOCKED_N)

    out = {
        "question": "sigma_seed at the 12M rung, by LR schedule",
        "locked_n": LOCKED_N,
        "rung_window": [RUNG_LO, RUNG_HI],
        "all": {**allp, "ci95": ci95(allp["sigma"], allp["df"]) if allp["sigma"] else None},
        "annealed": {**ann, "ci95": ci95(ann["sigma"], ann["df"]) if ann["sigma"] else None},
        "regime_matched": {**regime,
                           "ci95": ci95(regime["sigma"], regime["df"]) if regime["sigma"] else None,
                           "definition": "annealed with <50% of the schedule consumed at the 12M rung — A-1's own regime"},
        "flat": {**flat, "ci95": ci95(flat["sigma"], flat["df"]) if flat["sigma"] else None},
        "binomial_se_at_locked_n": binom,
        "binomial_share_of_all_variance": (binom / allp["sigma"]) ** 2 if allp["sigma"] else None,
        "excluded_locked_n_reads_off_rung": rejected,
        "note": ("A-1's reference class is ANNEALED: both its arms run the 50M "
                 "anneal schedule and are killed at the 12M rung. The 50M-dose "
                 "constant 0.0617 (RESULTS.md:1177) is a different instrument."),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")

    for key in ("all", "annealed", "regime_matched", "flat"):
        b = out[key]
        ci = b.get("ci95")
        print(f"{key:9s} sigma={b['sigma']:.5f} df={b['df']:2d} "
              f"fleets={b['n_fleets']:2d}"
              + (f" ci95=[{ci[0]:.4f}, {ci[1]:.4f}]" if ci else ""))
    print(f"\nbinomial se at n={LOCKED_N}: {binom:.5f} "
          f"({out['binomial_share_of_all_variance']*100:.1f}% of the all-fleet variance)")
    print(f"\nfleets used ({allp['n_fleets']}):")
    for f in allp["fleets"]:
        print(f"  {f['fleet']:34s} k={f['k']} {f['schedule']:8s} sd={f['sd']:.5f} "
              f"{sorted(f['per_seed'])}")
    if rejected:
        print(f"\nexcluded ({len(rejected)} locked-n reads off the 12M rung — "
              "best-checkpoint reads at other doses):")
        for r in rejected[:8]:
            print(f"  {r['file']:44s} {r['why']}")
        if len(rejected) > 8:
            print(f"  ... and {len(rejected) - 8} more (all in the JSON)")
    print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
