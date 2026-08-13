"""D25's two BLOCKING pre-launch gates, at zero lanes
(configs/showdown_sp_actpred12m.yaml R0-12b and R0-13).

    python scripts/d25_gates.py verify      # R0-15-style attestation, run first
    python scripts/d25_gates.py r012b       # four capacity nulls on the s36 tape
    python scripts/d25_gates.py r013-bar    # the L6 LEARNED bar for §6
    python scripts/d25_gates.py r013-pool   # the historical-pool correction

Both encoder env vars are required (POKEMON_RL_ENCODER_V2=1
POKEMON_RL_ENCODER_IDS=1) and every read is offline — no server, no lanes.

SELF-CONTAINED ON PURPOSE. The design cycle's probe scripts live in
`results/d25/scripts/` and results/ is gitignored, so a gate that imported them
would be unreproducible the moment that directory is lost — which is exactly
what nearly happened to the tapes themselves. Everything the fits need is
re-implemented here from the ratified recipe, and `verify` proves the
re-implementation reproduces the frozen control atoms before any gate runs.

THE RECIPE, from §5, and it is not adjustable:
  * ONE frozen reference tape supplies observations, labels, legality masks and
    battle splits for every lane, so only the ctx encoder varies and the
    ablated arm's noise is common-mode;
  * L6 canonical label space with obs-derived legality, aliased rows dropped;
  * lambda FROZEN at 0.01, NO per-lane selection;
  * mean over 8 BATTLE-level 70/30 splits, seeds 0-7;
  * LBFGS max_iter >= 2000 with `||g||_2 < 1e-3` ASSERTED on every fit. At the
    first gate's 300 iterations 44 of 96 fits failed convergence and the
    control mean was inflated ~25%; 2000 and 8000 agree to four decimals. The
    grader fails loudly and NEVER silently drops or retries.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from eval_checkpoint import _load_showdown_agent  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.common.masking import masked_logits  # noqa: E402
from rl.networks.opp_action import N_CLASSES, OTHER_MOVE, SWITCH  # noqa: E402

D25 = REPO / "results" / "d25"
NEG = -1e8
NSPL = 8
LAM = 1e-2
MAX_ITER = 2000
GTOL = 1e-3            # R0-12c's asserted bound
LANES = (26, 27, 28, 50, 51)

# The frozen references, by sha256 (§5, §14B-2). `verify` checks these.
TAPE_SHA = {
    "s36": "3ffee9ba8f0c8fd826573ecb0a2334e249f73ae914720035f3fd839ffe074917",
    "s37": "58e64af1d57705bb5981c3465a03527244fd59ca113dabc35ca66af1dc39483f",
    "s35": "9388ef3efd184603d7a0379e69096c3116c1b102f9f7b202ca6d46808babe484",
}
# The frozen L6-native control distribution on the s36 primary reference (§5).
CONTROL_L6 = {26: 0.0217, 27: 0.0072, 28: 0.0201, 50: 0.0114, 51: 0.0145}
CONTROL_MEAN = 0.0150
# The same run's PER-SPLIT atoms at split seeds 0 and 1 (results/d25/
# d25_refreeze_s36.json). `verify` reproduces these EXACTLY rather than
# comparing against the 8-split mean — splits 0 and 1 happen to be the two
# lowest of the eight, so a mean-vs-mean check would look like a systematic
# defect and a per-split check is decisive.
CONTROL_SPLITS_01 = {
    26: (+0.0131, +0.0199), 27: (-0.0022, +0.0084), 28: (-0.0149, +0.0185),
    50: (+0.0088, +0.0081), 51: (+0.0051, +0.0099),
}
# §6's pre-registered bar, anchored on 12-class values. R0-13-bar re-derives it.
BAR_PREREG = 0.371
BAR_MULTIPLIER = 0.80  # Reviewer 1's example, frozen as the operative choice
                       # and disclosed as a free parameter, not a measurement.

# Observation layout, v2 + ids at OBS_DIM 828 (rl/envs/showdown.py).
OPP_MONS, MONB, OPP_ACT, OPP_MV, MD = 404, 34, 608, 624, 46


# --------------------------------------------------------------------------
# the probe
# --------------------------------------------------------------------------


def zs(A, tr):
    """Z-score on the FIT split only, dropping dead columns. Returns the live
    count — the de-dormancy diagnostic §5 records alongside every atom."""
    flat = A[tr].reshape(-1, A.shape[-1])
    s = flat.std(0)
    keep = s > 1e-8
    mu = flat[:, keep].mean(0)
    return (A[..., keep] - mu) / s[keep], int(keep.sum())


def prep(ctx, groups, tr):
    C, live = zs(ctx, tr)
    out = []
    for cls_idx, feat in groups:
        if feat is None:
            out.append((cls_idx, None, 0))
        else:
            F_, _ = zs(feat, tr)
            out.append((cls_idx, torch.as_tensor(F_, dtype=torch.float64), F_.shape[-1]))
    return torch.as_tensor(C, dtype=torch.float64), out, live


def fit_eval(C, groups, ncls, Y, M, fit, ev, lam, tag, conv):
    """One scorer-shaped probe fit. Scorer-shaped and not `Linear(ctx -> K)`
    because ctx is `ctx_net` over MAX-POOLED team features: opponent slot
    identity is destroyed before ctx exists, and the identical linear ctx probe
    cannot decode even the actor's OWN greedy action (gain -0.061)."""
    dc = C.shape[1]
    Ws = [torch.zeros(dc + d, dtype=torch.float64, requires_grad=True) for _, _, d in groups]
    bb = torch.zeros(ncls, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS(Ws + [bb], max_iter=MAX_ITER, history_size=20,
                            line_search_fn="strong_wolfe")

    def logits(idx):
        out = [None] * ncls
        for (cls_idx, F_, _), W in zip(groups, Ws):
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

    def closure():
        opt.zero_grad()
        loss = torch.nn.functional.cross_entropy(logits(fit), Y[fit]) + \
            lam * sum((W @ W) for W in Ws)
        loss.backward()
        return loss

    opt.step(closure)
    fit_loss = float(closure().detach())
    gnorm = float(torch.sqrt(sum((p.grad ** 2).sum() for p in Ws + [bb])))
    conv.append(dict(tag=tag, fit_loss=fit_loss, gnorm=gnorm))
    if not (np.isfinite(fit_loss) and gnorm < GTOL):
        raise AssertionError(
            f"NON-CONVERGED FIT {tag}: loss {fit_loss:.6f} ||g|| {gnorm:.3e} >= {GTOL:g}. "
            "R0-12c: the grader fails loudly and never silently drops or retries."
        )
    with torch.no_grad():
        lg = logits(ev)
        return float(torch.nn.functional.cross_entropy(lg, Y[ev]))


def split_by_battle(battle, seed):
    """BATTLE-level, never row-level (Reviewer 1 MUST-FIX 7): rows within a
    battle share the opponent's team, so a row split leaks it across the fold."""
    rng = np.random.default_rng(seed)
    b = np.unique(battle)
    rng.shuffle(b)
    trb = set(b[: int(0.7 * len(b))].tolist())
    tr = np.where(np.isin(battle, list(trb)))[0]
    te = np.where(~np.isin(battle, list(trb)))[0]
    assert not (set(battle[tr].tolist()) & set(battle[te].tolist())), "BATTLE BLEED"
    return tr, te


def nll(q, y, idx):
    return float(-np.log(np.clip(q[idx, y[idx]], 1e-300, None)).mean())


def marginal(y, m, ncls, tr):
    """A1: the mask-renormalised class marginal fitted on the train split. The
    manipulation check's g is the residual ABOVE this, which is the design
    against C3(a) — a head that fits P(class) and is called a belief."""
    pr = np.bincount(y[tr], minlength=ncls) + 0.5
    pr = pr / pr.sum()
    q = np.where(m, pr[None, :], 0.0)
    return q / q.sum(1, keepdims=True)


def ctx_features(obs, agent):
    store = {}
    handle = agent.actor.ctx_net.register_forward_hook(
        lambda _m, _i, out: store.setdefault("ctx", out.detach())
    )
    with torch.no_grad():
        agent.actor(torch.as_tensor(obs, dtype=torch.float32))
    handle.remove()
    return store["ctx"].numpy()


# --------------------------------------------------------------------------
# the tape
# --------------------------------------------------------------------------


def build(tape, ckpt_path):
    """Labels, oracle push-forward, obs-derived legality and features from one
    tape, in the L6 space. ALIASED ROWS ARE DROPPED HERE (`obs2[:, 5]`, the
    encoder's own aliased-turn flag) — 4.0%-10.3% across the five tapes, and
    every constant in the pre-registration was measured on the filtered set."""
    d = np.load(tape)
    ckpt = load_checkpoint(ckpt_path)
    agent = _load_showdown_agent(ckpt, Config(**ckpt["config"]))
    idx = np.where(d["obs2"][:, 5] < 0.5)[0]
    o1 = d["obs1"][idx].astype(np.float64)
    n = len(idx)
    kind, ident = d["kind2"][idx], d["ident2"][idx]
    own_mv = d["own_move_ids2"][idx]
    mvid = np.rint(o1[:, -4:] * 256).astype(np.int64)  # this row's own id suffix

    with torch.no_grad():
        p = torch.softmax(masked_logits(
            agent.actor(torch.as_tensor(d["obs2"][idx], dtype=torch.float32)),
            torch.as_tensor(d["mask2"][idx], dtype=torch.bool)), -1).numpy()

    y6 = np.full(n, OTHER_MOVE, np.int64)
    q6 = np.zeros((n, N_CLASSES))
    for i in range(n):
        if kind[i] == 0:
            y6[i] = SWITCH
        else:
            w = np.where(mvid[i] == ident[i])[0]
            y6[i] = w[0] if len(w) and ident[i] > 0 else OTHER_MOVE
        q6[i, SWITCH] = p[i, :6].sum()
        for j in range(4):
            mid = own_mv[i, j]
            w = np.where(mvid[i] == mid)[0] if mid > 0 else np.array([], int)
            q6[i, w[0] if len(w) else OTHER_MOVE] += p[i, 6 + j]
    q6 = np.clip(q6, 1e-12, None)
    q6 /= q6.sum(1, keepdims=True)

    m6 = np.zeros((n, N_CLASSES), bool)
    m6[:, :4] = mvid > 0
    m6[:, OTHER_MOVE] = True                                   # always legal
    m6[:, SWITCH] = (6 - 1 - np.rint(o1[:, 2] * 6).astype(int)) > 0
    assert m6[np.arange(n), y6].all(), "a realised label is marked illegal"

    feats = dict(
        mv=np.stack([o1[:, OPP_MV + j * MD:OPP_MV + (j + 1) * MD] for j in range(4)], 1),
        oa=o1[:, OPP_ACT:OPP_MV][:, None, :],
    )
    return dict(n=n, battle=d["battle"][idx], y6=y6, q6=q6, m6=m6, feats=feats,
                obs1=o1, obs2=d["obs2"][idx].astype(np.float64),
                keep=float(len(idx) / len(d["obs1"])), agent=agent)


def groups_l6(F):
    """Designer A's L6 scorer, class order {slot0..3, OTHER_MOVE, SWITCH}."""
    return [([0, 1, 2, 3], F["mv"]), ([OTHER_MOVE], None), ([SWITCH], F["oa"])]


def lane_ctx(obs1, lane):
    ckpt = load_checkpoint(REPO / f"runs/showdown_sp_struct12m_s{lane}/checkpoint.pt")
    agent = _load_showdown_agent(ckpt, Config(**ckpt["config"]))
    return ctx_features(obs1, agent).astype(np.float64)


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


# --------------------------------------------------------------------------
# verify — R0-15's attestation, and the re-implementation's own check
# --------------------------------------------------------------------------


def cmd_verify():
    print("=== FROZEN TAPE ATTESTATION (R0-15) ===")
    for name, want in TAPE_SHA.items():
        path = D25 / f"oppact_{name}ref.npz"
        got = sha256(path)
        flag = "OK" if got == want else "!! MISMATCH !!"
        print(f"  {name}: {got}  {flag}")
        assert got == want, f"{path} is not the frozen tape"
    print("\n=== FROZEN L6 CONTROL DISTRIBUTION (s36 primary reference) ===")
    print("  reproducing §5's atoms with this file's own probe, 2 splits of 8")
    D = build(D25 / "oppact_s36ref.npz", REPO / "runs/showdown_sp_struct50m_s36/ckpt_012000000.pt")
    Y, M = torch.as_tensor(D["y6"]), torch.as_tensor(D["m6"])
    G6 = groups_l6(D["feats"])
    conv = []
    got = {lane: [] for lane in LANES}
    for sp in range(2):  # 2 of the 8 is enough to catch a re-implementation bug
        tr, te = split_by_battle(D["battle"], sp)
        Ce, Ge, _ = prep(np.zeros((D["n"], 1)), G6, tr)
        a2e = fit_eval(Ce, Ge, N_CLASSES, Y, M, tr, te, LAM, f"abl.sp{sp}", conv)
        for lane in LANES:
            C, Gr, _ = prep(lane_ctx(D["obs1"], lane), G6, tr)
            a2s = fit_eval(C, Gr, N_CLASSES, Y, M, tr, te, LAM, f"s{lane}.sp{sp}", conv)
            got[lane].append(a2e - a2s)
    print(f"  {'lane':6s} {'frozen split 0/1':>22s} {'reproduced':>22s}  "
          f"{'8-split atom':>12s}")
    worst = 0.0
    for lane in LANES:
        want, have = CONTROL_SPLITS_01[lane], got[lane]
        worst = max(worst, max(abs(a - b) for a, b in zip(want, have)))
        print(f"  s{lane:<5d} {want[0]:+10.4f} {want[1]:+10.4f} "
              f"{have[0]:+11.4f} {have[1]:+10.4f}  {CONTROL_L6[lane]:+12.4f}")
        for a, b in zip(want, have):
            assert abs(a - b) < 2e-4, (lane, a, b)
    print(f"\n  max |reproduced - frozen| over 10 atoms: {worst:.2e}  PASS")
    print(f"  convergence: {len(conv)}/{len(conv)} fits under ||g|| < {GTOL:g}, "
          f"max {max(c['gnorm'] for c in conv):.2e}")
    print("  Splits 0 and 1 are the two LOWEST of the frozen eight, which is why")
    print("  this compares per-split and not against the 8-split mean.")


# --------------------------------------------------------------------------
# R0-12b — the four capacity nulls
# --------------------------------------------------------------------------


def pca(X, tr, dim):
    """Top-`dim` principal components, fitted on the FIT split only."""
    mu = X[tr].mean(0)
    _, _, Vt = np.linalg.svd(X[tr] - mu, full_matrices=False)
    return (X - mu) @ Vt[:dim].T


def cmd_r012b():
    print("=== R0-12b: CAPACITY NULLS on the frozen s36 tape, L6, max_iter 2000 ===")
    print("ACTION ON FAIL (any null >= the control mean +0.0150): the mechanism")
    print("letter drops to recorded-only and the rung is re-adjudicated.\n")
    D = build(D25 / "oppact_s36ref.npz", REPO / "runs/showdown_sp_struct50m_s36/ckpt_012000000.pt")
    print(f"tape: n={D['n']} rows, {len(np.unique(D['battle']))} battles, "
          f"kept {D['keep'] * 100:.1f}%")
    Y, M = torch.as_tensor(D["y6"]), torch.as_tensor(D["m6"])
    G6 = groups_l6(D["feats"])
    CTX = {lane: lane_ctx(D["obs1"], lane) for lane in LANES}
    live = {lane: int((CTX[lane].std(0) > 1e-8).sum()) for lane in LANES}
    print(f"live ctx units: {live}\n")

    conv, rows = [], {}
    t0 = time.time()
    for sp in range(NSPL):
        tr, te = split_by_battle(D["battle"], sp)
        Ce, Ge, _ = prep(np.zeros((D["n"], 1)), G6, tr)
        a2e = fit_eval(Ce, Ge, N_CLASSES, Y, M, tr, te, LAM, f"abl.sp{sp}", conv)

        def delta(name, ctx):
            C, Gr, _ = prep(ctx, G6, tr)
            a2s = fit_eval(C, Gr, N_CLASSES, Y, M, tr, te, LAM, f"{name}.sp{sp}", conv)
            rows.setdefault(name, []).append(a2e - a2s)

        # 1-2. PCA-384 of an OBSERVATION. Lane-independent by construction.
        delta("pca_obs_own", pca(D["obs1"], tr, 384))
        delta("pca_obs_opp", pca(D["obs2"], tr, 384))
        for lane in LANES:
            # 3. row-shuffled real ctx: same dimensionality, same marginals,
            #    ZERO state-correspondence.
            perm = np.random.default_rng(1000 + sp).permutation(D["n"])
            delta(f"shuffled_s{lane}", CTX[lane][perm])
            # 4. iid Gaussian at the lane's OWN live dimension.
            gen = np.random.default_rng(2000 + sp)
            delta(f"gauss_s{lane}", gen.standard_normal((D["n"], live[lane])))
            # the real trained ctx, refitted here as the in-run comparator
            delta(f"real_s{lane}", CTX[lane])
        print(f"  split {sp} done ({time.time() - t0:.0f}s cumulative)", flush=True)

    def summarise(prefix):
        keys = [k for k in rows if k.startswith(prefix)]
        vals = [float(np.mean(rows[k])) for k in sorted(keys)]
        return vals, float(np.mean(vals))

    print("\n  null                                   per-lane means            MEAN")
    verdicts = {}
    for prefix, label in (
        ("pca_obs_own", "PCA-384 of the RAW OBSERVATION"),
        ("pca_obs_opp", "PCA-384 of the OPPONENT'S OWN OBS (cheating)"),
        ("shuffled_", "row-shuffled real ctx"),
        ("gauss_", "iid Gaussian at the live dimension"),
        ("real_", "**real trained ctx**"),
    ):
        vals, mean = summarise(prefix)
        cells = " ".join(f"{v:+.4f}" for v in vals)
        print(f"  {label:44s} {cells:>28s}  {mean:+.4f}")
        verdicts[prefix] = mean

    print(f"\n  control mean (frozen, §5): {CONTROL_MEAN:+.4f}")
    failed = [k for k, v in verdicts.items() if k != "real_" and v >= CONTROL_MEAN]
    print(f"  nulls at or above it: {failed if failed else 'NONE'}")
    print(f"\n  VERDICT: {'FAIL' if failed else 'PASS'} — "
          + ("a capacity null reaches the control's level; the mechanism letter "
             "drops to recorded-only" if failed else
             "added uninformative dimensions COST held-out NLL; only a LEARNED "
             "ctx pays, so the letter stands as a mechanism read"))
    print(f"\n  convergence: all {len(conv)} fits under ||g|| < {GTOL:g}, "
          f"max {max(c['gnorm'] for c in conv):.2e}; total {time.time() - t0:.0f}s")
    out = D25 / "d25_r012b.json"
    out.write_text(json.dumps(dict(rows=rows, means=verdicts, conv=conv,
                                   live=live, control_mean=CONTROL_MEAN,
                                   failed=failed), indent=1))
    print(f"  -> {out}")


# --------------------------------------------------------------------------
# R0-13 (b) — the LEARNED bar, re-derived in the ADOPTED L6 space
# --------------------------------------------------------------------------


def cmd_r013_bar():
    print("=== R0-13: the LEARNED bar, re-derived in the ADOPTED L6 SPACE ===")
    print("§6's 0.371 is 0.80 x mean(g_frozen-probe) over FIVE 12-CLASS own-tape")
    print("values (0.474/0.452/0.523/0.410/0.458 -> 0.463). This re-derives the")
    print("same statistic in L6. The bar is a RATIO of two quantities scaled by")
    print("the same pool correction, so it is SCALE-INVARIANT and only the label")
    print("space can move it.\n")
    print("g_frozen-probe = (A1 - A2_ablated) / (A1 - A3), on each lane's OWN tape:")
    print("the gap closure a probe with NO ctx already achieves.\n")
    conv, out = [], {}
    for lane in LANES:
        t0 = time.time()
        D = build(D25 / f"oppact_s{lane}.npz",
                  REPO / f"runs/showdown_sp_struct12m_s{lane}/checkpoint.pt")
        Y, M = torch.as_tensor(D["y6"]), torch.as_tensor(D["m6"])
        G6 = groups_l6(D["feats"])
        gs = []
        for sp in range(NSPL):
            tr, te = split_by_battle(D["battle"], sp)
            a1 = nll(marginal(D["y6"], D["m6"], N_CLASSES, tr), D["y6"], te)
            a3 = float((-(D["q6"] * np.log(D["q6"])).sum(1))[te].mean())
            Ce, Ge, _ = prep(np.zeros((D["n"], 1)), G6, tr)
            a2e = fit_eval(Ce, Ge, N_CLASSES, Y, M, tr, te, LAM,
                           f"s{lane}.abl.sp{sp}", conv)
            gs.append((a1 - a2e) / (a1 - a3))
        out[lane] = gs
        print(f"  s{lane}: g = {np.mean(gs):.4f}  split sd {np.std(gs, ddof=1):.4f}  "
              f"[{min(gs):.4f},{max(gs):.4f}]  ({time.time() - t0:.0f}s)", flush=True)

    mean_g = float(np.mean([np.mean(v) for v in out.values()]))
    bar = BAR_MULTIPLIER * mean_g
    print(f"\n  L6 mean g_frozen-probe: {mean_g:.4f}   (12-class was 0.463)")
    print(f"  OPERATIVE LEARNED BAR = {BAR_MULTIPLIER} x {mean_g:.4f} = **{bar:.4f}**")
    print(f"  pre-registered value:  {BAR_PREREG:.4f}   "
          f"(moves by {bar - BAR_PREREG:+.4f}, {100 * (bar / BAR_PREREG - 1):+.1f}%)")
    print("\n  The 0.80 multiplier is NOT a measured constant — it is Reviewer 1's")
    print("  example, frozen as the operative choice and disclosed as a free")
    print("  parameter. Only the g values above are measurements.")
    print(f"\n  convergence: all {len(conv)} fits under ||g|| < {GTOL:g}, "
          f"max {max(c['gnorm'] for c in conv):.2e}")
    path = D25 / "d25_r013_bar.json"
    path.write_text(json.dumps(dict(g=out, mean_g=mean_g, bar=bar,
                                    multiplier=BAR_MULTIPLIER,
                                    prereg=BAR_PREREG, conv=conv), indent=1))
    print(f"  -> {path}")


# --------------------------------------------------------------------------
# R0-13 (a) — the historical-pool correction
# --------------------------------------------------------------------------

PUSH_EVERY, ROLLOUT = 150, 128 * 8
TOTAL_STEPS = 12_000_000


def real_push_ids():
    """The RETAINED push ids at 12M, from the REAL `_evict_index` — simulated
    against the shipped SnapshotPool rather than copied from a list, because
    "the lane's own 8M-12M checkpoints" describes a pool this repo does not
    build and would have reported that the ceiling barely moves."""
    from rl.selfplay.pool import SnapshotPool

    pool = SnapshotPool(20, 0.8)
    pool.members, pool.stats, pool.push_ids = [], [], []
    n_push = TOTAL_STEPS // (PUSH_EVERY * ROLLOUT)
    for k in range(n_push + 1):          # +1: the step-0 anchor, pushed before the loop
        pool.members.append(object())
        pool.stats.append([0.0, 0])
        pool.push_ids.append(k)
        if len(pool.members) > pool.pool_size:
            evict = pool._evict_index()
            del pool.members[evict], pool.stats[evict], pool.push_ids[evict]
    return list(pool.push_ids)


def push_step(push_id):
    """Push id k is taken at update k*PUSH_EVERY, i.e. step k*PUSH_EVERY*ROLLOUT.
    **k = 0 IS THE STEP-0 ANCHOR**, pushed before the first rollout — the
    design cycle's reconstruction used (k+1)*step and so mapped the random-init
    anchor onto a 0.15M checkpoint, which is where the header's "push ids
    spanning 0.15M-12M" came from. The anchor has no checkpoint on disk
    (they start at 200k), so it is proxied by the 200k one and the sensitivity
    is reported."""
    return push_id * PUSH_EVERY * ROLLOUT


def cmd_r013_pool():
    print("=== R0-13: HISTORICAL-POOL CORRECTION, real _evict_index schedule ===")
    print("Every §0 information number was measured against a ONE-MEMBER pool")
    print("(latest_prob 1.0) while training draws 20% HISTORICAL from a")
    print("20-member pool. NO-LAUNCH if the pool-corrected ORACLE WINDOW falls")
    print("below 0.60 nats or the pool-corrected REALISED gain below 0.30.\n")
    ids = real_push_ids()
    print(f"retained push ids ({len(ids)}): {ids}")
    print(f"  -> steps {push_step(ids[0]) / 1e6:.2f}M .. {push_step(ids[-1]) / 1e6:.2f}M")
    print("  push id 0 is the STEP-0 ANCHOR (never evicted); it has no checkpoint")
    print("  on disk and is proxied by ckpt_000200000. It carries 1/19 of the 20%")
    print("  historical mass, i.e. ~1.05% of the mixture.\n")

    def window(q, m):
        marg = q.mean(0)
        mq = np.where(m, marg[None, :], 0.0)
        mq /= mq.sum(1, keepdims=True)
        mq = np.clip(mq, 1e-12, None)
        return (float(-(q * np.log(mq)).sum(1).mean()),
                float(-(q * np.log(q)).sum(1).mean()))

    conv, out = [], {}
    for lane in LANES:
        t0 = time.time()
        run = REPO / f"runs/showdown_sp_struct12m_s{lane}"
        D = build(D25 / f"oppact_s{lane}.npz", run / "checkpoint.pt")
        n, m6 = D["n"], D["m6"]
        d = np.load(D25 / f"oppact_s{lane}.npz")
        keep = np.where(d["obs2"][:, 5] < 0.5)[0]
        obs2, mask2 = d["obs2"][keep], d["mask2"][keep]
        own_mv = d["own_move_ids2"][keep]
        mvid = np.rint(D["obs1"][:, -4:] * 256).astype(np.int64)

        def push6(p):
            q = np.zeros((n, N_CLASSES))
            q[:, SWITCH] = p[:, :6].sum(1)
            for i in range(n):
                for j in range(4):
                    mid = own_mv[i, j]
                    w = np.where(mvid[i] == mid)[0] if mid > 0 else np.array([], int)
                    q[i, w[0] if len(w) else OTHER_MOVE] += p[i, 6 + j]
            q = np.clip(q, 1e-12, None)
            return q / q.sum(1, keepdims=True)

        def policy(ckpt_path):
            ck = load_checkpoint(ckpt_path)
            ag = _load_showdown_agent(ck, Config(**ck["config"]))
            with torch.no_grad():
                return torch.softmax(masked_logits(
                    ag.actor(torch.as_tensor(obs2, dtype=torch.float32)),
                    torch.as_tensor(mask2, dtype=torch.bool)), -1).numpy()

        q_latest = D["q6"]
        a1s, a3s = window(q_latest, m6)
        hist = []
        for k in ids[:-1]:
            step = max(round(push_step(k) / 200_000) * 200_000, 200_000)
            hist.append(push6(policy(run / f"ckpt_{step:09d}.pt")))
        qbar = 0.8 * q_latest + 0.2 * np.mean(hist, 0)
        a1p, a3p = window(qbar, m6)

        # The pool-corrected REALISED gain: labels resampled from the mixture
        # each row actually faces, then the L6 with-ctx probe refitted on them.
        # Holding the realised numerator constant would assume the answer.
        rng = np.random.default_rng(lane)
        cdf = qbar.cumsum(1)
        y_pool = (rng.random((n, 1)) > cdf).sum(1).clip(0, N_CLASSES - 1).astype(np.int64)
        Yp, M = torch.as_tensor(y_pool), torch.as_tensor(m6)
        G6 = groups_l6(D["feats"])
        ctx = ctx_features(D["obs1"], D["agent"]).astype(np.float64)
        gains = []
        for sp in range(NSPL):
            tr, te = split_by_battle(D["battle"], sp)
            a1 = nll(marginal(y_pool, m6, N_CLASSES, tr), y_pool, te)
            C, Gr, _ = prep(ctx, G6, tr)
            a2s = fit_eval(C, Gr, N_CLASSES, Yp, M, tr, te, LAM,
                           f"s{lane}.pool.sp{sp}", conv)
            gains.append(a1 - a2s)
        out[lane] = dict(a1_1member=a1s, a3_1member=a3s, window_1member=a1s - a3s,
                         a1_pool=a1p, a3_pool=a3p, window_pool=a1p - a3p,
                         realised_pool=float(np.mean(gains)))
        print(f"  s{lane}: window {a1s - a3s:.4f} -> {a1p - a3p:.4f} "
              f"({100 * (a1p - a3p) / (a1s - a3s):.0f}%)   "
              f"pool-corrected realised gain {np.mean(gains):.4f}   "
              f"({time.time() - t0:.0f}s)", flush=True)

    win = float(np.mean([v["window_pool"] for v in out.values()]))
    win1 = float(np.mean([v["window_1member"] for v in out.values()]))
    real = float(np.mean([v["realised_pool"] for v in out.values()]))
    print(f"\n  1-member ORACLE WINDOW (mean of 5): {win1:.4f}")
    print(f"  POOL-CORRECTED WINDOW:              {win:.4f}  "
          f"({100 * win / win1:.0f}%; Reviewer 1's pre-stated prior was 86%)")
    print(f"  POOL-CORRECTED REALISED GAIN:       {real:.4f}  (1-member L6: 0.544)")
    ok = win >= 0.60 and real >= 0.30
    print(f"\n  NO-LAUNCH THRESHOLDS: window < 0.60 or realised < 0.30")
    print(f"  VERDICT: {'PASS' if ok else 'NO-LAUNCH'}")
    print("\n  CAVEAT, recorded at pre-registration: the tape's states come from")
    print("  latest-vs-latest play, so under pool play the state distribution")
    print("  shifts too. This is the right ORDER, not an exact number.")
    path = D25 / "d25_r013_pool.json"
    path.write_text(json.dumps(dict(lanes=out, push_ids=ids, window=win,
                                    window_1member=win1, realised=real,
                                    pass_=ok, conv=conv), indent=1))
    print(f"  -> {path}")


# --------------------------------------------------------------------------
# R0-10b — the gradient-ratio calibration, on the BUILT head
# --------------------------------------------------------------------------

GRID = (0.05, 0.1, 0.25, 0.5)          # R0-10's pre-stated sweep
BAND = (0.05, 1.5)                     # required at 600k / 6M / 12M
N_ROWS = 1024                          # D19-B's procedure, verbatim
STAGES = ("init", 600_000, 6_000_000, 12_000_000)
# D19-B's own table on s26, for orientation only. D25's aux gradient reaches
# the trunk through a WIDER path (ctx AND mon_net/move_net/species_emb/
# move_emb, the last two via B6a's new opponent-move pass), so its ratios
# cannot be reused — only its policy column is a like-for-like reference.
D19_POLICY = {"init": 0.005, 600_000: 0.434, 6_000_000: 0.324, 12_000_000: 1.094}
D19_AUX = {"init": 0.058, 600_000: 0.116, 6_000_000: 0.377, 12_000_000: 0.492}


def cmd_r010b():
    from rl.agents.ppo import clipped_surrogate_loss
    from rl.common.masking import masked_entropy
    from rl.networks.opp_action import aux_cross_entropy, canonicalise
    from rl.train import make_agent

    print("=== R0-10b: AUX/POLICY TRUNK-GRADIENT RATIO on the BUILT head ===")
    print("D19-B's procedure verbatim: 1,024 real tape rows, policy proxy =")
    print("the surrogate at ratio 1 with z-scored advantages, head at gain 0.01.")
    print("REQUIRED: coef x raw ratio in [0.05, 1.5] at 600k / 6M / 12M. A")
    print("coefficient outside the band is REMOVED from R0-10's grid; if the")
    print("whole grid is outside it, the rung does not launch.\n")

    lane = 26
    tape = np.load(D25 / f"oppact_s{lane}.npz")
    keep = np.where(tape["obs2"][:, 5] < 0.5)[0][:N_ROWS]
    obs = torch.as_tensor(tape["obs1"][keep], dtype=torch.float32)
    mask = torch.as_tensor(tape["mask1"][keep], dtype=torch.bool)
    choice = torch.as_tensor(np.stack([
        tape["kind2"][keep], tape["ident2"][keep], np.ones(len(keep), np.int64),
    ], -1))

    cfg_path = REPO / "configs/showdown_sp_actpred12m.yaml"
    from rl.common.config import load_config
    cfg = load_config(cfg_path)

    def fresh(step, seed=0):
        from types import SimpleNamespace

        import gymnasium as gym
        spaces = SimpleNamespace(
            observation_space=gym.spaces.Box(-1.0, 4.0, (828,), np.float32),
            action_space=gym.spaces.Discrete(10),
        )
        torch.manual_seed(seed)
        agent = make_agent(cfg, spaces)
        if step != "init":
            ck = load_checkpoint(REPO / f"runs/showdown_sp_struct12m_s{lane}"
                                        f"/ckpt_{step:09d}.pt")
            agent.actor.load_state_dict(ck["agent"]["actor"])
        return agent

    probe = fresh("init")
    target, allow, valid, stats = canonicalise(obs.double(), choice,
                                               probe.actor.tokenizer.id_off)
    # FREE CROSS-CHECK: the SHIPPED canonicaliser against the design cycle's
    # own label path, on the tape the frozen numbers were measured from.
    D = build(D25 / f"oppact_s{lane}.npz",
              REPO / f"runs/showdown_sp_struct12m_s{lane}/checkpoint.pt")
    agree = float((target.numpy() == D["y6"][:len(keep)]).mean())
    print(f"shipped canonicaliser vs the design cycle's labels: {agree:.4f} agree "
          f"on {len(keep)} rows")
    assert agree == 1.0, "the shipped label path disagrees with the frozen one"
    print(f"labelled {float(valid.float().mean()):.4f}, "
          f"illegal {stats['aux/illegal_label_frac']:.4f}, "
          f"collisions {stats['aux/frame_collision_frac']:.4f}\n")

    def trunk_of(agent):
        return [p for name, p in agent.actor.named_parameters()
                if not name.startswith(("scorer.", "slot_bias"))]

    # FIVE head draws per stage, and the RANGE is what gets quoted. The head is
    # freshly initialised for every D25 lane, so a one-draw ratio is a property
    # of a seed and not of the design — this chapter's named systematic error is
    # promoting the most favourable measured variant into the summary.
    rows = {}
    for step in STAGES:
        pols, auxs, ratios = [], [], []
        for seed in range(5):
            agent = fresh(step, seed)
            trunk = trunk_of(agent)
            logits, *feats = agent.actor(obs, return_features=True)
            logp = torch.log_softmax(masked_logits(logits, mask), -1)
            gen = torch.Generator().manual_seed(seed)
            actions = torch.distributions.Categorical(logits=logp).sample()
            lp = logp.gather(1, actions[:, None]).squeeze(-1)
            adv = torch.randn(len(keep), generator=gen)
            adv = (adv - adv.mean()) / (adv.std() + 1e-8)
            policy_loss, _, _ = clipped_surrogate_loss(lp, lp.detach(), adv, 0.2)
            g_pol = torch.autograd.grad(policy_loss, trunk, retain_graph=True,
                                        allow_unused=True)
            aux = aux_cross_entropy(agent.aux_head(*feats), target, allow, valid)
            g_aux = torch.autograd.grad(aux, [*trunk, *agent.aux_params],
                                        allow_unused=True)[:len(trunk)]

            def norm(gs):
                live = [g.norm() ** 2 for g in gs if g is not None]
                return float(torch.sqrt(sum(live))) if live else 0.0

            pols.append(norm(g_pol))
            auxs.append(norm(g_aux))
            ratios.append(auxs[-1] / pols[-1] if pols[-1] else float("inf"))
        rows[step] = dict(policy=float(np.mean(pols)), aux_raw=float(np.mean(auxs)),
                          raw_ratio=float(np.mean(ratios)),
                          raw_lo=float(min(ratios)), raw_hi=float(max(ratios)))
        label = "init" if step == "init" else f"{step / 1e6:g}M"
        print(f"  {label:>5s}: ||g_trunk policy|| {np.mean(pols):.4f} "
              f"(D19-B on s26: {D19_POLICY[step]:.3f})   "
              f"||g_trunk aux|| {np.mean(auxs):.4f} (D19-B: {D19_AUX[step]:.3f})   "
              f"raw ratio {min(ratios):.4f}-{max(ratios):.4f}")

    print(f"\n  coefficient x raw ratio (MEAN over 5 head draws), band "
          f"[{BAND[0]}, {BAND[1]}] at 600k / 6M / 12M:")
    keepers = []
    for coef in GRID:
        vals = [coef * rows[s]["raw_ratio"] for s in STAGES[1:]]
        ok = all(BAND[0] <= v <= BAND[1] for v in vals)
        if ok:
            keepers.append(coef)
        cells = "  ".join(f"{v:6.4f}" for v in vals)
        print(f"    coef {coef:<5g} {cells}   (init {coef * rows['init']['raw_ratio']:6.3f})   "
              f"{'IN BAND' if ok else 'OUT — removed from the R0-10 grid'}")
    print(f"\n  R0-10's grid after R0-10b: {keepers if keepers else 'EMPTY'}")
    print(f"  VERDICT: {'PASS' if keepers else '**NO-LAUNCH**'} — "
          + ("R0-10 sweeps these and takes the LARGEST value satisfying both its "
             "own conditions" if keepers else
             "the whole pre-stated grid is outside the band"))

    # The band is INHERITED from D19-B, whose own table is printed above. Apply
    # it to D19-B's OWN recommended coefficient and see what happens.
    print("\n  BEFORE ANY REMEDY, THE GATE ITSELF: the band [0.05, 1.5] is")
    print("  inherited from D19-B (§6, 'with the chosen coefficient'). Applied to")
    print("  D19-B's OWN table at D19-B's OWN recommended coefficient 0.1:")
    for step, ratio in ((600_000, 0.27), (6_000_000, 1.17), (12_000_000, 0.45)):
        v = 0.1 * ratio
        verdict = "IN" if BAND[0] <= v <= BAND[1] else "**OUT**"
        print(f"    {step / 1e6:>4g}M  {v:.3f}  {verdict}")
    print("  -> the band rejects the recommendation of the design that proposed")
    print("     it, at 2 of the 3 gated stages. It is not a criterion the design")
    print("     cycle ever met, which is a defect in the gate and not in D25.")

    binding = min(rows[s]["raw_ratio"] for s in STAGES[1:])
    loosest = max(rows[s]["raw_ratio"] for s in STAGES[1:])
    print(f"\n  ARITHMETIC, NOT A PROPOSAL: on the MEAN ratios the band is")
    print(f"  satisfied by coef in [{BAND[0] / binding:.2f}, {BAND[1] / loosest:.1f}]"
          f" — 3-500x the top of the pre-stated grid. Changing the grid or the")
    print(f"  band is a change to a RATIFIED pre-registration and is the")
    print(f"  maintainer's call under the standing 2-designers-2-reviews process.")
    print("\n  The init row is reported and NOT gated, exactly as R0-10b writes it:")
    print("  the policy gradient at init is genuinely tiny (a near-uniform head by")
    print("  design), so a large ratio there is expected and means nothing.")
    path = D25 / "d25_r010b.json"
    path.write_text(json.dumps(dict(rows={str(k): v for k, v in rows.items()},
                                    grid=list(GRID), band=list(BAND),
                                    keepers=keepers,
                                    coef_window=[BAND[0] / binding, BAND[1] / loosest]),
                               indent=1))
    print(f"  -> {path}")


# --------------------------------------------------------------------------
# smoke — read R0-10's arms
# --------------------------------------------------------------------------

SMOKE_COEF = {"c005": 0.05, "c010": 0.1, "c025": 0.25, "c050": 0.5}
# Control band, from the five comparator lanes (§7 S3 / §9 R1).
ENTROPY_BAND = (0.212, 0.284)
ANCHOR_MIN = 0.75


def cmd_smoke():
    import csv
    import subprocess

    print("=== R0-10 COEFFICIENT SMOKE — read of the arms present on disk ===")
    print("BLIND TO WIN RATE. Take the LARGEST coefficient satisfying BOTH")
    print("(a) g >= 0.25 and RISING, and (b) entropy and winrate_anchor in band.\n")
    rows = {}
    for tag, coef in SMOKE_COEF.items():
        run = REPO / "runs" / f"showdown_sp_actpred_smoke_{tag}"
        if not (run / "checkpoint.pt").exists():
            print(f"  {tag} (coef {coef:<5g}) — not run")
            continue
        hist = run / "history.csv"
        if not hist.exists():
            subprocess.run([sys.executable, str(REPO / "scripts/extract_history.py"),
                            str(run)], check=True, capture_output=True)
        data = list(csv.DictReader(hist.open()))

        def col(key):
            return np.array([float(r[key]) for r in data if r.get(key) not in (None, "")])

        aux, pol = col("aux/trunk_norm"), col("aux/policy_trunk_norm")
        # RATIO OF MEANS. A per-minibatch mean-of-ratios is Jensen-inflated
        # ~1.3-1.5x, which is how the offline proxy came to overstate itself.
        ratio = float(aux.mean() / pol.mean()) if len(pol) and pol.mean() else float("nan")
        half = len(aux) // 2
        late = float(aux[half:].mean() / pol[half:].mean()) if half else float("nan")
        ent, anchor = col("loss/entropy"), col("selfplay/winrate_anchor")
        loss = col("aux/loss")
        rows[tag] = dict(
            coef=coef, ratio=ratio, ratio_late=late,
            in_band=BAND[0] <= ratio <= BAND[1],
            entropy=float(ent[-1]) if len(ent) else float("nan"),
            anchor=float(anchor[-1]) if len(anchor) else float("nan"),
            aux_loss_first=float(loss[0]) if len(loss) else float("nan"),
            aux_loss_last=float(loss[-1]) if len(loss) else float("nan"),
            illegal=float(col("aux/illegal_label_frac").max()) if len(col("aux/illegal_label_frac")) else 0.0,
            collision=float(col("aux/frame_collision_frac").max()) if len(col("aux/frame_collision_frac")) else 0.0,
            labelled=float(col("aux/labelled_frac").mean()),
            aux_clip=float(col("aux/grad_clip_frac").mean()),
        )
        r = rows[tag]
        print(f"  {tag} (coef {coef:<5g})")
        print(f"    LIVE trunk ratio (ratio-of-means)  {ratio:.4f}  "
              f"[back half {late:.4f}]  {'IN' if r['in_band'] else 'OUT of'} "
              f"[{BAND[0]}, {BAND[1]}]")
        print(f"    aux/loss {r['aux_loss_first']:.4f} -> {r['aux_loss_last']:.4f}"
              f"   (log 6 = 1.792)")
        print(f"    loss/entropy {r['entropy']:.4f} (control band "
              f"{ENTROPY_BAND[0]}-{ENTROPY_BAND[1]}, a BACK-HALF statistic — at "
              f"100k steps this is a smoke read, not a gate)")
        print(f"    selfplay/winrate_anchor {r['anchor']:.4f} (R1 wants >= {ANCHOR_MIN} by 4M)")
        print(f"    aux/grad_clip_frac {r['aux_clip']:.4f}  labelled {r['labelled']:.4f}")
        print(f"    illegal {r['illegal']:.6f}  collisions {r['collision']:.6f}"
              f"   {'OK' if r['illegal'] == 0 == r['collision'] else '** HARD FAIL **'}")
    if not rows:
        print("\nNo arms on disk yet.")
        return
    print("\n  NOT COMPUTED HERE: condition (a)'s g, which needs a tape collected")
    print("  from each arm's own checkpoint (A1 and A3 are re-derived on it at")
    print("  read time so no constant can drift). `aux/loss` above is the head's")
    print("  CE on fresh on-policy rows and is the right thing to watch falling,")
    print("  but it is NOT g and must not be reported as g.")
    ok = [t for t, r in rows.items() if r["in_band"] and r["illegal"] == 0 == r["collision"]]
    print(f"\n  arms with a live ratio in band and clean label health: "
          f"{[f'{t} ({SMOKE_COEF[t]})' for t in ok] or 'NONE'}")
    (D25 / "d25_smoke.json").write_text(json.dumps(rows, indent=1))
    print(f"  -> {D25 / 'd25_smoke.json'}")


COMMANDS = {"verify": cmd_verify, "r012b": cmd_r012b, "r013-bar": cmd_r013_bar,
            "r013-pool": cmd_r013_pool, "r010b": cmd_r010b, "smoke": cmd_smoke}


if __name__ == "__main__":
    from rl.envs.showdown import OBS_DIM

    if OBS_DIM != 828:
        raise SystemExit(
            f"OBS_DIM is {OBS_DIM}, not 828: set POKEMON_RL_ENCODER_V2=1 and "
            "POKEMON_RL_ENCODER_IDS=1 in the process environment"
        )
    torch.set_num_threads(4)
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        raise SystemExit(f"usage: {sys.argv[0]} {{{'|'.join(COMMANDS)}}}")
    COMMANDS[sys.argv[1]]()
