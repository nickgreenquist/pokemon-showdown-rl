#!/usr/bin/env python
"""R6 400k SMOKE CHECK -- R0 gate (1) of the trio headers (configs/showdown_r6_trio_{a,b}.yaml),
computed from the smoke's run dir so the PASS is read, not eyeballed.

    python scripts/r6_smoke_check.py runs/showdown_r6_trio_a_smoke400k_s904 --expect-resume [--json-out ...]
    python scripts/r6_smoke_check.py runs/showdown_r6_trio_b_smoke400k_s912 [--json-out ...]

Every expectation is DERIVED, never typed (docs/landmines.md, the typed-dial-list shape):
  * the horizon from the run dir's own config.yaml; the DONE line from the watchdog log;
  * the actor and the critic-without-head counts from the W reference lane's OWN meta.yaml
    (runs/showdown_monster200m_w_s104 by default: the base every R6 lane derives from);
  * the outcome head's size from the config: value_aux_out * (value_sizes[-1] + 1);
  * the aux_outcome/ev_* column COUNT from value_aux_out; l2init/* from what the run logged.
Gates: S_REACHED, S_C6, S_PARAMS, S_HISTORY (columns present AND moving; l2init rising;
collect/episodes_discarded == 0), S_RESUME (with --expect-resume: meta.yaml `resumes`, the
watchdog's RESUMED line carrying c6=1, the split history merged by scripts/merge_history.py),
S_ERRORS (no Traceback in the lane's nohup/resume logs). PASS iff every gate is ok. eval/win_rate
is printed as DESCRIPTIVE only -- a smoke reads nothing (CLAUDE.md rule 6).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

import pandas as pd
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from merge_history import history_path  # noqa: E402  (merged-or-plain history for a run dir)
REPORT_COLS = ("time/steps_per_sec", "time/update_sec", "time/collect_sec", "loss/approx_kl",
               "loss/entropy", "loss/explained_variance", "eval/win_rate")
ERR_RE = re.compile(r"\bError\b|illegal|desync", re.IGNORECASE)


def load_yaml(p: str) -> dict:
    with open(p) as f:
        return yaml.safe_load(f) or {}


def n_offline(run: str) -> int:
    return len(glob.glob(os.path.join(run, "wandb/offline-run-*/run-*.wandb")))


def ckpt_step(run: str) -> int:
    import torch
    return int(torch.load(os.path.join(run, "checkpoint.pt"), map_location="cpu", weights_only=False)["step"])


def check(run: str, w_ref: str, watchdog_log: str, expect_resume: bool, expect_c6: bool = True,
          step: int | None = None, history: str | None = None) -> dict:
    rel = os.path.relpath(os.path.abspath(run), REPO)
    cfg, meta, wmeta = load_yaml(os.path.join(run, "config.yaml")), load_yaml(os.path.join(run, "meta.yaml")), load_yaml(os.path.join(w_ref, "meta.yaml"))
    wd_lines = open(watchdog_log).read().splitlines() if os.path.exists(watchdog_log) else []
    gates: dict[str, dict] = {}

    total = int(cfg["total_steps"])
    step = ckpt_step(run) if step is None else step
    done = [l for l in wd_lines if f"{rel} DONE at step" in l]
    gates["S_REACHED"] = {"ok": bool(step >= total and done), "checkpoint_step": step, "total_steps": total,
                          "watchdog_done_line": done[-1] if done else None}

    c6 = (meta.get("encoder") or {}).get("c6")
    gates["S_C6"] = {"ok": bool(c6) == expect_c6, "stamped": c6, "expected": expect_c6}

    agent = cfg.get("agent") or {}
    coef = float(agent.get("aux_outcome_coef") or 0.0)
    tk = agent.get("trunk_kwargs") or {}
    vao = int(tk.get("value_aux_out") or 0)
    vs = tk.get("value_sizes") or []
    head = vao * (int(vs[-1]) + 1) if (vao and vs) else 0
    P, WP = meta.get("params") or {}, wmeta.get("params") or {}
    exp = {"actor": WP.get("actor")}
    if coef > 0:
        exp.update({"critic": WP.get("critic", 0) + head, "critic_aux_outcome": head,
                    "critic_without_aux_outcome": WP.get("critic")})
        coef_ok = meta.get("aux_outcome_coef") is not None and abs(float(meta["aux_outcome_coef"]) - coef) < 1e-12
    else:
        exp.update({"critic": WP.get("critic")})
        coef_ok = "aux_outcome_coef" not in meta and "critic_aux_outcome" not in P
    mism = {k: {"stamped": P.get(k), "expected": v} for k, v in exp.items() if P.get(k) != v}
    gates["S_PARAMS"] = {"ok": bool(not mism and coef_ok), "expected": exp, "stamped": P, "mismatch": mism,
                         "aux_outcome_coef": {"stamped": meta.get("aux_outcome_coef"), "config": coef},
                         "w_ref": w_ref, "head_formula": f"value_aux_out {vao} * (value_sizes[-1] {vs[-1] if vs else None} + 1)"}

    hp = history or str(history_path(run))
    h = pd.read_csv(hp)

    def series(c):
        return h[c].dropna() if c in h else pd.Series(dtype=float)

    def moving(c):
        s = series(c)
        return bool(len(s) >= 2 and s.nunique() >= 2)

    def rising(c):
        s = series(c)
        return bool(len(s) >= 2 and float(s.iloc[-1]) > float(s.iloc[0]))

    l2 = sorted(c for c in h.columns if c.startswith("l2init/"))
    aux_ev = sorted(c for c in h.columns if c.startswith("aux_outcome/ev_"))
    hist: dict = {"history": hp, "rows": int(len(h)), "last_step": int(h["_step"].max()) if "_step" in h else None,
                  "l2init_cols": l2, "l2init_rising": {c: rising(c) for c in l2}, "l2init_moving": {c: moving(c) for c in l2},
                  "aux_ev_cols": aux_ev, "aux_ev_expected_count": vao if coef > 0 else 0}
    ok = bool(l2) and all(rising(c) for c in l2) and all(moving(c) for c in l2)
    if coef > 0:
        hist["aux_ev_moving"] = {c: moving(c) for c in aux_ev}
        hist["aux_ev_last"] = {c: float(series(c).iloc[-1]) for c in aux_ev if len(series(c))}
        hist["loss_aux_outcome_moving"] = moving("loss/aux_outcome")
        ok &= len(aux_ev) == vao and all(moving(c) for c in aux_ev) and moving("loss/aux_outcome")
    else:
        hist["heads_leaked"] = bool(aux_ev or "loss/aux_outcome" in h)
        ok &= not hist["heads_leaked"]
    disc = series("collect/episodes_discarded")
    hist["episodes_discarded_sum"] = float(disc.sum()) if len(disc) else None
    ok &= bool(len(disc)) and float(disc.sum()) == 0.0
    for c in REPORT_COLS:
        s = series(c)
        hist[c.replace("/", "_") + "_mean"] = float(s.mean()) if len(s) else None
    hist["note"] = "eval/win_rate is DESCRIPTIVE; a smoke reads nothing (rule 6)"
    gates["S_HISTORY"] = {"ok": bool(ok), **hist}

    if expect_resume:
        res = meta.get("resumes") or []
        lines = [l for l in wd_lines if f"RESUMED {rel} ->" in l]
        c6_ok = (all("c6=1" in l for l in lines) if expect_c6 else True) and bool(lines)
        n = n_offline(run)
        segs_ok = (n == 0) or (n == len(res) + 1)
        gates["S_RESUME"] = {"ok": bool(res and all("from_step" in r for r in res) and lines and c6_ok and segs_ok),
                             "resumes": res, "watchdog_resumed_lines": lines, "offline_runs": n,
                             "segments_match_resumes": segs_ok}

    tb, errs = [], []
    for p in (os.path.join(REPO, rel + ".nohup.log"), os.path.join(REPO, rel + ".resume.log")):
        if os.path.exists(p):
            for l in open(p, errors="replace"):
                if "Traceback" in l:
                    tb.append(f"{os.path.basename(p)}: {l.strip()[:160]}")
                elif ERR_RE.search(l):
                    errs.append(f"{os.path.basename(p)}: {l.strip()[:160]}")
    gates["S_ERRORS"] = {"ok": not tb, "tracebacks": tb[:5], "n_tracebacks": len(tb),
                         "error_like_lines": errs[:8], "n_error_like_lines": len(errs)}

    verdict = "PASS" if all(g["ok"] for g in gates.values()) else "FAIL"
    return {"run": rel, "verdict": verdict, "gates": gates}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--w-ref", default=os.path.join(REPO, "runs/showdown_monster200m_w_s104"))
    ap.add_argument("--watchdog-log", default=os.path.join(REPO, "runs/train_watchdog.log"))
    ap.add_argument("--expect-resume", action="store_true")
    ap.add_argument("--no-c6", action="store_true", help="expect encoder.c6 false (never for an R6 smoke)")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    r = check(args.run, args.w_ref, args.watchdog_log, args.expect_resume, expect_c6=not args.no_c6)
    print(f"SMOKE CHECK {r['run']}: {r['verdict']}")
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
