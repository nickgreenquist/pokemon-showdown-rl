"""CH3 R5b BI-3: the offline gate harness — D-gates on the GATE split, before
any Stage-2 battle (pre-reg Q6, B-10).

    python scripts/ch3_r5b_gates.py --prereg configs/eval/ch3_r5b_exit.yaml --lane s62
    python scripts/ch3_r5b_gates.py --prereg ... --merge

Per lane, on GATE-split SEARCHED decisions only (placeholder rows never
entered the dataset — BI-1 excluded them at the recording site):

  D-2  a1 (X1 argmax agreement with search/chosen) >= a0_selfplay + 0.20,
       where a0_selfplay = stored policy_argmax agreement with chosen —
       MEASURED on GATE, free, and cross-checked against r5a's recorded
       self-play flip rate (|a0_gate - a0_r5a| <= 0.02 or the discrepancy
       is disclosed and the GATE value governs). STOP below.
  D-3  F (X1-vs-X0 argmax flip rate) in [0.25, (1 - a0_selfplay) + 0.05].
       X0's argmax is the STORED policy_argmax; the harness also recomputes
       it live from the base actor and records the replay agreement (B-8's
       offline determinism read — must be 1.0). STOP either side.
  D-4  mean masked entropy of X1 >= 0.55 x X0's, both computed here with
       the same code. Below -> the BC entropy-collapse landmine fired;
       re-resolve tau on SEL and re-fit (never on a win rate).
  D-5  critic identity: canonical digest AND torch.equal per tensor, X0 vs
       X1 (and X0 vs PL when the placebo pin exists). VOID otherwise.
  D-9  switch-action rate (argmax in 0..5) of X1 vs X0 — RECORDED, never
       gated; travels with every licensed sentence (C7).
  F-R  target provenance: on 500 seeded sample rows, an INDEPENDENT
       softmax_tau recompute must match the distiller's float64 targets to
       1e-9; every sampled row's chosen action is search-scored; the
       harvest's realized searched-decisions/battle is quoted from the
       collection final.
  F-L  battle-disjoint splits re-audited (zero intersection).
  PL   dose measurement: flip(PL vs X0) on GATE, required
       flip(PL)/flip(X1) in [0.80, 1.25] (measured when the PL pin exists;
       the dose search itself lives in the placebo builder).

Writes results/ch3_r5b/gates/<lane>_gates.json; --merge pools the four
lanes into d_gates.json with the all-green bit B-10 reads.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ch3_eval import _sha256  # noqa: E402
from ch3_r4_anchors import _git  # noqa: E402
from ch3_r5b_collect import COLLECT_DIR, LANES, assert_t_gate_pass  # noqa: E402
from ch3_r5b_distill import (  # noqa: E402
    FIT_DIR,
    build_targets_f64,
    critic_digest,
    load_lane_dataset,
)
from eval_checkpoint import _load_showdown_agent  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.common.masking import masked_logits  # noqa: E402

GATES_DIR = "results/ch3_r5b/gates"
R5A_DIR = "results/ch3_r5a"
D2_MARGIN = 0.20
D3_LO = 0.25
D3_TOL = 0.05
D4_FRAC = 0.55
A0_XCHECK_TOL = 0.02
FR_SAMPLE = 500
FR_TOL = 1e-9
PL_DOSE_BAND = (0.80, 1.25)
SWITCH_ACTIONS = 6  # poke-env SinglesEnv: actions 0..5 switch, 6..9 move


def _load_actor(prereg: dict, pin: str, smoke: bool = False):
    spec = prereg["checkpoints"][pin]
    path = spec["path"]
    if smoke and pin.startswith(("d6", "p6")):
        path = path.replace("exit_", "exit_smoke_")
    else:
        got = _sha256(path)
        if not spec["sha256"].startswith("<"):
            assert got == spec["sha256"], f"B-5 FAIL: {pin} sha {got} != pin"
    ckpt = load_checkpoint(path)
    agent = _load_showdown_agent(ckpt, Config(**ckpt["config"]))
    return ckpt, agent


@torch.no_grad()
def actor_read(actor, obs, mask, batch: int = 4096):
    """(argmax, mean masked entropy) over rows."""
    picks, ents = [], []
    for i in range(0, len(obs), batch):
        logits = masked_logits(actor(obs[i:i + batch]), mask[i:i + batch])
        logp = F.log_softmax(logits, dim=-1)
        picks.append(logits.argmax(dim=-1))
        ents.append(-(logp.exp() * logp).nan_to_num().sum(-1))
    return torch.cat(picks), float(torch.cat(ents).mean())


def r5a_selfplay_flip_rate(lane: str) -> float | None:
    p = Path(R5A_DIR) / f"ts_{lane}.final.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    searched = d.get("search/searched_decisions")
    flips = d.get("search/flips")
    return flips / searched if searched else None


def f_r_check(data: dict, tau: str, rng_seed: int = 20260824) -> dict:
    """Independent recompute (written independently of build_targets_f64 on
    purpose: per-row loop, exp/sum on the scored subset) vs the distiller's
    float64 targets, on FR_SAMPLE seeded rows, to FR_TOL."""
    n = len(data["row_ev"])
    rng = np.random.default_rng(rng_seed)
    ix = rng.choice(n, size=min(FR_SAMPLE, n), replace=False)
    ref = build_targets_f64(data["row_ev"][ix], data["chosen"][ix], tau)
    max_err = 0.0
    for j, i in enumerate(ix):
        ev = data["row_ev"][i].astype(np.float64)
        scored = np.flatnonzero(np.isfinite(ev))
        assert data["chosen"][i] in scored, (
            f"F-R FAIL: row {i} chosen action is not search-scored"
        )
        row = np.zeros_like(ev)
        if tau == "hard":
            row[data["chosen"][i]] = 1.0
        else:
            w = np.exp((ev[scored] / float(tau))
                       - (ev[scored] / float(tau)).max())
            row[scored] = w / w.sum()
        max_err = max(max_err, float(np.abs(row - ref[j]).max()))
    assert max_err <= FR_TOL, f"F-R FAIL: recompute max err {max_err} > {FR_TOL}"
    return {"sampled_rows": int(len(ix)), "max_abs_err": max_err, "tau": tau}


def run_lane(prereg: dict, prereg_path: str, lane: str, collect_dir: str,
             smoke: bool, out_dir: Path) -> dict:
    data = load_lane_dataset(lane, collect_dir, smoke=smoke)
    gate_ix = data["idx"]["GATE"]
    obs = torch.as_tensor(data["obs"][gate_ix], dtype=torch.float32)
    mask = torch.as_tensor(data["mask"][gate_ix], dtype=torch.bool)
    chosen = np.asarray(data["chosen"][gate_ix])
    stored_x0 = np.asarray(data["policy_argmax"][gate_ix])

    dname = prereg["lane_map"][lane]
    pname = prereg["placebo_map"][lane]
    base_ckpt, base_agent = _load_actor(prereg, lane)
    x1_ckpt, x1_agent = _load_actor(prereg, dname, smoke=smoke)

    x0_live, x0_entropy = actor_read(base_agent.actor, obs, mask)
    x1_pick, x1_entropy = actor_read(x1_agent.actor, obs, mask)
    x0_live = x0_live.numpy()
    x1_pick = x1_pick.numpy()

    replay_agreement = float((x0_live == stored_x0).mean())
    a0 = float((stored_x0 == chosen).mean())
    a1 = float((x1_pick == chosen).mean())
    flip_x1 = float((x1_pick != stored_x0).mean())
    f_base = 1.0 - a0

    r5a_flip = r5a_selfplay_flip_rate(lane)
    a0_xcheck = None if r5a_flip is None else abs(a0 - (1.0 - r5a_flip))

    # D-5 (X0 vs X1; PL folded in when its pin exists)
    d5 = {"x1_digest_equal": critic_digest(x1_ckpt["agent"]["critic"])
          == critic_digest(base_ckpt["agent"]["critic"])}
    d5["x1_torch_equal"] = all(
        torch.equal(x1_ckpt["agent"]["critic"][k], v)
        for k, v in base_ckpt["agent"]["critic"].items())
    pl_report = None
    pl_path = prereg["checkpoints"][pname]["path"]
    if smoke:
        pl_path = pl_path.replace("exit_", "exit_smoke_")
    if Path(pl_path).exists():
        pl_ckpt, pl_agent = _load_actor(prereg, pname, smoke=smoke)
        pl_pick, pl_entropy = actor_read(pl_agent.actor, obs, mask)
        flip_pl = float((pl_pick.numpy() != stored_x0).mean())
        d5["pl_digest_equal"] = critic_digest(pl_ckpt["agent"]["critic"]) \
            == critic_digest(base_ckpt["agent"]["critic"])
        d5["pl_torch_equal"] = all(
            torch.equal(pl_ckpt["agent"]["critic"][k], v)
            for k, v in base_ckpt["agent"]["critic"].items())
        pl_report = {
            "flip_pl": flip_pl,
            "dose_ratio": flip_pl / flip_x1 if flip_x1 else None,
            "dose_in_band": bool(flip_x1) and
                PL_DOSE_BAND[0] <= flip_pl / flip_x1 <= PL_DOSE_BAND[1],
            "entropy": pl_entropy,
        }

    # tau from the fit transcript (F-S: selection inputs on the record)
    tp = Path(FIT_DIR) / (f"{lane}_tau_grid_smoke.json" if smoke
                          else f"{lane}_tau_grid.json")
    transcript = json.loads(tp.read_text())
    tau = transcript["chosen_tau"]
    fr = f_r_check(data, tau)

    final_path = Path(collect_dir) / f"{lane}.final.json"
    rows_per_battle = None
    if final_path.exists():
        rows_per_battle = json.loads(final_path.read_text())["rows_per_battle"]

    d2_original_pass = a1 >= a0 + D2_MARGIN
    # AMENDMENT A1 (2026-08-25, prereg d2_rule_amended): capture-fraction
    # form + battle-clustered significance. The ORIGINAL verdict is
    # recorded beside it on every branch, per the amendment's own terms.
    gain_rows = (x1_pick == chosen).astype(float) - (stored_x0 == chosen).astype(float)
    bids = np.asarray(data["battle_id"][gate_ix])
    battle_means = [gain_rows[bids == b].mean() for b in np.unique(bids)]
    se_cluster = float(np.std(battle_means, ddof=1) / np.sqrt(len(battle_means)))
    capture = (a1 - a0) / (1.0 - a0) if a0 < 1.0 else 0.0
    d2_amended_pass = capture >= 0.20 and (a1 - a0) >= 4 * se_cluster
    if "d2_rule_amended" in prereg:
        d2_pass = d2_amended_pass
    else:
        d2_pass = d2_original_pass
    d3_hi = f_base + D3_TOL
    d3_pass = D3_LO <= flip_x1 <= d3_hi
    d4_floor = D4_FRAC * x0_entropy
    d4_pass = x1_entropy >= d4_floor

    x0_sha = _sha256(prereg["checkpoints"][lane]["path"])
    x1_file = prereg["checkpoints"][dname]["path"]
    if smoke:
        x1_file = x1_file.replace("exit_", "exit_smoke_")
    d6_files_differ = x0_sha != _sha256(x1_file)

    report = {
        "lane": lane,
        "smoke": smoke,
        "gate_rows": int(len(gate_ix)),
        "D-2": {"a0_selfplay": a0, "a1": a1, "margin_required": D2_MARGIN,
                "pass": bool(d2_pass),
                "original_absolute_pass": bool(d2_original_pass),
                "amended": {"active": "d2_rule_amended" in prereg,
                            "capture_fraction": capture,
                            "capture_bar": 0.20,
                            "gain": a1 - a0,
                            "se_cluster": se_cluster,
                            "n_battles": len(battle_means),
                            "pass": bool(d2_amended_pass)},
                "a0_r5a_flip_xcheck": {
                    "r5a_flip_rate": r5a_flip, "abs_diff": a0_xcheck,
                    "within_tol": None if a0_xcheck is None
                    else bool(a0_xcheck <= A0_XCHECK_TOL),
                    "governing": "GATE-split value"}},
        "D-3": {"flip_x1_vs_x0": flip_x1, "band": [D3_LO, d3_hi],
                "f_base": f_base, "pass": bool(d3_pass)},
        "D-4": {"x0_entropy": x0_entropy, "x1_entropy": x1_entropy,
                "floor": d4_floor, "pass": bool(d4_pass)},
        "D-5": {**d5, "pass": bool(d5["x1_digest_equal"] and d5["x1_torch_equal"]
                and d5.get("pl_digest_equal", True)
                and d5.get("pl_torch_equal", True))},
        "D-6_lane_files_differ": bool(d6_files_differ),
        "D-9": {"x0_switch_rate": float((stored_x0 < SWITCH_ACTIONS).mean()),
                "x1_switch_rate": float((x1_pick < SWITCH_ACTIONS).mean()),
                "recorded_never_gated": True},
        "F-R": {**fr, "rows_per_battle": rows_per_battle, "pass": True},
        "F-L": {"battle_disjoint": True, "pass": True},  # loader asserts
        "B-8_replay_agreement_x0": replay_agreement,
        "PL": pl_report,
        "tau": tau,
        "prereg": prereg_path,
        "prereg_sha256": _sha256(prereg_path),
        "git_sha": _git(["rev-parse", "HEAD"]),
        "finished_at": time.time(),
    }
    report["all_blocking_green"] = bool(
        d2_pass and d3_pass and d4_pass and report["D-5"]["pass"]
        and d6_files_differ and replay_agreement == 1.0)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (f"{lane}_gates_smoke.json" if smoke else f"{lane}_gates.json")
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{out.name}: a0 {a0:.4f} a1 {a1:.4f} "
          f"(D-2 {'PASS' if d2_pass else 'STOP'}), "
          f"F {flip_x1:.4f} in [{D3_LO}, {d3_hi:.4f}] "
          f"(D-3 {'PASS' if d3_pass else 'STOP'}), "
          f"H {x1_entropy:.4f} >= {d4_floor:.4f} "
          f"(D-4 {'PASS' if d4_pass else 'STOP'}), "
          f"D-5 {'PASS' if report['D-5']['pass'] else 'VOID'}, "
          f"replay {replay_agreement:.4f}")
    return report


def merge(out_dir: Path, smoke: bool) -> None:
    suffix = "_gates_smoke.json" if smoke else "_gates.json"
    reports = {}
    for lane in LANES:
        p = out_dir / f"{lane}{suffix}"
        assert p.exists(), f"--merge: {p} missing"
        reports[lane] = json.loads(p.read_text())
    pooled = {
        "lanes": list(LANES),
        "all_blocking_green": all(r["all_blocking_green"]
                                  for r in reports.values()),
        "per_lane": {lane: {
            "a0": r["D-2"]["a0_selfplay"], "a1": r["D-2"]["a1"],
            "flip": r["D-3"]["flip_x1_vs_x0"],
            "green": r["all_blocking_green"]} for lane, r in reports.items()},
        "finished_at": time.time(),
    }
    out = out_dir / ("d_gates_smoke.json" if smoke else "d_gates.json")
    out.write_text(json.dumps(pooled, indent=2) + "\n")
    print(f"{out.name}: all_blocking_green = {pooled['all_blocking_green']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--lane", choices=LANES)
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--collect-dir", default=COLLECT_DIR)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--out-dir", default=GATES_DIR)
    args = parser.parse_args()
    import os
    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required (B-6, offline jobs too)"
    with open(args.prereg) as f:
        prereg = yaml.safe_load(f)
    assert_t_gate_pass()
    if args.merge:
        merge(Path(args.out_dir), args.smoke)
        return
    assert args.lane, "--lane or --merge required"
    run_lane(prereg, args.prereg, args.lane, args.collect_dir, args.smoke,
             Path(args.out_dir))


if __name__ == "__main__":
    main()
