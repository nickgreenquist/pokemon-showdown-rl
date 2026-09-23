#!/usr/bin/env python
"""R7 B1 -- the rollout-Q instrument (the I-op), G0's engine.

`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md` §6 as amended (boxes 2
and 3): positions sampled from the committee's own self-play ON THE ENGINE,
stratified by turn bucket; the FULL row x column matrix at each; 256 rollouts
per cell, SPLIT 128/128, with CRN-1 across rows (the chance seed is keyed on
the column and the sample, never the row -- `pkmn_gen1.SearchNode.expand`);
both seats stochastic under the committee. The rollouts ARE the value: no
critic enters the oracle.

Reads, per position, all on disk in the rows file before anything is averaged:

  regret_depth1_ceiling  Qbar_B[argmax_a Qbar_A[a]] - Qbar_B[a_greedy], the
                         argmax chosen on one half and EVALUATED on the other
                         (unbiased -- amendment 2 item 1a), averaged over the
                         two orderings; beside it the PERMUTED-SPLIT ZERO-GAP
                         NULL (the same statistic with the half assignment
                         permuted, item 1c). This is the depth-1
                         policy-improvement ceiling under a PERFECT evaluator
                         and bounds the FIRST ExIt iteration only.
  regret_critic_depth1   the same split-sample regret for the action the
                         T-op picks with the committee's CRITIC at the leaves
                         (rl/search/native.py, the observation critic).
  spearman_critic        rank correlation, over the position's cells, of the
                         critic-valued cell (mean over S chance samples) with
                         the rollout Q -- can the critic be a leaf?
  spearman_root_q        over rows: the operator's Qbar vs the rollout Qbar.
  opp_model_gap          max_a E_b Q(a,b) - max_a min_b Q(a,b): whether the
                         root's opponent model (best response to pi vs
                         minimax) matters. NOT a depth-2 read.
  opp_best_outside_topk  for k in {2,3,4}: is the oracle's best reply to our
                         greedy action outside pi_opp's top-k (amendment 2
                         item 5)?
  v_root_rollout / v_root_critic / v_root_search   the three root estimates
                         (rollout under pi x pi_opp; the critic's own output;
                         the operator's v') -- the ESTIMATOR question
                         (amendment 2 item 4) is read across positions.
  fusion_flip / fusion_bound   PENDING build B1b (the engine->engine
                         resample); recorded as null with the reason.
  spearman_privileged    PENDING: no privileged critic is trained for this
                         committee; recorded as null with the reason.

SCALE: rollout outcomes are -1/0/+1 (loss/tie/win). Every regret is reported
in OUTCOME units and, beside it, in WIN-RATE units (= outcome / 2), and every
threshold below is stated on the WIN-RATE scale. The G0 kill is pre-stated in
the plan: the UPPER 95% bound of the mean split-sample regret_depth1_ceiling
below 0.005 WIN-RATE, with the measured null below it. This script computes
and prints both; it does not decide.

VERSION MARKER: every row carries `instrument_version`; a rows file written
by another version is refused rather than resumed (the skip-guard landmine).
RESUME: rows already on disk are kept and their positions skipped; a death
costs one position. RATE: printed as seconds per position against the plan's
~2-4 core-hours for 500.

Runs niced beside a training fleet only with its CPU share disclosed (brief
§2); never beside a Foul Play arm. No server, no throughput claim.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

INSTRUMENT_VERSION = "rollout_q/1"
BUCKETS = ((2, 8), (9, 15), (16, 22), (23, 10_000))   # scripts/outcome_variance.py's edges
KILL_WIN_RATE = 0.005                                  # plan §6, WIN-RATE scale
N_ACTIONS = 10


# ---------------------------------------------------------------------------
# Pure statistics (tested in tests/test_rollout_q.py).
# ---------------------------------------------------------------------------

def cell_means(outcomes: np.ndarray, half: np.ndarray | None = None) -> np.ndarray:
    """`outcomes` (n_rows, n_cols, S) -> (n_rows, n_cols) means over the
    samples selected by `half` (a bool (S,) mask; None = all)."""
    o = outcomes if half is None else outcomes[:, :, half]
    return o.mean(axis=2)


def regret_split(outcomes: np.ndarray, q_col: np.ndarray, a_greedy: int, half: np.ndarray,
                 a_eval: int | None = None) -> float:
    """value(chosen row, other half) - value(greedy row, other half), averaged
    over the two orderings. Outcome units."""
    qa = cell_means(outcomes, half) @ q_col
    qb = cell_means(outcomes, ~half) @ q_col
    if a_eval is None:
        ra = qb[int(np.argmax(qa))] - qb[a_greedy]
        rb = qa[int(np.argmax(qb))] - qa[a_greedy]
    else:
        ra = qb[a_eval] - qb[a_greedy]
        rb = qa[a_eval] - qa[a_greedy]
    return 0.5 * (float(ra) + float(rb))


def permuted_null(outcomes: np.ndarray, q_col: np.ndarray, a_greedy: int, n_perm: int,
                  rng: np.random.Generator) -> float:
    """The ceiling statistic under a PERMUTED half assignment: the mean over
    `n_perm` random halvings of the samples. With a true zero gap this is what
    pure noise prints; the estimate is read against it."""
    s = outcomes.shape[2]
    vals = []
    for _ in range(n_perm):
        perm = rng.permutation(s)
        half = np.zeros(s, dtype=bool)
        half[perm[: s // 2]] = True
        vals.append(regret_split(outcomes, q_col, a_greedy, half))
    return float(np.mean(vals))


def opp_model_gap(q: np.ndarray, q_col: np.ndarray) -> float:
    """max_a E_b[Q(a,b)] - max_a min_b Q(a,b) on the full-matrix means."""
    return float((q @ q_col).max() - q.min(axis=1).max())


def best_reply_outside_topk(q: np.ndarray, a: int, opp_prior_cols: np.ndarray, k: int) -> bool:
    """Is the oracle's best reply to row `a` (the column minimising Q[a, :])
    outside pi_opp's top-k columns? Ties toward the lowest column index."""
    b_star = int(np.argmin(q[a]))
    order = np.argsort(-opp_prior_cols, kind="stable")
    return b_star not in set(order[:k].tolist())


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64).ravel(); y = np.asarray(y, dtype=np.float64).ravel()
    if x.size < 4 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return float("nan")
    rx = _rank(x); ry = _rank(y)
    return float(np.corrcoef(rx, ry)[0, 1])


def _rank(v: np.ndarray) -> np.ndarray:
    order = np.argsort(v, kind="stable")
    ranks = np.empty(v.size, dtype=np.float64)
    ranks[order] = np.arange(v.size, dtype=np.float64)
    # average ties
    _, inv, counts = np.unique(v, return_inverse=True, return_counts=True)
    sums = np.zeros(counts.size); np.add.at(sums, inv, ranks)
    return sums[inv] / counts[inv]


def mean_se(xs) -> tuple[float, float]:
    xs = np.asarray([x for x in xs if x == x], dtype=np.float64)
    if xs.size == 0:
        return float("nan"), float("nan")
    if xs.size == 1:
        return float(xs[0]), float("nan")
    return float(xs.mean()), float(xs.std(ddof=1) / math.sqrt(xs.size))


def win_rate(outcome_units: float) -> float:
    """A win-rate point is half an outcome point on the -1..+1 scale."""
    return outcome_units / 2.0


def bucket_of(turn: int) -> int:
    for i, (lo, hi) in enumerate(BUCKETS):
        if lo <= turn <= hi:
            return i
    return len(BUCKETS) - 1


# ---------------------------------------------------------------------------
# The committee as a batched stochastic policy on engine observations.
# ---------------------------------------------------------------------------

class Committee:
    """Equal-weight log-prob ensemble (rl/search/ensemble.py's rule) that can
    SAMPLE, batched, and expose the masked mean log-probs and the mean critic
    value. `members` are PPOAgents."""

    def __init__(self, members, rng: np.random.Generator):
        import torch
        self.torch = torch
        self.members = list(members)
        self.rng = rng

    def logp(self, obs: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """(n, 10) masked mean log-probs (-inf off the mask)."""
        from rl.common.masking import masked_logits
        torch = self.torch
        obs_t = torch.as_tensor(obs, dtype=torch.float32)
        mask_t = torch.as_tensor(mask, dtype=torch.bool)
        with torch.no_grad():
            lps = [torch.log_softmax(masked_logits(m.actor(obs_t), mask_t), dim=-1) for m in self.members]
            mean = torch.stack(lps).mean(dim=0)
        out = mean.numpy().astype(np.float64)
        out[~mask] = -np.inf
        return out

    def probs(self, obs: np.ndarray, mask: np.ndarray) -> np.ndarray:
        lp = self.logp(obs, mask)
        p = np.exp(lp - lp.max(axis=1, keepdims=True))
        p[~mask] = 0.0
        return p / p.sum(axis=1, keepdims=True)

    def sample(self, obs: np.ndarray, mask: np.ndarray) -> np.ndarray:
        p = self.probs(obs, mask)
        u = self.rng.random(p.shape[0])
        c = np.cumsum(p, axis=1)
        a = (u[:, None] > c).sum(axis=1)
        return np.minimum(a, N_ACTIONS - 1).astype(np.int64)

    def greedy(self, obs: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return self.logp(obs, mask).argmax(axis=1)

    def critic(self, obs: np.ndarray) -> np.ndarray:
        """The committee's observation critic: the mean of the members' V."""
        torch = self.torch
        x = torch.as_tensor(np.ascontiguousarray(obs), dtype=torch.float32)
        with torch.no_grad():
            vs = [m.critic(x).squeeze(-1) for m in self.members]
        return torch.stack(vs).mean(dim=0).numpy().astype(np.float64)


def load_committee(paths: list[str], shas: list[str] | None, rng) -> tuple[Committee, list[dict]]:
    from eval_checkpoint import _load_showdown_agent
    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config

    members, prov = [], []
    for i, p in enumerate(paths):
        digest = hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
        if shas and shas[i] and shas[i] != digest:
            sys.exit(f"checkpoint {p}: sha256 {digest[:12]} != expected {shas[i][:12]}")
        c = load_checkpoint(p)
        agent = _load_showdown_agent(c, Config(**c["config"]))
        agent.actor.eval(); agent.critic.eval()
        members.append(agent)
        prov.append({"path": p, "sha256": digest, "step": int(c.get("step", -1))})
    return Committee(members, rng), prov


# ---------------------------------------------------------------------------
# Positions and rollouts.
# ---------------------------------------------------------------------------

def rollout_matrix(root, tables, committee: Committee, rows, cols, n_samples: int, seed_base: int,
                   max_steps: int = 6000) -> tuple[np.ndarray, int]:
    """Play every (row, col, sample) leaf to termination under the committee
    on both seats. Returns outcomes (n_rows, n_cols, S) from P1's seat
    (+1/-1/0) and the number of policy steps taken."""
    cells = [(r, c, n_samples) for r in rows for c in cols]
    lb = root.leaves(tables, "p1", cells, seed_base)
    steps = 0
    while lb.live() > 0:
        steps += 1
        if steps > max_steps:
            raise RuntimeError("rollouts did not terminate")
        acts = {}
        for seat in ("p1", "p2"):
            idx, obs, mask = lb.pending(tables, seat)
            acts[seat] = (idx.tolist(), committee.sample(obs, mask).tolist() if len(idx) else [])
        lb.step(tables, acts["p1"][0], acts["p1"][1], acts["p2"][0], acts["p2"][1])
    o = lb.outcome("p1").astype(np.float64)
    o[o == 2] = 0.0                       # tie
    out = np.zeros((len(rows), len(cols), n_samples), dtype=np.float64)
    cell = lb.cell(); sample = lb.sample()
    for i in range(lb.n):
        ci = int(cell[i]); out[ci // len(cols), ci % len(cols), int(sample[i])] = o[i]
    return out, steps


def load_rows(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        v = r.get("instrument_version")
        if v != INSTRUMENT_VERSION:
            sys.exit(f"REFUSED: {path} carries rows of instrument version {v!r}, this is {INSTRUMENT_VERSION!r}; "
                     "move the file aside rather than mixing versions")
        rows.append(r)
    return rows


def measure_position(pid: int, node, tables, committee: Committee, args, rng: np.random.Generator,
                     meta: dict) -> dict:
    from rl.search import native

    t0 = time.time()
    mask1 = np.asarray(node.mask(tables, "p1"), bool); mask2 = np.asarray(node.mask(tables, "p2"), bool)
    rows = np.flatnonzero(mask1).tolist(); cols = np.flatnonzero(mask2).tolist()
    obs1 = node.obs(tables, "p1"); obs2 = node.obs(tables, "p2")
    pi1 = committee.probs(obs1[None], mask1[None])[0]; pi2 = committee.probs(obs2[None], mask2[None])[0]
    a_greedy = int(np.argmax(np.where(mask1, pi1, -1.0)))
    row_of = {a: i for i, a in enumerate(rows)}
    q_col = pi2[cols] / pi2[cols].sum()

    # THE ORACLE: 2 x half rollouts per cell, CRN across rows.
    S = args.rollouts
    seed_base = native.seed_base(args.seed * 1_000_003 + pid, 0)
    outcomes, steps = rollout_matrix(node, tables, committee, rows, cols, S, seed_base)
    half = np.zeros(S, dtype=bool); half[: S // 2] = True
    q_full = cell_means(outcomes)                       # (n_rows, n_cols), both halves
    qbar_full = q_full @ q_col
    g = row_of[a_greedy]
    ceiling = regret_split(outcomes, q_col, g, half)
    null = permuted_null(outcomes, q_col, g, args.null_perms, rng)

    # THE CRITIC SIDE: the operator on the same root with the committee's
    # observation critic, over ALL columns for the spearman and at the T-op's k
    # for the chosen action.
    def value_fn(e):
        return committee.critic(e["obs"])
    prior1 = np.where(mask1, pi1, 0.0); prior2 = np.where(mask2, pi2, 0.0)
    full = native.solve([native.World(node)], tables, "p1", prior1, prior2, value_fn, pid,
                        cols_k=N_ACTIONS, chance_s=args.critic_chance, tau=1.0)
    top = native.solve([native.World(node)], tables, "p1", prior1, prior2, value_fn, pid,
                       cols_k=args.critic_cols_k, chance_s=args.critic_chance, tau=1.0)
    # full.cols is top-k over ALL legal columns (k=10 covers them), in pi_opp order; realign to `cols`.
    col_pos = {c: j for j, c in enumerate(full["cols"])}
    q_cell_critic = np.stack([full["q_cell"][:, col_pos[c]] for c in cols], axis=1)  # (n_rows, n_cols)
    a_critic = int(top["action"])
    regret_critic = regret_split(outcomes, q_col, g, half, a_eval=row_of[a_critic])
    sp_critic = spearman(q_cell_critic, q_full)
    sp_root_q = spearman(full["q_row"][mask1], qbar_full)
    v_root_critic = float(committee.critic(obs1[None])[0])
    v_root_rollout = float(np.where(mask1, pi1, 0.0)[rows] @ qbar_full)
    gap = opp_model_gap(q_full, q_col)
    outside = {str(k): bool(best_reply_outside_topk(q_full, g, pi2[cols], k)) for k in args.topk_read}
    turn = int(node.turn())
    row = {
        "instrument_version": INSTRUMENT_VERSION, "pid": pid, "turn": turn, "bucket": bucket_of(turn),
        "battle_seed": int(node.seed()), "rows": rows, "cols": cols, "a_greedy": a_greedy, "a_critic": a_critic,
        "a_rollout_argmax": int(rows[int(np.argmax(qbar_full))]),
        "pi1": [float(x) for x in pi1], "pi2": [float(x) for x in pi2],
        "rollouts_per_cell": S, "steps": steps,
        "q_half_a": cell_means(outcomes, half).tolist(), "q_half_b": cell_means(outcomes, ~half).tolist(),
        "q_cell_critic": q_cell_critic.tolist(),
        "regret_depth1_ceiling": ceiling, "regret_depth1_ceiling_null": null,
        "regret_critic_depth1": regret_critic,
        "spearman_critic": sp_critic, "spearman_root_q": sp_root_q,
        "spearman_privileged": None, "spearman_privileged_why": "no privileged critic is trained for this committee",
        "opp_model_gap": gap, "opp_best_outside_topk": outside,
        "v_root_rollout": v_root_rollout, "v_root_critic": v_root_critic, "v_root_search": float(full["v"]),
        "v_root_search_prior": float(full["v_prior"]),
        "fusion_flip": None, "fusion_bound": None, "fusion_why": "PENDING B1b (engine->engine resample)",
        "search_counters_topk": top["counters"], "seconds": time.time() - t0,
        **meta,
    }
    return row


def summarise(rows: list[dict], args) -> dict:
    def block(sel: list[dict]) -> dict:
        out = {"positions": len(sel)}
        for key in ("regret_depth1_ceiling", "regret_depth1_ceiling_null", "regret_critic_depth1",
                    "opp_model_gap", "spearman_critic", "spearman_root_q"):
            m, se = mean_se([r[key] for r in sel])
            out[key] = {"mean_outcome": m, "se_outcome": se, "mean_win_rate": win_rate(m),
                        "se_win_rate": win_rate(se) if se == se else se,
                        "upper95_win_rate": win_rate(m + 1.96 * se) if se == se else float("nan")}
        for k in args.topk_read:
            vals = [r["opp_best_outside_topk"][str(k)] for r in sel]
            out[f"opp_best_outside_top{k}"] = float(np.mean(vals)) if vals else float("nan")
        out["mean_rollout_steps"] = float(np.mean([r["steps"] for r in sel])) if sel else float("nan")
        out["mean_seconds"] = float(np.mean([r["seconds"] for r in sel])) if sel else float("nan")
        # The estimator question, across positions: which root estimate ranks the
        # rollout root value better, the critic's own or the searched backup?
        if len(sel) >= 4:
            vr = [r["v_root_rollout"] for r in sel]
            out["spearman_root_estimator"] = {"critic": spearman([r["v_root_critic"] for r in sel], vr),
                                              "search_v": spearman([r["v_root_search"] for r in sel], vr)}
        return out
    summary = {"pooled": block(rows), "by_bucket": {}}
    for i, (lo, hi) in enumerate(BUCKETS):
        sel = [r for r in rows if r["bucket"] == i]
        summary["by_bucket"][f"{lo}-{'+' if hi > 999 else hi}"] = block(sel)
    p = summary["pooled"]["regret_depth1_ceiling"]
    null = summary["pooled"]["regret_depth1_ceiling_null"]["mean_win_rate"]
    summary["kill_read"] = {
        "rule": "the UPPER 95% bound of the mean split-sample regret_depth1_ceiling (WIN-RATE scale) "
                f"below {KILL_WIN_RATE}, with the measured zero-gap null below it -- plan §6",
        "upper95_win_rate": p["upper95_win_rate"], "null_mean_win_rate": null,
        "threshold_win_rate": KILL_WIN_RATE,
        "fires": bool(p["upper95_win_rate"] == p["upper95_win_rate"] and p["upper95_win_rate"] < KILL_WIN_RATE
                      and null < KILL_WIN_RATE),
        "scale": "WIN-RATE (outcome / 2)",
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoints", nargs="+", required=True, help="the committee's checkpoint paths")
    ap.add_argument("--sha256", nargs="*", default=None, help="expected sha256 per checkpoint (same order)")
    ap.add_argument("--positions", type=int, default=500)
    ap.add_argument("--rollouts", type=int, default=256, help="per cell, split in two halves")
    ap.add_argument("--null-perms", type=int, default=8)
    ap.add_argument("--critic-chance", type=int, default=2, help="the operator's S at the critic leaves")
    ap.add_argument("--critic-cols-k", type=int, default=3, help="the T-op's k for regret_critic_depth1")
    ap.add_argument("--topk-read", type=int, nargs="+", default=[2, 3, 4])
    ap.add_argument("--k", type=int, default=16, help="battles in flight in the position stream")
    ap.add_argument("--seed", type=int, default=20260922)
    ap.add_argument("--bank", default=None)
    ap.add_argument("--torch-threads", type=int, default=2)
    ap.add_argument("--out", default="results/r7_g0/rollout_q.json")
    ap.add_argument("--rows", default="results/r7_g0/rollout_q.rows.jsonl")
    args = ap.parse_args()
    if args.rollouts % 2 or args.rollouts < 4:
        sys.exit("--rollouts must be even and >= 4 (two halves)")
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    import torch
    torch.set_num_threads(args.torch_threads)
    import pkmn_gen1
    import engine_team_bank as bank
    from rl.envs.engine_tables import build_tables

    if args.bank is None:
        banks = sorted((ROOT / "data/engine").glob("teams_*.bin"), key=lambda p: p.stat().st_size)
        if not banks:
            sys.exit("no team bank under data/engine")
        args.bank = str(banks[-1] if len(banks) > 1 else banks[0])
    rng = np.random.default_rng(args.seed)
    committee, prov = load_committee(args.checkpoints, args.sha256, rng)
    tables, fp = build_tables()
    _h, payload = bank.read_bank(pathlib.Path(args.bank))
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    meta = {"git_sha": sha, "tables_fingerprint": fp, "c6": bool(os.environ.get("POKEMON_RL_ENCODER_C6")),
            "qos": "background" if _qos_background() else "normal"}

    rows_path = ROOT / args.rows
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    rows = load_rows(rows_path)
    done = {r["pid"] for r in rows}
    if rows:
        print(f"RESUME: {len(rows)} positions on disk", flush=True)
    per_bucket = [sum(1 for r in rows if r["bucket"] == i) for i in range(len(BUCKETS))]
    target_per_bucket = args.positions // len(BUCKETS)

    # The position stream: k battles, the committee on both seats, a target turn
    # per slot drawn from the bucket that still needs positions.
    env = pkmn_gen1.BatchEnv(args.k, args.seed, tables, payload, "p1")
    targets: dict[int, int | None] = {}

    def need_bucket() -> int | None:
        short = [i for i in range(len(BUCKETS)) if per_bucket[i] < target_per_bucket]
        return None if not short else int(rng.choice(short))

    def assign(slot: int) -> None:
        b = need_bucket()
        if b is None:
            targets[slot] = None
            return
        lo, hi = BUCKETS[b]
        targets[slot] = int(rng.integers(lo, min(hi, 40) + 1))

    for s in range(args.k):
        assign(s)
    pid = max(done) + 1 if done else 0
    t_start = time.time()
    measured = 0
    while sum(per_bucket) < target_per_bucket * len(BUCKETS):
        li, lobs, lmask, _ = env.pending("learner")
        oi, oobs, omask, _ = env.pending("opponent")
        la = committee.sample(lobs, lmask) if len(li) else np.zeros(0, np.int64)
        oa = committee.sample(oobs, omask) if len(oi) else np.zeros(0, np.int64)
        both = set(li.tolist()) & set(oi.tolist())
        for slot in sorted(both):
            tgt = targets.get(slot)
            node = env.snapshot(slot)
            if tgt is None or node.turn() < tgt:
                continue
            b = bucket_of(node.turn())
            if per_bucket[b] >= target_per_bucket:
                assign(slot); continue
            targets[slot] = None
            row = measure_position(pid, node, tables, committee, args, rng, meta)
            with rows_path.open("a") as f:
                f.write(json.dumps(row) + "\n")
            rows.append(row); per_bucket[b] += 1; pid += 1; measured += 1
            el = time.time() - t_start
            print(f"pos {pid} turn {row['turn']} bucket {b} rows {len(row['rows'])} cols {len(row['cols'])} "
                  f"ceiling {win_rate(row['regret_depth1_ceiling']):+.4f} null {win_rate(row['regret_depth1_ceiling_null']):+.4f} "
                  f"critic {win_rate(row['regret_critic_depth1']):+.4f} sp_c {row['spearman_critic']:+.3f} "
                  f"(win-rate) | {row['seconds']:.1f} s, {el / measured:.1f} s/pos, {sum(per_bucket)}/{args.positions}",
                  flush=True)
        env.step(li.tolist(), la.tolist(), [0.0] * len(li), 0, oi.tolist(), oa.tolist())
        for ep in env.drain_finished():
            assign(int(ep["slot"]))

    summary = summarise(rows, args)
    out = {"instrument_version": INSTRUMENT_VERSION, "written": dt.datetime.now(dt.timezone.utc).isoformat(),
           "committee": prov, "bank": args.bank, "args": vars(args), **meta, "summary": summary,
           "rows_file": os.path.relpath(rows_path, ROOT), "positions": len(rows)}
    (ROOT / args.out).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / args.out).write_text(json.dumps(out, indent=1))
    p = summary["pooled"]
    print("\n" + "=" * 78)
    print(f"ROLLOUT-Q ({INSTRUMENT_VERSION}) -- {len(rows)} positions, {args.rollouts} rollouts/cell split "
          f"{args.rollouts // 2}/{args.rollouts // 2}, committee of {len(prov)}; ALL NUMBERS BELOW IN WIN-RATE UNITS")
    for key in ("regret_depth1_ceiling", "regret_depth1_ceiling_null", "regret_critic_depth1", "opp_model_gap"):
        v = p[key]
        print(f"  {key:<30} {v['mean_win_rate']:+.4f} +- {v['se_win_rate']:.4f}  (upper95 {v['upper95_win_rate']:+.4f})")
    for key in ("spearman_critic", "spearman_root_q"):
        print(f"  {key:<30} {p[key]['mean_outcome']:+.3f} +- {p[key]['se_outcome']:.3f}  (rank correlation)")
    for k in args.topk_read:
        print(f"  opp_best_outside_top{k:<11} {p[f'opp_best_outside_top{k}']:.3f}")
    if "spearman_root_estimator" in p:
        e = p["spearman_root_estimator"]
        print(f"  root estimator vs rollout V     critic {e['critic']:+.3f}   search v' {e['search_v']:+.3f}")
    kr = summary["kill_read"]
    print(f"\n  KILL READ: upper95 {kr['upper95_win_rate']:+.4f} vs {KILL_WIN_RATE} win-rate, null {kr['null_mean_win_rate']:+.4f} "
          f"-> {'FIRES' if kr['fires'] else 'does not fire'} (the plan decides the branch, not this script)")
    print(f"  rate: {p['mean_seconds']:.1f} s/position; wrote {args.out}")
    print("=" * 78)


def _qos_background() -> bool:
    try:
        return os.getpriority(4, 0) != 0
    except OSError:
        return False


if __name__ == "__main__":
    main()
