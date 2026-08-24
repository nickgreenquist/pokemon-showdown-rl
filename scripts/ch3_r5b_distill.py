"""CH3 R5b BI-2: the distiller — actor-only expert-iteration fit, frozen critic.

    python scripts/ch3_r5b_distill.py --prereg configs/eval/ch3_r5b_exit.yaml --lane s62

One lane per invocation. Loads the lane's Stage-2a collection
(results/ch3_r5b/collect/<lane>.chunk*.npz), splits by the pre-reg's
battle-disjoint sha rule (SEL 5% / GATE 5% / FIT 90%), runs the FULL
temperature grid {hard, 0.05, 0.10, 0.25, 0.50}, applies the pre-stated
selection rule on SEL ONLY, and writes runs/exit_<lane>/checkpoint.pt
carrying the base cfg VERBATIM and the full agent state with the CRITIC
BYTE-IDENTICAL (D-5; optimizer/updates/aux_head carried verbatim from the
base checkpoint — the supervised fit's own Adam moments are NOT persisted,
the base checkpoint's shape is).

Free numbers, all pre-declared (pre-reg Q5): LR 1e-3, batch 512, Adam
(scripts/train_bc.py committed defaults), train to the SEL-split
cross-entropy minimum with patience 3 evaluations (one per epoch), cap 20
epochs, KL-to-init DROPPED, no dose-based early stopping.

SEL METRIC — THE IMPLEMENTED READING, ON THE RECORD: the selection rule
("the SMALLEST tau whose fit attains the minimum SEL cross-entropy within
1 standard error of the grid's best") needs a COMMON reference across
taus — CE against each tau's OWN target has a different floor per tau
(the target's entropy) and is not comparable. The common reference is CE
against the teacher's CHOSEN action (`search/chosen`) on SEL. Both the
common CE and the own-target CE are recorded in the grid transcript;
selection uses the common one. `hard` orders as the smallest tau (it is
the tau -> 0 limit). No win rate is an input anywhere.

The transcript (results/ch3_r5b/fit/<lane>_tau_grid.json) is written for
pre-launch transcription into the pre-reg header (B-10), and the distilled
pin sha256 is printed for `checkpoints:` stamping (B-5).

B-12 fidelity tripwire runs at save time: the written checkpoint is
rehydrated fresh and must produce BIT-IDENTICAL actor logits on up to
1000 stored obs.
"""

import argparse
import hashlib
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
from ch3_r5b_collect import COLLECT_DIR, LANES, OBS_DIM, assert_t_gate_pass  # noqa: E402
from eval_checkpoint import _load_showdown_agent  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.common.masking import masked_logits  # noqa: E402

FIT_DIR = "results/ch3_r5b/fit"
TAU_GRID = ("hard", "0.05", "0.10", "0.25", "0.50")  # ordered smallest-first
LR = 1e-3          # train_bc.py committed default, not swept
BATCH = 512        # train_bc.py committed default, not swept
MAX_EPOCHS = 20
PATIENCE = 3


def split_of(lane: str, battle_id: int) -> str:
    """The pre-reg's battle-disjoint rule, verbatim: h==0 SEL, h==1 GATE,
    else FIT."""
    h = int(hashlib.sha256(f"{lane}:{battle_id}".encode()).hexdigest()[:8], 16) % 20
    return "SEL" if h == 0 else ("GATE" if h == 1 else "FIT")


def load_lane_dataset(lane: str, collect_dir: str, smoke: bool = False) -> dict:
    """Every chunk npz of the lane, concatenated, with split indices."""
    prefix = f"{lane}_smoke" if smoke else lane
    paths = sorted(Path(collect_dir).glob(f"{prefix}.chunk*.npz"))
    assert paths, f"no {prefix}.chunk*.npz under {collect_dir}"
    parts = [np.load(p) for p in paths]
    data = {k: np.concatenate([p[k] for p in parts], axis=0)
            for k in ("obs", "mask", "row_ev", "chosen", "policy_argmax",
                      "battle_id", "decision_index")}
    for p in parts:
        assert str(p["lane"]) == lane, f"lane mismatch in {p}"
    assert data["obs"].shape[1] == OBS_DIM
    splits = np.array([split_of(lane, int(b)) for b in data["battle_id"]])
    idx = {name: np.flatnonzero(splits == name) for name in ("FIT", "SEL", "GATE")}
    for name, ix in idx.items():
        assert len(ix), f"{name} split is EMPTY for {lane} — dataset too small"
    # F-L: zero battle_id intersection across splits, by construction —
    # asserted anyway so the audit is mechanical.
    sets = {name: set(data["battle_id"][ix].tolist()) for name, ix in idx.items()}
    assert not (sets["FIT"] & sets["SEL"]) and not (sets["FIT"] & sets["GATE"]) \
        and not (sets["SEL"] & sets["GATE"]), "F-L FAIL: split battle overlap"
    data["idx"] = idx
    data["n_chunks"] = len(paths)
    return data


def build_targets_f64(row_ev: np.ndarray, chosen: np.ndarray, tau: str) -> np.ndarray:
    """softmax_tau over the search-scored (finite) entries in FLOAT64; 'hard'
    = one-hot on search/chosen. Rows the search did not score get exact zero
    mass. F-R's offline recompute compares against THIS (the fit's own
    intermediate) at 1e-9 — the float32 training cast rounds at ~1e-8."""
    n, a = row_ev.shape
    out = np.zeros((n, a), dtype=np.float64)
    if tau == "hard":
        out[np.arange(n), chosen] = 1.0
        return out
    t = float(tau)
    ev = row_ev.astype(np.float64)
    finite = np.isfinite(ev)
    z = np.where(finite, ev / t, -np.inf)
    z -= z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def build_targets(row_ev: np.ndarray, chosen: np.ndarray, tau: str) -> torch.Tensor:
    return torch.as_tensor(build_targets_f64(row_ev, chosen, tau).astype(np.float32))


def critic_digest(critic_sd: dict) -> str:
    """Canonical D-5 digest of a critic sub-state_dict: sorted keys, each
    contributing name/shape/dtype/raw bytes. Deterministic across processes
    (torch.save zip bytes are not guaranteed to be)."""
    h = hashlib.sha256()
    for k in sorted(critic_sd):
        t = critic_sd[k].detach().cpu().contiguous()
        h.update(k.encode())
        h.update(str(tuple(t.shape)).encode())
        h.update(str(t.dtype).encode())
        h.update(t.numpy().tobytes())
    return h.hexdigest()


def build_base_agent(prereg: dict, lane: str):
    spec = prereg["checkpoints"][lane]
    got = _sha256(spec["path"])
    assert got == spec["sha256"], f"B-5 FAIL: {lane} sha256 {got} != pin"
    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    agent = _load_showdown_agent(ckpt, cfg)
    assert type(agent.actor).__name__ != "PrefixSliceActor", (
        "distillation requires a native-828 checkpoint, got a sliced shim"
    )
    return ckpt, cfg, agent


def sel_ce(actor, obs, mask, chosen, idx, batch: int = 4096) -> tuple[float, float]:
    """Common-reference SEL metric: mean and se of per-row CE against the
    teacher's chosen action."""
    ces = []
    with torch.no_grad():
        for i in range(0, len(idx), batch):
            ix = idx[i:i + batch]
            logits = masked_logits(actor(obs[ix]), mask[ix])
            ces.append(F.cross_entropy(logits, chosen[ix], reduction="none"))
    ce = torch.cat(ces)
    return float(ce.mean()), float(ce.std(unbiased=True) / len(ce) ** 0.5)


def own_target_ce(actor, obs, mask, targets, idx, batch: int = 4096) -> float:
    tot, n = 0.0, 0
    with torch.no_grad():
        for i in range(0, len(idx), batch):
            ix = idx[i:i + batch]
            logp = F.log_softmax(masked_logits(actor(obs[ix]), mask[ix]), dim=-1)
            tot += float(-(targets[ix] * logp).sum(-1).sum())
            n += len(ix)
    return tot / n


def fit_actor(agent, obs, mask, targets, chosen, fit_idx, sel_idx, seed: int,
              fixed_epochs: int | None = None) -> dict:
    """The fit, shared with the placebo builder (BI-5). Trains agent.actor in
    place; restores the best-SEL weights before returning. `fixed_epochs`
    (the placebo's ONE knob) disables early stopping and the best-weights
    restore — the dose search owns the stop, result-blind."""
    torch.manual_seed(seed)
    generator = torch.Generator().manual_seed(seed)
    optimizer = torch.optim.Adam(agent.actor.parameters(), lr=LR)
    fit_t = torch.as_tensor(fit_idx)
    history, best = [], (float("inf"), -1, None)  # (sel_ce, epoch, state)
    stale = 0
    n_epochs = fixed_epochs if fixed_epochs is not None else MAX_EPOCHS
    for epoch in range(1, n_epochs + 1):
        perm = fit_t[torch.randperm(len(fit_t), generator=generator)]
        total = 0.0
        for i in range(0, len(perm), BATCH):
            ix = perm[i:i + BATCH]
            logp = F.log_softmax(masked_logits(agent.actor(obs[ix]), mask[ix]), -1)
            loss = -(targets[ix] * logp).sum(-1).mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += loss.item() * len(ix)
        ce, se = sel_ce(agent.actor, obs, mask, chosen, sel_idx)
        history.append({"epoch": epoch, "fit_loss": total / len(perm),
                        "sel_ce": ce, "sel_ce_se": se})
        print(f"  epoch {epoch:2d}: fit_loss {total / len(perm):.4f}, "
              f"sel_ce {ce:.4f} (+/-{se:.4f})", flush=True)
        if fixed_epochs is None:
            if ce < best[0]:
                best = (ce, epoch, {k: v.detach().clone()
                                    for k, v in agent.actor.state_dict().items()})
                stale = 0
            else:
                stale += 1
                if stale >= PATIENCE:
                    break
    if fixed_epochs is None:
        assert best[2] is not None
        agent.actor.load_state_dict(best[2])
        ce, se = best[0], history[best[1] - 1]["sel_ce_se"]
        best_epoch = best[1]
    else:
        ce, se = history[-1]["sel_ce"], history[-1]["sel_ce_se"]
        best_epoch = n_epochs
    return {"sel_ce": ce, "sel_ce_se": se, "best_epoch": best_epoch,
            "epochs_run": len(history), "history": history}


def select_tau(grid: dict) -> tuple[str, str]:
    """The pre-stated rule: SMALLEST tau (TAU_GRID order, 'hard' smallest)
    whose SEL common-reference CE is within 1 se of the grid's best."""
    best = min(TAU_GRID, key=lambda t: grid[t]["sel_ce"])
    bar = grid[best]["sel_ce"] + grid[best]["sel_ce_se"]
    return best, next(t for t in TAU_GRID if grid[t]["sel_ce"] <= bar)


def save_distilled(base_ckpt: dict, agent, out_path: Path) -> str:
    """Base cfg VERBATIM, full agent state, critic/optimizer/updates/aux_head
    carried byte-for-byte from the base checkpoint; ONLY the actor moves. No
    normalizers block is added (D26 checkpoints have none — the frozen-
    normalizer trap must not be 'helpfully' armed, pre-reg Q5)."""
    assert "normalizers" not in base_ckpt, "base unexpectedly carries normalizers"
    agent_state = dict(base_ckpt["agent"])
    agent_state["actor"] = {k: v.detach().cpu() for k, v in
                            agent.actor.state_dict().items()}
    payload = {"agent": agent_state, "step": base_ckpt["step"],
               "config": base_ckpt["config"]}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, out_path)
    # D-5 self-check: the written critic digests identical to the base's.
    reread = load_checkpoint(out_path)
    assert critic_digest(reread["agent"]["critic"]) == \
        critic_digest(base_ckpt["agent"]["critic"]), "D-5 FAIL at save time"
    for k, v in base_ckpt["agent"]["critic"].items():
        assert torch.equal(reread["agent"]["critic"][k], v), f"D-5 FAIL: {k}"
    return _sha256(str(out_path))


def fidelity_tripwire(agent, prereg: dict, out_path: Path, obs, mask, n: int = 1000):
    """B-12: rehydrate the written checkpoint and assert BIT-IDENTICAL actor
    logits on up to n stored obs."""
    ckpt = load_checkpoint(out_path)
    cfg = Config(**ckpt["config"])
    fresh = _load_showdown_agent(ckpt, cfg)
    ix = torch.arange(min(n, len(obs)))
    with torch.no_grad():
        a = masked_logits(agent.actor(obs[ix]), mask[ix])
        b = masked_logits(fresh.actor(obs[ix]), mask[ix])
    assert torch.equal(a, b), "B-12 FAIL: rehydrated logits differ bitwise"
    print(f"B-12 fidelity tripwire: bit-identical logits on {len(ix)} obs")


def run_lane(prereg: dict, prereg_path: str, lane: str, collect_dir: str,
             smoke: bool) -> None:
    data = load_lane_dataset(lane, collect_dir, smoke=smoke)
    idx = data["idx"]
    obs = torch.as_tensor(data["obs"], dtype=torch.float32)
    mask = torch.as_tensor(data["mask"], dtype=torch.bool)
    chosen = torch.as_tensor(data["chosen"], dtype=torch.int64)
    print(f"{lane}: {len(obs)} searched rows over {data['n_chunks']} chunks | "
          f"FIT {len(idx['FIT'])} / SEL {len(idx['SEL'])} / GATE {len(idx['GATE'])}")

    seed = int(lane.lstrip("s"))
    grid = {}
    fitted = {}
    for tau in TAU_GRID:
        print(f"tau={tau}:")
        _, _, agent = build_base_agent(prereg, lane)
        targets = build_targets(data["row_ev"], data["chosen"], tau)
        res = fit_actor(agent, obs, mask, targets, chosen,
                        idx["FIT"], idx["SEL"], seed)
        res["own_target_sel_ce"] = own_target_ce(
            agent.actor, obs, mask, targets, idx["SEL"])
        grid[tau] = res
        fitted[tau] = agent

    best_tau, chosen_tau = select_tau(grid)
    print(f"grid best tau={best_tau} (sel_ce {grid[best_tau]['sel_ce']:.4f}); "
          f"selected SMALLEST within 1 se: tau={chosen_tau}")

    base_ckpt, _, _ = build_base_agent(prereg, lane)
    dname = f"d{lane.lstrip('s')}"
    out_path = Path(prereg["checkpoints"][dname]["path"])
    if smoke:
        out_path = Path(str(out_path).replace("exit_", "exit_smoke_"))
    sha = save_distilled(base_ckpt, fitted[chosen_tau], out_path)
    fidelity_tripwire(fitted[chosen_tau], prereg, out_path, obs, mask)

    fit_dir = Path(FIT_DIR)
    fit_dir.mkdir(parents=True, exist_ok=True)
    transcript = {
        "lane": lane,
        "smoke": smoke,
        "selection_rule": "smallest tau with SEL common-reference CE (vs "
                          "search/chosen) within 1 se of the grid best; no "
                          "win rate is an input",
        "grid": {t: {k: v for k, v in grid[t].items() if k != "history"}
                 for t in TAU_GRID},
        "history": {t: grid[t]["history"] for t in TAU_GRID},
        "best_tau": best_tau,
        "chosen_tau": chosen_tau,
        "lr": LR, "batch": BATCH, "max_epochs": MAX_EPOCHS, "patience": PATIENCE,
        "kl_to_init": 0.0,
        "rows": {k: int(len(v)) for k, v in idx.items()},
        "distilled_path": str(out_path),
        "distilled_sha256": sha,
        "critic_digest": critic_digest(base_ckpt["agent"]["critic"]),
        "prereg": prereg_path,
        "prereg_sha256": _sha256(prereg_path),
        "git_sha": _git(["rev-parse", "HEAD"]),
        "finished_at": time.time(),
    }
    tp = fit_dir / (f"{lane}_tau_grid_smoke.json" if smoke
                    else f"{lane}_tau_grid.json")
    tp.write_text(json.dumps(transcript, indent=2) + "\n")
    print(f"{tp.name}: chosen tau={chosen_tau}; distilled pin {dname} "
          f"sha256 {sha} -> stamp into checkpoints: (B-5)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--lane", required=True, choices=LANES)
    parser.add_argument("--collect-dir", default=COLLECT_DIR)
    parser.add_argument("--smoke", action="store_true",
                        help="fit on <lane>_smoke chunks, write exit_smoke_* pin")
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
