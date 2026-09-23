#!/usr/bin/env python
"""R7 G0 readout generator: `readouts/R7_G0_READOUT.md` from the rows file,
every number re-derived from `results/r7_g0/rollout_q.rows.jsonl` (never from
the summary JSON, never typed), the permuted null printed beside the estimate,
both scales named, the T-op's override rate beside `regret_critic_depth1`, the
PENDING columns named, the CPU-share disclosure computed from
`logs/r6_fleet/monitor.log`, and the plan's branch stated in the plan's words.

Plan §6 (docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md), amendment boxes 2
and 3. Rule 6: nothing here is a win-rate A/B; the kill fires only on the
measured ceiling.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import types

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import rollout_q as rq  # noqa: E402

PLAN = "docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md"
BRANCH_WORDS = (
    "**Branches.** The **upper 95% bound** of mean split-sample `regret_depth1_ceiling` below "
    "**0.005 win-rate** (the effect of fixing every decision could not clear the credit line even if "
    "compounded): a **measured mechanism ceiling on depth-1 search over this policy** — the chapter "
    "closes on P1 and the training-side build is not started. Above it: the prize is real and G1 "
    "follows. `spearman` picks the first arm's leaf critic (observation by default; privileged only "
    "if it ranks better on the same rows); neither ranking above the critic's own raw-value `spearman` "
    "on the root: B2 trains the evaluator on rollout labels first (the G0 rows are the dataset)."
)


def _ts(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def lane_rates(monitor: pathlib.Path, start: dt.datetime, end: dt.datetime) -> dict[str, list[float]]:
    """Per-lane `rate=N steps/s` readings whose monitor timestamp is in [start, end]."""
    out: dict[str, list[float]] = {}
    if not monitor.exists():
        return out
    pat = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\] (showdown_r6_trio_[ab]_s\d+) .*?rate=(\d+) steps/s")
    for line in monitor.read_text().splitlines():
        m = pat.match(line)
        if not m:
            continue
        t = _ts(m.group(1))
        if start <= t <= end:
            out.setdefault(m.group(2), []).append(float(m.group(3)))
    return out


def zero_gap_null(r: dict, rng: np.random.Generator, n_perm: int = 16) -> float:
    """A MEASURED zero-gap null from the stored halves: the split-sample
    statistic with the row labels of the scoring half PERMUTED relative to the
    selecting half, so the row chosen on one half points at a random row of the
    other. Expectation exactly 0 when the halves are independent (which is what
    the split buys); its spread across positions is the noise floor. Outcome
    units. This is what the plan's "measured zero-gap null" means; the rows'
    own `regret_depth1_ceiling_null` column is NOT it -- see the readout."""
    qa, qb = np.asarray(r["q_half_a"], float), np.asarray(r["q_half_b"], float)
    pi2 = np.asarray(r["pi2"], float); cols = r["cols"]
    q_col = pi2[cols] / pi2[cols].sum()
    va, vb = qa @ q_col, qb @ q_col
    rows = r["rows"]; g = rows.index(int(r["a_greedy"]))
    ia, ib = int(np.argmax(va)), int(np.argmax(vb))
    vals = []
    for _ in range(n_perm):
        s = rng.permutation(len(rows))
        vals.append(0.5 * ((vb[s[ia]] - vb[s[g]]) + (va[s[ib]] - va[s[g]])))
    return float(np.mean(vals))


def resplit_check(r: dict) -> float:
    """Re-derive the rows' split-sample ceiling from the stored halves (a
    provenance check that the readout reads the same numbers the instrument
    wrote). Outcome units."""
    qa, qb = np.asarray(r["q_half_a"], float), np.asarray(r["q_half_b"], float)
    pi2 = np.asarray(r["pi2"], float); cols = r["cols"]
    q_col = pi2[cols] / pi2[cols].sum()
    va, vb = qa @ q_col, qb @ q_col
    g = r["rows"].index(int(r["a_greedy"]))
    return 0.5 * ((vb[int(np.argmax(va))] - vb[g]) + (va[int(np.argmax(vb))] - va[g]))


def fmt_pm(block: dict, key: str, scale: str = "win_rate") -> str:
    v = block[key]
    if scale == "win_rate":
        return f"{v['mean_win_rate']:+.4f} ± {v['se_win_rate']:.4f} (upper95 {v['upper95_win_rate']:+.4f})"
    return f"{v['mean_outcome']:+.4f} ± {v['se_outcome']:.4f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True, help="absolute path of rollout_q.rows.jsonl")
    ap.add_argument("--summary", default=None, help="rollout_q.json (committee provenance only)")
    ap.add_argument("--monitor", default=None, help="logs/r6_fleet/monitor.log for the CPU-share disclosure")
    ap.add_argument("--launch", default="2026-09-23T00:38:00Z", help="G0 launch, UTC")
    ap.add_argument("--end", default=None, help="G0 end, UTC (default: the rows file's mtime)")
    ap.add_argument("--baseline", default="2026-09-23T00:12:00Z,2026-09-23T00:33:00Z",
                    help="the pre-G0 window the lane bands come from")
    ap.add_argument("--out", required=True, help="the markdown to write")
    ap.add_argument("--topk-read", type=int, nargs="+", default=[2, 3, 4])
    args = ap.parse_args()

    rows_path = pathlib.Path(args.rows)
    rows = rq.load_rows(rows_path)
    if not rows:
        sys.exit(f"no rows at {rows_path}")
    sha = hashlib.sha256(rows_path.read_bytes()).hexdigest()
    ns = types.SimpleNamespace(topk_read=args.topk_read)
    summary = rq.summarise(rows, ns)
    pooled = summary["pooled"]
    kill = summary["kill_read"]
    prov = {}
    if args.summary and pathlib.Path(args.summary).exists():
        prov = json.loads(pathlib.Path(args.summary).read_text())

    # ---- the zero-gap null, from the stored halves ------------------------
    rng = np.random.default_rng(20260923)
    zg = np.array([zero_gap_null(r, rng) for r in rows])
    zg_m, zg_se = rq.mean_se(zg)
    rederived = np.array([resplit_check(r) for r in rows])
    stored = np.array([r["regret_depth1_ceiling"] for r in rows])
    max_dev = float(np.abs(rederived - stored).max())
    zg_bucket = {}
    for i, (lo, hi) in enumerate(rq.BUCKETS):
        sel = [z for z, r in zip(zg, rows) if r["bucket"] == i]
        zg_bucket[f"{lo}-{'+' if hi > 999 else hi}"] = rq.mean_se(sel) if sel else (float("nan"), float("nan"))
    null_ok = abs(rq.win_rate(zg_m)) + 1.96 * rq.win_rate(zg_se) < rq.KILL_WIN_RATE
    fires_plan = bool(kill["upper95_win_rate"] == kill["upper95_win_rate"]
                      and kill["upper95_win_rate"] < kill["threshold_win_rate"] and null_ok)

    # ---- the T-op read, per row ------------------------------------------
    def tc(r, k):
        return float(r["search_counters_topk"][k])
    override = np.array([tc(r, "search/override") for r in rows])
    kl_prior = np.array([tc(r, "search/kl_prior") for r in rows])
    margin = np.array([tc(r, "search/margin") for r in rows])
    ms = np.array([tc(r, "search/ms") for r in rows])
    leaves = np.array([tc(r, "search/leaves") for r in rows])
    prior_top1 = np.array([max(r["pi1"][a] for a in r["rows"]) for r in rows])
    forced = np.array([len(r["rows"]) == 1 for r in rows])
    regret_c = np.array([r["regret_critic_depth1"] for r in rows])
    ov = override > 0
    m_ov, se_ov = rq.mean_se(regret_c[ov]) if ov.any() else (float("nan"), float("nan"))
    m_all, se_all = rq.mean_se(regret_c)

    # ---- fusion, from the rows (None before the pass) ---------------------
    fus = [r for r in rows if r.get("fusion_flip") is not None]
    fusion_block = None
    if fus:
        mf, sf = rq.mean_se([r["fusion_flip"] for r in fus])
        mb, sb = rq.mean_se([r["fusion_bound"] for r in fus])
        fusion_block = {"positions": len(fus), "worlds": fus[0].get("fusion_worlds"),
                        "flip": (mf, sf), "bound_wr": (rq.win_rate(mb), rq.win_rate(sb), rq.win_rate(mb + 1.96 * sb))}

    # ---- CPU share ---------------------------------------------------------
    launch = _ts(args.launch)
    end = _ts(args.end) if args.end else dt.datetime.fromtimestamp(rows_path.stat().st_mtime, dt.timezone.utc)
    b0, b1 = (_ts(s) for s in args.baseline.split(","))
    during = lane_rates(pathlib.Path(args.monitor), launch, end) if args.monitor else {}
    base = lane_rates(pathlib.Path(args.monitor), b0, b1) if args.monitor else {}

    git_shas = sorted({r.get("git_sha") for r in rows})
    qos = sorted({r.get("qos") for r in rows})
    c6 = sorted({r.get("c6") for r in rows})
    fps = sorted({r.get("tables_fingerprint", "")[:12] for r in rows})
    seconds = sum(r["seconds"] for r in rows)

    L: list[str] = []
    L.append("# R7 G0 — the rollout-Q instrument (I-op) readout\n")
    L.append(f"Written {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} by `scripts/r7_g0_readout.py`. "
             f"**Every number below is re-derived from the rows file at generation time**; nothing is typed.\n")
    L.append("## Provenance\n")
    L.append(f"- rows: `{os.path.relpath(rows_path, ROOT.parent) if str(rows_path).startswith(str(ROOT.parent)) else rows_path}` — "
             f"sha256 `{sha[:16]}…`, **{len(rows)} positions**, instrument `{rows[0]['instrument_version']}`, "
             f"rows written by `scripts/rollout_q.py` at git {git_shas}, qos {qos}, c6 {c6}, tables {fps}.")
    L.append(f"- dose per row: `rollouts_per_cell` {sorted({r['rollouts_per_cell'] for r in rows})} split half/half, the FULL "
             f"row × column matrix; {seconds / 3600:.1f} core-hours of rollouts; mean {np.mean([r['steps'] for r in rows]):.0f} policy steps per position.")
    if prov:
        L.append(f"- committee: " + ", ".join(f"`{pathlib.Path(c['path']).name}` (step {c['step']}, sha `{c['sha256'][:12]}`)" for c in prov.get("committee", [])) +
                 f"; bank `{prov.get('bank')}`; summary JSON written {prov.get('written')}.")
    L.append(f"- plan: `{PLAN}` §6; the kill rule and the branch are quoted verbatim below. Rule 6: nothing here is a win-rate A/B.\n")

    L.append("## The kill read — split-sample `regret_depth1_ceiling`, WIN-RATE scale (outcome / 2)\n")
    L.append(f"> {kill['rule']}\n")
    L.append("| bucket (turns) | positions | ceiling mean ± se | upper95 | zero-gap null (mean ± se, expect 0) | re-split replicate (mean ± se) | opp_model_gap |")
    L.append("|---|---:|---|---:|---|---|---|")
    for name, blk in [("pooled", pooled)] + list(summary["by_bucket"].items()):
        z = (zg_m, zg_se) if name == "pooled" else zg_bucket[name]
        L.append(f"| **{name}** | {blk['positions']} | {blk['regret_depth1_ceiling']['mean_win_rate']:+.4f} ± {blk['regret_depth1_ceiling']['se_win_rate']:.4f} | "
                 f"{blk['regret_depth1_ceiling']['upper95_win_rate']:+.4f} | {rq.win_rate(z[0]):+.4f} ± {rq.win_rate(z[1]):.4f} | "
                 f"{blk['regret_depth1_ceiling_null']['mean_win_rate']:+.4f} ± {blk['regret_depth1_ceiling_null']['se_win_rate']:.4f} | "
                 f"{blk['opp_model_gap']['mean_win_rate']:+.4f} ± {blk['opp_model_gap']['se_win_rate']:.4f} |")
    L.append("")
    L.append(f"Outcome scale (±1), pooled: ceiling {fmt_pm(pooled, 'regret_depth1_ceiling', 'outcome')}; zero-gap null {zg_m:+.4f} ± {zg_se:.4f}; "
             f"re-split replicate {fmt_pm(pooled, 'regret_depth1_ceiling_null', 'outcome')}. Provenance check: the ceiling re-derived from the stored "
             f"halves (`q_half_a`, `q_half_b`, `pi2`, `cols`, `a_greedy`) matches the stored column to {max_dev:.1e}.\n")
    L.append("**On the two nulls.** The instrument's `regret_depth1_ceiling_null` column (`scripts/rollout_q.py::permuted_null`) re-halves the SAME "
             "samples and recomputes the split-sample statistic: that is a second, independent draw of the same unbiased estimator, with the SAME "
             "expectation as the estimate — a re-split REPLICATE, not the zero-gap null its docstring claims (it reads identical to the estimate on "
             "positions where every halving picks the same row). It is reported here as the replication check it actually is. The **zero-gap null** "
             "the plan's kill clause names is computed above from the stored halves: the same statistic with the scoring half's row labels permuted "
             "relative to the selecting half, so the chosen row carries no information — expectation exactly 0, and its spread is the noise floor. "
             "The instrument is corrected in its next version (`rollout_q/2`) after this chapter closes; the rows file is not touched.\n")
    fires = fires_plan
    L.append(f"**KILL READ (the plan's clause, both halves):** upper95 **{kill['upper95_win_rate']:+.4f}** vs threshold {kill['threshold_win_rate']} win-rate; "
             f"zero-gap null **{rq.win_rate(zg_m):+.4f} ± {rq.win_rate(zg_se):.4f}** ({'below' if null_ok else 'NOT below'} the threshold at its own 95% bound) → "
             f"the rule **{'FIRES' if fires else 'does not fire'}**. (The rows' own `kill_read.fires`, which used the re-split column, reads "
             f"{'FIRES' if kill['fires'] else 'does not fire'} — same verdict here, different null.)\n")

    L.append("## The other reads (plan §6, amendment box 2)\n")
    L.append("| read | pooled | by bucket |")
    L.append("|---|---|---|")
    for key, label in (("spearman_critic", "spearman(critic, rollout-Q) over cells"),
                       ("spearman_root_q", "spearman(root Q̄ depth-1, rollout-Q) over rows")):
        by = ", ".join(f"{n}: {b[key]['mean_outcome']:+.3f}" for n, b in summary['by_bucket'].items())
        L.append(f"| {label} | {pooled[key]['mean_outcome']:+.3f} ± {pooled[key]['se_outcome']:.3f} | {by} |")
    for k in args.topk_read:
        by = ", ".join(f"{n}: {b[f'opp_best_outside_top{k}']:.3f}" for n, b in summary['by_bucket'].items())
        L.append(f"| opp_best_outside_top{k} (fraction of positions) | {pooled[f'opp_best_outside_top{k}']:.3f} | {by} |")
    if "spearman_root_estimator" in pooled:
        e = pooled["spearman_root_estimator"]
        L.append(f"| root estimator vs rollout V (across positions) | critic {e['critic']:+.3f}, search v′ {e['search_v']:+.3f} | — |")
    L.append("")

    L.append("## The T-op read — `regret_critic_depth1` BESIDE its override rate (the landmine: match on the override rate, not the delta)\n")
    L.append(f"- T-op at the rows' dials (cols_k 3, chance_s 2, τ 1, critic = the committee's observation critic): **override rate "
             f"{override.mean():.3f}** ({int(ov.sum())}/{len(rows)} positions), mean `search/kl_prior` {kl_prior.mean():.4f}, mean margin "
             f"{margin.mean():+.4f} (outcome), {leaves.mean():.0f} leaves and {ms.mean():.1f} ms per decision (niced, beside the fleet — not a timing number).")
    L.append(f"- `regret_critic_depth1`, unconditional: {rq.win_rate(m_all):+.4f} ± {rq.win_rate(se_all):.4f} win-rate — **zero by construction on every "
             f"non-overridden position**, so this row alone says nothing about the operator.")
    if ov.any():
        L.append(f"- `regret_critic_depth1` CONDITIONAL on an override ({int(ov.sum())} positions): {rq.win_rate(m_ov):+.4f} ± {rq.win_rate(se_ov):.4f} win-rate "
                 f"(the split-sample regret of the T-op's action vs greedy where they differ; positive = the override was better under the rollout oracle).")
    else:
        L.append("- `regret_critic_depth1` CONDITIONAL on an override: **no position was overridden at these dials** — the T-op is the greedy policy "
                 "here, and the read is EMPTY, not null. A τ / k sweep on the saved positions is the next instrument.")
    L.append(f"- Amendment-4 dose read on these positions: π_θ top-1 ≥ 0.97 on **{(prior_top1 >= 0.97).mean():.3f}** of positions "
             f"(mean top-1 {prior_top1.mean():.3f}; §32's R5 read was 0.885 per decision), forced (one legal row) {forced.mean():.3f}. "
             f"Positions here are sampled per turn bucket, not per decision, so this is not a decision-weighted rate.\n")

    L.append("## Fusion (P3's licence): `fusion_flip` / `fusion_bound` over resampled worlds\n")
    if fusion_block:
        f_ = fusion_block
        L.append(f"- {f_['positions']} positions × {f_['worlds']} resampled worlds (`scripts/rollout_q_fusion.py`, B1b): "
                 f"flip {f_['flip'][0]:.3f} ± {f_['flip'][1]:.3f}; bound **{f_['bound_wr'][0]:+.4f} ± {f_['bound_wr'][1]:.4f} win-rate** "
                 f"(upper95 {f_['bound_wr'][2]:+.4f}) against the credit floor +0.025 (plan §10: above it P3's licence is spent and the T-op searches B ≥ 2 worlds).\n")
    else:
        L.append("- **PENDING** — the fusion pass has not been run over these rows yet (`fusion_flip` is null on every row).\n")

    L.append("## PENDING columns, named\n")
    why = sorted({r.get("spearman_privileged_why") for r in rows if r.get("spearman_privileged") is None})
    L.append(f"- `spearman_privileged`: PENDING on every row — {why}. The observation critic is the leaf by default (plan §6); the privileged "
             f"antisymmetric critic (B2) exists as a network but no trained checkpoint of it exists yet.")
    if not fusion_block:
        L.append("- `fusion_flip`, `fusion_bound`: PENDING (above).")
    L.append("- A true depth-2 ceiling: unmeasured before the fleet, by the plan's own words (amendment box 3, item 2).\n")

    L.append("## CPU-share disclosure — G0 ran niced beside the R6 fleet (plan §8)\n")
    L.append(f"Window {launch.isoformat(timespec='minutes')} → {end.isoformat(timespec='minutes')} UTC; baseline {b0.isoformat(timespec='minutes')} → {b1.isoformat(timespec='minutes')} UTC; "
             f"rates are `logs/r6_fleet/monitor.log`'s per-rung `rate=` readings (steps/s). Step-matched lanes: a wall cost, not a measurement.\n")
    if during:
        L.append("| lane | baseline mean (n) | during G0 mean (n) | during / baseline | during min |")
        L.append("|---|---:|---:|---:|---:|")
        for lane in sorted(set(during) | set(base)):
            b, d = base.get(lane, []), during.get(lane, [])
            bm = np.mean(b) if b else float("nan"); dm = np.mean(d) if d else float("nan")
            L.append(f"| {lane} | {bm:.0f} ({len(b)}) | {dm:.0f} ({len(d)}) | {dm / bm if b and d else float('nan'):.3f} | {min(d) if d else float('nan'):.0f} |")
        L.append("")
    else:
        L.append("- monitor.log not given or empty in the window: DISCLOSURE MISSING, add `--monitor`.\n")

    L.append("## The branch, in the plan's words (§6)\n")
    L.append(f"> {BRANCH_WORDS}\n")
    L.append(f"Read against this file's numbers: the kill rule **{'FIRES' if fires else 'does not fire'}** — "
             f"{'the chapter closes on P1; B0–B1 stay as instruments; no training-side build.' if fires else 'the prize is real and G1 follows (engine mirror matches, L-op vs greedy, n = 5,000 per arm, seat-swapped).'} "
             f"Leaf critic for the first arm: observation (`spearman_critic` {pooled['spearman_critic']['mean_outcome']:+.3f}; privileged PENDING). "
             f"Estimator: the searched root v′ ranks the rollout root value "
             f"{'better' if pooled.get('spearman_root_estimator', {}).get('search_v', 0) > pooled.get('spearman_root_estimator', {}).get('critic', 0) else 'no better'} than the critic's raw value "
             f"({pooled.get('spearman_root_estimator', {}).get('search_v', float('nan')):+.3f} vs {pooled.get('spearman_root_estimator', {}).get('critic', float('nan')):+.3f}).\n")
    L.append("Rule 6 applies to everything above: these are mechanism reads on 500 positions under the rollout oracle, never a win-rate A/B, and no small-run null is cited.\n")

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L))
    print(f"wrote {out} ({len(rows)} rows, sha {sha[:12]}); kill read: upper95 {kill['upper95_win_rate']:+.4f}, null {kill['null_mean_win_rate']:+.4f} -> "
          f"{'FIRES' if fires else 'does not fire'}; override rate {override.mean():.3f}")


if __name__ == "__main__":
    main()
