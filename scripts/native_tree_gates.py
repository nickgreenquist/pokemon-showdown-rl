#!/usr/bin/env python
"""DEEP SEARCH Step A -- the native tree's gates on G0's 500 banked roots.

`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md` r2 §2 Step A. Plays no battle and
starts no server; G0's rows (`results/r7_g0/`) are READ, never written.

  reduction   GATE (i-a). At depth cap 1 -- mode br_prior, the root grid, the top
              `cols_k` columns, `chance_k` = `chance_s` children, soft_br at `tau`,
              Pass leaves valued the way `native.solve` values them -- the tree
              (`rl/search/native_tree.py::search`) must REPRODUCE `native.solve`'s
              Qbar and pi' on every root, BITWISE (the grid is `native.solve`'s own
              batch), with every shared `search/*` counter equal. The dials are read
              from the banked critic L-op's summary (`belief_k4s2t005.json`), never
              typed. Any root that differs fails the gate (exit 1).
  oracle      GATE (i-c), DECISION QUALITY on G0's true-world rollout oracle. Per root,
              the critic L-op's own 8 belief worlds (the belief read's generator,
              default_rng([belief_seed, pid]): the SAME worlds the banked critic L-op
              searched) are searched by each ARM below at 1,800 TOTAL simulations
              (§35's budget); every arm's root statistics go to disk, and the
              candidate of each root rule (soft_br at the L-op's tau, gumbel_mctx,
              legacy_gumbel, visits, argmax, the arm's own) is read off them AFTER
              the search. `--summarise` gates each (arm, rule) to a TARGET OVERRIDE
              RATE by a quantile of its OWN margins (Stage 0c's scorer; the landmine:
              match on the override rate, never the delta) and scores it on G0's
              oracle against the banked critic L-op at its native gate (0.080, the
              matched rate), paired per root. DESCRIPTIVE: a gap diagnoses the port
              (the estimand, the leaf, the foe prior, fusion at depth), never kills
              it (proposal §3). Caveat that travels with every number: the oracle is
              the committee-vs-committee continuation, and the tree's leaves are the
              critic the oracle's rollouts are not.
              ARMS: br (br_prior, root grid, depth cap 8), br_sh (the same with Gumbel's
              sequential halving at the root: rows compared at EQUAL root visits), legacy (tree.py's decoupled
              rule, foe minimising, no grid, cols_k 5 as tree.py's opp_k), rm (sm_rm),
              d1 (br_prior at depth cap 1 with chance_k 8: the one-ply twin at ~equal
              work), br_true (br_prior on the TRUE world only: the T-op's setting, a
              peek, read against the banked true-world one-ply).

The committee is G0's (its paths and sha256s from `rollout_q.json`, verified on
load); the leaf evaluator is its mean observation critic and the prior below the
root its geometric-pool policy (`scripts/rollout_q.py::Committee`), exactly as the
G0 chapter's reads use them. The tables fingerprint must equal the banked rows'.

  bench       GATE (ii), the P-CORE BENCH -- a TIMED instrument, so it refuses a busy box
              (1-min load above --max-load) and any nice / background QoS: run it on the
              quiet box after the fleet, at nice 0. Per config (worlds, the tree's dials)
              and per worker count (1 / 2 / 5 / 10 processes, each on its own roots), on
              turn-stratified G0 roots: ms per decision p50 / p99, simulations and leaves
              per second, the time split (value / prior forwards, engine, Python), rows
              per forward (batch fill), depth, peak RSS; and HOURS PER 3,200-BATTLE ARM
              at G2L's measured searched decisions per battle. The inference rungs are 8
              worlds (the L-op's), the training rungs the TRUE world (Step C's B = 1).
              Not built: the shared-inference process (one network server fed by many
              tree workers); the per-worker scaling says whether it is needed.

Runs from the worktree with PYTHONPATH on it (a worktree pins nothing without it),
an env that has `pkmn_gen1`, POKEMON_RL_ENCODER_C6 unset, bytecode writes off:
  env -u POKEMON_RL_ENCODER_C6 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<worktree> \\
    taskpolicy -b /opt/anaconda3/envs/pkmn-engine-r7/bin/python scripts/native_tree_gates.py reduction
Output: <out-dir>/reduction.json (default out-dir: the main checkout's
results/native_tree, gitignored).
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN_CHECKOUT = pathlib.Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

SHARED_COUNTERS = ("search/leaves", "search/rows", "search/cols", "search/worlds", "search/override",
                   "search/kl_prior", "search/margin", "search/pi_top1", "search/prior_top1", "search/topk_mass",
                   "search/terminal_frac", "search/pass_leaf_frac", "search/v", "search/v_prior")


def _stamps(tables_fp: str) -> dict:
    import pkmn_gen1
    from rl.envs.showdown import OBS_DIM
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True,
                                text=True, cwd=ROOT).stdout.strip())
    info = pkmn_gen1.build_info()
    return {"git_sha": sha, "git_dirty": dirty, "worktree": str(ROOT), "engine_sha": str(info.get("engine_sha", ""))[:12],
            "obs_dim": int(OBS_DIM), "tables_fingerprint": tables_fp[:12],
            "written": dt.datetime.now(dt.timezone.utc).isoformat()}


def load_g0(g0_dir: pathlib.Path) -> tuple[list[dict], dict, dict]:
    rows = [json.loads(line) for line in (g0_dir / "rollout_q.rows.jsonl").read_text().splitlines() if line.strip()]
    bad = sorted({str(r.get("instrument_version")) for r in rows} - {"rollout_q/1", "rollout_q/2"})
    if bad:
        sys.exit(f"REFUSED: G0's rows carry instrument versions {bad}")
    return rows, json.loads((g0_dir / "rollout_q.json").read_text()), json.loads((g0_dir / "belief_k4s2t005.json").read_text())


def reduction(args) -> int:
    import pkmn_gen1
    import torch
    import rollout_q as rq
    from rl.envs.engine_tables import build_tables
    from rl.search import native, native_tree
    from rl.search.native import World

    torch.set_num_threads(args.torch_threads)
    g0_dir = pathlib.Path(args.g0_dir)
    rows, g0_summary, belief = load_g0(g0_dir)
    dials = native.dials_from(belief["dials"])
    if dials.get("root_rule", "soft_br") != "soft_br":
        sys.exit("REFUSED: the banked critic L-op must be the soft best response")
    cols_k, chance_s, tau = int(dials.get("cols_k", 3)), int(dials.get("chance_s", 2)), float(dials.get("tau", 1.0))
    paths = [c["path"] for c in g0_summary["committee"]]
    shas = [c["sha256"] for c in g0_summary["committee"]]
    committee, prov = rq.load_committee(paths, shas, np.random.default_rng(0))
    tables, fp = build_tables()
    banked_fp = rows[0].get("tables_fingerprint") or g0_summary.get("tables_fingerprint")
    if banked_fp and banked_fp != fp:
        sys.exit(f"REFUSED: tables fingerprint {fp[:12]} != G0's {str(banked_fp)[:12]}")

    def value_fn(e):
        return committee.critic(e["obs"])

    sel = sorted(rows, key=lambda r: int(r["pid"]))
    if args.limit:
        sel = sel[: args.limit]
    fails, n_ok, worst_q = [], 0, 0.0
    t0 = time.perf_counter()
    ms_ref = ms_tree = 0.0
    for r in sel:
        pid = int(r["pid"])
        node = pkmn_gen1.SearchNode.load(base64.b64decode(r["node_b64"]))
        m1 = np.asarray(node.mask(tables, "p1"), bool)
        m2 = np.asarray(node.mask(tables, "p2"), bool)
        prior1 = np.where(m1, np.asarray(r["pi1"], np.float64), 0.0)
        prior2 = np.where(m2, np.asarray(r["pi2"], np.float64), 0.0)
        key = pid * 100_003 + 17
        a = time.perf_counter()
        ref = native.solve([World(node)], tables, "p1", prior1, prior2, value_fn, key, both_views=False, **dials)
        b = time.perf_counter()
        grid = len(ref["rows"]) * len(ref["cols"]) * chance_s
        got = native_tree.search([World(node)], tables, "p1", prior1, prior2, value_fn, committee.probs, key,
                                 sims=grid, mode="br_prior", root_rule="soft_br", root_grid=True, depth_cap=1,
                                 cols_k=cols_k, chance_k=chance_s, tau=tau, pass_leaf="critic", both_views=False)
        c = time.perf_counter()
        ms_ref += (b - a) * 1e3
        ms_tree += (c - b) * 1e3
        why = []
        if not np.array_equal(ref["pi"], got["pi"]):
            why.append("pi")
        if not np.array_equal(ref["q_row"], got["q_row"], equal_nan=True):
            why.append("q_row")
            d = np.nanmax(np.abs(ref["q_row"] - got["q_row"]))
            worst_q = max(worst_q, float(d))
        if ref["action"] != got["action"] or ref["policy_action"] != got["policy_action"]:
            why.append("action")
        for k in SHARED_COUNTERS:
            if ref["counters"][k] != got["counters"][k]:
                why.append(k)
        if got["counters"]["tree/sims"] != grid or got["counters"]["tree/errors"]:
            why.append("tree_sims_or_errors")
        if why:
            fails.append({"pid": pid, "why": why})
        else:
            n_ok += 1
    out = {
        "gate": "i-a reduction", "n": len(sel), "bitwise": n_ok, "fails": fails, "max_abs_q_diff": worst_q,
        "dials": {"cols_k": cols_k, "chance_s": chance_s, "tau": tau, "source": str(g0_dir / "belief_k4s2t005.json")},
        "committee": [p["sha256"][:12] for p in prov], "ms_native_solve_mean": ms_ref / max(len(sel), 1),
        "ms_tree_mean": ms_tree / max(len(sel), 1), "seconds": time.perf_counter() - t0,
        "verdict": "PASS" if (n_ok == len(sel) and len(sel) > 0) else "FAIL", **_stamps(fp),
    }
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reduction.json").write_text(json.dumps(out, indent=1))
    print(f"[i-a] {out['verdict']}: {n_ok}/{len(sel)} roots bitwise (pi', Qbar, action, {len(SHARED_COUNTERS)} counters); "
          f"max |dQ| {worst_q:.3g}; native.solve {out['ms_native_solve_mean']:.2f} ms, tree {out['ms_tree_mean']:.2f} ms "
          f"per root; wrote {out_dir / 'reduction.json'}")
    for f in fails[:10]:
        print("  FAIL", f)
    return 0 if out["verdict"] == "PASS" else 1


ORACLE_VERSION = "native_tree_oracle/2"
BUDGET = 1800                         # §35's XTG9: 900 iterations x 2 worlds, TOTAL simulations
# batch 4 descents per tree per round (virtual loss): the committee's forward costs about the same from 8 to 64 rows,
# so 8 worlds x 4 = 32 rows a call instead of 8 cuts the calls ~4x (v1 at batch 1 ran 136 s a root on the E-cores)
ARMS = {
    "br": dict(sims=BUDGET, mode="br_prior", root_grid=True, depth_cap=8, cols_k=4, chance_k=2, root_rule="soft_br",
               batch=4),
    "br_sh": dict(sims=BUDGET, mode="br_prior", root_grid=True, depth_cap=8, cols_k=4, chance_k=2, root_rule="gumbel_mctx",
                  root_select="sequential_halving", batch=4),
    "legacy": dict(sims=BUDGET, mode="legacy", root_grid=False, depth_cap=8, cols_k=5, chance_k=2, opp_rule="puct",
                   root_rule="legacy_gumbel", beta=4.0, batch=4),
    "rm": dict(sims=BUDGET, mode="sm_rm", root_grid=False, depth_cap=8, cols_k=4, chance_k=2, root_rule="rm_average",
               batch=4),
    "d1": dict(sims=1, mode="br_prior", root_grid=True, depth_cap=1, cols_k=4, chance_k=8, root_rule="soft_br"),
    "br_true": dict(sims=BUDGET, mode="br_prior", root_grid=True, depth_cap=8, cols_k=4, chance_k=2, root_rule="soft_br",
                    batch=8),
}
TRUE_ARMS = ("br_true",)
CONTRASTS = [("br", "d1"), ("br_sh", "d1"), ("br_sh", "br"), ("legacy", "br"), ("rm", "br")]
RULES = ("soft_br", "gumbel_mctx", "legacy_gumbel", "visits", "argmax", "own")
KEEP = ("tree/sims", "search/leaves", "tree/depth_mean", "tree/depth_max", "tree/upd_mean", "tree/turns_mean",
        "tree/turns_max", "tree/nodes", "tree/merges", "tree/pass_nodes", "tree/terminal_sims", "tree/capped_sims",
        "tree/world_agree", "tree/errors", "tree/worlds_failed", "tree/fallback", "search/ms", "search/rust_ms",
        "tree/ms_value", "tree/ms_prior", "tree/forwards_v", "tree/forwards_p", "search/kl_prior", "tree/v_mix",
        "search/topk_mass", "search/terminal_frac")


def candidate(rule: str, rows: list[int], prior_m: np.ndarray, q: np.ndarray, n: np.ndarray, v_mix: float,
              pi_own: np.ndarray, greedy: int, tau: float) -> tuple[int, float]:
    """A root rule's candidate (an action) and its margin over greedy, read off the
    root statistics AFTER the search (the search never reads the root rule except
    sm_rm's average strategy, which is `own`). Mirrors native_tree._decide."""
    vis = (n > 0) & np.isfinite(q)
    qd = np.where(vis, q, v_mix)
    if rule == "soft_br":
        z = np.log(prior_m) + qd / tau
    elif rule == "gumbel_mctx":
        lo, hi = qd.min(), qd.max()
        z = np.log(prior_m) + (50.0 + float(n.max())) * 0.1 * (qd - lo) / max(hi - lo, 1e-8)
    elif rule == "legacy_gumbel":
        if vis.any():
            lo, hi = q[vis].min(), q[vis].max()
            qn = np.where(vis, (np.nan_to_num(q) - lo) / max(hi - lo, 1e-6), 0.0)
        else:
            qn = np.zeros(len(rows))
        z = np.log(prior_m) + 4.0 * qn
    elif rule == "visits":
        z = n.astype(np.float64)
    elif rule == "argmax":
        z = qd
    elif rule == "own":
        z = pi_own
    else:
        raise ValueError(rule)
    j = int(np.argmax(z))
    ig = rows.index(greedy)
    return int(rows[j]), float(qd[j] - qd[ig])


def oracle(args) -> int:
    import pkmn_gen1
    import torch
    import rollout_q as rq
    from rl.envs.engine_tables import build_tables
    from rl.search import native_tree
    from rl.search.native import World
    from rl.search.resample import resample_world

    g0_dir = pathlib.Path(args.g0_dir)
    rows_all, g0_summary, belief = load_g0(g0_dir)
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.summarise:
        return oracle_summary(args, rows_all, belief, out_dir)
    torch.set_num_threads(args.torch_threads)
    tau = float(belief["dials"].get("tau", 1.0))
    arms = {k: native_tree.dials_from({**v, "tau": tau} if v.get("root_rule") == "soft_br" else v) for k, v in ARMS.items()}
    paths = [c["path"] for c in g0_summary["committee"]]
    shas = [c["sha256"] for c in g0_summary["committee"]]
    committee, prov = rq.load_committee(paths, shas, np.random.default_rng(0))
    tables, fp = build_tables()
    banked_fp = rows_all[0].get("tables_fingerprint") or g0_summary.get("tables_fingerprint")
    if banked_fp and banked_fp != fp:
        sys.exit(f"REFUSED: tables fingerprint {fp[:12]} != G0's {str(banked_fp)[:12]}")
    stamps = _stamps(fp)
    stamps["committee"] = [p["sha256"][:12] for p in prov]

    def value_fn(e):
        return committee.critic(e["obs"])

    i_sh, n_sh = (int(x) for x in args.shard.split("/"))
    rows_path = out_dir / f"{args.tag}.rows.s{i_sh}of{n_sh}.jsonl"
    done = set()
    if rows_path.exists():
        for line in rows_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("version") != ORACLE_VERSION:
                    sys.exit(f"REFUSED: {rows_path} carries version {r.get('version')}, not {ORACLE_VERSION}")
                done.add(int(r["pid"]))
    todo = [r for r in sorted(rows_all, key=lambda r: int(r["pid"])) if int(r["pid"]) % n_sh == i_sh
            and int(r["pid"]) not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"[i-c] {ORACLE_VERSION} shard {args.shard}: {len(done)} on disk, {len(todo)} to measure; arms "
          f"{json.dumps(arms)}; committee {stamps['committee']}; git {stamps['git_sha']}"
          f"{' DIRTY' if stamps['git_dirty'] else ''}", flush=True)
    t_start = time.time()
    for n_new, r in enumerate(todo, 1):
        pid = int(r["pid"])
        t0 = time.perf_counter()
        row = {"version": ORACLE_VERSION, "pid": pid, "bucket": int(r["bucket"]), "turn": int(r["turn"]),
               "a_greedy": int(r["a_greedy"]), "dials": arms,
               **{k: stamps[k] for k in ("git_sha", "git_dirty", "engine_sha")}}
        try:
            node = pkmn_gen1.SearchNode.load(base64.b64decode(r["node_b64"]))
            m1 = np.asarray(node.mask(tables, "p1"), bool)
            m2 = np.asarray(node.mask(tables, "p2"), bool)
            rows = np.flatnonzero(m1).tolist()
            if rows != [int(a) for a in r["rows"]]:
                raise RuntimeError("G0's rows disagree with the reloaded root's mask")
            prior1 = np.where(m1, np.asarray(r["pi1"], np.float64), 0.0)
            prior2 = np.where(m2, np.asarray(r["pi2"], np.float64), 0.0)
            wrng = np.random.default_rng([int(args.belief_seed), pid])
            worlds, refused = [], []
            for b in range(args.worlds):
                try:
                    w, _info = resample_world(node, tables, "p1", wrng)
                except RuntimeError as e:
                    refused.append(str(e)[:120])
                    continue
                if not np.array_equal(np.asarray(w.mask(tables, "p1"), bool), m1):
                    refused.append("our mask moved in the resampled world")
                    continue
                worlds.append(World(w))
            row.update({"rows": rows, "worlds_built": len(worlds), "worlds_refused": refused, "arms": {}})
            key = pid * 1_000_003 + 29
            for name, dials in arms.items():
                ws = [World(node)] if name in TRUE_ARMS else worlds
                if not ws:
                    row["arms"][name] = {"no_world": True}
                    continue
                opp = prior2 if name in TRUE_ARMS else None
                res = native_tree.search(ws, tables, "p1", prior1, opp, value_fn, committee.probs, key, **dials)
                c = res["counters"]
                row["arms"][name] = {"q": [None if not np.isfinite(x) else float(x) for x in res["q_row"][m1]],
                                     "n": [float(x) for x in res["n_row"][m1]],
                                     "pi": [float(x) for x in res["pi"][m1]], "action": int(res["action"]),
                                     "counters": {k: float(c.get(k, float("nan"))) for k in KEEP},
                                     "errors": {k: v for k, v in c.items() if k.startswith("tree/error/")}}
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:                        # counted, written, never retried
            row = {"version": ORACLE_VERSION, "pid": pid, "bucket": int(r["bucket"]), "error": type(e).__name__,
                   "message": str(e)[:400]}
        row["seconds"] = time.perf_counter() - t0
        with rows_path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        el = time.time() - t_start
        if "error" in row:
            print(f"[i-c] pid {pid} ERROR {row['error']}: {row['message'][:160]}", flush=True)
        else:
            dm = {k: round(v["counters"]["tree/depth_mean"], 2) for k, v in row["arms"].items() if "counters" in v}
            print(f"[i-c] pid {pid} worlds {row['worlds_built']} depth {dm} | {row['seconds']:.1f} s | "
                  f"{n_new}/{len(todo)}, {el / n_new:.1f} s/pos", flush=True)
    return 0


def oracle_summary(args, rows_all: list[dict], belief: dict, out_dir: pathlib.Path) -> int:
    import glob
    import r7_stage0c_rollout_curve as s0c

    tau = float(belief["dials"].get("tau", 1.0))
    g0_by_pid = {int(r["pid"]): r for r in rows_all}
    brows = [json.loads(line) for line in (pathlib.Path(args.g0_dir) / "belief_k4s2t005.rows.jsonl").read_text().splitlines()
             if line.strip()]
    if {r.get("version") for r in brows} != {belief["version"]}:
        sys.exit("REFUSED: the banked critic rows are not the version their summary names")
    bel_by_pid = {int(r["pid"]): r for r in brows}
    got = []
    for p in sorted(glob.glob(str(out_dir / f"{args.tag}.rows.s*of*.jsonl"))):
        for line in pathlib.Path(p).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("version") != ORACLE_VERSION:
                    sys.exit(f"REFUSED: {p} carries version {r.get('version')}")
                got.append(r)
    errs = [r for r in got if "error" in r]
    ok = sorted((r for r in got if "error" not in r), key=lambda r: r["pid"])
    ok = [r for r in ok if all("q" in a for a in r["arms"].values())]
    n = len(ok)
    if n == 0:
        print("no rows")
        return 1
    orc = [s0c.oracle_of(g0_by_pid[r["pid"]]) for r in ok]
    greedy = [int(g0_by_pid[r["pid"]]["a_greedy"]) for r in ok]
    bel = [bel_by_pid[r["pid"]] for r in ok]
    # THE CRITIC L-op, banked, at its native gate: the matched operating point.
    crit_native = np.array([int(b["a_belief"]) != int(b["a_greedy"]) for b in bel])
    target = float(crit_native.mean())
    crit_gain = np.where(crit_native, s0c.gains_for([b["a_belief"] for b in bel], orc, greedy), 0.0) / 2.0
    # the banked TRUE-world one-ply (the peek twin of br_true), at its native gate
    true_native = np.array([int(b["a_true"]) != int(b["a_greedy"]) for b in bel])
    true_gain = np.where(true_native, s0c.gains_for([b["a_true"] for b in bel], orc, greedy), 0.0) / 2.0
    out = {"version": ORACLE_VERSION, "positions": n, "errors": len(errs), "matched_rate": target,
           "critic_native": {"override": target, "gain": s0c.stat(crit_gain)},
           "true_one_ply_native": {"override": float(true_native.mean()), "gain": s0c.stat(true_gain)}, "arms": {}}
    pp: dict[tuple[str, str], np.ndarray] = {}                 # (arm, rule) -> per-root gain at the matched rate
    for name in ARMS:
        per = {}
        for rule in RULES:
            cands, margins = [], []
            for r, g0 in zip(ok, (g0_by_pid[r["pid"]] for r in ok)):
                a = r["arms"][name]
                rows = r["rows"]
                pi1 = np.asarray(g0["pi1"], np.float64)
                prior_m = pi1[rows] / pi1[rows].sum()
                q = np.array([np.nan if x is None else x for x in a["q"]], np.float64)
                c, m = candidate(rule, rows, prior_m, q, np.asarray(a["n"], np.float64), a["counters"]["tree/v_mix"],
                                 np.asarray(a["pi"], np.float64), int(g0["a_greedy"]), tau)
                cands.append(c)
                margins.append(m)
            moves = np.array([c != g for c, g in zip(cands, greedy)])
            og = s0c.gains_for(cands, orc, greedy)
            matched = s0c.read_operator(moves, np.array(margins), og, target)
            nominal = s0c.read_operator(moves, np.array(margins), og, 0.10)
            ref = true_gain if name in TRUE_ARMS else crit_gain
            pp[(name, rule)] = matched["per_position"]
            per[rule] = {"moves_at_gate0": float(moves.mean()),
                         "matched": {k: v for k, v in matched.items() if k != "per_position"},
                         "nominal": {k: v for k, v in nominal.items() if k != "per_position"},
                         "d_vs_one_ply_matched": s0c.stat(matched["per_position"] - ref),
                         "curve": {str(t): s0c.stat(s0c.read_operator(moves, np.array(margins), og, t)["per_position"])
                                   for t in s0c.CURVE_TARGETS}}
        cs = [r["arms"][name]["counters"] for r in ok]
        mean = lambda k: float(np.mean([c[k] for c in cs]))
        out["arms"][name] = {"rules": per, "depth_mean": mean("tree/depth_mean"), "depth_max_mean": mean("tree/depth_max"),
                             "upd_mean": mean("tree/upd_mean"), "turns_mean": mean("tree/turns_mean"),
                             "leaves_mean": mean("search/leaves"), "ms_mean": mean("search/ms"),
                             "world_agree_mean": mean("tree/world_agree"), "errors": float(sum(c["tree/errors"] for c in cs)),
                             "fallbacks": float(sum(c["tree/fallback"] for c in cs))}
    # PAIRED CONTRASTS, per root rule at the matched rate: depth vs breadth at ~equal work (the tree against its own
    # depth-cap-1 twin, d1: ~1,830 leaves vs the tree's ~1,620), the root's selection (sequential halving vs PUCT) and
    # the estimand (tree.py's decoupled rule and regret matching against br_prior).
    out["contrasts"] = {f"{a} - {b}": {rule: s0c.stat(pp[(a, rule)] - pp[(b, rule)]) for rule in RULES}
                        for a, b in CONTRASTS}
    out["written"] = dt.datetime.now(dt.timezone.utc).isoformat()
    (out_dir / f"{args.tag}.summary.json").write_text(json.dumps(out, indent=1, default=float))
    lines = [f"# gate (i-c): the native tree vs the one-ply critic L-op on G0's oracle ({n} roots, {len(errs)} errors)",
             "", f"matched override {target:.3f} (the critic L-op's native gate); gains in WIN-RATE units; d paired per root",
             f"critic L-op (B8, one ply) at its native gate: {out['critic_native']['gain']['mean']:+.4f} +- "
             f"{out['critic_native']['gain']['se']:.4f}", "",
             "| arm | rule | depth | leaves | gain @matched | d vs one-ply (z) | gain @0.10 | moves@0 |", "|---|---|---|---|---|---|---|---|"]
    for name, a in out["arms"].items():
        for rule, rr in a["rules"].items():
            g, d = rr["matched"]["gain"], rr["d_vs_one_ply_matched"]
            lines.append(f"| {name} | {rule} | {a['depth_mean']:.2f} | {a['leaves_mean']:.0f} | {g['mean']:+.4f} +- {g['se']:.4f} "
                         f"| {d['mean']:+.4f} ({d['z']:+.2f}) | {rr['nominal']['gain']['mean']:+.4f} | {rr['moves_at_gate0']:.3f} |")
    lines += ["", "PAIRED CONTRASTS at the matched rate (mean +- se (z)), per root rule:", "",
              "| contrast | " + " | ".join(RULES) + " |", "|---|" + "---|" * len(RULES)]
    for name, c in out["contrasts"].items():
        lines.append(f"| {name} | " + " | ".join(f"{c[r]['mean']:+.4f} +- {c[r]['se']:.4f} ({c[r]['z']:+.2f})" for r in RULES) + " |")
    (out_dir / f"{args.tag}.summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


TIMING = ("search/ms", "search/rust_ms", "tree/ms_value", "tree/ms_prior")


def _tag_rows(out_dir: pathlib.Path, tag: str) -> dict[int, dict]:
    import glob

    got = {}
    for p in sorted(glob.glob(str(out_dir / f"{tag}.rows.s*of*.jsonl"))):
        for line in pathlib.Path(p).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("version") != ORACLE_VERSION:
                    sys.exit(f"REFUSED: {p} carries version {r.get('version')}, not {ORACLE_VERSION}")
                got[int(r["pid"])] = r
    return got


def oracle_diff(args) -> int:
    """The REGRESSION CHECK of a refactor: the roots two tags share, arm by arm -- the same
    root, worlds and dials under two commits must give the same search. Equal means
    bitwise: q, n, pi, the action and every counter but the timing ones. Exit 1 on any
    difference, with the largest ones printed."""
    out_dir = pathlib.Path(args.out_dir)
    a, b = _tag_rows(out_dir, args.tag), _tag_rows(out_dir, args.against)
    pids = sorted(p for p in set(a) & set(b) if "error" not in a[p] and "error" not in b[p])
    if not pids:
        print(f"no shared error-free roots between {args.tag} ({len(a)}) and {args.against} ({len(b)})")
        return 1
    shas = lambda rows: sorted({str(rows[p].get("git_sha", "?"))[:10] for p in pids})
    print(f"[diff] {args.tag} (git {shas(a)}) vs {args.against} (git {shas(b)}): {len(pids)} shared roots")
    bad = 0
    for p in pids:
        ra, rb = a[p], b[p]
        for k in ("rows", "worlds_built", "worlds_refused", "a_greedy"):
            if ra.get(k) != rb.get(k):
                print(f"  pid {p}: root field {k} differs: {ra.get(k)} vs {rb.get(k)}")
                bad += 1
    for name in sorted(set().union(*(a[p]["arms"] for p in pids))):
        same = agree = n_cmp = 0
        dq = dpi = 0.0
        ckeys: set[str] = set()
        dial_diff = False
        for p in pids:
            xa, xb = a[p]["arms"].get(name), b[p]["arms"].get(name)
            if xa is None or xb is None or "q" not in xa or "q" not in xb:
                continue
            n_cmp += 1
            if a[p]["dials"].get(name) != b[p]["dials"].get(name):
                dial_diff = True
            qa = np.array([np.nan if x is None else x for x in xa["q"]], np.float64)
            qb = np.array([np.nan if x is None else x for x in xb["q"]], np.float64)
            fin = np.isfinite(qa) & np.isfinite(qb)
            q_eq = np.array_equal(np.isfinite(qa), np.isfinite(qb)) and np.array_equal(qa[fin], qb[fin])
            if fin.any():
                dq = max(dq, float(np.abs(qa[fin] - qb[fin]).max()))
            dpi = max(dpi, float(np.abs(np.asarray(xa["pi"]) - np.asarray(xb["pi"])).max()))
            ck = {k for k in set(xa["counters"]) | set(xb["counters"]) if k not in TIMING
                  and not (xa["counters"].get(k) == xb["counters"].get(k)
                           or (np.isnan(xa["counters"].get(k, 0.0)) and np.isnan(xb["counters"].get(k, 0.0))))}
            ckeys |= ck
            agree += xa["action"] == xb["action"]
            same += bool(q_eq and xa["n"] == xb["n"] and xa["pi"] == xb["pi"] and xa["action"] == xb["action"] and not ck
                         and xa.get("errors") == xb.get("errors"))
        bad += n_cmp - same
        print(f"  {name:8s} {same}/{n_cmp} bitwise, action agrees {agree}/{n_cmp}, max |dq| {dq:.3g}, max |dpi| {dpi:.3g}"
              f"{', counters differ: ' + ','.join(sorted(ckeys)) if ckeys else ''}{', DIALS DIFFER' if dial_diff else ''}")
    print(f"[diff] {'IDENTICAL' if bad == 0 else f'{bad} DIFFERENCES'}")
    return 0 if bad == 0 else 1


BENCH_VERSION = "native_tree_bench/1"
BENCH_CONFIGS = {
    # inference (Step B): the L-op's 8 worlds, br_prior with sequential halving and tree.py's legacy rule
    **{f"inf_sh_{n}_b{b}": {"worlds": 8, "tree": dict(sims=n, mode="br_prior", root_select="sequential_halving",
                                                       root_rule="gumbel_mctx", batch=b)}
       for n in (450, 1800, 7200) for b in (1, 4, 16)},
    **{f"inf_legacy_{n}_b4": {"worlds": 8, "tree": dict(sims=n, mode="legacy", root_grid=False, cols_k=5,
                                                         root_rule="legacy_gumbel", batch=4)} for n in (1800, 7200)},
    # training (Step C): the TRUE world, B = 1, a few hundred simulations at a depth floor
    **{f"train_{n}_b{b}": {"worlds": 1, "tree": dict(sims=n, mode="br_prior", root_rule="gumbel_mctx", batch=b)}
       for n in (256, 1024) for b in (1, 4, 8, 16)},
}


def _qos_background() -> bool:
    try:
        return os.getpriority(4, 0) != 0          # PRIO_DARWIN_PROCESS: nonzero under background QoS
    except OSError:
        return False


def bench(args) -> int:
    import resource
    import pkmn_gen1
    import torch
    import rollout_q as rq
    from rl.envs.engine_tables import build_tables
    from rl.search import native_tree
    from rl.search.native import World
    from rl.search.resample import resample_world

    load1 = os.getloadavg()[0]
    niced = os.nice(0) != 0
    if not args.worker and not args.force:
        if niced or _qos_background():
            sys.exit("REFUSED: a timed instrument runs at nice 0 and normal QoS (CLAUDE.md: never nice what you time)")
        if load1 > args.max_load:
            sys.exit(f"REFUSED: 1-min load {load1:.2f} > --max-load {args.max_load}: the bench needs the quiet box")
    configs = {k: v for k, v in BENCH_CONFIGS.items() if not args.configs or k in args.configs.split(",")}
    unknown = sorted(set(args.configs.split(",")) - set(BENCH_CONFIGS)) if args.configs else []
    if unknown:
        sys.exit(f"unknown bench config(s) {unknown}; known: {sorted(BENCH_CONFIGS)}")
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_all, g0_summary, _belief = load_g0(pathlib.Path(args.g0_dir))
    # turn-stratified roots: the lowest pids of each bucket
    by_b: dict[int, list] = {}
    for r in sorted(rows_all, key=lambda r: int(r["pid"])):
        by_b.setdefault(int(r["bucket"]), []).append(r)
    roots = sorted([r for b in sorted(by_b) for r in by_b[b][: args.per_bucket]], key=lambda r: int(r["pid"]))

    if not args.worker:
        # the parent: one pass per worker count, each spawning that many worker processes
        stamps = None
        summary = {"version": BENCH_VERSION, "load1_at_start": load1, "configs": configs, "runs": {}}
        for w in [int(x) for x in args.workers.split(",")]:
            tag = f"{args.tag}_w{w}"
            procs = [subprocess.Popen([sys.executable, __file__, "bench", "--worker", f"{i}/{w}", "--tag", tag,
                                       "--out-dir", str(out_dir), "--g0-dir", args.g0_dir, "--per-bucket", str(args.per_bucket),
                                       "--torch-threads", str(args.torch_threads)]
                                      + (["--configs", args.configs] if args.configs else []))
                     for i in range(w)]
            t0 = time.time()
            codes = [p.wait() for p in procs]
            wall = time.time() - t0
            if any(codes):
                sys.exit(f"worker exit codes {codes} at {w} workers")
            recs = []
            for i in range(w):
                recs += [json.loads(x) for x in (out_dir / f"bench_{tag}.w{i}.jsonl").read_text().splitlines() if x.strip()]
            summary["runs"][str(w)] = _bench_summary(recs, w, wall)
        g2l = json.loads((MAIN_CHECKOUT / "results" / "r7_g2" / "g2l.json").read_text())
        per_battle = float(g2l["search/searched"]) / float(g2l.get("battles_finished") or 3200)
        summary["searched_decisions_per_battle"] = per_battle
        for w, run in summary["runs"].items():
            for name, c in run["configs"].items():
                c["hours_per_3200_battle_arm_per_worker"] = 3200 * per_battle * c["ms_mean"] / 3.6e6
        summary["written"] = dt.datetime.now(dt.timezone.utc).isoformat()
        (out_dir / f"bench_{args.tag}.json").write_text(json.dumps(summary, indent=1))
        for w, run in summary["runs"].items():
            for name, c in run["configs"].items():
                print(f"[ii] w{w} {name:22s} ms p50 {c['ms_p50']:7.0f} p99 {c['ms_p99']:7.0f} | sims/s/worker {c['sims_per_s']:6.0f} "
                      f"| rows/fwd {c['rows_per_forward']:5.1f} | depth {c['depth_mean']:.2f} | split v/p/e/py "
                      f"{c['split']['value']:.2f}/{c['split']['prior']:.2f}/{c['split']['engine']:.2f}/{c['split']['python']:.2f} "
                      f"| h/arm {c['hours_per_3200_battle_arm_per_worker']:.1f}")
        return 0

    # a worker: every config over its slice of the roots, one line per decision
    torch.set_num_threads(args.torch_threads)
    i_w, n_w = (int(x) for x in args.worker.split("/"))
    mine = [r for j, r in enumerate(roots) if j % n_w == i_w]
    committee, _prov = rq.load_committee([c["path"] for c in g0_summary["committee"]],
                                         [c["sha256"] for c in g0_summary["committee"]], np.random.default_rng(0))
    tables, _fp = build_tables()

    def value_fn(e):
        return committee.critic(e["obs"])

    path = out_dir / f"bench_{args.tag}.w{i_w}.jsonl"
    with path.open("w") as f:
        for name, cfg in configs.items():
            dials = native_tree.dials_from(cfg["tree"])
            for r in mine:
                node = pkmn_gen1.SearchNode.load(base64.b64decode(r["node_b64"]))
                m1 = np.asarray(node.mask(tables, "p1"), bool)
                prior1 = np.where(m1, np.asarray(r["pi1"], np.float64), 0.0)
                if cfg["worlds"] == 1:
                    ws, opp = [World(node)], np.where(np.asarray(node.mask(tables, "p2"), bool), np.asarray(r["pi2"]), 0.0)
                else:
                    wrng = np.random.default_rng([20260923, int(r["pid"])])
                    ws = []
                    for _b in range(cfg["worlds"]):
                        try:
                            w_, _i = resample_world(node, tables, "p1", wrng)
                        except RuntimeError:
                            continue
                        if np.array_equal(np.asarray(w_.mask(tables, "p1"), bool), m1):
                            ws.append(World(w_))
                    opp = None
                    if not ws:
                        continue
                t0 = time.perf_counter()
                res = native_tree.search(ws, tables, "p1", prior1, opp, value_fn, committee.probs,
                                         int(r["pid"]) * 7919 + 1, **dials)
                ms = (time.perf_counter() - t0) * 1e3
                c = res["counters"]
                f.write(json.dumps({"config": name, "pid": int(r["pid"]), "ms": ms, "sims": c["tree/sims"],
                                    "leaves": c["search/leaves"], "fwd_v": c["tree/forwards_v"], "fwd_p": c["tree/forwards_p"],
                                    "prior_rows": c["tree/prior_rows"], "depth": c["tree/depth_mean"],
                                    "upd": c["tree/upd_mean"], "turns": c["tree/turns_mean"], "ms_value": c["tree/ms_value"],
                                    "ms_prior": c["tree/ms_prior"], "ms_engine": c["search/rust_ms"],
                                    "rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20}) + "\n")
                f.flush()
    return 0


def _bench_summary(recs: list[dict], workers: int, wall: float) -> dict:
    out = {"workers": workers, "wall_s": wall, "configs": {}}
    for name in sorted({x["config"] for x in recs}):
        xs = [x for x in recs if x["config"] == name]
        ms = np.array([x["ms"] for x in xs])
        tot = ms.sum()
        v = sum(x["ms_value"] for x in xs)
        pr = sum(x["ms_prior"] for x in xs)
        e = sum(x["ms_engine"] for x in xs)
        out["configs"][name] = {
            "decisions": len(xs), "ms_mean": float(ms.mean()), "ms_p50": float(np.percentile(ms, 50)),
            "ms_p99": float(np.percentile(ms, 99)), "sims_per_s": float(sum(x["sims"] for x in xs) / (tot / 1e3)),
            "leaves_per_s": float(sum(x["leaves"] for x in xs) / (tot / 1e3)),
            "rows_per_forward": float(sum(x["leaves"] for x in xs) / max(sum(x["fwd_v"] for x in xs), 1)),
            "prior_rows_per_forward": float(sum(x["prior_rows"] for x in xs) / max(sum(x["fwd_p"] for x in xs), 1)),
            "depth_mean": float(np.mean([x["depth"] for x in xs])), "upd_mean": float(np.mean([x["upd"] for x in xs])),
            "turns_mean": float(np.mean([x["turns"] for x in xs])), "rss_mb_max": float(max(x["rss_mb"] for x in xs)),
            "split": {"value": v / tot, "prior": pr / tot, "engine": e / tot, "python": max(0.0, 1 - (v + pr + e) / tot)},
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    red = sub.add_parser("reduction", help="gate (i-a): the depth-1 reduction to native.solve")
    orc = sub.add_parser("oracle", help="gate (i-c): decision quality on G0's oracle at matched override")
    bch = sub.add_parser("bench", help="gate (ii): the P-core bench (the quiet box, nice 0)")
    dif = sub.add_parser("diff", help="the regression check: two oracle tags' shared roots, bitwise")
    for p in (red, orc, bch, dif):
        p.add_argument("--g0-dir", default=str(MAIN_CHECKOUT / "results" / "r7_g0"))
        p.add_argument("--out-dir", default=str(MAIN_CHECKOUT / "results" / "native_tree"))
        p.add_argument("--limit", type=int, default=0)
        p.add_argument("--torch-threads", type=int, default=1)
    orc.add_argument("--shard", default="0/1", help="i/n: this process measures pids with pid %% n == i")
    orc.add_argument("--tag", default="oracle")
    orc.add_argument("--worlds", type=int, default=8, help="the critic L-op's B")
    orc.add_argument("--belief-seed", type=int, default=20260923, help="the belief read's --seed: the same worlds")
    orc.add_argument("--summarise", action="store_true", help="measure nothing: join every shard of --tag and score it")
    bch.add_argument("--configs", default="", help=f"comma list (default all): {sorted(BENCH_CONFIGS)}")
    bch.add_argument("--workers", default="1,2,5,10", help="worker counts, one pass each")
    bch.add_argument("--per-bucket", type=int, default=10, help="roots per turn bucket (the proposal's full bench: 50)")
    bch.add_argument("--tag", default="bench")
    bch.add_argument("--max-load", type=float, default=1.5)
    bch.add_argument("--force", action="store_true", help="run on a busy box anyway (the numbers are then NOT the bench)")
    bch.add_argument("--worker", default="", help=argparse.SUPPRESS)
    dif.add_argument("--tag", required=True)
    dif.add_argument("--against", required=True, help="the reference tag (e.g. rows from an earlier commit)")
    args = ap.parse_args()
    if os.environ.get("POKEMON_RL_ENCODER_C6"):
        sys.exit("REFUSED: POKEMON_RL_ENCODER_C6 is set; G0's rows and the W finals are c6-off")
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    sys.exit({"reduction": reduction, "oracle": oracle, "bench": bench, "diff": oracle_diff}[args.cmd](args))


if __name__ == "__main__":
    main()
