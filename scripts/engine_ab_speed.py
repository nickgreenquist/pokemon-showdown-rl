#!/usr/bin/env python
"""THE HEAD-TO-HEAD SPEED A/B: train the same dose on Node, then on the engine.

WHY THIS REPLACES THE EARLIER NUMBER. The first "2.3x" compared an engine rate
measured today against a Node rate banked on 2026-09-01 — a different day, a
different box state, a different set of neighbours. That is not an A/B, it is
two measurements subtracted. This runs BOTH ARMS ON THIS BOX, BACK TO BACK, on
an idle machine, and reports WALL-CLOCK SECONDS TO THE SAME DOSE.

The headline is one number: how long does it take to train N steps the old way,
and how long the new way. Not per lane, not per step, not collection-only.

FAIRNESS IS BY CONSTRUCTION, NOT BY INSPECTION. Both configs are generated here
from ONE base dict; the ONLY difference is the `collector` block (and the run
name). Nothing else can drift, because nothing else is written twice.

    python scripts/engine_ab_speed.py --steps 1000000
    python scripts/engine_ab_speed.py --steps 1000000 --engine-k 8   # matched-K

TWO SETTINGS, AND THE DIFFERENCE MATTERS:
  * DEFAULT (--engine-k 256): production-vs-production. Each collector at the
    width you would actually train it at. This answers "how much faster is the
    new way".
  * --engine-k 8: matched concurrency, so the COLLECTOR is the only delta. This
    answers "how much of the speedup is the collector itself" and is the
    apples-to-apples control. Run both if you can; quote which one you mean.

EVALS ARE OFF in both arms (`eval_every` past the horizon). The locked eval
protocol stays on the Showdown server either way, so including it would add the
same constant to both arms and dilute the ratio while adding server variance.
This measures TRAINING throughput, which is the thing the port changes.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import pathlib
import re
import shutil
import subprocess
import sys
import time

import yaml

MAIN = pathlib.Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")
PY = "/opt/anaconda3/envs/pkmn-engine-port/bin/python"
BASE_CONFIG = pathlib.Path("configs/engine_a1.yaml")
BANK = "data/engine/teams_a1_5000000.bin"


def busy() -> list[str]:
    out = []
    for pat, what in ((r"rl\.train", "a training lane"),
                      (r"(^|/|[[:space:]])(cargo|maturin)[[:space:]]", "a build")):
        r = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True)
        if r.stdout.strip():
            out.append(what)
    return out


def simulator_workers() -> int:
    """CLAUDE.md rule 5: `showdown/config/config.js` must set `simulator: 4`.

    THIS IS A CORRECTNESS GUARD ON THE HEADLINE NUMBER, not housekeeping. That
    setting is worth +81% collection throughput on the Node path, and the file
    is GITIGNORED — a re-clone silently resets it to the default. Running the
    A/B against a 1-worker server would hand the Node arm an 81% handicap and
    inflate the reported speedup by that whole amount, with nothing anywhere in
    the output to show it happened. So it is read, asserted, and RECORDED in
    the result as provenance.
    """
    cfg = MAIN / "showdown/config/config.js"
    m = re.search(r"^\s*simulator\s*:\s*(\d+)", cfg.read_text(), re.M)
    if not m:
        raise SystemExit(
            f"{cfg} has no `simulator:` line. CLAUDE.md rule 5 requires "
            "simulator: 4; without it the Node arm runs ~81% slower and this "
            "A/B would report a speedup that is mostly a misconfiguration.")
    return int(m.group(1))


def server_up() -> bool:
    return bool(subprocess.run(["pgrep", "-f", "node pokemon-showdown start"],
                               capture_output=True, text=True).stdout.strip())


def start_server() -> None:
    if server_up():
        return
    subprocess.Popen(
        "cd %s/showdown && nohup node pokemon-showdown start --no-security "
        ">> %s/logs/showdown_server.log 2>&1 &" % (MAIN, MAIN),
        shell=True)
    for _ in range(120):
        time.sleep(1)
        if subprocess.run(["nc", "-z", "localhost", "8000"],
                          capture_output=True).returncode == 0:
            time.sleep(5)
            return
    raise SystemExit("server did not come up on 8000")


def stop_server() -> None:
    subprocess.run(["pkill", "-f", "node pokemon-showdown start"],
                   capture_output=True)
    time.sleep(3)


def build_config(base: dict, arm: str, steps: int, k: int, seed: int,
                 out: pathlib.Path, rep: int = 1, lane: int = 0) -> pathlib.Path:
    """Both arms from ONE base. The collector block is the only edit.

    `lane` is the index within a WIDTH > 1 arm. It shifts the seed, because
    concurrent lanes MUST have distinct seeds (CLAUDE.md rule 2 — poke-env
    derives Showdown usernames from a globally-seeded `random`, so same-seed
    lanes collide and die with a misleading TimeoutError), and it enters the
    seat tag for the same reason at one more level.
    """
    cfg = copy.deepcopy(base)
    seed = seed + lane
    cfg["total_steps"] = steps
    cfg["eval_every"] = steps * 10          # evals OFF, both arms alike
    cfg["eval_win_rate"] = False
    cfg["logger"] = "wandb"
    cfg["seed"] = seed
    cfg["run_name"] = f"ab_{arm}_s{seed}_r{rep}"
    cfg["checkpoint_every"] = steps * 10    # no ladder writes skewing either arm
    cfg.pop("env_kwargs", None) or None
    # PER-REPLICATE SEAT TAG, and the arm is in it. Alternation runs the two
    # Node replicates back to back at the SAME seed, and with no tag
    # `seat_names` gives both the identical pair `as2s{seed}a/b` (rl/envs/
    # showdown.py:976). If replicate 1's seats have not fully released when
    # replicate 2 connects, replicate 2 dies with a misleading TimeoutError —
    # and a killed arm's username pair stays poisoned for HOURS, which would
    # take the rest of the A/B with it. A tag hashes into the name, so any
    # distinct tag separates them. Kept on the engine arm too: identical
    # env_kwargs across arms is the point, and the engine path ignores it.
    cfg["env_kwargs"] = {"opp_action": True,     # keep D25 on, both recipes have it
                         "seat_tag": f"ab{arm}{rep}l{lane}"}
    if arm == "node":
        cfg["collector"] = {"mode": "async", "concurrency": 8}
    else:
        cfg["collector"] = {"mode": "engine", "k": k,
                            "team_bank": BANK, "learner_seat": "p1",
                            "min_bank_pairs": 1_000_000}
    p = out / f"ab_{arm}_r{rep}_l{lane}.yaml"
    p.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return p


def steady_state(run_dir: pathlib.Path, batch: int, drop: int = 2) -> dict | None:
    """Per-update wall EXCLUDING startup — the number sample size cannot fix.

    MEASURED on a real Node lane: per-update wall has a CV of only 2.5%, so at
    33 updates (1M steps) the se on an arm's rate is 0.44% and on the RATIO
    0.62%. Statistical noise is not the problem. STARTUP is: the engine arm is
    the short one, so a 20 s startup is 8% of a 1M run and 2.7% of a 3M run —
    an order of magnitude larger than the statistical term, and it does NOT
    average down. Reporting a steady-state rate beside the total makes the
    comparison robust to it instead of paying for more steps to dilute it.
    """
    import csv
    import subprocess as sp
    hist = run_dir / "history.csv"
    if not hist.exists():
        sp.run([PY, "scripts/extract_history.py", str(run_dir)],
               capture_output=True)
    if not hist.exists():
        return None
    per = []
    with open(hist) as fh:
        for r in csv.DictReader(fh):
            c, u = r.get("time/collect_sec", ""), r.get("time/update_sec", "")
            if c in ("", None) or u in ("", None):
                continue
            try:
                per.append(float(c) + float(u))
            except ValueError:
                pass
    per = per[drop:]
    if not per:
        return None
    import statistics as st
    mean = st.fmean(per)
    return {"updates_used": len(per), "dropped": drop,
            "sec_per_update_mean": mean,
            "sec_per_update_cv": (st.stdev(per) / mean) if len(per) > 1 else None,
            "steady_state_steps_per_sec": batch / mean}


def run_arm(arm: str, cfgs: list[pathlib.Path], logs: list[pathlib.Path],
            stagger_sec: float = 0.0) -> dict:
    """Run one arm at its full width and return the FLEET wall clock.

    Wall is measured from the FIRST launch to the LAST exit, which is what a
    fleet actually costs you: a 3-seed result is not ready until the slowest
    seed is. The stagger is inside that window, deliberately — it is applied
    IDENTICALLY to both arms, so it cancels in the ratio, and lanes launched
    dead simultaneously are their own hazard (a lane can SIGSEGV at startup
    before writing any log line).
    """
    import os
    e = dict(os.environ)
    e.update({"POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"})
    t0 = time.time()
    procs, handles = [], []
    for i, (cfg, log) in enumerate(zip(cfgs, logs)):
        if i and stagger_sec:
            time.sleep(stagger_sec)
        fh = open(log, "w")
        handles.append(fh)
        procs.append(subprocess.Popen([PY, "-m", "rl.train", "--config", str(cfg)],
                                      stdout=fh, stderr=subprocess.STDOUT, env=e))
    rcs = [p.wait() for p in procs]
    for fh in handles:
        fh.close()
    return {"arm": arm, "wall_seconds": time.time() - t0,
            "rc": max(rcs) if rcs else 1, "rcs": rcs,
            "width": len(cfgs), "stagger_sec": stagger_sec,
            "config": [str(c) for c in cfgs], "log": [str(l) for l in logs]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--steps", type=int, default=1_000_000)
    ap.add_argument("--order", default="ABBA",
                    help="run order, A=node B=engine. ABBA cancels LINEAR "
                         "drift exactly (both arms mean position 2.5); ABAB "
                         "does not (A 2.0 vs B 3.0). Default ABBA = 2 "
                         "replicates per arm; ABBAABBA doubles it, but the "
                         "statistical term is not the binding one, so the "
                         "extra block buys little.")
    ap.add_argument("--engine-k", type=int, default=256)
    ap.add_argument("--width", type=int, default=1,
                    help="LANES PER ARM. width 1 answers 'how fast is one lane'. "
                         "width 3 answers 'how long does a 3-seed fleet take', "
                         "which is the unit this project actually works in — "
                         "and unlike the banked cross-day comparison it puts "
                         "both arms on the same box in the same hour. A lane "
                         "is a SEED, not a shard: raising width does NOT make "
                         "one run finish sooner, it runs more seeds at once.")
    ap.add_argument("--stagger-sec", type=float, default=15.0,
                    help="delay between lane launches within an arm, applied "
                         "IDENTICALLY to both arms so it cancels in the ratio. "
                         "Simultaneous launches are their own hazard: a lane "
                         "can SIGSEGV at startup before writing a log line.")
    ap.add_argument("--seed", type=int, default=9301)
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/ab_speed.json"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    b = busy()
    if b and not args.force:
        raise SystemExit(
            f"the box is busy ({'; '.join(b)}). This is a WALL-CLOCK "
            "measurement — anything else running makes both arms wrong and the "
            "ratio meaningless. Wait, or pass --force to record it as tainted.")

    workers = simulator_workers()
    if workers != 4:
        raise SystemExit(
            f"showdown/config/config.js sets simulator: {workers}, not 4 "
            "(CLAUDE.md rule 5). The Node arm would run ~81% slower and the "
            "speedup this prints would be mostly that misconfiguration. Fix "
            "the file and re-run; the setting is gitignored, so a re-clone "
            "loses it.")

    # PREFLIGHT THE ENGINE ARM'S BANK. ABBA puts a NODE run first, so a missing
    # bank would otherwise surface ~33 minutes in, when the engine arm's turn
    # comes and rl/train.py refuses the config. The bank lives under `data/`,
    # which is gitignored and was moved out of the engine worktree by the
    # teardown — exactly the kind of thing that is either there or very much
    # not, and is worth one stat call to find out now.
    if not (MAIN / BANK).exists():
        raise SystemExit(
            f"team bank {MAIN / BANK} is missing, so the engine arm cannot "
            "run. If the engine worktree has not been torn down yet, its "
            "data/ still holds the bank — run the teardown first "
            "(scripts/engine_post_lane_queue.sh) rather than regenerating, "
            "since a rebuilt bank has a different sha256 and every gate "
            "record cites the current one.")

    base = yaml.safe_load(BASE_CONFIG.read_text())
    # The update batch, read from the config rather than pasted in: it is the
    # denominator of every steady-state rate, and a base config with different
    # rollout_steps would otherwise report rates that are quietly wrong.
    batch = int(base["agent"]["rollout_steps"]) * int(base["num_envs"])
    work = pathlib.Path("results/engine_a1/ab"); work.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # ALTERNATING REPLICATES, not one long run of each.
    # The statistical term is already tiny — per-update wall has a CV of 2.5%,
    # so the ratio's se is 0.62% at 1M steps. What actually threatens this
    # number is SYSTEMATIC drift: the box warms, background load creeps, and a
    # single A-then-B ordering hands all of that to whichever arm runs second.
    # Replication with alternation attacks that; more steps do not. ABBA
    # cancels a linear trend exactly (both arms average position 2.5), where
    # ABAB leaves A at 2.0 against B at 3.0.
    order = [c.upper() for c in args.order if c.upper() in ("A", "B")]
    results: dict[str, list] = {"node": [], "engine": []}
    for idx, slot in enumerate(order, start=1):
        arm = "node" if slot == "A" else "engine"
        rep = len(results[arm]) + 1
        rds = [pathlib.Path(f"runs/ab_{arm}_s{args.seed + lane}_r{rep}")
               for lane in range(args.width)]
        for rd in rds:
            shutil.rmtree(rd, ignore_errors=True)
        cfgs = [build_config(base, arm, args.steps, args.engine_k,
                             args.seed, work, rep, lane)
                for lane in range(args.width)]
        logs = [work / f"ab_{arm}_r{rep}_l{lane}.log" for lane in range(args.width)]
        if arm == "node":
            start_server()
        else:
            stop_server()
        print(f"--- [{idx}/{len(order)}] {arm} rep {rep}: {args.width} lane(s) x "
              f"{args.steps:,} steps "
              f"({'async concurrency 8' if arm=='node' else f'engine k={args.engine_k}'})",
              flush=True)
        r = run_arm(arm, cfgs, logs, args.stagger_sec)
        # FLEET steps: at width W the arm delivers W x steps, and the ratio of
        # fleet walls is the thing a fleet operator actually experiences.
        fleet_steps = args.steps * args.width
        ss = [steady_state(rd, batch) for rd in rds]
        ss = [x for x in ss if x]
        r.update(steps=args.steps, fleet_steps=fleet_steps, replicate=rep,
                 slot=idx,
                 steps_per_sec=(fleet_steps / r["wall_seconds"]
                                if r["wall_seconds"] else None),
                 per_lane_steps_per_sec=(args.steps / r["wall_seconds"]
                                         if r["wall_seconds"] else None),
                 steady_state=({"steady_state_steps_per_sec":
                                sum(x["steady_state_steps_per_sec"] for x in ss),
                                "per_lane": ss} if ss else None))
        results[arm].append(r)
        print(f"    rc={r['rc']}  wall={r['wall_seconds']:.1f}s  "
              f"{r['steps_per_sec']:.0f} steps/s fleet "
              f"({r['per_lane_steps_per_sec']:.0f}/lane)", flush=True)

    out = {
        "question": "wall-clock seconds to train the SAME dose, old way vs new way",
        "dose_steps": args.steps,
        "width": args.width,
        "stagger_sec": args.stagger_sec,
        "engine_k": args.engine_k,
        "matched_concurrency": args.engine_k == 8,
        "arms": results,
        "showdown_simulator_workers": workers,
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    import statistics as _st
    ok = {a: [r for r in results[a] if r["rc"] == 0] for a in ("node", "engine")}
    if ok["node"] and ok["engine"]:
        nw = [r["wall_seconds"] for r in ok["node"]]
        ew = [r["wall_seconds"] for r in ok["engine"]]
        # PAIRED by replicate index where both exist — that is what the
        # alternation buys, and it is a tighter estimator than mean/mean.
        pairs = [n_ / e_ for n_, e_ in zip(nw, ew)]
        out["per_pair_speedup"] = pairs
        out["speedup_wall_clock"] = _st.fmean(pairs)
        if len(pairs) > 1:
            sd = _st.stdev(pairs)
            out["speedup_sd"] = sd
            out["speedup_se"] = sd / math.sqrt(len(pairs))
        ns = [r["steady_state"]["steady_state_steps_per_sec"]
              for r in ok["node"] if r.get("steady_state")]
        es = [r["steady_state"]["steady_state_steps_per_sec"]
              for r in ok["engine"] if r.get("steady_state")]
        if ns and es:
            out["speedup_steady_state"] = _st.fmean(es) / _st.fmean(ns)
        print(f"\nSPEEDUP, wall clock, same dose, same box, alternated "
              f"{args.order}: {out['speedup_wall_clock']:.2f}x")
        print("  per-pair: " + ", ".join(f"{p:.2f}x" for p in pairs))
        if "speedup_se" in out:
            print(f"  sd {out['speedup_sd']:.3f}  se {out['speedup_se']:.3f} "
                  f"over {len(pairs)} pairs")
        if "speedup_steady_state" in out:
            print(f"  steady-state (startup excluded): "
                  f"{out['speedup_steady_state']:.2f}x")
        print(f"  node   {_st.fmean(nw)/60:.1f} min/run   "
              f"engine {_st.fmean(ew)/60:.1f} min/run")

    out["order"] = args.order
    out["replicates"] = {a: len(results[a]) for a in results}
    out["disclosures"] = [
        (f"ONE LANE each, width 1. This is not a fleet number."
         if args.width == 1 else
         f"WIDTH {args.width}: each arm ran {args.width} concurrent lanes at "
         f"distinct seeds, and the wall is FIRST LAUNCH to LAST EXIT — a "
         f"{args.width}-seed result is not ready until the slowest seed is. A "
         "lane is a SEED, not a shard of one run, so this does NOT say a "
         "single run finishes sooner at higher width."),
        f"ALTERNATED {args.order} with {len(ok['node'])}/{len(ok['engine'])} "
        "completed replicates, and the ratio is the mean of PER-PAIR ratios, "
        "so a monotone drift in the box cancels rather than landing on "
        "whichever arm ran second. The reported sd/se is across pairs and is "
        "an empirical error bar, not an assumption.",
        f"engine k={args.engine_k}; "
        + ("MATCHED to the Node arm's concurrency, so the collector is the only "
           "delta" if args.engine_k == 8 else
           "the production setting, so this is old-way vs new-way, NOT a "
           "controlled test of the collector alone — run with --engine-k 8 for that"),
        "evals OFF in both arms; the locked protocol stays on the server either "
        "way, so including it would add the same constant to both and dilute "
        "the ratio",
        "each run is back to back on one idle box; the server is brought UP "
        "for a Node run and DOWN for an engine run, every time",
        f"the Showdown server ran with simulator: {workers} (CLAUDE.md rule 5, "
        "checked at launch and recorded here rather than assumed — the file is "
        "gitignored, the setting is worth +81% on the Node path, and getting it "
        "wrong would inflate this ratio by that whole amount)",
        "ORDER/THERMAL BIAS IS NOW CANCELLED BY DESIGN rather than disclosed: "
        "ABBA gives both arms mean run position 2.5, so a linear trend drops "
        "out of the per-pair ratios. ABAB would NOT do this (A 2.0 vs B 3.0).",
        "TWO RATIOS ARE REPORTED. `speedup_wall_clock` includes startup and is "
        "what you actually pay. `speedup_steady_state` excludes the first 2 "
        "updates and is what the collector sustains. They differ because "
        "startup is a fixed cost falling on a short arm: at 1M steps a 20 s "
        "startup is 8% of the engine arm against 2% of the Node arm. Sample "
        "size does not fix that — per-update CV is 2.5%, so the ratio's "
        "STATISTICAL se is already 0.62% at 1M steps.",
    ]
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
