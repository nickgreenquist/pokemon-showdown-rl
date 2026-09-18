"""The anneal audit decides a maintainer ruling, so its windowing must be right.

RESULTS §29 reads the last quarter of training against the quarter before it,
across nine lanes, and concludes that the tail trades explained variance for win
rate. Two things could silently invert that: a window that slides off the data,
and a metric column that is mostly blank being averaged over the wrong rows.
"""
import importlib.util
from pathlib import Path

MOD = Path(__file__).parent.parent / "scripts/anneal_tail_audit.py"
spec = importlib.util.spec_from_file_location("anneal_tail_audit", MOD)
at = importlib.util.module_from_spec(spec)
spec.loader.exec_module(at)


def test_the_window_is_half_open_and_the_two_windows_do_not_overlap():
    pairs = [(s, float(s)) for s in range(100)]
    mid = at.window(pairs, 50, 75)
    tail = at.window(pairs, 75, 100)
    assert mid == [float(s) for s in range(50, 75)]
    assert tail == [float(s) for s in range(75, 100)]
    assert not (set(mid) & set(tail)), "the windows overlap; the delta is diluted"


def test_blank_and_nan_cells_are_skipped_not_read_as_zero():
    """wandb history is sparse -- most metrics are blank on most rows. Reading a
    blank as 0.0 would drag every mean toward zero and could flip a sign."""
    import csv
    import tempfile

    rows = [{"_step": "1", "loss/explained_variance": "0.7"},
            {"_step": "2", "loss/explained_variance": ""},
            {"_step": "3", "loss/explained_variance": "NaN"},
            {"_step": "4", "loss/explained_variance": "0.5"}]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "history.csv"
        with p.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["_step", "loss/explained_variance"])
            w.writeheader()
            w.writerows(rows)
        steps, series = at.read(p)
        assert steps == [1, 2, 3, 4]
        assert series["loss/explained_variance"] == [(1, 0.7), (4, 0.5)]


def test_every_metric_it_reports_is_a_locked_name():
    """CLAUDE.md locks the metric names and requires them logged from PPO's
    update. A typo here would silently report an empty series as 'too few
    points' rather than as a mistake."""
    locked = {"loss/explained_variance", "loss/entropy", "loss/approx_kl",
              "loss/value", "rollout/episode_return", "selfplay/winrate_latest",
              "eval/win_rate"}
    assert set(at.COLS) == locked


def test_the_selfplay_winrate_is_carried_because_it_is_the_instrument_check():
    """Self-play against the latest opponent is zero-sum, so it MUST sit at
    ~0.5 and move by ~0. §29 uses that as the check that the windows are being
    read correctly -- if this column ever leaves the report, the check goes."""
    assert "selfplay/winrate_latest" in at.COLS
