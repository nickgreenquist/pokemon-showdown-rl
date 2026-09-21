"""Gates for the R7 screen's readout instrument (scripts/arch_screen_readout.py).

THE BOOTSTRAP IS THE PRIMARY READ. An untested interval is the same class of
hazard as an unlogged counter: it produces a number on every run, so nothing
looks wrong, and the number can be silently the wrong width. Three things are
pinned here, each with the mistake it would catch:

1. IT CLUSTERS BY BATTLE, NOT BY ROW. Fed rows whose outcome is constant
   WITHIN a battle and varies BETWEEN battles, a by-battle bootstrap has to be
   MUCH wider than a by-row one — a by-row resample would treat the 25
   decisions of one battle as 25 independent draws. The test builds exactly
   that data and asserts the width ordering, so a refactor that resamples rows
   fails here instead of quietly halving every CI in the readout.
2. IT KEEPS THE PAIRING. One replicate must score BOTH arms on the SAME
   resampled battles. If B beats A by a constant on every single row, the
   paired delta is that constant with a ZERO-width interval; an unpaired
   bootstrap would put a spread on it. This is the 2026-09-17 failure shape in
   miniature (an unmatched comparison turning a null into a "result").
3. A BATTLE DRAWN TWICE COUNTS TWICE. An implementation that builds a boolean
   mask instead of gathering indices silently de-duplicates the resample,
   which collapses the interval toward zero. Detected by feeding a case whose
   replicate spread must be strictly positive.

And `_load`'s cross-check is exercised in both directions: it passes on a
consistent pair of files and RAISES on a row file that disagrees with the
metrics json it sits beside.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import arch_screen_readout as R  # noqa: E402

RNG = np.random.default_rng(7)


def _rows(battle_ids, agree, kl=None, free=None, reveal=None, epoch=3):
    n = len(battle_ids)
    return {
        "battle_ids": np.asarray(battle_ids, dtype=np.int64),
        "agree": np.asarray(agree, dtype=bool),
        "free": np.ones(n, dtype=bool) if free is None else np.asarray(free, dtype=bool),
        "kl": np.zeros(n, dtype=np.float32) if kl is None else np.asarray(kl, np.float32),
        "entropy": np.zeros(n, dtype=np.float32),
        "teacher_entropy": np.zeros(n, dtype=np.float32),
        "reveal": (np.zeros(n, dtype=np.int64) if reveal is None
                   else np.asarray(reveal, dtype=np.int64)),
        "action": np.zeros(n, dtype=np.int64),
        "n_legal": np.full(n, 4, dtype=np.int64),
        "epoch": np.int64(epoch),
    }


def _clustered(n_battles=200, per_battle=25, p=0.5, shift=0.0):
    """Outcome constant WITHIN a battle, Bernoulli BETWEEN battles. All the
    variance lives at the cluster level, which is the regime that separates a
    by-battle bootstrap from a by-row one."""
    bids = np.repeat(np.arange(n_battles), per_battle)
    won = RNG.random(n_battles) < (p + shift)
    return bids, np.repeat(won, per_battle)


def _ci(samples):
    lo, hi = np.percentile(samples, R.CI)
    return float(lo), float(hi)


def test_the_bootstrap_clusters_by_battle_not_by_row():
    bids, a = _clustered()
    _, b = _clustered()
    rows_a, rows_b = _rows(bids, a), _rows(bids, b)
    by_battle = R._bootstrap([(rows_a, rows_b)], n_boot=400, seed=1)["agreement_free"]

    # A by-ROW bootstrap on the same data, for the comparison only.
    rng = np.random.default_rng(1)
    by_row = []
    for _ in range(400):
        idx = rng.integers(0, len(bids), size=len(bids))
        by_row.append(float(rows_b["agree"][idx].mean() - rows_a["agree"][idx].mean()))
    by_row = np.asarray(by_row)

    w_battle = np.diff(_ci(by_battle))[0]
    w_row = np.diff(_ci(by_row))[0]
    # Each battle contributes 25 identical rows, so the row-level interval is
    # understated by roughly sqrt(25) = 5x. Assert a loose 3x to stay robust.
    assert w_battle > 3.0 * w_row, (w_battle, w_row)


def test_the_bootstrap_keeps_the_pairing():
    """One replicate must score BOTH arms on the SAME resampled battles.

    Built so the arms are strongly correlated (B is A plus a few extra
    agreements, row by row): the PAIRED interval then reflects only the
    variance of the DIFFERENCE and must be much narrower than one that
    resamples each arm independently. The point estimate is identical either
    way, which is exactly why this has to be tested on the WIDTH -- an
    unpaired implementation reports the same number with the wrong interval,
    and that is the 2026-09-17 failure shape.
    """
    # `a` varies a lot between battles (p = 0.5); `b` is `a` with one fixed
    # tenth of the battles forced to agree. Both arms therefore have large
    # between-battle variance while their DIFFERENCE has little -- which is
    # the situation a paired interval exists for, and the situation two
    # independent resamples get wrong.
    bids, a = _clustered(n_battles=150, per_battle=20, p=0.5)
    b = a.copy()
    b[np.isin(bids, np.arange(15))] = True
    rows_a, rows_b = _rows(bids, a), _rows(bids, b)
    paired = R._bootstrap([(rows_a, rows_b)], n_boot=400, seed=2)["agreement_free"]

    # The unpaired counterfactual: resample each arm's battles separately.
    rng = np.random.default_rng(2)
    groups = [np.flatnonzero(bids == g) for g in np.unique(bids)]
    unpaired = []
    for _ in range(400):
        ia = np.concatenate([groups[p] for p in rng.integers(0, len(groups), len(groups))])
        ib = np.concatenate([groups[p] for p in rng.integers(0, len(groups), len(groups))])
        unpaired.append(float(rows_b["agree"][ib].mean() - rows_a["agree"][ia].mean()))
    unpaired = np.asarray(unpaired)

    point = float(b.mean() - a.mean())
    lo, hi = _ci(paired)
    assert lo > 0.0 and lo <= point <= hi, (lo, point, hi)
    assert np.diff(_ci(paired))[0] < 0.5 * np.diff(_ci(unpaired))[0], (
        _ci(paired), _ci(unpaired))


def test_a_battle_drawn_twice_counts_twice():
    """A resample built as a boolean MASK would de-duplicate repeated draws and
    collapse the spread. Under a real gather the replicate spread is strictly
    positive, and the replicate mean is centred on the point estimate."""
    bids, a = _clustered(n_battles=120, per_battle=10, p=0.45)
    _, b = _clustered(n_battles=120, per_battle=10, p=0.55)
    boot = R._bootstrap([(_rows(bids, a), _rows(bids, b))], n_boot=500, seed=3)["agreement_free"]
    assert boot.std() > 1e-3, boot.std()
    point = float(b.mean() - a.mean())
    assert abs(boot.mean() - point) < 0.05, (boot.mean(), point)
    assert len(np.unique(boot)) > 50  # not a degenerate constant


def test_three_seeds_are_averaged_not_pooled():
    """The aggregator is the MEAN of three per-seed paired deltas. With three
    seeds of very different sizes a pooled-rows difference would be dominated
    by the largest; the mean is not."""
    per_seed = []
    deltas = []
    for n_b, shift in ((400, 0.00), (40, 0.30), (40, -0.30)):
        bids, a = _clustered(n_battles=n_b, per_battle=10, p=0.5)
        b = a.copy()
        flip = RNG.random(len(a)) < abs(shift)
        b = (a | flip) if shift > 0 else (a & ~flip)
        per_seed.append((_rows(bids, a), _rows(bids, b)))
        deltas.append(float(b.mean() - a.mean()))
    boot = R._bootstrap(per_seed, n_boot=300, seed=4)["agreement_free"]
    assert abs(float(boot.mean()) - float(np.mean(deltas))) < 0.02, (boot.mean(), deltas)


def _write_pair(tmp_path: Path, name: str, rows: dict, best: float, epoch: int,
                val_kl: float = 0.0, fitted_entropy: float = 0.0):
    hist = [{"epoch": e, "agreement_free": (best if e == epoch else best - 0.1),
             "val_kl": val_kl, "fitted_entropy": fitted_entropy,
             "teacher_entropy": 1.0, "agreement": best}
            for e in range(1, epoch + 2)]
    (tmp_path / f"{name}.json").write_text(json.dumps({
        "run_name": name, "history": hist, "best_epoch": epoch,
        "best_agreement_free": best, "actor_params": 1,
    }))
    np.savez_compressed(tmp_path / f"{name}_val_rows.npz", **rows)


def test_load_cross_checks_the_saved_rows_against_the_fits_own_means(tmp_path):
    bids = np.repeat(np.arange(10), 4)
    agree = np.zeros(40, dtype=bool)
    agree[:22] = True                      # agreement_free = 0.55
    rows = _rows(bids, agree, kl=np.full(40, 0.25, np.float32), epoch=3)
    _write_pair(tmp_path, "ok", rows, best=0.55, epoch=3, val_kl=0.25)
    name, rep, got, epoch, row = R._load(tmp_path, 0, "ok")
    assert name == "ok" and epoch == 3 and row["agreement_free"] == 0.55

    # A row file that disagrees with the json it sits beside must RAISE.
    _write_pair(tmp_path, "bad", rows, best=0.61, epoch=3, val_kl=0.25)
    with pytest.raises(AssertionError):
        R._load(tmp_path, 0, "bad")
    # ... and so must one that agrees on agreement and disagrees on KL.
    _write_pair(tmp_path, "badkl", rows, best=0.55, epoch=3, val_kl=0.99)
    with pytest.raises(AssertionError):
        R._load(tmp_path, 0, "badkl")


def test_the_rule_constants_match_the_committed_prereg():
    """The readout restates the rule rather than reading it, so the two CAN
    drift. This test is the thing that notices."""
    cfg = (Path(__file__).resolve().parents[1] / "configs" / "bc_arch_screen.yaml").read_text()
    assert "delta_agreement_free_min: 0.02" in cfg
    assert "max_throughput_ratio_vs_entity_deepsets: 3.0" in cfg
    assert "ci_must_exclude_zero: true" in cfg
    assert R.GATE_DELTA == 0.02 and R.GATE_THROUGHPUT == 3.0
    assert R.SEEDS == (0, 1, 2) and "seeds: [0, 1, 2]" in cfg
    assert R.N_BOOT == 1000 and "1000 resamples" in cfg
    for _, tpl in R.ARMS.values():
        assert tpl.replace("{seed}", "{seed}") in cfg
