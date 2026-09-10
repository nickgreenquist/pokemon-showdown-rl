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

--det-blind (2026-09-10, docs/search_relook/DET_BLIND.md) RE-RUNS S1 ONLY,
on the same 800 decisions, with the information-boundary leaf encoding on:

  * the S1 root encode passes the ROOT battle's `PublicView`, so the
    determinizer's unrevealed bench and invented movesets are encoded as
    UNKNOWN exactly where the live encoder leaves them unknown;
  * the primary search arm is `SearchAgent(..., leaf_encoding="det_blind")`
    at Dose M, and the comparator arm is the SAME Dose M AS-IS. Both key
    the same `decision_rng`, so they draw the identical four
    determinizations and differ ONLY in how a leaf is encoded — the flip
    rate between them is therefore the artefact's decision footprint, with
    nothing else moving.
  * output goes to <out>/s1_det_blind.json and NO s2 file is written: S2's
    read rule is about BUDGET (Dose L vs Dose M) and there is no Dose L in
    this mode, so `s2.json` keeps its pre-registered meaning untouched.
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
from rl.search.shadow_battle import public_view, shadow_battle
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


def screen_lane(
    prereg: dict, lane: str, n: int, harvest_dir: Path, det_blind: bool = False
) -> tuple[list[dict], dict]:
    agent, cfg = _load_agent(prereg["checkpoints"][lane])
    if det_blind:
        # arm "m" = the det_blind primary; arm "l" = the AS-IS comparator at
        # the SAME dose. Same decision_rng key -> identical determinizations.
        search_m = SearchAgent(agent, DOSES["M"], checkpoint_seed=cfg.seed,
                               leaf_encoding="det_blind")
        search_l = SearchAgent(agent, DOSES["M"], checkpoint_seed=cfg.seed)
    else:
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
        view = public_view(battle) if det_blind else None
        try:
            dets = [sample_determinization(battle, rng) for _ in range(n_det_s1)]
            for det in dets:
                state = battle_to_state(battle, det, BridgeCounters())
                sb = shadow_battle(state, turn=int(battle.turn), view=view)
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

def _s1_stats(rows: list[dict], arm: str = "m") -> dict:
    """Pooled S1 read. `usable` = a decision with 4 det deltas AND a defined
    margin on `arm` (>= 2 legal rows, no watchdog trip, not a placeholder).
    `arm` is "m" everywhere except the --det-blind re-run's secondary read,
    which prices the same Deltas against the AS-IS arm's margins."""
    mk, sk = f"margin_{arm}", f"row_ev_sd_{arm}"
    usable = [r for r in rows if r["deltas"] and r[mk] is not None]
    if not usable:
        return {"n_decisions": len(rows), "n_usable": 0}
    all_deltas = np.array([d for r in usable for d in r["deltas"]], dtype=np.float64)
    mean_delta = np.array([float(np.mean(r["deltas"])) for r in usable])
    sd_delta = np.array([float(np.std(r["deltas"], ddof=1)) for r in usable])
    margins = np.array([float(r[mk]) for r in usable])
    ev_sd = np.array([float(r[sk]) for r in usable])
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


def _det_blind_flips(rows: list[dict]) -> dict:
    """The --det-blind flip block, arms named. `_s2_stats`' arithmetic is
    reused unchanged; only the labels differ, because in this mode "m" is
    det_blind@M and "l" is as-is@M on the IDENTICAL determinizations. The
    S2 budget bound is not reported: there is no Dose L here."""
    s = _s2_stats(rows)
    if not s.get("n_usable"):
        return s
    ren = {
        "flip_rate_L_vs_M": "flip_rate_det_blind_vs_as_is",
        "n_flips_L_vs_M": "n_flips_det_blind_vs_as_is",
        "flip_rate_M_vs_greedy": "flip_rate_det_blind_vs_greedy",
        "flip_rate_L_vs_greedy": "flip_rate_as_is_vs_greedy",
        "mean_margin_M_at_L_vs_M_flips": "mean_margin_det_blind_at_flips",
        "median_margin_M_at_L_vs_M_flips": "median_margin_det_blind_at_flips",
        "mean_margin_M_at_non_flips": "mean_margin_det_blind_at_non_flips",
        "median_margin_M_at_non_flips": "median_margin_det_blind_at_non_flips",
        "n_watchdog_m": "n_watchdog_det_blind",
        "n_watchdog_l": "n_watchdog_as_is",
        "ms_per_decision_M": "ms_per_decision_det_blind",
        "ms_per_decision_L": "ms_per_decision_as_is",
        "leaves_per_decision_M": "leaves_per_decision_det_blind",
        "leaves_per_decision_L": "leaves_per_decision_as_is",
    }
    drop = ("S2_LOW_FLIP_BOUND_HOLDS", "decisions_touched_per_battle_prestated_38")
    out = {"arm_primary": "det_blind@M", "arm_comparator": "as_is@M"}
    out.update({ren.get(k, k): v for k, v in s.items() if k not in drop})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", default="configs/eval/ch3_rung2.yaml")
    ap.add_argument("--harvest", default="results/ch3_r1")
    ap.add_argument("--per-lane", type=int, default=200)
    ap.add_argument("--out", default="results/search_s1_s2")
    ap.add_argument("--torch-threads", type=int, default=2)
    ap.add_argument("--lanes", default="", help="comma list; default all in the prereg")
    ap.add_argument(
        "--det-blind", action="store_true",
        help="re-run S1 ONLY with the information-boundary leaf encoding "
             "(docs/search_relook/DET_BLIND.md); writes s1_det_blind.json",
    )
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
    arms = ("det_blind@M + as-is@M" if args.det_blind else "Dose M + Dose L")
    for lane in lanes:
        print(f"[{time.strftime('%H:%M:%S')}] screening {lane} "
              f"({args.per_lane} decisions, S1 + {arms})...", flush=True)
        lrows, meta = screen_lane(
            prereg, lane, args.per_lane, Path(args.harvest),
            det_blind=args.det_blind,
        )
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
        "leaf_encoding": "det_blind" if args.det_blind else "as_is",
        "arm_m": "det_blind@M" if args.det_blind else "as_is@M",
        "arm_l": "as_is@M" if args.det_blind else "as_is@L",
    }
    if args.det_blind:
        provenance["root_encoding"] = (
            "embed_battle(shadow_battle(battle_to_state(battle, det), "
            "turn=battle.turn, view=public_view(battle)), type_chart)"
        )
        provenance["root_encoding_note"] = (
            "the det_blind root: the determinizer's unrevealed bench and "
            "invented movesets are encoded as UNKNOWN, exactly as the live "
            "encoder leaves them. Declared residual families (measured, "
            "DET_BLIND.md): opponent HP quantisation, transformed-Ditto base "
            "stats/types and everything downstream of them, preparing, "
            "root trapped, the sleep/Rest counter split."
        )
        provenance["paired_note"] = (
            "arm_m and arm_l key the SAME decision_rng, so they expand the "
            "identical four determinizations and the same branches; the only "
            "difference between them is how a leaf is ENCODED"
        )

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
    if args.det_blind:
        s1["screen"] = (
            "S1 (det_blind re-run) — leaf-encoding bias vs decision margin, "
            "with the information-boundary leaf encoding on"
        )
        # the same Deltas priced against the AS-IS arm's margins, so the ratio
        # can be read against the original screen's denominator too
        s1["pooled_vs_as_is_margins"] = _s1_stats(rows, arm="l")
        s1["flips"] = _det_blind_flips(rows)
        s1["flips_per_lane"] = {
            ln: _det_blind_flips([r for r in rows if r["lane"] == ln])
            for ln in lanes
        }
        s1["decisions"] = [
            {k: v for k, v in r.items() if not k.startswith("err_l")} for r in rows
        ]
        out_path = outdir / "s1_det_blind.json"
        out_path.write_text(json.dumps(s1, indent=2) + "\n")
        print(json.dumps(
            {"S1_det_blind": s1["pooled"], "flips": s1["flips"]}, indent=2
        ))
        print(f"wrote {out_path}  ({wall / 60:.1f} min)")
        return

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
