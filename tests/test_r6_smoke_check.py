"""scripts/r6_smoke_check.py: the R6 400k smoke's PASS on a synthetic run dir, and a FAIL on each
of the shapes it exists to catch (a false c6 stamp, a wrong head count, the heads leaking into a
trio B smoke, a resume the watchdog never logged, a RESUMED line without c6=1)."""
import pathlib
import sys

import pandas as pd
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from r6_smoke_check import check  # noqa: E402

W_ACTOR, W_CRITIC = 626059, 1807489


def _cfg(aux: bool):
    a = {"trunk_kwargs": {"value_sizes": [1024, 1024]}}
    if aux:
        a["aux_outcome_coef"] = 0.1
        a["trunk_kwargs"]["value_aux_out"] = 3
    return {"total_steps": 400000, "agent": a}


def _meta(aux: bool, c6=True):
    m = {"encoder": {"c6": c6}, "params": {"actor": W_ACTOR, "critic": W_CRITIC}}
    if aux:
        m["aux_outcome_coef"] = 0.1
        m["params"] = {"actor": W_ACTOR, "critic": W_CRITIC + 3075, "critic_aux_outcome": 3075,
                       "critic_without_aux_outcome": W_CRITIC}
        m["resumes"] = [{"at": "x", "from_step": 200012, "rng_restored": True}]
    return m


def _history(aux: bool, n=40):
    d = {"_step": [i * 10000 for i in range(n)], "l2init/anchor_dist_ctx_net": [0.01 * i for i in range(n)],
         "collect/episodes_discarded": [0] * n, "time/steps_per_sec": [900.0] * n, "eval/win_rate": [0.5] * n}
    if aux:
        for k in ("survivors_own", "survivors_opp", "hp_margin"):
            d[f"aux_outcome/ev_{k}"] = [0.1 + 0.005 * i for i in range(n)]
        d["loss/aux_outcome"] = [1.0 - 0.01 * i for i in range(n)]
        d["aux_outcome/grad_norm"] = [0.3 + 0.001 * i for i in range(n)]
        d["aux_outcome/clip_scale"] = [0.22] * n
    return pd.DataFrame(d)


def _run(tmp_path, name, aux, meta=None, hist=None, wd=None):
    run = tmp_path / "runs" / name
    run.mkdir(parents=True)
    (run / "config.yaml").write_text(yaml.safe_dump(_cfg(aux)))
    (run / "meta.yaml").write_text(yaml.safe_dump(meta if meta is not None else _meta(aux)))
    (hist if hist is not None else _history(aux)).to_csv(run / "history.csv", index=False)
    wref = tmp_path / "wref"
    wref.mkdir(exist_ok=True)
    (wref / "meta.yaml").write_text(yaml.safe_dump({"params": {"actor": W_ACTOR, "critic": W_CRITIC}}))
    wdl = tmp_path / "train_watchdog.log"
    rel = str(run)  # check() reports paths relative to the repo; the log lines must carry the same text
    import os
    rel = os.path.relpath(run, pathlib.Path(__file__).resolve().parents[1])
    wdl.write_text(wd if wd is not None else f"[t]   RESUMED {rel} -> pid 1 (own session; c6=1; log x)\n[t] {rel} DONE at step 400012/400000 (resumes=1)\n")
    return str(run), str(wref), str(wdl)


def test_trio_a_shape_passes_and_each_defect_fails(tmp_path):
    run, wref, wdl = _run(tmp_path, "a_ok", True)
    r = check(run, wref, wdl, expect_resume=True, step=400012, history=f"{run}/history.csv")
    assert r["verdict"] == "PASS", r
    assert r["gates"]["S_PARAMS"]["expected"]["critic_aux_outcome"] == 3075
    # a false c6 stamp
    run, wref, wdl = _run(tmp_path, "a_c6", True, meta=_meta(True, c6=False))
    r = check(run, wref, wdl, expect_resume=True, step=400012, history=f"{run}/history.csv")
    assert r["verdict"] == "FAIL" and not r["gates"]["S_C6"]["ok"]
    # a 384-critic head count (1,155) stamped on a 1024 critic
    m = _meta(True); m["params"]["critic_aux_outcome"] = 1155; m["params"]["critic"] = W_CRITIC + 1155
    run, wref, wdl = _run(tmp_path, "a_head", True, meta=m)
    r = check(run, wref, wdl, expect_resume=True, step=400012, history=f"{run}/history.csv")
    assert not r["gates"]["S_PARAMS"]["ok"] and "critic_aux_outcome" in r["gates"]["S_PARAMS"]["mismatch"]
    # a DEAD head: EV flat at zero while the loss column still moves
    h = _history(True)
    for k in ("survivors_own", "survivors_opp", "hp_margin"):
        h[f"aux_outcome/ev_{k}"] = 0.0
    run, wref, wdl = _run(tmp_path, "a_dead", True, hist=h)
    r = check(run, wref, wdl, expect_resume=True, step=400012, history=f"{run}/history.csv")
    assert not r["gates"]["S_HISTORY"]["ok"] and not all(r["gates"]["S_HISTORY"]["aux_ev_rising"].values())
    # the lane never reached the horizon
    run, wref, wdl = _run(tmp_path, "a_short", True)
    r = check(run, wref, wdl, expect_resume=True, step=300000, history=f"{run}/history.csv")
    assert not r["gates"]["S_REACHED"]["ok"]


def test_resume_evidence(tmp_path):
    import os
    run, wref, wdl = _run(tmp_path, "a_nores", True, wd="")
    rel = os.path.relpath(run, pathlib.Path(__file__).resolve().parents[1])
    pathlib.Path(wdl).write_text(f"[t] {rel} DONE at step 400012/400000 (resumes=0)\n")
    r = check(run, wref, wdl, expect_resume=True, step=400012, history=f"{run}/history.csv")
    assert not r["gates"]["S_RESUME"]["ok"], "no RESUMED line must fail the resume test"
    pathlib.Path(wdl).write_text(f"[t]   RESUMED {rel} -> pid 1 (own session; c6=0; log x)\n[t] {rel} DONE at step 400012/400000 (resumes=1)\n")
    r = check(run, wref, wdl, expect_resume=True, step=400012, history=f"{run}/history.csv")
    assert not r["gates"]["S_RESUME"]["ok"], "a resume without the c6 flag is the watchdog defect this guards"
    # a trio B smoke expects no resume and no heads
    run, wref, wdl = _run(tmp_path, "b_ok", False)
    r = check(run, wref, wdl, expect_resume=False, step=400003, history=f"{run}/history.csv")
    assert r["verdict"] == "PASS" and "S_RESUME" not in r["gates"]
    run, wref, wdl = _run(tmp_path, "b_leak", False, hist=_history(True))
    r = check(run, wref, wdl, expect_resume=False, step=400003, history=f"{run}/history.csv")
    assert not r["gates"]["S_HISTORY"]["ok"] and r["gates"]["S_HISTORY"]["heads_leaked"]
    # a flat l2init trace (the dial ran and reported nothing)
    h = _history(False); h["l2init/anchor_dist_ctx_net"] = 0.0
    run, wref, wdl = _run(tmp_path, "b_flat", False, hist=h)
    r = check(run, wref, wdl, expect_resume=False, step=400003, history=f"{run}/history.csv")
    assert not r["gates"]["S_HISTORY"]["ok"]
