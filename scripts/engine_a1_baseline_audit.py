#!/usr/bin/env python
"""Which historical runs qualify as A-1's BASELINE ARM? Answered from files.

A-1 compares the pkmn/engine collector against the Node path at 12M. Its
baseline may be REUSED from history only if the candidate is the same
experiment in everything except the collector — otherwise the comparison
measures the difference in recipes, not the difference in collectors.

This checks every candidate against configs/engine_a1.yaml field by field and
prints QUALIFIES / DISQUALIFIED with the reason, so the answer to "how many
qualify" is a lookup rather than a memory.

    python scripts/engine_a1_baseline_audit.py

Candidates checked: the async acceptance fleet (G9's treatment arm, which
JOURNEY 7.5 names), the sync fleet at the same rung, and the four
showdown_sp_recipe12m checkpoints the maintainer flagged 2026-09-09.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

MAIN = pathlib.Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")
BACKUP = pathlib.Path(
    "/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-d25-backup-20260815"
    "/_runs_sacred")

# The fields that must match for a collector comparison to mean anything. The
# collector itself is deliberately NOT here — it is the treatment.
MUST_MATCH = [
    ("agent.rollout_steps", "the update budget"),
    ("agent.minibatches", "the update budget"),
    ("num_envs", "the update budget"),
    ("agent.lr", "the optimiser"),
    ("agent.lr_anneal_steps", "the LR schedule AT THE READ"),
    ("agent.epochs", "the optimiser"),
    ("agent.gae_lambda", "credit assignment"),
    ("agent.gamma", "credit assignment"),
    ("agent.hidden_sizes", "the network"),
    ("agent.trunk", "the network"),
    ("agent.aux_oppact_coef", "the D25 auxiliary"),
    ("agent.aux_label_space", "the D25 auxiliary"),
    ("env_kwargs.opp_action", "the D25 auxiliary"),
    ("selfplay.opponent", "the opponent"),
    ("selfplay.pool_size", "the opponent"),
    ("selfplay.push_every_updates", "the opponent"),
    ("selfplay.latest_prob", "the opponent"),
]
ENCODER = {"obs_dim": 828, "encoder": "v2", "set_prior": True,
           "recharge_fix": True, "ids": True}


def dig(d: dict, path: str):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return "<absent>"
        cur = cur[part]
    return cur


def audit(ref: dict, cand_dir: pathlib.Path, eval_json: pathlib.Path | None) -> dict:
    cfg_p = cand_dir / "config.yaml"
    if not cfg_p.exists():
        return {"run": cand_dir.name, "qualifies": False,
                "reasons": [f"no config.yaml at {cand_dir}"]}
    cfg = yaml.safe_load(cfg_p.read_text()) or {}
    meta = {}
    mp = cand_dir / "meta.yaml"
    if mp.exists():
        meta = yaml.safe_load(mp.read_text()) or {}

    reasons, notes = [], []
    enc = meta.get("encoder")
    if enc is None:
        notes.append("no meta.yaml encoder stamp — identity would need the state dict")
    elif {k: enc.get(k) for k in ENCODER} != ENCODER:
        reasons.append(f"encoder stamp {enc} != {ENCODER}")

    for path, why in MUST_MATCH:
        want, got = dig(ref, path), dig(cfg, path)
        if want != got:
            reasons.append(f"{path}: {got!r} != A-1's {want!r}  ({why})")

    mode = dig(cfg, "collector.mode")
    notes.append(f"collector: {mode if mode != '<absent>' else 'sync (no collector block)'}")
    if meta.get("git_dirty") is True:
        notes.append("git_dirty: true — the code that ran cannot be reconstructed exactly")
    elif meta.get("git_dirty") is False:
        notes.append("git_dirty: false")

    ev = None
    if eval_json and eval_json.exists():
        d = json.loads(eval_json.read_text())
        ev = {"n": d.get("episodes"), "step": d.get("step"),
              "win_rate": d.get("eval/win_rate"), "file": str(eval_json)}
        if d.get("episodes", 0) < 3000:
            reasons.append(f"banked eval is n={d.get('episodes')}, below the locked 3000")
    else:
        notes.append("no banked locked-protocol eval found")

    return {"run": cand_dir.name, "qualifies": not reasons,
            "reasons": reasons, "notes": notes, "banked_eval": ev}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=pathlib.Path,
                    default=pathlib.Path("configs/engine_a1.yaml"))
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/baseline_audit.json"))
    args = ap.parse_args(argv)
    ref = yaml.safe_load(args.config.read_text())

    cands = []
    for s in (66, 75, 83):
        cands.append((MAIN / "runs" / f"showdown_sp_batch50m_async_s{s}",
                      MAIN / "runs" / f"showdown_sp_batch50m_async_s{s}" / "g9_treat" / "rung_12M_n3000.json"))
    for s in (66, 75, 83):
        cands.append((MAIN / "runs" / f"showdown_sp_batch50m_s{s}",
                      MAIN / "runs" / f"showdown_sp_batch50m_s{s}" / "g9_basis" / "rung_12M_n3000.json"))
    for s in (62, 63, 64, 65):
        live = MAIN / "runs" / f"showdown_sp_recipe12m_s{s}"
        cands.append((live if live.exists() else BACKUP / f"showdown_sp_recipe12m_s{s}",
                      MAIN / "results" / "d26" / f"final_s{s}.json"))

    rows = [audit(ref, d, e) for d, e in cands]
    ok = [r for r in rows if r["qualifies"]]
    out = {"reference": str(args.config), "n_candidates": len(rows),
           "n_qualifying": len(ok),
           "qualifying": [r["run"] for r in ok], "rows": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")

    for r in rows:
        print(f"{'QUALIFIES  ' if r['qualifies'] else 'DISQUALIFIED'} {r['run']}")
        for x in r["reasons"]:
            print(f"     x {x}")
        for n in r["notes"]:
            print(f"     . {n}")
        if r["banked_eval"]:
            b = r["banked_eval"]
            print(f"     . banked eval n={b['n']} step={b['step']} win={b['win_rate']}")
    print(f"\n{len(ok)} of {len(rows)} qualify: {[r['run'] for r in ok]}")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
