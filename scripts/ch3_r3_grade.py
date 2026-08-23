"""CH3 R3 grader: the dose-axis segment contrasts, cells T1/T2a/T2b/T3.

    python scripts/ch3_r3_grade.py --prereg configs/eval/ch3_rung3.yaml

NON-CREDITING (design MF-7) — this prints mechanism cells, never a credit.
Refuses a dirty tree; stamps prereg + git sha into results/ch3_r3/
r3_readout.json. Reads fresh finals (A0R3, A1SS, A1SL) from the R3 results
dir and the REUSED Dose-M finals from results/ch3_r2 under the pre-reg's
verified sha-unchanged condition. F-gates before any cell: R2-5 exact on
every fresh chunk, F4 era gate on fresh A0 vs the R2 A0 anchor, sha
re-verification of the four checkpoints. Cells are evaluated on both
segments; every true predicate is printed and the LANDING cell follows the
pre-stated precedence T3 > T1 > T2a > T2b.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import yaml


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg", default="configs/eval/ch3_rung3.yaml")
    args = parser.parse_args()

    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    ).stdout.strip()
    assert not dirty, "grader refuses a dirty tree:\n" + dirty
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()

    prereg = yaml.safe_load(open(args.prereg))
    out_dir = Path(prereg["results_dir"])
    lanes = prereg["arms"]["A0R3"]["lanes"]

    # F5: pinned checkpoint shas still hold at grade time
    for lane, spec in prereg["checkpoints"].items():
        got = _sha256(spec["path"])
        assert got == spec["sha256"], f"F5: {lane} sha mismatch at grade time"

    # F2 / R2-5: exact win_rate == wins_from_returns on every fresh chunk
    chunk_files = sorted(out_dir.glob("*.chunk*.json"))
    assert chunk_files, f"no chunk files under {out_dir}"
    for p in chunk_files:
        rep = json.loads(p.read_text())
        assert rep["eval/win_rate"] == rep["wins_from_returns"], f"F2 FAIL: {p.name}"
    print(f"F2 PASS: R2-5 exact on {len(chunk_files)} fresh chunk files")

    def finals(prefix: str, source: Path) -> dict[str, dict]:
        out = {}
        for lane in lanes:
            p = source / f"{prefix}_{lane}.final.json"
            assert p.exists(), f"missing {p}"
            out[lane] = json.loads(p.read_text())
        return out

    a0 = finals("a0r3", out_dir)
    s = finals("a1ss", out_dir)
    l = finals("a1sl", out_dir)
    m = {}
    for lane, fname in zip(lanes, prereg["reused_m"]["finals"]):
        p = Path(prereg["reused_m"]["source"]) / fname
        m[lane] = json.loads(p.read_text())
        pinned = prereg["anchors"]["m_r2_per_lane"][lane]
        got = m[lane]["eval/win_rate"]
        assert abs(got - pinned) < 5e-6, f"reused M {lane}: {got} != pinned {pinned}"

    # F4 era gate
    a0_pooled = float(np.mean([a0[x]["eval/win_rate"] for x in lanes]))
    era_diff = abs(a0_pooled - prereg["anchors"]["a0_r2_pooled"])
    print(f"F4 era: fresh A0 pooled {a0_pooled:.5f} vs {prereg['anchors']['a0_r2_pooled']}"
          f" -> |diff| {era_diff:.5f} ({'FIRES — @M reuse VOID, re-run M fresh' if era_diff > 0.02 else 'PASS'})")
    if era_diff > 0.02:
        sys.exit(1)

    band = float(prereg["segment_band"])
    wr = {lane: {"A0": a0[lane]["eval/win_rate"], "S": s[lane]["eval/win_rate"],
                 "M": m[lane]["eval/win_rate"], "L": l[lane]["eval/win_rate"]}
          for lane in lanes}
    seg1 = np.array([wr[x]["M"] - wr[x]["S"] for x in lanes])
    seg2 = np.array([wr[x]["L"] - wr[x]["M"] for x in lanes])
    res = {}
    for name, seg in (("seg1", seg1), ("seg2", seg2)):
        mean = float(seg.mean())
        se = float(seg.std(ddof=1) / np.sqrt(len(seg)))
        res[name] = {"per_lane": {x: float(v) for x, v in zip(lanes, seg)},
                     "mean": mean, "se_clustered": se,
                     "bar": max(band, 2 * se),
                     "ci_lo": mean - 2 * se, "ci_hi": mean + 2 * se}
        print(f"{name}: per-lane {[f'{v:+.4f}' for v in seg]} mean {mean:+.5f} "
              f"se {se:.5f} bar {res[name]['bar']:.4f} CI [{mean-2*se:+.4f}, {mean+2*se:+.4f}]")

    t1 = res["seg2"]["mean"] >= res["seg2"]["bar"]
    t2a = all(r["ci_hi"] < band for r in res.values())
    t2b = any(r["ci_lo"] <= 0 <= r["ci_hi"] or r["ci_lo"] <= band <= r["ci_hi"]
              for r in res.values()) and not (t1 or t2a)
    t3 = any(r["mean"] <= -r["bar"] for r in res.values())
    cells = {"T1": t1, "T2a": t2a, "T2b": t2b, "T3": t3}
    landing = next((c for c in ("T3", "T1", "T2a", "T2b") if cells[c]), "T2b")
    print(f"cells true: {[c for c, v in cells.items() if v]} -> LANDING (precedence T3>T1>T2a>T2b): {landing}")

    secondary = {}
    for dose, fin in (("S", s), ("M", m), ("L", l)):
        secondary[dose] = {
            "delta_vs_a0_per_lane": {x: wr[x][dose] - wr[x]["A0"] for x in lanes},
            "flip_rate": {x: fin[x].get("search/flip_rate") for x in lanes},
            "placeholder_skip_rate": {x: fin[x].get("search/placeholder_skip_rate") for x in lanes},
            "ms_mean": {x: fin[x].get("search/ms_mean") for x in lanes},
            "leaves_mean": {x: fin[x].get("search/leaves_mean") for x in lanes},
        }

    readout = {
        "prereg_sha256": _sha256(args.prereg),
        "git_sha": git_sha,
        "non_crediting": True,
        "a0_pooled_fresh": a0_pooled,
        "era_diff": era_diff,
        "win_rates": wr,
        "segments": res,
        "cells_true": cells,
        "landing_cell": landing,
        "secondary": secondary,
    }
    (out_dir / "r3_readout.json").write_text(json.dumps(readout, indent=2) + "\n")
    print(f"wrote {out_dir}/r3_readout.json (NON-CREDITING; no README change from any cell)")


if __name__ == "__main__":
    main()
