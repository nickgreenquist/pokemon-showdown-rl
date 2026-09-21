"""scripts/merge_history.py::history_path -- the merged-or-plain branch selection on a run dir,
with the extractor and the merger stubbed: a resumed run (several offline runs) reads
history_merged.csv (merging once if missing), an unresumed one reads history.csv (extracting
once if missing)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import merge_history as mh  # noqa: E402


def _wandb(run, n):
    for i in range(n):
        d = run / "wandb" / f"offline-run-2026090{i}_000000-x{i}"
        d.mkdir(parents=True)
        (d / f"run-x{i}.wandb").write_bytes(b"")


def test_branches(tmp_path, monkeypatch):
    calls = {"merge": 0, "extract": 0}
    monkeypatch.setattr(mh, "merge", lambda run: calls.__setitem__("merge", calls["merge"] + 1) or (run / "history_merged.csv").write_text("_step\n0\n"))
    monkeypatch.setattr(mh.subprocess, "run", lambda *a, **k: calls.__setitem__("extract", calls["extract"] + 1) or pathlib.Path(a[0][-1], "history.csv").write_text("_step\n0\n"))
    # unresumed, history present: no call
    r1 = tmp_path / "r1"; r1.mkdir(); (r1 / "history.csv").write_text("_step\n0\n")
    assert mh.history_path(r1).name == "history.csv" and calls == {"merge": 0, "extract": 0}
    # unresumed, history missing: one extraction
    r2 = tmp_path / "r2"; r2.mkdir(); _wandb(r2, 1)
    assert mh.history_path(r2).name == "history.csv" and calls["extract"] == 1
    # resumed (two offline runs), merged missing: one merge, never the extractor
    r3 = tmp_path / "r3"; r3.mkdir(); _wandb(r3, 2); (r3 / "history.csv").write_text("_step\n0\n")
    assert mh.history_path(r3).name == "history_merged.csv" and calls == {"merge": 1, "extract": 1}
    # resumed, merged present: no call
    assert mh.history_path(r3).name == "history_merged.csv" and calls == {"merge": 1, "extract": 1}
