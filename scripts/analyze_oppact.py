# VENDORED 2026-08-29 (CLEANUP B1) byte-identical from results/d25/scripts/analyze_oppact.py
# — that directory is gitignored, so this tracked copy is the only one a
# fresh clone can resolve. The original stays as the executed artifact.
"""D25 information measurement, analysis stage (DESIGNER A). Zero lanes.

Entropy decomposition of the OPPONENT'S ACTION in the label space an
auxiliary head could actually emit from seat 1's own observation:

  L6 = {our opponent-move-slot 0..3, OTHER_MOVE, SWITCH}

  A0  uniform over the legal L6 classes            (ACTION-MASK BASELINE)
  A1  global marginal, renormalised on the mask    (state-independent prior)
  A2  fitted probe on the FROZEN actor ctx (384)   (what the aux head can learn)
  A2' fitted probe on the raw observation (828)    (linear ceiling on the obs)
  A3  ORACLE: entropy of the opponent's OWN policy pushed onto L6
      (the irreducible floor -- no predictor can beat it)

HEADLINE = A1 - A2 nats (learnable, non-trivial, beyond legality).
CEILING  = A1 - A3 nats.
"""
import argparse
import sys

import numpy as np
import torch

REPO = "/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl"
sys.path.insert(0, REPO)
sys.path.insert(0, REPO + "/scripts")

from eval_checkpoint import _load_showdown_agent  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.common.masking import masked_logits  # noqa: E402

NEG = -1e8
NCLS = 6  # slot0..3, OTHER, SWITCH
SWITCH, OTHER = 5, 4


def labels_and_mask(d):
    obs1 = d["obs1"]
    slot_ids = np.rint(obs1[:, -4:] * 256).astype(np.int64)  # our view of their moves
    kind2, ident2 = d["kind2"], d["ident2"]
    n = len(kind2)
    y = np.full(n, OTHER, dtype=np.int64)
    for i in range(n):
        if kind2[i] == 0:
            y[i] = SWITCH
        else:
            w = np.where(slot_ids[i] == ident2[i])[0]
            y[i] = w[0] if len(w) and ident2[i] > 0 else OTHER
    # legality as SEAT 1 can infer it: a slot class is available iff the slot
    # carries a move id; OTHER is always conceivable; SWITCH iff the opponent
    # has a live bench, and the faint count is public (obs1[2]).
    m = np.zeros((n, NCLS), dtype=bool)
    m[:, :4] = slot_ids > 0
    m[:, OTHER] = True
    opp_fainted = np.rint(obs1[:, 2] * 6).astype(int)
    m[:, SWITCH] = (6 - 1 - opp_fainted) > 0
    assert m[np.arange(n), y].all(), "a realised label was marked illegal"
    return y, m


def oracle_pushforward(d, agent):
    """A3: entropy of pi(.|opponent's own obs) pushed onto L6, exactly."""
    obs1, obs2, mask2 = d["obs1"], d["obs2"], d["mask2"]
    slot_ids = np.rint(obs1[:, -4:] * 256).astype(np.int64)
    own = d["own_move_ids2"]
    with torch.no_grad():
        logits = agent.actor(torch.as_tensor(obs2, dtype=torch.float32))
        p = torch.softmax(
            masked_logits(logits, torch.as_tensor(mask2, dtype=torch.bool)), dim=-1
        ).numpy()
    n = len(p)
    q = np.zeros((n, NCLS))
    q[:, SWITCH] = p[:, :6].sum(1)
    for i in range(n):
        for j in range(4):
            cls = OTHER
            mid = own[i, j]
            if mid > 0:
                w = np.where(slot_ids[i] == mid)[0]
                if len(w):
                    cls = w[0]
            q[i, cls] += p[i, 6 + j]
    q = np.clip(q, 1e-12, None)
    q /= q.sum(1, keepdims=True)
    ent = -(q * np.log(q)).sum(1)
    return ent, q


def ctx_features(d, agent):
    store = {}
    h = agent.actor.ctx_net.register_forward_hook(
        lambda _m, _i, out: store.setdefault("ctx", out.detach())
    )
    with torch.no_grad():
        agent.actor(torch.as_tensor(d["obs1"], dtype=torch.float32))
    h.remove()
    return store["ctx"].numpy()


def fit_probe(X, y, m, tr, te, lams=(1e-4, 1e-3, 1e-2, 1e-1, 1.0), seed=0, iters=600):
    """Masked multinomial logistic probe. lambda chosen on an inner split of
    the fit set only (no test leakage); refit on the full fit set."""
    mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
    Xz = torch.as_tensor((X - mu) / sd, dtype=torch.float32)
    Y = torch.as_tensor(y)
    M = torch.as_tensor(m)
    g = np.random.default_rng(seed)
    inner = g.permutation(tr)
    cut = int(0.75 * len(inner))
    itr, iva = inner[:cut], inner[cut:]

    def run(idx_fit, idx_ev, lam):
        torch.manual_seed(seed)
        W = torch.zeros(X.shape[1], NCLS, requires_grad=True)
        b = torch.zeros(NCLS, requires_grad=True)
        opt = torch.optim.Adam([W, b], lr=0.05)
        xf, yf, mf = Xz[idx_fit], Y[idx_fit], M[idx_fit]
        for _ in range(iters):
            opt.zero_grad()
            lg = torch.where(mf, xf @ W + b, torch.full((len(idx_fit), NCLS), NEG))
            loss = torch.nn.functional.cross_entropy(lg, yf) + lam * (W * W).sum()
            loss.backward()
            opt.step()
        with torch.no_grad():
            xe, ye, me = Xz[idx_ev], Y[idx_ev], M[idx_ev]
            lg = torch.where(xe @ W + b > NEG, xe @ W + b, xe @ W + b)
            lg = torch.where(me, lg, torch.full((len(idx_ev), NCLS), NEG))
            return float(torch.nn.functional.cross_entropy(lg, ye))

    scores = {lam: run(itr, iva, lam) for lam in lams}
    best = min(scores, key=scores.get)
    return run(tr, te, best), best, scores


def nll_from_probs(q, y, idx):
    return float(-np.log(np.clip(q[idx, y[idx]], 1e-12, None)).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("checkpoint")
    args = ap.parse_args()
    d = np.load(args.npz)
    ckpt = load_checkpoint(args.checkpoint)
    cfg = Config(**ckpt["config"])
    agent = _load_showdown_agent(ckpt, cfg)

    y, m = labels_and_mask(d)
    n = len(y)
    battle = d["battle"]
    rng = np.random.default_rng(0)
    bids = np.unique(battle)
    rng.shuffle(bids)
    tr_b = set(bids[: int(0.7 * len(bids))].tolist())
    tr = np.array([i for i in range(n) if battle[i] in tr_b])
    te = np.array([i for i in range(n) if battle[i] not in tr_b])

    print(f"n={n}  train={len(tr)} test={len(te)}  battles={len(bids)}")
    print("label hist:", np.bincount(y, minlength=NCLS).tolist())
    print("legal-class count hist:", np.bincount(m.sum(1)).tolist())

    # A0 uniform over legal
    A0 = float(np.log(m[te].sum(1)).mean())
    # A1 marginal fitted on train, renormalised on mask
    prior = np.bincount(y[tr], minlength=NCLS) + 0.5
    prior = prior / prior.sum()
    q1 = np.where(m, prior[None, :], 0.0)
    q1 = q1 / q1.sum(1, keepdims=True)
    A1 = nll_from_probs(q1, y, te)
    # A3 oracle
    ent, q3 = oracle_pushforward(d, agent)
    A3 = float(ent[te].mean())
    A3_ce = nll_from_probs(q3, y, te)

    ctx = ctx_features(d, agent)
    A2, lam2, sc2 = fit_probe(ctx, y, m, tr, te)
    A2p, lam2p, sc2p = fit_probe(d["obs1"].astype(np.float32), y, m, tr, te)

    print()
    print(f"A0 uniform-over-legal (MASK BASELINE)   {A0:.4f} nats")
    print(f"A1 marginal prior, mask-renormalised    {A1:.4f} nats")
    print(f"A2 probe on FROZEN ctx (384)            {A2:.4f} nats   (lam={lam2})")
    print(f"A2' probe on raw obs (828)              {A2p:.4f} nats   (lam={lam2p})")
    print(f"A3 ORACLE floor E[H(pi|opp obs)]        {A3:.4f} nats")
    print(f"   (oracle CE against realised labels   {A3_ce:.4f})")
    print()
    print(f"HEADLINE  A1 - A2  = {A1 - A2:.4f} nats  (frozen-trunk probe)")
    print(f"          A1 - A2' = {A1 - A2p:.4f} nats  (raw-obs probe)")
    print(f"CEILING   A1 - A3  = {A1 - A3:.4f} nats")
    print(f"MASK TERM A0 - A1  = {A0 - A1:.4f} nats")
    print(f"inner-CV ctx: {sc2}")

    # battle-clustered se of the headline
    def per_battle(qA, qB):
        vals = []
        for b in np.unique(battle[te]):
            idx = te[battle[te] == b]
            vals.append(
                nll_from_probs(qA, y, idx) - nll_from_probs(qB, y, idx)
            )
        return np.asarray(vals)

    # recompute probe test probs for clustering
    print()
    # top-1 accuracy
    print("top-1 acc: marginal %.3f  oracle-argmax %.3f" % (
        (q1[te].argmax(1) == y[te]).mean(), (q3[te].argmax(1) == y[te]).mean()))
    # switch-vs-move sub-read
    isw = (y == SWITCH).astype(int)
    base = isw[tr].mean()
    Hb = -(base * np.log(base) + (1 - base) * np.log(1 - base))
    print(f"binary switch-vs-move: base rate {base:.4f}, H = {Hb:.4f} nats")


if __name__ == "__main__":
    main()
