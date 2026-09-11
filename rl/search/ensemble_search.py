"""The ENSEMBLE as the search's PRIOR (and its leaf value), not just as a
leaf evaluator.

`rl/search/agent.py::SearchAgent` consumes its agent through exactly three
surfaces, and nothing else:

    logits, *feats = agent.actor(obs_t, return_features=True)
    q              = torch.softmax(agent.aux_head(*feats), dim=-1)
    v              = agent.critic(batch)

`EnsembleAgent` exposes none of them — it has `members` and `act()` — which is
why `scripts/ch3_eval.py` can build an ensemble OR a search but never both, and
why the composition both 2026-09-10 design reviews named as the cheapest
untested lever was not buildable. This module supplies those three surfaces
over M frozen members so a `SearchAgent` can be handed an ensemble unchanged.

WHY IT IS WORTH BUILDING (measured, not assumed):

  * the masked log-prob ensemble is the only free-compute dial this project has
    CREDITED — CH3 R0.B, +0.036, cell B1 — and on the 100M finals its first
    batch read 0.82667 against a fresh greedy 0.78867 (+0.038, n=3000).
  * the D5 margin gate is worth +0.016 out of sample on the same checkpoints.
  * they are structurally ORTHOGONAL: the ensemble changes the PRIOR and the
    LEAF VALUE, the gate changes the SELECTOR. Neither has ever been measured
    in the presence of the other.

THREE DECISIONS, EACH STATED RATHER THAN IMPLIED.

1. THE PRIOR IS THE LOG-POOL, because that is what `EnsembleAgent` already is.
   `_EnsembleActor` returns the equal-weight mean of the members' masked
   log-softmax. `SearchAgent._forward` then applies
   `softmax(masked_logits(...))` to it, which renormalises the log-pool — the
   normalised GEOMETRIC mean of the members' policies. Its argmax is bitwise
   `EnsembleAgent`'s argmax, so the searched object's prior and the greedy
   ensemble object are the same policy, and a delta between them is attributable
   to the search alone.

2. q IS THE ARITHMETIC MEAN OF THE MEMBERS' OPPONENT MODELS, each computed from
   ITS OWN features. The oppact head is member-specific and consumes that
   member's trunk features, so pooling features across members would feed one
   member's head another member's activations. `_EnsembleActor` therefore
   returns per-member features as a single opaque payload and
   `_EnsembleAuxHead` unpacks it, keeping every member self-consistent.

   The caller applies `softmax` to whatever `aux_head` returns, so this head
   returns `log(mean_prob)` — softmax of a log-probability vector is that
   probability vector exactly (it is already normalised), which is how the
   arithmetic mean survives a softmax the callee does not control. A plain
   logit mean would NOT be the mean opponent model; it would be another
   log-pool, and on a distribution this peaked the two differ materially.

3. THE LEAF VALUE IS THE ARITHMETIC MEAN of the members' critics — the same
   rule `SearchAgent._loo_critic_fn` already uses for the LOO ensemble
   evaluator, so the two forms are comparable. Note the difference in
   MEMBERSHIP: LOO excludes the lane's own critic (it is a screen for "would a
   better evaluator help"), while this includes every member (it is the ladder
   object). They must never be quoted against each other without saying so.

THE NO-OP PROPERTY, which is how this repo gates every search dial: a
ONE-MEMBER ensemble reproduces that member bitwise on all three surfaces —
`log_softmax` is monotone and `softmax(log_softmax(x)) == softmax(x)`, and a
one-element mean is the element. `tests/test_ensemble_search.py` pins it.

NOT WIRED YET, DELIBERATELY. `scripts/ch3_eval.py` builds a SearchAgent from
`agent0` alone; handing it one of these is a three-line change that was NOT
made while the EG10 verdict arm was running, because that queue relaunches on
failure and a resumed arm must not run different code than its finished chunks.
"""

from __future__ import annotations

import torch

from rl.common.masking import masked_logits


class _EnsembleActor:
    """`actor(obs, return_features=True) -> (mean_logprob, per_member_feats)`.

    `mask` is not available here — `SearchAgent._forward` masks the returned
    logits itself — so the members' log_softmax is taken over the FULL action
    set and the caller's `masked_logits` then applies the finite -1e8 sentinel.
    That differs from `EnsembleAgent`, which masks BEFORE log_softmax. The
    ARGMAX is identical either way (masking before or after a monotone
    transform cannot reorder the legal entries among themselves, and a masked
    entry is at the sentinel scale in both), but the renormalised
    probabilities over legal actions are not, so the prior here is the log-pool
    restricted to legal actions rather than renormalised twice. Stated because
    the prior enters the row law as a weight, not only as an argmax.
    """

    def __init__(self, members):
        self._members = members

    def __call__(self, obs_t: torch.Tensor, return_features: bool = False):
        outs = [m.actor(obs_t, return_features=True) for m in self._members]
        logps = torch.stack([torch.log_softmax(o[0], dim=-1) for o in outs])
        mean_logp = logps.mean(dim=0)
        if not return_features:
            return mean_logp
        # One opaque payload: SearchAgent splats `*feats` into aux_head, so a
        # single element arrives as a single positional argument.
        return mean_logp, [tuple(o[1:]) for o in outs]


class _EnsembleAuxHead:
    """`aux_head(per_member_feats) -> log(mean_prob)`.

    The caller softmaxes the result, and softmax of a log-probability vector
    returns that vector, so this delivers the ARITHMETIC mean of the members'
    opponent models through an interface that insists on softmaxing.
    """

    def __init__(self, members):
        self._members = members

    def __call__(self, per_member_feats):
        probs = torch.stack([
            torch.softmax(m.aux_head(*feats), dim=-1)
            for m, feats in zip(self._members, per_member_feats)
        ])
        mean_p = probs.mean(dim=0)
        # log of a normalised mean; clamped because a member can drive a class
        # to exactly 0 in float32 and log(0) would poison the softmax with NaN
        # rather than with the -inf the masking contract forbids anyway.
        return torch.log(mean_p.clamp_min(1e-38))


class _EnsembleCritic:
    """`critic(batch) -> mean over members`, the `_loo_critic_fn` rule."""

    def __init__(self, members):
        self._members = members

    def __call__(self, t: torch.Tensor):
        vs = [m.critic(t).reshape(-1) for m in self._members]
        return torch.stack(vs).mean(dim=0)


class EnsembleSearchAdapter:
    """M frozen PPOAgents behind the surface `SearchAgent` consumes.

    Carries `aux_head` as an attribute because `SearchAgent.__init__` asserts
    `agent.aux_head is not None` — every member must have one, and that is
    checked here rather than allowed to fail later inside a leaf.
    """

    def __init__(self, members):
        members = list(members)
        assert members, "an ensemble needs at least one member"
        for i, m in enumerate(members):
            assert getattr(m, "aux_head", None) is not None, (
                f"ensemble member {i} has no oppact head; a checkpoint without "
                "one can never be searched (rl/search/agent.py's assert)"
            )
        self.members = members
        self.actor = _EnsembleActor(members)
        self.aux_head = _EnsembleAuxHead(members)
        self.critic = _EnsembleCritic(members)
        first = members[0]
        self.obs_rank = first.obs_rank
        self.device = getattr(first, "device", "cpu")

    def act(self, obs, action_mask=None, deterministic: bool = False) -> int:
        """`EnsembleAgent`'s own rule, so a greedy read off this object and a
        greedy read off `EnsembleAgent` are the same policy. Deterministic
        only — the locked eval protocol never samples."""
        assert deterministic, "the locked protocol evaluates deterministically"
        assert action_mask is not None, "masking is a harness contract"
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        single = obs_t.ndim == self.obs_rank
        if single:
            obs_t = obs_t.unsqueeze(0)
        mask_t = torch.as_tensor(action_mask, dtype=torch.bool, device=self.device)
        with torch.no_grad():
            logps = torch.stack([
                torch.log_softmax(masked_logits(m.actor(obs_t), mask_t), dim=-1)
                for m in self.members
            ])
        actions = logps.mean(dim=0).argmax(dim=-1)
        return int(actions.item()) if single else actions.cpu().numpy()
