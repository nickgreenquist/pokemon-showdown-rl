"""D25 §6 manipulation check: did the aux head actually learn?

    python scripts/d25_manipulation.py

Per treatment lane, on THAT LANE'S OWN tape (results/d25/oppact_s{52..56}.npz,
mirror self-play of its 12M final — §6: own distribution, NOT the frozen
reference tape): the head's held-out NLL per non-aliased labelled opponent
decision, reported as GAP CLOSURE

    g = (A1 - NLL_head) / (A1 - A3)

with A1 (mask-renormalised class marginal, fit on the train split) and A3
(oracle floor: mean entropy of the label generator's own pushed-forward
distribution) RE-DERIVED here from the lane's own tape, per split; mean over
the same 8 battle-level 70/30 splits as §5. The head is not fitted to the
tape — every row is held out — the splits exist so A1 is honestly
out-of-sample and g is unit-compatible with the frozen-probe g that set the
bar.

PARTITION (one statistic, the 5-lane MEDIAN g, §6):
    LEARNED  median g >= 0.3286   (R0-13(b)'s re-derived bar)
    WEAK     0.10 <= median g < 0.3286
    VOID     median g < 0.10

g > 1.0 IS A HARD FAIL HERE, with no pool-mixture escape: these are MIRROR
tapes, so the oracle evaluated IS the actor that generated every label —
beating it means the label or the timing is wrong.

Also reads the head at the 3M and 6M checkpoints on the same tape (labels
and A1/A3 unchanged) so the trajectory is visible; only 12M bears the letter.
"""

import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from d25_gates import NSPL, build, marginal, nll, split_by_battle  # noqa: E402
from eval_checkpoint import _load_showdown_agent  # noqa: E402
from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402

LANES = (52, 53, 54, 55, 56)
STEPS = (3_000_000, 6_000_000, 12_000_000)
BAR = 0.3286          # R0-13(b): 0.80 x L6 mean frozen-probe g 0.4108
from rl.common.masking import masked_logits  # B4 2026-08-29: the harness sentinel, not a hand-rolled copy


def head_nll_rows(agent, obs1, y6, m6):
    """Per-row head NLL: actor features -> aux head -> m6-masked CE."""
    with torch.no_grad():
        _, ctx, opp_moves, bench = agent.actor(
            torch.as_tensor(obs1, dtype=torch.float32), return_features=True)
        lg = agent.aux_head(ctx, opp_moves, bench)
        lg = masked_logits(lg, torch.as_tensor(m6))
        return torch.nn.functional.cross_entropy(
            lg, torch.as_tensor(y6), reduction="none").numpy()


def main() -> None:
    per_lane = {}
    detail = {}
    for s in LANES:
        tape = REPO / f"results/d25/oppact_s{s}.npz"
        final = REPO / f"runs/showdown_sp_actpred12m_s{s}/checkpoint.pt"
        D = build(tape, final)
        y6, m6, q6, battle, obs1 = D["y6"], D["m6"], D["q6"], D["battle"], D["obs1"]
        n = D["n"]

        rows_nll = {}
        for step in STEPS:
            if step == 12_000_000:
                agent = D["agent"]           # build already loaded the final
            else:
                ck = load_checkpoint(
                    REPO / f"runs/showdown_sp_actpred12m_s{s}/ckpt_{step:09d}.pt")
                agent = _load_showdown_agent(ck, Config(**ck["config"]))
            rows_nll[step] = head_nll_rows(agent, obs1, y6, m6)

        ent_q6 = -(q6 * np.log(q6)).sum(1)
        g = {step: [] for step in STEPS}
        a1s, a3s, nh = [], [], []
        for sp in range(NSPL):
            tr, te = split_by_battle(battle, sp)
            A1 = nll(marginal(y6, m6, 6, tr), y6, te)
            A3 = float(ent_q6[te].mean())
            a1s.append(A1); a3s.append(A3)
            for step in STEPS:
                NLLh = float(rows_nll[step][te].mean())
                g[step].append((A1 - NLLh) / (A1 - A3))
                if step == 12_000_000:
                    nh.append(NLLh)
        gm = {step: float(np.mean(g[step])) for step in STEPS}
        per_lane[s] = gm[12_000_000]
        detail[f"s{s}"] = dict(
            n=n, keep=D["keep"], g_by_step={str(k): v for k, v in gm.items()},
            g12_split_sd=float(np.std(g[12_000_000], ddof=1)),
            A1=float(np.mean(a1s)), A3=float(np.mean(a3s)),
            NLL_head=float(np.mean(nh)))
        print(f"s{s}: n={n} (kept {D['keep']*100:.1f}%)  A1 {np.mean(a1s):.4f}  "
              f"A3 {np.mean(a3s):.4f}  NLL_head {np.mean(nh):.4f}  "
              f"g@3M/6M/12M {gm[3_000_000]:+.4f}/{gm[6_000_000]:+.4f}/"
              f"{gm[12_000_000]:+.4f}", flush=True)
        if gm[12_000_000] > 1.0:
            raise SystemExit(
                f"HARD FAIL: s{s} g = {gm[12_000_000]:.4f} > 1.0 on a MIRROR "
                "tape (oracle == generator) — label or timing is wrong.")

    med = float(np.median(list(per_lane.values())))
    verdict = ("LEARNED" if med >= BAR
               else "WEAK" if med >= 0.10 else "VOID")
    print(f"\n5-lane MEDIAN g = {med:.4f} vs LEARNED bar {BAR} -> **{verdict}**")
    print("consistency (recorded secondary): "
          f"{sum(v >= BAR for v in per_lane.values())}/5 lanes >= bar")
    with open(REPO / "results/d25/manipulation.json", "w") as f:
        json.dump(dict(per_lane={str(k): v for k, v in per_lane.items()},
                       median=med, bar=BAR, verdict=verdict, detail=detail),
                  f, indent=1)
    print("wrote results/d25/manipulation.json")


if __name__ == "__main__":
    main()
