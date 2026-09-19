"""The antisymmetry test has to be decisive, so its arithmetic is pinned.

`scripts/critic_antisymmetry.py` separates the two causes RESULTS §27.1 could
not: a critic perspective bias, or the determinization sampler. It works because
gen 1 is ZERO-SUM, so V(s) + V(swap(s)) must be 0 for a calibrated critic, and
both terms come from the same determinization and the same encoder -- no outcome
and no sampler enter.

Two things could make it say the wrong thing: an se that treats the `dets`
evaluations of one position as independent (they are not, and it would shrink
the se by ~2x), and a `_swap` that is not actually an involution.
"""
import math

import numpy as np
import pytest


def _clustered(by_ep):
    """The estimator the script uses, lifted so it can be tested directly."""
    clustered = np.array([np.mean(v) for v in by_ep.values()])
    mean = float(clustered.mean())
    se = float(clustered.std(ddof=1) / math.sqrt(clustered.size))
    return mean, se


def test_the_se_clusters_by_position_not_by_evaluation():
    """4 determinizations of one position are one draw, not four. Pooling them
    as independent is the SEEDS-DO-NOT-PAIR-BATTLES mistake in a new place."""
    rng = np.random.default_rng(0)
    # 50 positions, each with a true offset; 4 near-identical dets each
    by_ep = {}
    flat = []
    for e in range(50):
        base = rng.normal(0.2, 0.5)
        vals = [base + rng.normal(0, 0.01) for _ in range(4)]
        by_ep[e] = vals
        flat += vals
    _, se_clustered = _clustered(by_ep)
    se_naive = float(np.std(flat, ddof=1) / math.sqrt(len(flat)))
    assert se_clustered > 1.5 * se_naive, (
        f"clustered se {se_clustered:.4f} is not meaningfully larger than the "
        f"naive {se_naive:.4f} -- the clustering is not doing anything")


def test_a_perfectly_antisymmetric_critic_reads_zero():
    """The null: a calibrated critic in a zero-sum game sums to 0."""
    by_ep = {e: [0.0, 0.0, 0.0, 0.0] for e in range(30)}
    mean, se = _clustered(by_ep)
    assert mean == pytest.approx(0.0)


def test_a_seat_biased_critic_reads_TWICE_the_per_side_bias():
    """The alternative, and the arithmetic that makes the readout interpretable:
    if the critic adds +b to whichever side it is looking at, then
    V(s) + V(swap(s)) = 2b, so the per-side bias is HALF the measured sum."""
    b = 0.0416
    by_ep = {e: [2 * b] * 4 for e in range(30)}
    mean, _ = _clustered(by_ep)
    assert mean / 2 == pytest.approx(b)


def test_swap_is_an_involution_on_a_real_engine_state():
    """If `_swap` is not faithful, V(swap(s)) is the value of some OTHER
    position and the whole test measures nothing."""
    import importlib.util
    from pathlib import Path

    import numpy as np
    from rl.search.bridge import BridgeCounters, battle_to_state
    from rl.search.determinize import sample_determinization
    from tests.test_ch3_matrix import _two_mon_battle

    spec = importlib.util.spec_from_file_location(
        "outcome_variance", Path(__file__).parent.parent / "scripts/outcome_variance.py")
    ov = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ov)

    b = _two_mon_battle()
    st = battle_to_state(b, sample_determinization(b, np.random.default_rng(3)),
                         BridgeCounters())
    back = ov._swap(ov._swap(st))
    assert [m.hp for m in back.side_one.pokemon] == [m.hp for m in st.side_one.pokemon]
    assert [m.hp for m in back.side_two.pokemon] == [m.hp for m in st.side_two.pokemon]
    assert back.side_one.active_index == st.side_one.active_index


def test_the_script_states_what_it_cannot_say():
    """It measures SELF-CONSISTENCY, not accuracy: a critic can be perfectly
    antisymmetric and badly wrong. If that caveat ever leaves the file, the
    result will be read as a verdict on the critic's quality."""
    from pathlib import Path
    src = (Path(__file__).parent.parent / "scripts/critic_antisymmetry.py").read_text()
    assert "SELF-CONSISTENCY, never accuracy" in src or "not its accuracy" in src
    assert "88%" in src, "the ranking gap it does NOT touch must stay named"
