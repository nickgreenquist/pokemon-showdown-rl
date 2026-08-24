"""CH3 R5b BI-5: the placebo builder — cross-battle legal-count-matched
shuffled-distribution targets, dose-matched result-blind (pre-reg Q8).

    python scripts/ch3_r5b_placebo.py --prereg configs/eval/ch3_r5b_exit.yaml --lane s62

CONSTRUCTION (the rebuilt Q8, verbatim):
* pairing is CROSS-BATTLE within the same lane, within the FIT split: each
  FIT row is paired with a row drawn uniformly (seeded rng) from a
  DIFFERENT battle_id of the same lane;
* partners are restricted to rows with an IDENTICAL LEGAL-ACTION COUNT
  (mask sum), and the target is INDEX-ALIGNED onto the current row's legal
  set: the k-th legal action of this row receives the k-th component of
  the partner's tau-shaped target — every target is LEGAL BY CONSTRUCTION;
* the target is the SAME temperature tau applied to the PARTNER's row_ev
  (a shuffled DISTRIBUTION, form-matched to the treatment);
* rows with no partner at their legal count are DROPPED; the dropped
  fraction is reported; > 2% -> PL disclosed as ROW-MISMATCHED.

DOSE IS MEASURED, NOT ASSERTED: one fixed-seed 20-epoch run records
flip(PL_E vs X0) on the GATE split after EVERY epoch E — under a single
seeded generator the epoch-E state is bit-identical to a fixed_epochs=E
fit, so this IS the step-count search, exhaustively transcribed. The
selected step count is the in-band epoch (flip(PL)/flip(X1) in
[0.80, 1.25]) with ratio closest to 1.0 (ties -> fewer epochs). If no
epoch lands in band, PL is saved at the closest ratio and reported
DOSE-UNMATCHED / NON-BINDING (the D25-P sentence survives untested).
flip(X1) is read from the lane's BI-3 gates JSON — run gates first.

No win rate is an input anywhere; the treatment's step count is untouched.
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
    BATCH,
    FIT_DIR,
    LR,
    MAX_EPOCHS,
    build_base_agent,
    build_targets_f64,
    fidelity_tripwire,
    load_lane_dataset,
    save_distilled,
)
from ch3_r5b_gates import GATES_DIR, PL_DOSE_BAND, actor_read  # noqa: E402

from rl.common.masking import masked_logits  # noqa: E402

PAIR_SEED = 20260824
DROP_DISCLOSE_FRAC = 0.02


def build_placebo_targets(mask: np.ndarray, row_ev: np.ndarray,
                          chosen: np.ndarray, battle_id: np.ndarray,
                          fit_idx: np.ndarray, tau: str, seed: int):
    """Returns (kept_fit_idx, targets[n_all, a] float32 with rows only at
    kept_fit_idx, report). Pairing among FIT rows only."""
    rng = np.random.default_rng(seed)
    legal_count = mask.sum(axis=1)
    # partner pools: FIT rows grouped by legal count
    by_count: dict[int, np.ndarray] = {}
    for c in np.unique(legal_count[fit_idx]):
        by_count[int(c)] = fit_idx[legal_count[fit_idx] == c]
    tau_targets = build_targets_f64(row_ev, chosen, tau)  # over ALL rows
    n, a = mask.shape
    targets = np.zeros((n, a), dtype=np.float32)
    kept, dropped = [], 0
    for i in fit_idx:
        pool = by_count[int(legal_count[i])]
        pool = pool[battle_id[pool] != battle_id[i]]
        if not len(pool):
            dropped += 1
            continue
        j = int(rng.choice(pool))
        src = tau_targets[j][mask[j].astype(bool)]        # partner's legal set
        dst_actions = np.flatnonzero(mask[i])             # this row's legal set
        assert len(src) == len(dst_actions)
        targets[i, dst_actions] = src.astype(np.float32)
        kept.append(i)
    kept = np.asarray(kept, dtype=fit_idx.dtype)
    frac = dropped / len(fit_idx) if len(fit_idx) else 0.0
    report = {"fit_rows": int(len(fit_idx)), "kept": int(len(kept)),
              "dropped": dropped, "dropped_frac": frac,
              "row_mismatched": bool(frac > DROP_DISCLOSE_FRAC),
              "pair_seed": seed}
    return kept, targets, report


def dose_search(agent, obs, mask, targets, kept_idx, gate_obs, gate_mask,
                stored_x0_gate: np.ndarray, flip_x1: float, seed: int):
    """One fixed-seed MAX_EPOCHS run; flip(PL_E vs X0) measured on GATE after
    every epoch. Returns (probes, selected_epoch, selected_state)."""
    torch.manual_seed(seed)
    generator = torch.Generator().manual_seed(seed)
    optimizer = torch.optim.Adam(agent.actor.parameters(), lr=LR)
    fit_t = torch.as_tensor(kept_idx)
    probes = []
    best = None  # (dist_to_1, epoch, state)
    for epoch in range(1, MAX_EPOCHS + 1):
        perm = fit_t[torch.randperm(len(fit_t), generator=generator)]
        total = 0.0
        for i in range(0, len(perm), BATCH):
            ix = perm[i:i + BATCH]
            logp = F.log_softmax(masked_logits(agent.actor(obs[ix]), mask[ix]), -1)
            loss = -(torch.as_tensor(targets[ix.numpy()]) * logp).sum(-1).mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += loss.item() * len(ix)
        picks, _ = actor_read(agent.actor, gate_obs, gate_mask)
        flip_pl = float((picks.numpy() != stored_x0_gate).mean())
        ratio = flip_pl / flip_x1 if flip_x1 else float("inf")
        in_band = PL_DOSE_BAND[0] <= ratio <= PL_DOSE_BAND[1]
        probes.append({"epoch": epoch, "fit_loss": total / len(perm),
                       "flip_pl": flip_pl, "ratio": ratio,
                       "in_band": bool(in_band)})
        print(f"  epoch {epoch:2d}: flip_pl {flip_pl:.4f}, "
              f"ratio {ratio:.3f} {'IN BAND' if in_band else ''}", flush=True)
        dist = abs(ratio - 1.0)
        if best is None or (in_band and not best[3]) or \
                (in_band == best[3] and dist < best[0]):
            best = (dist, epoch,
                    {k: v.detach().clone()
                     for k, v in agent.actor.state_dict().items()},
                    in_band)
    _, epoch, state, in_band = best
    agent.actor.load_state_dict(state)
    return probes, epoch, in_band


def run_lane(prereg: dict, prereg_path: str, lane: str, collect_dir: str,
             smoke: bool) -> None:
    data = load_lane_dataset(lane, collect_dir, smoke=smoke)
    idx = data["idx"]
    obs = torch.as_tensor(data["obs"], dtype=torch.float32)
    mask_t = torch.as_tensor(data["mask"], dtype=torch.bool)

    tp = Path(FIT_DIR) / (f"{lane}_tau_grid_smoke.json" if smoke
                          else f"{lane}_tau_grid.json")
    tau = json.loads(tp.read_text())["chosen_tau"]
    gp = Path(GATES_DIR) / (f"{lane}_gates_smoke.json" if smoke
                            else f"{lane}_gates.json")
    gate_report = json.loads(gp.read_text())
    flip_x1 = gate_report["D-3"]["flip_x1_vs_x0"]

    kept, targets, pair_report = build_placebo_targets(
        data["mask"], data["row_ev"], data["chosen"], data["battle_id"],
        idx["FIT"], tau, PAIR_SEED + int(lane.lstrip("s")))
    print(f"{lane}: placebo pairing kept {pair_report['kept']}/"
          f"{pair_report['fit_rows']} (dropped {pair_report['dropped_frac']:.4f}"
          f"{', ROW-MISMATCHED' if pair_report['row_mismatched'] else ''}); "
          f"tau={tau}, flip_x1={flip_x1:.4f}")

    gate_ix = idx["GATE"]
    stored_x0_gate = np.asarray(data["policy_argmax"][gate_ix])
    _, _, agent = build_base_agent(prereg, lane)
    probes, sel_epoch, in_band = dose_search(
        agent, obs, mask_t, targets, kept,
        obs[gate_ix], mask_t[gate_ix], stored_x0_gate, flip_x1,
        seed=int(lane.lstrip("s")))

    base_ckpt, _, _ = build_base_agent(prereg, lane)
    pname = prereg["placebo_map"][lane]
    out_path = Path(prereg["checkpoints"][pname]["path"])
    if smoke:
        out_path = Path(str(out_path).replace("exit_", "exit_smoke_"))
    sha = save_distilled(base_ckpt, agent, out_path)
    fidelity_tripwire(agent, prereg, out_path, obs, mask_t)

    transcript = {
        "lane": lane,
        "smoke": smoke,
        "tau": tau,
        "pairing": pair_report,
        "dose_search": probes,
        "selected_epoch": sel_epoch,
        "dose_matched": bool(in_band),
        "non_binding_if_unmatched": not in_band,
        "flip_x1_reference": flip_x1,
        "band": list(PL_DOSE_BAND),
        "placebo_path": str(out_path),
        "placebo_sha256": sha,
        "prereg": prereg_path,
        "prereg_sha256": _sha256(prereg_path),
        "git_sha": _git(["rev-parse", "HEAD"]),
        "finished_at": time.time(),
    }
    out = Path(FIT_DIR) / (f"{lane}_placebo_smoke.json" if smoke
                           else f"{lane}_placebo.json")
    out.write_text(json.dumps(transcript, indent=2) + "\n")
    verdict = "DOSE-MATCHED" if in_band else "DOSE-UNMATCHED (NON-BINDING)"
    print(f"{out.name}: epoch {sel_epoch}, {verdict}; placebo pin {pname} "
          f"sha256 {sha} -> stamp into checkpoints: (B-5)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--lane", required=True, choices=LANES)
    parser.add_argument("--collect-dir", default=COLLECT_DIR)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    import os
    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required (B-6, offline jobs too)"
    with open(args.prereg) as f:
        prereg = yaml.safe_load(f)
    assert_t_gate_pass()
    run_lane(prereg, args.prereg, args.lane, args.collect_dir, args.smoke)


if __name__ == "__main__":
    main()
