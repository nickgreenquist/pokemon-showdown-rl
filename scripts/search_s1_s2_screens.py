"""Search relook — offline screens S1 and S2 on the chapter-3 search line.

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
      python scripts/search_s1_s2_screens.py \
        --prereg configs/eval/ch3_rung2.yaml --harvest results/ch3_r1 \
        --per-lane 200 --out results/search_s1_s2

Both screens replay the SAME strided sample of real harvested non-aliased
decisions (200/lane over the four D26 lanes = 800) through the R2-credited
search path. Offline: no server, no battles, no websocket. PUBLIC harvest
file only (harvest_<lane>.pkl, never harvest_priv_* — FG-4).

The READ RULES ARE PRE-REGISTERED in docs/search_relook/S1_S2_SCREENS.md,
written before this script was run. Restated here verbatim:

  S1 FIRES if the pooled sd of Delta (across decisions and determinizations)
  >= the median row_ev margin — the encoding artefact is then as large as
  the decision itself and the leaf encoder is the first fix, before any
  depth work.

  S2 IS ONE-DIRECTIONAL. R3 measured flip rate RISING with evaluator noise
  while wins FELL (flips are not wins), so a high flip rate proves nothing;
  but a LOW one bounds headroom: if L flips < 5% of M's decisions, then at
  ~38 decisions/battle a 4x budget touches < 2 decisions per battle and
  cannot plausibly move win rate past the 0.025 credit line.

S1 — leaf-encoding bias priced in VALUE units. FG-6 measured that a
shadow-encoded determinized state differs from the live encoding in ~33.9
dims/state (results/ch3_r1/fg_battery.json, family_diff_counts). Nobody had
propagated that through the critic. Per decision: v_root = critic(live obs);
for each of the SAME four determinizations Dose M draws (same
`decision_rng` key, same `sample_determinization` order, so these are M's
own dets), build the ROOT engine State with NO action applied, encode it
exactly as a leaf is encoded but at the ROOT turn
(`embed_battle(shadow_battle(state, battle.turn), type_chart)` — the FG-6
construction verbatim, only the turn differs from a leaf's turn+1), and take
v_det = critic(that encoding). Delta = v_det - v_root. Priced against the
decision's own scale: the row_ev margin (top1 - top2 over legal rows) from a
normal Dose-M `search.act` on the same decision.

S2 — budget headroom by flip rate. The same 800 decisions through Dose M and
Dose L (n_det 4 vs 16, separate SearchAgent instances, same
checkpoint_seed): flip rates L-vs-M, M-vs-greedy, L-vs-greedy, and the M
row_ev margin at the L-vs-M flips. Because both doses key the same
`decision_rng` and draw determinizations sequentially from it, L's first
four dets ARE M's four dets — L is a strict superset of M's sample, not an
independent redraw.

Writes <out>/s1.json and <out>/s2.json (per-decision rows + pooled stats).
"""

import argparse
import json
import os
import pickle
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.envs.showdown import embed_battle
from rl.search.agent import SearchAgent
from rl.search.bridge import BridgeCounters, battle_to_state
from rl.search.determinize import sample_determinization
from rl.search.harvest import rehydrate_battle
from rl.search.matrix import DOSES, SearchWatchdogError, decision_rng
from rl.search.shadow_battle import shadow_battle
from rl.train import make_agent

# Pre-stated S2 bound constant (decisions per battle). Conservative: a
# LARGER decisions/battle makes the "< 2 decisions touched" bound HARDER to
# meet, so this cannot flatter the screen. The harvest-measured value is
# computed alongside and reported as the secondary read.
DECISIONS_PER_BATTLE_PRESTATED = 38.0
S2_LOW_FLIP_THRESHOLD = 0.05
CREDIT_LINE = 0.025


def _load_agent(spec: dict):
    """Exactly scripts/ch3_r1_spike.py::_load_agent."""
    import gymnasium as gym

    from rl.envs.showdown import OBS_DIM

    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    assert not getattr(cfg, "normalize_obs", False)
    env = gym.Env()
    env.observation_space = gym.spaces.Box(-1.0, 4.0, shape=(OBS_DIM,), dtype=np.float32)
    env.action_space = gym.spaces.Discrete(10)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])
    return agent, cfg


def _critic(agent, batch: np.ndarray) -> np.ndarray:
    with torch.no_grad():
        v = agent.critic(torch.as_tensor(batch, dtype=torch.float32))
    return v.reshape(-1).numpy().astype(np.float64)


def _margin(row_ev: dict) -> tuple[float | None, float | None, int]:
    """(top1 - top2, sd across legal rows, n_legal) from stats['search/row_ev']."""
    vals = np.array(sorted((float(v) for v in row_ev.values()), reverse=True))
    if vals.size < 2:
        return None, (float(vals.std()) if vals.size else None), int(vals.size)
    return float(vals[0] - vals[1]), float(vals.std()), int(vals.size)


def screen_lane(prereg: dict, lane: str, n: int, harvest_dir: Path) -> tuple[list[dict], dict]:
    agent, cfg = _load_agent(prereg["checkpoints"][lane])
    search_m = SearchAgent(agent, DOSES["M"], checkpoint_seed=cfg.seed)
    search_l = SearchAgent(agent, DOSES["L"], checkpoint_seed=cfg.seed)
    type_chart = search_m._type_chart
    n_det_s1 = DOSES["M"].n_det

    with open(harvest_dir / f"harvest_{lane}.pkl", "rb") as f:
        battles = pickle.load(f)
    pool = [
        (bi, si)
        for bi, b in enumerate(battles)
        for si, row in enumerate(b["rows"])
        if not row["aliased"]
    ]
    lane_meta = {
        "lane": lane,
        "checkpoint_seed": int(cfg.seed),
        "n_episodes": len(battles),
        "n_rows_total": int(sum(len(b["rows"]) for b in battles)),
        "n_rows_nonaliased": len(pool),
        "searchable_decisions_per_battle": len(pool) / max(len(battles), 1),
    }
    idx = np.linspace(0, len(pool) - 1, num=n, dtype=int)

    out: list[dict] = []
    for k in idx:
        bi, si = pool[k]
        row = battles[bi]["rows"][si]
        turn = int(row["turn"])

        # ---- S1: root deltas on Dose M's own determinizations -----------
        battle = rehydrate_battle(row["battle"])
        v_root = float(_critic(agent, row["obs"][None, :].astype(np.float32))[0])
        rng = decision_rng(int(cfg.seed), bi, int(battle.turn), si)
        encs, det_err = [], None
        try:
            dets = [sample_determinization(battle, rng) for _ in range(n_det_s1)]
            for det in dets:
                state = battle_to_state(battle, det, BridgeCounters())
                sb = shadow_battle(state, turn=int(battle.turn))
                encs.append(embed_battle(sb, type_chart))
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:  # engine/PyO3 faults are DATA here
            det_err = f"{type(exc).__name__}: {exc}"
        if encs:
            v_det = _critic(agent, np.stack(encs).astype(np.float32))
            deltas = (v_det - v_root).tolist()
        else:
            deltas = []

        # ---- S2 + S1 margin: Dose M then Dose L on the same decision ----
        rec = {
            "lane": lane, "episode": bi, "step": si, "turn": turn,
            "v_root": v_root,
            "v_det": [float(x) for x in (v_det if encs else [])],
            "deltas": [float(x) for x in deltas],
            "det_error": det_err,
            "greedy_recorded": int(row["action"]),
        }
        # `act` does not mutate `battle` (verified offline: two acts on one
        # rehydrated object, and a third on a fresh one, return the same
        # action on 8/8 probed decisions), so the same object serves S1,
        # Dose M and Dose L — which also makes S1's dets object-identical,
        # not merely content-identical, to M's.
        for tag, search in (("m", search_m), ("l", search_l)):
            t0 = time.perf_counter()
            try:
                action, stats = search.act(
                    battle, row["obs"], row["mask"], battle_index=bi, decision_index=si
                )
                err = None
            except SearchWatchdogError as exc:
                action, stats, err = -1, {}, str(exc)
            rec[f"ms_{tag}"] = (time.perf_counter() - t0) * 1e3
            rec[f"chosen_{tag}"] = int(action)
            rec[f"err_{tag}"] = err
            rec[f"placeholder_skip_{tag}"] = int(stats.get("search/placeholder_skip", 0))
            rec[f"leaves_{tag}"] = int(stats.get("search/leaves", 0))
            row_ev = stats.get("search/row_ev")
            if row_ev:
                marg, sd, n_legal = _margin(row_ev)
                rec[f"margin_{tag}"] = marg
                rec[f"row_ev_sd_{tag}"] = sd
                rec[f"n_legal_{tag}"] = n_legal
            else:
                rec[f"margin_{tag}"] = None
                rec[f"row_ev_sd_{tag}"] = None
                rec[f"n_legal_{tag}"] = int(np.asarray(row["mask"]).sum())
        out.append(rec)
    return out, lane_meta


# ---------------------------------------------------------------------------
# aggregation
# ---------------------------------------------------------------------------

def _s1_stats(rows: list[dict]) -> dict:
    """Pooled S1 read. `usable` = a decision with 4 det deltas AND a defined
    Dose-M margin (>= 2 legal rows, no watchdog trip, not a placeholder)."""
    usable = [r for r in rows if r["deltas"] and r["margin_m"] is not None]
    if not usable:
        return {"n_decisions": len(rows), "n_usable": 0}
    all_deltas = np.array([d for r in usable for d in r["deltas"]], dtype=np.float64)
    mean_delta = np.array([float(np.mean(r["deltas"])) for r in usable])
    sd_delta = np.array([float(np.std(r["deltas"], ddof=1)) for r in usable])
    margins = np.array([float(r["margin_m"]) for r in usable])
    ev_sd = np.array([float(r["row_ev_sd_m"]) for r in usable])
    pooled_sd = float(all_deltas.std(ddof=1))
    median_margin = float(np.median(margins))
    return {
        "n_decisions": len(rows),
        "n_usable": len(usable),
        "n_delta_samples": int(all_deltas.size),
        # --- the pre-registered read ---
        "pooled_sd_delta": pooled_sd,
        "median_row_ev_margin": median_margin,
        "S1_FIRES": bool(pooled_sd >= median_margin),
        "ratio_sd_delta_over_median_margin": pooled_sd / median_margin if median_margin else None,
        # --- the declared secondary reads ---
        "frac_absmean_delta_gt_margin": float(np.mean(np.abs(mean_delta) > margins)),
        "mean_signed_delta": float(all_deltas.mean()),
        "se_mean_signed_delta_by_decision": float(mean_delta.std(ddof=1) / np.sqrt(len(usable))),
        "median_signed_delta": float(np.median(all_deltas)),
        "frac_delta_positive": float(np.mean(all_deltas > 0)),
        "mean_abs_mean_delta": float(np.abs(mean_delta).mean()),
        "median_abs_mean_delta": float(np.median(np.abs(mean_delta))),
        "mean_within_decision_sd_delta": float(sd_delta.mean()),
        "delta_percentiles": {
            p: float(np.percentile(all_deltas, p)) for p in (1, 5, 25, 50, 75, 95, 99)
        },
        "margin_percentiles": {
            p: float(np.percentile(margins, p)) for p in (5, 25, 50, 75, 95)
        },
        "mean_row_ev_margin": float(margins.mean()),
        "mean_row_ev_sd_across_rows": float(ev_sd.mean()),
        "median_row_ev_sd_across_rows": float(np.median(ev_sd)),
        "mean_v_root": float(np.mean([r["v_root"] for r in usable])),
    }


def _s2_stats(rows: list[dict]) -> dict:
    ok = [
        r for r in rows
        if r["err_m"] is None and r["err_l"] is None
        and not r["placeholder_skip_m"] and not r["placeholder_skip_l"]
    ]
    if not ok:
        return {"n_usable": 0}
    lm = np.array([r["chosen_l"] != r["chosen_m"] for r in ok])
    mg = np.array([r["chosen_m"] != r["greedy_recorded"] for r in ok])
    lg = np.array([r["chosen_l"] != r["greedy_recorded"] for r in ok])
    marg = np.array([r["margin_m"] if r["margin_m"] is not None else np.nan for r in ok])
    flip_marg = marg[lm & ~np.isnan(marg)]
    same_marg = marg[~lm & ~np.isnan(marg)]
    rate = float(lm.mean())
    return {
        "n_decisions": len(rows),
        "n_usable": len(ok),
        "n_watchdog_m": int(sum(r["err_m"] is not None for r in rows)),
        "n_watchdog_l": int(sum(r["err_l"] is not None for r in rows)),
        "n_placeholder_skips": int(sum(r["placeholder_skip_m"] for r in rows)),
        # --- the pre-registered read ---
        "flip_rate_L_vs_M": rate,
        "S2_LOW_FLIP_BOUND_HOLDS": bool(rate < S2_LOW_FLIP_THRESHOLD),
        "decisions_touched_per_battle_prestated_38": rate * DECISIONS_PER_BATTLE_PRESTATED,
        # --- the declared secondary reads ---
        "flip_rate_M_vs_greedy": float(mg.mean()),
        "flip_rate_L_vs_greedy": float(lg.mean()),
        "n_flips_L_vs_M": int(lm.sum()),
        "mean_margin_M_at_L_vs_M_flips": float(flip_marg.mean()) if flip_marg.size else None,
        "median_margin_M_at_L_vs_M_flips": float(np.median(flip_marg)) if flip_marg.size else None,
        "mean_margin_M_at_non_flips": float(same_marg.mean()) if same_marg.size else None,
        "median_margin_M_at_non_flips": float(np.median(same_marg)) if same_marg.size else None,
        "ms_per_decision_M": float(np.mean([r["ms_m"] for r in ok])),
        "ms_per_decision_L": float(np.mean([r["ms_l"] for r in ok])),
        "leaves_per_decision_M": float(np.mean([r["leaves_m"] for r in ok])),
        "leaves_per_decision_L": float(np.mean([r["leaves_l"] for r in ok])),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", default="configs/eval/ch3_rung2.yaml")
    ap.add_argument("--harvest", default="results/ch3_r1")
    ap.add_argument("--per-lane", type=int, default=200)
    ap.add_argument("--out", default="results/search_s1_s2")
    ap.add_argument("--torch-threads", type=int, default=2)
    ap.add_argument("--lanes", default="", help="comma list; default all in the prereg")
    args = ap.parse_args()

    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required (828-d D26 objects)"
    torch.set_num_threads(args.torch_threads)

    prereg = yaml.safe_load(Path(args.prereg).read_text())
    lanes = args.lanes.split(",") if args.lanes else list(prereg["checkpoints"])
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    metas: dict[str, dict] = {}
    t0 = time.perf_counter()
    for lane in lanes:
        print(f"[{time.strftime('%H:%M:%S')}] screening {lane} "
              f"({args.per_lane} decisions, S1 + Dose M + Dose L)...", flush=True)
        lrows, meta = screen_lane(prereg, lane, args.per_lane, Path(args.harvest))
        rows.extend(lrows)
        metas[lane] = meta
    wall = time.perf_counter() - t0

    dpb = float(np.mean([m["searchable_decisions_per_battle"] for m in metas.values()]))
    provenance = {
        "prereg": args.prereg,
        "harvest": args.harvest,
        "per_lane": args.per_lane,
        "lanes": lanes,
        "torch_threads": args.torch_threads,
        "wall_sec": wall,
        "dose_S1_dets": DOSES["M"].n_det,
        "root_encoding": "embed_battle(shadow_battle(battle_to_state(battle, det), turn=battle.turn), type_chart)",
        "root_encoding_note": (
            "identical to FG-6's construction (scripts/ch3_fidelity_check.py::"
            "fg6_encoder_parity) and to a leaf's encoding except the turn "
            "(root turn, not turn+1) and that no instruction branch is applied"
        ),
        "det_stream": (
            "decision_rng(cfg.seed, episode, battle.turn, step) then n_det "
            "sequential sample_determinization draws — byte-identical to the "
            "dets Dose M uses inside solve_decision"
        ),
        "lane_meta": metas,
        "searchable_decisions_per_battle_measured": dpb,
        "decisions_per_battle_prestated": DECISIONS_PER_BATTLE_PRESTATED,
    }

    s1 = {
        "screen": "S1 — leaf-encoding bias vs decision margin",
        "read_rule": (
            "S1 FIRES if the pooled sd of Delta (across decisions and "
            "determinizations) >= the median row_ev margin — the encoding "
            "artefact is then as large as the decision itself and the leaf "
            "encoder is the first fix, before any depth work."
        ),
        "provenance": provenance,
        "pooled": _s1_stats(rows),
        "per_lane": {ln: _s1_stats([r for r in rows if r["lane"] == ln]) for ln in lanes},
        "decisions": [
            {k: v for k, v in r.items() if not k.startswith(("chosen_", "err_l"))}
            for r in rows
        ],
    }
    s2_pooled = _s2_stats(rows)
    s2_pooled["decisions_touched_per_battle_measured"] = (
        s2_pooled.get("flip_rate_L_vs_M", float("nan")) * dpb
    )
    s2 = {
        "screen": "S2 — budget headroom by flip rate",
        "read_rule": (
            "S2 IS ONE-DIRECTIONAL. R3 measured flip rate RISING with "
            "evaluator noise while wins FELL (flips are not wins), so a high "
            "flip rate proves nothing; but a LOW one bounds headroom: if L "
            "flips < 5% of M's decisions, then at ~38 decisions/battle a 4x "
            "budget touches < 2 decisions per battle and cannot plausibly "
            "move win rate past the 0.025 credit line."
        ),
        "credit_line": CREDIT_LINE,
        "provenance": provenance,
        "pooled": s2_pooled,
        "per_lane": {ln: _s2_stats([r for r in rows if r["lane"] == ln]) for ln in lanes},
        "decisions": [
            {
                k: r[k] for k in (
                    "lane", "episode", "step", "turn", "chosen_m", "chosen_l",
                    "greedy_recorded", "margin_m", "margin_l", "row_ev_sd_m",
                    "n_legal_m", "leaves_m", "leaves_l", "ms_m", "ms_l",
                    "err_m", "err_l", "placeholder_skip_m",
                )
            }
            for r in rows
        ],
    }
    (outdir / "s1.json").write_text(json.dumps(s1, indent=2) + "\n")
    (outdir / "s2.json").write_text(json.dumps(s2, indent=2) + "\n")
    print(json.dumps({"S1": s1["pooled"], "S2": s2["pooled"]}, indent=2))
    print(f"wrote {outdir}/s1.json and {outdir}/s2.json  ({wall / 60:.1f} min)")


if __name__ == "__main__":
    main()
