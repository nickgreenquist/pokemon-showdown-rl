"""CH3 R0.A — the instrumented headroom audit (descriptive, no verdict).

    python scripts/ch3_audit.py --prereg configs/eval/ch3_rung0.yaml --battles-per-lane 250

Plays battles-per-lane per D26 lane (default 250 x 4 = 1000) with the lane's
own policy, logging PER DECISION: turn, n_legal, p_max, top-2 gap, V(s), the
oppact L6 posterior entropy, and the gen-1 placeholder flags. Writes
<results_dir>/audit_<lane>.npz + a pooled audit_summary.json carrying every
R0.A output named in the ratified design:

  contested_frac at p_max < {0.99, 0.95, 0.90, 0.75}   (what a search could flip)
  placeholder_frac (Fight placeholder) + recharge_frac  (K0-3 input; measured
      BEFORE any bridge exists — prices the search's no-op stratum)
  decisions_per_battle vs SH                            (re-anchors the cost model)
  Z1: V calibration (10 bins), Brier + reliability/resolution/uncertainty,
      AUC by turn decile, AUC POOLED OVER DECILES 2-8 (the K0-1 statistic,
      aggregator named: pooled, per-decile recorded never governing),
      aleatoric floor of explained variance (the number D22 never produced)
  flip_budget (n_legal >= 2 fraction — sanity, not teeth)

K0-1 is evaluated and printed: pooled-AUC(deciles 2-8) < 0.60 -> NO V-LEAF
SEARCH (re-route to MC-leaf / FG-8). K0-2 needs A1's delta and is evaluated
by the grader once R0.B lands; this script prints its contested_frac half.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import yaml

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.common.evaluation import EVAL_SEED_OFFSET
from rl.envs.make import make_eval_env
from rl.envs.normalize import frozen_obs_env
from rl.train import make_agent


def _battle1(env):
    return env.unwrapped._env.env.battle1


def audit_lane(prereg: dict, lane: str, battles: int, out_dir: Path) -> dict:
    spec = prereg["checkpoints"][lane]
    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    torch.set_num_threads(cfg.torch_threads)
    env = frozen_obs_env(make_eval_env(cfg), cfg, ckpt)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])

    rows = []  # per decision: [ep, turn, n_legal, p_max, gap, V, aux_H, fight, rech]
    ep_out = []  # per episode: [outcome, final_turn, decisions]
    for ep in range(battles):
        obs, info = env.reset(seed=EVAL_SEED_OFFSET + cfg.eval_episodes + ep)
        mask = info.get("action_mask")
        done, steps = False, 0
        while not done and steps < 10_000:
            b = _battle1(env)
            avail = list(getattr(b, "available_moves", []) or [])
            fight = int(len(avail) == 1 and avail[0].id == "fight")
            rech = int(len(avail) == 1 and avail[0].id == "recharge")
            obs_t = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
            mask_t = torch.as_tensor(mask, dtype=torch.bool)
            with torch.no_grad():
                from rl.common.masking import masked_logits

                logits, *feats = agent.actor(obs_t, return_features=True)
                ml = masked_logits(logits, mask_t)
                probs = torch.softmax(ml, dim=-1)[0]
                v = float(agent.critic(obs_t).reshape(-1)[0])
                if agent.aux_head is not None:
                    aux_p = torch.softmax(agent.aux_head(*feats), dim=-1)[0]
                    aux_h = float(-(aux_p * torch.log(aux_p + 1e-12)).sum())
                else:
                    aux_h = float("nan")
            top2 = torch.topk(probs, k=min(2, probs.numel())).values
            rows.append([
                ep, getattr(b, "turn", steps), int(mask_t.sum()),
                float(top2[0]), float(top2[0] - (top2[1] if top2.numel() > 1 else 0.0)),
                v, aux_h, fight, rech,
            ])
            action = agent.act(obs, mask, deterministic=True)
            obs, reward, term, trunc, info = env.step(action)
            mask = info.get("action_mask")
            steps += 1
            done = term or trunc
        ep_out.append([info.get("outcome", 0) if done else 0,
                       rows[-1][1] if rows else 0, steps])
    env.close()
    dec = np.array(rows, dtype=np.float64)
    eps = np.array(ep_out, dtype=np.float64)
    np.savez_compressed(out_dir / f"audit_{lane}.npz", decisions=dec, episodes=eps)
    return {"lane": lane, "decisions": dec, "episodes": eps}


def _auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Rank AUC (probability a random win-state outscores a random non-win)."""
    pos, neg = scores[labels == 1], scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(order) + 1)
    # midranks for ties
    allv = np.concatenate([pos, neg])
    sv = np.sort(allv)
    uniq, start = np.unique(sv, return_index=True)
    for u, s in zip(uniq, start):
        idx = np.where(allv == u)[0]
        ranks[idx] = s + 1 + (len(idx) - 1) / 2.0
    r_pos = ranks[: len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def summarize(lanes: list[dict], out_dir: Path) -> dict:
    dec = np.concatenate([l["decisions"] for l in lanes])
    # label each decision with its episode outcome (win=1 else 0), rel turn
    labels, rel = [], []
    for l in lanes:
        d, e = l["decisions"], l["episodes"]
        out_by_ep = {int(i): (1 if e[int(i), 0] > 0 else 0) for i in range(len(e))}
        fin_by_ep = {int(i): max(e[int(i), 1], 1.0) for i in range(len(e))}
        for row in d:
            labels.append(out_by_ep[int(row[0])])
            rel.append(min(row[1] / fin_by_ep[int(row[0])], 1.0))
    y = np.array(labels, dtype=np.float64)
    rel = np.array(rel)
    v = dec[:, 5]
    pv = np.clip((v + 1) / 2, 0.0, 1.0)
    decile = np.minimum((rel * 10).astype(int), 9)
    mid = (decile >= 1) & (decile <= 7)  # deciles 2-8, 1-indexed

    bins = np.minimum((pv * 10).astype(int), 9)
    ybar = y.mean()
    rel_term = res_term = evar = 0.0
    calib = []
    for k in range(10):
        m = bins == k
        if not m.any():
            calib.append(None)
            continue
        pk, yk, nk = pv[m].mean(), y[m].mean(), int(m.sum())
        calib.append({"bin": k, "n": nk, "p_mean": pk, "y_mean": yk})
        rel_term += nk * (pk - yk) ** 2
        res_term += nk * (yk - ybar) ** 2
        evar += nk * (yk * (1 - yk))
    n = len(y)
    per_decile_auc = {int(k): _auc(v[decile == k], y[decile == k]) for k in range(10)}
    auc_pooled_2_8 = _auc(v[mid], y[mid])
    summary = {
        "n_decisions": n,
        "n_battles": int(sum(len(l["episodes"]) for l in lanes)),
        "decisions_per_battle_vs_SH": n / sum(len(l["episodes"]) for l in lanes),
        "flip_budget_nlegal_ge2": float((dec[:, 2] >= 2).mean()),
        "contested_frac": {
            str(t): float((dec[:, 3] < t).mean()) for t in (0.99, 0.95, 0.90, 0.75)
        },
        "placeholder_frac_fight": float(dec[:, 7].mean()),
        "recharge_frac": float(dec[:, 8].mean()),
        "aux_entropy_median": float(np.nanmedian(dec[:, 6])),
        "brier": float(((pv - y) ** 2).mean()),
        "brier_reliability": rel_term / n,
        "brier_resolution": res_term / n,
        "brier_uncertainty": float(ybar * (1 - ybar)),
        "aleatoric_floor_ev": float(1 - (evar / n) / max(y.var(), 1e-12)),
        "calibration_bins": calib,
        "auc_per_decile_recorded_never_governing": per_decile_auc,
        "K0_1_auc_pooled_deciles_2_8": auc_pooled_2_8,
        "K0_1_bar": 0.60,
        "K0_1_verdict": "PASS (V-leaf search allowed)"
        if auc_pooled_2_8 >= 0.60
        else "FAIL -> NO V-LEAF SEARCH; re-route to MC-leaf (FG-8)",
    }
    (out_dir / "audit_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", required=True)
    ap.add_argument("--battles-per-lane", type=int, default=250)
    args = ap.parse_args()
    prereg = yaml.safe_load(Path(args.prereg).read_text())
    out_dir = Path(prereg["results_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    lanes = []
    for lane in prereg["checkpoints"]:
        print(f"auditing {lane} ({args.battles_per_lane} battles)...")
        lanes.append(audit_lane(prereg, lane, args.battles_per_lane, out_dir))
    summary = summarize(lanes, out_dir)
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("calibration_bins",)}, indent=2))


if __name__ == "__main__":
    main()
