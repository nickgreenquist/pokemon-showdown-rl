# VENDORED 2026-08-29 (CLEANUP B1) byte-identical from results/design_ch2/scripts/z1_1.py
# — that directory is gitignored, so this tracked copy is the only one a
# fresh clone can resolve. The original stays as the executed artifact.
"""Z1-1 (CALIBRATED offline trunk-fraction screen) + Z1-2 (tau calibration).

Zero lanes, zero server, read-only on runs/. Screens D28's candidate synthetic
aux task BEFORE compute is spent.

WHY THE CALIBRATION EXISTS (rl/agents/ppo.py:554-561): offline fitted-head
trunk-fraction proxies were previously measured in this repo to be DOMINATED by
the head's last-layer weight scale (13.6x spread with the actor held fixed), so
a raw offline number CANNOT be compared to a live band. Per DESIGN2.md sec.1 /
ch2_review_2.md MF-5 the fix is: run the IDENTICAL offline procedure on two
reference tasks whose LIVE answers are banked, and read the candidate only
through that mapping.

  live anchors (results/design_ch2/trunk_fraction_bins.json, recomputed
  2026-08-16): D25 real task  late-bin 0.50-0.62, run-mean 0.62-0.68
                D25-P shuffled late-bin 0.05-0.09, run-mean 0.16-0.18

THE PROCEDURE, identical for every (tape, task) pair — any deviation voids the
calibration:
  1. head-input features (ctx, opp_moves, opp_bench) from the tape's OWN
     checkpoint over the tape's obs1 rows, trunk frozen, cached (no_grad).
  2. a FRESH width-96 OppActionHead, init_head(gain=0.01) (D25's
     aux_head_gain), fitted to convergence on the task's labels over the
     standard valid rows, train split only. Same optimizer (Adam), same lr
     schedule, same epochs, same batch size, same init seed for every task.
  3. ONE gradient read through the FULL graph: re-forward the actor WITH grad
     over a large fixed batch of valid rows, compute the fitted head's masked
     CE, autograd over (trunk params = actor minus scorer./slot_bias) + (head
     params), and report
         f_offline = ||grad_trunk|| / ||grad_(trunk+head)||
     with ppo.py:_aux_gradient's own norm arithmetic
     (norm of the stack of per-parameter grad norms).

TASKS
  A  real     D25's hard L6 labels via opp_action.canonicalise      (anchor HIGH)
  B  shuffled A's labels permuted within exact-allow classes,
              opp_action.shuffle_within_allow — D25-P's construction (anchor LOW)
  C  synth    the D28 candidate AS AMENDED (DESIGN2 sec.1 / review-2 MF-1):
              ONE shared w_move across the four opponent-move slots,
              s_j = <w_move, raw_opp_move_block_j>; separate w_global for
              class 4 (OTHER_MOVE, over the global block) and w_bench for
              class 5 (SWITCH, over the pooled opponent-mon blocks). Per-class
              score standardisation (unit variance over the tape) then
              y ~ Categorical(softmax(masked(tau * s_std, allow))), drawn once.
  C0 synth-r0 the SUPERSEDED r0 construction (four INDEPENDENT w_j) — run at
              the reference tau only, to measure review-2 MF-1 rather than
              argue it.
  D  ownact   the REJECTED candidate, for the record: the agent's own action.
              The tapes carry no seat-1 action, so this is the actor's GREEDY
              action under mask1 (stated in the results json as such).

READ: does f_offline(A) separate from f_offline(B) in the same direction as the
live anchors? Then where does C (per tau) and D land, as a fraction of the A-B
gap. If A and B do NOT separate, Z1-1 is void as a screen and that is the
finding.

Run (CPU only, single thread, nice'd — 4 training lanes are live):
  POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nice -n 10 \
    /opt/anaconda3/envs/pokemon-showdown-rl/bin/python \
    results/design_ch2/scripts/z1_1.py --out results/design_ch2/z1_1_results.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import numpy as np
import torch

REPO = "/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl"
sys.path.insert(0, REPO)
sys.path.insert(0, REPO + "/scripts")

if os.environ.get("POKEMON_RL_ENCODER_V2") != "1" or os.environ.get(
    "POKEMON_RL_ENCODER_IDS"
) != "1":
    raise SystemExit(
        "set POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 before importing "
        "rl.envs.showdown — the tapes are 828-wide v2+ids"
    )

from eval_checkpoint import _load_showdown_agent  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.common.masking import masked_logits  # noqa: E402
from rl.envs.showdown import OPP_CHOICE_ALIASED, OPP_CHOICE_PRESENT  # noqa: E402
from rl.networks.opp_action import (  # noqa: E402
    N_CLASSES,
    OTHER_MOVE,
    SWITCH,
    OppActionHead,
    aux_cross_entropy,
    canonicalise,
    marginal_nll,
    shuffle_within_allow,
)

# ---- fixed seeds and fixed procedure constants ---------------------------
W_SEED = 20260817          # module-constant: the synthetic readout W. Identical
                           # across tapes and (in the arm) across lanes.
LABEL_SEED = 4242          # the once-per-tape synthetic label draw
SHUFFLE_SEED = 909         # task B's permutation
FIT_SEED = 1234            # head init + minibatch order, IDENTICAL per task
SPLIT_SEED = 0             # battle-clustered 70/30 split (final_measure.py's)
GRAD_SEED = 77             # the gradient-read row subset

HEAD_GAIN = 0.01           # D25's aux_head_gain
FIT_LR = 1e-3
FIT_LR_FINE = 1e-4
FIT_BATCH = 512
GRAD_ROWS = 4096           # rows in the single full-graph gradient read

TAPES = [
    ("s52", "results/d25/oppact_s52.npz", "D25 lane (aux-trained, seed 52)"),
    ("s26", "results/d25/oppact_s26.npz", "Rung-2 comparator lane (struct12m, seed 26)"),
    ("s36ref", "results/d25/oppact_s36ref.npz", "reference (struct50m s36 @12M, no aux)"),
    ("s53", "results/d25/oppact_s53.npz", "D25 lane (aux-trained, seed 53)"),
]

# ---- raw-obs block accessors (offsets come from the net's own tokenizer) --
_REVEALED, _FAINTED, _IS_ACTIVE = 0, 2, 3  # within a raw (mon_dim+1) opp block


def raw_blocks(obs: torch.Tensor, layout):
    """(global, opp_move_blocks, pooled_opp_mon_block) — the RAW obs blocks the
    head's six entities are built from.

    The bench pool mirrors EntityDeepSetsNet._aux_features: max over the
    REVEALED, non-fainted, non-active opponent mon blocks, all-zero when no
    such slot exists. Max (not mean) so the synthetic readout sees the same
    pooling nonlinearity the entity path applies."""
    glob = obs[:, : layout.global_dim]
    mv = obs[:, layout.opp_move_off : layout.id_off].view(
        obs.shape[0], 4, layout.move_dim
    )
    mons = obs[:, layout.opp_mon_off : layout.opp_act_off].view(
        obs.shape[0], 6, layout.mon_dim + 1
    )
    live = (
        (mons[:, :, _REVEALED] > 0)
        & (mons[:, :, _FAINTED] <= 0)
        & (mons[:, :, _IS_ACTIVE] <= 0)
    )
    floor = torch.full_like(mons, torch.finfo(mons.dtype).min)
    pooled = torch.where(live.unsqueeze(-1), mons, floor).amax(dim=1)
    pooled = torch.where(
        live.any(dim=1, keepdim=True), pooled, torch.zeros_like(pooled)
    )
    return glob, mv, pooled


def synth_scores(obs, layout, allow, valid, shared: bool):
    """The synthetic class scores, standardised. `shared=True` is the AMENDED
    task (one w_move over the four slots); `shared=False` is the superseded r0
    construction (four independent w_j), kept only so MF-1 is measured."""
    glob, mv, pooled = raw_blocks(obs, layout)
    g = torch.Generator().manual_seed(W_SEED)
    if shared:
        w_move = torch.randn(layout.move_dim, generator=g)
        s_mv = mv @ w_move                                   # (N, 4)
    else:
        w_move = torch.randn(4, layout.move_dim, generator=g)
        s_mv = torch.einsum("njd,jd->nj", mv, w_move)
    w_glob = torch.randn(layout.global_dim, generator=g)
    w_bench = torch.randn(layout.mon_dim + 1, generator=g)
    s_glob = glob @ w_glob                                   # (N,)
    s_bench = pooled @ w_bench                               # (N,)

    def std(x, sel):
        """zero-mean / unit-variance over the tape's contributing entries."""
        vals = x[sel]
        if vals.numel() < 2:
            return x
        mu, sd = vals.mean(), vals.std()
        return (x - mu) / sd.clamp(min=1e-6)

    v = valid.unsqueeze(-1)
    # the four move slots share ONE scale (the readout is shared, so a
    # per-slot scale would break the permutation equivariance MF-1 restored)
    s_mv = std(s_mv, (allow[:, :4] & v).bool())
    s_glob = std(s_glob, valid)
    s_bench = std(s_bench, valid & allow[:, SWITCH])
    return torch.cat([s_mv, s_glob.unsqueeze(-1), s_bench.unsqueeze(-1)], dim=-1)


def synth_labels(scores, allow, valid, tau, seed):
    """y ~ Categorical(softmax(masked(tau*s, allow))), drawn ONCE. Returns
    (target, sampler_entropy_over_valid, class_marginal)."""
    logits = masked_logits(tau * scores, allow)
    p = torch.softmax(logits, dim=-1)
    g = torch.Generator().manual_seed(seed)
    target = torch.multinomial(p, 1, generator=g).squeeze(-1)
    ent = -(p.clamp_min(1e-12).log() * p).sum(-1)
    ent = float(ent[valid].mean()) if int(valid.sum()) else float("nan")
    return target, ent, class_marginal(target, valid)


def class_marginal(target, valid):
    v = target[valid]
    if v.numel() == 0:
        return [0.0] * N_CLASSES
    return (torch.bincount(v, minlength=N_CLASSES).double() / v.numel()).tolist()


# ---- the fixed fit + gradient-read procedure ------------------------------
def fit_head(feats, target, allow, valid, tr, epochs):
    """A fresh width-96 OppActionHead fitted to convergence. IDENTICAL
    optimizer / schedule / epochs / batch / init seed for every task."""
    ctx, opp_moves, opp_bench = feats
    torch.manual_seed(FIT_SEED)
    head = OppActionHead(ctx.shape[1], opp_moves.shape[2], sizes=[96])
    head.init_head(HEAD_GAIN)
    opt = torch.optim.Adam(head.parameters(), lr=FIT_LR, eps=1e-5)
    gen = torch.Generator().manual_seed(FIT_SEED)
    curve = []
    n = tr.numel()
    for ep in range(epochs):
        if ep == int(0.75 * epochs):
            for grp in opt.param_groups:
                grp["lr"] = FIT_LR_FINE
        perm = tr[torch.randperm(n, generator=gen)]
        tot, seen = 0.0, 0
        for i in range(0, n, FIT_BATCH):
            idx = perm[i : i + FIT_BATCH]
            logits = head(ctx[idx], opp_moves[idx], opp_bench[idx])
            loss = aux_cross_entropy(
                logits, target[idx], allow[idx], valid[idx]
            )
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            tot += float(loss.detach()) * idx.numel()
            seen += idx.numel()
        if ep % 25 == 0 or ep == epochs - 1:
            curve.append((ep, tot / seen))
    return head, curve


@torch.no_grad()
def evaluate(head, feats, target, allow, valid, idx):
    ctx, opp_moves, opp_bench = feats
    logits = head(ctx[idx], opp_moves[idx], opp_bench[idx])
    ce = float(aux_cross_entropy(logits, target[idx], allow[idx], valid[idx]))
    pred = masked_logits(logits, allow[idx]).argmax(-1)
    v = valid[idx]
    acc = float((pred[v] == target[idx][v]).double().mean()) if int(v.sum()) else float("nan")
    return ce, acc


def grad_read(actor, head, obs, target, allow, valid, rows):
    """The single FULL-GRAPH gradient read. Re-forwards the actor with grad,
    then autograds the fitted head's loss over (trunk params, head params).
    Norm arithmetic is ppo.py:_aux_gradient's verbatim."""
    trunk = [
        p for name, p in actor.named_parameters()
        if not name.startswith(("scorer.", "slot_bias"))
    ]
    params = trunk + list(head.parameters())
    trunk_ids = {id(p) for p in trunk}
    _, ctx, mv, bench = actor(obs[rows], return_features=True)
    loss = aux_cross_entropy(head(ctx, mv, bench), target[rows], allow[rows], valid[rows])
    grads = torch.autograd.grad(loss, params, allow_unused=True)
    present = [g for g in grads if g is not None]
    on_trunk = [g for p, g in zip(params, grads) if g is not None and id(p) in trunk_ids]
    total = float(torch.norm(torch.stack([g.norm() for g in present])))
    tnorm = float(torch.norm(torch.stack([g.norm() for g in on_trunk]))) if on_trunk else 0.0
    return tnorm / total if total > 0 else float("nan"), tnorm, total, float(loss)


# ---- tape preparation -----------------------------------------------------
def prepare(path):
    d = np.load(path)
    obs = torch.as_tensor(d["obs1"], dtype=torch.float32)
    mask1 = torch.as_tensor(d["mask1"])
    ckpt_path = str(d["checkpoint"])
    ck = load_checkpoint(ckpt_path)
    agent = _load_showdown_agent(ck, Config(**ck["config"]))
    actor = agent.actor
    actor.eval()

    # The tapes predate the (kind, id, flags) seam, so reconstruct `flags`:
    # PRESENT iff a real order named an entity (kind >= 0); ALIASED from the
    # OPPONENT's own aliased-turn bit obs2[:,5] — final_measure.py:36's filter.
    kind = torch.as_tensor(d["kind2"])
    ident = torch.as_tensor(d["ident2"])
    aliased = torch.as_tensor(d["obs2"][:, 5] >= 0.5)
    flags = torch.where(kind >= 0, torch.full_like(kind, OPP_CHOICE_PRESENT), torch.zeros_like(kind))
    flags = flags | torch.where(aliased, torch.full_like(kind, OPP_CHOICE_ALIASED), torch.zeros_like(kind))
    choice = torch.stack([kind, ident, flags], dim=-1)
    target, allow, valid, stats = canonicalise(obs, choice, actor.tokenizer)

    with torch.no_grad():
        chunks = [actor(obs[i : i + 1024], return_features=True) for i in range(0, obs.shape[0], 1024)]
    feats = tuple(torch.cat([c[k] for c in chunks], dim=0) for k in (1, 2, 3))

    battle = d["battle"]
    rng = np.random.default_rng(SPLIT_SEED)
    bids = np.unique(battle)
    rng.shuffle(bids)
    tr_b = set(bids[: int(0.7 * len(bids))].tolist())
    in_tr = torch.as_tensor(np.isin(battle, list(tr_b)))
    tr = (in_tr & valid).nonzero(as_tuple=True)[0]
    te = (~in_tr & valid).nonzero(as_tuple=True)[0]

    def pick(pool, seed, k=GRAD_ROWS):
        g = torch.Generator().manual_seed(seed)
        k = min(k, pool.numel())
        return pool[torch.randperm(pool.numel(), generator=g)[:k]]

    # PRIMARY grad-read batch: a fixed random subset of ALL valid rows.
    # Secondary batches split it by the fit's own train/test partition — a
    # fitted head sits at its optimum on train rows and not on held-out ones,
    # and the live number is measured on fresh on-policy rows, so the two are
    # reported separately rather than assumed equal.
    rows = pick(valid.nonzero(as_tuple=True)[0], GRAD_SEED)
    return dict(
        obs=obs, mask1=mask1, actor=actor, feats=feats, target=target, allow=allow,
        valid=valid, stats=stats, tr=tr, te=te, rows=rows, ckpt=ckpt_path,
        rows_tr=pick(tr, GRAD_SEED + 1, 2048), rows_te=pick(te, GRAD_SEED + 2, 2048),
        n=obs.shape[0],
    )


def own_action_task(t):
    """Task D: the agent's own action, mapped into the six-class head.
    move slot j -> class j; any switch -> SWITCH; OTHER_MOVE is unused and
    never labelled (it stays always-legal so the >=1-legal assert holds).
    Own legality comes from mask1, NOT from D25's opponent-derived allow."""
    with torch.no_grad():
        logits = torch.cat(
            [t["actor"](t["obs"][i : i + 2048]) for i in range(0, t["n"], 2048)], dim=0
        )
        act = masked_logits(logits, t["mask1"]).argmax(-1)
    target = torch.where(act >= 6, act - 6, torch.full_like(act, SWITCH))
    allow = torch.zeros_like(t["allow"])
    allow[:, :4] = t["mask1"][:, 6:10]
    allow[:, OTHER_MOVE] = True
    allow[:, SWITCH] = t["mask1"][:, :6].any(dim=1)
    return target, allow


def run_task(name, tape, target, allow, epochs, extra=None):
    t0 = time.time()
    head, curve = fit_head(tape["feats"], target, allow, tape["valid"], tape["tr"], epochs)
    tr_ce, tr_acc = evaluate(head, tape["feats"], target, allow, tape["valid"], tape["tr"])
    te_ce, te_acc = evaluate(head, tape["feats"], target, allow, tape["valid"], tape["te"])
    f, tn, tot, gl = grad_read(
        tape["actor"], head, tape["obs"], target, allow, tape["valid"], tape["rows"]
    )
    f_tr = grad_read(tape["actor"], head, tape["obs"], target, allow,
                     tape["valid"], tape["rows_tr"])[0]
    f_te = grad_read(tape["actor"], head, tape["obs"], target, allow,
                     tape["valid"], tape["rows_te"])[0]
    rec = dict(
        task=name,
        train_loss_final=curve[-1][1],
        # convergence evidence: the loss at the half-way epoch and just before
        # the lr drop, against the final. A task whose fit is still moving at
        # the end would void the "fitted to convergence" clause.
        train_loss_at_half=curve[len(curve) // 2][1],
        train_loss_curve=curve,
        train_ce=tr_ce, train_acc=tr_acc,
        test_ce=te_ce, test_acc=te_acc,
        marginal_nll_train=marginal_nll(target, allow, tape["valid"] & _mask_of(tape["tr"], tape["n"])),
        marginal_nll_test=marginal_nll(target, allow, tape["valid"] & _mask_of(tape["te"], tape["n"])),
        class_marginal=class_marginal(target, tape["valid"]),
        f_offline=f, grad_trunk=tn, grad_total=tot, grad_read_loss=gl,
        f_offline_train_rows=f_tr, f_offline_test_rows=f_te,
        grad_rows=int(tape["rows"].numel()),
        head_last_layer_wnorm=float(head.scorer[-1].weight.norm()),
        seconds=round(time.time() - t0, 1),
    )
    if extra:
        rec.update(extra)
    print(
        f"  {name:<14} trainloss {rec['train_loss_final']:.4f} "
        f"testCE {te_ce:.4f} acc {te_acc:.3f} A1 {rec['marginal_nll_test']:.4f} "
        f"f_offline {f:.4f}  ({rec['seconds']}s)",
        flush=True,
    )
    return rec


def _mask_of(idx, n):
    m = torch.zeros(n, dtype=torch.bool)
    m[idx] = True
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/design_ch2/z1_1_results.json")
    ap.add_argument("--epochs", type=int, default=160)
    ap.add_argument("--tapes", default="s52,s26,s36ref")
    ap.add_argument("--taus", default="1.0,2.0,4.0,8.0")
    args = ap.parse_args()
    torch.set_num_threads(1)

    want = args.tapes.split(",")
    taus = [float(x) for x in args.taus.split(",")]
    out = dict(
        meta=dict(
            epochs=args.epochs, lr=FIT_LR, lr_fine=FIT_LR_FINE, batch=FIT_BATCH,
            head_gain=HEAD_GAIN, width=96, grad_rows=GRAD_ROWS,
            seeds=dict(W=W_SEED, label=LABEL_SEED, shuffle=SHUFFLE_SEED,
                       fit=FIT_SEED, split=SPLIT_SEED, grad=GRAD_SEED),
            live_anchors=dict(d25_late=[0.50, 0.62], d25_run_mean=[0.62, 0.68],
                              d25p_late=[0.05, 0.09], d25p_run_mean=[0.16, 0.18]),
            d25_oracle_entropy_nats=0.250,
            d25_class_marginal_pct=[43.6, 27.3, 13.6, 5.2, 3.0, 7.2],
            own_action_source="actor greedy under mask1 (tapes carry no seat-1 action)",
        ),
        tapes={},
    )

    for key, path, desc in TAPES:
        if key not in want:
            continue
        print(f"== {key}  {desc}", flush=True)
        tape = prepare(path)
        print(
            f"  rows {tape['n']} valid {int(tape['valid'].sum())} "
            f"train {tape['tr'].numel()} test {tape['te'].numel()} "
            f"ckpt {tape['ckpt']}",
            flush=True,
        )
        rows = []

        # --- Z1-2: the tau curve (label entropy only; no fitting) ----------
        scores = synth_scores(
            tape["obs"], tape["actor"].tokenizer, tape["allow"], tape["valid"], shared=True
        )
        tau_curve = []
        for tau in [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0]:
            _, ent, marg = synth_labels(scores, tape["allow"], tape["valid"], tau, LABEL_SEED)
            tau_curve.append(dict(tau=tau, oracle_entropy=ent, class_marginal=marg))
        # the tau whose sampler entropy matches D25's measured 0.250 nats
        tau_star = _match_tau(scores, tape["allow"], tape["valid"], 0.250)

        # --- A: the real task ---------------------------------------------
        rows.append(run_task("A_real", tape, tape["target"], tape["allow"], args.epochs))

        # --- B: shuffled within exact-allow classes ------------------------
        g = torch.Generator().manual_seed(SHUFFLE_SEED)
        shuf, sstats = shuffle_within_allow(tape["target"], tape["allow"], tape["valid"], g)
        rows.append(run_task("B_shuffled", tape, shuf, tape["allow"], args.epochs,
                             extra=dict(shuffle_stats=sstats)))

        # --- C: the synthetic pointer task, per tau ------------------------
        for tau in sorted(set(taus + [round(tau_star, 4)])):
            tgt, ent, marg = synth_labels(scores, tape["allow"], tape["valid"], tau, LABEL_SEED)
            rows.append(run_task(f"C_synth_tau{tau:g}", tape, tgt, tape["allow"], args.epochs,
                                 extra=dict(tau=tau, oracle_entropy=ent,
                                            is_entropy_matched=abs(tau - tau_star) < 1e-6)))

        # --- C0: the superseded r0 per-slot construction, at tau* ----------
        s0 = synth_scores(tape["obs"], tape["actor"].tokenizer, tape["allow"],
                          tape["valid"], shared=False)
        tgt0, ent0, _ = synth_labels(s0, tape["allow"], tape["valid"], tau_star, LABEL_SEED)
        rows.append(run_task(f"C0_synth_r0_tau{tau_star:g}", tape, tgt0, tape["allow"],
                             args.epochs, extra=dict(tau=tau_star, oracle_entropy=ent0,
                                                     note="superseded r0: four INDEPENDENT w_j")))

        # --- D: own action (rejected candidate, for the record) ------------
        dt, da = own_action_task(tape)
        rows.append(run_task("D_ownaction", tape, dt, da, args.epochs,
                             extra=dict(allow_source="mask1 (own legality)")))

        def anchors(field):
            a = [r[field] for r in rows if r["task"] == "A_real"][0]
            b = [r[field] for r in rows if r["task"] == "B_shuffled"][0]
            return a, b

        for field, out_key in (("f_offline", "pos_in_AB_gap"),
                               ("f_offline_test_rows", "pos_in_AB_gap_test_rows")):
            fa, fb = anchors(field)
            for r in rows:
                r[out_key] = (r[field] - fb) / (fa - fb) if abs(fa - fb) > 1e-9 else None
        fa, fb = anchors("f_offline")
        fa_te, fb_te = anchors("f_offline_test_rows")
        out["tapes"][key] = dict(
            desc=desc, checkpoint=tape["ckpt"], n_rows=tape["n"],
            n_valid=int(tape["valid"].sum()), n_train=int(tape["tr"].numel()),
            n_test=int(tape["te"].numel()), canonicalise_stats=tape["stats"],
            tau_star_entropy_matched=tau_star, tau_curve=tau_curve, tasks=rows,
            f_A=fa, f_B=fb, AB_gap=fa - fb,
            f_A_test_rows=fa_te, f_B_test_rows=fb_te, AB_gap_test_rows=fa_te - fb_te,
        )
        with open(args.out, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"  -> wrote {args.out}", flush=True)


def _match_tau(scores, allow, valid, target_ent, lo=0.05, hi=200.0):
    """bisect tau so the sampler's own entropy over valid rows hits target."""
    def ent(tau):
        p = torch.softmax(masked_logits(tau * scores, allow), dim=-1)
        e = -(p.clamp_min(1e-12).log() * p).sum(-1)
        return float(e[valid].mean())
    if ent(hi) > target_ent:
        return hi
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if ent(mid) > target_ent:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


if __name__ == "__main__":
    main()
