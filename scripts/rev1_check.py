# VENDORED 2026-08-29 (CLEANUP B1) byte-identical from results/d25/scripts/rev1_check.py
# — that directory is gitignored, so this tracked copy is the only one a
# fresh clone can resolve. The original stays as the executed artifact.
"""REVIEWER 1 independent re-derivation for D25. Read-only; writes nothing to the repo.

Attacks:
  (1) split hygiene (battle disjointness) + split-seed sensitivity of the headline
  (2) 6-class (A) vs 12-class (B) label space: oracle MI (estimator-free) and
      realised probe gain, on the SAME tape.
  (3) Delta_ctx NULL: the same scorer probe with ctx ROW-SHUFFLED (same
      dimensionality, same marginals, zero state-correspondence).
"""
import sys

import numpy as np
import torch

REPO = "/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl"
TMP = "/Users/nickgreenquist/.claude/jobs/62d4fa41/tmp"
sys.path.insert(0, REPO)
sys.path.insert(0, REPO + "/scripts")
sys.path.insert(0, TMP)

from analyze_oppact import ctx_features  # noqa: E402
from eval_checkpoint import _load_showdown_agent  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.common.masking import masked_logits  # noqa: E402

NEG = -1e8
# layout re-derived from rl/envs/showdown.py (v2+ids, OBS_DIM 828)
OPP_MONS, MONB = 404, 34          # 6 opponent mon blocks, each 34 wide
OPP_ACT, OPP_MV, MD = 608, 624, 46


def nll(q, y, idx):
    return float(-np.log(np.clip(q[idx, y[idx]], 1e-300, None)).mean())


def zs(A, tr):
    flat = A[tr].reshape(-1, A.shape[-1])
    s = flat.std(0)
    keep = s > 1e-8
    mu = flat[:, keep].mean(0)
    return (A[..., keep] - mu) / s[keep], int(keep.sum())


def scorer_probe(ctx, groups, ncls, y, m, tr, te,
                 lams=(1e-3, 1e-2, 1e-1, 1.0), max_iter=300):
    """groups: list of (class_indices, feat (n,k,d) or None)."""
    C, _ = zs(ctx, tr)
    C = torch.as_tensor(C, dtype=torch.float64)
    dc = C.shape[1]
    G = []
    for cls_idx, feat in groups:
        if feat is None:
            G.append((cls_idx, None, 0))
        else:
            F_, _ = zs(feat, tr)
            G.append((cls_idx, torch.as_tensor(F_, dtype=torch.float64), F_.shape[-1]))
    Y, M = torch.as_tensor(y), torch.as_tensor(m)
    g = np.random.default_rng(0)
    inner = g.permutation(tr)
    cut = int(0.75 * len(inner))
    itr, iva = inner[:cut], inner[cut:]

    def run(fit, ev, lam):
        Ws = [torch.zeros(dc + d, dtype=torch.float64, requires_grad=True) for _, _, d in G]
        bb = torch.zeros(ncls, dtype=torch.float64, requires_grad=True)
        opt = torch.optim.LBFGS(Ws + [bb], max_iter=max_iter, history_size=20,
                                line_search_fn="strong_wolfe")

        def logits(idx):
            lg = torch.zeros(len(idx), ncls, dtype=torch.float64)
            cols = []
            for (cls_idx, F_, d), W in zip(G, Ws):
                c = C[idx]
                if F_ is None:
                    v = (c @ W).unsqueeze(1).expand(-1, len(cls_idx))
                else:
                    pair = torch.cat([c.unsqueeze(1).expand(-1, F_.shape[1], -1), F_[idx]], -1)
                    v = pair @ W
                cols.append((cls_idx, v))
            lg = lg.clone()
            out = [None] * ncls
            for cls_idx, v in cols:
                for k, cc in enumerate(cls_idx):
                    out[cc] = v[:, k]
            lg = torch.stack(out, 1)
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

    sc = {lam: run(itr, iva, lam)[0] for lam in lams}
    best = min(sc, key=sc.get)
    ev, q = run(tr, te, best)
    return ev, best, q


def build(npz, ckpt_path):
    d = np.load(npz)
    ckpt = load_checkpoint(ckpt_path)
    agent = _load_showdown_agent(ckpt, Config(**ckpt["config"]))
    obs1, obs2 = d["obs1"], d["obs2"]
    ok = obs2[:, 5] < 0.5
    idx = np.where(ok)[0]
    o1 = obs1[idx].astype(np.float64)
    n = len(idx)
    battle = d["battle"][idx]
    kind, ident = d["kind2"][idx], d["ident2"][idx]
    own_mv, own_team = d["own_move_ids2"][idx], d["own_team2"][idx]
    mvid = np.rint(o1[:, -4:] * 256).astype(np.int64)       # our 4 opp-move slots
    spid = np.rint(o1[:, -14:-8] * 256).astype(np.int64)    # our 6 opp-species slots

    # ---- oracle push-forwards, from seat 2's own policy on its own obs ----
    with torch.no_grad():
        p = torch.softmax(masked_logits(
            agent.actor(torch.as_tensor(obs2[idx], dtype=torch.float32)),
            torch.as_tensor(d["mask2"][idx], dtype=torch.bool)), -1).numpy()

    # 6-class (A): slot0..3, OTHER=4, SWITCH=5
    y6 = np.full(n, 4, np.int64)
    q6 = np.zeros((n, 6))
    # 12-class (B): switch->our opp-slot 0..5, move->6..9, 10 unseen switch, 11 other move
    y12 = np.full(n, 11, np.int64)
    q12 = np.zeros((n, 12))
    for i in range(n):
        # labels
        if kind[i] == 0:
            y6[i] = 5
            w = np.where(spid[i] == ident[i])[0]
            y12[i] = w[0] if len(w) and ident[i] > 0 else 10
        else:
            w = np.where(mvid[i] == ident[i])[0]
            y6[i] = w[0] if len(w) and ident[i] > 0 else 4
            y12[i] = 6 + w[0] if len(w) and ident[i] > 0 else 11
        # oracle
        for a in range(6):
            sp = own_team[i, a]
            w = np.where(spid[i] == sp)[0]
            q12[i, w[0] if len(w) and sp > 0 else 10] += p[i, a]
        q6[i, 5] = p[i, :6].sum()
        for j in range(4):
            mid = own_mv[i, j]
            w = np.where(mvid[i] == mid)[0] if mid > 0 else np.array([], int)
            q6[i, w[0] if len(w) else 4] += p[i, 6 + j]
            q12[i, 6 + w[0] if len(w) else 11] += p[i, 6 + j]
    q6 = np.clip(q6, 1e-12, None); q6 /= q6.sum(1, keepdims=True)
    q12 = np.clip(q12, 1e-12, None); q12 /= q12.sum(1, keepdims=True)

    # ---- obs-derivable legality masks ----
    m6 = np.zeros((n, 6), bool)
    m6[:, :4] = mvid > 0
    m6[:, 4] = True
    m6[:, 5] = (6 - 1 - np.rint(o1[:, 2] * 6).astype(int)) > 0
    mon = o1[:, OPP_MONS:OPP_MONS + 6 * MONB].reshape(n, 6, MONB)
    rev, fnt, act = mon[:, :, 0] > 0.5, mon[:, :, 2] > 0.5, mon[:, :, 3] > 0.5
    m12 = np.zeros((n, 12), bool)
    m12[:, :6] = rev & (~fnt) & (~act)
    m12[:, 6:10] = mvid > 0
    m12[:, 10] = rev.sum(1) < 6
    m12[:, 11] = True
    assert m6[np.arange(n), y6].all()
    bad = ~m12[np.arange(n), y12]
    feats = dict(
        ctx=ctx_features(d, agent).astype(np.float64)[idx],
        mv=np.stack([o1[:, OPP_MV + j * MD:OPP_MV + (j + 1) * MD] for j in range(4)], 1),
        oa=o1[:, OPP_ACT:OPP_MV][:, None, :],
        mon=mon,
    )
    return dict(n=n, battle=battle, y6=y6, y12=y12, q6=q6, q12=q12, m6=m6, m12=m12,
                feats=feats, bad12=float(bad.mean()), keep=float(ok.mean()))


def split(battle, seed, n):
    rng = np.random.default_rng(seed)
    b = np.unique(battle); rng.shuffle(b)
    trb = set(b[: int(0.7 * len(b))].tolist())
    tr = np.array([i for i in range(n) if battle[i] in trb])
    te = np.array([i for i in range(n) if battle[i] not in trb])
    assert not (set(battle[tr].tolist()) & set(battle[te].tolist())), "BATTLE BLEED"
    return tr, te


def marginal(y, m, ncls, tr):
    pr = np.bincount(y[tr], minlength=ncls) + 0.5
    pr = pr / pr.sum()
    q = np.where(m, pr[None, :], 0.0)
    return q / q.sum(1, keepdims=True)


def main():
    tag, npz, ck = sys.argv[1], sys.argv[2], sys.argv[3]
    D = build(npz, ck)
    n, battle, F = D["n"], D["battle"], D["feats"]
    print(f"### {tag}  n={n} (kept {D['keep']*100:.1f}%)  battles={len(np.unique(battle))}"
          f"  12-class realised-label-marked-illegal frac {D['bad12']:.4f}")

    # ---------- estimator-free ORACLE comparison, 6 vs 12 -------------------
    for name, y, q, m, K in (("L6 (A)", D["y6"], D["q6"], D["m6"], 6),
                             ("L12 (B)", D["y12"], D["q12"], D["m12"], 12)):
        tr, te = split(battle, 0, n)
        q1 = marginal(y, m, K, tr)
        A1, A3 = nll(q1, y, te), float((-(q * np.log(q)).sum(1))[te].mean())
        A3ce = nll(q, y, te)
        print(f"  {name:8s} A1 {A1:.4f}  A3 {A3:.4f}  ORACLE-MI(A1-A3) {A1-A3:.4f}"
              f"   [oracle CE {A3ce:.4f}, identity delta {A3ce-A3:+.4f}]")

    # ---------- split-seed sensitivity of A's headline ----------------------
    heads = []
    for s in range(6):
        tr, te = split(battle, s, n)
        q1 = marginal(D["y6"], D["m6"], 6, tr)
        A1 = nll(q1, D["y6"], te)
        A2s, lam, _ = scorer_probe(F["ctx"], [([0, 1, 2, 3], F["mv"]), ([4], None),
                                              ([5], F["oa"])], 6, D["y6"], D["m6"], tr, te)
        heads.append(A1 - A2s)
        print(f"  split seed {s}: A1 {A1:.4f}  A2s {A2s:.4f}  HEADLINE {A1-A2s:+.4f} (lam {lam})")
    h = np.array(heads)
    print(f"  HEADLINE over 6 splits: mean {h.mean():.4f} sd {h.std(ddof=1):.4f} "
          f"min {h.min():.4f} max {h.max():.4f}")

    # ---------- 12-class realised probe -------------------------------------
    tr, te = split(battle, 0, n)
    q1 = marginal(D["y12"], D["m12"], 12, tr)
    A1_12 = nll(q1, D["y12"], te)
    A2_12, lam, _ = scorer_probe(F["ctx"], [(list(range(6)), F["mon"]),
                                            ([6, 7, 8, 9], F["mv"]),
                                            ([10], None), ([11], None)],
                                 12, D["y12"], D["m12"], tr, te)
    A3_12 = float((-(D["q12"] * np.log(D["q12"])).sum(1))[te].mean())
    print(f"  L12 REALISED: A1 {A1_12:.4f} A2s {A2_12:.4f} gain {A1_12-A2_12:+.4f} "
          f"({100*(A1_12-A2_12)/(A1_12-A3_12):.0f}% of the {A1_12-A3_12:.4f}-nat ceiling, lam {lam})")

    # ---------- Delta_ctx and its NULL --------------------------------------
    tr, te = split(battle, 0, n)
    q1 = marginal(D["y6"], D["m6"], 6, tr)
    A1 = nll(q1, D["y6"], te)
    grp = lambda c: [([0, 1, 2, 3], F["mv"]), ([4], None), ([5], F["oa"])]  # noqa: E731
    A2s, _, _ = scorer_probe(F["ctx"], grp(0), 6, D["y6"], D["m6"], tr, te)
    A2e, _, _ = scorer_probe(np.zeros((n, 1)), grp(0), 6, D["y6"], D["m6"], tr, te)
    print(f"  Delta_ctx (real ctx)      = {A2e - A2s:+.4f}")
    live = (F["ctx"][tr].std(0) > 1e-8).sum()
    print(f"    live ctx units (nonzero var on fit split): {live} of {F['ctx'].shape[1]}")
    for s in (1, 2, 3):
        rng = np.random.default_rng(100 + s)
        perm = rng.permutation(n)
        A2n, _, _ = scorer_probe(F["ctx"][perm], grp(0), 6, D["y6"], D["m6"], tr, te)
        print(f"  Delta_ctx NULL (row-shuffled ctx, seed {s}) = {A2e - A2n:+.4f}")
    rng = np.random.default_rng(7)
    gauss = rng.standard_normal((n, live))
    A2g, _, _ = scorer_probe(gauss, grp(0), 6, D["y6"], D["m6"], tr, te)
    print(f"  Delta_ctx NULL (iid gaussian, dim {live})    = {A2e - A2g:+.4f}")


if __name__ == "__main__":
    main()
