#!/usr/bin/env python
"""Does recalibrating the leaf value change the ACTION, or only the fit?

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/calibration_action_diff.py --battles 200

IDEAS 2.13 is justified by **+0.0195 of explained variance** (RESULTS §27.1) --
and this project has measured three times that EV does not track strength: §21
(2.67x critic width bought ZERO EV while the win rate moved), §27.1 (88% of the
critic's gap is RANKING, which no rescaling touches) and §29 (EV moves the
OPPOSITE way to the win rate in 9 lanes of 9). **A lever justified by EV is a
lever justified by the one quantity measured not to matter.**

The row may still pay through a different channel: `row_ev` takes an
EXPECTATION over leaf values, so a monotone map reorders rows even though it
cannot reorder leaves at one node, and the D5 gate is a threshold on that same
scale. The claim is "the search picks a different action", not "the critic fits
better". **This measures that claim directly, and it is the thing to run before
an arm.**

WHY IT IS EXACT, NOT NOISY. Both selectors run on the SAME decision with the
SAME rng, so they draw the same determinizations, expand the same leaves and
differ ONLY in the value transform. There is no sampling error in the
comparison at all -- the action either changed or it did not.

IF THE ACTION ALMOST NEVER CHANGES, 2.13 IS INERT IN PRACTICE whatever its EV,
and it should close without a fleet-grade arm.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).parent))
REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoints", nargs="+", default=[
        "runs/showdown_monster200m_w_s104/ckpt_200000000.pt",
        "runs/showdown_monster200m_w_s112/ckpt_200000012.pt",
        "runs/showdown_monster200m_w_s120/ckpt_200000003.pt"])
    ap.add_argument("--rows", default="results/outcome_variance/variance.json.rows.jsonl",
                    help="the luck-ceiling run the calibration is fitted from")
    ap.add_argument("--battles", type=int, default=200)
    ap.add_argument("--dose", default="M")
    ap.add_argument("--margin", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=20260919)
    ap.add_argument("--out", default="results/outcome_variance/calib_action_diff.json")
    args = ap.parse_args()

    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    from poke_env.data import GenData

    from eval_checkpoint import _load_showdown_agent, _opponent_from_checkpoint
    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config
    from rl.common.evaluation import EVAL_SEED_OFFSET
    from rl.common.value_calibration import ValueCalibration
    from rl.envs.make import make_env
    from rl.envs.showdown import embed_battle
    from rl.envs.showdown import OBS_DIM  # noqa: F401  (import-time encoder pin)
    from rl.search.agent import SearchAgent
    from rl.search.matrix import DOSES

    cal = ValueCalibration.from_rows(args.rows)
    print(f"calibration: {len(cal.xs)} knots from {cal.fit_meta}", flush=True)

    members = []
    for p in args.checkpoints:
        c = load_checkpoint(p)
        members.append(_load_showdown_agent(c, Config(**c["config"])))
    from rl.search.ensemble_search import EnsembleSearchAdapter
    obj = EnsembleSearchAdapter(members) if len(members) > 1 else members[0]

    raw = SearchAgent(obj, DOSES[args.dose], checkpoint_seed=112,
                      margin_delta=args.margin)
    fit = SearchAgent(obj, DOSES[args.dose], checkpoint_seed=112,
                      margin_delta=args.margin, calibration=cal.to_dict())

    c0 = load_checkpoint(args.checkpoints[0])
    cfg0 = Config(**c0["config"])
    opponent, _ = _opponent_from_checkpoint(args.checkpoints[0], cfg0.seed)
    env = make_env(cfg0.env_id, cfg0.seed, env_kwargs={"opponent": opponent})
    from rl.search.ensemble import EnsembleAgent
    driver = EnsembleAgent(members) if len(members) > 1 else members[0]

    n = diff = both_override = 0
    only_raw = only_fit = 0
    changes: Counter = Counter()
    for ep in range(args.battles):
        obs, info = env.reset(seed=EVAL_SEED_OFFSET + 70000 + ep)
        mask = info.get("action_mask")
        done, step = False, 0
        while not done and step < 500:
            inner = getattr(getattr(env.unwrapped, "_env", None), "env", None)
            battle = getattr(inner, "battle1", None) if inner is not None else None
            if battle is not None and not battle.finished and int(np.sum(mask)) > 1:
                try:
                    a_raw, s_raw = raw.act(battle, obs, mask, ep, step)
                    a_fit, s_fit = fit.act(battle, obs, mask, ep, step)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except BaseException:
                    a_raw = a_fit = None
                if a_raw is not None:
                    n += 1
                    if a_raw != a_fit:
                        diff += 1
                        changes[(a_raw, a_fit)] += 1
                    orr = bool(s_raw.get("search/overrode"))
                    orf = bool(s_fit.get("search/overrode"))
                    both_override += int(orr and orf)
                    only_raw += int(orr and not orf)
                    only_fit += int(orf and not orr)
            obs, _, term, trunc, info = env.step(driver.act(obs, mask, deterministic=True))
            mask, done, step = info.get("action_mask"), term or trunc, step + 1
        if (ep + 1) % 25 == 0:
            print(f"  {ep + 1}/{args.battles} battles, {n} decisions, "
                  f"{diff} changed ({diff / max(n, 1):.2%})", flush=True)
    env.close()

    print("\n" + "=" * 78)
    print("DOES THE CALIBRATION CHANGE THE ACTION?  (IDEAS 2.13, RESULTS §27.1)")
    print("=" * 78)
    print(f"\n  decisions compared          {n}")
    print(f"  ACTION CHANGED              {diff}  ({diff / max(n, 1):.2%})")
    print(f"  search overrode under BOTH  {both_override}")
    print(f"  overrode only RAW           {only_raw}")
    print(f"  overrode only CALIBRATED    {only_fit}")
    print(f"  net change in override rate {(only_fit - only_raw) / max(n, 1):+.4f}")
    print(f"\n  calibration leaves touched  raw {raw.counters['calib/leaves']} "
          f"(must be 0), calibrated {fit.counters['calib/leaves']}")
    print(f"  mean |shift| per leaf       "
          f"{fit.counters['calib/shift_sum'] / max(fit.counters['calib/leaves'], 1):.4f}")
    print("\n  Both selectors ran on the SAME decisions with the SAME rng, so they")
    print("  drew the same determinizations and expanded the same leaves. There is")
    print("  no sampling error here: the action either changed or it did not.")
    print("\n  READ: if the action almost never changes, 2.13 is INERT IN PRACTICE")
    print("  whatever its explained variance, and it closes without an arm. If it")
    print("  changes often, note that it also MOVES THE OVERRIDE RATE -- so any")
    print("  win-rate arm must re-sweep margin_delta, matched on the realized rate.")
    print("=" * 78)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "decisions": n, "action_changed": diff,
        "action_changed_rate": diff / max(n, 1),
        "override_both": both_override, "override_only_raw": only_raw,
        "override_only_calibrated": only_fit,
        "calib_leaves": fit.counters["calib/leaves"],
        "calib_mean_shift": fit.counters["calib/shift_sum"] / max(fit.counters["calib/leaves"], 1),
        "dose": args.dose, "margin_delta": args.margin,
        "fit_meta": cal.fit_meta,
    }, indent=2) + "\n")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
