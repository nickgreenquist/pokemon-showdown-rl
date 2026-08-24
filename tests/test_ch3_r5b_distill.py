"""CH3 R5b BI-2 (the distiller) — offline gates. No server, no battles.

Pinned here, per pre-reg Q5/D-0/D-5 (configs/eval/ch3_r5b_exit.yaml):

* the battle-disjoint split rule reproduces the pre-reg's sha construction
  exactly (h==0 SEL, h==1 GATE, else FIT) and is deterministic;
* targets: 'hard' is one-hot on search/chosen; numeric tau is softmax over
  the FINITE row_ev entries only, with EXACT zero mass on unscored rows
  (masked CE to an out-of-support target was the r1 placebo's degenerate
  case — the treatment must never have one);
* softmax_tau really sharpens: lower tau concentrates mass on the argmax;
* F-R recompute: build_targets(tau) matches an independent softmax to 1e-9;
* the selection rule picks the SMALLEST tau within 1 se of the grid best,
  with 'hard' ordered smallest;
* critic_digest changes when any tensor changes by one ULP, and is
  insensitive to dict insertion order.
"""

import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import ch3_r5b_distill as distill  # noqa: E402


def test_split_rule_matches_prereg_construction():
    import hashlib
    for lane in ("s62", "s65"):
        for b in (0, 1, 7, 100, 3099):
            h = int(hashlib.sha256(f"{lane}:{b}".encode()).hexdigest()[:8], 16) % 20
            want = "SEL" if h == 0 else ("GATE" if h == 1 else "FIT")
            assert distill.split_of(lane, b) == want


def test_hard_targets_one_hot_on_chosen():
    ev = np.array([[0.1, np.nan, 0.9], [0.5, 0.2, np.nan]], dtype=np.float32)
    chosen = np.array([2, 0])
    t = distill.build_targets(ev, chosen, "hard").numpy()
    assert t.tolist() == [[0, 0, 1], [1, 0, 0]]


def test_soft_targets_zero_mass_off_support_and_recompute():
    ev = np.array([[0.3, np.nan, -0.1, 0.7]], dtype=np.float32)
    chosen = np.array([3])
    t64 = distill.build_targets_f64(ev, chosen, "0.25")[0]
    t32 = distill.build_targets(ev, chosen, "0.25").numpy()[0]
    assert t64[1] == 0.0 and t32[1] == 0.0
    # the reference starts from the SAME float32-rounded EVs the npz stores
    # (F-R's real recompute reads stored float32 row_ev too)
    z = ev[0, [0, 2, 3]].astype(np.float64) / 0.25
    e = np.exp(z - z.max())
    ref = e / e.sum()
    # F-R's 1e-9 bar holds on the float64 intermediate; the float32
    # training cast agrees to float32 eps.
    assert abs(t64[0] - ref[0]) < 1e-9 and abs(t64[2] - ref[1]) < 1e-9 \
        and abs(t64[3] - ref[2]) < 1e-9
    assert np.allclose(t32[[0, 2, 3]], ref, atol=1e-6)
    assert abs(t32.sum() - 1.0) < 1e-6


def test_lower_tau_sharpens():
    ev = np.array([[0.3, 0.1, 0.7, np.nan]], dtype=np.float32)
    chosen = np.array([2])
    peak = {tau: distill.build_targets(ev, chosen, tau).numpy()[0, 2]
            for tau in ("0.05", "0.10", "0.25", "0.50")}
    assert peak["0.05"] > peak["0.10"] > peak["0.25"] > peak["0.50"]
    hard = distill.build_targets(ev, chosen, "hard").numpy()[0, 2]
    assert hard == 1.0 >= peak["0.05"]


def _grid(**ce):
    return {t: {"sel_ce": c, "sel_ce_se": s} for t, (c, s) in ce.items()}


def test_select_tau_smallest_within_one_se():
    g = _grid(hard=(1.30, 0.01), **{"0.05": (1.21, 0.01), "0.10": (1.20, 0.01),
                                    "0.25": (1.28, 0.01), "0.50": (1.40, 0.01)})
    best, chosen = distill.select_tau(g)
    assert best == "0.10" and chosen == "0.05"  # 1.21 <= 1.20 + 0.01
    g = _grid(hard=(1.10, 0.02), **{"0.05": (1.30, 0.01), "0.10": (1.20, 0.01),
                                    "0.25": (1.25, 0.01), "0.50": (1.40, 0.01)})
    best, chosen = distill.select_tau(g)
    assert best == "hard" and chosen == "hard"


def test_critic_digest_sensitive_and_order_free():
    sd = {"a.weight": torch.ones(3, 3), "b.bias": torch.zeros(2)}
    d1 = distill.critic_digest(sd)
    reordered = {"b.bias": sd["b.bias"], "a.weight": sd["a.weight"]}
    assert distill.critic_digest(reordered) == d1
    bumped = {k: v.clone() for k, v in sd.items()}
    bumped["a.weight"][0, 0] = torch.nextafter(
        torch.tensor(1.0), torch.tensor(2.0))
    assert distill.critic_digest(bumped) != d1
