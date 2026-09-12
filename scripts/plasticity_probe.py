"""Capacity-loss / plasticity probe — Lyle et al. 2204.09560 Def 1, in the
Moalla et al. 2405.00662 trainability style, on our own gen-1 checkpoints.

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/plasticity_probe.py --out results/plasticity_probe

    # self-test, tiny sizes, a few seconds, writes nothing durable:
    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/plasticity_probe.py --dry

THE QUESTION. `docs/research_reports/MODEL_SCALE_2026-09-12.md` §D'-3 reads our
srank99 / dormancy trajectories and then says the literature will not let them
carry the weight: Lyle 2303.01486 §5.2 falsifies feature rank AND sparsity as
causal plasticity indicators, and Lyle 2204.09560 Cor. 1 predicts exactly our
collapse as the SPARSE-REWARD limit of a healthy learner. So a low srank is
consistent with two different worlds:

  (i) the parameters can no longer be optimised at all  -> plasticity loss,
      which argues for width + L2-toward-init (ARM W);
  (ii) the representation is a sparse-reward artifact of a net that would
      still fit anything you asked it to -> width is unlikely to pay, and the
      levers are dense targets / gae_lambda 1.0.

Def 1 separates them: freeze NOTHING, take the checkpoint's CURRENT parameters
as an initialisation, and measure how far a FIXED optimisation budget can drive
the loss on FRESH RANDOM targets over inputs from our own domain, against a
fresh random init of the same architecture under the identical budget.

PROTOCOL (frozen before the run; the full write-up is
docs/research_reports/PLASTICITY_PROBE_2026-09-12.md).

INPUTS. `results/d22/{obs_s35,obs_s36,obs_s37}.npz` — seat-1 obs and action
masks at every decision of 200 self-play mirror battles per D22 lane
(`scripts/d22_collect_obs.py`). Pooled: 19,218 rows x 828. One fixed shuffle
(seed 20260912), 80/20 train/held-out. NOTE the obs come from the D22
struct50m lanes, not from the probed checkpoints: the probe needs "inputs from
our own domain", not each checkpoint's own on-policy measure, and one shared
input set is what makes the checkpoints comparable to each other.

TARGETS (drawn once, identical for every parameter set).
  critic / `randnet`  : outputs of a FRESH EntityDeepSetsNet critic (target
                        seed 9001, init_head(1.0)) on the same obs, then
                        standardised with the TRAIN split's mean/std. Loss MSE.
  critic / `iid`      : one i.i.d. N(0,1) scalar per row (generator seed 4242).
                        Pure memorisation; the held-out leg is ~1.0 by
                        construction and is reported only as the control that
                        proves it. Loss MSE.
  actor  / `randpol`  : logits of a FRESH EntityDeepSetsNet actor (target seed
                        9002, built exactly as PPOAgent builds an actor),
                        STANDARDISED over legal entries with the train split's
                        mean/std, then masked-softmaxed. Loss = forward
                        KL(target || student) over legal actions.
                        The standardisation is not cosmetic: the shipped init
                        rescales the actor's final layer by gain 0.01, so a
                        fresh actor's raw logits have std ~0.003 and the raw
                        target distribution is the uniform one to three
                        decimals (measured) — there would be nothing to fit.
                        `init_head` zeroes every bias, so the logits are
                        exactly gain * (W . f) and the standardisation cancels
                        the gain: the target is the same object at gain 0.01
                        and at 1.0. Standardised, it has mean entropy ~1.53
                        nats against ~1.75 for uniform-over-legal and mean
                        max-prob ~0.39 (exact values in the output's
                        `meta.target_meta`).

CONDITIONS, per parameter set:
  FULL       every parameter trainable (Def 1 proper).
  HEAD-ONLY  trunk frozen, final linear only. Critic: `head` (384->1). Actor:
             `scorer[-1]` (256->1) plus `slot_bias` (10), i.e. the whole
             readout that sits on the per-action features. Implemented by
             caching the frozen net's input to that final layer once and
             training the layer on the cache — mathematically identical to
             freezing, and it is what makes the condition free.
             HEAD-ONLY starts from the checkpoint's OWN head weights: Def 1
             asks what the current parameters can do, not what a re-rolled
             head could do.
  Controls   two FRESH inits of the same architecture (seeds 20260912 /
             20260913, built exactly as PPOAgent builds them: actor
             init_head(0.01), critic init_head(1.0)), and the earliest rungs
             available (engine_a1_s66 @500k and @1M).

BUDGET, identical for every condition: Adam, batch 256, 6000 steps (= 100
epochs of the train split), at BOTH lr 2.5e-4 (the runs' lr) and lr 1e-3.
Calibrated 2026-09-12 on a dry run: a fresh-init FULL critic goes 1.051 ->
0.062 held-out MSE on `randnet` by step 2000 (17x, and flat from ~1500), a
fresh-init FULL actor 0.226 -> 0.0047 held-out KL by step 1000 — the budget
had to reach clearly sub-initial loss on the fresh init, and 6000 is 3x past
the point where that is already true, so the 100% mark reads asymptotic fit
while the 25% / 50% marks read optimisation SPEED. Batch order is a fixed
stream per (part, family, lr), SHARED across parameter sets, so every
comparison is paired. Losses are reported at 0 / 25 / 50 / 100% of budget, on
the full train split and the full held-out split.

TWO DEVIATIONS FROM LYLE, both disclosed with every number. (1) Lyle's
empirical capacity read uses 50,000 gradient steps; ours is 6,000, which is
what fits one CPU process in the window. A 6k budget is a strictly harder test
of trainability than a 50k one (less time to recover), so a "no capacity loss"
verdict from it is conservative and a "capacity lost" verdict would need the
longer budget before it could be called asymptotic. (2) Def 1 is an
EXPECTATION over target draws f ~ P_F; we take ONE draw per family (a second
independent draw of the critic's random-network family, `randnet2`, runs at
the run's own lr as a cheap read on how much of the level is the draw). Pairing
the same draws across every parameter set removes the draw from the
BETWEEN-checkpoint comparison, which is the comparison the probe exists for.

DISCLOSURE that travels with every actor number: a trained actor is a sharp
policy, so its step-0 forward KL to a near-uniform random target is an order of
magnitude above a fresh init's (measured: ~10 vs ~0.2 nats). Def 1 asks exactly
"what can a fixed budget do from HERE", so that distance is part of the
measurement and not a bug — but the raw final loss must be read next to the
step-0 loss and the fraction-of-initial-remaining, both of which the output
carries. The critic legs do not have this asymmetry (a trained critic's outputs
and a unit-variance target start ~1 MSE apart, same as a fresh init's).

ALSO REPORTED, so the trainability numbers sit next to the instrument the repo
already uses: srank99 (smallest k with 99% of the singular mass) and the
participation ratio of each net's penultimate features on the held-out obs,
float64, via `scripts/d22_dormant_rank.py::srank99` — the same hardened
function that backs `results/d22/effective_rank_float64.csv`. Two feature sets
per net: `ctx` (the ctx_net output, 384-d — directly comparable to the D22
CSV) and `head_in` (the actual input to the trained final layer: for the
critic that IS ctx; for the actor the 256-d scorer penultimate over all
B x 10 action pairs).

Nets are constructed by `scripts/d22_dormant_rank.py::build`, i.e.
`EntityDeepSetsNet(828, 10|1, **ckpt.config.agent.trunk_kwargs)` + that
checkpoint's own `agent[part]` state dict — identical in effect to
`scripts/ch3_eval.py::_load_member_spaces` (make_agent -> PPOAgent builds the
two nets with exactly these arguments), without needing spaces or an optimiser.
Every checkpoint's trunk_kwargs is asserted equal to the reference before use;
a checkpoint that differs is SKIPPED and named in the output, never silently
rebuilt at another shape.

No server, no battles, one process, torch threads pinned to 1.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.append(str(Path(__file__).parent))

from d22_dormant_rank import build, srank99  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.masking import masked_logits  # noqa: E402

# Every checkpoint below must carry exactly this trunk shape (asserted, not
# assumed): the probe compares parameter sets of ONE architecture.
REF_TRUNK_KWARGS = {
    "species_vocab": 152, "move_vocab": 166, "embed_dim": 64, "entity_dim": 128,
    "pool": "max", "ctx_sizes": [384, 384], "scorer_sizes": [256],
    "value_sizes": [384, 384],
}

CHECKPOINTS = [
    ("100M_final", "runs/showdown_sp_100m_s112/ckpt_100000008.pt"),
    ("100M_rung12M", "runs/showdown_sp_100m_s112/ckpt_012000023.pt"),
    ("50M_s66", "runs/showdown_sp_batch50m_s66/ckpt_050000000.pt"),
    ("50M_s75", "runs/showdown_sp_batch50m_s75/ckpt_050000000.pt"),
    ("50M_s83", "runs/showdown_sp_batch50m_s83/ckpt_050000000.pt"),
    ("early_500k", "runs/engine_a1_s66/ckpt_000500006.pt"),
    ("early_1M", "runs/engine_a1_s66/ckpt_001000017.pt"),
]
FRESH_SEEDS = [("fresh_a", 20260912), ("fresh_b", 20260913)]
# Distinct streams for the two nets of one fresh init; large offset so no
# fresh actor ever shares a seed with another fresh critic.
PART_SEED_OFFSET = {"actor": 0, "critic": 7_000_000}
# Batch-order streams, fixed and SHARED across parameter sets so that every
# comparison between checkpoints is paired. Not hash() — string hashing is
# salted per process (PYTHONHASHSEED), which would make the run irreproducible.
ORDER_SEEDS = {
    ("critic", "randnet", 2.5e-4): 101, ("critic", "randnet", 1e-3): 102,
    ("critic", "iid", 2.5e-4): 103, ("critic", "iid", 1e-3): 104,
    ("actor", "randpol", 2.5e-4): 105, ("actor", "randpol", 1e-3): 106,
    ("critic", "randnet2", 2.5e-4): 107,
}

OBS_SEEDS = (35, 36, 37)
SPLIT_SEED = 20260912
TARGET_SEED_CRITIC = 9001
TARGET_SEED_CRITIC2 = 9003
TARGET_SEED_ACTOR = 9002
TARGET_SEED_IID = 4242
LRS = (2.5e-4, 1e-3)
# Def 1 is an expectation over target draws; we can afford one second draw of
# the critic's random-network family, at the run's own lr, as a cheap read on
# how much of the level is the draw.
FAMILY_LRS = {"randnet": LRS, "iid": LRS, "randpol": LRS, "randnet2": (2.5e-4,)}
EVAL_CHUNK = 1024


# --------------------------------------------------------------------------
# data + targets
# --------------------------------------------------------------------------
def load_obs(root: Path, limit: int = 0):
    obs, masks = [], []
    for seed in OBS_SEEDS:
        d = np.load(root / f"obs_s{seed}.npz")
        obs.append(d["obs"])
        masks.append(d["masks"])
    obs = torch.from_numpy(np.concatenate(obs))
    masks = torch.from_numpy(np.concatenate(masks))
    gen = torch.Generator().manual_seed(SPLIT_SEED)
    perm = torch.randperm(len(obs), generator=gen)
    obs, masks = obs[perm], masks[perm]
    if limit:
        obs, masks = obs[:limit], masks[:limit]
    n_train = int(0.8 * len(obs))
    return obs, masks, n_train


def fresh_net(part: str, seed: int):
    """A fresh init exactly as PPOAgent makes one: construct, then init_head at
    the gain that part uses (0.01 policy / 1.0 value; ppo.py L645-646)."""
    torch.manual_seed(seed)
    net = build(part, REF_TRUNK_KWARGS)
    net.init_head(0.01 if part == "actor" else 1.0)
    return net


@torch.no_grad()
def batched(net, x, chunk=2048):
    net.eval()
    return torch.cat([net(x[i:i + chunk]) for i in range(0, len(x), chunk)])


def make_targets(obs, masks, n_train):
    """All three target families, drawn once and shared by every parameter set."""
    tgt = {}

    for key, seed in (("randnet", TARGET_SEED_CRITIC), ("randnet2", TARGET_SEED_CRITIC2)):
        v = batched(fresh_net("critic", seed), obs).squeeze(-1)
        mu, sd = v[:n_train].mean(), v[:n_train].std()
        tgt[key] = ((v - mu) / sd, {"seed": seed, "raw_mean": float(mu), "raw_std": float(sd)})

    g = torch.Generator().manual_seed(TARGET_SEED_IID)
    tgt["iid"] = (torch.randn(len(obs), generator=g), {})

    lg = batched(fresh_net("actor", TARGET_SEED_ACTOR), obs)
    legal = lg[masks]
    mu, sd = legal.mean(), legal.std()
    p = torch.softmax(masked_logits((lg - mu) / sd, masks), dim=-1)
    ent = -(torch.where(masks, p * p.clamp_min(1e-12).log(), torch.zeros_like(p))).sum(-1)
    tgt["randpol"] = (p, {
        "raw_logit_mean": float(mu), "raw_logit_std": float(sd),
        "target_entropy_nats": float(ent.mean()),
        "uniform_entropy_nats": float(masks.sum(1).float().log().mean()),
        "target_max_prob": float(p.max(-1).values.mean()),
    })
    return tgt


# --------------------------------------------------------------------------
# losses
# --------------------------------------------------------------------------
def mse(pred, target):
    return ((pred.squeeze(-1) - target) ** 2).mean()


def fwd_kl(logits, mask, target_p):
    """KL(target || student) over legal actions. Illegal positions contribute
    exactly 0 (the repo's where-guard pattern, rl/common/masking) — never
    0 * -1e8 arithmetic."""
    logq = torch.log_softmax(masked_logits(logits, mask), dim=-1)
    terms = torch.where(
        mask, target_p * (target_p.clamp_min(1e-12).log() - logq), torch.zeros_like(logq)
    )
    return terms.sum(-1).mean()


# --------------------------------------------------------------------------
# the two training conditions
# --------------------------------------------------------------------------
@torch.no_grad()
def eval_full(net, part, x, mask, y):
    net.eval()
    tot, n = 0.0, 0
    for i in range(0, len(x), EVAL_CHUNK):
        xb = x[i:i + EVAL_CHUNK]
        if part == "critic":
            loss = mse(net(xb), y[i:i + EVAL_CHUNK])
        else:
            loss = fwd_kl(net(xb), mask[i:i + EVAL_CHUNK], y[i:i + EVAL_CHUNK])
        tot += float(loss) * len(xb)
        n += len(xb)
    net.train()
    return tot / n


def run_full(net, part, data, lr, steps, batch, order_seed, marks):
    """Def 1 proper: every parameter trainable, fixed budget."""
    xtr, mtr, ytr, xte, mte, yte = data
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    gen = torch.Generator().manual_seed(order_seed)
    out = {}

    def snap(step):
        out[str(step)] = {
            "train": eval_full(net, part, xtr, mtr, ytr),
            "heldout": eval_full(net, part, xte, mte, yte),
        }

    snap(0)
    net.train()
    for step in range(1, steps + 1):
        idx = torch.randint(0, len(xtr), (batch,), generator=gen)
        opt.zero_grad(set_to_none=True)
        if part == "critic":
            loss = mse(net(xtr[idx]), ytr[idx])
        else:
            loss = fwd_kl(net(xtr[idx]), mtr[idx], ytr[idx])
        loss.backward()
        opt.step()
        if step in marks:
            snap(step)
    return out


@torch.no_grad()
def head_features(net, part, x, chunk=2048):
    """The exact input tensor the final linear sees, captured by a forward
    pre-hook rather than by re-deriving the forward (which would be a second
    copy of the trunk's logic, free to drift). Critic -> (N, 384) into `head`;
    actor -> (N, 10, 256) into `scorer[-1]`."""
    net.eval()
    final = net.head if part == "critic" else net.scorer[-1]
    grabbed = []
    handle = final.register_forward_pre_hook(lambda _m, inp: grabbed.append(inp[0].detach()))
    for i in range(0, len(x), chunk):
        net(x[i:i + chunk])
    handle.remove()
    return torch.cat(grabbed)


def run_head(net, part, feats_tr, feats_te, data, lr, steps, batch, order_seed, marks):
    """Trunk frozen, final linear only — on the cached frozen features, which
    is the same function and a fraction of the cost."""
    _xtr, mtr, ytr, _xte, mte, yte = data
    final = net.head if part == "critic" else net.scorer[-1]
    head = torch.nn.Linear(final.in_features, 1)
    head.load_state_dict(final.state_dict())
    params = list(head.parameters())
    slot_bias = None
    if part == "actor":
        slot_bias = net.slot_bias.detach().clone().requires_grad_(True)
        params.append(slot_bias)
    opt = torch.optim.Adam(params, lr=lr)
    gen = torch.Generator().manual_seed(order_seed)

    def logits_of(f):
        return head(f).squeeze(-1) + slot_bias

    def ev(feats, mask, target):
        with torch.no_grad():
            tot, n = 0.0, 0
            for i in range(0, len(feats), EVAL_CHUNK):
                fb = feats[i:i + EVAL_CHUNK]
                if part == "critic":
                    loss = mse(head(fb), target[i:i + EVAL_CHUNK])
                else:
                    loss = fwd_kl(logits_of(fb), mask[i:i + EVAL_CHUNK], target[i:i + EVAL_CHUNK])
                tot += float(loss) * len(fb)
                n += len(fb)
            return tot / n

    out = {}

    def snap(step):
        out[str(step)] = {"train": ev(feats_tr, mtr, ytr), "heldout": ev(feats_te, mte, yte)}

    snap(0)
    for step in range(1, steps + 1):
        idx = torch.randint(0, len(feats_tr), (batch,), generator=gen)
        opt.zero_grad(set_to_none=True)
        if part == "critic":
            loss = mse(head(feats_tr[idx]), ytr[idx])
        else:
            loss = fwd_kl(logits_of(feats_tr[idx]), mtr[idx], ytr[idx])
        loss.backward()
        opt.step()
        if step in marks:
            snap(step)
    return out


# --------------------------------------------------------------------------
@torch.no_grad()
def rank_report(net, part, xte, where):
    """srank99 + participation ratio, float64, of (a) the ctx_net output — the
    D22 instrument, comparable to results/d22/effective_rank_float64.csv — and
    (b) the true input to the trained final layer."""
    net.eval()
    ctx = []
    handle = net.ctx_net.register_forward_hook(lambda _m, _i, out: ctx.append(out.detach()))
    feats = head_features(net, part, xte)
    handle.remove()
    ctx = torch.cat(ctx)
    s_ctx, pr_ctx = srank99(ctx, f"{where} ctx")
    flat = feats.reshape(-1, feats.shape[-1])
    s_hd, pr_hd = srank99(flat, f"{where} head_in")
    return {
        "srank99_ctx": s_ctx, "pr_ctx": round(pr_ctx, 2), "ctx_width": ctx.shape[-1],
        "srank99_head_in": s_hd, "pr_head_in": round(pr_hd, 2),
        "head_in_width": feats.shape[-1],
    }


def parameter_sets(dry: bool):
    """(name, kind, spec) for every parameter set, checkpoints first. A
    checkpoint whose trunk_kwargs differ from the reference is SKIPPED."""
    sets, skipped = [], []
    ckpts = CHECKPOINTS[:1] if dry else CHECKPOINTS
    for name, path in ckpts:
        if not Path(path).exists():
            skipped.append({"name": name, "path": path, "why": "missing"})
            continue
        tk = load_checkpoint(path)["config"]["agent"]["trunk_kwargs"]
        if tk != REF_TRUNK_KWARGS:
            skipped.append({"name": name, "path": path, "why": f"trunk_kwargs {tk}"})
            continue
        sets.append((name, "checkpoint", path))
    for name, seed in (FRESH_SEEDS[:1] if dry else FRESH_SEEDS):
        sets.append((name, "fresh", seed))
    return sets, skipped


def get_net(kind, spec, part, state_cache=None):
    """A pristine net for this parameter set — a FRESH object every call, so a
    FULL run can never inherit the parameters a previous FULL run moved."""
    if kind == "fresh":
        return fresh_net(part, spec + PART_SEED_OFFSET[part])
    key = (spec, part)
    if state_cache is None or key not in state_cache:
        sd = load_checkpoint(spec)["agent"][part]
        if state_cache is not None:
            state_cache[key] = sd
    else:
        sd = state_cache[key]
    net = build(part, REF_TRUNK_KWARGS)
    net.load_state_dict(sd)
    return net


@torch.no_grad()
def linear_probe_check(sets, obs, n_train, target, out_path):
    """Closed-form control for the HEAD-ONLY condition: the least-squares
    readout of the frozen critic features, solved directly (ridge lambda 1e-6,
    float64) instead of by 6,000 Adam steps. If the two disagree, HEAD-ONLY was
    measuring the optimiser and not the representation. Reported as held-out R^2
    so the number reads as "how much of a random target the frozen features
    linearly explain"."""
    y = target.double()
    ytr, yte = y[:n_train], y[n_train:]
    rows = {}
    for name, kind, spec in sets:
        net = get_net(kind, spec, "critic")
        f = head_features(net, "critic", obs).double()
        ones = torch.ones(len(f), 1, dtype=torch.float64)
        ftr = torch.cat([f[:n_train], ones[:n_train]], 1)
        fte = torch.cat([f[n_train:], ones[n_train:]], 1)
        a = ftr.T @ ftr + 1e-6 * torch.eye(ftr.shape[1], dtype=torch.float64)
        w = torch.linalg.solve(a, ftr.T @ ytr)
        mse_te = float(((fte @ w - yte) ** 2).mean())
        rows[name] = {
            "train_mse": float(((ftr @ w - ytr) ** 2).mean()),
            "heldout_mse": mse_te,
            "heldout_r2": 1.0 - mse_te / float(yte.var()),
            "feature_std": float(f[n_train:].std()),
        }
        print(f"  {name:12s} lstsq heldout MSE {mse_te:.4f}  R2 {rows[name]['heldout_r2']:.3f}",
              flush=True)
    out_path.write_text(json.dumps(
        {"note": "closed-form control for HEAD_ONLY, critic / randnet targets",
         "heldout_target_var": float(yte.var()), "rows": rows}, indent=2) + "\n")
    print(f"wrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results/plasticity_probe")
    ap.add_argument("--linear-probe", action="store_true",
                    help="run ONLY the closed-form HEAD-ONLY control (see "
                         "linear_probe_check) and write linear_probe_check.json")
    ap.add_argument("--obs-root", default="results/d22")
    ap.add_argument("--steps", type=int, default=6000)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--dry", action="store_true",
                    help="self-test: 512 rows, 20 steps, one checkpoint, one "
                         "fresh seed; exercises every path in a few seconds "
                         "and writes to <out>/dry_run.json")
    ap.add_argument("--force", action="store_true", help="overwrite the output JSON")
    args = ap.parse_args()

    torch.set_num_threads(1)
    from rl.envs.showdown import OBS_DIM
    assert OBS_DIM == 828, f"expected the 828-d id-suffix encoder, got {OBS_DIM}"

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / ("dry_run.json" if args.dry else "probe.json")
    if out_path.exists() and not args.force and not args.linear_probe:
        raise SystemExit(f"refusing to overwrite {out_path} — pass --force")

    steps = 20 if args.dry else args.steps
    batch = 64 if args.dry else args.batch
    marks = {steps // 4, steps // 2, steps}

    obs, masks, n_train = load_obs(Path(args.obs_root), limit=512 if args.dry else 0)
    targets = make_targets(obs, masks, n_train)
    xtr, mtr, xte, mte = obs[:n_train], masks[:n_train], obs[n_train:], masks[n_train:]

    sets, skipped = parameter_sets(args.dry)
    print(f"rows {len(obs)} (train {n_train} / held-out {len(obs) - n_train}), "
          f"{len(sets)} parameter sets, {steps} steps x batch {batch}", flush=True)
    if args.linear_probe:
        linear_probe_check(sets, obs, n_train, targets["randnet"][0],
                           out_dir / "linear_probe_check.json")
        return
    for s in skipped:
        print(f"  SKIPPED {s['name']}: {s['why']}", flush=True)

    families = {"critic": ("randnet", "randnet2", "iid"), "actor": ("randpol",)}
    runs, ranks, state_cache = [], {}, {}
    t_start = time.time()
    for name, kind, spec in sets:
        ranks[name] = {}
        for part in ("critic", "actor"):
            base = get_net(kind, spec, part, state_cache)
            ranks[name][part] = rank_report(base, part, xte, f"{name} {part}")
            f_all = head_features(base, part, obs)
            f_tr, f_te = f_all[:n_train], f_all[n_train:]
            for family in families[part]:
                y, _ = targets[family]
                data = (xtr, mtr, y[:n_train], xte, mte, y[n_train:])
                for lr in FAMILY_LRS[family]:
                    order = ORDER_SEEDS[(part, family, lr)]
                    t0 = time.time()
                    hd = run_head(base, part, f_tr, f_te, data, lr, steps,
                                  batch, order, marks)
                    net = get_net(kind, spec, part, state_cache)
                    fl = run_full(net, part, data, lr, steps, batch, order, marks)
                    for cond, losses in (("FULL", fl), ("HEAD_ONLY", hd)):
                        runs.append({"param_set": name, "kind": kind, "part": part,
                                     "family": family, "condition": cond, "lr": lr,
                                     "losses": losses})
                    print(f"  {name:12s} {part:6s} {family:8s} lr {lr:g}  "
                          f"FULL {fl[str(steps)]['heldout']:.5f} / "
                          f"HEAD {hd[str(steps)]['heldout']:.5f}  "
                          f"[{time.time() - t0:.0f}s]", flush=True)
                    del net
            del f_all, f_tr, f_te, base
        state_cache.clear()
        print(f"{name} done [{time.time() - t_start:.0f}s]", flush=True)

    meta = {
        "protocol": "Lyle 2204.09560 Def 1 / Moalla 2405.00662 trainability style",
        "report": "docs/research_reports/PLASTICITY_PROBE_2026-09-12.md",
        "rows_total": len(obs), "rows_train": n_train, "rows_heldout": len(obs) - n_train,
        "obs_source": [f"results/d22/obs_s{s}.npz" for s in OBS_SEEDS],
        "split_seed": SPLIT_SEED, "steps": steps, "batch": batch, "lrs": list(LRS),
        "marks": sorted(marks), "optimizer": "Adam", "torch_threads": 1,
        "trunk_kwargs": REF_TRUNK_KWARGS,
        "target_meta": {k: v[1] for k, v in targets.items()},
        "target_seeds": {"critic_randnet": TARGET_SEED_CRITIC,
                         "actor_randpol": TARGET_SEED_ACTOR, "critic_iid": TARGET_SEED_IID},
        "skipped": skipped,
        "checkpoints": {n: s for n, k, s in sets if k == "checkpoint"},
        "fresh_seeds": {n: s for n, k, s in sets if k == "fresh"},
        "git_sha": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                  text=True).stdout.strip(),
        "wall_sec": round(time.time() - t_start, 1),
        "dry": args.dry,
    }
    out_path.write_text(json.dumps({"meta": meta, "srank": ranks, "runs": runs}, indent=2) + "\n")
    print(f"wrote {out_path} [{meta['wall_sec']}s]")


if __name__ == "__main__":
    main()
