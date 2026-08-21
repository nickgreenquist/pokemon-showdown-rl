"""D28's zero-information synthetic aux task (DESIGN2 §1, chapter 2).

The dosable control for D25's one open caveat ("a generic auxiliary gradient
of matched size would have helped too"): the aux head trains on labels drawn
from a FIXED random linear readout of the raw obs blocks its entities are
built from — zero opponent-ACTION information by construction (the readout
never sees `opp_choice`; scores are a function of the observation alone).
Honest scope, stated wherever D28 is quoted: the label reads opponent
move/mon FEATURE blocks, so the trunk is still pushed to encode opponent
features — "zero-information" refers to the opponent's decision, not to the
opponent's existence.

Construction (the AMENDED task — one shared w_move; the per-slot r0 variant
is ~75% unrepresentable by the head's shared scorer and collapses into its
slot_bias, measured in Z1-1):

    s_j     = <w_move, raw_opp_move_block_j>       j = 0..3   (ONE shared w)
    s_4     = <w_glob, raw_global_block>                       (OTHER_MOVE)
    s_5     = <w_bench, maxpool(live bench opp mon blocks)>    (SWITCH)
    logits  = masked_logits(tau * (standardise(s) + b), allow)
    y       ~ Categorical(softmax(logits)), drawn once per row

W = (w_move, w_glob, w_bench) is drawn fresh from a module-constant seed at
every call and NEVER serialised (the theta0 precedent): identical task across
lanes, no checkpoint coupling. The label draw uses a dedicated per-lane
generator handed in by the agent (the `_shuffle_gen` precedent — the default
torch stream carries minibatch randperm, and global `random` carries poke-env
usernames; neither may move).

standardise() uses FROZEN SCALARS (Z1-2), not batch statistics — a per-batch
standardisation would make the target nonstationary in minibatch composition.
The four move slots share ONE (mu, sigma): a per-slot scale would break the
permutation equivariance the shared readout exists to preserve. The per-slot
OFFSETS b[0..3] are legitimate where per-slot scales are not: the production
head carries a scalar slot_bias per slot, so a constant per-slot offset is
exactly representable (Z1-2's criterion text carries the same argument).

Provenance: construction ported from the Stage-0 reference implementation
(results/design_ch2/scripts/z1_1.py, executed 2026-08-17); constants frozen
by Z1-2 (results/design_ch2/z1_2_frozen.json).
"""

from __future__ import annotations

import torch

from rl.common.masking import masked_logits
from rl.networks.opp_action import N_CLASSES, SWITCH

# The synthetic readout's seed. Module constant, never serialised, never
# per-lane: every lane trains against the IDENTICAL task.
ZEROINFO_W_SEED = 20260817

# Z1-2 frozen constants (results/design_ch2/z1_2_frozen.json, 2026-08-20;
# criterion + derivation in the JSON; reviewers' caveats: the tau pick is
# seed-degenerate within its entropy band — stated criterion honoured — and
# per-lane realised entropy spans 0.206-0.271 around the pooled 0.235).
# Standardisation is pooled over the 10 D25-era tapes (5 aux-trained + the 5
# Rung-2 comparator lanes; 76,364 valid rows); offsets are mean-zero gauge.
# Values are ROUNDED copies of the JSON (5-7 figures); the rounding was
# verified label-identical on a full tape (max |delta score| 5.7e-6, review
# SF-4), and tests/test_zeroinfo.py asserts module==JSON to the rounding.
ZEROINFO_FROZEN: dict | None = {
    "tau": 6.94,
    "b": [1.39941, 0.83812, -0.22570, -0.71738, -1.12180, -0.17265],
    "standardisation": {
        "move": [0.264042, 2.432108],
        "global": [0.664521, 0.565015],
        "bench": [0.310099, 1.460024],
    },
}

_REVEALED, _FAINTED, _IS_ACTIVE = 0, 2, 3  # within a raw (mon_dim+1) opp block


def raw_blocks(
    obs: torch.Tensor, tok
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """(global, opp_move_blocks, pooled_opp_mon_block) — the RAW obs blocks
    the head's six entities are built from, sliced off the tokenizer's own
    layout so encoder drift breaks here loudly rather than silently.

    The bench pool mirrors EntityDeepSetsNet's aux features: max over the
    REVEALED, non-fainted, non-active opponent mon blocks, all-zero when no
    such slot exists. Max (not mean) so the synthetic readout sees the same
    pooling nonlinearity the entity path applies."""
    glob = obs[:, : tok.global_dim]
    mv = obs[:, tok.opp_move_off : tok.id_off].view(obs.shape[0], 4, tok.move_dim)
    mons = obs[:, tok.opp_mon_off : tok.opp_act_off].view(
        obs.shape[0], 6, tok.mon_dim + 1
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


def synthetic_scores(obs: torch.Tensor, tok) -> torch.Tensor:
    """The frozen-task class scores: shared-w readouts, frozen
    standardisation, frozen per-class offsets. (N, 6)."""
    if ZEROINFO_FROZEN is None:
        raise RuntimeError(
            "ZEROINFO_FROZEN is unset: Z1-2's constants have not been frozen "
            "into rl/networks/zeroinfo.py — a lane must never train against "
            "an unfrozen task."
        )
    fz = ZEROINFO_FROZEN
    glob, mv, pooled = raw_blocks(obs, tok)
    g = torch.Generator().manual_seed(ZEROINFO_W_SEED)
    w_move = torch.randn(tok.move_dim, generator=g)
    w_glob = torch.randn(tok.global_dim, generator=g)
    w_bench = torch.randn(tok.mon_dim + 1, generator=g)
    mu_m, sd_m = fz["standardisation"]["move"]
    mu_g, sd_g = fz["standardisation"]["global"]
    mu_b, sd_b = fz["standardisation"]["bench"]
    s_mv = (mv @ w_move - mu_m) / sd_m                       # (N, 4), ONE scale
    s_glob = (glob @ w_glob - mu_g) / sd_g                   # (N,)
    s_bench = (pooled @ w_bench - mu_b) / sd_b               # (N,)
    scores = torch.cat(
        [s_mv, s_glob.unsqueeze(-1), s_bench.unsqueeze(-1)], dim=-1
    )
    return scores + torch.as_tensor(fz["b"], dtype=scores.dtype)


def synthetic_labels(
    obs: torch.Tensor,
    allow: torch.Tensor,
    valid: torch.Tensor,
    tok,
    gen: torch.Generator,
) -> tuple[torch.Tensor, dict[str, float]]:
    """Replace the rollout's aux targets with the zero-info draw.

    Takes the CANONICALISED allow/valid untouched — D25's row filter is
    reused verbatim so the trained rows match (~0.80-0.82 labelled_frac) —
    and returns (target, stats). `aux/synth_sampler_entropy` is the sampler's
    exact entropy over valid rows: the manipulation check's A3 term, computed
    not estimated. Rows outside `valid` get a drawn label too (harmless: the
    loss never reads them — same contract as the shuffled placebo)."""
    if allow.shape[-1] != N_CLASSES:
        raise ValueError(f"allow width {allow.shape[-1]} != {N_CLASSES}")
    scores = synthetic_scores(obs, tok)
    logits = masked_logits(float(ZEROINFO_FROZEN["tau"]) * scores, allow)
    p = torch.softmax(logits, dim=-1)
    target = torch.multinomial(p, 1, generator=gen).squeeze(-1)
    ent = -(p.clamp_min(1e-12).log() * p).sum(-1)
    n_valid = int(valid.sum())
    marg = (
        torch.bincount(target[valid], minlength=N_CLASSES).double() / n_valid
        if n_valid
        else torch.zeros(N_CLASSES, dtype=torch.double)
    )
    stats = {
        "aux/synth_sampler_entropy": float(ent[valid].mean()) if n_valid else 0.0,
        "aux/synth_switch_frac": float(marg[SWITCH]),
    }
    return target, stats
