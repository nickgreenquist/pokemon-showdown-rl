"""R0.B ensemble agent: masked log-prob mean over frozen checkpoint actors.

Chapter-3 rung 0's free-compute arm (ch3_search_design_r2.md §4 R0.B): at
each decision, average the members' masked log-softmax and play the argmax.
Deterministic only — this object exists for the locked eval protocol and
refuses to sample. A single-member ensemble reproduces that member's argmax
exactly (R0-c's gate relies on this: log_softmax is monotone in the logits),
so the wrapper provably adds nothing when "disabled".

Masking contract: members share one obs and one mask; masking goes through
`rl/common/masking.masked_logits` (finite -1e8 sentinel, no `mask is None`
branch), applied per member BEFORE log_softmax so a masked action's mean
log-prob stays at the sentinel scale and can never win the argmax. Ties
break toward the LOWEST action index (torch.argmax returns the first
maximum), stated rather than assumed.
"""

from __future__ import annotations

import torch

from rl.common.masking import masked_logits


class EnsembleAgent:
    """Equal-weight log-prob ensemble over PPOAgent members (actors only)."""

    def __init__(self, members):
        assert len(members) >= 1, "ensemble needs at least one member"
        self.members = list(members)
        self.obs_rank = self.members[0].obs_rank
        # R0.B's pre-registered how-we-would-know: ensemble/flip_rate =
        # fraction of decisions where the ensemble argmax differs from the
        # MODAL member argmax (ties toward the lowest action index among the
        # most-common). Counters read by the driver, reset never.
        self.decisions = 0
        self.flips = 0

    def act(self, obs, action_mask=None, deterministic: bool = False) -> int:
        assert deterministic, "R0.B evaluates deterministically only"
        assert action_mask is not None, "masking is a harness contract"
        first = self.members[0]
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=first.device)
        single = obs_t.ndim == self.obs_rank
        if single:
            obs_t = obs_t.unsqueeze(0)
        mask_t = torch.as_tensor(action_mask, dtype=torch.bool, device=first.device)
        logps = []
        with torch.no_grad():
            for m in self.members:
                logits = masked_logits(m.actor(obs_t), mask_t)
                logps.append(torch.log_softmax(logits, dim=-1))
        stacked = torch.stack(logps)  # (M, B, A)
        mean_logp = stacked.mean(dim=0)
        actions = mean_logp.argmax(dim=-1)
        if single:
            self.decisions += 1
            member_choices = stacked[:, 0, :].argmax(dim=-1).tolist()
            counts: dict[int, int] = {}
            for c in member_choices:
                counts[c] = counts.get(c, 0) + 1
            top = max(counts.values())
            modal = min(a for a, n in counts.items() if n == top)
            if int(actions.item()) != modal:
                self.flips += 1
            return int(actions.item())
        return actions.cpu().numpy()
