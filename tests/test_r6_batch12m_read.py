"""scripts/r6_batch12m_read.py: the 4.12 screen's mechanical GO / FALLBACK rule on synthetic
per-bin tables, and the chunked history loader on a small CSV with eval rows mixed in."""
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from r6_batch12m_read import BIN, load_bins, rule  # noqa: E402

H = 12_000_000


def _table(kl, ent, ev, upd=5.0, col=20.0):
    bins = list(range(H // BIN))
    return pd.DataFrame({"loss/approx_kl": kl, "loss/clip_frac": [0.2] * 12, "loss/entropy": ent,
                         "loss/explained_variance": ev, "loss/adv_std": [1.0] * 12,
                         "time/update_sec": [upd] * 12, "time/collect_sec": [col] * 12,
                         "n_updates": [100] * 12}, index=bins)


def test_go_when_all_three_hold_and_fallback_on_each_failure():
    w = {f"w{i}": _table([0.03] * 12, np.linspace(1.6, 1.2, 12), np.linspace(0.1, 0.5, 12)) for i in range(3)}
    good = _table([0.5] + [0.02] * 11, np.linspace(1.7, 1.1, 12), np.linspace(0.1, 0.48, 12))
    r = rule({"s204": good, "s212": good}, w, H)
    assert r["verdict"] == "GO" and all(c["ok"] for c in r["checks"].values())
    assert r["checks"]["a_kl_in_band"]["per_lane"]["s204"]["bins_outside"] == [], "bin 0 is excluded"
    collapsed = _table([0.02] * 6 + [0.0005] * 6, np.linspace(1.7, 1.1, 12), np.linspace(0.1, 0.48, 12))
    r = rule({"s204": good, "s212": collapsed}, w, H)
    assert r["verdict"] == "FALLBACK" and not r["checks"]["a_kl_in_band"]["ok"]
    assert r["checks"]["a_kl_in_band"]["per_lane"]["s212"]["bins_outside"] == list(range(6, 12))
    rising = _table([0.02] * 12, np.linspace(1.1, 1.7, 12), np.linspace(0.1, 0.48, 12))
    r = rule({"s204": good, "s212": rising}, w, H)
    assert r["verdict"] == "FALLBACK" and not r["checks"]["b_entropy_falling"]["ok"]
    collapsed_ent = _table([0.02] * 12, np.linspace(1.7, 0.3, 12), np.linspace(0.1, 0.48, 12))
    r = rule({"s204": good, "s212": collapsed_ent}, w, H)
    assert not r["checks"]["b_entropy_falling"]["ok"], "0.3 vs the W lanes' 1.2 is a collapse"
    plateau = _table([0.02] * 12, [1.7] + [1.25] * 5 + [1.27] * 6, np.linspace(0.1, 0.48, 12))
    r = rule({"s204": good, "s212": plateau}, w, H)
    assert r["checks"]["b_entropy_falling"]["ok"], "a plateau near the W lanes is not a failure"
    low_ev = _table([0.02] * 12, np.linspace(1.7, 1.1, 12), np.linspace(0.1, 0.40, 12))
    r = rule({"s204": low_ev, "s212": low_ev}, w, H)
    assert r["verdict"] == "FALLBACK" and not r["checks"]["c_ev_within_tol"]["ok"]
    assert abs(r["checks"]["c_ev_within_tol"]["w_last_bin_ev"] - 0.5) < 1e-9


def test_load_bins_drops_eval_rows_cuts_at_horizon_and_medians_kl(tmp_path):
    rows = []
    for step in range(0, 3_000_000 + 1, 50_000):
        rows.append({"_step": step, "loss/approx_kl": 0.01 if (step // 50_000) % 2 else 0.05,
                     "loss/clip_frac": 0.2, "loss/entropy": 1.5, "loss/explained_variance": 0.3,
                     "loss/adv_std": 1.0, "time/update_sec": 4.0, "time/collect_sec": 10.0, "eval/win_rate": np.nan})
        rows.append({"_step": step + 1, "loss/approx_kl": np.nan, "eval/win_rate": 0.7})  # an eval row
    p = tmp_path / "history.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    t = load_bins(str(p), horizon=2_000_000, chunksize=7)   # many tiny chunks: the stop is on the RAW max
    assert list(t.index) == [0, 1], "only the two bins below the 2M horizon"
    assert t.loc[0, "n_updates"] == 20 and abs(t.loc[0, "loss/approx_kl"] - 0.03) < 1e-9
    assert abs(t.loc[1, "loss/entropy"] - 1.5) < 1e-9 and abs(t.loc[1, "time/update_sec"] - 4.0) < 1e-9
