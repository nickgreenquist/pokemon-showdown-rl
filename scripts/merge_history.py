"""Merge a resumed run's SPLIT wandb offline histories into history_merged.csv.

    python scripts/merge_history.py runs/gen4_wang50m_s216

A `--resume` starts a NEW offline run whose steps OVERLAP the old one (the
checkpoint lags the last logged step by far more than one update), so
scripts/extract_history.py hard-fails on a run dir with several offline
runs. The merge rule (docs/landmines.md, the R2 resumes): for segment k
keep rows with `_step` < the from_step of the resume that started segment
k+1; the last segment keeps everything; then assert `_step` is monotone
non-decreasing. Segments are the offline-run dirs in time order (their
names carry the start timestamp); the cut points come from meta.yaml's
`resumes` list — one entry per resume, in order, so len(segments) ==
len(resumes) + 1 or the merge refuses. A segment that died at reset has no
history rows and contributes nothing (still counted). Writes
<run>/history_merged.csv and prints one line per segment.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from extract_history import read_history  # noqa: E402


def merge(run: Path) -> Path:
    meta = yaml.safe_load((run / "meta.yaml").read_text())
    resumes = meta.get("resumes") or []
    segments = sorted(run.glob("wandb/offline-run-*/run-*.wandb"), key=lambda p: p.parent.name)
    if len(segments) != len(resumes) + 1:
        raise SystemExit(f"{run}: {len(segments)} offline runs but {len(resumes)} resumes in meta.yaml — refusing")
    cuts = [int(r["from_step"]) for r in resumes] + [None]
    rows_out: list[dict] = []
    keys: list[str] = []
    for k, (seg, cut) in enumerate(zip(segments, cuts)):
        rows = read_history(seg)
        kept = [r for r in rows if "_step" in r and (cut is None or r["_step"] < cut)]
        for r in kept:
            for key in r:
                if key not in keys:
                    keys.append(key)
        rows_out.extend(kept)
        span = f"{int(rows[0]['_step'])}..{int(rows[-1]['_step'])}" if rows else "empty"
        print(f"segment {k}: {seg.parent.name} rows {len(rows)} ({span}) kept {len(kept)}"
              + (f" (< from_step {cut})" if cut is not None else " (last: all)"))
    steps = [r["_step"] for r in rows_out]
    for a, b in zip(steps, steps[1:]):
        if b < a:
            raise SystemExit(f"{run}: merged _step not monotone ({a} -> {b}) — refusing to write")
    out = run / "history_merged.csv"
    keys = sorted(keys, key=lambda k: (not k.startswith("_"), k))
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows_out)
    print(f"wrote {out}: {len(rows_out)} rows, {len(segments)} segments, last _step {int(steps[-1]) if steps else 'n/a'}")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    merge(Path(sys.argv[1]))
