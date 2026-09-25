#!/usr/bin/env python
"""R7 G0, the ROOT-RULE read (after the 2026-09-23 simultaneous-move note):
on the saved positions, which root rule turns the SAME payoff matrix into the
best play -- greedy (the policy's argmax), the pure and the soft best
response to the foe's prior (`native.solve`'s rule), regret matching's
average strategy (the matrix's Nash equilibrium, Lisy et al. 2013), or the
pure maximin row -- scored against G0's OWN ROLLOUT ORACLE two ways:

  under_prior     E_{a~sigma, b~pi_opp}[Qbar_rollout(a, b)]  -- what the rule
                  gets against the foe it modelled;
  vs_best_reply   min_b E_{a~sigma}[Qbar_rollout(a, b)]      -- what it gets
                  against a foe who replies to the RULE (exploitability).

Two levels. `--level oracle` (default; numpy only, seconds) applies every rule
to the ROLLOUT matrix itself: the ceiling of each rule under a perfect
evaluator, i.e. whether solving the matrix beats best-responding to the prior
when the values are right. `--level critic` re-solves each position with the
committee's observation critic at the given dials (k, S) and applies the rules
to the CRITIC's matrix, scoring the chosen row distribution on the rollout
matrix restricted to those columns -- the operator-level read, at matched
override rates (the sweep's device). Both report win-rate units, pooled and
by turn bucket, with the override rate (mass moved off the greedy row) beside
every number. Rule 6: a mechanism read, never a win-rate A/B.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from rl.search import root_rules as rr  # noqa: E402

VERSION = "rollout_q_root_rules/1"


def read_position(r: dict) -> dict:
    rows_a, cols_b = r["rows"], r["cols"]
    pi1, pi2 = np.asarray(r["pi1"], float), np.asarray(r["pi2"], float)
    qa, qb = np.asarray(r["q_half_a"], float), np.asarray(r["q_half_b"], float)   # (n_rows, n_cols) outcome units
    prior_rows = pi1[rows_a] / pi1[rows_a].sum()
    q_col = pi2[cols_b] / pi2[cols_b].sum()
    return {"q": 0.5 * (qa + qb), "qa": qa, "qb": qb, "prior_rows": prior_rows, "q_col": q_col,
            "greedy": rows_a.index(int(r["a_greedy"])), "rows": rows_a, "cols": cols_b,
            "bucket": int(r["bucket"]), "pid": int(r["pid"])}


def score_rule(rule: str, pos: dict, q_for_rule: np.ndarray, q_col_for_rule: np.ndarray, tau: float, rm_iters: int,
               split: bool = False) -> dict:
    """`split`: the rule sees ONE half of the rollouts and is scored on the
    OTHER (both orderings, averaged) -- the ceiling's split-sample discipline,
    so neither the chosen row's value (winner's curse) nor the worst column
    (the min over noisy columns) is read on the samples that selected it. Off
    the split, `q_for_rule` is the caller's matrix (the critic's at the critic
    level; the full oracle at the oracle level, in-sample)."""
    g = pos["greedy"]
    if not split:
        sigma = rr.apply_rule(rule, q_for_rule, pos["prior_rows"], q_col_for_rule, g, tau=tau, rm_iters=rm_iters)
        ev = rr.evaluate(sigma, pos["q"], pos["q_col"])
        return {"under_prior": ev["under_prior"], "vs_best_reply": ev["vs_best_reply"],
                "override": float(1.0 - sigma[g]), "argmax_differs": float(int(np.argmax(sigma)) != g)}
    out = {"under_prior": 0.0, "vs_best_reply": 0.0, "override": 0.0, "argmax_differs": 0.0}
    for q_sel, q_eval in ((pos["qa"], pos["qb"]), (pos["qb"], pos["qa"])):
        sigma = rr.apply_rule(rule, q_sel, pos["prior_rows"], pos["q_col"], g, tau=tau, rm_iters=rm_iters)
        ev = rr.evaluate(sigma, q_eval, pos["q_col"])
        out["under_prior"] += 0.5 * ev["under_prior"]
        out["vs_best_reply"] += 0.5 * ev["vs_best_reply"]
        out["override"] += 0.5 * float(1.0 - sigma[g])
        out["argmax_differs"] += 0.5 * float(int(np.argmax(sigma)) != g)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--level", choices=("oracle", "critic"), default="oracle")
    ap.add_argument("--split", action="store_true", help="oracle level: choose on one half of the rollouts, score on the other")
    ap.add_argument("--tau", type=float, nargs="+", default=[1.0, 0.5, 0.25, 0.1])
    ap.add_argument("--rm-iters", type=int, default=2000)
    ap.add_argument("--checkpoints", nargs="*", default=None, help="critic level only")
    ap.add_argument("--sha256", nargs="*", default=None)
    ap.add_argument("--cols-k", type=int, default=3)
    ap.add_argument("--chance-s", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=20260923)
    args = ap.parse_args()
    import rollout_q as rq
    rows = rq.load_rows(pathlib.Path(args.rows))
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        sys.exit("no rows")
    positions = [read_position(r) for r in rows]

    critic_q = None
    if args.level == "critic":
        os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
        os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
        import torch
        torch.set_num_threads(2)
        import pkmn_gen1
        from rl.envs.engine_tables import build_tables
        from rl.search import native
        rng = np.random.default_rng(args.seed)
        committee, prov = rq.load_committee(args.checkpoints, args.sha256, rng)
        tables, _ = build_tables()
        value_fn = lambda e: committee.critic(e["obs"])
        critic_q = []
        t0 = time.time()
        for i, (r, pos) in enumerate(zip(rows, positions)):
            node = pkmn_gen1.SearchNode.load(base64.b64decode(r["node_b64"]))
            pi1 = np.asarray(r["pi1"]); pi2 = np.asarray(r["pi2"])
            mask1 = np.asarray(node.mask(tables, "p1"), bool); mask2 = np.asarray(node.mask(tables, "p2"), bool)
            res = native.solve([native.World(node)], tables, "p1", np.where(mask1, pi1, 0.0), np.where(mask2, pi2, 0.0),
                               value_fn, pos["pid"] * 31 + 7, cols_k=args.cols_k, chance_s=args.chance_s, tau=1.0)
            # The critic's matrix over the operator's columns; the oracle is
            # then read on the SAME columns so the two matrices align.
            col_idx = [pos["cols"].index(c) for c in res["cols"]] if res["cols"] != [-1] else list(range(len(pos["cols"])))
            critic_q.append((np.asarray(res["q_cell"], float), col_idx, np.asarray(res["q_col"], float)))
            if (i + 1) % 50 == 0:
                print(f"{i + 1}/{len(rows)} solved, {(time.time() - t0) / (i + 1):.2f} s/pos", flush=True)

    cells: dict[tuple, list[dict]] = {}
    for i, pos in enumerate(positions):
        if args.level == "oracle":
            variants = [("oracle", pos["q"], pos["q_col"], pos)]
        else:
            qc, col_idx, qcol_c = critic_q[i]
            sub = dict(pos)
            sub["q"] = pos["q"][:, col_idx]                    # the oracle on the operator's columns
            sub["q_col"] = pos["q_col"][col_idx] / pos["q_col"][col_idx].sum()
            variants = [("critic", qc, qcol_c, sub)]
        for level, q_rule, qcol_rule, p_eval in variants:
            for rule in rr.RULES:
                taus = args.tau if rule == "soft_br" else [None]
                for tau in taus:
                    key = (level, rule, tau)
                    s = score_rule(rule, p_eval, q_rule, qcol_rule, tau if tau is not None else 1.0, args.rm_iters,
                                   split=(args.split and level == "oracle"))
                    s["bucket"] = pos["bucket"]
                    cells.setdefault(key, []).append(s)

    def summarise(sel: list[dict]) -> dict:
        out = {"positions": len(sel)}
        for k in ("under_prior", "vs_best_reply", "override", "argmax_differs"):
            m, se = rq.mean_se([s[k] for s in sel])
            out[k] = {"mean_win_rate": rq.win_rate(m), "se_win_rate": rq.win_rate(se) if se == se else se} if k in ("under_prior", "vs_best_reply") else {"mean": m, "se": se}
        return out
    table = []
    for (level, rule, tau), sel in cells.items():
        entry = {"level": level, "rule": rule, "tau": tau, "pooled": summarise(sel), "by_bucket": {}}
        for b, (lo, hi) in enumerate(rq.BUCKETS):
            sb = [s for s in sel if s["bucket"] == b]
            if sb:
                entry["by_bucket"][f"{lo}-{'+' if hi > 999 else hi}"] = summarise(sb)
        table.append(entry)
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"version": VERSION, "written": dt.datetime.now(dt.timezone.utc).isoformat(),
                                    "level": args.level, "split": bool(args.split), "positions": len(rows), "rows_file": args.rows,
                                    "dials": {"tau": args.tau, "rm_iters": args.rm_iters, "cols_k": args.cols_k, "chance_s": args.chance_s},
                                    "table": table}, indent=1))
    greedy = next(e for e in table if e["rule"] == "greedy")["pooled"]
    md = [f"# Root rules on the saved positions ({VERSION}, level {args.level}{', SPLIT-SAMPLE' if args.split else ', in-sample'}) -- {len(rows)} positions, WIN-RATE units", "",
          "| rule | tau | under prior ± se | Δ vs greedy | vs best reply ± se | Δ vs greedy | override (mass) | argmax differs |",
          "|---|--:|---|--:|---|--:|--:|--:|"]
    for e in table:
        p = e["pooled"]
        md.append(f"| {e['rule']} | {e['tau'] if e['tau'] is not None else ''} | {p['under_prior']['mean_win_rate']:+.4f} ± {p['under_prior']['se_win_rate']:.4f} | "
                  f"{p['under_prior']['mean_win_rate'] - greedy['under_prior']['mean_win_rate']:+.4f} | "
                  f"{p['vs_best_reply']['mean_win_rate']:+.4f} ± {p['vs_best_reply']['se_win_rate']:.4f} | "
                  f"{p['vs_best_reply']['mean_win_rate'] - greedy['vs_best_reply']['mean_win_rate']:+.4f} | "
                  f"{p['override']['mean']:.3f} | {p['argmax_differs']['mean']:.3f} |")
    out_path.with_suffix(".md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nwrote {out_path} and {out_path.with_suffix('.md')}")


if __name__ == "__main__":
    main()
