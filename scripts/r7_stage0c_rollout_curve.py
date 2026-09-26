#!/usr/bin/env python
"""R7 STAGE 0c -- the decision-level BUDGET CURVE: a ROLLOUT-evaluated one-ply
L-op on belief worlds against the CRITIC L-op, on G0's 500 banked positions.

JOURNEY step 14 (the strength chapter; its exit condition asks for "one
comparison at a REAL budget"). This is the mechanism screen that decides whether
that comparison's heavy arm is worth building. It plays NO Foul Play battle and
starts no server.

WHAT IT MEASURES, per G0 position (reloaded from the row's `node_b64`; G0's rows
and the banked belief rows are READ, never written):

  worlds     W draws of `rl/search/resample.py::resample_world` from the belief
             read's OWN generator, default_rng([belief_seed, pid]), so the first
             8 / 32 worlds ARE the critic L-op's B = 8 / 32 worlds (paired on
             worlds). A refused draw is counted and skipped.
  rollouts   in every built world, the FULL matrix -- every legal row of ours x
             every legal foe column OF THAT WORLD -- played to the end ONCE under
             the R5 committee on both seats (G0's rollout policy:
             `scripts/rollout_q.py::Committee.sample`, `SearchNode.leaves`, CRN
             across rows because the engine keys chance on (seed_base, col,
             sample), never the row). Rung R = the first R world DRAWS, so "R
             rollouts per cell" means R belief worlds x one rollout each. The rungs
             are NESTED (the same worlds and rollouts, prefixes of them).
  Qbar_w(a)  sum_b q_w(b) O_w(a, b), q_w the committee's prior on THAT world's foe
             view (the belief read's per-world foe prior, the same call), over the
             columns a variant keeps, renormalised:
               full  every legal foe column             (G0's ceiling construction)
               k4    the world's top-k foe replies, k = the L-op's cols_k (read
                     from the banked dials; 4): the evaluator-only swap
               3x4   our top-3 rows by the prior x k4   (the cheap deployable)
             Qbar(a) = mean over the rung's worlds (PIMC).
  candidate  soft_br (PRIMARY): argmax prior(a) exp(Qbar(a) / tau) at the L-op's
             tau (read from the banked dials; 0.05) -- `native.solve`'s root rule,
             so against the critic L-op only the EVALUATOR changes. argmax
             (secondary): G0's pure best response. margin = Qbar(cand) -
             Qbar(greedy), outcome units.
  critic     `scripts/rollout_q_belief.py::measure` at B = 8 (a provenance check
             against the banked rows) and B = 32 (the breadth axis): the critic
             L-op exactly as banked, dials and gate read from
             results/r7_g0/belief_k4s2t005.json, never typed.

SCORING. Every candidate is scored on G0's TRUE-WORLD rollout oracle (both
halves, 256 rollouts per cell, Qbar under G0's pi2 over every legal column),
exactly as the banked belief read scored `gain_belief`. No choice made here reads
those rollouts: this script draws its own worlds, its own chance seeds (a seed
namespace G0 never used) and its own policy samples. So the full oracle is
unbiased; G0 split its halves only because its own argmax read them.
gain = Qbar_oracle(cand) - Qbar_oracle(greedy), reported in WIN-RATE units
(outcome / 2). Caveats that travel with every number: the estimand is the
committee-vs-committee continuation (the operator's rollouts optimise the same
estimand the oracle measures, so this is decision quality under self-play, not
strength against Foul Play or humans); positions are G0's turn-stratified
self-play positions, not a ladder distribution.

THE GATE, NEVER TUNED ON OUTCOMES. The rows file carries no oracle value. Each
operator is gated post hoc to a TARGET OVERRIDE RATE by a quantile of its OWN
margins: override iff cand != greedy and margin >= g, with g set so the rate
hits the target. (The landmine: MATCH ON THE OVERRIDE RATE, NOT THE DELTA.)

  PRIMARY matched rate: the banked critic belief L-op's own operating point. Its
  native gate (0.01 critic units) overrides 40 of 500 positions, 0.080. The
  brief's nominal 0.10 CANNOT be matched: the critic's PIMC argmax leaves greedy
  on only 41 of 500 positions (0.082), so no gate reaches 0.10 (a DEVIATION,
  stated). Every operator is ALSO read at the nominal 0.10, which the rollout
  rungs do reach, and on a curve of targets.

THE PRE-STATED RULE (written before any full-run row exists; a run with fewer
than 490 positions or without every rung 16/32/64/128 prints NO VERDICT).
d_i = gain_rollout_i - gain_critic_i, paired per position. The rollout operator
is the PRIMARY variant (full matrix, soft_br), gated to the matched rate. The
critic is the banked belief L-op at its native gate, which IS the matched rate.
se = sd(d) / sqrt(N). "Still rising" means gain(128) - gain(64) > 1 se, paired
over positions.

  KEEP LIGHT      upper95 of mean d at R = 128 < 0, AND not still rising: the
                  rollout evaluator does not beat the critic at the matched rate
                  even at 128 worlds -- a MEASURED MECHANISM CEILING on this axis
                  at this budget (rule 6's one permitted kill). Stage 1 gets no
                  heavy arm on this axis.
  STAGE 1         mean d >= 2 se at ANY rung: the axis pays at the decision level.
    at the knee   Stage 1's heavy arm H runs at the KNEE R*, the smallest rung
                  whose gain is within 1 se (paired) of the BEST rung's -- R = 128
                  on a monotone curve; on a curve that peaks and falls, the peak.
                  H uses the 3x4 cells if the 3x4 gain at R* is within 1 se
                  (paired) of the full matrix's, else the full matrix.
                  Precedence: STAGE 1, then KEEP LIGHT, then UNRESOLVED.
  ADD R = 512     still rising (in ANY branch): before Stage 1 or any conclusion,
                  run --worlds 512 --rungs 128 256 512 --per-bucket 25 (the 25
                  lowest pids of each turn bucket, 100 positions), and the knee
                  rule moves to {128, 256, 512}.
  UNRESOLVED      none of the above: rule 6 -- no conclusion; the MDE is reported.

Secondary reads, no branch: the same at the nominal 0.10; k4 vs critic (the
evaluator-only swap on the L-op's own cells); argmax vs soft_br; critic B32 - B8
(the breadth axis); the rollout operator's PEEK (G0's true-world rollout
operator, selected on one half and scored on the other, minus the belief
rollout operator, both at the matched rate); the primary by turn bucket.

THE X-AXIS IS WORK: rollouts per decision (and worlds, cells) per rung and
variant. Seconds are recorded per position as a DISCLOSURE only. This runs under
background QoS on the efficiency cores; the P-core cost is a separate quiet-box
bench (Stage 0b).

RESUME-SAFE. One JSON line per position, version-marked (a file of another
version is refused), appended after the position completes; a restart skips done
pids. A position reproduces bit for bit on resume: its worlds, chance seeds and
policy samples are all keyed on (seed, pid). --shard i/n splits pids across
processes, one rows file each; --summarise joins every shard of a tag.

COUNTERS TO DISK, per row: worlds tried/built/refused (with reasons), resample
tries, rollouts run, lockstep steps, the per-rung work, the error (an error row is
written, counted and never retried), seconds. The summary adds per-rung override
rates, moves-at-gate-0, the B8 reproduction against the banked rows, and the
--self-check result (the lockstep rollout vs `rollout_q.rollout_matrix`).

LAUNCH (the full run; detached, background QoS -- an analysis job, never a
training lane -- resume-safe; the env G0/G1b used, PYTHONPATH on the MAIN checkout,
bytecode writes off so nothing lands in the checkout; POKEMON_RL_ENCODER_C6 must be
unset). From the repo root, O = results/r7_stage0c (the default --out-dir):
  bash -c 'for s in 0 1; do PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl nohup taskpolicy -b \
    /opt/anaconda3/envs/pkmn-engine-r7/bin/python scripts/r7_stage0c_rollout_curve.py --shard $s/2 --self-check \
    --out-dir O --tag stage0c > O/stage0c.s${s}of2.log 2>&1 & done'
  then, once both shards have exited: the same python with --summarise --out-dir O --tag stage0c.
  Each shard also writes a (partial) summary as it exits; the --summarise run is the read.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import glob
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
import time

import numpy as np

VERSION = "stage0c_rollout_curve/1"
MAIN_CHECKOUT = "/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl"
RUNGS = (16, 32, 64, 128)
VARIANTS = ("full", "k4", "3x4")
RULES = ("soft_br", "argmax")
PRIMARY = "full/soft_br"
NOMINAL_OVERRIDE = 0.10
CURVE_TARGETS = (0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20, 0.30)
TOP_ROWS = 3
VERDICT_MIN_POSITIONS = 490
BUCKET_NAMES = ("2-8", "9-15", "16-22", "23+")
HERE = pathlib.Path(__file__).resolve().parent


def repo_root() -> pathlib.Path:
    """The checkout whose `rl` and `scripts` this run imports: $PSRL_REPO, else
    this file's grandparent if it is a checkout (once the file lives in
    scripts/), else the main checkout."""
    for cand in (os.environ.get("PSRL_REPO"), str(pathlib.Path(__file__).resolve().parents[1]), MAIN_CHECKOUT):
        if cand and (pathlib.Path(cand) / "rl" / "search" / "native.py").exists():
            return pathlib.Path(cand)
    raise SystemExit("cannot find the repo checkout (set PSRL_REPO)")


# ---------------------------------------------------------------------------
# Pure pieces (numpy only; tests/test_r7_stage0c_rollout_curve.py).
# ---------------------------------------------------------------------------

def encode_i8(a: np.ndarray) -> str:
    return base64.b64encode(np.asarray(a, dtype=np.int8).tobytes()).decode("ascii")


def decode_i8(s: str, shape: tuple[int, int]) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), dtype=np.int8).reshape(shape).astype(np.float64)


def top_k(actions: list[int], prior: np.ndarray, k: int) -> list[int]:
    """`native.solve`'s column rule, applied to any legal list: the actions ordered
    by `prior` descending, STABLE (ties to the lower action index), the first k.
    For our rows the first is the greedy action (np.argmax's lowest-index tie)."""
    legal = np.asarray(actions, dtype=np.int64)
    order = legal[np.argsort(-np.asarray(prior, dtype=np.float64)[legal], kind="stable")]
    return order[: min(k, len(order))].tolist()


def world_qbar(outcomes: np.ndarray, cols_w: list[int], foe_prior: np.ndarray, keep: list[int]) -> np.ndarray:
    """Qbar_w per row over the columns in `keep` (a subset of `cols_w`), weighted by
    the foe prior renormalised over `keep`. `outcomes` is (n_rows, len(cols_w))."""
    pos = {int(c): j for j, c in enumerate(cols_w)}
    idx = [pos[int(c)] for c in keep]
    q = np.asarray(foe_prior, dtype=np.float64)[list(keep)]
    return np.asarray(outcomes, dtype=np.float64)[:, idx] @ (q / q.sum())


def root_candidate(prior_m: np.ndarray, qbar: np.ndarray, rule: str, tau: float, ig: int) -> tuple[int, float]:
    """Index (into the rows given) of the operator's candidate, and its margin over
    the greedy row `ig` in outcome units. soft_br is `native.solve`'s arithmetic in
    the same order; argmax is the pure best response (lowest index on ties)."""
    qbar = np.asarray(qbar, dtype=np.float64)
    if rule == "soft_br":
        logits = np.log(np.asarray(prior_m, dtype=np.float64)) + qbar / tau
        p = np.exp(logits - logits.max())
        p /= p.sum()
        j = int(np.argmax(p))
    elif rule == "argmax":
        j = int(np.argmax(qbar))
    else:
        raise ValueError(f"unknown root rule {rule!r}; the rules are {RULES}")
    return j, float(qbar[j] - qbar[ig])


def gate_for_target(moves: np.ndarray, margins: np.ndarray, target: float) -> dict:
    """The gate g that brings the override rate to `target`, reading ONLY the
    operator's own margins: override_i = moves_i and margin_i >= g. When fewer
    than target x n positions move at all, the target is unreachable: g = -inf
    (every move overrides) and the realised rate is the operator's maximum."""
    moves = np.asarray(moves, dtype=bool)
    margins = np.asarray(margins, dtype=np.float64)
    n = int(moves.size)
    k = int(round(target * n))
    mv = np.sort(margins[moves])[::-1]
    if k <= 0:
        g = math.inf
    elif mv.size <= k:
        g = -math.inf
    else:
        g = float(mv[k - 1])
    over = moves & (margins >= g)
    return {"gate": g, "target": float(target), "override": float(over.mean()) if n else float("nan"),
            "n_override": int(over.sum()), "reachable": bool(mv.size >= k), "overrides": over}


def mean_se(x) -> tuple[float, float]:
    x = np.asarray(list(x), dtype=np.float64)
    if x.size == 0:
        return float("nan"), float("nan")
    if x.size == 1:
        return float(x[0]), float("nan")
    return float(x.mean()), float(x.std(ddof=1) / math.sqrt(x.size))


def stat(x) -> dict:
    x = np.asarray(list(x), dtype=np.float64)          # a generator is read once
    m, se = mean_se(x)
    return {"mean": m, "se": se, "upper95": m + 1.96 * se if se == se else float("nan"),
            "z": m / se if se == se and se > 0 else float("nan"), "n": int(x.size)}


def knee_of(g: dict[int, np.ndarray]) -> dict:
    """The knee of a gain curve over any rung set: BEST = the rung with the largest
    mean gain; KNEE = the smallest rung whose gain is within 1 se of BEST's, the se
    of the PAIRED per-position difference. On a monotone curve BEST is the top rung
    (the docstring's "within 1 se of R = 128"); on a curve that peaks and falls the
    knee is never a rung past the peak."""
    rungs = sorted(g)
    best = max(rungs, key=lambda R: (float(np.mean(g[R])), -R))
    diffs = {R: stat(g[best] - g[R]) for R in rungs}
    knee = next(R for R in rungs if R == best or diffs[R]["mean"] <= diffs[R]["se"])
    return {"best": best, "knee": knee, "best_minus": {str(R): diffs[R] for R in rungs}}


def cells_at(g_full: dict[int, np.ndarray], g_3x4: dict[int, np.ndarray], knee: int) -> tuple[str, dict]:
    """The pre-stated cells rule at the knee R*: H uses the 3x4 cells iff their gain
    is within 1 se (paired) of the full matrix's, else the full matrix. One helper
    for the verdict and the follow-up curve, so the two can never disagree."""
    gap = stat(g_full[knee] - g_3x4[knee])
    return ("3x4" if gap["mean"] <= gap["se"] else "full"), gap


def verdict(d: dict[int, np.ndarray], g_full: dict[int, np.ndarray], g_3x4: dict[int, np.ndarray],
            n_positions: int) -> dict:
    """The pre-stated rule (module docstring), on per-position arrays in WIN-RATE
    units: d[R] = rollout primary - critic (paired), g_full[R] / g_3x4[R] the
    rollout operators' own gains at the matched rate. Precedence: STAGE 1, then
    KEEP LIGHT, then UNRESOLVED; ADD R = 512 attaches to any branch."""
    rungs = sorted(d)
    missing = sorted(set(RUNGS) - set(rungs))
    if n_positions < VERDICT_MIN_POSITIONS or missing:
        return {"branch": "NO VERDICT", "why": f"n {n_positions} (need >= {VERDICT_MIN_POSITIONS}), rungs missing {missing}"}
    top = max(RUNGS)
    d_top = stat(d[top])
    pays = {R: bool(stat(d[R])["mean"] >= 2 * stat(d[R])["se"]) for R in RUNGS}
    rise = stat(g_full[top] - g_full[64])
    still_rising = bool(rise["mean"] > rise["se"])
    out = {"d_at_128": d_top, "pays_at": [R for R in RUNGS if pays[R]], "rise_64_to_128": rise,
           "still_rising": still_rising}
    if any(pays.values()):
        k = knee_of({R: g_full[R] for R in RUNGS})
        cells, gap = cells_at(g_full, g_3x4, k["knee"])
        out.update({"branch": "STAGE 1", "knee": k["knee"], "best": k["best"], "cells": cells,
                    "full_minus_3x4_at_knee": gap})
    elif d_top["upper95"] < 0 and not still_rising:
        out["branch"] = "KEEP LIGHT"
    else:
        out["branch"] = "UNRESOLVED"
        out["mde_win_rate"] = 2.8 * d_top["se"]      # 80% power, two-sided 5%: (1.96 + 0.84) se
    if still_rising:
        out["add_R512"] = "run --worlds 512 --rungs 128 256 512 --per-bucket 25 before Stage 1 or any conclusion"
    return out


# ---------------------------------------------------------------------------
# The summary: joins the rows with G0's oracle and the banked critic rows.
# ---------------------------------------------------------------------------

def oracle_of(g0: dict) -> dict:
    """G0's true-world oracle for one position: Qbar per row under pi2 over every
    legal column, both halves (256 rollouts per cell) and each half alone."""
    qa = np.asarray(g0["q_half_a"], dtype=np.float64)
    qb = np.asarray(g0["q_half_b"], dtype=np.float64)
    pi2 = np.asarray(g0["pi2"], dtype=np.float64)
    cols = g0["cols"]
    q_col = pi2[cols] / pi2[cols].sum()
    rows = [int(a) for a in g0["rows"]]
    return {"rows": rows, "row_of": {a: i for i, a in enumerate(rows)}, "qbar": (0.5 * (qa + qb)) @ q_col,
            "qa": qa @ q_col, "qb": qb @ q_col, "ig": rows.index(int(g0["a_greedy"]))}


def gains_for(cands: list[int], oracles: list[dict], greedy: list[int]) -> np.ndarray:
    """Outcome-unit oracle gain of each candidate over greedy (ungated)."""
    return np.array([o["qbar"][o["row_of"][int(c)]] - o["qbar"][o["row_of"][int(g)]]
                     for c, o, g in zip(cands, oracles, greedy)], dtype=np.float64)


def read_operator(moves, margins, oracle_gain, target: float) -> dict:
    gate = gate_for_target(moves, margins, target)
    g = np.where(gate["overrides"], oracle_gain, 0.0) / 2.0          # WIN-RATE
    s = stat(g)
    return {"gate": gate["gate"], "override": gate["override"], "n_override": gate["n_override"],
            "reachable": gate["reachable"], "gain": s, "per_position": g}


def true_world_rollout(g0_rows: list[dict], rule: str, tau: float, target: float) -> dict:
    """G0's own TRUE-WORLD rollout operator: the candidate chosen on one half and
    scored on the other, both orderings (G0's split), gated to `target` over the
    2N (position, ordering) margins. Its gain minus the belief operator's is the
    rollout operator's peek."""
    moves, margins, gains = [], [], []
    for r in g0_rows:
        o = oracle_of(r)
        pi1 = np.asarray(r["pi1"], dtype=np.float64)
        prior_m = pi1[o["rows"]] / pi1[o["rows"]].sum()
        for sel, sco in ((o["qa"], o["qb"]), (o["qb"], o["qa"])):
            j, m = root_candidate(prior_m, sel, rule, tau, o["ig"])
            moves.append(j != o["ig"]); margins.append(m); gains.append(sco[j] - sco[o["ig"]])
    gate = gate_for_target(np.array(moves), np.array(margins), target)
    per = np.where(gate["overrides"], np.array(gains), 0.0).reshape(-1, 2).mean(axis=1) / 2.0
    return {"override": gate["override"], "gain": stat(per), "per_position": per}


def load_jsonl(path: pathlib.Path, version_key: str, version: str | None) -> list[dict]:
    out = []
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if version is not None and r.get(version_key) != version:
            raise SystemExit(f"REFUSED: {path} holds a row of version {r.get(version_key)!r}, this reads {version!r}; "
                             "move the file aside rather than mixing versions")
        out.append(r)
    return out


def summarise(rows: list[dict], g0_by_pid: dict[int, dict], belief_by_pid: dict[int, dict], tau: float,
              self_check: dict | None = None) -> dict:
    errs = [r for r in rows if "error" in r]
    ok = sorted((r for r in rows if "error" not in r), key=lambda r: r["pid"])
    n = len(ok)
    if n == 0:
        return {"positions": 0, "errors": len(errs), "verdict": {"branch": "NO VERDICT", "why": "no rows"}}
    pids = [r["pid"] for r in ok]
    g0 = [g0_by_pid[p] for p in pids]
    bel = [belief_by_pid[p] for p in pids]
    orc = [oracle_of(r) for r in g0]
    greedy = [int(r["a_greedy"]) for r in g0]
    for r, gr in zip(ok, greedy):
        if int(r["a_greedy"]) != gr:
            raise SystemExit(f"pid {r['pid']}: a_greedy {r['a_greedy']} != G0's {gr}")
    rungs = sorted({int(R) for r in ok for R in r["rungs"]})
    rungs = [R for R in rungs if all(str(R) in r["rungs"] for r in ok)]   # a rung every row measured

    # THE CRITIC, banked: the belief L-op at its native gate is the matched operating point.
    crit_native = np.array([int(b["a_belief"]) != int(b["a_greedy"]) for b in bel])
    target = float(crit_native.mean())
    crit_gain_native = np.where(crit_native, gains_for([b["a_belief"] for b in bel], orc, greedy), 0.0) / 2.0
    crit_moves = np.array([int(b["t_pimc"]) != int(b["a_greedy"]) for b in bel])
    crit_margins = np.array([float(b["margin_pimc"]) for b in bel])
    crit_oracle = gains_for([b["t_pimc"] for b in bel], orc, greedy)
    critic = {"matched_rate": target, "native": {"override": target, "gain": stat(crit_gain_native)},
              "max_override": float(crit_moves.mean()),
              "nominal": read_operator(crit_moves, crit_margins, crit_oracle, NOMINAL_OVERRIDE),
              "curve": {str(t): read_operator(crit_moves, crit_margins, crit_oracle, t) for t in CURVE_TARGETS}}

    # THE ROLLOUT OPERATORS, every rung x variant x rule, at the matched rate, the nominal and the curve.
    ops: dict[str, dict] = {}
    for R in rungs:
        for v in VARIANTS:
            for rule in RULES:
                key = f"{v}/{rule}"
                cands = [r["rungs"][str(R)][key]["cand"] for r in ok]
                margins = np.array([r["rungs"][str(R)][key]["margin"] for r in ok])
                moves = np.array([int(c) != g for c, g in zip(cands, greedy)])
                og = gains_for(cands, orc, greedy)
                ops[f"{R}/{key}"] = {
                    "R": R, "variant": v, "rule": rule,
                    "rollouts_per_decision": float(np.mean([r["rungs"][str(R)]["rollouts"][v] for r in ok])),
                    "worlds_mean": float(np.mean([r["rungs"][str(R)]["worlds"] for r in ok])),
                    "moves_at_gate0": float(moves.mean()),
                    "matched": read_operator(moves, margins, og, target),
                    "nominal": read_operator(moves, margins, og, NOMINAL_OVERRIDE),
                    "curve": {str(t): read_operator(moves, margins, og, t) for t in CURVE_TARGETS},
                }

    # The paired reads.
    def per(key: str, R: int, which: str = "matched") -> np.ndarray:
        return ops[f"{R}/{key}"][which]["per_position"]

    d = {R: per(PRIMARY, R) - crit_gain_native for R in rungs}
    paired = {str(R): {v_r: stat(per(v_r, R) - crit_gain_native) for v_r in (f"{v}/{rule}" for v in VARIANTS for rule in RULES)}
              for R in rungs}
    g_full = {R: per(PRIMARY, R) for R in rungs}
    g_3x4 = {R: per("3x4/soft_br", R) for R in rungs}
    ver = verdict(d, g_full, g_3x4, n)
    # The curve over whatever rungs this tag measured (the R = 512 follow-up reads its knee AND its cells here).
    curve = {"primary_gain": {str(R): stat(g_full[R]) for R in rungs},
             "step": {f"{a}->{b}": stat(g_full[b] - g_full[a]) for a, b in zip(rungs, rungs[1:])}}
    if rungs:
        curve["knee"] = knee_of(g_full)
        curve["cells_at_knee"], curve["full_minus_3x4_at_knee"] = cells_at(g_full, g_3x4, curve["knee"]["knee"])

    # The critic's breadth axis, recomputed on this program: B32 - B8 at each's native gate and at the matched rate.
    breadth, repro, breadth_pp = {}, {}, {}
    cr = {B: [r["critic"].get(B) for r in ok] for B in ("8", "32")}
    if all(x is not None for x in cr["8"]):
        same_t = [int(c["t_pimc"]) == int(b["t_pimc"]) for c, b in zip(cr["8"], bel)]
        same_a = [int(c["a_belief"]) == int(b["a_belief"]) for c, b in zip(cr["8"], bel)]
        dm = [abs(float(c["margin_pimc"]) - float(b["margin_pimc"])) for c, b in zip(cr["8"], bel)]
        repro = {"positions": n, "t_pimc_identical": int(sum(same_t)), "a_belief_identical": int(sum(same_a)),
                 "max_abs_margin_diff": float(max(dm)) if dm else float("nan")}
    for B in ("8", "32"):
        if all(x is not None for x in cr[B]):
            nat = np.array([int(c["a_belief"]) != g for c, g in zip(cr[B], greedy)])
            og = gains_for([c["t_pimc"] for c in cr[B]], orc, greedy)
            mv = np.array([int(c["t_pimc"]) != g for c, g in zip(cr[B], greedy)])
            mg = np.array([float(c["margin_pimc"]) for c in cr[B]])
            m = read_operator(mv, mg, og, target)
            breadth_pp[B] = m.pop("per_position")
            breadth[B] = {"native_override": float(nat.mean()), "max_override": float(mv.mean()), "matched": m,
                          "native_gain": stat(np.where(nat, gains_for([c["a_belief"] for c in cr[B]], orc, greedy), 0.0) / 2.0)}
    if "8" in breadth_pp and "32" in breadth_pp:
        breadth["b32_minus_b8_matched"] = stat(breadth_pp["32"] - breadth_pp["8"])

    # The rollout operator's peek: G0's true-world rollout operator vs the belief one, both at the matched rate.
    tw = true_world_rollout(g0, "soft_br", tau, target)
    peek = {"true_world": {"override": tw["override"], "gain": tw["gain"]}}
    if 128 in rungs:
        peek["true_minus_belief_128"] = stat(tw["per_position"] - per(PRIMARY, 128))

    # By turn bucket: the primary d at the top rung (descriptive).
    top = max(rungs) if rungs else None
    by_bucket = {}
    if top is not None:
        for b, name in enumerate(BUCKET_NAMES):
            sel = np.array([int(r["bucket"]) == b for r in ok])
            if sel.any():
                by_bucket[name] = {"n": int(sel.sum()), "d": stat(d[top][sel]),
                                   "rollout_gain": stat(g_full[top][sel]), "critic_gain": stat(crit_gain_native[sel])}

    counters = {
        "positions": n, "errors": len(errs), "error_types": _count(e.get("error") for e in errs),
        "worlds_tried": int(sum(r["worlds_tried"] for r in ok)), "worlds_built": int(sum(r["worlds_built"] for r in ok)),
        "worlds_refused": int(sum(len(r["worlds_refused"]) for r in ok)),
        "refusal_reasons": _count(w["why"][:60] for r in ok for w in r["worlds_refused"]),
        "resample_tries": int(sum(r["resample_tries"] for r in ok)),
        "rollouts_run": int(sum(r["rollouts_run"] for r in ok)), "lockstep_steps": int(sum(r["lockstep_steps"] for r in ok)),
        "rollouts_per_position": stat(r["rollouts_run"] for r in ok),
        "seconds_per_position": stat(r["seconds"] for r in ok),
        "rollouts_per_second": float(sum(r["rollouts_run"] for r in ok) / max(sum(r["seconds"] for r in ok), 1e-9)),
        "no_world_by_rung": {str(R): int(sum(bool(r["rungs"][str(R)].get("no_world")) for r in ok)) for R in rungs},
        "qos": sorted({r.get("qos", "?") for r in ok}), "launch_git_sha": sorted({r.get("launch_git_sha", "?") for r in ok}),
        "git_dirty": sorted({bool(r.get("git_dirty")) for r in ok}), "engine_sha": sorted({r.get("engine_sha", "?") for r in ok}),
    }
    strip = lambda x: {k: v for k, v in x.items() if k != "per_position"}   # noqa: E731
    return {
        "version": VERSION, "positions": n, "rungs": rungs, "matched_rate": target, "nominal_rate": NOMINAL_OVERRIDE,
        "verdict": ver, "critic": {**{k: v for k, v in critic.items() if k not in ("nominal", "curve")},
                                   "nominal": strip(critic["nominal"]),
                                   "curve": {t: strip(x) for t, x in critic["curve"].items()}},
        "operators": {k: {**{kk: vv for kk, vv in o.items() if kk not in ("matched", "nominal", "curve")},
                          "matched": strip(o["matched"]), "nominal": strip(o["nominal"]),
                          "curve": {t: strip(x) for t, x in o["curve"].items()}} for k, o in ops.items()},
        "paired_vs_critic_matched": paired, "curve": curve, "breadth": breadth,
        "b8_reproduction": repro, "peek": peek, "by_bucket": by_bucket, "counters": counters,
        "self_check": self_check,
    }


def _count(xs) -> dict:
    out: dict[str, int] = {}
    for x in xs:
        out[str(x)] = out.get(str(x), 0) + 1
    return out


def _json_safe(x):
    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_safe(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_json_safe(v) for v in x.tolist()]
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return f if math.isfinite(f) else str(f)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def render_md(s: dict) -> str:
    def g(x: dict) -> str:
        return f"{x['mean']:+.4f} ± {x['se']:.4f}" if x.get("se") == x.get("se") else f"{x['mean']:+.4f}"
    L = [f"# Stage 0c ({VERSION}) -- rollout vs critic L-op on {s['positions']} G0 positions, WIN-RATE units", ""]
    v = s["verdict"]
    L.append(f"**VERDICT (the pre-stated rule): {v['branch']}**" + (f" -- {v.get('why')}" if v.get("why") else ""))
    for k in ("knee", "cells", "add_R512", "mde_win_rate"):
        if k in v:
            L.append(f"- {k}: {v[k]}")
    if "d_at_128" in v:
        L.append(f"- d at R=128 (primary - critic, paired): {g(v['d_at_128'])} (upper95 {v['d_at_128']['upper95']:+.4f}); "
                 f"pays at {v['pays_at']}; rise 64->128 {g(v['rise_64_to_128'])}; still rising {v['still_rising']}")
    c = s["critic"]
    L += ["", f"Matched rate = the banked critic belief L-op's native override **{s['matched_rate']:.3f}** "
              f"(its max, ungated: {c['max_override']:.3f}; the nominal {s['nominal_rate']} is "
              f"{'reachable' if c['nominal']['reachable'] else 'NOT reachable'} for it). "
              f"Critic at its native gate: {g(c['native']['gain'])}.", "",
          "| rung | variant/rule | rollouts/decision | moves@gate0 | matched: override, gain | nominal 0.10: override, gain | paired d vs critic (matched) |",
          "|--:|---|--:|--:|---|---|---|"]
    for key, o in s["operators"].items():
        pr = s["paired_vs_critic_matched"][str(o["R"])][f"{o['variant']}/{o['rule']}"]
        L.append(f"| {o['R']} | {o['variant']}/{o['rule']} | {o['rollouts_per_decision']:.0f} | {o['moves_at_gate0']:.3f} | "
                 f"{o['matched']['override']:.3f}, {g(o['matched']['gain'])} | {o['nominal']['override']:.3f}, "
                 f"{g(o['nominal']['gain'])} | {g(pr)} (z {pr['z']:+.2f}) |")
    cv = s.get("curve", {})
    if cv.get("primary_gain"):
        L += ["", "Primary curve (full/soft_br, matched rate): " + "; ".join(
            f"R {R}: {g(x)}" for R, x in cv["primary_gain"].items())]
        if cv.get("step"):
            L.append("Steps (paired): " + "; ".join(f"{k}: {g(x)}" for k, x in cv["step"].items()))
        if cv.get("knee"):
            L.append(f"Knee over these rungs: best R {cv['knee']['best']}, knee R {cv['knee']['knee']}"
                     + (f"; cells {cv['cells_at_knee']} (full - 3x4 at the knee, paired: {g(cv['full_minus_3x4_at_knee'])})"
                        if cv.get("cells_at_knee") else ""))
    b = s.get("breadth", {})
    if b:
        L += ["", "Critic breadth (recomputed on this program): " + "; ".join(
            f"B{B}: native override {b[B]['native_override']:.3f} gain {g(b[B]['native_gain'])}, matched {g(b[B]['matched']['gain'])}"
            for B in ("8", "32") if B in b)]
        if "b32_minus_b8_matched" in b:
            L.append(f"B32 - B8 at the matched rate: {g(b['b32_minus_b8_matched'])}")
    if s.get("b8_reproduction"):
        rp = s["b8_reproduction"]
        L.append(f"B8 reproduction vs the banked rows: t_pimc identical {rp['t_pimc_identical']}/{rp['positions']}, "
                 f"a_belief identical {rp['a_belief_identical']}/{rp['positions']}, max |margin diff| {rp['max_abs_margin_diff']:.2e}")
    pk = s.get("peek", {})
    if pk:
        L.append(f"True-world rollout operator (G0 split, soft_br, matched): override {pk['true_world']['override']:.3f}, "
                 f"gain {g(pk['true_world']['gain'])}" + (f"; true - belief at R=128: {g(pk['true_minus_belief_128'])}"
                                                          if "true_minus_belief_128" in pk else ""))
    if s.get("by_bucket"):
        L += ["", "| bucket | n | d (primary - critic) | rollout gain | critic gain |", "|---|--:|---|---|---|"]
        for name, x in s["by_bucket"].items():
            L.append(f"| {name} | {x['n']} | {g(x['d'])} | {g(x['rollout_gain'])} | {g(x['critic_gain'])} |")
    k = s["counters"]
    L += ["", f"Counters: positions {k['positions']}, errors {k['errors']} {k['error_types']}; worlds tried {k['worlds_tried']}, "
              f"built {k['worlds_built']}, refused {k['worlds_refused']} {k['refusal_reasons']}; resample tries {k['resample_tries']}; "
              f"rollouts {k['rollouts_run']} ({g(k['rollouts_per_position'])} per position), lockstep steps {k['lockstep_steps']}; "
              f"{k['seconds_per_position']['mean']:.1f} s/position, {k['rollouts_per_second']:.0f} rollouts/s "
              f"(qos {k['qos']}: a disclosure, not a cost); no-world decisions by rung {k['no_world_by_rung']}; "
              f"git {k['launch_git_sha']} dirty {k['git_dirty']}; engine {k['engine_sha']}"]
    if s.get("self_check") is not None:
        L.append(f"Self-check (lockstep rollout vs rollout_q.rollout_matrix, one world): {s['self_check']}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# The engine side (imports inside, so the pure pieces test without pkmn_gen1).
# ---------------------------------------------------------------------------

def rollout_worlds(worlds: list, tables, committee, rows: list[int], cols_list: list[list[int]],
                   seed_bases: list[int], max_steps: int = 6000) -> tuple[list[np.ndarray], int]:
    """`scripts/rollout_q.py::rollout_matrix`'s loop in LOCKSTEP over several
    worlds, so the committee's forward passes batch across them: one leaf batch
    per world, one rollout per cell, both seats sampled by the committee (p1 then
    p2 each step, as rollout_matrix). With a single world it draws the committee's
    samples in exactly rollout_matrix's order (--self-check asserts it). Returns
    the outcomes (n_rows, n_cols_w) per world from P1's seat (+1 / -1 / 0) and the
    number of lockstep steps."""
    lbs = [w.leaves(tables, "p1", [(int(r), int(c), 1) for r in rows for c in cols], int(sb))
           for w, cols, sb in zip(worlds, cols_list, seed_bases)]
    steps = 0
    while True:
        live = [i for i, lb in enumerate(lbs) if lb.live() > 0]
        if not live:
            break
        steps += 1
        if steps > max_steps:
            raise RuntimeError("rollouts did not terminate")
        acts: dict[str, dict[int, tuple[list, list]]] = {}
        for seat in ("p1", "p2"):
            parts = []
            for i in live:
                idx, obs, mask = lbs[i].pending(tables, seat)
                if len(idx):
                    parts.append((i, idx, obs, mask))
            per: dict[int, tuple[list, list]] = {}
            if parts:
                a = committee.sample(np.concatenate([p[2] for p in parts]), np.concatenate([p[3] for p in parts]))
                o = 0
                for i, idx, _obs, _mask in parts:
                    per[i] = (idx.tolist(), a[o:o + len(idx)].tolist())
                    o += len(idx)
            acts[seat] = per
        for i in live:
            p1 = acts["p1"].get(i, ([], []))
            p2 = acts["p2"].get(i, ([], []))
            lbs[i].step(tables, p1[0], p1[1], p2[0], p2[1])
    outs = []
    for lb, cols in zip(lbs, cols_list):
        o = lb.outcome("p1").astype(np.float64)
        o[o == 2] = 0.0                                   # tie
        out = np.zeros((len(rows), len(cols)), dtype=np.float64)
        cell = lb.cell()
        for k in range(lb.n):
            ci = int(cell[k])
            out[ci // len(cols), ci % len(cols)] = o[k]
        outs.append(out)
    return outs, steps


class Cfg:
    pass


def measure_position(r: dict, node, tables, committee, native, resample_world, rqb, cfg: Cfg) -> dict:
    t0 = time.perf_counter()
    pid = int(r["pid"])
    mask1 = np.asarray(node.mask(tables, "p1"), bool)
    rows = [int(a) for a in r["rows"]]
    if rows != np.flatnonzero(mask1).tolist():
        raise RuntimeError("G0's rows disagree with the reloaded root's mask")
    pi1 = np.asarray(r["pi1"], dtype=np.float64)
    prior1 = np.where(mask1, pi1, 0.0)
    prior_m = prior1[mask1] / prior1[mask1].sum()
    greedy = int(r["a_greedy"])
    ig = rows.index(greedy)
    top = top_k(rows, prior1, cfg.top_rows)
    top_idx = [rows.index(a) for a in top]
    prior_top = prior_m[top_idx] / prior_m[top_idx].sum()
    if top[0] != greedy:
        raise RuntimeError("the top row is not the greedy action")

    # 1. WORLDS, from the belief read's own generator (its first 8 / 32 are the critic's).
    wrng = np.random.default_rng([cfg.belief_seed, pid])
    built, refused, tries = [], [], 0
    for b in range(cfg.worlds):
        try:
            world, info = resample_world(node, tables, "p1", wrng)
        except RuntimeError as e:
            refused.append({"b": b, "why": str(e)[:200]})
            tries += int(getattr(e, "info", {}).get("tries", 0))
            continue
        tries += int(info.get("tries", 1))
        if not np.array_equal(np.asarray(world.mask(tables, "p1"), bool), mask1):
            refused.append({"b": b, "why": "our mask moved in the resampled world"})
            continue
        m2w = np.asarray(world.mask(tables, "p2"), bool)
        if not m2w.any():
            refused.append({"b": b, "why": "the foe owes no decision in this world"})
            continue
        p2w = committee.probs(np.asarray(world.obs(tables, "p2"), np.float32)[None], m2w[None])[0]
        built.append((b, world, np.flatnonzero(m2w).tolist(), np.where(m2w, p2w, 0.0)))

    # 2. ROLLOUTS: one per cell per built world, lockstep; every draw keyed on (seed, pid).
    committee.rng = np.random.default_rng([cfg.seed, pid, 1])
    seed_bases = [native.seed_base(cfg.seed * 1_000_003 + pid, b + 1) for b, _w, _c, _p in built]
    outs, steps = rollout_worlds([w for _b, w, _c, _p in built], tables, committee, rows,
                                 [c for _b, _w, c, _p in built], seed_bases) if built else ([], 0)

    q_full, q_k4, cells, stored = [], [], {v: [] for v in VARIANTS}, []
    for (b, world, cols_w, p2w), o in zip(built, outs):
        kc = top_k(cols_w, p2w, cfg.cols_k)
        q_full.append(world_qbar(o, cols_w, p2w, cols_w))
        q_k4.append(world_qbar(o, cols_w, p2w, kc))
        cells["full"].append(len(rows) * len(cols_w))
        cells["k4"].append(len(rows) * len(kc))
        cells["3x4"].append(len(top) * len(kc))
        stored.append({"b": b, "cols": cols_w, "p2": [float(x) for x in p2w[cols_w]], "o": encode_i8(o),
                       "digest": hashlib.sha1(bytes(world.save())).hexdigest()[:12]})
    draws = [b for b, _w, _c, _p in built]

    rung_out = {}
    for R in cfg.rungs:
        sel = [j for j, b in enumerate(draws) if b < R]
        ent: dict = {"worlds": len(sel), "rollouts": {v: int(sum(cells[v][j] for j in sel)) for v in VARIANTS}}
        if sel:
            qf = np.mean([q_full[j] for j in sel], axis=0)
            qk = np.mean([q_k4[j] for j in sel], axis=0)
            for v, q, pm, gi, rws in (("full", qf, prior_m, ig, rows), ("k4", qk, prior_m, ig, rows),
                                      ("3x4", qk[top_idx], prior_top, 0, top)):
                for rule in RULES:
                    j, margin = root_candidate(pm, q, rule, cfg.tau, gi)
                    ent[f"{v}/{rule}"] = {"cand": int(rws[j]), "margin": margin}
                ent[f"{v}/qbar"] = [float(x) for x in q]
        else:
            # No world built at this rung: the operator plays greedy, COUNTED (the L-op's
            # own rule, rl/search/lop.py: "No world built -> greedy, counted").
            ent["no_world"] = True
            for v in VARIANTS:
                for rule in RULES:
                    ent[f"{v}/{rule}"] = {"cand": greedy, "margin": 0.0}
        rung_out[str(R)] = ent

    # 3. THE CRITIC L-op, the belief read's own measure(): B8 (provenance) and B32 (breadth).
    critic = {}
    for B in cfg.critic_worlds:
        s = rqb.measure(r, node, tables, committee, native, resample_world, cfg.dials, cfg.gate, B,
                        cfg.true_key(pid), cfg.belief_seed)
        critic[str(B)] = {k: s.get(k) for k in ("a_belief", "t_pimc", "margin_pimc", "t_avg", "worlds_ok",
                                                  "a_true", "t_true", "margin_true")}
        critic[str(B)]["worlds_refused"] = len(s.get("worlds_refused", []))

    return {"version": VERSION, "pid": pid, "bucket": int(r["bucket"]), "turn": int(r["turn"]), "a_greedy": greedy,
            "rows": rows, "top_rows": top, "worlds_tried": cfg.worlds, "worlds_built": len(built),
            "worlds_refused": refused, "resample_tries": tries, "rollouts_run": int(sum(o.size for o in outs)),
            "lockstep_steps": steps, "rungs": rung_out, "critic": critic, "worlds": stored,
            "seconds": time.perf_counter() - t0, **cfg.meta}


def select_positions(g0_rows: list[dict], args) -> list[dict]:
    rows = sorted(g0_rows, key=lambda r: int(r["pid"]))
    if args.pids:
        want = set(args.pids)
        rows = [r for r in rows if int(r["pid"]) in want]
    if args.per_bucket:
        keep = []
        for b in range(len(BUCKET_NAMES)):
            keep += [r for r in rows if int(r["bucket"]) == b][: args.per_bucket]
        rows = sorted(keep, key=lambda r: int(r["pid"]))
    i, n = (int(x) for x in args.shard.split("/"))
    rows = [r for r in rows if int(r["pid"]) % n == i]
    if args.limit:
        rows = rows[: args.limit]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--g0-rows", default="results/r7_g0/rollout_q.rows.jsonl", help="G0's rows (read only)")
    ap.add_argument("--g0-summary", default="results/r7_g0/rollout_q.json", help="the committee's paths and sha256s")
    ap.add_argument("--belief-rows", default="results/r7_g0/belief_k4s2t005.rows.jsonl", help="the banked critic L-op rows")
    ap.add_argument("--belief-summary", default="results/r7_g0/belief_k4s2t005.json", help="the critic L-op's dials and gate")
    ap.add_argument("--belief-seed", type=int, default=20260923,
                    help="the belief read's --seed (its default); the B8 reproduction line checks it")
    ap.add_argument("--seed", type=int, default=20260926, help="this pass's chance and policy-sample namespace")
    ap.add_argument("--worlds", type=int, default=max(RUNGS))
    ap.add_argument("--rungs", type=int, nargs="+", default=list(RUNGS))
    ap.add_argument("--critic-worlds", type=int, nargs="*", default=[8, 32])
    ap.add_argument("--top-rows", type=int, default=TOP_ROWS)
    ap.add_argument("--pids", type=int, nargs="*", default=None)
    ap.add_argument("--per-bucket", type=int, default=0, help="the lowest N pids of each turn bucket (the R=512 follow-up: 25)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", default="0/1", help="i/n: this process measures pids with pid %% n == i")
    ap.add_argument("--out-dir", default=None, help="default: <repo>/results/r7_stage0c (gitignored), never the checkout")
    ap.add_argument("--tag", default="stage0c")
    ap.add_argument("--torch-threads", type=int, default=2)
    ap.add_argument("--self-check", action="store_true", help="assert the lockstep rollout == rollout_matrix on the first position")
    ap.add_argument("--summarise", action="store_true", help="measure nothing: join every shard of --tag and write the summary")
    args = ap.parse_args()
    if max(args.rungs) > args.worlds:
        sys.exit(f"--rungs {args.rungs} exceed --worlds {args.worlds}")

    repo = repo_root()
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "scripts"))

    def path(p: str) -> pathlib.Path:
        return pathlib.Path(p) if os.path.isabs(p) else repo / p

    out_dir = pathlib.Path(args.out_dir) if args.out_dir else repo / "results" / "r7_stage0c"
    out_dir.mkdir(parents=True, exist_ok=True)
    i_sh, n_sh = (int(x) for x in args.shard.split("/"))
    rows_path = out_dir / f"{args.tag}.rows.s{i_sh}of{n_sh}.jsonl"
    selfcheck_path = out_dir / f"{args.tag}.selfcheck.s{i_sh}of{n_sh}.json"

    g0_rows = [json.loads(line) for line in path(args.g0_rows).read_text().splitlines() if line.strip()]
    bad = sorted({str(r.get("instrument_version")) for r in g0_rows} - {"rollout_q/1", "rollout_q/2"})
    if bad:
        sys.exit(f"REFUSED: {args.g0_rows} carries instrument versions {bad}")
    g0_by_pid = {int(r["pid"]): r for r in g0_rows}
    belief_summary = json.loads(path(args.belief_summary).read_text())
    # The banked rows must be the version their own summary names (never mixed).
    belief_rows = load_jsonl(path(args.belief_rows), "version", belief_summary["version"])
    belief_by_pid = {int(r["pid"]): r for r in belief_rows}
    tau = float(belief_summary["dials"].get("tau", 1.0))

    if not args.summarise:
        if os.environ.get("POKEMON_RL_ENCODER_C6"):
            sys.exit("REFUSED: POKEMON_RL_ENCODER_C6 is set; G0's rows and the W finals are c6-off")
        os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
        os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
        import torch
        torch.set_num_threads(args.torch_threads)
        import pkmn_gen1
        from rl.envs.engine_tables import build_tables
        from rl.search import native
        from rl.search.resample import resample_world
        import rollout_q as rq
        import rollout_q_belief as rqb

        # The program this pass is, stamped BEFORE any position (a running block imports the working tree).
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=repo).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True,
                                    text=True, cwd=repo).stdout.strip())
        try:
            qos = "background" if os.getpriority(4, 0) != 0 else "normal"
        except OSError:
            qos = "unknown"

        dials = native.dials_from(belief_summary["dials"])         # the signature's list; an unknown key fails
        if dials.get("root_rule", "soft_br") != "soft_br":
            sys.exit("REFUSED: the critic L-op here is the soft best response; root_rule must be soft_br")
        cell = (dials.get("cols_k", 3), dials.get("chance_s", 2), float(dials.get("tau", 1.0)))
        gi = rqb.SWEEP_GRID.index(cell) if cell in rqb.SWEEP_GRID else None

        cfg = Cfg()
        cfg.dials, cfg.gate, cfg.tau = dials, float(belief_summary["margin_gate"]), float(dials.get("tau", 1.0))
        cfg.cols_k, cfg.top_rows = int(dials.get("cols_k", 3)), int(args.top_rows)
        cfg.worlds, cfg.rungs, cfg.critic_worlds = int(args.worlds), sorted(set(args.rungs)), list(args.critic_worlds)
        cfg.seed, cfg.belief_seed = int(args.seed), int(args.belief_seed)
        cfg.true_key = lambda pid: pid * 100_003 + (gi + 1 if gi is not None else 999_331)   # the belief read's rule

        g0_summary = json.loads(path(args.g0_summary).read_text())
        paths_ = [c["path"] for c in g0_summary["committee"]]
        shas = [c["sha256"] for c in g0_summary["committee"]]
        committee, prov = rq.load_committee(paths_, shas, np.random.default_rng(args.seed))
        tables, fp = build_tables()
        fps = {g0_rows[0].get("tables_fingerprint"), belief_summary.get("tables_fingerprint")}
        if any(f and f != fp for f in fps):
            sys.exit(f"REFUSED: tables fingerprint {fp[:12]} != the banked rows' {sorted(str(f)[:12] for f in fps)}")
        engine = pkmn_gen1.build_info()
        cfg.meta = {"launch_git_sha": sha, "git_dirty": dirty, "qos": qos, "tables_fingerprint": fp[:12],
                    "engine_sha": str(engine.get("engine_sha", ""))[:12], "torch_threads": args.torch_threads,
                    "seed": args.seed, "belief_seed": args.belief_seed}

        done = {int(r["pid"]) for r in load_jsonl(rows_path, "version", VERSION)}
        todo = [r for r in select_positions(g0_rows, args) if int(r["pid"]) not in done]
        print(f"[stage0c] {VERSION} shard {args.shard}: {len(done)} positions on disk, {len(todo)} to measure; "
              f"W {cfg.worlds}, rungs {cfg.rungs}, critic B {cfg.critic_worlds}; dials {dials} gate {cfg.gate} "
              f"(read from {args.belief_summary}); committee {[p['sha256'][:12] for p in prov]}; tables {fp[:12]}; "
              f"engine {cfg.meta['engine_sha']}; git {sha}{' DIRTY' if dirty else ''}; qos {qos}; "
              f"torch threads {args.torch_threads}", flush=True)

        if args.self_check and todo:
            r0 = todo[0]
            node0 = pkmn_gen1.SearchNode.load(base64.b64decode(r0["node_b64"]))
            rows0 = [int(a) for a in r0["rows"]]
            cols0 = [int(c) for c in r0["cols"]]
            sb0 = native.seed_base(args.seed * 1_000_003 + int(r0["pid"]), 999)
            committee.rng = np.random.default_rng([args.seed, 999])
            ref, _ = rq.rollout_matrix(node0, tables, committee, rows0, cols0, 1, sb0)
            committee.rng = np.random.default_rng([args.seed, 999])
            mine, _ = rollout_worlds([node0], tables, committee, rows0, [cols0], [sb0])
            ok_ = bool(np.array_equal(ref[:, :, 0], mine[0]))
            sc = {"pid": int(r0["pid"]), "cells": len(rows0) * len(cols0), "identical": ok_}
            selfcheck_path.write_text(json.dumps(sc))
            print(f"[stage0c] SELF-CHECK lockstep rollout vs rollout_q.rollout_matrix on pid {r0['pid']} "
                  f"({sc['cells']} cells): {'IDENTICAL' if ok_ else 'DIFFERS -- stopping'}", flush=True)
            if not ok_:
                sys.exit(1)

        t_start, n_new, rollouts_new = time.time(), 0, 0
        for r in todo:
            pid = int(r["pid"])
            try:
                node = pkmn_gen1.SearchNode.load(base64.b64decode(r["node_b64"]))
                row = measure_position(r, node, tables, committee, native, resample_world, rqb, cfg)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:                                    # counted, written, never retried
                row = {"version": VERSION, "pid": pid, "bucket": int(r["bucket"]), "error": type(e).__name__,
                       "message": str(e)[:400], **cfg.meta}
            with rows_path.open("a") as f:
                f.write(json.dumps(_json_safe(row)) + "\n")
            n_new += 1
            if "error" in row:
                print(f"[stage0c] pid {pid} ERROR {row['error']}: {row['message'][:160]}", flush=True)
                continue
            rollouts_new += row["rollouts_run"]
            b8 = row["critic"].get("8")
            bk = belief_by_pid.get(pid)
            repro = (b8 is not None and bk is not None and int(b8["t_pimc"]) == int(bk["t_pimc"])
                     and int(b8["a_belief"]) == int(bk["a_belief"]))
            el = time.time() - t_start
            print(f"[stage0c] pid {pid} bucket {row['bucket']} rows {len(row['rows'])} worlds {row['worlds_built']}/"
                  f"{row['worlds_tried']} (refused {len(row['worlds_refused'])}, tries {row['resample_tries']}) "
                  f"rollouts {row['rollouts_run']} steps {row['lockstep_steps']} | {row['seconds']:.1f} s | "
                  f"B8 repro {'ok' if repro else 'DIFFERS'} | {n_new}/{len(todo)}, {el / n_new:.1f} s/pos, "
                  f"{rollouts_new / max(el, 1e-9):.0f} rollouts/s", flush=True)

    # THE SUMMARY: every shard of this tag.
    rows_all = []
    for p in sorted(glob.glob(str(out_dir / f"{args.tag}.rows.s*of*.jsonl"))):
        rows_all += load_jsonl(pathlib.Path(p), "version", VERSION)
    sc_all = [json.loads(pathlib.Path(p).read_text()) for p in sorted(glob.glob(str(out_dir / f"{args.tag}.selfcheck.*.json")))]
    summary = summarise(rows_all, g0_by_pid, belief_by_pid, tau, self_check=sc_all or None)
    summary["written"] = dt.datetime.now(dt.timezone.utc).isoformat()
    summary["inputs"] = {"g0_rows": str(path(args.g0_rows)), "belief_rows": str(path(args.belief_rows)),
                         "belief_summary": str(path(args.belief_summary)), "rows_files": sorted(glob.glob(str(out_dir / f"{args.tag}.rows.s*of*.jsonl")))}
    (out_dir / f"{args.tag}.summary.json").write_text(json.dumps(_json_safe(summary), indent=1))
    md = render_md(summary) if summary.get("positions") else "no rows\n"
    (out_dir / f"{args.tag}.summary.md").write_text(md)
    print(md)
    print(f"wrote {out_dir / (args.tag + '.summary.json')} and .md")


if __name__ == "__main__":
    main()
