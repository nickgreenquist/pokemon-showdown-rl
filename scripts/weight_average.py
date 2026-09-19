#!/usr/bin/env python
"""IDEAS 2.12 -- average a lane's last N checkpoints into one.

    python scripts/weight_average.py --run runs/showdown_monster200m_w_s104 --last 5

The free post-hoc antidote to end-of-anneal noise. [RWL-4] named it and never
ran it, and RESULTS §29 is the reason it is worth running now: **the annealed
tail is where 3-6 points of win rate are made, in 9 lanes of 9** -- so the last
few checkpoints of a lane are not interchangeable samples of one plateau, they
are the interval where the thing is still moving. Averaging over a moving
trajectory is a different operation from averaging over a converged one, and
this is the cheap way to find out which it resembles here.

WITHIN A LANE ONLY, and that is not a detail. Averaging across INDEPENDENTLY
TRAINED lanes is not licensed: there is no shared basin and permutation symmetry
makes the mean meaningless. This composes with 4.8's committee rather than
competing with it -- an averaged lane can still be a committee member.

WHAT IS AVERAGED. Every FLOATING-POINT tensor in the model state dict.
Integer buffers (step counters, RNG state) take the LAST checkpoint's value
rather than a nonsensical mean; a rounded average of two step counters is not a
step counter. Optimizer state is dropped: the output is for EVALUATION, and a
resumed run from an averaged checkpoint is a different and untested object.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[1]
CKPT = re.compile(r"^ckpt_(\d+)\.pt$")


def lane_checkpoints(run: Path) -> list[tuple[int, Path]]:
    out = []
    for p in run.iterdir():
        m = CKPT.match(p.name)
        if m:
            out.append((int(m.group(1)), p))
    return sorted(out)


# THE WEIGHTS ARE TWO LEVELS DOWN, and assuming otherwise produced a file that
# averaged NOTHING and looked fine. The layout is
#     ckpt["agent"]["actor" | "critic" | "aux_head"] -> a flat state dict
# with "optimizer", "updates" and "theta0_hash" alongside them. The first draft
# reached for ckpt["agent"] and found 6 entries, none of them tensors, so it
# "averaged 0 float tensors" -- caught only because the counter was printed.
SUBMODELS = ("actor", "critic", "aux_head")


def average(paths: list[Path]) -> tuple[dict, list[str], int, int]:
    """Mean of every float tensor in every submodel; last value elsewhere."""
    from rl.common.checkpoint import load_checkpoint

    cks = [load_checkpoint(str(p)) for p in paths]
    base = cks[-1]
    assert "agent" in base, f"unexpected checkpoint layout: {sorted(base)}"
    agents = [c["agent"] for c in cks]
    out_agent = dict(base["agent"])
    touched, n_float, n_other = [], 0, 0
    for sub_name in SUBMODELS:
        if sub_name not in base["agent"]:
            continue
        sds = [a[sub_name] for a in agents]
        keys = set(sds[-1])
        for sd in sds:
            assert set(sd) == keys, (
                f"{sub_name}: checkpoints disagree on their parameter set -- "
                "averaging across a changed architecture is meaningless")
        merged = {}
        for name, t in sds[-1].items():
            if torch.is_tensor(t) and t.is_floating_point():
                merged[name] = torch.stack(
                    [sd[name].float() for sd in sds]).mean(0).to(t.dtype)
                n_float += 1
            else:
                # A rounded mean of two step counters is not a step counter.
                merged[name] = t
                n_other += 1
        out_agent[sub_name] = merged
        touched.append(sub_name)
    assert n_float > 0, "averaged NOTHING -- the layout assumption is wrong again"
    # THE OPTIMIZER STAYS, and not because it is meaningful. `PPOAgent.
    # load_state_dict` indexes `state["optimizer"]["state"]` unconditionally, so
    # dropping it makes the file UNLOADABLE -- the first draft did that and only
    # a load test caught it. It is carried verbatim from the LAST checkpoint and
    # it does NOT correspond to the averaged weights, so a RESUME from this file
    # would run Adam moments fitted to a different point. The file is marked
    # `weight_averaged` at the top level so that is discoverable from the
    # artifact and not only from the sidecar.
    out = dict(base)
    out["agent"] = out_agent
    out["weight_averaged"] = {
        "sources": [p.name for p in paths],
        "eval_only": True,
        "warning": ("optimizer state is the LAST checkpoint's and does not match "
                    "these weights; do not resume from this file"),
    }
    return out, touched, n_float, n_other


def geometry(run: Path, windows=(2, 5, 10, 20, 40, 80)) -> None:
    """IS THERE NOISE TO AVERAGE, and what does averaging cost?

    Weight averaging helps when the iterates OSCILLATE around a minimum, because
    the mean cancels the noise. It hurts when they DRIFT, because the mean is
    just an earlier, less-trained point. Which one this is, is measurable, and
    it decides whether IDEAS 2.12 can do anything before an arm is spent.

    Two readings, both on the last checkpoints of one lane:
      * displacement  ||avg_N - final|| against ||first_N - final||: how far
        back along the path the average lands;
      * cos(d_i, d_{i+1}) of consecutive displacement vectors: positive is a
        drift, ~0 is a random walk, negative is oscillation. With ~1M
        parameters pure noise would sit within +/-0.001 of zero, so anything
        larger is systematic.
    """
    from rl.common.checkpoint import load_checkpoint

    cks = lane_checkpoints(run)
    final = load_checkpoint(str(cks[-1][1]))["agent"]

    def flat(sd):
        return torch.cat([t.float().reshape(-1) for sub in SUBMODELS
                          for t in sd[sub].values()
                          if torch.is_tensor(t) and t.is_floating_point()])

    vf = flat(final)
    tot = float(vf.norm())
    print(f"\n## {run.name}: how far back does the average land?\n")
    print(f"  {'window':>7} {'span':>24} {'||avg-final||':>14} {'||first-final||':>16} {'ratio':>7}")
    for N in windows:
        if N > len(cks):
            continue
        sel = cks[-N:]
        vs = [flat(load_checkpoint(str(p))["agent"]) for _, p in sel]
        avg = torch.stack(vs).mean(0)
        d_avg = float((avg - vf).norm()) / tot
        d_first = float((vs[0] - vf).norm()) / tot
        print(f"  {N:>7} {f'{sel[0][0]:,}..{sel[-1][0]:,}':>24} {d_avg:>14.5f} "
              f"{d_first:>16.5f} {d_avg / max(d_first, 1e-12):>7.2f}")

    print(f"\n## {run.name}: drift, walk, or oscillation?\n")
    print("  cos(d_i, d_i+1) of consecutive displacements -- drift > 0, walk ~ 0,")
    print("  oscillation < 0. Pure noise at ~1M params sits within +/-0.001.\n")
    for lo, hi, lab in ((-11, None, "last 10 (LR ~2% -> 0)"),
                        (-41, -30, "40..30 back"),
                        (-101, -90, "100..90 back"),
                        (-301, -290, "300..290 back")):
        if abs(lo) > len(cks):
            continue
        sel = cks[lo:hi] if hi else cks[lo:]
        vs = [flat(load_checkpoint(str(p))["agent"]) for _, p in sel]
        d = [vs[i + 1] - vs[i] for i in range(len(vs) - 1)]
        cs = [float(torch.nn.functional.cosine_similarity(d[i], d[i + 1], dim=0))
              for i in range(len(d) - 1)]
        print(f"  {lab:<26} span {sel[0][0]:>12,}..{sel[-1][0]:<12,} "
              f"mean cos {sum(cs) / len(cs):+.4f}  (n={len(cs)})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--last", type=int, default=5)
    ap.add_argument("--out", default=None)
    ap.add_argument("--geometry", action="store_true",
                    help="measure whether there is noise to average, and what "
                         "averaging costs, instead of writing a checkpoint")
    args = ap.parse_args()
    if args.geometry:
        geometry(Path(args.run))
        return

    run = Path(args.run)
    cks = lane_checkpoints(run)
    assert len(cks) >= args.last, f"{run} has {len(cks)} checkpoints, need {args.last}"
    chosen = cks[-args.last:]
    print(f"{run.name}: averaging {args.last} of {len(cks)} checkpoints")
    for step, p in chosen:
        print(f"   {step:>12,}  {p.name}")

    out_path = Path(args.out) if args.out else run / f"avg_last{args.last}.pt"
    ck, touched, n_float, n_other = average([p for _, p in chosen])
    torch.save(ck, out_path)
    h = hashlib.sha256(out_path.read_bytes()).hexdigest()
    meta = {
        "run": run.name, "last": args.last,
        "steps": [s for s, _ in chosen],
        "sources": [p.name for _, p in chosen],
        "submodels_averaged": touched,
        "tensors_averaged": n_float, "tensors_copied": n_other,
        "sha256": h, "path": str(out_path),
        "note": "EVAL ONLY -- optimizer state dropped; a resume from this is untested.",
    }
    (out_path.with_suffix(".meta.json")).write_text(json.dumps(meta, indent=2) + "\n")
    print(f"\n  averaged {n_float} float tensors across {touched}, "
          f"copied {n_other} non-float")
    print(f"  -> {out_path}")
    print(f"     sha256 {h}")
    print(f"     meta   {out_path.with_suffix('.meta.json').name}")
    print("\n  WITHIN-LANE ONLY. Averaging across independently trained lanes has")
    print("  no shared basin and permutation symmetry makes the mean meaningless.")


if __name__ == "__main__":
    main()
