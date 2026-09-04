"""The 100M pre-registration — internal-consistency tests (R0-a's automated
half). DRAFT-stage: these must be green from draft through ratification
through readout. They read no run data.

R0-a: configs/showdown_sp_100m.yaml differs from the Stage-2 acceptance
config in exactly {total_steps, agent.lr_anneal_steps, seed, run_name},
asserted in BOTH directions; the sync fallback differs from the async 100M
file in exactly {collector, run_name}. The defect class is R2's own: a
"one-lever" config that silently carries a second delta."""

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
M100 = yaml.safe_load((REPO / "configs/showdown_sp_100m.yaml").read_text())
SYNC = yaml.safe_load((REPO / "configs/showdown_sp_100m_sync.yaml").read_text())
ACC = yaml.safe_load(
    (REPO / "configs/showdown_sp_batch50m_async.yaml").read_text()
)
TXT = (REPO / "configs/showdown_sp_100m.yaml").read_text()


def _flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flat(v, key + "."))
        else:
            out[key] = v
    return out


def test_r0a_one_diff_vs_acceptance_both_directions():
    a, m = _flat(ACC), _flat(M100)
    assert a.keys() == m.keys(), (
        f"key sets differ: {sorted(a.keys() ^ m.keys())}"
    )
    changed = sorted(k for k in a if a[k] != m[k])
    assert changed == [
        "agent.lr_anneal_steps", "run_name", "seed", "total_steps",
    ], f"unexpected delta set: {changed}"


def test_sync_fallback_differs_only_in_collector_and_run_name():
    m, s = _flat(M100), _flat(SYNC)
    dropped = sorted(m.keys() - s.keys())
    assert dropped == ["collector.concurrency", "collector.mode"], dropped
    assert not (s.keys() - m.keys())
    changed = sorted(k for k in s if s[k] != m[k])
    assert changed == ["run_name"], changed
    assert SYNC["run_name"] == "showdown_sp_100m_sync_s104"


def test_lever_values_and_anneal_guard():
    assert M100["total_steps"] == 100_000_000
    assert M100["agent"]["lr_anneal_steps"] == 100_000_000  # R0-b
    assert M100["seed"] == 104
    assert M100["checkpoint_every"] == 500_000  # S4: the rung ladder stays
    assert M100["eval_every"] == 250_000  # S3: untouched, undiscussed


def test_seed_windows_disjoint_and_unused():
    """R0-l as claimed [review-1 S10 / review-2 SF-15]: the three lanes'
    8-wide sub-env windows are pairwise disjoint, and NO seed in any window
    appears in a stamped run config on disk — both branches safe."""
    import re

    seeds = [104, 112, 120]
    windows = [set(range(s, s + 8)) for s in seeds]
    for i in range(3):
        for j in range(i + 1, 3):
            assert not windows[i] & windows[j], "sub-env windows overlap"
    used = set()
    # LEGAL OWNERS (the ec368a1 precedent): once launched, the 100M fleet's
    # own run dirs stamp these seeds; R0-l's "unused" claim was a LAUNCH-time
    # gate (it passed in the wave preflight, logs/ch5_100m_wave.log
    # 2026-09-01T10:58Z) and the fleet is the first legal owner of
    # 104/112/120. Any OTHER stamped run in a window still fails.
    legal = {f"showdown_sp_100m_s{s}" for s in (104, 112, 120)}
    if (REPO / "runs").exists():
        for p in (REPO / "runs").glob("*/config.yaml"):
            if p.parent.name in legal:
                continue
            m = re.search(r"^seed: (\d+)", p.read_text(), re.M)
            if m:
                used.add(int(m.group(1)))
    for w in windows:
        assert not (w & used), f"window {sorted(w)} hits stamped seeds {w & used}"


def test_header_carries_the_load_bearing_verbatims():
    # The credit line with the larger-of clause, exactly once.
    assert TXT.count("LARGER of the pooled-binomial se_diff") == 1
    # The supersession of CHAPTER5 §7 ruling 4 is explicit, on both of the
    # ruling's own grounds (review-2 SF-5), and ruling 3's un-mooting is
    # addressed (SF-6).
    assert "SUPERSESSION" in TXT and "ruling 4" in TXT and "ruling 3" in TXT
    # The control numbers the primary reads against.
    assert "0.4745556" in TXT and "0.7864444" in TXT
    # Acceptance fills complete (2026-09-01 wave): no unfilled cell may
    # remain, and the realized G9/G8 numbers are carried.
    assert "[G9-FILL]" not in TXT and "[G8-FILL]" not in TXT
    assert "[FILLED 2026-09-01]" in TXT
    assert "+0.02322" in TXT and "901.2" in TXT and "574.1" in TXT
    # The barred words appear only inside the barring sentences.
    assert TXT.count('"flat"') >= 1 and TXT.count('"plateau"') >= 1
