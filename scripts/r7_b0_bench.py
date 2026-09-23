#!/usr/bin/env python
"""R7 B0 acceptance bench -- the T-op's per-decision cost AT FLEET WIDTH.

The spec is the imported chapter's REPLY BOX 2 §1 (`docs/proposals/
SEARCH_IN_TRAINING_CHAPTER_2026-09-22.md`), adopted verbatim by the plan's
amendment box 3 item 1 and the runner brief §4. Restated, with what this script
does for each:

  1. NORMAL QoS, asserted: refuses to run under `taskpolicy -b` (Darwin process
     priority 4 reads nonzero there -- `docs/landmines.md:614-626`, the 6.8x),
     and stamps the P/E core split into the output.
  2. `torch_threads: 1`, the fleet's setting. A `--torch-threads 4` run is a
     DISCLOSURE ROW, never the planning number (`landmines.md:328`).
  3. AT FLEET WIDTH: `--widths 5 6` runs the operator in 5 and then 6 concurrent
     lane processes, each with a paired LEARNER-LOAD process (forward+backward on
     256-row minibatches through the same actor and critic, `torch_threads: 1`),
     so every lane occupies two threads exactly as the async two-core lane will.
     A `--widths 1` run is a disclosure row, never the number.
  4. THE FLEET'S CRITIC FORM: ONE VIEW by default (corrected 2026-09-23, BEFORE
     the bench ever ran for a verdict: plan AMENDMENT BOX 5 item 5 took B2's
     antisymmetric critic out of the fleet's base, so the T-op's leaf reads the
     acting seat's view only). `--both-views` (the antisymmetric form: two
     encodes, one 2N-row forward) is now the DISCLOSURE ROW, for B2's own lap.
  5. Reports per-decision p50 AND p99 per lane; the fleet number is the SLOWEST
     lane's p99, because a fleet is gated by its slowest lane.
  6. The four components separately: (i) engine + tracker + encoder (the Rust
     loop's own clock, `rust_ns`), (ii) PyO3 crossing + numpy construction
     (expand wall minus (i)), (iii) critic forward, (iv) the root solve.
  7. PASS LINE, pre-stated: p99 TOTAL per decision at SIX-wide, normal QoS,
     torch_threads 1, <= 2 x the plan's table = 2 x 1.8 ms = 3.6 ms (plan §5).
     Outside that, the T-op is a lane and not a fleet. The budget is unchanged;
     the CONFIGURATION it is read at moved to the fleet's own before any run:
     one view (item 4) at `--cols 4` (the G0 sweep's cell, box 4 item 3 -- the
     plan's table assumed 3). The six-wide verdict also decides box 6's R-F2
     (3 + 3 six-wide, or 3 + 2).

The operator shape is the plan's T-op row: every legal row for the acting seat
x up to `--cols` opponent replies x `--chance` samples (~6.7 x 3 x 2 ~= 40
leaves). Positions come from a live engine self-play stream (`BatchEnv`, both
seats scripted random -- the state distribution is not the trained policy's, so
the leaf count is REPORTED beside every number and is what makes them
comparable). The critic is the fleet's own architecture (trio B's trunk kwargs,
1,807,489 params, asserted), at random init -- timing does not depend on the
weights.

REFUSES to run beside a training fleet or a Foul Play arm (`rl.train`,
`ch3_eval`, `foul` in any command line) unless `--smoke`, which runs one lane for
a few dozen decisions, writes nothing under `results/`, and prints SMOKE on
every line: a smoke checks the code path, it measures nothing.

Output: `results/r7_b0_bench/<utc-stamp>.json` (every number in
`readouts/R7_B0_BENCH.md` traces to one of these) and a table on stdout.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import multiprocessing as mp
import os
import pathlib
import platform
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# The fleet critic. Copied from configs/showdown_r6_trio_b_fallback.yaml's
# agent.trunk_kwargs, and the param count is ASSERTED below against the config
# header's stamped 1,807,489 so a drift here cannot go unnoticed.
FLEET_TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128, pool="max",
    ctx_sizes=[384, 384], scorer_sizes=[256], value_sizes=[1024, 1024],
)
FLEET_CRITIC_PARAMS = 1_807_489
FLEET_ACTOR_PARAMS = 626_059
PLAN_TABLE_MS = 1.8          # plan §5, the T-op row (both views)
PASS_MULTIPLIER = 2.0        # REPLY BOX 2 §1 item 7
PASS_LINE_MS = PLAN_TABLE_MS * PASS_MULTIPLIER
PRIO_DARWIN_PROCESS = 4      # sys/resource.h; nonzero == PRIO_DARWIN_BG


def qos_is_background() -> bool:
    try:
        return os.getpriority(PRIO_DARWIN_PROCESS, 0) != 0
    except OSError:
        return False


def sysctl(key: str) -> str:
    try:
        return subprocess.run(["sysctl", "-n", key], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:  # noqa: BLE001
        return "?"


def busy_box() -> list[str]:
    """Command lines that make any timing here invalid (a training lane, an
    FP arm, an eval queue). Never `taskpolicy`d away -- they are the reason."""
    out = subprocess.run(["ps", "-eo", "command"], capture_output=True, text=True).stdout.splitlines()
    bad = []
    for line in out:
        low = line.lower()
        if any(k in low for k in ("-m rl.train", "ch3_eval", "foul", "rl.eval", "reads_queue", "exit_gate")):
            if "r7_b0_bench" in low:
                continue
            bad.append(line.strip()[:120])
    return bad


def percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


# ---------------------------------------------------------------------------
# The learner-load process: one thread of forward+backward, forever.
# ---------------------------------------------------------------------------

def learner_load(stop: mp.Event, torch_threads: int, seed: int) -> None:
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    import torch
    torch.set_num_threads(torch_threads)
    torch.manual_seed(seed)
    from rl.networks.entity_deepsets import EntityDeepSetsNet
    actor = EntityDeepSetsNet(828, 10, **FLEET_TRUNK_KWARGS)
    critic = EntityDeepSetsNet(828, 1, **FLEET_TRUNK_KWARGS)
    opt = torch.optim.Adam(list(actor.parameters()) + list(critic.parameters()), lr=1e-4)
    x = torch.rand(256, 828)
    # id tails must be valid indices: the tokenizer reads species/move ids off
    # the last 20 dims (scaled by 256) -- keep them small and integral.
    x[:, -20:] = torch.randint(0, 100, (256, 20)).float() / 256.0
    while not stop.is_set():
        logits = actor(x)
        v = critic(x)
        loss = logits.logsumexp(-1).mean() + v.pow(2).mean()
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()


# ---------------------------------------------------------------------------
# The lane process: the T-op per decision, timed in four parts.
# ---------------------------------------------------------------------------

def lane(args, lane_id: int, width: int, out_q: mp.Queue, stop: mp.Event) -> None:
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    import numpy as np
    import torch
    torch.set_num_threads(args.torch_threads)
    torch.manual_seed(1000 + lane_id)
    import pkmn_gen1
    import engine_team_bank as bank
    from rl.envs.engine_tables import build_tables
    from rl.networks.entity_deepsets import EntityDeepSetsNet

    tables, _fp = build_tables()
    _h, payload = bank.read_bank(pathlib.Path(args.bank))
    critic_kwargs = dict(FLEET_TRUNK_KWARGS)
    if args.privileged:
        critic_kwargs["privileged_dim"] = 408
    critic = EntityDeepSetsNet(828, 1, **critic_kwargs).eval()
    n_params = sum(p.numel() for p in critic.parameters())
    if not args.privileged:
        assert n_params == FLEET_CRITIC_PARAMS, f"critic has {n_params} params, the fleet's has {FLEET_CRITIC_PARAMS}"
    env = pkmn_gen1.BatchEnv(args.k, 7000 + 13 * lane_id + 1000 * width, tables, payload, "p1")
    rng = np.random.default_rng(lane_id)
    tau = 1.0

    rec = {k: [] for k in ("total", "rust", "glue", "critic", "solve", "leaves", "rows", "cols")}
    decisions = 0
    warm = args.warmup
    while decisions < args.decisions + warm and not stop.is_set():
        li, lobs, lmask, _ = env.pending("learner")
        oi, oa = env.scripted_actions("opponent", "random")
        la = []
        for j, slot in enumerate(li.tolist()):
            rows = np.flatnonzero(lmask[j]).tolist()
            node = env.snapshot(slot)
            r1, r2 = node.requests()
            if r2 == "pass":
                cols = [-1]
            else:
                legal = np.flatnonzero(node.mask(tables, "p2")).tolist()
                cols = rng.choice(legal, size=min(args.cols, len(legal)), replace=False).tolist()
            cells = [(r, c, args.chance) for r in rows for c in cols]
            seed_base = int(rng.integers(0, 2**63 - 1))

            t0 = time.perf_counter_ns()
            e = node.expand(tables, "p1", cells, seed_base, both_views=args.both_views)
            t1 = time.perf_counter_ns()
            n = e["n"]
            live = e["terminal"] == 0
            with torch.no_grad():
                if args.privileged:
                    x = torch.from_numpy(np.concatenate([e["obs"], e["priv"]], 1))
                    v = critic(x).squeeze(-1).numpy()
                elif not args.both_views:
                    v = critic(torch.from_numpy(e["obs"])).squeeze(-1).numpy()
                else:
                    # The antisymmetric form: V = 1/2 (f(obs1) - f(obs2)), one
                    # 2N-row forward.
                    f = critic(torch.from_numpy(np.concatenate([e["obs"], e["obs2"]], 0))).squeeze(-1).numpy()
                    v = 0.5 * (f[:n] - f[n:])
            t2 = time.perf_counter_ns()
            term = e["terminal"].astype(np.float32)
            v = np.where(live, v, np.where(term == 2, 0.0, term))
            # Root solve: per-cell mean over chance, uniform over the columns,
            # then the prior-regularised mixed root (P4).
            q_cell = np.zeros(len(cells), dtype=np.float64)
            np.add.at(q_cell, e["cell"], v)
            q_cell /= args.chance
            q_row = q_cell.reshape(len(rows), len(cols)).mean(1)
            prior = rng.random(len(rows)); prior /= prior.sum()
            z = np.log(prior) + q_row / tau
            pi = np.exp(z - z.max()); pi /= pi.sum()
            a = int(rows[int(rng.choice(len(rows), p=pi))])
            t3 = time.perf_counter_ns()
            la.append(a)
            if decisions >= warm:
                rust = int(e["rust_ns"])
                rec["total"].append((t3 - t0) / 1e6)
                rec["rust"].append(rust / 1e6)
                rec["glue"].append((t1 - t0 - rust) / 1e6)
                rec["critic"].append((t2 - t1) / 1e6)
                rec["solve"].append((t3 - t2) / 1e6)
                rec["leaves"].append(n)
                rec["rows"].append(len(rows))
                rec["cols"].append(len(cols))
            decisions += 1
            if decisions >= args.decisions + warm:
                break
        # Fill the rest of the learner's pending slots so the env can advance.
        while len(la) < len(li):
            j = len(la)
            la.append(int(rng.choice(np.flatnonzero(lmask[j]))))
        env.step(li.tolist(), la, [0.0] * len(li), 0, oi.tolist(), oa.tolist())
        env.drain_finished()

    summary = {"lane": lane_id, "width": width, "decisions": len(rec["total"]),
               "critic_params": n_params, "pid": os.getpid()}
    for k in ("total", "rust", "glue", "critic", "solve"):
        xs = rec[k]
        summary[k] = {"p50_ms": percentile(xs, 0.5), "p99_ms": percentile(xs, 0.99),
                      "mean_ms": float(np.mean(xs)) if xs else float("nan")}
    for k in ("leaves", "rows", "cols"):
        summary[k + "_mean"] = float(np.mean(rec[k])) if rec[k] else float("nan")
    out_q.put(summary)


def run_width(args, width: int) -> dict:
    ctx = mp.get_context("spawn")
    stop = ctx.Event()
    out_q = ctx.Queue()
    lanes, loads = [], []
    for i in range(width):
        p = ctx.Process(target=lane, args=(args, i, width, out_q, stop), name=f"lane{i}")
        p.start(); lanes.append(p)
        if not args.no_learner_load:
            q = ctx.Process(target=learner_load, args=(stop, args.torch_threads, 500 + i), name=f"learner{i}")
            q.start(); loads.append(q)
    results = [out_q.get() for _ in lanes]
    stop.set()
    for p in lanes + loads:
        p.join(timeout=60)
        if p.is_alive():
            p.terminate()
    results.sort(key=lambda r: r["lane"])
    slowest = max(results, key=lambda r: r["total"]["p99_ms"])
    return {"width": width, "lanes": results,
            "fleet_p99_ms": slowest["total"]["p99_ms"], "fleet_p50_ms_max": max(r["total"]["p50_ms"] for r in results),
            "slowest_lane": slowest["lane"], "leaves_mean": sum(r["leaves_mean"] for r in results) / len(results)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--widths", type=int, nargs="+", default=[5, 6])
    ap.add_argument("--decisions", type=int, default=2000, help="timed decisions per lane")
    ap.add_argument("--warmup", type=int, default=200, help="untimed decisions per lane first")
    ap.add_argument("--k", type=int, default=8, help="battles in flight per lane (the fleet's k)")
    ap.add_argument("--cols", type=int, default=4, help="opponent replies searched (top-k stand-in; 4 = the G0 sweep's cell)")
    ap.add_argument("--chance", type=int, default=2, help="chance samples per cell")
    ap.add_argument("--torch-threads", type=int, default=1)
    ap.add_argument("--both-views", action="store_true",
                    help="DISCLOSURE ROW: B2's antisymmetric form (two encodes, one 2N-row forward); the fleet reads one view")
    ap.add_argument("--privileged", action="store_true", help="DISCLOSURE ROW: the 408-block critic (obs || priv)")
    ap.add_argument("--no-learner-load", action="store_true", help="DISCLOSURE ROW: one thread per lane")
    ap.add_argument("--bank", default=None, help="team bank (default: the smallest under data/engine)")
    ap.add_argument("--smoke", action="store_true", help="one lane, few decisions, beside anything, writes nothing")
    ap.add_argument("--out-dir", default="results/r7_b0_bench")
    args = ap.parse_args()

    if args.bank is None:
        banks = sorted((ROOT / "data/engine").glob("teams_*.bin"), key=lambda p: p.stat().st_size)
        if not banks:
            sys.exit("no team bank under data/engine")
        args.bank = str(banks[0])

    if args.smoke:
        args.widths = [1]
        args.decisions = min(args.decisions, 40)
        args.warmup = min(args.warmup, 5)
        tag = "SMOKE -- NOT A MEASUREMENT"
    else:
        tag = "MEASUREMENT"
        if qos_is_background():
            sys.exit("REFUSED: running under background QoS (taskpolicy -b) -- the number would be wrong, "
                     "not slow (docs/landmines.md:614-626)")
        busy = busy_box()
        if busy:
            sys.exit("REFUSED: the box is running something whose timing this would corrupt, or that "
                     "would corrupt this:\n  " + "\n  ".join(busy))

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip())
    import pkmn_gen1  # noqa: E402
    info = {
        "tag": tag, "stamp": stamp, "git_sha": sha, "git_dirty": dirty,
        "qos": "background" if qos_is_background() else "normal",
        "cores": {"performance": sysctl("hw.perflevel0.physicalcpu"), "efficiency": sysctl("hw.perflevel1.physicalcpu"),
                  "logical": sysctl("hw.ncpu")},
        "machine": platform.machine(), "python": sys.version.split()[0],
        "engine": pkmn_gen1.build_info() if hasattr(pkmn_gen1, "build_info") else None,
        "args": vars(args), "plan_table_ms": PLAN_TABLE_MS, "pass_line_ms": PASS_LINE_MS,
        "widths": [],
    }
    print(f"[{tag}] {stamp} sha {sha}{' DIRTY' if dirty else ''} qos={info['qos']} "
          f"cores P{info['cores']['performance']}/E{info['cores']['efficiency']} torch_threads={args.torch_threads} "
          f"both_views={args.both_views} privileged={args.privileged} learner_load={not args.no_learner_load}")
    for w in args.widths:
        t0 = time.time()
        r = run_width(args, w)
        r["wall_s"] = time.time() - t0
        info["widths"].append(r)
        print(f"\nwidth {w}: fleet p99 {r['fleet_p99_ms']:.3f} ms (slowest lane {r['slowest_lane']}), "
              f"max lane p50 {r['fleet_p50_ms_max']:.3f} ms, leaves/decision {r['leaves_mean']:.1f}, "
              f"{r['wall_s']:.0f} s")
        print(f"  {'lane':>4} {'dec':>5} {'total p50':>10} {'total p99':>10} {'rust p99':>9} {'glue p99':>9} "
              f"{'critic p99':>11} {'solve p99':>10} {'leaves':>7}")
        for ln in r["lanes"]:
            print(f"  {ln['lane']:>4} {ln['decisions']:>5} {ln['total']['p50_ms']:>10.3f} {ln['total']['p99_ms']:>10.3f} "
                  f"{ln['rust']['p99_ms']:>9.3f} {ln['glue']['p99_ms']:>9.3f} {ln['critic']['p99_ms']:>11.3f} "
                  f"{ln['solve']['p99_ms']:>10.3f} {ln['leaves_mean']:>7.1f}")
    six = next((r for r in info["widths"] if r["width"] == 6), None)
    if six is not None and not args.smoke and not args.both_views and not args.privileged \
            and not args.no_learner_load and args.torch_threads == 1 and args.cols == 4:
        verdict = "PASS" if six["fleet_p99_ms"] <= PASS_LINE_MS else "FAIL"
        info["verdict"] = {"read": verdict, "fleet_p99_ms_at_6": six["fleet_p99_ms"], "pass_line_ms": PASS_LINE_MS,
                           "rule": "p99 total per decision at six-wide, normal QoS, torch_threads 1, the fleet's "
                                   "one-view critic at cols 4, learner load on, <= 2 x the plan's 1.8 ms"}
        print(f"\nVERDICT {verdict}: six-wide fleet p99 {six['fleet_p99_ms']:.3f} ms vs pass line {PASS_LINE_MS:.1f} ms "
              f"(2 x plan §5's {PLAN_TABLE_MS} ms)")
    else:
        info["verdict"] = {"read": "NONE", "why": "not the pass-line configuration (smoke, disclosure row, or no six-wide run)"}
        print(f"\n[{tag}] no verdict: not the pass-line configuration")
    if not args.smoke:
        out = ROOT / args.out_dir
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{stamp}.json"
        path.write_text(json.dumps(info, indent=1))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
