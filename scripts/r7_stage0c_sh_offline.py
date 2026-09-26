#!/usr/bin/env python
"""Stage 0c OFFLINE: SEQUENTIAL HALVING over rows vs UNIFORM allocation, on the R = 512 follow-up's stored rollouts
(results/r7_stage0c/stage0c_r512.rows.s*of2.jsonl: 100 positions x 512 belief worlds x the full matrix, one rollout
per cell, kept per world). No new rollout: every operator below re-reads the same outcomes.

    PYTHONPATH=<main> python scripts/r7_stage0c_sh_offline.py > results/r7_stage0c/stage0c_r512.sh_offline.txt

Scored exactly as Stage 0c scores (scripts/r7_stage0c_rollout_curve.py): soft_br at the belief L-op's tau, gated to
the banked critic L-op's native override rate by a quantile of the operator's own margins, gains on G0's true-world
oracle in win-rate units. It first REPRODUCES the stored full/soft_br candidates and margins at R 128/256/512 bit for
bit, or stops. SH: ceil(log2 rows) phases, the budget split evenly across phases, each phase's worlds shared by the
surviving rows (CRN), the top half by the soft_br logit kept and the GREEDY row always kept (the hedged root that
prices the margin), until two remain or the 512 worlds run out. DESCRIPTIVE planning numbers for Stage 1's operator
cost: in-sample on the same rollouts that define the full-512 choice it is compared with.
"""
import glob
import json
import math
import sys

import numpy as np

import pathlib
MAIN = str(pathlib.Path(__file__).resolve().parents[1])
sys.path.insert(0, MAIN + "/scripts")
import r7_stage0c_rollout_curve as s0c  # noqa: E402

rows = [json.loads(l) for f in sorted(glob.glob(MAIN + "/results/r7_stage0c/stage0c_r512.rows.s*of2.jsonl"))
        for l in open(f) if l.strip()]
rows = sorted((r for r in rows if "error" not in r), key=lambda r: r["pid"])
g0 = {}
for l in open(MAIN + "/results/r7_g0/rollout_q.rows.jsonl"):
    if l.strip():
        x = json.loads(l); g0[int(x["pid"])] = x
bel = {}
for l in open(MAIN + "/results/r7_g0/belief_k4s2t005.rows.jsonl"):
    if l.strip():
        x = json.loads(l); bel[int(x["pid"])] = x
tau = float(json.load(open(MAIN + "/results/r7_g0/belief_k4s2t005.json"))["dials"]["tau"])

P = []
for r in rows:
    pid = int(r["pid"]); g = g0[pid]
    prows = [int(a) for a in r["rows"]]
    pi1 = np.asarray(g["pi1"], float)
    prior_m = pi1[prows] / pi1[prows].sum()
    ig = prows.index(int(r["a_greedy"]))
    ws = sorted(r["worlds"], key=lambda w: int(w["b"]))
    Q = np.zeros((len(ws), len(prows))); cost = np.zeros(len(ws), int)
    for i, w in enumerate(ws):
        o = s0c.decode_i8(w["o"], (len(prows), len(w["cols"])))
        p2 = np.asarray(w["p2"], float)
        Q[i] = o @ (p2 / p2.sum())
        cost[i] = len(w["cols"])
    P.append({"pid": pid, "rows": prows, "prior": prior_m, "ig": ig, "Q": Q, "cost": cost, "r": r,
              "orc": s0c.oracle_of(g), "greedy": int(r["a_greedy"])})

target = float(np.mean([int(bel[p["pid"]]["a_belief"]) != int(bel[p["pid"]]["a_greedy"]) for p in P]))


def score(cands, margins):
    moves = np.array([c != p["greedy"] for c, p in zip(cands, P)])
    og = s0c.gains_for(cands, [p["orc"] for p in P], [p["greedy"] for p in P])
    return s0c.read_operator(moves, np.array(margins), og, target)


def uniform(R):
    cands, margins, spent = [], [], []
    for p in P:
        q = p["Q"][:R].mean(axis=0)
        j, m = s0c.root_candidate(p["prior"], q, "soft_br", tau, p["ig"])
        cands.append(p["rows"][j]); margins.append(m); spent.append(int(p["cost"][:R].sum()) * len(p["rows"]))
    return cands, margins, spent


# reproduction: the stored rung candidates and margins, bit for bit
for R in (128, 256, 512):
    c, m, _ = uniform(R)
    st = [(p["r"]["rungs"][str(R)]["full/soft_br"]["cand"], p["r"]["rungs"][str(R)]["full/soft_br"]["margin"]) for p in P]
    assert [x[0] for x in st] == c and np.allclose([x[1] for x in st], m, atol=1e-12), R
print(f"reproduced the stored full/soft_br candidates and margins at R 128/256/512 on {len(P)} positions; target {target:.3f}")


def sh(budget, keep_greedy=True):
    cands, margins, spent = [], [], []
    for p in P:
        n = len(p["rows"]); surv = list(range(n))
        phases = max(1, math.ceil(math.log2(n)))
        per = budget / phases
        s = np.zeros(n); k = np.zeros(n); nxt = 0; used = 0
        while True:
            avg = p["cost"].mean()
            m = max(1, int(per // (len(surv) * avg)))
            take = list(range(nxt, min(nxt + m, len(p["Q"]))))
            if not take:
                break
            for i in surv:
                s[i] += p["Q"][take, i].sum(); k[i] += len(take)
            used += int(p["cost"][take].sum()) * len(surv)
            nxt += len(take)
            if len(surv) <= (2 if keep_greedy else 1):
                if used >= budget or nxt >= len(p["Q"]):
                    break
                continue
            z = {i: math.log(p["prior"][i]) + (s[i] / k[i]) / tau for i in surv}
            ranked = sorted(surv, key=lambda i: -z[i])
            keep = ranked[: max(1, math.ceil(len(surv) / 2))]
            if keep_greedy and p["ig"] not in keep:
                keep = keep + [p["ig"]]
            surv = keep
            if used >= budget or nxt >= len(p["Q"]):
                break
        q = np.where(k > 0, s / np.maximum(k, 1), -np.inf)
        z = np.array([math.log(p["prior"][i]) + q[i] / tau if k[i] > 0 else -np.inf for i in range(n)])
        j = int(np.argmax(z))
        cands.append(p["rows"][j]); margins.append(float(q[j] - q[p["ig"]])); spent.append(used)
    return cands, margins, spent


full512 = uniform(512)[0]
print(f"\n{'operator':24s} {'rollouts/decision':>18s} {'gain @matched (win rate)':>28s} {'agree w/ full-512':>18s}")
for R in (8, 16, 32, 64, 128, 256, 512):
    c, m, sp = uniform(R)
    g = score(c, m)["gain"]
    print(f"{'uniform R ' + str(R):24s} {np.mean(sp):18.0f} {g['mean']:+14.4f} +- {g['se']:.4f} {np.mean([a == b for a, b in zip(c, full512)]):18.2f}")
for B in (1500, 3000, 6000, 12000, 24000):
    c, m, sp = sh(B)
    g = score(c, m)["gain"]
    print(f"{'SH budget ' + str(B):24s} {np.mean(sp):18.0f} {g['mean']:+14.4f} +- {g['se']:.4f} {np.mean([a == b for a, b in zip(c, full512)]):18.2f}")
# paired: SH at each budget minus uniform 512, per position at the matched rate
u = score(*uniform(512)[:2])["per_position"]
for B in (3000, 6000, 12000):
    x = score(*sh(B)[:2])["per_position"]
    d = x - u
    print(f"paired SH {B} - uniform 512: {d.mean():+.4f} +- {d.std(ddof=1) / math.sqrt(len(d)):.4f}")
