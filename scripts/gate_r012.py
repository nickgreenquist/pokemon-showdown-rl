# VENDORED 2026-08-29 (CLEANUP B1) byte-identical from results/d25/scripts/gate_r012.py
# — that directory is gitignored, so this tracked copy is the only one a
# fresh clone can resolve. The original stays as the executed artifact.
"""R0-12 GATE: five-lane control distribution of Delta_ctx.

Binding corrections applied (Reviewer 1 MUST-FIX 3, 5, 6, 7):
  * 12-CLASS canonical label space (B's), L6 reported by marginalising.
  * SCORER-SHAPED estimators only (never a linear probe on ctx alone).
  * SPLIT-AVERAGED over N_SPLITS battle-level splits, split sd reported.
  * FROZEN lambda grid; inner lambda split is BY BATTLE (rev1 MUST-FIX 7:
    the designers' inner split was a row permutation and leaked battles).
  * per-lane live-ctx-unit count reported alongside (rev1 MUST-FIX 6).

Writes JSON to the job tmp dir. Repo tree untouched.
"""
import json
import sys
import time

import numpy as np
import torch

TMP = "/Users/nickgreenquist/.claude/jobs/62d4fa41/tmp"
sys.path.insert(0, TMP)

from rev1_check import build, marginal, nll  # noqa: E402

NEG = -1e8
LAMS = (1e-3, 1e-2, 1e-1, 1.0)   # FROZEN grid
N_SPLITS = 8
MAX_ITER = 300


def zs(A, tr):
    flat = A[tr].reshape(-1, A.shape[-1])
    s = flat.std(0)
    keep = s > 1e-8
    mu = flat[:, keep].mean(0)
    return (A[..., keep] - mu) / s[keep], int(keep.sum())


def prep(ctx, groups, tr):
    C, live = zs(ctx, tr)
    C = torch.as_tensor(C, dtype=torch.float64)
    G = []
    for cls_idx, feat in groups:
        if feat is None:
            G.append((cls_idx, None, 0))
        else:
            F_, _ = zs(feat, tr)
            G.append((cls_idx, torch.as_tensor(F_, dtype=torch.float64), F_.shape[-1]))
    return C, G, live


def fit_eval(C, G, ncls, Y, M, fit, ev, lam):
    dc = C.shape[1]
    Ws = [torch.zeros(dc + d, dtype=torch.float64, requires_grad=True) for _, _, d in G]
    bb = torch.zeros(ncls, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS(Ws + [bb], max_iter=MAX_ITER, history_size=20,
                            line_search_fn="strong_wolfe")

    def logits(idx):
        out = [None] * ncls
        for (cls_idx, F_, d), W in zip(G, Ws):
            c = C[idx]
            if F_ is None:
                v = (c @ W).unsqueeze(1).expand(-1, len(cls_idx))
            else:
                pair = torch.cat([c.unsqueeze(1).expand(-1, F_.shape[1], -1), F_[idx]], -1)
                v = pair @ W
            for k, cc in enumerate(cls_idx):
                out[cc] = v[:, k]
        lg = torch.stack(out, 1) + bb
        return torch.where(M[idx], lg, torch.full_like(lg, NEG))

    def cl():
        opt.zero_grad()
        loss = torch.nn.functional.cross_entropy(logits(fit), Y[fit]) + \
            lam * sum((W @ W) for W in Ws)
        loss.backward()
        return loss

    opt.step(cl)
    with torch.no_grad():
        lg = logits(ev)
        return (float(torch.nn.functional.cross_entropy(lg, Y[ev])),
                torch.softmax(lg, -1).numpy())


def probe(ctx, groups, ncls, y, m, battle, tr, te, seed):
    """lambda chosen on an inner split BY BATTLE of the fit set only."""
    C, G, live = prep(ctx, groups, tr)
    Y, M = torch.as_tensor(y), torch.as_tensor(m)
    rng = np.random.default_rng(1000 + seed)
    b = np.unique(battle[tr])
    rng.shuffle(b)
    itrb = set(b[: int(0.75 * len(b))].tolist())
    itr = tr[np.isin(battle[tr], list(itrb))]
    iva = tr[~np.isin(battle[tr], list(itrb))]
    sc = {lam: fit_eval(C, G, ncls, Y, M, itr, iva, lam)[0] for lam in LAMS}
    best = min(sc, key=sc.get)
    ev, q = fit_eval(C, G, ncls, Y, M, tr, te, best)
    return ev, best, q, live, sc


def split_by_battle(battle, seed, n):
    rng = np.random.default_rng(seed)
    b = np.unique(battle)
    rng.shuffle(b)
    trb = set(b[: int(0.7 * len(b))].tolist())
    tr = np.where(np.isin(battle, list(trb)))[0]
    te = np.where(~np.isin(battle, list(trb)))[0]
    assert not (set(battle[tr].tolist()) & set(battle[te].tolist())), "BATTLE BLEED"
    return tr, te


def marg12_to_6(q12, y12map=None):
    """L6 = {slot0..3, OTHER, SWITCH} from L12 {sw0..5,mv0..3,10 unseen sw,11 other}."""
    q6 = np.zeros((q12.shape[0], 6))
    q6[:, 5] = q12[:, :6].sum(1) + q12[:, 10]
    q6[:, :4] = q12[:, 6:10]
    q6[:, 4] = q12[:, 11]
    return q6


def y12_to_y6(y12):
    y6 = np.where(y12 < 6, 5, np.where(y12 == 10, 5, np.where(y12 == 11, 4, y12 - 6)))
    return y6.astype(np.int64)


def main():
    lanes = [(s, f"{TMP}/oppact_s{s}.npz",
              f"/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/"
              f"runs/showdown_sp_struct12m_s{s}/checkpoint.pt")
             for s in (26, 27, 28, 50, 51)]
    out = {}
    for seed, npz, ck in lanes:
        t0 = time.time()
        D = build(npz, ck)
        n, battle, F = D["n"], D["battle"], D["feats"]
        g12 = [(list(range(6)), F["mon"]), ([6, 7, 8, 9], F["mv"]),
               ([10], None), ([11], None)]
        rec = dict(n=n, battles=int(len(np.unique(battle))), keep=D["keep"],
                   bad12=D["bad12"], splits=[])
        print(f"### s{seed}  n={n} battles={len(np.unique(battle))} "
              f"kept {D['keep']*100:.1f}%  bad12 {D['bad12']:.4f}", flush=True)
        for s in range(N_SPLITS):
            tr, te = split_by_battle(battle, s, n)
            q1_12 = marginal(D["y12"], D["m12"], 12, tr)
            A1_12 = nll(q1_12, D["y12"], te)
            A3_12 = float((-(D["q12"] * np.log(D["q12"])).sum(1))[te].mean())
            A2s, lam_s, q_s, live, _ = probe(F["ctx"], g12, 12, D["y12"], D["m12"],
                                             battle, tr, te, s)
            A2e, lam_e, q_e, _, _ = probe(np.zeros((n, 1)), g12, 12, D["y12"], D["m12"],
                                          battle, tr, te, s)
            # L6 reporting view: marginalise the SAME fitted 12-way posteriors
            y6 = y12_to_y6(D["y12"])
            m6 = D["m6"]
            q1_6 = marginal(y6, m6, 6, tr)
            A1_6 = nll(q1_6, y6, te)
            q6s = marg12_to_6(q_s)
            q6e = marg12_to_6(q_e)
            q6s = np.clip(q6s, 1e-12, None); q6s /= q6s.sum(1, keepdims=True)
            q6e = np.clip(q6e, 1e-12, None); q6e /= q6e.sum(1, keepdims=True)
            Q6s = np.full((n, 6), 1.0 / 6); Q6s[te] = q6s
            Q6e = np.full((n, 6), 1.0 / 6); Q6e[te] = q6e
            A2s6, A2e6 = nll(Q6s, y6, te), nll(Q6e, y6, te)
            row = dict(split=s, A1_12=A1_12, A3_12=A3_12, A2s_12=A2s, A2e_12=A2e,
                       d_ctx=A2e - A2s, gain_12=A1_12 - A2s, lam_s=lam_s, lam_e=lam_e,
                       A1_6=A1_6, A2s_6=A2s6, A2e_6=A2e6, d_ctx_6=A2e6 - A2s6,
                       gain_6=A1_6 - A2s6, live=live, n_te=int(len(te)))
            rec["splits"].append(row)
            print(f"  split {s}: A1_12 {A1_12:.4f} A2s {A2s:.4f} A2e {A2e:.4f} "
                  f"D_ctx {A2e - A2s:+.4f} | L6 gain {A1_6 - A2s6:+.4f} "
                  f"D_ctx6 {A2e6 - A2s6:+.4f} | lam {lam_s}/{lam_e} live {live}",
                  flush=True)
        d = np.array([r["d_ctx"] for r in rec["splits"]])
        d6 = np.array([r["d_ctx_6"] for r in rec["splits"]])
        g = np.array([r["gain_12"] for r in rec["splits"]])
        g6 = np.array([r["gain_6"] for r in rec["splits"]])
        rec.update(d_ctx_mean=float(d.mean()), d_ctx_sd=float(d.std(ddof=1)),
                   d_ctx6_mean=float(d6.mean()), d_ctx6_sd=float(d6.std(ddof=1)),
                   gain12_mean=float(g.mean()), gain12_sd=float(g.std(ddof=1)),
                   gain6_mean=float(g6.mean()), gain6_sd=float(g6.std(ddof=1)),
                   live=rec["splits"][0]["live"], secs=time.time() - t0)
        print(f"  == s{seed} D_ctx(12) mean {d.mean():+.4f} sd {d.std(ddof=1):.4f} "
              f"[{d.min():+.4f},{d.max():+.4f}] | D_ctx(6) mean {d6.mean():+.4f} "
              f"sd {d6.std(ddof=1):.4f} | gain12 {g.mean():.4f} gain6 {g6.mean():.4f} "
              f"| {time.time() - t0:.0f}s", flush=True)
        out[f"s{seed}"] = rec
        with open(f"{TMP}/d25_r012_control.json", "w") as f:
            json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
