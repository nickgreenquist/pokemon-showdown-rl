"""D25 treatment atoms: Delta_ref-ctx for the five treatment lanes (§5).

    python scripts/d25_atoms.py                       # the banked treatment run
    python scripts/d25_atoms.py --lanes 57,58,59,60,61 \
        --run-prefix showdown_sp_actpred12m_placebo_s \
        --out results/d25p/placebo_atoms.json         # D25-P (R-2's input)

Computes, for each treatment lane s52-56, the mechanism co-primary's atom on
the FROZEN s36 reference tape — mean over 8 battle-level 70/30 splits (seeds
0-7) of NLL(scorer-shaped probe, ctx ABLATED) - NLL(same probe WITH the
lane's ctx) — in BOTH label spaces (L6-native PRIMARY, 12-class secondary),
lambda frozen at 0.01, LBFGS convergence asserted at the letter's ||g|| <
1e-3 on every fit. Writes results/d25/treatment_atoms.json in
scripts/d25_grade.py's input schema, plus a full per-split detail file.

PROVENANCE, DISCLOSED: this imports the fit/build machinery
(rev1_check.build, gate_r012.prep/split, analyze_oppact.ctx_features) —
the SAME code path that produced the FROZEN control atoms (refreeze_ref.py,
2026-08-13), so treatment and control go through byte-identical fits.
Since 2026-08-29 (CLEANUP B1) those three modules are VENDORED byte-identical
into scripts/, so a fresh clone resolves them; the gitignored
results/d25/scripts/ originals remain the executed artifacts. results/d25/ is already the only copy of the frozen
tapes; the mechanism co-primary is unreproducible without it either way.
The committed d25_gates.py `verify` independently reproduces the L6-native
control atoms to < 2e-4 with its own re-implementation, which is the
standing check that this path computes what §5 froze.

The tape sha256 is verified against §5's frozen value before any fit.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
D25 = REPO / "results" / "d25"
sys.path.insert(0, str(REPO))
# Vendored copies in scripts/ take precedence (CLEANUP B1, 2026-08-29):
# gate_r012 / rev1_check / analyze_oppact are tracked there now; the
# gitignored results/d25/scripts/ originals remain only as fallback on
# the machine that ran D25.
sys.path.insert(0, str(D25 / "scripts"))
sys.path.insert(0, str(REPO / "scripts"))

import gate_r012 as G  # noqa: E402  (vendored, provenance above)
from analyze_oppact import ctx_features  # noqa: E402
from rev1_check import build  # noqa: E402

from eval_checkpoint import _load_showdown_agent  # noqa: E402
from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.common.masking import masked_logits  # noqa: E402  (B4 2026-08-29: harness sentinel)

NSPL = 8
LAM = 1e-2                       # FROZEN. No per-lane selection (§5).
MAX_ITER = 2000
GTOL = 1e-3                      # the letter's asserted bound (§5)
LANES = (52, 53, 54, 55, 56)     # the treatment arm
REF_NPZ = D25 / "oppact_s36ref.npz"
REF_CKPT = REPO / "runs/showdown_sp_struct50m_s36/ckpt_012000000.pt"
REF_SHA = "3ffee9ba8f0c8fd826573ecb0a2334e249f73ae914720035f3fd839ffe074917"

CONV = []


def fit_eval(C, Gr, ncls, Y, M, fit, ev, lam, tag):
    """refreeze_ref.py's fit verbatim, at the letter's GTOL: LBFGS
    strong-wolfe, convergence asserted, never silently dropped or retried."""
    dc = C.shape[1]
    Ws = [torch.zeros(dc + d, dtype=torch.float64, requires_grad=True)
          for _, _, d in Gr]
    bb = torch.zeros(ncls, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS(Ws + [bb], max_iter=MAX_ITER, history_size=20,
                            line_search_fn="strong_wolfe")

    def logits(idx):
        out = [None] * ncls
        for (cls_idx, F_, d), W in zip(Gr, Ws):
            c = C[idx]
            if F_ is None:
                v = (c @ W).unsqueeze(1).expand(-1, len(cls_idx))
            else:
                pair = torch.cat(
                    [c.unsqueeze(1).expand(-1, F_.shape[1], -1), F_[idx]], -1)
                v = pair @ W
            for k, cc in enumerate(cls_idx):
                out[cc] = v[:, k]
        lg = torch.stack(out, 1) + bb
        return masked_logits(lg, M[idx])

    def cl():
        opt.zero_grad()
        loss = torch.nn.functional.cross_entropy(logits(fit), Y[fit]) + \
            lam * sum((W @ W) for W in Ws)
        loss.backward()
        return loss

    opt.step(cl)
    fl = float(cl())
    gn = float(torch.sqrt(sum((p.grad ** 2).sum() for p in Ws + [bb])))
    CONV.append(dict(tag=tag, fit_loss=fl, gnorm=gn))
    if not (np.isfinite(fl) and gn < GTOL):
        raise AssertionError(
            f"NON-CONVERGED FIT {tag}: loss {fl:.6f} ||g|| {gn:.3e} >= "
            f"{GTOL:g} — the letter fails loudly, never drops or retries.")
    with torch.no_grad():
        return float(torch.nn.functional.cross_entropy(logits(ev), Y[ev]))


def main():
    # D25-P: the placebo arm needs the SAME atom on the SAME frozen s36
    # reference tape, differing only in whose ctx is read. These flags exist so
    # that is a command-line change and not an in-place edit of LANES — this
    # script produced the BANKED treatment atoms in §5's attestation
    # (+0.0530/+0.0659/+0.0505/+0.0619/+0.0568), and the defaults below
    # reproduce them exactly.
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lanes", default=",".join(str(s) for s in LANES))
    ap.add_argument("--run-prefix", default="showdown_sp_actpred12m_s")
    ap.add_argument("--out", default=str(D25 / "treatment_atoms.json"))
    args = ap.parse_args()
    lanes = [int(x) for x in args.lanes.split(",") if x.strip()]
    out_path = Path(args.out)
    detail_path = out_path.with_name(out_path.stem + "_detail.json")

    t00 = time.time()
    got = hashlib.sha256(REF_NPZ.read_bytes()).hexdigest()
    assert got == REF_SHA, f"{REF_NPZ} is not the frozen s36 tape: {got}"
    print(f"frozen s36 reference tape attested: {got}")

    D = build(str(REF_NPZ), str(REF_CKPT))
    n, battle, F = D["n"], D["battle"], D["feats"]
    print(f"tape: n={n} rows, battles={len(np.unique(battle))}, kept "
          f"{D['keep']*100:.1f}%", flush=True)

    d = np.load(REF_NPZ)
    obs1 = d["obs1"][d["obs2"][:, 5] < 0.5]

    g12 = [(list(range(6)), F["mon"]), ([6, 7, 8, 9], F["mv"]),
           ([10], None), ([11], None)]
    g6 = [([0, 1, 2, 3], F["mv"]), ([4], None), ([5], F["oa"])]
    Y12, M12 = torch.as_tensor(D["y12"]), torch.as_tensor(D["m12"])
    Y6, M6 = torch.as_tensor(D["y6"]), torch.as_tensor(D["m6"])

    CTX, live_units = {}, {}
    for s in lanes:
        ck = load_checkpoint(str(REPO / f"runs/{args.run_prefix}{s}/checkpoint.pt"))
        agent = _load_showdown_agent(ck, Config(**ck["config"]))
        CTX[s] = ctx_features({"obs1": obs1}, agent).astype(np.float64)
        live_units[s] = int((CTX[s].std(0) > 1e-8).sum())
        print(f"  s{s}: ctx {CTX[s].shape}, live units {live_units[s]}",
              flush=True)

    rows = {s: [] for s in lanes}
    for sp in range(NSPL):
        t0 = time.time()
        tr, te = G.split_by_battle(battle, sp, n)
        Ce, Ge, _ = G.prep(np.zeros((n, 1)), g12, tr)
        A2e12 = fit_eval(Ce, Ge, 12, Y12, M12, tr, te, LAM, f"abl12.sp{sp}")
        Ce6, Ge6, _ = G.prep(np.zeros((n, 1)), g6, tr)
        A2e6n = fit_eval(Ce6, Ge6, 6, Y6, M6, tr, te, LAM, f"abl6n.sp{sp}")

        line = []
        for s in lanes:
            C, Gr, _ = G.prep(CTX[s], g12, tr)
            A2s12 = fit_eval(C, Gr, 12, Y12, M12, tr, te, LAM, f"s{s}.12.sp{sp}")
            C6, Gr6, _ = G.prep(CTX[s], g6, tr)
            A2s6n = fit_eval(C6, Gr6, 6, Y6, M6, tr, te, LAM, f"s{s}.6n.sp{sp}")
            rows[s].append(dict(split=sp, d12=A2e12 - A2s12, d6n=A2e6n - A2s6n))
            line.append(f"s{s} {A2e12 - A2s12:+.4f}/{A2e6n - A2s6n:+.4f}")
        print(f"split {sp} ({len(te)} te, {time.time()-t0:.0f}s) d12/d6n: "
              + "  ".join(line), flush=True)

    out = {"L6": {}, "c12": {}}
    detail = dict(rows={f"s{s}": rows[s] for s in lanes}, live=live_units,
                  conv=CONV, n=n, lam=LAM, nspl=NSPL, tape_sha=REF_SHA)
    for key, space in (("d6n", "L6"), ("d12", "c12")):
        print(f"\n=== Delta_ref-ctx {space} (s36 reference, {NSPL} splits) ===")
        for s in lanes:
            v = np.array([r[key] for r in rows[s]])
            out[space][str(s)] = float(v.mean())
            print(f"  s{s}: {v.mean():+.4f}  split sd {v.std(ddof=1):.4f}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1)
    with open(detail_path, "w") as f:
        json.dump(detail, f, indent=1)
    print(f"\nwrote {out_path} (+ detail); "
          f"convergence max ||g|| {max(c['gnorm'] for c in CONV):.3e}; "
          f"total {time.time()-t00:.0f}s")


if __name__ == "__main__":
    main()
