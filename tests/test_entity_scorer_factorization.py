"""The pointer scorer's ctx half is shared across all ten action slots.

`EntityDeepSetsNet` scores 10 actions by running ONE shared scorer over
`[ctx || entity_i]` pairs. `ctx` is the SAME vector in all ten slots, so the
first Linear's ctx-side columns compute the identical product ten times. A
linear map over a concatenation splits exactly:

    W @ [ctx ; e_i] + b  ==  (W[:, :ctx_in] @ ctx + b)  +  W[:, ctx_in:] @ e_i

This test pins that identity against the LIVE module weights, so it passes both
before and after the factorization lands — it is a statement about the maths,
not about which implementation is currently checked in. If someone changes the
scorer so the identity stops holding (a nonlinearity before the concat, a
per-slot ctx, a bias that is not shared), this fails and says why.

Measured at the production shape when this was written: 1,313,280 -> 428,544
MAC/row for scorer[0], a 67.4% cut on that layer and ~26% of the whole epoch
loop, worth ~1.97x on the scorer forward in isolation.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F

from rl.envs.showdown import OBS_DIM
from rl.networks.entity_deepsets import EntityDeepSetsNet

TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
    pool="max", ctx_sizes=[384, 384], scorer_sizes=[256], value_sizes=[384, 384],
)


def _split_first_linear(scorer, ctx_in: int):
    lin0 = scorer[0]
    return lin0.weight[:, :ctx_in], lin0.weight[:, ctx_in:], lin0.bias


def test_concat_scorer_equals_its_factored_form():
    torch.manual_seed(0)
    net = EntityDeepSetsNet(OBS_DIM, 10, **TRUNK_KWARGS)
    scorer = net.scorer
    ctx_in = scorer[0].in_features - TRUNK_KWARGS["entity_dim"]
    assert ctx_in == TRUNK_KWARGS["ctx_sizes"][-1], (
        "the scorer's input is ctx || entity; if that stops being true the "
        "factorization identity does not apply")

    B, A = 64, 10
    ctx = torch.randn(B, ctx_in)
    entities = torch.randn(B, A, TRUNK_KWARGS["entity_dim"])

    # The form the module uses today: one big concat, ten identical ctx copies.
    pairs = torch.cat([ctx.unsqueeze(1).expand(-1, A, -1), entities], dim=-1)
    concat_logits = scorer(pairs).squeeze(-1)

    # The factored form: the ctx half once per ROW, not once per (row, slot).
    w_ctx, w_ent, b = _split_first_linear(scorer, ctx_in)
    z = F.linear(ctx, w_ctx, b).unsqueeze(1) + F.linear(entities, w_ent)
    h = scorer[1](z)                      # keep the ReLU a MODULE call: the
    for layer in scorer[2:]:              # d22 dormancy probe hooks scorer.1
        h = layer(h)
    factored_logits = h.squeeze(-1)

    d = (concat_logits - factored_logits).abs().max().item()
    scale = concat_logits.abs().max().item()
    assert d < 1e-4, (
        f"the split identity does not hold: max |diff| {d:.3e} on a logit "
        f"scale of {scale:.3f}. The scorer is no longer a linear map over "
        "[ctx || entity] and the factorization must not be applied.")


def test_the_saving_is_what_it_is_claimed_to_be():
    """Guards the ARITHMETIC in the design note, not the implementation.

    If someone widens the scorer or the entity dim, the prize changes and the
    note that quotes 26% of the epoch loop needs revisiting."""
    ctx_in, ent, width, A = 384, 128, 256, 10
    now = A * (ctx_in + ent) * width + A * width
    factored = ctx_in * width + A * ent * width + A * width
    assert now == 1_313_280, now
    assert factored == 428_544, factored
    assert 1 - factored / now > 0.6
