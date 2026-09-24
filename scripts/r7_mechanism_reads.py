#!/usr/bin/env python
"""R7 fleet MECHANISM READS (iii) and (vi) -- the instrument the fleet pre-reg names (scripts/derive_r7_fleet.py's
header), built before launch because nothing else scored a NEW checkpoint on G0's banked rows (the design review,
2026-09-24: rollout_q.py samples its own positions under its own checkpoints; rollout_q_evaluator.py regrets against
the banked R5 greedy).

On a fixed, bucket-balanced subset of G0's positions (the first --per-bucket rows of each of G0's four turn buckets,
in row order: the same positions for every lane), for each scored unit (one checkpoint, or --committee for all of
them as one committee):
  (iii) SPEARMAN   the per-position rank correlation of the unit's critic over the position's cells (the mean of S
                   chance leaves per cell, terminal leaves taking their outcome -- native.solve's rule) against G0's
                   rollout cell means: rollout_q_evaluator.py's `spearman_base`, the same leaves (its S 4 and seeds).
  (vi)  REGRET     the unit's greedy at the root (its masked argmax, the committee rule G0 used for `a_greedy`) scored
                   on G0's banked split halves: 0.5 * [(qb[argmax qa] - qb[a]) + (qa[argmax qb] - qa[a])], with
                   qa/qb = q_half_a/b @ q_col and q_col the banked foe prior -- rollout_q.py's regret_split with the
                   unit's action for the banked greedy. A FIXED YARDSTICK: the Q-values are rollouts under the R5
                   committee, not the student's own continuation (disclosed with every number).
Nodes are re-encoded under THIS process's encoder flags (G0's rows are c6 off; the fleet's checkpoints are c6 on:
run with POKEMON_RL_ENCODER_C6=1 for them). --expect-reproduce asserts, for the R5 W committee under G0's own
flags, that the unit's greedy IS the banked a_greedy, the regret IS the banked regret_depth1_ceiling and the Spearman
IS the evaluator's spearman_base, on every scored position (the instrument's provenance test).

    python scripts/r7_mechanism_reads.py --rows <main>/results/r7_g0/rollout_q.rows.jsonl \\
        --checkpoints runs/r7_fleet_searched_f1_s376/ckpt_*.pt ... --out results/r7_mech/end.json
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
VERSION = "r7_mechanism_reads/1"
S_LEAVES = 4               # rollout_q_evaluator.py's --leaf-samples default (its spearman_base)
PER_BUCKET = 50            # the fleet pre-reg's positions: the first 50 of each of G0's four buckets


def select(rows: list[dict], per_bucket: int) -> list[dict]:
    if per_bucket <= 0:
        return rows
    seen: dict[int, int] = {}
    out = []
    for r in rows:
        b = int(r["bucket"])
        if seen.get(b, 0) < per_bucket:
            out.append(r)
            seen[b] = seen.get(b, 0) + 1
    return out


def regret_banked(r: dict, a: int) -> float:
    pi2 = np.asarray(r["pi2"], float)
    q_col = pi2[r["cols"]] / pi2[r["cols"]].sum()
    qa = np.asarray(r["q_half_a"], float) @ q_col
    qb = np.asarray(r["q_half_b"], float) @ q_col
    j = {act: i for i, act in enumerate(r["rows"])}[int(a)]
    return 0.5 * (float(qb[int(np.argmax(qa))] - qb[j]) + float(qa[int(np.argmax(qb))] - qa[j]))


def ms(xs) -> tuple[float, float]:
    x = np.asarray([v for v in xs if v == v], float)
    return float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True, help="G0's rows (read only)")
    ap.add_argument("--checkpoints", nargs="+", required=True)
    ap.add_argument("--sha256", nargs="*", default=None)
    ap.add_argument("--committee", action="store_true", help="score the checkpoints as ONE committee (else each alone)")
    ap.add_argument("--per-bucket", type=int, default=PER_BUCKET)
    ap.add_argument("--expect-reproduce", default=None,
                    help="the evaluator's rows (rollout_q_evaluator.py .rows.jsonl): assert the provenance identities")
    ap.add_argument("--out", required=True)
    ap.add_argument("--torch-threads", type=int, default=2)
    args = ap.parse_args()
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    import torch
    torch.set_num_threads(args.torch_threads)
    import pkmn_gen1
    from rl.envs.engine_tables import build_tables
    from rl.search import native
    import rollout_q as rq
    from rollout_q_evaluator import spearman

    rows_path = pathlib.Path(args.rows)
    rows = select(rq.load_rows(rows_path), args.per_bucket)
    if not rows:
        sys.exit(f"no rows in {rows_path}")
    tables, _fp = build_tables()
    rng = np.random.default_rng(20260924)
    units = ([list(range(len(args.checkpoints)))] if args.committee else [[i] for i in range(len(args.checkpoints))])
    t0 = time.time()
    # the LAUNCH commit, before anything runs (a sha taken at write time describes a different tree)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, cwd=ROOT).stdout.strip())
    # Render every position's cells once (the leaves do not depend on the scored unit).
    pos = []
    for r in rows:
        node = pkmn_gen1.SearchNode.load(base64.b64decode(r["node_b64"]))
        cells = [(a, b, S_LEAVES) for a in r["rows"] for b in r["cols"]]
        e = node.expand(tables, "p1", cells, native.seed_base(int(r["pid"]) * 1_000_033 + 17, 0), both_views=False)
        if int(e["n"]) != len(cells) * S_LEAVES or not np.array_equal(
                np.asarray(e["cell"]), np.repeat(np.arange(len(cells)), S_LEAVES)):
            sys.exit(f"pid {r['pid']}: leaves are not {S_LEAVES} per cell in cell order -- the reshape would misalign")
        term = np.asarray(e["terminal"]).reshape(len(cells), S_LEAVES)
        pos.append({"row": r, "node": node, "obs": np.asarray(e["obs"], np.float32).reshape(len(cells) * S_LEAVES, -1),
                    "live": term == 0, "tval": np.where(term == 2, 0.0, term.astype(np.float64)),
                    "q": (0.5 * (np.asarray(r["q_half_a"], float) + np.asarray(r["q_half_b"], float))).reshape(-1),
                    "mask1": np.asarray(node.mask(tables, "p1"), bool),
                    "obs1": np.asarray(node.obs(tables, "p1"), np.float32)})
    results = []
    per_rows = []
    for unit in units:
        paths = [args.checkpoints[i] for i in unit]
        shas = [args.sha256[i] for i in unit] if args.sha256 else None
        committee, prov = rq.load_committee(paths, shas, rng)
        sp, rg, agree = [], [], []
        for p in pos:
            r = p["row"]
            pi1 = committee.probs(p["obs1"][None], p["mask1"][None])[0]
            a = int(np.argmax(np.where(p["mask1"], pi1, -1.0)))
            v = committee.critic(p["obs"]).reshape(p["live"].shape)
            cell = np.where(p["live"], v, p["tval"]).mean(axis=1)
            s, g = spearman(cell, p["q"]), regret_banked(r, a)
            sp.append(s); rg.append(g); agree.append(a == int(r["a_greedy"]))
            per_rows.append({"unit": [x["path"] for x in prov], "pid": int(r["pid"]), "bucket": int(r["bucket"]),
                             "a_student": a, "a_banked_greedy": int(r["a_greedy"]), "regret": g, "spearman": s,
                             "pi1_max_abs_diff_vs_banked": float(np.max(np.abs(np.where(p["mask1"], pi1, 0.0) - np.asarray(r["pi1"], float))))})
        (sm, sse), (gm, gse) = ms(sp), ms(rg)
        results.append({"unit": prov, "positions": len(pos), "spearman_mean": sm, "spearman_se": sse,
                        "regret_mean": gm, "regret_se": gse, "agree_banked_greedy": float(np.mean(agree))})
        print(f"[mech] {', '.join(pathlib.Path(x['path']).parent.name for x in prov)}: spearman {sm:+.4f} +- {sse:.4f}, "
              f"regret {gm:+.5f} +- {gse:.5f} over {len(pos)} positions (banked-greedy agreement {np.mean(agree):.3f})", flush=True)
    summary = {"version": VERSION, "rows": str(rows_path), "rows_sha256": hashlib.sha256(rows_path.read_bytes()).hexdigest(),
               "per_bucket": args.per_bucket, "pids": [int(p["row"]["pid"]) for p in pos], "s_leaves": S_LEAVES,
               "encoder": {k: os.environ.get(k) for k in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS", "POKEMON_RL_ENCODER_C6")},
               "rows_c6": sorted({str(p["row"].get("c6")) for p in pos}), "committee": args.committee, "git_sha": sha,
               "git_dirty": dirty, "seconds": time.time() - t0, "units": results,
               "yardstick": "G0's banked split halves: rollouts under the R5 committee, not the student's continuation"}
    if args.expect_reproduce:
        ev = {int(json.loads(l)["pid"]): json.loads(l) for l in pathlib.Path(args.expect_reproduce).read_text().splitlines() if l.strip()}
        bad = []
        for pr in per_rows:
            r = next(p["row"] for p in pos if int(p["row"]["pid"]) == pr["pid"])
            if pr["a_student"] != pr["a_banked_greedy"]:
                bad.append((pr["pid"], "greedy", pr["a_student"], pr["a_banked_greedy"]))
            if abs(pr["regret"] - float(r["regret_depth1_ceiling"])) > 1e-9:
                bad.append((pr["pid"], "regret", pr["regret"], r["regret_depth1_ceiling"]))
            e = ev.get(pr["pid"])
            if e is not None and abs(pr["spearman"] - float(e["spearman_base"])) > 1e-9:
                bad.append((pr["pid"], "spearman", pr["spearman"], e["spearman_base"]))
        summary["reproduce"] = {"checked": len(per_rows), "failures": bad[:20], "n_failures": len(bad)}
        print(f"[mech] REPRODUCE: {len(per_rows)} positions checked, {len(bad)} failures" + (f": {bad[:5]}" if bad else ""))
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=1) + "\n")
    out.with_suffix(".rows.jsonl").write_text("".join(json.dumps(x) + "\n" for x in per_rows))
    print(f"wrote {out}")
    if args.expect_reproduce and summary["reproduce"]["n_failures"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
