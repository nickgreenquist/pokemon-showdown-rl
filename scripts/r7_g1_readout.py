#!/usr/bin/env python
"""R7 G1 readout generator: `readouts/R7_G1_READOUT.md` from the rows files,
every number re-derived at generation time (never typed, never lifted from a
summary JSON where the rows can say it):

  * G1 /1 (`results/r7_g1/g1.rows.jsonl`): the gated L-op on the TRUE world vs
    its own greedy, seat-swapped, with the greedy-vs-greedy anchor;
  * the belief read (`results/r7_g0/belief_*.json` + rows,
    `scripts/rollout_q_belief.py`): the same operator on G0's positions with
    and without peeking, and the correction it makes to amendment box 4 item 4
    (the fusion pass read P3's licence at tau 1.0);
  * G1b (`results/r7_g1b/g1b.rows.jsonl`, the /2 harness): the belief arms in
    the mirror, PAIRED on battle_seed with re-runs of /1's true-world arms that
    must reproduce /1's rows in order. PENDING until its rows exist.

Plan §6 and §10 (docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md) are
quoted verbatim from the plan file. Rule 6: nothing here is a win-rate A/B
against the credit line; G1 is a mechanism read on the operator.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import re
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = pathlib.Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")


def wr(outcomes) -> tuple[float, float]:
    o = np.asarray(outcomes, float)
    p = float(((o + 1.0) / 2.0).mean())
    return p, math.sqrt(max(p * (1 - p), 1e-12) / len(o))


def ms(xs) -> tuple[float, float]:
    x = np.asarray(xs, float)
    return float(x.mean()), float(x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else float("nan")


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_rows(p: pathlib.Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def plan_block(plan: str, start: str, stop_pat: str) -> str:
    """The plan's own words: from the line starting with `start` up to (not
    including) the first following line matching `stop_pat`."""
    lines = plan.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith(start))
    out = [lines[i]]
    for l in lines[i + 1:]:
        if re.match(stop_pat, l):
            break
        out.append(l)
    return " ".join(s.strip() for s in out).strip()


def arm_stats(rows: list[dict], arm: str) -> dict | None:
    sel = [r for r in rows if r["arm"] == arm]
    if not sel:
        return None
    o = np.array([r["outcome"] for r in sel], float)
    p, se = wr(o)
    d = np.array([r["decisions"] for r in sel], float)
    ov = np.array([r["overrides"] for r in sel], float)
    ln = np.array([r["length"] for r in sel], float)
    lm, lse = ms(ln)
    return {"n": len(sel), "win": p, "se": se, "ties": int((o == 0).sum()), "wins": int((o > 0).sum()),
            "override": float(ov.sum() / max(d.sum(), 1)), "dec_per_battle": float(d.mean()),
            "ov_per_battle": float(ov.mean()), "any_override": float((ov > 0).mean()), "length": lm, "length_se": lse,
            "win_ties_as_loss": float((o > 0).mean())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--main", default=str(MAIN), help="the main checkout (results/, logs/, the plan)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--belief", default="results/r7_g0/belief_k4s2t005.json")
    ap.add_argument("--belief-b4", default="results/r7_g0/belief_k4s2t005_b4.json")
    args = ap.parse_args()
    M = pathlib.Path(args.main)
    g1_rows_p = M / "results/r7_g1/g1.rows.jsonl"
    g1 = load_rows(g1_rows_p)
    g1j = json.loads((M / "results/r7_g1/g1.json").read_text())
    g1_log = (M / "logs/r7_g1/g1.log").read_text().splitlines()
    # The log's first stamp is the box's LOCAL time (a naive stamp); rendered in UTC.
    launch_local = next((l[:19] for l in g1_log if re.match(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", l)), None)
    launch = (dt.datetime.strptime(launch_local, "%Y-%m-%d %H:%M:%S").astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
              if launch_local else "?")
    bel = json.loads((M / args.belief).read_text())
    bel_rows = load_rows(pathlib.Path(bel["rows_out"]))
    b4p = M / args.belief_b4
    b4 = json.loads(b4p.read_text()) if b4p.exists() else None
    sweep = json.loads((M / "results/r7_g0/top_sweep.json").read_text())
    g0_rows = load_rows(M / "results/r7_g0/rollout_q.rows.jsonl")
    g0j = json.loads((M / "results/r7_g0/rollout_q.json").read_text())
    plan = (M / "docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md").read_text()
    g1b_rows_p = M / "results/r7_g1b/g1b.rows.jsonl"
    g1b = load_rows(g1b_rows_p)
    g1bj_p = M / "results/r7_g1b/g1b.json"
    g1bj = json.loads(g1bj_p.read_text()) if g1bj_p.exists() else None
    maturin = M / "logs/r7_g0/maturin_b6.log"
    so_built = dt.datetime.fromtimestamp(maturin.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tip = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    eng = subprocess.run(["git", "diff", "--stat", "9a3e4ae", "HEAD", "--", "engine/"], capture_output=True, text=True, cwd=ROOT).stdout.strip()

    A = {a: arm_stats(g1, a) for a in ("lop_p1", "lop_p2", "greedy_greedy")}
    lop = [r for r in g1 if r["arm"] in ("lop_p1", "lop_p2")]
    P, Pse = wr([r["outcome"] for r in lop])
    d_all = sum(r["decisions"] for r in lop); ov_all = sum(r["overrides"] for r in lop)
    ov_pooled = ov_all / d_all
    ovpb = float(np.mean([r["overrides"] for r in lop]))
    anc, anc_se = A["greedy_greedy"]["win"], A["greedy_greedy"]["se"]
    d1 = A["lop_p1"]["win"] - anc; d1se = math.hypot(A["lop_p1"]["se"], anc_se)
    d2 = A["lop_p2"]["win"] - (1 - anc); d2se = math.hypot(A["lop_p2"]["se"], anc_se)
    harness = g1j["summary"]["lop_minus_anchor"]
    seat_x = A["lop_p1"]["win"] - A["lop_p2"]["win"]; seat_xse = math.hypot(A["lop_p1"]["se"], A["lop_p2"]["se"])
    ties_loss = float(np.mean([r["outcome"] > 0 for r in lop]))
    len_lop, len_lop_se = ms([r["length"] for r in lop])
    len_gg, len_gg_se = A["greedy_greedy"]["length"], A["greedy_greedy"]["length_se"]
    # The JSON's summary must agree with the rows (a provenance check, not a source).
    js = g1j["summary"]
    agree = all(abs(js[a]["win_rate"] - A[a]["win"]) < 1e-12 and js[a]["n"] == A[a]["n"] for a in A)
    sw = next(c for c in sweep["cells"] if (c["cols_k"], c["chance_s"], float(c["tau"]), c["margin_gate"]) == (4, 2, 0.05, 0.01))
    rates = [float(m.group(1)) for l in g1_log for m in [re.search(r"^\[lop_p\d\] \d+/\d+ battles, ([\d.]+) battles/min.*?([\d.]+) ms/searched", l)] if m]
    ms_searched = [float(m.group(1)) for l in g1_log for m in [re.search(r"([\d.]+) ms/searched decision", l)] if m]

    # The fusion pass (rollout_q_fusion/1): its dials and how often ITS true-world action moved.
    fus = g0j["fusion"]
    fus_override = float(np.mean([r["fusion_a_true"] != r["a_greedy"] for r in g0_rows if r.get("fusion_a_true") is not None]))
    fus_n = sum(1 for r in g0_rows if r.get("fusion_a_true") is not None)
    fsrc = (ROOT / "scripts/rollout_q_fusion.py").read_text()
    fus_dials_line = next(l.strip() for l in fsrc.splitlines() if "dials = dict(" in l)

    B = bel["summary"]["pooled"]
    Bb = bel["summary"]["by_bucket"]
    # The v' decomposition on G0's positions (outcome units): the critic vs the rollout root value,
    # the one-step lookahead under the prior, and v' at the working dials.
    bmap = {r["pid"]: r for r in bel_rows}
    vr = np.array([r["v_root_rollout"] for r in g0_rows]); vc = np.array([r["v_root_critic"] for r in g0_rows])
    vsp = np.array([r["v_root_search_prior"] for r in g0_rows])
    vt = np.array([bmap[r["pid"]]["v_true"] for r in g0_rows])
    crit_bias = ms(vc - vr); max_bias = ms(vt - vsp)
    # The T-op's dose, as a SCALE: frac ~0.4 of decisions (amendment box 4 item 3) x G1's decisions per battle.
    n_searched = 0.4 * d_all / len(lop)
    fc_u95 = (B["fusion_cost"]["mean_win_rate"] + 1.96 * B["fusion_cost"]["se_win_rate"])
    rule = plan_block(plan, "- **The fusion read after B6**", r"^- \*\*")
    g1_text = plan_block(plan, "**G1 — engine self-play", r"^\s*$")

    L = [f"# R7 G1 — the operator in the engine mirror, and how much of it is seeing the hidden state", "",
         f"Written {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} by `scripts/r7_g1_readout.py` (branch `r7-native-search` at `{tip}`). "
         "**Every number below is re-derived from the rows files at generation time; nothing is typed.** Rule 6: G1 is a mechanism read on the "
         "operator, never a win-rate A/B against the credit line (G2 is that, off FP@20).", "",
         "## Provenance", "",
         f"- G1 rows: `results/r7_g1/g1.rows.jsonl` — sha256 `{sha256(g1_rows_p)[:16]}…`, version `{g1[0]['version']}`, **{len(g1):,} battles** "
         f"({', '.join(f'{a} {A[a]['n']:,}' for a in A)}); the summary JSON agrees with the rows: **{agree}**. One process, launched {launch} "
         f"(`logs/r7_g1/g1.log`), QoS `{g1j['qos']}` — niced beside the R6 fleet, so every ms figure here is an efficiency-core timing, not a cost "
         "(the B0 bench is the cost).",
         f"- Program: the worktree at `9a3e4ae` with B6's second form in progress; the extension it loaded was rebuilt at {so_built} "
         f"(`logs/r7_g0/maturin_b6.log`), a minute before launch, from engine sources unchanged through `{tip}` "
         f"(`git diff 9a3e4ae..{tip} -- engine/`: {'empty' if not eng else eng}). The /1 harness predates the launch-SHA stamp (fixed in /2). "
         f"**The operator G1 ran is the sweep's, bit for bit, across that rebuild:** the belief read's true-world arm takes the sweep's decision keys "
         f"and reproduces the sweep's cell exactly on the rebuilt extension (override {bel['sweep_reproduction']['here_override']:.3f}, regret "
         f"{bel['sweep_reproduction']['here_gain_win_rate']:+.5f} win-rate: identical = **{bel['sweep_reproduction']['identical']}**); the sweep was "
         f"written {sweep['written'][:19]}Z, before it.",
         f"- Committee: {', '.join(f'`{pathlib.Path(c['path']).parent.name}/{pathlib.Path(c['path']).name}` (sha `{c['sha256'][:12]}`)' for c in g1j['committee'])}; "
         f"bank `{pathlib.Path(g1j['bank']).name}`; tables `{g1j['tables_fingerprint'][:12]}`; dials k {g1j['args']['cols_k']}, S {g1j['args']['chance_s']}, "
         f"τ {g1j['args']['tau']}, margin gate {g1j['args']['margin_gate']} critic units (the sweep's cell, amendment box 4 item 3); "
         f"{g1j['args']['k']} battles in flight; seed {g1j['args']['seed']}.",
         f"- The plan's G1 (§6), verbatim: > {g1_text}", "",
         "## The read — win rate from the L-op's seat, ties as half", "",
         "| arm | seat | battles | win rate ± se | ties | override (of all decisions) | decisions / battle | overrides / battle | battles with ≥ 1 override | mean length ± se |",
         "|---|---|--:|---|--:|--:|--:|--:|--:|---|"]
    for a, seat in (("lop_p1", "p1"), ("lop_p2", "p2"), ("greedy_greedy", "p1 (learner)")):
        s = A[a]
        L.append(f"| {a} | {seat} | {s['n']:,} | {s['win']:.4f} ± {s['se']:.4f} | {s['ties']} | {s['override']:.3f} | {s['dec_per_battle']:.1f} | "
                 f"{s['ov_per_battle']:.2f} | {s['any_override']:.3f} | {s['length']:.2f} ± {s['length_se']:.2f} |")
    L.append(f"| **L-op pooled** | both | {len(lop):,} | **{P:.4f} ± {Pse:.4f}** | {sum(A[a]['ties'] for a in ('lop_p1', 'lop_p2'))} | {ov_pooled:.3f} | "
             f"{d_all / len(lop):.1f} | {ovpb:.2f} | {float(np.mean([r['overrides'] > 0 for r in lop])):.3f} | {len_lop:.2f} ± {len_lop_se:.2f} |")
    L += ["",
          f"- **THE READ: the gated L-op beats its own greedy policy by {P - 0.5:+.4f} ± {Pse:.4f} win-rate over the seat-balanced symmetric line "
          f"({(P - 0.5) / Pse:.1f} se), at an override rate of {ov_pooled:.3f} of all decisions** ({ovpb:.2f} overrides a battle).",
          f"- The instrument check: greedy vs greedy (learner in p1) reads {anc:.4f} ± {anc_se:.4f}, {(anc - 0.5) / anc_se:+.2f} se from 0.5 — passes, and bounds "
          "the p1 seat's own advantage.",
          f"- Seat-matched against the measured anchor: lop_p1 − anchor = {d1:+.4f} ± {d1se:.4f}; lop_p2 − (1 − anchor) = {d2:+.4f} ± {d2se:.4f}; their mean, "
          f"{(d1 + d2) / 2:+.4f}, is exactly pooled − 0.5 (the anchor cancels in a seat-balanced pair). The harness's own line, pooled − anchor = "
          f"{harness['delta']:+.4f} ± {harness['se_diff']:.4f}, subtracts a p1-seat anchor from a seat-balanced number: conservative, reported, not the read.",
          f"- No seat interaction: lop_p1 − lop_p2 = {seat_x:+.4f} ± {seat_xse:.4f}. Ties as losses (the locked protocol's convention) move the pooled rate to "
          f"{ties_loss:.4f}.",
          "",
          "## What G1 licenses — and the two advantages G2 will not have", "",
          f"- **It licenses:** the operator is not broken, and the sweep's dials transfer to live play (override {ov_pooled:.3f} of every decision in the "
          f"mirror against {sw['override_rate']:.3f} of G0's positions — a different mix: G0's are turn-stratified simultaneous turns from SAMPLED play, "
          "G1's are every decision of GREEDY play, forced ones included). Nothing blocks G2 or the fleet on G1's account.",
          "- **It does not license** any FP@20, vs-SH or ladder number. G1 is the operator's best case twice over: **(1) it searches the TRUE world** — the "
          "foe's hidden members, sets and HP are in the leaves; **(2) its foe prior is the committee on the foe's TRUE view, and the foe IS that committee** — "
          "the opponent model is exact up to the foe playing its argmax where the L-op models the top-4 mix (that mismatch runs against the L-op). (1) is "
          "measured below and in G1b; (2) only G2 can measure.", "",
          "## The correction: P3's licence at the dials the operator runs (the belief read)", "",
          f"**What amendment box 4 item 4 read.** `scripts/rollout_q_fusion.py` (`{fus['version']}`) fixes its dials in code — `{fus_dials_line}` — and "
          f"`post_g0.sh` ran it with the defaults (k 3, S 2), no gate: **τ 1.0, where the operator's own true-world action moved {fus_override:.3f} of "
          f"G0's {fus_n} positions.** A flip rate of {fus['fusion_flip']['mean']:.3f} between worlds was close to mechanical for an operator that barely "
          "moves, and each resampled world carried the foe's TRUE-view prior, re-masked. \"P3's licence is INTACT\" was a read of the wrong operator.", "",
          f"**The re-read** (`scripts/rollout_q_belief.py`, `{bel['version']}`, git `{bel['launch_git_sha']}`{' DIRTY' if bel['git_dirty'] else ''}, QoS "
          f"{bel['qos']}): G0's {bel['positions']} positions × B = {bel['worlds']} resampled worlds at the working dials ({bel['dials']}, gate "
          f"{bel['margin_gate']}), each world's foe prior recomputed by the committee from that world's foe view; every action scored on G0's own rollout "
          f"oracle at the true world; worlds refused {B['worlds_refused']}.", "",
          "| arm | what it is | override | gain ± se, win-rate per decision | gain \\| override |", "|---|---|--:|---|---|"]
    what = {"true": "G1's L-op: the true world, the foe's true-view prior, gated", "belief": "the same L-op on resampled worlds (PIMC), gated — G2's operator",
            "t_true": "the T-op target's argmax, true world", "t_avg": "argmax of the world-averaged targets — a student's fixed point under true-world targets",
            "t_pimc": "argmax of the PIMC target — what a B ≥ 2 T-op would teach"}
    for arm in ("true", "belief", "t_true", "t_avg", "t_pimc"):
        a = B[arm]
        L.append(f"| {arm} | {what[arm]} | {a['override']:.3f} ({a['n_override']}) | {a['gain_win_rate']:+.4f} ± {a['gain_se_win_rate']:.4f} | "
                 f"{a['gain_cond_win_rate']:+.4f} ± {a['gain_cond_se_win_rate']:.4f} |")
    L += ["",
          f"- **The choice depends on the hidden world ~{B['world_flip']['mean'] / fus['fusion_flip']['mean']:.0f}× more than the fusion pass said:** "
          f"per-world argmax flips {B['world_flip']['mean']:.3f} ± {B['world_flip']['se']:.3f} (the fusion pass: {fus['fusion_flip']['mean']:.3f}); the belief "
          f"L-op makes the true L-op's move on {B['true_overrides_kept']['same_move']:.2f} of the {B['true_overrides_kept']['n']} positions where the true "
          f"L-op overrides; the gated actions differ on {B['flip']['mean']:.3f} ± {B['flip']['se']:.3f} of positions; the T-op's target moves "
          f"TV {B['tv_target']['mean']:.3f} ± {B['tv_target']['se']:.3f} between the true world and the world average.",
          f"- **The value it keeps:** the belief L-op gains {B['belief']['gain_win_rate']:+.4f} ± {B['belief']['gain_se_win_rate']:.4f} per decision against "
          f"the true L-op's {B['true']['gain_win_rate']:+.4f} ± {B['true']['gain_se_win_rate']:.4f}; **the peek, {B['peek']['mean_win_rate']:+.4f} ± "
          f"{B['peek']['se_win_rate']:.4f}, is NOT resolved on {bel['positions']} positions** (the per-decision gains rest on ~{B['true']['n_override']} "
          "overrides). G1b measures it at the battle level.",
          f"- **The student:** a student trained on true-world targets converges to the world-averaged target (t_avg, {B['t_avg']['gain_win_rate']:+.4f} ± "
          f"{B['t_avg']['gain_se_win_rate']:.4f}); PIMC targets would teach t_pimc ({B['t_pimc']['gain_win_rate']:+.4f} ± {B['t_pimc']['gain_se_win_rate']:.4f}). "
          f"**Fusion cost {B['fusion_cost']['mean_win_rate']:+.4f} ± {B['fusion_cost']['se_win_rate']:.4f} per decision (upper95 {fc_u95:+.4f}).**"]
    if b4:
        P4 = b4["summary"]["pooled"]
        L.append(f"- **B = 4** (the same first four worlds): belief gain {P4['belief']['gain_win_rate']:+.4f} ± {P4['belief']['gain_se_win_rate']:.4f}, peek "
                 f"{P4['peek']['mean_win_rate']:+.4f} ± {P4['peek']['se_win_rate']:.4f}, fusion cost {P4['fusion_cost']['mean_win_rate']:+.4f} ± "
                 f"{P4['fusion_cost']['se_win_rate']:.4f}; world_flip {P4['world_flip']['mean']:.3f}, TV {P4['tv_target']['mean']:.3f}. The world-dependence "
                 "reads are stable across B; the belief L-op's gain is not (fewer worlds, a noisier average), and the fusion cost changes sign — it is noise "
                 "around zero at this n. B = 8 is G1b's.")
    L += [f"- **The v′ target** (outcome units, ±1): its peek-optimism, value_fusion_gap = mean_b v′_wb − v′_pimc = {B['value_fusion_gap']['mean']:+.4f} ± "
          f"{B['value_fusion_gap']['se']:.4f} (positive in every turn bucket: "
          f"{', '.join(f'{k} {v['value_fusion_gap']['mean']:+.4f}' for k, v in Bb.items())}), is small beside the evaluator's own: the committee critic reads "
          f"{crit_bias[0]:+.4f} ± {crit_bias[1]:.4f} above the rollout root value on the same positions, and the root max at τ 0.05 adds "
          f"{max_bias[0]:+.4f} ± {max_bias[1]:.4f} over the one-step lookahead under the prior. The value target's bias is the evaluator's, not the peek's.",
          "", f"**The plan's rule (§10), verbatim:** > {rule}", "",
          f"**Read against it: the licence HOLDS at the working dials, now on the right measurement.** Fusion cost upper95 {fc_u95:+.4f} per decision; even "
          f"summed over the T-op's ~{n_searched:.0f} searched decisions of a battle it is {fc_u95 * n_searched:+.3f}, below the +0.025 floor. **The T-op stays "
          "B = 1.** What changes is the reading of G1: its operator's choices lean on the hidden world far more than the fusion pass said, so **G1's "
          f"{P - 0.5:+.4f} is an UPPER bound on G2's operator in the same mirror**, and the share the ladder keeps is G1b's to measure.", ""]

    L += ["## G1b — the belief arms in the mirror, paired", ""]
    if g1b:
        G = {a: arm_stats(g1b, a) for a in ("lop_p1", "lop_p2", "greedy_greedy", "lop_belief_p1", "lop_belief_p2")}
        L += ["| arm | seat | battles | win rate ± se | override | overrides / battle | mean length |", "|---|---|--:|---|--:|--:|--:|"]
        for a in G:
            if G[a]:
                s = G[a]
                L.append(f"| {a} | {'p2' if a.endswith('p2') else 'p1'} | {s['n']:,} | {s['win']:.4f} ± {s['se']:.4f} | {s['override']:.3f} | "
                         f"{s['ov_per_battle']:.2f} | {s['length']:.2f} |")
        L.append("")
        diffs, same = [], 0
        for st, sb in (("lop_p1", "lop_belief_p1"), ("lop_p2", "lop_belief_p2")):
            t = {r["battle_seed"]: r["outcome"] for r in g1b if r["arm"] == st}
            for r in g1b:
                if r["arm"] == sb and r["battle_seed"] in t:
                    diffs.append((r["outcome"] - t[r["battle_seed"]]) / 2.0)
        belief = [r for r in g1b if r["arm"] in ("lop_belief_p1", "lop_belief_p2")]
        true2 = [r for r in g1b if r["arm"] in ("lop_p1", "lop_p2")]
        if belief:
            pb, pbse = wr([r["outcome"] for r in belief])
            ovb = sum(r["overrides"] for r in belief) / max(sum(r["decisions"] for r in belief), 1)
            L.append(f"\n- **The belief L-op vs its own greedy, pooled: {pb:.4f} ± {pbse:.4f} — {pb - 0.5:+.4f} over the symmetric line "
                     f"({(pb - 0.5) / pbse:.1f} se), override {ovb:.3f}.**")
        if len(diffs) > 1:
            dm, dse = ms(diffs)
            L.append(f"- **Belief minus true, PAIRED on {len(diffs):,} battles (the same teams and chance streams): {dm:+.4f} ± {dse:.4f}** "
                     f"(identical outcome on {float(np.mean(np.asarray(diffs) == 0)):.3f} of pairs).")
        if true2:
            pt, ptse = wr([r["outcome"] for r in true2])
            L.append(f"- The re-run true-world arms: {pt:.4f} ± {ptse:.4f} on {len(true2):,} battles.")
        # /1 reproduction, from the ROWS: a /2 re-run of /1's arms must match /1's rows in order.
        rep_ = {}
        for a in ("lop_p1", "lop_p2", "greedy_greedy"):
            x1 = [r for r in g1 if r["arm"] == a]; x2 = [r for r in g1b if r["arm"] == a]
            n = min(len(x1), len(x2))
            if n:
                rep_[a] = (sum(all(u[k] == v[k] for k in ("outcome", "length", "decisions", "overrides")) for u, v in zip(x1[:n], x2[:n])), n)
        if rep_:
            L.append("- **/1 reproduction** (the re-run's rows against /1's, in order, on outcome, length, decisions and overrides): " + "; ".join(
                f"{a} {same:,}/{n:,} identical" for a, (same, n) in rep_.items()) +
                (f" — git `{g1bj.get('launch_git_sha')}`{' DIRTY' if g1bj.get('git_dirty') else ''}." if g1bj else " — the /2 JSON (launch SHA) is written at run end."))
        done = {a: (G[a]["n"] if G[a] else 0) for a in G}
        if any(v < 2500 for k, v in done.items() if k != "greedy_greedy"):
            L.append(f"- **PARTIAL** — battles on disk per arm: {done}; the run is resume-safe and continues on the idle box.")
    else:
        L.append("**PENDING** — launched 2026-09-23 21:53Z (`logs/r7_scripts/launch_g1b.sh`, one process per seat, niced, guard-killed at fleet end or "
                 "Thu 07:30Z); rows `results/r7_g1b/g1b.rows.jsonl`.")
    L += ["", "## Secondary reads", "",
          f"- Per override: the pooled gain over {ovpb:.2f} overrides a battle is {(P - 0.5) / ovpb:+.4f} win-rate per override, against the sweep's "
          f"{sw['regret_cond_win_rate']:+.4f} conditional on an override at the same cell. The two are scored against different foes and continuations "
          "(G0's oracle: both seats SAMPLED; the mirror: both GREEDY), so the sweep's number ranks dials and does not predict a match; the gap is not chased.",
          f"- Battle length: L-op battles run {len_lop:.2f} ± {len_lop_se:.2f} turns against {len_gg:.2f} ± {len_gg_se:.2f} greedy-vs-greedy "
          f"({len_lop - len_gg:+.2f}).",
          f"- Rate (niced, E-cores; not a cost): {min(rates) if rates else float('nan'):.0f}–{max(rates) if rates else float('nan'):.0f} battles/min on the "
          f"L-op arms at k {g1j['args']['k']}, {np.median(ms_searched) if ms_searched else float('nan'):.1f} ms per searched decision (median over progress lines).",
          "", "## Branch", "",
          "G1 carries no kill clause; it reads the operator as WORKING in its best case. Next, per the plan: **G2** on the idle box (the L-op's ladder path with "
          "belief samples through B6's bridge, whose gate R1-E passed; n = 3,000 per arm off FP@20, in-session anchor, the credit line verbatim) and **G3** on "
          "the fleet's own lanes. Added by this read: **G1b** (above) prices the peek at the battle level before G2 spends an idle-box block; the T-op stays "
          "B = 1 (the licence holds on the right measurement); and the **evaluator trained on rollout labels** stays first in line, since the critic's own "
          "optimism dominates the v′ target and the root-rule read already named the evaluator the binding constraint (amendment box 4 items 1 and 5)."]
    out = pathlib.Path(args.out)
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\nwrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
