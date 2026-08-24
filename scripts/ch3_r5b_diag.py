"""CH3 R5b BI-4: D-7 (srank RECORDED) + D-8 (on-distribution discrimination
RECORDED) — both riders, neither ever gates (pre-reg Q6).

    python scripts/ch3_r5b_diag.py --prereg configs/eval/ch3_r5b_exit.yaml --lane s62

D-7  actor and critic ctx srank99 of the DISTILLED checkpoint (X1) on the
     fixed 13,702-obs probe set — the pooled results/ch3_r1/harvest_s6*.pkl
     observations, the same probe design B's M2 calibrated against the
     D23 record (control 11/17/16 reproduced as 11/16/17). Computed with
     scripts/d22_dormant_rank.py's own build()/probe()/srank99 (float64,
     Gram/eigvalsh fallback, hard-fail on non-finite). The base (X0)
     numbers are recomputed on the same probe for the paired quote — M2's
     D26 record is 49/51/35/52 critic-ctx of 384.

D-8  mean |v_LOO - v_own| on the lane's GATE-split REAL decision points:
     v_own = the lane's own critic, v_LOO = the mean of the OTHER THREE
     lanes' critics (the `loo` pool combiner, rl/search/agent.py
     _loo_critic_fn, mean over members). The number that settles whether
     on-distribution critic disagreement is ~0.06 (A's E2-bridge
     estimate) or ~0.45 (the R4-13 synthetic reading). A's consequence
     sentence travels in the pre-reg; this script only records.

Writes results/ch3_r5b/diag/<lane>_diag.json. RECORDED, NEVER GATED.
"""

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ch3_eval import _sha256  # noqa: E402
from ch3_r4_anchors import _git  # noqa: E402
from ch3_r5b_collect import COLLECT_DIR, LANES, assert_t_gate_pass  # noqa: E402
from ch3_r5b_distill import load_lane_dataset  # noqa: E402
from d22_dormant_rank import build, probe  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402

DIAG_DIR = "results/ch3_r5b/diag"
HARVEST_GLOB = "results/ch3_r1/harvest_s6?.pkl"
PROBE_ROWS_EXPECTED = 13702


def load_probe_obs() -> torch.Tensor:
    """The fixed probe set: every recorded obs across the four lanes'
    harvests, pooled in lane order (M2's construction)."""
    paths = sorted(Path(".").glob(HARVEST_GLOB))
    assert len(paths) == 4, f"expected 4 harvest files, got {paths}"
    obs = []
    for p in paths:
        episodes = pickle.load(open(p, "rb"))
        for ep in episodes:
            for row in ep["rows"]:
                obs.append(np.asarray(row["obs"], dtype=np.float32))
    arr = np.stack(obs)
    assert arr.shape == (PROBE_ROWS_EXPECTED, 828), (
        f"probe set is {arr.shape}, expected ({PROBE_ROWS_EXPECTED}, 828) — "
        "the fixed probe must not drift"
    )
    return torch.from_numpy(arr)


def sranks_of(ckpt_path: str, probe_obs: torch.Tensor, where: str) -> dict:
    c = load_checkpoint(ckpt_path)
    tk = c["config"]["agent"]["trunk_kwargs"]
    pd_dim = int(c["config"]["agent"].get("privileged_dim") or 0)
    assert pd_dim == 0, f"{where}: unexpected privileged critic"
    out = {}
    for part in ("actor", "critic"):
        net = build(part, tk, 0)
        net.load_state_dict(c["agent"][part])
        net.eval()
        _, ranks = probe(net, probe_obs, f"{where} {part}")
        out[part] = ranks
    return out


def d8_discrimination(prereg: dict, lane: str, collect_dir: str,
                      smoke: bool) -> dict:
    data = load_lane_dataset(lane, collect_dir, smoke=smoke)
    gate_ix = data["idx"]["GATE"]
    obs = torch.as_tensor(data["obs"][gate_ix], dtype=torch.float32)

    def critic_of(pin: str):
        spec = prereg["checkpoints"][pin]
        got = _sha256(spec["path"])
        assert got == spec["sha256"], f"B-5 FAIL: {pin} sha {got} != pin"
        c = load_checkpoint(spec["path"])
        net = build("critic", c["config"]["agent"]["trunk_kwargs"], 0)
        net.load_state_dict(c["agent"]["critic"])
        net.eval()
        return net

    own = critic_of(lane)
    pool = [x for x in ("s62", "s63", "s64", "s65") if x != lane]
    assert len(pool) == 3 and lane not in pool  # the loo membership law
    peers = [critic_of(x) for x in pool]
    with torch.no_grad():
        v_own = own(obs).reshape(-1)
        v_loo = torch.stack([p(obs).reshape(-1) for p in peers]).mean(dim=0)
        diff = (v_loo - v_own).abs()
    return {
        "gate_rows": int(len(gate_ix)),
        "loo_pool": pool,
        "mean_abs_v_loo_minus_v_own": float(diff.mean()),
        "p50": float(diff.median()),
        "p90": float(diff.quantile(0.9)),
        "max": float(diff.max()),
        "v_own_mean": float(v_own.mean()),
        "v_loo_mean": float(v_loo.mean()),
        "a_e2_reference": 0.06,
        "r4_13_synthetic_reference": 0.45,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--lane", required=True, choices=LANES)
    parser.add_argument("--collect-dir", default=COLLECT_DIR)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--skip-srank", action="store_true",
                        help="D-8 only (srank forwards 13,702 obs x 4 nets)")
    args = parser.parse_args()
    import os
    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required (B-6, offline jobs too)"
    with open(args.prereg) as f:
        prereg = yaml.safe_load(f)
    assert_t_gate_pass()
    lane = args.lane

    report = {"lane": lane, "smoke": args.smoke, "recorded_never_gated": True}
    if not args.skip_srank:
        probe_obs = load_probe_obs()
        base_path = prereg["checkpoints"][lane]["path"]
        dname = prereg["lane_map"][lane]
        x1_path = prereg["checkpoints"][dname]["path"]
        if args.smoke:
            x1_path = x1_path.replace("exit_", "exit_smoke_")
        report["D-7"] = {
            "probe_rows": int(len(probe_obs)),
            "x0": sranks_of(base_path, probe_obs, f"{lane} X0"),
            "x1": sranks_of(x1_path, probe_obs, f"{lane} X1"),
        }
    report["D-8"] = d8_discrimination(prereg, lane, args.collect_dir, args.smoke)
    report.update({
        "prereg": args.prereg,
        "prereg_sha256": _sha256(args.prereg),
        "git_sha": _git(["rev-parse", "HEAD"]),
        "finished_at": time.time(),
    })
    out_dir = Path(DIAG_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (f"{lane}_diag_smoke.json" if args.smoke
                     else f"{lane}_diag.json")
    out.write_text(json.dumps(report, indent=2) + "\n")
    d8 = report["D-8"]
    msg = f"{out.name}: D-8 mean |v_LOO - v_own| = " \
          f"{d8['mean_abs_v_loo_minus_v_own']:.4f} (p50 {d8['p50']:.4f})"
    if "D-7" in report:
        c7 = report["D-7"]
        msg += (f" | D-7 X1 critic ctx srank99 "
                f"{c7['x1']['critic']['srank99_ctx']} "
                f"(X0 {c7['x0']['critic']['srank99_ctx']})")
    print(msg)


if __name__ == "__main__":
    main()
