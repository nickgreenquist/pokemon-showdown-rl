#!/usr/bin/env python
"""R7 400k WARM-START SHAKEDOWN CHECK -- R0 gate (1) of the fleet pre-reg (scripts/derive_r7_fleet.py's header),
computed from the smoke's run dir so the PASS is read, not eyeballed.

    python scripts/r7_smoke_check.py runs/r7_fleet_smoke400k_searched_s424 --arm searched --expect-resume [--json-out ...]
    python scripts/r7_smoke_check.py runs/r7_fleet_smoke400k_control_s432 --arm control [--json-out ...]

Every expectation is DERIVED, never typed (docs/landmines.md, the typed-dial-list shape): the counter table is
derive_r7_fleet.py's GATE_COUNTERS (the header prints the same table; a test greps rl/ for every name), the horizon
from the run dir's own config.yaml, the heads expectation from its collector.outcome_targets, the DONE and RESUMED
lines from the watchdog log. Gates:
  S_REACHED   the checkpoint's step >= total_steps and the watchdog's DONE line.
  S_META      meta.yaml: encoder.c6 true, engine.bank_zero_copy true, git_dirty false, a git_sha.
  S_THETA0    the lane's log carries the THETA0 donor line (the warm start anchored to the donor's theta0).
  S_COUNTERS  every BOTH-ARMS counter present (a finite value on some row); l2init/* at the eval rows; aux_outcome/*
              iff the base keeps the heads; the SEARCHED-ONLY counters present on the searched arm and ABSENT on the
              control; search/played_frac == search/searched_frac > 0 on every update row (searched) or == 0 on every
              update row (control); loss/approx_kl_unsearched and loss/grad_norm moving.
  S_RESUME    (with --expect-resume) meta.yaml's resumes, the watchdog's RESUMED line with c6=1, the history's
              segments matching the resumes (read through scripts/merge_history.py).
  S_ERRORS    no Traceback in the lane's nohup/resume logs.
PASS iff every gate is ok. eval/win_rate is printed as DESCRIPTIVE only -- a smoke reads nothing (CLAUDE.md rule 6).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys

import pandas as pd
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from merge_history import history_path  # noqa: E402  (merged-or-plain history for a run dir)

_spec = importlib.util.spec_from_file_location("derive_r7_fleet", os.path.join(REPO, "scripts/derive_r7_fleet.py"))
_derive = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_derive)
GATE_COUNTERS = _derive.GATE_COUNTERS
THETA0_LINE = "THETA0: warm start anchored to the donor's theta0"


def load_yaml(p: str) -> dict:
    with open(p) as f:
        return yaml.safe_load(f) or {}


def ckpt_step(run: str) -> int:
    import torch
    return int(torch.load(os.path.join(run, "checkpoint.pt"), map_location="cpu", weights_only=False)["step"])


def n_offline(run: str) -> int:
    import glob
    return len(glob.glob(os.path.join(run, "wandb/offline-run-*/run-*.wandb")))


def check(run: str, arm: str, watchdog_log: str, expect_resume: bool, step: int | None = None,
          history: str | None = None) -> dict:
    rel = os.path.relpath(os.path.abspath(run), REPO)
    cfg, meta = load_yaml(os.path.join(run, "config.yaml")), load_yaml(os.path.join(run, "meta.yaml"))
    wd_lines = open(watchdog_log).read().splitlines() if os.path.exists(watchdog_log) else []
    gates: dict[str, dict] = {}

    total = int(cfg["total_steps"])
    step = ckpt_step(run) if step is None else step
    done = [l for l in wd_lines if f"{rel} DONE at step" in l]
    gates["S_REACHED"] = {"ok": bool(step >= total and done), "checkpoint_step": step, "total_steps": total,
                          "watchdog_done_line": done[-1] if done else None}

    enc, eng = meta.get("encoder") or {}, meta.get("engine") or {}
    gates["S_META"] = {"ok": bool(enc.get("c6") is True and eng.get("bank_zero_copy") is True
                                  and meta.get("git_dirty") is False and meta.get("git_sha")),
                       "encoder.c6": enc.get("c6"), "engine.bank_zero_copy": eng.get("bank_zero_copy"),
                       "git_sha": meta.get("git_sha"), "git_dirty": meta.get("git_dirty")}

    logs = [p for p in (os.path.join(REPO, rel + ".nohup.log"), os.path.join(REPO, rel + ".resume.log")) if os.path.exists(p)]
    theta0 = [l.strip() for p in logs for l in open(p, errors="replace") if THETA0_LINE in l]
    gates["S_THETA0"] = {"ok": bool(theta0), "lines": theta0[:3], "logs": [os.path.basename(p) for p in logs]}

    hp = history or str(history_path(run))
    h = pd.read_csv(hp)

    def present(c: str) -> bool:
        cols = [k for k in h.columns if k.startswith(c)] if c.endswith("/") else ([c] if c in h.columns else [])
        return any(h[k].dropna().map(lambda v: math.isfinite(float(v))).any() for k in cols)

    def moving(c: str) -> bool:
        s = h[c].dropna() if c in h else pd.Series(dtype=float)
        return bool(len(s) >= 2 and s.nunique() >= 2)

    heads = bool((cfg.get("collector") or {}).get("outcome_targets", False))
    missing = [c for c in GATE_COUNTERS["both"] + GATE_COUNTERS["eval_rows"] if not present(c)]
    if heads:
        missing += [c for c in GATE_COUNTERS["heads"] if not present(c)]
    leaked_heads = [] if heads else [c for c in GATE_COUNTERS["heads"] if present(c)]
    so = GATE_COUNTERS["searched_only"]
    so_wrong = [c for c in so if not present(c)] if arm == "searched" else [c for c in so if present(c)]
    upd = h[h["search/searched_frac"].notna() & h["search/played_frac"].notna()] if {
        "search/searched_frac", "search/played_frac"} <= set(h.columns) else h.iloc[0:0]
    if arm == "searched":
        played_ok = bool(len(upd)) and bool(((upd["search/played_frac"] - upd["search/searched_frac"]).abs() < 1e-12).all()) \
            and bool((upd["search/searched_frac"] > 0).all())
    else:
        played_ok = bool(len(upd)) and bool((upd["search/played_frac"] == 0).all())
    not_moving = [c for c in ("loss/approx_kl_unsearched", "loss/grad_norm") if not moving(c)]
    gates["S_COUNTERS"] = {
        "ok": bool(not missing and not leaked_heads and not so_wrong and played_ok and not not_moving),
        "history": hp, "rows": int(len(h)), "update_rows": int(len(upd)), "missing": missing,
        "heads_expected": heads, "heads_leaked": leaked_heads,
        ("searched_only_missing" if arm == "searched" else "searched_only_present_on_control"): so_wrong,
        "played_frac_ok": played_ok, "not_moving": not_moving,
        "eval_win_rate_descriptive": float(h["eval/win_rate"].dropna().iloc[-1]) if "eval/win_rate" in h and h["eval/win_rate"].notna().any() else None,
    }

    if expect_resume:
        res = meta.get("resumes") or []
        lines = [l for l in wd_lines if f"RESUMED {rel} ->" in l]
        n = n_offline(run)
        segs_ok = (n == 0) or (n == len(res) + 1)
        gates["S_RESUME"] = {"ok": bool(res and all("from_step" in r for r in res) and lines
                                        and all("c6=1" in l for l in lines) and segs_ok),
                             "resumes": res, "watchdog_resumed_lines": lines, "offline_runs": n,
                             "segments_match_resumes": segs_ok}

    tb = [f"{os.path.basename(p)}: {l.strip()[:160]}" for p in logs for l in open(p, errors="replace") if "Traceback" in l]
    gates["S_ERRORS"] = {"ok": not tb, "tracebacks": tb[:5], "n_tracebacks": len(tb)}

    verdict = "PASS" if all(g["ok"] for g in gates.values()) else "FAIL"
    return {"run": rel, "arm": arm, "verdict": verdict, "gates": gates}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--arm", choices=("searched", "control"), required=True)
    ap.add_argument("--watchdog-log", default=os.path.join(REPO, "runs/train_watchdog.log"))
    ap.add_argument("--expect-resume", action="store_true")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    r = check(args.run, args.arm, args.watchdog_log, args.expect_resume)
    print(f"R7 SMOKE CHECK {r['run']} ({r['arm']}): {r['verdict']}")
    for name, g in r["gates"].items():
        ev = {k: v for k, v in g.items() if k != "ok"}
        print(f"  {name}: {'OK' if g['ok'] else 'FAIL'}  {json.dumps(ev, default=str)[:900]}")
    if args.json_out:
        os.makedirs(os.path.dirname(args.json_out) or ".", exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump(r, f, indent=2, default=str)
        print(f"-> {args.json_out}")
    sys.exit(0 if r["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
